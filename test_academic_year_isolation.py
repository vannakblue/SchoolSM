import os
import sys
import django

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()


from decimal import Decimal
import datetime
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
from apps.accounts.models import User
from apps.academics.models import AcademicYear, Classroom, Subject, Timetable, GradeLevelRule, ClassSubject
from apps.academics.utils import get_active_academic_year
from apps.students.models import Student
from apps.examinations.models import ExamTerm, Grade
from apps.attendance.models import StudentAttendance
from apps.finance.models import MonthlyFeeConfig, MonthlyFeeRate, StudentMonthlyPayment, Invoice, FeeCategory
from apps.teachers.models import Teacher
from apps.academics.views import (
    classroom_list, classroom_delete_all, timetable_view, timetable_save_matrix, timetable_clear_all
)
from apps.students.views import student_list
from apps.examinations.views import grade_entry_matrix
from apps.attendance.views import student_attendance_grid

def run_tests():
    print("================================================================")
    print("RUNNING ACADEMIC YEAR STRICT ISOLATION TEST SUITE")
    print("================================================================")

    # 1. Setup Academic Years
    year_a, _ = AcademicYear.objects.get_or_create(
        name="2024-2025",
        defaults={'start_date': '2024-09-01', 'end_date': '2025-07-15', 'is_current': False}
    )
    year_b, _ = AcademicYear.objects.get_or_create(
        name="2025-2026",
        defaults={'start_date': '2025-09-01', 'end_date': '2026-07-15', 'is_current': True}
    )
    print(f"✅ Academic Years: {year_a.name} (id={year_a.id}) & {year_b.name} (id={year_b.id})")

    # 2. Setup Teacher & Subject
    teacher, _ = Teacher.objects.get_or_create(
        teacher_id="TCH-ISO-01",
        defaults={'khmer_name': 'ហេង ពិសី', 'status': 'ACTIVE', 'max_weekly_hours': 18}
    )
    teacher.khmer_name = 'ហេង ពិសី'
    teacher.save()

    subject, _ = Subject.objects.get_or_create(
        code="M",
        defaults={'name_kh': 'គណិតវិទ្យា', 'name_en': 'Mathematics', 'credit': 4, 'order': 1}
    )

    # 3. Setup Classrooms for Year A and Year B
    class_a, _ = Classroom.objects.get_or_create(
        code="7A-2024",
        academic_year=year_a,
        defaults={'name': 'ថ្នាក់ទី៧A (2024)', 'grade_level': 7, 'track': 'GENERAL'}
    )
    class_b, _ = Classroom.objects.get_or_create(
        code="7A-2025",
        academic_year=year_b,
        defaults={'name': 'ថ្នាក់ទី៧A (2025)', 'grade_level': 7, 'track': 'GENERAL'}
    )
    print(f"✅ Classrooms created: {class_a.name} in {year_a.name} & {class_b.name} in {year_b.name}")

    # 4. Test Timetable Clash Scope Isolation (Same teacher, same day, same period across different years MUST NOT clash)
    Timetable.objects.filter(classroom__in=[class_a, class_b]).delete()

    tt_a = Timetable.objects.create(
        classroom=class_a,
        subject=subject,
        teacher=teacher,
        day_of_week=1,
        period_number=1,
        start_time=datetime.time(7, 0),
        end_time=datetime.time(7, 50),
    )

    # In Year B, teacher can teach same period without clash error
    tt_b = Timetable(
        classroom=class_b,
        subject=subject,
        teacher=teacher,
        day_of_week=1,
        period_number=1,
        start_time=datetime.time(7, 0),
        end_time=datetime.time(7, 50),
    )
    # Validate clean()
    try:
        tt_b.clean()
        tt_b.save()
        print("✅ Timetable clean() passed: Teacher can teach in different academic years without cross-year clash.")
    except Exception as e:
        print(f"❌ Timetable clash failed: {e}")
        assert False, "Cross-year timetable clash occurred!"

    # 5. Test Student Isolation
    Student.objects.filter(student_id__in=["STU-2024-01", "STU-2025-01"]).delete()
    stu_a = Student.objects.create(
        student_id="STU-2024-01",
        khmer_name="សិស្ស ឆ្នាំចាស់",
        gender="M",
        date_of_birth=datetime.date(2010, 1, 1),
        academic_year=year_a,
        classroom=class_a,
        status="ACTIVE"
    )
    stu_b = Student.objects.create(
        student_id="STU-2025-01",
        khmer_name="សិស្ស ឆ្នាំថ្មី",
        gender="F",
        date_of_birth=datetime.date(2010, 5, 1),
        academic_year=year_b,
        classroom=class_b,
        status="ACTIVE"
    )


    # 6. Test RequestFactory with Session Switch
    factory = RequestFactory()
    admin_user = User.objects.filter(role='ADMIN').first()
    if not admin_user:
        admin_user = User.objects.create_superuser('admin_test', 'admin@test.com', 'password123')

    # Test student_list filtering with session active year = Year A
    req_a = factory.get('/students/')
    req_a.user = admin_user
    req_a.session = {'active_academic_year_id': year_a.id}
    res_a = student_list(req_a)
    content_a = res_a.content.decode('utf-8')
    assert "សិស្ស ឆ្នាំចាស់" in content_a, "stu_a should be in Year A list"
    assert "សិស្ស ឆ្នាំថ្មី" not in content_a, "stu_b MUST NOT be in Year A list"
    print("✅ Student List View Isolation: Year A sees only Year A students (Year B students excluded).")

    # Test student_list filtering with session active year = Year B
    req_b = factory.get('/students/')
    req_b.user = admin_user
    req_b.session = {'active_academic_year_id': year_b.id}
    res_b = student_list(req_b)
    content_b = res_b.content.decode('utf-8')
    assert "សិស្ស ឆ្នាំថ្មី" in content_b, "stu_b should be in Year B list"
    assert "សិស្ស ឆ្នាំចាស់" not in content_b, "stu_a MUST NOT be in Year B list"
    print("✅ Student List View Isolation: Year B sees only Year B students (Year A students excluded).")


    # 7. Test Timetable Clearing Isolation
    # When clearing timetable for Year A, Year B's timetable must remain completely untouched!
    from django.contrib.messages.storage.fallback import FallbackStorage
    req_clear = factory.post('/academics/timetable/clear-all/')
    req_clear.user = admin_user
    req_clear.session = {'active_academic_year_id': year_a.id}
    setattr(req_clear, '_messages', FallbackStorage(req_clear))
    timetable_clear_all(req_clear)


    assert not Timetable.objects.filter(classroom=class_a).exists(), "Year A timetables should be deleted"
    assert Timetable.objects.filter(classroom=class_b).exists(), "Year B timetables MUST NOT be deleted when Year A is cleared"
    print("✅ Timetable Clear Isolation: Clearing Year A timetable left Year B timetable 100% intact.")

    # 8. Clean up test records
    Timetable.objects.filter(classroom__in=[class_a, class_b]).delete()
    stu_a.delete()
    stu_b.delete()
    class_a.delete()
    class_b.delete()

    print("================================================================")
    print("🎉 ALL STRICT ACADEMIC YEAR ISOLATION TESTS PASSED 100%!")
    print("================================================================")

if __name__ == '__main__':
    run_tests()
