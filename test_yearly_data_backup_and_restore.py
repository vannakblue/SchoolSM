import os
import sys
import django
from decimal import Decimal
from datetime import date

if sys.stdout and sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from apps.academics.models import AcademicYear, Classroom, GradeLevel, Subject
from apps.students.models import Student
from apps.examinations.models import ExamTerm, Grade
from apps.attendance.models import StudentAttendance
from apps.students.models import AcademicYearStudentArchive
from apps.tools.backup_utils import create_academic_year_backup, restore_academic_year_backup
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from apps.students.views import api_restore_student_archive

User = get_user_model()

def run_tests():
    print("=== Testing Academic Year Backup & Restore Pipeline ===")

    # Setup Academic Year
    ay, _ = AcademicYear.objects.get_or_create(
        name="2025-2026 Test Year",
        defaults={'start_date': date(2025, 10, 1), 'end_date': date(2026, 7, 31), 'is_current': False}
    )

    classroom, _ = Classroom.objects.get_or_create(
        name="10A Test",
        academic_year=ay,
        defaults={'grade_level': 10, 'code': '10A-TEST'}
    )

    subj, _ = Subject.objects.get_or_create(
        code="MATH-10-TEST",
        defaults={'name_en': 'Mathematics Test', 'name_kh': 'គណិតវិទ្យា (តេស្ត)'}
    )

    student, _ = Student.objects.update_or_create(
        student_id="TEST-YEAR-001",
        defaults={
            'khmer_name': 'សុខ តេស្តឆ្នាំ',
            'gender': Student.Gender.MALE,
            'date_of_birth': date(2009, 5, 12),
            'academic_year': ay,
            'classroom': classroom
        }
    )

    exam_term, _ = ExamTerm.objects.get_or_create(
        name="ប្រឡងខែវិច្ឆិកា ២០២៥ (តេស្ត)",
        academic_year=ay,
        defaults={'start_date': date(2025, 11, 20), 'end_date': date(2025, 11, 25)}
    )

    grade, _ = Grade.objects.update_or_create(
        student=student,
        subject=subj,
        exam_term=exam_term,
        defaults={'classroom': classroom, 'score': Decimal('88.50'), 'max_score': Decimal('100.00')}
    )

    att, _ = StudentAttendance.objects.update_or_create(
        student=student,
        date=date(2025, 11, 21),
        session=StudentAttendance.Session.MORNING,
        period_number=1,
        defaults={'classroom': classroom, 'status': StudentAttendance.Status.PRESENT}
    )

    print(f"Created baseline data: Student={student.khmer_name}, Grade={grade.score}, Att={att.status}")

    # 1. Create Academic Year Backup
    res = create_academic_year_backup(ay, label="Auto Test Backup", user_info="TestRunner")
    print("Backup created successfully:")
    print(f"  Filename: {res['filename']}")
    print(f"  Students count: {res['students_count']}")
    print(f"  Grades count: {res['grades_count']}")
    print(f"  Attendances count: {res['attendances_count']}")

    assert res['students_count'] >= 1
    assert res['grades_count'] >= 1
    assert res['attendances_count'] >= 1

    # 2. Simulate data modification / purge of this student
    student.khmer_name = "ឈ្មោះកែប្រែខុស"
    student.save()
    grade.score = Decimal('10.00')
    grade.save()

    print(f"Modified data: Student={student.khmer_name}, Grade={grade.score}")

    # 3. Restore Academic Year Backup from file
    restore_res = restore_academic_year_backup(res['filepath'], user_info="TestRunner")
    print(f"Restore result: {restore_res['message']}")
    print(f"  Counts: {restore_res['counts']}")

    # Refresh from DB
    student.refresh_from_db()
    grade.refresh_from_db()

    print(f"Post-restore check: Student={student.khmer_name}, Grade={grade.score}")
    assert student.khmer_name == 'សុខ តេស្តឆ្នាំ', f"Expected 'សុខ តេស្តឆ្នាំ', got '{student.khmer_name}'"
    assert grade.score == Decimal('88.50'), f"Expected 88.50, got {grade.score}"

    # 4. Test Archive Restore API
    archive = AcademicYearStudentArchive.objects.create(
        academic_year=ay,
        academic_year_name=ay.name,
        action_type=AcademicYearStudentArchive.ActionType.SOFT_UNENROLL,
        students_count=1,
        grades_count=1,
        attendances_count=1,
        archive_payload=res['payload']
    )

    from django.test import Client
    client = Client()
    from apps.accounts.models import User
    admin_user = User.objects.filter(role='ADMIN').first() or User.objects.filter(is_superuser=True).first()
    if not admin_user:
        admin_user = User.objects.create_superuser('testadmin', 'test@test.com', 'password123', role='ADMIN')
    else:
        admin_user.role = 'ADMIN'
        admin_user.save()
    client.force_login(admin_user)

    response = client.post(f'/students/archives/{archive.id}/restore/', content_type='application/json')
    print(f"Archive API restore response status: {response.status_code}")
    print(f"Archive API response content: {response.json()}")
    assert response.status_code == 200
    assert response.json().get('status') == 'success'

    print("ALL TESTS PASSED SUCCESSFULLY! ✅")

if __name__ == '__main__':
    run_tests()
