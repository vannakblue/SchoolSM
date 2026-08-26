import os
import sys
import django
from datetime import datetime, date, time, timedelta
from decimal import Decimal

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client, RequestFactory
from apps.accounts.models import User
from apps.academics.models import AcademicYear, Classroom, Subject, Timetable
from apps.students.models import Student
from apps.teachers.models import Teacher, TeacherAttendance
from apps.attendance.models import StudentAttendance, AttendanceSubmissionLog
from apps.teachers.utils import (
    get_teacher_daily_attendance_data,
    get_teacher_range_attendance_report,
    sync_teacher_attendance_from_student_logs
)
from apps.teachers.views import teacher_attendance_report, teacher_attendance_view

def run_tests():
    print("==========================================================================")
    print("TEST: TEACHER ATTENDANCE EXTRACTION FROM STUDENT ATTENDANCE & MULTI-REPORTS")
    print("==========================================================================")

    # 1. Setup Academic Year & Classroom
    ay, _ = AcademicYear.objects.get_or_create(
        name="2025-2026",
        defaults={'start_date': '2025-09-01', 'end_date': '2026-07-15', 'is_current': True}
    )
    AcademicYear.objects.filter(id=ay.id).update(is_current=True)
    AcademicYear.objects.exclude(id=ay.id).update(is_current=False)

    cls_10a, _ = Classroom.objects.get_or_create(
        code='10A-TEST',
        academic_year=ay,
        defaults={'name': 'ថ្នាក់ទី ១០A តេស្ត', 'grade_level': 10}
    )

    sub_math, _ = Subject.objects.get_or_create(
        code='M-TEST',
        defaults={'name_kh': 'គណិតវិទ្យា', 'name_en': 'Mathematics', 'category': 'SCIENCE'}
    )
    sub_kh, _ = Subject.objects.get_or_create(
        code='K-TEST',
        defaults={'name_kh': 'ភាសាខ្មែរ', 'name_en': 'Khmer Language', 'category': 'GENERAL'}
    )

    # Create Teachers
    t1, _ = Teacher.objects.get_or_create(
        teacher_id='T-TEST-01',
        defaults={
            'khmer_name': 'លី វណ្ណារ៉ា',
            'latin_name': 'LY VANNARA',
            'specialization': 'គណិតវិទ្យា',
            'base_salary': Decimal('520.00'),
            'status': 'ACTIVE',
            'phone': '012345671'
        }
    )
    t2, _ = Teacher.objects.get_or_create(
        teacher_id='T-TEST-02',
        defaults={
            'khmer_name': 'សោម គន្ធា',
            'latin_name': 'SOM KUNTHEA',
            'specialization': 'ភាសាខ្មែរ',
            'base_salary': Decimal('520.00'),
            'status': 'ACTIVE',
            'phone': '012345672'
        }
    )
    t3, _ = Teacher.objects.get_or_create(
        teacher_id='T-TEST-03',
        defaults={
            'khmer_name': 'ឈឹម ស្រី',
            'latin_name': 'CHHIM SREY',
            'specialization': 'ប្រវត្តិវិទ្យា',
            'base_salary': Decimal('500.00'),
            'status': 'ACTIVE',
            'phone': '012345673'
        }
    )

    # Use a fixed Monday for test (e.g. 2026-08-17 is a Monday, weekday=1)
    test_monday = date(2026, 8, 17)
    assert test_monday.isoweekday() == 1

    # Cleanup old test records
    Timetable.objects.filter(classroom=cls_10a).delete()
    AttendanceSubmissionLog.objects.filter(classroom=cls_10a, date=test_monday).delete()
    TeacherAttendance.objects.filter(teacher__in=[t1, t2, t3], date=test_monday).delete()

    # Create Timetable entries for Monday:
    # T1: Period 1 (07:00-08:00) & Period 2 (08:00-09:00)
    tt1 = Timetable.objects.create(
        classroom=cls_10a,
        subject=sub_math,
        teacher=t1,
        day_of_week=1,
        period_number=1,
        start_time=time(7, 0),
        end_time=time(8, 0)
    )
    tt2 = Timetable.objects.create(
        classroom=cls_10a,
        subject=sub_math,
        teacher=t1,
        day_of_week=1,
        period_number=2,
        start_time=time(8, 0),
        end_time=time(9, 0)
    )
    # T2: Period 3 (09:00-10:00)
    tt3 = Timetable.objects.create(
        classroom=cls_10a,
        subject=sub_kh,
        teacher=t2,
        day_of_week=1,
        period_number=3,
        start_time=time(9, 0),
        end_time=time(10, 0)
    )

    admin_user = User.objects.filter(role='ADMIN').first()
    if not admin_user:
        admin_user = User.objects.create_superuser('admin_test_att', 'admin@att.com', 'adminpass', role='ADMIN')

    # SCENARIO:
    # 1. T1 only submitted student attendance for Period 1 (Period 2 is MISSING / UNRECORDED)
    AttendanceSubmissionLog.objects.create(
        classroom=cls_10a,
        date=test_monday,
        session=StudentAttendance.Session.MORNING,
        period_number=1,
        recorded_by=admin_user,
        submission_count=1
    )

    # 2. T2 submitted student attendance for Period 3 (COMPLETED)
    AttendanceSubmissionLog.objects.create(
        classroom=cls_10a,
        date=test_monday,
        session=StudentAttendance.Session.MORNING,
        period_number=3,
        recorded_by=admin_user,
        submission_count=1
    )

    # 3. T3 has no classes on Monday

    # -------------------------------------------------------------------------
    # TEST 1: Daily Evaluation Logic (get_teacher_daily_attendance_data)
    # -------------------------------------------------------------------------
    print("\n--- TEST 1: Daily Evaluation from Student Attendance ---")
    mock_now_dt = datetime(2026, 8, 17, 18, 0, 0) # End of Monday
    teachers = [t1, t2, t3]
    daily_res = get_teacher_daily_attendance_data(teachers, test_monday, ay, current_dt=mock_now_dt)

    t1_row = next(r for r in daily_res['rows'] if r['teacher'].id == t1.id)
    t2_row = next(r for r in daily_res['rows'] if r['teacher'].id == t2.id)
    t3_row = next(r for r in daily_res['rows'] if r['teacher'].id == t3.id)

    # Validate T1: 2 scheduled, 1 recorded, 1 unrecorded -> UNEXCUSED_ABSENCE
    assert t1_row['scheduled_count'] == 2, f"T1 scheduled should be 2, got {t1_row['scheduled_count']}"
    assert t1_row['recorded_count'] == 1, f"T1 recorded should be 1, got {t1_row['recorded_count']}"
    assert t1_row['unrecorded_count'] == 1, f"T1 unrecorded should be 1, got {t1_row['unrecorded_count']}"
    assert t1_row['daily_status'] == 'UNEXCUSED_ABSENCE', f"T1 status should be UNEXCUSED_ABSENCE, got {t1_row['daily_status']}"
    assert t1_row['compliance_rate'] == 50.0, f"T1 compliance should be 50%, got {t1_row['compliance_rate']}"
    print("✅ T1 (Missed 1 period): Correctly identified as UNEXCUSED_ABSENCE (50% compliance, 1 missed period).")

    # Validate T2: 1 scheduled, 1 recorded, 0 unrecorded -> PRESENT
    assert t2_row['scheduled_count'] == 1, f"T2 scheduled should be 1, got {t2_row['scheduled_count']}"
    assert t2_row['recorded_count'] == 1, f"T2 recorded should be 1, got {t2_row['recorded_count']}"
    assert t2_row['unrecorded_count'] == 0, f"T2 unrecorded should be 0, got {t2_row['unrecorded_count']}"
    assert t2_row['daily_status'] == 'PRESENT', f"T2 status should be PRESENT, got {t2_row['daily_status']}"
    assert t2_row['compliance_rate'] == 100.0, f"T2 compliance should be 100%, got {t2_row['compliance_rate']}"
    print("✅ T2 (Recorded all): Correctly identified as PRESENT (100% compliance).")

    # Validate T3: 0 scheduled -> NO_SCHEDULE
    assert t3_row['scheduled_count'] == 0
    assert t3_row['daily_status'] == 'NO_SCHEDULE'
    print("✅ T3 (No classes today): Correctly identified as NO_SCHEDULE.")

    # -------------------------------------------------------------------------
    # TEST 2: Sync Teacher Attendance DB
    # -------------------------------------------------------------------------
    print("\n--- TEST 2: Auto-Sync to TeacherAttendance DB ---")
    synced = sync_teacher_attendance_from_student_logs(test_monday, ay, current_dt=mock_now_dt)
    assert synced >= 2, f"Expected at least 2 synced teachers, got {synced}"

    att_t1 = TeacherAttendance.objects.get(teacher=t1, date=test_monday)
    att_t2 = TeacherAttendance.objects.get(teacher=t2, date=test_monday)

    assert att_t1.status == TeacherAttendance.Status.UNEXCUSED_ABSENCE
    assert att_t1.deduction_amount > 0, f"T1 deduction should be > 0, got {att_t1.deduction_amount}"
    assert att_t2.status == TeacherAttendance.Status.PRESENT
    assert att_t2.deduction_amount == 0
    print(f"✅ TeacherAttendance DB synced: T1 is {att_t1.status} (Deduction: ${att_t1.deduction_amount}), T2 is {att_t2.status}")

    # -------------------------------------------------------------------------
    # TEST 3: Range Aggregation (Weekly & Monthly)
    # -------------------------------------------------------------------------
    print("\n--- TEST 3: Range Aggregation (Week & Month) ---")
    week_start = test_monday
    week_end = test_monday + timedelta(days=5) # Mon to Sat
    range_res = get_teacher_range_attendance_report(teachers, week_start, week_end, ay, current_dt=mock_now_dt)

    t1_week = next(r for r in range_res['rows'] if r['teacher'].id == t1.id)
    t2_week = next(r for r in range_res['rows'] if r['teacher'].id == t2.id)

    assert t1_week['scheduled_hours'] == 2
    assert t1_week['unrecorded_hours'] == 1
    assert t1_week['unrecorded_days_count'] == 1
    assert t1_week['has_unrecorded'] is True
    print("✅ Weekly report accurately calculated total weekly hours, unrecorded hours, and unrecorded days.")

    # -------------------------------------------------------------------------
    # TEST 4: View Endpoints via Django Client
    # -------------------------------------------------------------------------
    print("\n--- TEST 4: View Endpoints & Templates Rendering ---")
    client = Client()
    client.force_login(admin_user)

    # 4.1 Daily Input Sheet View
    res_att_sheet = client.get(f'/teachers/attendance/?date={test_monday.strftime("%Y-%m-%d")}')
    assert res_att_sheet.status_code == 200, f"Expected 200, got {res_att_sheet.status_code}"
    html_sheet = res_att_sheet.content.decode('utf-8')
    assert 'ស្រង់វត្តមានគ្រូបង្រៀន' in html_sheet
    assert 'ខកខាន' in html_sheet or 'បានចុះ' in html_sheet
    print("✅ /teachers/attendance/ rendered with live student-attendance indicators.")

    # 4.2 Report View: Period Matrix Tab
    res_period = client.get(f'/teachers/attendance/report/?filter_type=period&date={test_monday.strftime("%Y-%m-%d")}')
    assert res_period.status_code == 200
    html_period = res_period.content.decode('utf-8')
    assert 'ម៉ោងទី ១' in html_period
    assert 'លី វណ្ណារ៉ា' in html_period
    print("✅ /teachers/attendance/report/?filter_type=period rendered successfully.")

    # 4.3 Report View: Day Tab
    res_day = client.get(f'/teachers/attendance/report/?filter_type=day&date={test_monday.strftime("%Y-%m-%d")}')
    assert res_day.status_code == 200
    html_day = res_day.content.decode('utf-8')
    assert 'តាមថ្ងៃ' in html_day
    print("✅ /teachers/attendance/report/?filter_type=day rendered successfully.")

    # 4.4 Report View: Week Tab
    res_week = client.get(f'/teachers/attendance/report/?filter_type=week&week_date={test_monday.strftime("%Y-%m-%d")}')
    assert res_week.status_code == 200
    html_week = res_week.content.decode('utf-8')
    assert 'តាមសប្តាហ៍' in html_week
    print("✅ /teachers/attendance/report/?filter_type=week rendered successfully.")

    # 4.5 Report View: Month Tab
    res_month = client.get(f'/teachers/attendance/report/?filter_type=month&month=2026-08')
    assert res_month.status_code == 200
    html_month = res_month.content.decode('utf-8')
    assert 'ប្រចាំខែ' in html_month
    print("✅ /teachers/attendance/report/?filter_type=month rendered successfully.")

    # Cleanup test records
    Timetable.objects.filter(classroom=cls_10a).delete()
    AttendanceSubmissionLog.objects.filter(classroom=cls_10a, date=test_monday).delete()
    TeacherAttendance.objects.filter(teacher__in=[t1, t2, t3], date=test_monday).delete()
    cls_10a.delete()
    sub_math.delete()
    sub_kh.delete()
    t1.delete()
    t2.delete()
    t3.delete()

    print("\n==========================================================================")
    print("🎉 ALL TEACHER ATTENDANCE EXTRACTION & MULTI-REPORT TESTS PASSED 100%!")
    print("==========================================================================")

if __name__ == '__main__':
    run_tests()
