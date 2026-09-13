import os
import sys
import django

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from decimal import Decimal
from django.utils import timezone
from django.test import Client
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.teachers.models import Teacher
from apps.students.models import Student
from apps.academics.models import AcademicYear, Classroom, Subject, ClassSubject, GradeLevelRule
from apps.examinations.models import ExamTerm, Grade
from django.test.utils import setup_test_environment


def run_tests():
    setup_test_environment()
    print("=" * 70)
    print("TEST SUITE: Active Exam Term Locking for Teachers (Portal & Mobile App)")
    print("=" * 70)

    # 1. Setup Test Environment
    print("\n[Step 1] Preparing academic year, exam terms, classroom and subjects...")
    year = AcademicYear.objects.filter(is_current=True).first() or AcademicYear.objects.first()
    if not year:
        year = AcademicYear.objects.create(name="2026-2027", start_date="2026-09-01", end_date="2027-07-15", is_current=True)

    # Term A (Active Term)
    term_a, _ = ExamTerm.objects.get_or_create(
        name="សម័យប្រឡងតេស្ត A (សកម្ម)",
        academic_year=year,
        defaults={
            'start_date': timezone.now().date(),
            'end_date': timezone.now().date() + timezone.timedelta(days=7),
            'is_active_for_grading': True,
            'is_grading_locked': False,
        }
    )
    term_a.set_as_active_grading_term()

    # Term B (Inactive Term)
    term_b, _ = ExamTerm.objects.get_or_create(
        name="សម័យប្រឡងតេស្ត B (បិទ)",
        academic_year=year,
        defaults={
            'start_date': timezone.now().date() - timezone.timedelta(days=30),
            'end_date': timezone.now().date() - timezone.timedelta(days=23),
            'is_active_for_grading': False,
            'is_grading_locked': False,
        }
    )
    term_b.is_active_for_grading = False
    term_b.save()

    classroom, _ = Classroom.objects.get_or_create(
        name="ថ្នាក់ទី 7T (Lock Test)",
        academic_year=year,
        defaults={'grade_level': 7, 'capacity': 40}
    )

    subject, _ = Subject.objects.get_or_create(
        code="TEST_SUB_LOCK",
        defaults={'name_kh': "គណិតវិទ្យាតេស្ត", 'name_en': "Math Test"}
    )
    GradeLevelRule.objects.get_or_create(
        grade_level=7,
        track=classroom.track,
        subject=subject,
        defaults={'max_score': Decimal('100.00')}
    )

    # Users: Admin & Teacher
    admin_user = User.objects.filter(role=User.Role.ADMIN).first() or User.objects.filter(is_superuser=True).first()
    if not admin_user:
        admin_user = User.objects.create_superuser('admin_test_lock', 'admin_lock@school.edu.kh', 'admin123')
    else:
        admin_user.set_password('admin123')
        admin_user.is_active = True
        admin_user.save()

    teacher_user, _ = User.objects.get_or_create(
        username="teacher_lock_test",
        defaults={'role': User.Role.TEACHER, 'first_name': "តេស្ត", 'last_name': "គ្រូ"}
    )
    teacher_user.role = User.Role.TEACHER
    teacher_user.is_active = True
    teacher_user.set_password('admin123')
    teacher_user.save()

    teacher_profile, _ = Teacher.objects.get_or_create(
        user=teacher_user,
        defaults={'teacher_id': "TCH-LOCK-01", 'khmer_name': "គ្រូ តេស្ត សោរ"}
    )

    # Assign teacher to classroom & subject
    ClassSubject.objects.get_or_create(
        classroom=classroom,
        subject=subject,
        defaults={'teacher': teacher_profile}
    )

    # Student
    stu_user, _ = User.objects.get_or_create(
        username="student_lock_test",
        defaults={'role': User.Role.STUDENT}
    )
    stu_user.role = User.Role.STUDENT
    stu_user.is_active = True
    stu_user.set_password('admin123')
    stu_user.save()

    student_obj, _ = Student.objects.get_or_create(
        user=stu_user,
        defaults={
            'student_id': "STU-LOCK-01",
            'khmer_name': "សិស្ស តេស្ត សោរ",
            'gender': "M",
            'date_of_birth': timezone.now().date() - timezone.timedelta(days=5000),
            'classroom': classroom,
            'academic_year': year,
            'status': "ACTIVE"
        }
    )
    student_obj.classroom = classroom
    student_obj.save()

    print(f"  ✓ Active Term: {term_a.name} (is_active_for_grading={term_a.is_active_for_grading})")
    print(f"  ✓ Inactive Term: {term_b.name} (is_active_for_grading={term_b.is_active_for_grading})")
    print(f"  ✓ Class: {classroom.name}, Teacher: {teacher_profile.khmer_name}")

    # 2. Test Model Methods
    print("\n[Step 2] Testing ExamTerm model methods...")
    active_term = ExamTerm.get_active_grading_term(academic_year=year)
    assert active_term.id == term_a.id, f"Expected {term_a.id}, got {active_term.id}"
    print(f"  ✓ ExamTerm.get_active_grading_term correctly returns: {active_term.name}")

    # 3. Test Web Portal (grade_entry_matrix)
    print("\n[Step 3] Testing Web Portal (grade_entry_matrix view)...")
    web_client = Client()

    # Teacher login
    web_client.force_login(teacher_user)
    res = web_client.get(f"/examinations/matrix/?term={term_b.id}&classroom={classroom.id}")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    # Context must lock selected_term to active_term (term_a), ignoring query param term_b!
    assert res.context['selected_term'].id == term_a.id, "Teacher must be locked to active term!"
    assert res.context['can_select_term'] is False, "Teacher can_select_term must be False!"
    # Verify disabled styling in HTML
    content_html = res.content.decode('utf-8')
    assert "កំណត់ដោយ Admin" in content_html, "Lock badge must appear in HTML for teacher!"
    assert "disabled" in content_html, "Disabled input must appear for teacher!"
    print("  ✓ Teacher GET request is strictly locked to Active Term A in Portal UI.")

    # Teacher attempting POST with inactive term_b must be blocked!
    post_data = {
        'term': term_b.id,
        'classroom': classroom.id,
        f"score_{student_obj.id}_{subject.id}": "85.00"
    }
    post_res = web_client.post("/examinations/matrix/", post_data, follow=True)
    assert any("មិនអនុញ្ញាត" in m.message for m in post_res.context['messages']), "Teacher must be blocked from POSTing to inactive term!"
    print("  ✓ Teacher POST to inactive term was strictly blocked.")

    # Teacher POST to active term_a succeeds!
    post_data_valid = {
        'term': term_a.id,
        'classroom': classroom.id,
        f"score_{student_obj.id}_{subject.id}": "92.50"
    }
    post_res_valid = web_client.post("/examinations/matrix/", post_data_valid, follow=True)
    grade_obj = Grade.objects.filter(student=student_obj, exam_term=term_a, subject=subject).first()
    assert grade_obj is not None and grade_obj.score == Decimal('92.50'), "Valid grade save failed!"
    print(f"  ✓ Teacher POST to active term A succeeded. Score: {grade_obj.score}")

    # 4. Test Mobile REST API
    print("\n[Step 4] Testing Mobile REST API...")
    api_client = APIClient()

    # Login teacher via Mobile Auth
    login_res = api_client.post('/api/v1/auth/login/', {
        'username': 'teacher_lock_test',
        'password': 'admin123'
    }, format='json')
    assert login_res.status_code == 200, f"Login failed: {login_res.data}"
    token = login_res.data['tokens']['access']
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    # Test GET metadata
    meta_res = api_client.get('/api/v1/grades/teacher-entry/meta/')
    assert meta_res.status_code == 200, f"Expected 200, got {meta_res.status_code}: {meta_res.data}"
    meta_data = meta_res.data
    assert meta_data['can_select_term'] is False, "Teacher can_select_term must be False in Mobile API!"
    assert meta_data['active_term_id'] == term_a.id, "active_term_id must match active term A!"
    assert len(meta_data['exam_terms']) == 1, "Teacher must only receive the active exam term in Mobile API!"
    assert meta_data['exam_terms'][0]['id'] == term_a.id
    print(f"  ✓ Mobile Metadata API returned: can_select_term={meta_data['can_select_term']}, active_term_id={meta_data['active_term_id']}")
    print(f"  ✓ Only active exam term sent to teacher mobile app: {meta_data['exam_terms'][0]['name']}")

    # Teacher attempting POST save to inactive term_b via Mobile API must receive 403 Forbidden!
    bad_save_res = api_client.post('/api/v1/grades/teacher-entry/save/', {
        'exam_term_id': term_b.id,
        'classroom_id': classroom.id,
        'scores': [{'student_id': student_obj.id, 'subject_id': subject.id, 'score': 70.0}]
    }, format='json')
    assert bad_save_res.status_code == 403, f"Expected 403, got {bad_save_res.status_code}"
    print(f"  ✓ Mobile Grade Save to inactive term correctly rejected with 403: {bad_save_res.data.get('message')}")

    # Teacher saving to active term_a via Mobile API succeeds!
    good_save_res = api_client.post('/api/v1/grades/teacher-entry/save/', {
        'exam_term_id': term_a.id,
        'classroom_id': classroom.id,
        'scores': [{'student_id': student_obj.id, 'subject_id': subject.id, 'score': 88.0}]
    }, format='json')
    assert good_save_res.status_code == 200, f"Expected 200, got {good_save_res.status_code}: {good_save_res.data}"
    grade_obj.refresh_from_db()
    assert grade_obj.score == Decimal('88.00'), f"Score was not updated: {grade_obj.score}"
    print(f"  ✓ Mobile Grade Save to active term A succeeded: Score = {grade_obj.score}")

    # 5. Test Admin 1-Click Toggle to Term B
    print("\n[Step 5] Testing Admin 1-Click Toggle (Switch active grading term to B)...")
    admin_web_client = Client()
    admin_web_client.force_login(admin_user)
    toggle_res = admin_web_client.get(f"/examinations/terms/{term_b.id}/toggle-active-grading/", follow=True)
    assert toggle_res.status_code == 200

    term_a.refresh_from_db()
    term_b.refresh_from_db()
    assert term_b.is_active_for_grading is True, "Term B should now be active!"
    assert term_a.is_active_for_grading is False, "Term A should now be deactivated!"
    print(f"  ✓ Admin toggle successful: Now Term B is active ({term_b.is_active_for_grading}) and Term A is deactivated ({term_a.is_active_for_grading})")

    # Now Teacher is locked to Term B!
    meta_res_2 = api_client.get('/api/v1/grades/teacher-entry/meta/')
    assert meta_res_2.data['active_term_id'] == term_b.id
    print(f"  ✓ Teacher Mobile app immediately switches lock to newly activated Term B: {meta_res_2.data['active_term_name']}")

    # Clean up test terms and records
    print("\n[Step 6] Cleaning up test records...")
    Grade.objects.filter(exam_term__in=[term_a, term_b]).delete()
    term_a.delete()
    term_b.delete()
    classroom.delete()
    teacher_profile.delete()
    teacher_user.delete()
    student_obj.delete()
    stu_user.delete()
    subject.delete()
    print("  ✓ Cleanup complete.")

    print("\n" + "=" * 70)
    print("🎉 ALL ACTIVE EXAM TERM LOCKING TESTS PASSED 100%!")
    print("=" * 70)


if __name__ == '__main__':
    run_tests()
