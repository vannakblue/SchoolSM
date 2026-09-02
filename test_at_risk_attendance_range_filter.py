import os
import sys
import django

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.utils import timezone
from apps.academics.models import AcademicYear, Classroom
from apps.students.models import Student
from apps.attendance.models import StudentAttendance
from apps.attendance.views import at_risk_attendance_view

User = get_user_model()

def run_tests():
    print("==========================================================================")
    print("🚀 TEST: AT-RISK ATTENDANCE CUSTOM RANGE & THRESHOLD FILTERING")
    print("==========================================================================")

    admin_user = User.objects.filter(role='ADMIN').first()
    if not admin_user:
        admin_user = User.objects.create_superuser('admin_risk_test', 'admin@risk.com', 'pass123')

    ay, _ = AcademicYear.objects.get_or_create(
        name="2026-2027 Risk Test Year",
        defaults={'start_date': '2026-09-01', 'end_date': '2027-07-15', 'is_current': True}
    )
    AcademicYear.objects.filter(id=ay.id).update(is_current=True)
    AcademicYear.objects.exclude(id=ay.id).update(is_current=False)

    cls, _ = Classroom.objects.get_or_create(
        code="7D-RISK",
        defaults={'name': 'ថ្នាក់ទី 7D', 'grade_level': 7, 'academic_year': ay}
    )
    cls.academic_year = ay
    cls.save()

    # Create 3 test students with different absence counts:
    # Student A: 2 unexcused absences
    # Student B: 4 unexcused absences
    # Student C: 6 unexcused absences
    s_a, _ = Student.objects.get_or_create(
        student_id="RISK001",
        defaults={'khmer_name': 'សុខ មួយ', 'gender': 'M', 'date_of_birth': timezone.now().date(), 'classroom': cls, 'academic_year': ay, 'status': 'ACTIVE'}
    )
    s_b, _ = Student.objects.get_or_create(
        student_id="RISK002",
        defaults={'khmer_name': 'សុខ ពីរ', 'gender': 'M', 'date_of_birth': timezone.now().date(), 'classroom': cls, 'academic_year': ay, 'status': 'ACTIVE'}
    )
    s_c, _ = Student.objects.get_or_create(
        student_id="RISK003",
        defaults={'khmer_name': 'សុខ បី', 'gender': 'M', 'date_of_birth': timezone.now().date(), 'classroom': cls, 'academic_year': ay, 'status': 'ACTIVE'}
    )

    # Clean old attendance
    StudentAttendance.objects.filter(student__in=[s_a, s_b, s_c]).delete()

    now = timezone.now().date()
    # Student A: 2 sessions absent = 2 ដង = 1.0 ថ្ងៃ
    StudentAttendance.objects.create(student=s_a, classroom=cls, date=now, session=StudentAttendance.Session.MORNING, status=StudentAttendance.Status.ABSENT)
    StudentAttendance.objects.create(student=s_a, classroom=cls, date=now, session=StudentAttendance.Session.AFTERNOON, status=StudentAttendance.Status.ABSENT)
    
    # Student B: 4 sessions absent = 4 ដង = 2.0 ថ្ងៃ
    for i in range(2):
        StudentAttendance.objects.create(student=s_b, classroom=cls, date=now - timezone.timedelta(days=i), session=StudentAttendance.Session.MORNING, status=StudentAttendance.Status.ABSENT)
        StudentAttendance.objects.create(student=s_b, classroom=cls, date=now - timezone.timedelta(days=i), session=StudentAttendance.Session.AFTERNOON, status=StudentAttendance.Status.ABSENT)

    # Student C: 6 sessions absent = 6 ដង = 3.0 ថ្ងៃ
    for i in range(3):
        StudentAttendance.objects.create(student=s_c, classroom=cls, date=now - timezone.timedelta(days=i), session=StudentAttendance.Session.MORNING, status=StudentAttendance.Status.ABSENT)
        StudentAttendance.objects.create(student=s_c, classroom=cls, date=now - timezone.timedelta(days=i), session=StudentAttendance.Session.AFTERNOON, status=StudentAttendance.Status.ABSENT)

    rf = RequestFactory()

    # 1. Test Filter by DAYS (Min = 1.0 Day) -> Should find A (1.0d), B (2.0d), C (3.0d)
    req1 = rf.get(f'/attendance/at-risk/?classroom={cls.id}&unit=DAYS&min_absences=1')
    req1.user = admin_user
    req1.session = {}
    setattr(req1, '_messages', FallbackStorage(req1))
    res1 = at_risk_attendance_view(req1)
    assert res1.status_code == 200
    html1 = res1.content.decode('utf-8')
    assert "RISK001" in html1 and "RISK002" in html1 and "RISK003" in html1
    assert "1.0 ថ្ងៃ" in html1 and "2 ដង" in html1
    print(f"✅ Filter Unit=DAYS (Min=1.0 Day): Found all 3 students with dual format '1.0 ថ្ងៃ (2 ដង)' -> PASSED")

    # 2. Test Filter by TIMES (2 to 4 Times) -> Should find A (2 times) and B (4 times), exclude C (6 times)
    req2 = rf.get(f'/attendance/at-risk/?classroom={cls.id}&unit=TIMES&min_absences=2&max_absences=4')
    req2.user = admin_user
    req2.session = {}
    setattr(req2, '_messages', FallbackStorage(req2))
    res2 = at_risk_attendance_view(req2)
    assert res2.status_code == 200
    html2 = res2.content.decode('utf-8')
    assert "RISK001" in html2 and "RISK002" in html2 and "RISK003" not in html2
    print(f"✅ Filter Unit=TIMES (2 to 4 Times): Found A=2 times, B=4 times, excluded C=6 times -> PASSED")

    # 3. Test Filter Exact by TIMES (Exactly 4 Times = 2.0 Days) -> Should return ONLY B
    req3 = rf.get(f'/attendance/at-risk/?classroom={cls.id}&unit=TIMES&min_absences=4&max_absences=4')
    req3.user = admin_user
    req3.session = {}
    setattr(req3, '_messages', FallbackStorage(req3))
    res3 = at_risk_attendance_view(req3)
    assert res3.status_code == 200
    html3 = res3.content.decode('utf-8')
    assert "RISK002" in html3 and "RISK001" not in html3 and "RISK003" not in html3
    print(f"✅ Filter Unit=TIMES (Exactly 4 Times / 2.0 Days): Found ONLY student B (RISK002) -> PASSED")

    print("\n==========================================================================")
    print("🎉 ALL AT-RISK ATTENDANCE RANGE FILTER ASSERTIONS PASSED 100%!")
    print("==========================================================================")

    # Clean up test data
    StudentAttendance.objects.filter(student__in=[s_a, s_b, s_c]).delete()
    s_a.delete()
    s_b.delete()
    s_c.delete()
    cls.delete()

if __name__ == '__main__':
    run_tests()
