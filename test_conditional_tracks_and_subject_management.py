import os
import sys
import django
from decimal import Decimal

if sys.stdout and sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.academics.models import AcademicYear, GradeLevelRule, Subject
from apps.examinations.models import StandardizedExam, ExamSubject, ExamCandidate, CandidateSubjectScore


def run_tests():
    print("================================================================================")
    print("TEST: CONDITIONAL TRACK DISPLAY & ADMIN SUBJECT / SCORE MANAGEMENT")
    print("================================================================================")

    admin_user = User.objects.filter(role='ADMIN').first()
    if not admin_user:
        admin_user = User.objects.create_superuser('admin_test_tracks', 'admin@example.com', 'pass123', role='ADMIN')

    client = Client()
    client.force_login(admin_user)

    year = AcademicYear.objects.filter(is_current=True).first() or AcademicYear.objects.first()

    # -------------------------------------------------------------------------
    # TEST 1: Grade 7 Exam (General Track, No Science/Social tracks)
    # -------------------------------------------------------------------------
    print("\n--- Test 1: Grade 7 Exam - Verify Science/Social presets hidden ---")
    exam_g7 = StandardizedExam.objects.create(
        name="សម័យប្រឡងតេស្តស្តង់ដា ថ្នាក់ទី ៧",
        academic_year=year,
        grade_level=7,
        track='GENERAL',
        exam_date='2026-11-20',
        session='MORNING'
    )

    edit_url_g7 = f"/examinations/standardized/{exam_g7.id}/edit/"
    res_g7 = client.get(edit_url_g7)
    assert res_g7.status_code == 200, f"Expected 200, got {res_g7.status_code}"

    content_g7 = res_g7.content.decode('utf-8')

    # Science / Social preset buttons must NOT be present for Grade 7
    assert '៧ វិទ្យាសាស្ត្រ' not in content_g7, "Hardcoded '៧ វិទ្យាសាស្ត្រ' should NOT appear!"
    assert '៧ សង្គម' not in content_g7, "Hardcoded '៧ សង្គម' should NOT appear!"
    assert 'វិទ្យាសាស្ត្រ (៧ មុខ)' not in content_g7, "Science preset button must NOT be shown for Grade 7!"
    assert 'សង្គម (៧ មុខ)' not in content_g7, "Social preset button must NOT be shown for Grade 7!"

    # MoEYS Standard button MUST be present
    assert 'ទាញយកមុខវិជ្ជាស្តង់ដារក្រសួង' in content_g7, "Should display MoEYS Standard subjects button!"
    assert 'ជ្រើសរើសមុខវិជ្ជា' in content_g7, "Should display Select Subjects button!"
    assert 'មិនទាន់មានមុខវិជ្ជាប្រឡងនៅឡើយទេ' in content_g7, "Should show empty table message when no subjects!"
    assert f'ទាញយកមុខវិជ្ជាស្តង់ដារក្រសួង (ថ្នាក់ទី {exam_g7.grade_level})' in content_g7, "Should show 1-click button in empty table!"

    print("✓ Grade 7 Edit page correctly hides Science/Social presets and displays MoEYS standard button.")

    # -------------------------------------------------------------------------
    # TEST 2: Attempting to apply SCIENCE_7 on Grade 7 should fail gracefully
    # -------------------------------------------------------------------------
    print("\n--- Test 2: Guard check - applying SCIENCE_7 on Grade 7 rejected ---")
    preset_url_g7 = f"/examinations/standardized/{exam_g7.id}/subjects/apply-preset/"
    res_preset_err = client.post(preset_url_g7, data={'preset': 'SCIENCE_7'}, content_type='application/json')
    assert res_preset_err.status_code == 400
    assert 'ថ្នាក់ចំណេះទូទៅ មិនមានការបែងចែក' in res_preset_err.json()['message']
    print("✓ API guard successfully prevents setting Science/Social track presets on Grade 7.")

    # -------------------------------------------------------------------------
    # TEST 3: Apply ALL_MOEYS on Grade 7
    # -------------------------------------------------------------------------
    print("\n--- Test 3: 1-Click Load MoEYS standard subjects on Grade 7 ---")
    res_preset_ok = client.post(preset_url_g7, data={'preset': 'ALL_MOEYS'}, content_type='application/json')
    assert res_preset_ok.status_code == 200
    g7_sub_count = exam_g7.exam_subjects.count()
    assert g7_sub_count >= 10, f"Expected MoEYS curriculum subjects for Grade 7, got {g7_sub_count}"
    print(f"✓ Successfully loaded {g7_sub_count} official MoEYS subjects for Grade 7.")

    # -------------------------------------------------------------------------
    # TEST 4: Admin removing a subject from Grade 7 exam via Delete API
    # -------------------------------------------------------------------------
    print("\n--- Test 4: Admin removing individual subject ---")
    first_sub = exam_g7.exam_subjects.first()
    sub_name = first_sub.subject.name_kh
    del_url = f"/examinations/standardized/{exam_g7.id}/subjects/{first_sub.id}/delete/"
    res_del = client.post(del_url)
    assert res_del.status_code == 200
    assert exam_g7.exam_subjects.count() == g7_sub_count - 1
    assert not exam_g7.exam_subjects.filter(id=first_sub.id).exists()
    print(f"✓ Successfully deleted subject «{sub_name}» from exam and updated total count to {exam_g7.exam_subjects.count()}.")

    # -------------------------------------------------------------------------
    # TEST 5: Admin custom editing max_score & coefficient on form submit
    # -------------------------------------------------------------------------
    print("\n--- Test 5: Admin custom score and coefficient editing ---")
    target_es = exam_g7.exam_subjects.first()
    form_post_data = {
        'name': exam_g7.name,
        'academic_year': year.id,
        'exam_type': 'OTHER',
        'grade_level': exam_g7.grade_level,
        'track': exam_g7.track,
        'session': exam_g7.session,
        'exam_date': '2026-11-20',
        'candidates_per_room': 25,
        'grading_method': 'BOTH',
        f'max_score_{target_es.id}': '100',
        f'coefficient_{target_es.id}': '2.0',
        f'session_{target_es.id}': 'MORNING',
        f'exam_date_{target_es.id}': '2026-11-20'
    }
    res_edit_post = client.post(edit_url_g7, data=form_post_data)
    assert res_edit_post.status_code == 302
    target_es.refresh_from_db()
    assert target_es.max_score == Decimal('100.00'), f"Expected 100.00, got {target_es.max_score}"
    assert target_es.coefficient == Decimal('2.00'), f"Expected 2.00, got {target_es.coefficient}"
    print(f"✓ Successfully customized score to {target_es.max_score} and coefficient to {target_es.coefficient}.")

    # -------------------------------------------------------------------------
    # TEST 6: Grade 11 Exam (Divided into Science & Social tracks)
    # -------------------------------------------------------------------------
    print("\n--- Test 6: Grade 11 Exam - Verify Science and Social presets appear ---")
    exam_g11 = StandardizedExam.objects.create(
        name="សម័យប្រឡងតេស្តស្តង់ដា ថ្នាក់ទី ១១",
        academic_year=year,
        grade_level=11,
        track='SCIENCE',
        exam_date='2026-11-20',
        session='AFTERNOON'
    )

    edit_url_g11 = f"/examinations/standardized/{exam_g11.id}/edit/"
    res_g11 = client.get(edit_url_g11)
    assert res_g11.status_code == 200

    content_g11 = res_g11.content.decode('utf-8')
    assert 'វិទ្យាសាស្ត្រ (៧ មុខ)' in content_g11, "Science preset MUST appear for Grade 11!"
    assert 'សង្គម (៧ មុខ)' in content_g11, "Social preset MUST appear for Grade 11!"

    # Apply Science 7 preset
    preset_url_g11 = f"/examinations/standardized/{exam_g11.id}/subjects/apply-preset/"
    res_preset_sci = client.post(preset_url_g11, data={'preset': 'SCIENCE_7'}, content_type='application/json')
    assert res_preset_sci.status_code == 200
    assert exam_g11.exam_subjects.count() == 7
    math_sub = exam_g11.exam_subjects.filter(subject__name_kh='គណិតវិទ្យា').first()
    assert math_sub is not None
    assert math_sub.max_score == Decimal('125.00')
    assert math_sub.coefficient == Decimal('2.50')
    print("✓ Grade 11 correctly features Science & Social presets and applies Science 7 (Math 125, 2.5).")

    # Clean up test exams
    exam_g7.delete()
    exam_g11.delete()

    print("\n================================================================================")
    print("🎉 ALL TESTS PASSED 100%! REQUIREMENT FULFILLED COMPLETELY.")
    print("================================================================================")


if __name__ == '__main__':
    run_tests()
