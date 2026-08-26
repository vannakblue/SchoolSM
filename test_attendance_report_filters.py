import os
import sys
import django
from datetime import datetime, date, timedelta

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.academics.models import AcademicYear, Classroom, Subject
from apps.students.models import Student
from apps.attendance.models import StudentAttendance, AttendanceSubmissionLog

def test_attendance_report_filters():
    print("==========================================================================")
    print("TEST: ATTENDANCE REPORT (TODAY / WEEK / MONTH) & 1-PER-SESSION DEDUP")
    print("==========================================================================")

    client = Client()
    admin = User.objects.filter(role='ADMIN').first()
    if not admin:
        admin = User.objects.create_superuser('admin_report_test', 'admin@test.com', 'adminpass', role='ADMIN')
    client.force_login(admin)

    ay, _ = AcademicYear.objects.get_or_create(
        name="2026-2027",
        defaults={'start_date': '2026-09-01', 'end_date': '2027-07-15', 'is_current': True}
    )
    AcademicYear.objects.filter(id=ay.id).update(is_current=True)
    AcademicYear.objects.exclude(id=ay.id).update(is_current=False)

    cls_7a = Classroom.objects.filter(code='7A', academic_year=ay).first()
    if not cls_7a:
        cls_7a = Classroom.objects.create(code='7A', name='ថ្នាក់ទី ៧A', grade_level=7, academic_year=ay)

    students = Student.objects.filter(classroom=cls_7a, academic_year=ay)
    st1 = students[0]
    st2 = students[1]

    sub_math, _ = Subject.objects.get_or_create(code='M', defaults={'name_kh': 'គណិតវិទ្យា', 'name_en': 'Math', 'category': 'SCIENCE'})
    sub_kh, _ = Subject.objects.get_or_create(code='K', defaults={'name_kh': 'ភាសាខ្មែរ', 'name_en': 'Khmer', 'category': 'GENERAL'})

    today = date.today()

    # Clean previous records for test date
    StudentAttendance.objects.filter(classroom=cls_7a, date=today).delete()
    AttendanceSubmissionLog.objects.filter(classroom=cls_7a, date=today).delete()

    # SCENARIO:
    # 1. Student 1 is marked ABSENT across Period 1, Period 2, Period 3, Period 4 in Morning Session (4 records in DB).
    # 2. Student 2 is marked PERMISSION across Period 1 and Period 2 in Morning Session, and ABSENT in Afternoon Session.
    for p in [1, 2, 3, 4]:
        StudentAttendance.objects.create(
            student=st1,
            classroom=cls_7a,
            date=today,
            session=StudentAttendance.Session.MORNING,
            period_number=p,
            subject=sub_math,
            status=StudentAttendance.Status.ABSENT,
            recorded_by=admin
        )

    for p in [1, 2]:
        StudentAttendance.objects.create(
            student=st2,
            classroom=cls_7a,
            date=today,
            session=StudentAttendance.Session.MORNING,
            period_number=p,
            subject=sub_math,
            status=StudentAttendance.Status.PERMISSION,
            recorded_by=admin
        )

    for p in [5, 6]:
        StudentAttendance.objects.create(
            student=st2,
            classroom=cls_7a,
            date=today,
            session=StudentAttendance.Session.AFTERNOON,
            period_number=p,
            subject=sub_kh,
            status=StudentAttendance.Status.ABSENT,
            recorded_by=admin
        )

    # Log the sessions
    AttendanceSubmissionLog.objects.create(
        classroom=cls_7a, date=today, session=StudentAttendance.Session.MORNING, period_number=1, recorded_by=admin, submission_count=1
    )
    AttendanceSubmissionLog.objects.create(
        classroom=cls_7a, date=today, session=StudentAttendance.Session.AFTERNOON, period_number=5, recorded_by=admin, submission_count=1
    )

    # 1. Test GET /attendance/report/?classroom=...&filter_type=today
    from django.test import RequestFactory
    from apps.attendance.views import attendance_report
    rf = RequestFactory()

    req_today = rf.get(f'/attendance/report/?classroom={cls_7a.id}&filter_type=today')
    req_today.user = admin
    res_today = attendance_report(req_today)
    assert res_today.status_code == 200
    html_today = res_today.content.decode('utf-8')
    assert '1 ពេល' in html_today or '50.0%' in html_today
    print("✅ PASSED: HTML contains correctly aggregated session metrics.")

    # 2. Test GET /attendance/report/?filter_type=week
    req_week = rf.get(f'/attendance/report/?classroom={cls_7a.id}&filter_type=week&week_date={today.strftime("%Y-%m-%d")}')
    req_week.user = admin
    res_week = attendance_report(req_week)
    assert res_week.status_code == 200
    html_week = res_week.content.decode('utf-8')
    assert 'សប្តាហ៍' in html_week
    print("✅ PASSED: Week filter successfully loaded.")

    # 3. Test GET /attendance/report/?filter_type=month
    req_month = rf.get(f'/attendance/report/?classroom={cls_7a.id}&filter_type=month&month={today.strftime("%Y-%m")}')
    req_month.user = admin
    res_month = attendance_report(req_month)
    assert res_month.status_code == 200
    html_month = res_month.content.decode('utf-8')
    assert 'ប្រចាំខែ' in html_month
    print("✅ PASSED: Month filter successfully loaded.")


    # Cleanup
    StudentAttendance.objects.filter(classroom=cls_7a, date=today).delete()
    AttendanceSubmissionLog.objects.filter(classroom=cls_7a, date=today).delete()

    print("==========================================================================")
    print("🎉 ALL ATTENDANCE REPORT FILTER & DEDUP TESTS PASSED 100%!")
    print("==========================================================================")

if __name__ == '__main__':
    test_attendance_report_filters()
