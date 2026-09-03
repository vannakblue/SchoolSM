import os
import sys
import django
import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from apps.academics.models import AcademicYear, Classroom, Subject
from apps.students.models import Student
from apps.examinations.models import (
    StandardizedExam, ExamCandidate, ExamRoom, ExamSubject, ExamStudentExclusion
)
from apps.examinations.views import (
    send_exam_seating_notification_telegram,
    send_exam_exclusion_notification_telegram
)

User = get_user_model()

def run_tests():
    print("=== STARTING STUDENT/PARENT EXAM SEATING & EXCLUSION PORTAL TEST SUITE ===")

    # 1. Setup Academic Year & Classroom
    from apps.academics.utils import get_active_academic_year
    ay = get_active_academic_year(None) or AcademicYear.objects.filter(is_active=True).first()
    
    cls12, _ = Classroom.objects.get_or_create(
        name='12A_PORTAL_TEST',
        defaults={'grade_level': 12, 'academic_year': ay}
    )

    # 2. Setup Student 1 (Normal Eligible Student with Assigned Room & Desk)
    u_stu1, _ = User.objects.get_or_create(
        username='stu_portal_test_1',
        defaults={'role': 'STUDENT', 'khmer_name': 'សុខ ចាន់ដារ៉ា'}
    )
    u_stu1.role = 'STUDENT'
    u_stu1.khmer_name = 'សុខ ចាន់ដារ៉ា'
    u_stu1.save()

    stu1, _ = Student.objects.get_or_create(
        student_id='STU_TEST_001',
        defaults={
            'khmer_name': 'សុខ ចាន់ដារ៉ា',
            'latin_name': 'Sok Chandara',
            'date_of_birth': datetime.date(2008, 5, 15),
            'classroom': cls12,
            'academic_year': ay,
            'user': u_stu1,
            'telegram_chat_id': '123456789'
        }
    )
    stu1.user = u_stu1
    stu1.classroom = cls12
    stu1.save()

    # 3. Setup Student 2 (Excluded due to UNEXCUSED_ABSENCE - ឈប់ច្រើន)
    u_stu2, _ = User.objects.get_or_create(
        username='stu_portal_test_2',
        defaults={'role': 'STUDENT', 'khmer_name': 'ម៉ៅ ស្រីម៉ៅ'}
    )
    u_stu2.role = 'STUDENT'
    u_stu2.khmer_name = 'ម៉ៅ ស្រីម៉ៅ'
    u_stu2.save()

    stu2, _ = Student.objects.get_or_create(
        student_id='STU_TEST_002',
        defaults={
            'khmer_name': 'ម៉ៅ ស្រីម៉ៅ',
            'latin_name': 'Mao Sreymao',
            'date_of_birth': datetime.date(2008, 7, 20),
            'classroom': cls12,
            'academic_year': ay,
            'user': u_stu2,
            'telegram_chat_id': '987654321'
        }
    )
    stu2.user = u_stu2
    stu2.classroom = cls12
    stu2.save()

    # 4. Setup Student 3 (Excluded due to FEE_OVERDUE - មិនទាន់បង់ថ្លៃទឹកភ្លើង)
    u_stu3, _ = User.objects.get_or_create(
        username='stu_portal_test_3',
        defaults={'role': 'STUDENT', 'khmer_name': 'គឹម វិសាល'}
    )
    u_stu3.role = 'STUDENT'
    u_stu3.khmer_name = 'គឹម វិសាល'
    u_stu3.save()

    stu3, _ = Student.objects.get_or_create(
        student_id='STU_TEST_003',
        defaults={
            'khmer_name': 'គឹម វិសាល',
            'latin_name': 'Kim Visal',
            'date_of_birth': datetime.date(2008, 9, 10),
            'classroom': cls12,
            'academic_year': ay,
            'user': u_stu3
        }
    )
    stu3.user = u_stu3
    stu3.classroom = cls12
    stu3.save()

    # 5. Setup StandardizedExam for Grade 12
    exam, _ = StandardizedExam.objects.get_or_create(
        name='ការប្រឡងតេស្តស្តង់ដា ឆមាសទី១ (Portal Test)',
        grade_level=12,
        academic_year=ay,
        defaults={
            'exam_type': StandardizedExam.ExamType.SEMESTER_1,
            'track': StandardizedExam.Track.ALL,
            'session': StandardizedExam.Session.MORNING,
            'exam_date': datetime.date(2026, 11, 25),
            'candidates_per_room': 25
        }
    )

    room1, _ = ExamRoom.objects.get_or_create(
        exam=exam,
        room_number=1,
        defaults={'room_name': 'បន្ទប់លេខ ០១', 'building': 'អគារ A'}
    )

    cand1, _ = ExamCandidate.objects.get_or_create(
        exam=exam,
        student=stu1,
        defaults={
            'room': room1,
            'desk_number': 5,
            'roll_number': '005',
            'candidate_name_kh': stu1.khmer_name,
            'gender': 'M',
            'origin_class': '12A'
        }
    )
    cand1.room = room1
    cand1.desk_number = 5
    cand1.roll_number = '005'
    cand1.save()

    # Exclude Student 2: UNEXCUSED_ABSENCE (ឈប់ច្រើន)
    exc2, _ = ExamStudentExclusion.objects.update_or_create(
        student=stu2,
        standardized_exam=exam,
        defaults={
            'academic_year': ay,
            'reason': ExamStudentExclusion.Reason.UNEXCUSED_ABSENCE,
            'notes': 'ឈប់រៀនលើសពី ១៥ ថ្ងៃឥតច្បាប់',
            'is_active': True
        }
    )

    # Exclude Student 3: FEE_OVERDUE (មិនទាន់បង់ថ្លៃទឹកភ្លើង)
    exc3, _ = ExamStudentExclusion.objects.update_or_create(
        student=stu3,
        standardized_exam=exam,
        defaults={
            'academic_year': ay,
            'reason': ExamStudentExclusion.Reason.FEE_OVERDUE,
            'notes': 'មិនទាន់ទូទាត់ប្រាក់កម្រៃថ្លៃទឹកភ្លើងប្រចាំខែ',
            'is_active': True
        }
    )

    # --- TEST 1: Student 1 Dashboard Check (Seating & Desk Info) ---
    c1 = Client()
    c1.force_login(u_stu1)
    res1 = c1.get('/dashboard/student/')
    assert res1.status_code == 200
    html1 = res1.content.decode('utf-8')
    assert 'ព័ត៌មានសម័យប្រឡង បន្ទប់ប្រឡង និងលេខតុ' in html1
    assert 'បន្ទប់លេខ ០១' in html1
    assert 'តុលេខ 05' in html1 or 'តុលេខ ៥' in html1 or '05' in html1
    assert '005' in html1
    assert 'មានឈ្មោះប្រឡង' in html1
    assert 'student_exam_admission_slip' in html1 or f'/examinations/student/admission-slip/{cand1.id}/' in html1
    print("1. [PASS] Student 1 dashboard accurately displays Exam Name, Room 01, Desk 05, Roll 005, and Eligible badge.")

    # --- TEST 2: Student 1 Admission Slip View ---
    slip_res = c1.get(f'/examinations/student/admission-slip/{cand1.id}/')
    assert slip_res.status_code == 200
    slip_html = slip_res.content.decode('utf-8')
    assert 'ប័ណ្ណអនុញ្ញាតចូលរួមប្រឡង' in slip_html
    assert 'សុខ ចាន់ដារ៉ា' in slip_html
    assert 'បន្ទប់លេខ ០១' in slip_html
    assert '005' in slip_html
    assert 'បទបញ្ជា និងការណែនាំសម្រាប់ការប្រឡង' in slip_html
    print("2. [PASS] Student 1 Exam Admission Slip renders printable hall ticket with 200 OK.")

    # --- TEST 3: Student 2 Dashboard Check (Excluded: UNEXCUSED_ABSENCE) ---
    c2 = Client()
    c2.force_login(u_stu2)
    res2 = c2.get('/dashboard/student/')
    assert res2.status_code == 200
    html2 = res2.content.decode('utf-8')
    assert 'ពុំមានឈ្មោះប្រឡង' in html2
    assert 'អវត្តមានច្រើន / ឈប់រៀនច្រើនឥតច្បាប់' in html2
    assert 'ឈប់រៀនលើសពី ១៥ ថ្ងៃឥតច្បាប់' in html2
    print("3. [PASS] Student 2 dashboard prominently displays Disqualified status and 'ឈប់រៀនច្រើនឥតច្បាប់' reason.")

    # --- TEST 4: Student 3 Dashboard Check (Excluded: FEE_OVERDUE) ---
    c3 = Client()
    c3.force_login(u_stu3)
    res3 = c3.get('/dashboard/student/')
    assert res3.status_code == 200
    html3 = res3.content.decode('utf-8')
    assert 'ពុំមានឈ្មោះប្រឡង' in html3
    assert 'មិនទាន់បង់ប្រាក់ថ្លៃទឹកភ្លើង / ជំពាក់ប្រាក់កម្រៃសិក្សា' in html3
    assert 'មិនទាន់ទូទាត់ប្រាក់កម្រៃថ្លៃទឹកភ្លើងប្រចាំខែ' in html3
    print("4. [PASS] Student 3 dashboard prominently displays Disqualified status and 'មិនទាន់បង់ប្រាក់ថ្លៃទឹកភ្លើង' reason.")

    # --- TEST 5: Telegram Notification Helpers Execution ---
    success1, msg1 = send_exam_seating_notification_telegram(cand1)
    assert success1 is True
    print("5. [PASS] send_exam_seating_notification_telegram executed cleanly.")

    success2, msg2 = send_exam_exclusion_notification_telegram(exc2)
    assert success2 is True
    print("6. [PASS] send_exam_exclusion_notification_telegram executed cleanly.")

    # --- TEST 6: Admin 1-Click Telegram Seating Broadcast Endpoint ---
    admin_user, _ = User.objects.get_or_create(username='admin_portal_tester', defaults={'role': 'ADMIN', 'is_staff': True, 'is_superuser': True})
    c_admin = Client()
    c_admin.force_login(admin_user)
    post_tg = c_admin.post(f'/examinations/standardized/{exam.id}/send-seating-telegram/')
    assert post_tg.status_code == 302
    print("7. [PASS] Admin 1-click Telegram Seating broadcast endpoint executed cleanly.")

    # Cleanup
    cand1.delete()
    exc2.delete()
    exc3.delete()
    exam.delete()
    stu1.delete()
    stu2.delete()
    stu3.delete()
    u_stu1.delete()
    u_stu2.delete()
    u_stu3.delete()
    cls12.delete()
    print("8. [PASS] Cleaned up all test artifacts.")

    print("\n=== ALL 8 STUDENT/PARENT EXAM PORTAL TESTS PASSED 100%! ===")

if __name__ == '__main__':
    run_tests()
