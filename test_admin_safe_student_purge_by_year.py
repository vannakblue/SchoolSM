import os
import sys
import json
from datetime import date, datetime
from decimal import Decimal
import django

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client, RequestFactory
from apps.accounts.models import User
from apps.academics.models import AcademicYear, Classroom, Subject
from apps.students.models import Student, AcademicYearStudentArchive
from apps.examinations.models import ExamTerm, Grade
from apps.attendance.models import StudentAttendance
from apps.teachers.models import Teacher, TeacherAttendance, TeacherPunchLog

def run_tests():
    print("=== STARTING ADMIN SAFE STUDENT PURGE BY ACADEMIC YEAR TEST SUITE ===")

    # 1. Setup Admin & Regular Users
    admin_user, _ = User.objects.get_or_create(
        username='test_admin_purge',
        defaults={'role': 'ADMIN', 'is_staff': True, 'is_superuser': True}
    )
    admin_user.set_password('Admin@123456')
    admin_user.role = 'ADMIN'
    admin_user.save()

    teacher_user, _ = User.objects.get_or_create(
        username='test_teacher_purge_user',
        defaults={'role': 'TEACHER'}
    )
    teacher_user.set_password('Teacher@123456')
    teacher_user.role = 'TEACHER'
    teacher_user.save()

    client = Client()
    client.force_login(admin_user)
    # Initial cleanup to ensure clean slate
    Student.objects.filter(student_id__startswith='STU-TARGET-').delete()
    Student.objects.filter(student_id__startswith='STU-PRESERVED-').delete()
    Student.objects.filter(student_id__startswith='STU-HARD-').delete()
    TeacherAttendance.objects.filter(teacher__teacher_id='TEA-PURGE-001').delete()
    TeacherPunchLog.objects.filter(teacher__teacher_id='TEA-PURGE-001').delete()
    Teacher.objects.filter(teacher_id='TEA-PURGE-001').delete()
    AcademicYear.objects.filter(name__in=['2026-2027-PURGE-TEST', '2025-2026-PRESERVED', '2024-2025-HARD-PURGE']).delete()

    print("1. [PASS] Setup test admin and user accounts.")

    # 2. Setup Academic Years & Classrooms
    year_target, _ = AcademicYear.objects.get_or_create(
        name='2026-2027-PURGE-TEST',
        defaults={'start_date': date(2026, 9, 1), 'end_date': date(2027, 7, 31), 'is_current': True}
    )
    year_preserved, _ = AcademicYear.objects.get_or_create(
        name='2025-2026-PRESERVED',
        defaults={'start_date': date(2025, 9, 1), 'end_date': date(2026, 7, 31), 'is_current': False}
    )

    class_target, _ = Classroom.objects.get_or_create(
        name='10A-PURGE-TEST',
        academic_year=year_target,
        defaults={'grade_level': 10}
    )
    class_preserved, _ = Classroom.objects.get_or_create(
        name='9A-PRESERVED',
        academic_year=year_preserved,
        defaults={'grade_level': 9}
    )

    subject_math, _ = Subject.objects.get_or_create(
        code='MATH-PURGE-TEST',
        defaults={'name_kh': 'គណិតវិទ្យា', 'name_en': 'Mathematics'}
    )

    # 3. Create Students, Grades, and Attendances for Target Year (2026-2027)
    for i in range(1, 4):
        s = Student.objects.create(
            student_id=f'STU-TARGET-00{i}',
            khmer_name=f'សិស្ស គោលដៅ {i}',
            latin_name=f'Target Student {i}',
            gender='M',
            date_of_birth=date(2010, 1, i),
            classroom=class_target,
            academic_year=year_target,
            phone='012345678',
            status='ACTIVE'
        )

    term_target, _ = ExamTerm.objects.get_or_create(
        name='ខែ តុលា 2026',
        academic_year=year_target,
        defaults={'start_date': date(2026, 10, 20), 'end_date': date(2026, 10, 25)}
    )

    target_students = Student.objects.filter(classroom=class_target)
    for s in target_students:
        Grade.objects.create(
            student=s,
            subject=subject_math,
            exam_term=term_target,
            classroom=class_target,
            score=Decimal('88.50'),
            max_score=Decimal('100.00')
        )
        StudentAttendance.objects.create(
            student=s,
            classroom=class_target,
            date=date(2026, 10, 1),
            status='PRESENT'
        )

    # 4. Create Students, Grades, and Attendances for Preserved Year (2025-2026)
    for i in range(1, 3):
        s_prev = Student.objects.create(
            student_id=f'STU-PRESERVED-00{i}',
            khmer_name=f'សិស្ស រក្សាទុក {i}',
            latin_name=f'Preserved Student {i}',
            gender='F',
            date_of_birth=date(2009, 5, i),
            classroom=class_preserved,
            academic_year=year_preserved,
            phone='098765432',
            status='ACTIVE'
        )

    term_preserved, _ = ExamTerm.objects.get_or_create(
        name='ខែ តុលា 2025',
        academic_year=year_preserved,
        defaults={'start_date': date(2025, 10, 20), 'end_date': date(2025, 10, 25)}
    )

    preserved_students = Student.objects.filter(classroom=class_preserved)
    for s in preserved_students:
        Grade.objects.create(
            student=s,
            subject=subject_math,
            exam_term=term_preserved,
            classroom=class_preserved,
            score=Decimal('92.00'),
            max_score=Decimal('100.00')
        )
        StudentAttendance.objects.create(
            student=s,
            classroom=class_preserved,
            date=date(2025, 10, 1),
            status='PRESENT'
        )

    # 5. Create Teacher Attendance to verify it remains 100% untouched
    teacher_prof, _ = Teacher.objects.get_or_create(
        user=teacher_user,
        defaults={'teacher_id': 'TEA-PURGE-001', 'khmer_name': 'គ្រូ គំរូ', 'latin_name': 'Sample Teacher', 'phone': '012345678', 'specialization': 'Math'}
    )
    t_att = TeacherAttendance.objects.create(
        teacher=teacher_prof,
        date=date(2026, 10, 1),
        status='PRESENT'
    )
    t_punch = TeacherPunchLog.objects.create(
        teacher=teacher_prof,
        date=date(2026, 10, 1),
        punch_time=datetime(2026, 10, 1, 7, 30),
        punch_type='IN',
        method='FINGERPRINT'
    )

    print("2. [PASS] Setup test fixtures (Target year: 3 students/grades/attendances, Preserved year: 2 students/grades/attendances, Teacher records).")

    # 6. Test Preview API
    resp_preview = client.get(f'/students/api/academic-year-purge-preview/?academic_year_id={year_target.id}')
    assert resp_preview.status_code == 200
    data_preview = resp_preview.json()
    assert data_preview['status'] == 'success'
    assert data_preview['students_count'] == 3
    assert data_preview['classrooms_count'] == 1
    assert data_preview['grades_count'] == 3
    assert data_preview['attendances_count'] == 3
    assert data_preview['challenge_text'] == '2026-2027-PURGE-TEST'
    print("3. [PASS] Preview API returned exact count statistics and confirmation challenge code.")

    # 7. Test Security Challenge Validation (Fail on wrong code)
    resp_fail = client.post(
        '/students/api/academic-year-purge-execute/',
        data=json.dumps({
            'academic_year_id': year_target.id,
            'action_type': 'SOFT_UNENROLL',
            'confirmation_text': 'WRONG_CODE'
        }),
        content_type='application/json'
    )
    assert resp_fail.status_code == 400
    assert 'ពាក្យផ្ទៀងផ្ទាត់មិនត្រឹមត្រូវ' in resp_fail.json()['message']
    print("4. [PASS] Security verification prevented execution on invalid confirmation text.")

    # 8. Test Execution Mode 1: Soft Unenroll with Full Archival
    resp_exec_soft = client.post(
        '/students/api/academic-year-purge-execute/',
        data=json.dumps({
            'academic_year_id': year_target.id,
            'action_type': 'SOFT_UNENROLL',
            'confirmation_text': '2026-2027-PURGE-TEST',
            'note': 'Test Soft Purge'
        }),
        content_type='application/json'
    )
    assert resp_exec_soft.status_code == 200
    data_soft = resp_exec_soft.json()
    assert data_soft['status'] == 'success'
    archive_id = data_soft['archive_id']

    # Verify Archive Record
    archive_obj = AcademicYearStudentArchive.objects.get(id=archive_id)
    assert archive_obj.students_count == 3
    assert archive_obj.grades_count == 3
    assert archive_obj.attendances_count == 3
    assert len(archive_obj.archive_payload['students']) == 3
    assert len(archive_obj.archive_payload['grades']) == 3
    assert len(archive_obj.archive_payload['attendances']) == 3
    assert archive_obj.archive_excel is not None

    # Verify Soft Unenroll effect: Students still exist, but unassigned from year/classroom
    for s_id in ['STU-TARGET-001', 'STU-TARGET-002', 'STU-TARGET-003']:
        s_check = Student.objects.get(student_id=s_id)
        assert s_check.classroom is None
        assert s_check.academic_year is None
    print("5. [PASS] Soft Unenroll executed: Complete JSON/Excel archive created, students unenrolled safely.")

    # 9. Test Execution Mode 2: Hard Purge with Full Archival
    # Create Year 2024 for Hard Purge test
    year_hard, _ = AcademicYear.objects.get_or_create(
        name='2024-2025-HARD-PURGE',
        defaults={'start_date': date(2024, 9, 1), 'end_date': date(2025, 7, 31)}
    )
    class_hard, _ = Classroom.objects.get_or_create(name='8A-HARD', academic_year=year_hard)
    s_hard = Student.objects.create(
        student_id='STU-HARD-001',
        khmer_name='សិស្ស លុបទាំងស្រុង',
        latin_name='Hard Delete Student',
        classroom=class_hard,
        academic_year=year_hard,
        date_of_birth=date(2011, 2, 2)
    )

    resp_exec_hard = client.post(
        '/students/api/academic-year-purge-execute/',
        data=json.dumps({
            'academic_year_id': year_hard.id,
            'action_type': 'PURGE_DELETE',
            'confirmation_text': '2024-2025-HARD-PURGE',
            'note': 'Test Hard Purge'
        }),
        content_type='application/json'
    )
    assert resp_exec_hard.status_code == 200
    assert not Student.objects.filter(student_id='STU-HARD-001').exists()
    assert AcademicYearStudentArchive.objects.filter(academic_year=year_hard).exists()
    print("6. [PASS] Hard Purge executed: Archive created and year students deleted from active table.")

    # 10. Test Strict Isolation: Preserved Year & Teacher Attendance are 100% Intact
    assert Student.objects.filter(classroom=class_preserved).count() == 2
    assert Grade.objects.filter(classroom=class_preserved).count() == 2
    assert StudentAttendance.objects.filter(classroom=class_preserved).count() == 2
    assert TeacherAttendance.objects.filter(id=t_att.id).exists()
    assert TeacherPunchLog.objects.filter(id=t_punch.id).exists()
    print("7. [PASS] Strict Isolation: Preserved Academic Year (2025-2026) and Teacher Attendance/Logs are 100% INTACT.")

    # 11. Test Archive Listing & Download Endpoints
    resp_archives = client.get('/students/archives/')
    assert resp_archives.status_code == 200
    assert 'ប័ណ្ណសារ' in resp_archives.content.decode('utf-8')

    resp_dl = client.get(f'/students/archives/{archive_id}/download/')
    assert resp_dl.status_code == 200
    assert resp_dl['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    assert len(resp_dl.content) > 0

    resp_json = client.get(f'/students/archives/{archive_id}/json/')
    assert resp_json.status_code == 200
    assert resp_json.json()['status'] == 'success'
    assert resp_json.json()['students_count'] == 3
    print("8. [PASS] Archive List, Excel Download (.xlsx), and JSON snapshot APIs returned 200 OK.")

    # Cleanup
    year_target.delete()
    year_preserved.delete()
    year_hard.delete()
    admin_user.delete()
    teacher_user.delete()
    teacher_prof.delete()
    t_att.delete()
    t_punch.delete()

    print("\n=== ALL 8 ADMIN SAFE STUDENT PURGE & ARCHIVAL TESTS PASSED 100%! ===")

if __name__ == '__main__':
    run_tests()
