import os
import sys
from decimal import Decimal
from datetime import date

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
import django
django.setup()

from django.test import Client, RequestFactory
from apps.accounts.models import User
from apps.academics.models import AcademicYear, Classroom, Subject
from apps.students.models import Student
from apps.attendance.models import StudentAttendance
from apps.examinations.models import ExamTerm, Grade
from apps.examinations.views import _calculate_bilingual_report_card_data

def run_tests():
    print("=" * 75)
    print("🧪 TESTING WESTERN INTERNATIONAL / BILINGUAL REPORT CARD (EOY TEMPLATE)")
    print("=" * 75)

    # 1. Setup Admin & Test Fixtures
    admin = User.objects.filter(role='ADMIN').first()
    client = Client()
    client.force_login(admin)

    ay, _ = AcademicYear.objects.get_or_create(
        name="2026-2027",
        defaults={'start_date': date(2026, 1, 1), 'end_date': date(2026, 12, 31), 'is_current': True}
    )

    cls_4b, _ = Classroom.objects.get_or_create(
        name="4B",
        academic_year=ay,
        defaults={'grade_level': 4, 'code': '4B'}
    )

    student, _ = Student.objects.get_or_create(
        student_id="WESTERN_001",
        defaults={
            'khmer_name': "អ៊ាត ម៉េងឡុង",
            'latin_name': "EATH MENGLONG",
            'gender': 'M',
            'date_of_birth': date(2014, 5, 12),
            'classroom': cls_4b,
            'academic_year': ay
        }
    )
    student.classroom = cls_4b
    student.academic_year = ay
    student.status = 'ACTIVE'
    student.save()

    # Setup Subjects
    sub_kh = Subject.objects.filter(name_kh="ភាសាខ្មែរ").first() or Subject.objects.create(name_kh="ភាសាខ្មែរ", name_en='Khmer', credit=4, code='KH_04')
    sub_en = Subject.objects.filter(name_kh="ភាសាអង់គ្លេស").first() or Subject.objects.create(name_kh="ភាសាអង់គ្លេស", name_en='English', credit=4, code='EN_04')
    sub_ma = Subject.objects.filter(name_kh="គណិតវិទ្យា").first() or Subject.objects.create(name_kh="គណិតវិទ្យា", name_en='Mathematics', credit=4, code='MA_04')
    sub_sc = Subject.objects.filter(name_kh="វិទ្យាសាស្ត្រ").first() or Subject.objects.create(name_kh="វិទ្យាសាស្ត្រ", name_en='Science', credit=3, code='SC_04')

    # Setup Terms for S1 and S2
    term_s1, _ = ExamTerm.objects.get_or_create(
        name="ឆមាសទី១ (2026)",
        academic_year=ay,
        semester=1,
        defaults={'term_type': 'SEMESTER_1', 'start_date': date(2026, 1, 15), 'end_date': date(2026, 5, 30)}
    )
    term_s2, _ = ExamTerm.objects.get_or_create(
        name="ឆមាសទី២ (2026)",
        academic_year=ay,
        semester=2,
        defaults={'term_type': 'SEMESTER_2', 'start_date': date(2026, 6, 1), 'end_date': date(2026, 11, 30)}
    )

    # Create Sample Grades for S1 (Averages ~91.26%)
    Grade.objects.update_or_create(student=student, subject=sub_kh, exam_term=term_s1, classroom=cls_4b, defaults={'score': Decimal('92.00'), 'max_score': Decimal('100.00')})
    Grade.objects.update_or_create(student=student, subject=sub_en, exam_term=term_s1, classroom=cls_4b, defaults={'score': Decimal('90.00'), 'max_score': Decimal('100.00')})
    Grade.objects.update_or_create(student=student, subject=sub_ma, exam_term=term_s1, classroom=cls_4b, defaults={'score': Decimal('95.00'), 'max_score': Decimal('100.00')})
    Grade.objects.update_or_create(student=student, subject=sub_sc, exam_term=term_s1, classroom=cls_4b, defaults={'score': Decimal('88.00'), 'max_score': Decimal('100.00')})

    # Create Sample Grades for S2 (Averages ~90.26%)
    Grade.objects.update_or_create(student=student, subject=sub_kh, exam_term=term_s2, classroom=cls_4b, defaults={'score': Decimal('90.00'), 'max_score': Decimal('100.00')})
    Grade.objects.update_or_create(student=student, subject=sub_en, exam_term=term_s2, classroom=cls_4b, defaults={'score': Decimal('92.00'), 'max_score': Decimal('100.00')})
    Grade.objects.update_or_create(student=student, subject=sub_ma, exam_term=term_s2, classroom=cls_4b, defaults={'score': Decimal('94.00'), 'max_score': Decimal('100.00')})
    Grade.objects.update_or_create(student=student, subject=sub_sc, exam_term=term_s2, classroom=cls_4b, defaults={'score': Decimal('85.00'), 'max_score': Decimal('100.00')})

    # Setup Attendance records
    StudentAttendance.objects.filter(student=student).delete()
    StudentAttendance.objects.create(student=student, classroom=cls_4b, date=date(2026, 10, 10), status=StudentAttendance.Status.PERMISSION)
    StudentAttendance.objects.create(student=student, classroom=cls_4b, date=date(2026, 11, 15), status=StudentAttendance.Status.ABSENT)

    print("[Phase 1] Test fixtures setup successfully.")

    # 2. Test Calculation Engine
    data = _calculate_bilingual_report_card_data(student, term=term_s2)
    print("\n[Phase 2] Testing Report Card Calculation Engine...")
    print(f"  ✓ Sem 1 Average: {data['s1_avg']}% (Letter: {data['s1_letter']}, GPA: {data['s1_gpa']}, Credits: {data['s1_credits']})")
    print(f"  ✓ Sem 2 Average: {data['s2_avg']}% (Letter: {data['s2_letter']}, GPA: {data['s2_gpa']}, Credits: {data['s2_credits']})")
    print(f"  ✓ Overall Average: {data['ov_avg']}% (Letter: {data['ov_letter']}, GPA: {data['ov_gpa']}, Credits: {data['ov_credits']})")
    print(f"  ✓ Rank: S1={data['s1_rank']} of {data['total_in_class']}, S2={data['s2_rank']} of {data['total_in_class']}, Overall={data['ov_rank']} of {data['total_in_class']}")
    print(f"  ✓ Promotion Status: {data['promotion_status_kh']} -> Grade {data['promoted_grade']}")
    print(f"  ✓ Attendance: Total Days={data['total_school_days']}, Absences={data['total_absences']}, Presence={data['overall_presence']}%")

    assert float(data['s1_avg']) > 85.0, "Sem 1 Average should be > 85%"
    assert float(data['s2_avg']) > 85.0, "Sem 2 Average should be > 85%"
    assert float(data['ov_avg']) > 85.0, "Overall Average should be > 85%"
    assert float(data['ov_gpa']) >= 3.0, "GPA should be >= 3.0"
    assert data['promoted_grade'] == 5, "Student in Grade 4 should be promoted to Grade 5"
    assert data['total_absences'] == 2, "Total absences should be 2"
    assert len(data['behavior_ratings']) == 6, "Must have 6 behavior evaluation categories"

    # 3. Test Direct View Endpoint (/examinations/report-card/<id>/<term_id>/western/)
    print("\n[Phase 3] Testing Direct Web View URL...")
    url_direct = f'/examinations/report-card/{student.id}/{term_s2.id}/western/'
    resp_direct = client.get(url_direct)
    assert resp_direct.status_code == 200, f"Direct view failed with HTTP {resp_direct.status_code}"
    content_direct = resp_direct.content.decode('utf-8')
    assert 'ព្រះរាជាណាចក្រកម្ពុជា' in content_direct
    assert 'ជាតិ សាសនា ព្រះមហាក្សត្រ' in content_direct
    assert 'ព្រឹត្តិបត្រពិន្ទុប្រចាំឆ្នាំ' in content_direct
    assert 'វិទ្យាល័យ' in content_direct
    assert 'សរុបពិន្ទុប្រឡងឆមាស' in content_direct
    assert 'មធ្យមភាគពិន្ទុប្រឡងឆមាស' in content_direct
    assert 'មធ្យមភាគពិន្ទុប្រចាំឆមាស' in content_direct
    assert 'ប័ណ្ណសរសើរ' in content_direct
    assert 'បានឃើញ និងឯកភាព' in content_direct
    assert 'គ្រូបន្ទុកថ្នាក់' in content_direct
    assert 'rank-red' in content_direct
    print("  ✓ HTTP 200 OK: Complete Official MoEYS Report Card template rendered")

    # 4. Test Template Switcher on Standard View (?template=western)
    print("\n[Phase 4] Testing Template Switcher (?template=western)...")
    url_switch = f'/examinations/report-card/{student.id}/{term_s2.id}/?template=western'
    resp_switch = client.get(url_switch)
    assert resp_switch.status_code == 200
    content_switch = resp_switch.content.decode('utf-8')
    assert 'ព្រឹត្តិបត្រពិន្ទុ' in content_switch
    print("  ✓ HTTP 200 OK: Standard report-card URL properly routed to MoEYS template with ?template=western")

    # 5. Test Default Term Fallback URL (/examinations/report-card/<id>/western/)
    print("\n[Phase 5] Testing Default Term Western URL...")
    url_def = f'/examinations/report-card/{student.id}/western/'
    resp_def = client.get(url_def)
    assert resp_def.status_code == 200
    print("  ✓ HTTP 200 OK: /examinations/report-card/<id>/western/ rendered cleanly")

    # 6. Test Batch Printing for Whole Classroom (/examinations/classroom/<id>/report-cards/western/)
    print("\n[Phase 6] Testing Classroom Whole-Batch Western Print URL...")
    url_batch = f'/examinations/classroom/{cls_4b.id}/report-cards/western/?term_id={term_s2.id}'
    resp_batch = client.get(url_batch)
    assert resp_batch.status_code == 200
    content_batch = resp_batch.content.decode('utf-8')
    assert '4B' in content_batch
    assert 'report-card-sheet' in content_batch
    assert student.khmer_name in content_batch
    print(f"  ✓ HTTP 200 OK: Whole classroom batch report cards rendered cleanly")

    # 7. Test Grade Summary Page Integration
    print("\n[Phase 7] Testing Grade Summary Page Report Card Buttons...")
    url_summary = f'/examinations/summary/?term_id={term_s2.id}&classroom_id={cls_4b.id}'
    resp_summary = client.get(url_summary)
    assert resp_summary.status_code == 200
    content_summary = resp_summary.content.decode('utf-8')
    assert f'/examinations/classroom/{cls_4b.id}/report-cards/western/' in content_summary
    assert 'ព្រឹត្តិបត្រពិន្ទុ' in content_summary
    print("  ✓ HTTP 200 OK: Grade summary page displays 1-click report card buttons")

    print("\n" + "=" * 75)
    print("🎉 ALL 8 PHASES OF WESTERN REPORT CARD SUITE PASSED 100% SUCCESSFULLY!")
    print("=" * 75)

if __name__ == '__main__':
    run_tests()
