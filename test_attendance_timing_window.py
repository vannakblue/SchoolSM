import os
import sys
import django
from datetime import datetime, date, time

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.academics.models import AcademicYear, Classroom, Subject, Timetable
from apps.teachers.models import Teacher
from apps.students.models import Student
from apps.attendance.models import StudentAttendance, AttendanceSubmissionLog
from apps.attendance.views import evaluate_attendance_timing_window

def test_attendance_timing_window():
    print("==========================================================================")
    print("TEST: ATTENDANCE TIMING WINDOW RULES & 2 SESSIONS")
    print("==========================================================================")

    # 1. Verify Session choices (strictly 2: MORNING, AFTERNOON)
    session_choices = [c[0] for c in StudentAttendance.Session.choices]
    print(f"✅ Session choices: {session_choices}")
    assert 'MORNING' in session_choices and 'AFTERNOON' in session_choices
    assert 'FULL_DAY' not in session_choices, "FULL_DAY should not be in Session choices!"

    from apps.attendance.models import AttendanceSetting
    att_settings = AttendanceSetting.get_settings()
    att_settings.submission_grace_minutes = 30
    att_settings.period_grace_minutes = {str(i): 30 for i in range(1, 9)}
    att_settings.is_maintenance_mode = False
    att_settings.save()

    # 2. Setup Academic Year & Teacher & Class
    ay, _ = AcademicYear.objects.get_or_create(
        name="2026-2027",
        defaults={'start_date': '2026-09-01', 'end_date': '2027-07-15', 'is_current': True}
    )
    AcademicYear.objects.filter(id=ay.id).update(is_current=True)
    AcademicYear.objects.exclude(id=ay.id).update(is_current=False)

    user_teacher, _ = User.objects.get_or_create(
        username="teacher_timing_test",
        defaults={'role': 'TEACHER', 'first_name': 'សំ', 'last_name': 'សុក'}
    )
    user_teacher.role = 'TEACHER'
    user_teacher.save()

    teacher, _ = Teacher.objects.get_or_create(
        teacher_id="TCH-TIMING-01",
        defaults={'khmer_name': 'លោកគ្រូ សំ សុក', 'status': 'ACTIVE', 'max_weekly_hours': 18}
    )
    teacher.user = user_teacher
    teacher.save()

    cls_7a = Classroom.objects.filter(code='7A', academic_year=ay).first()
    if not cls_7a:
        cls_7a = Classroom.objects.create(code='7A', name='ថ្នាក់ទី ៧A', grade_level=7, academic_year=ay)

    sub_math, _ = Subject.objects.get_or_create(code='M', defaults={'name_kh': 'គណិតវិទ្យា', 'name_en': 'Math', 'category': 'SCIENCE'})

    # Setup Timetable Slot: Period 1: 07:00 - 08:00
    today_date = date.today()
    today_dow = today_date.isoweekday()
    if today_dow > 6:
        today_dow = 1

    Timetable.objects.filter(teacher=teacher, day_of_week=today_dow, period_number=1).delete()
    tt_p1 = Timetable.objects.create(
        classroom=cls_7a,
        subject=sub_math,
        teacher=teacher,
        day_of_week=today_dow,
        period_number=1,
        start_time='07:00',
        end_time='08:00'
    )

    # Clean logs for this class/date/period
    AttendanceSubmissionLog.objects.filter(classroom=cls_7a, date=today_date, period_number=1).delete()

    # TEST CASE 1: 07:15 (Within first 30 mins) -> OPEN_MULTIPLE
    dt_0715 = datetime.combine(today_date, time(7, 15))
    eval1 = evaluate_attendance_timing_window(teacher, cls_7a, 1, today_date, current_dt=dt_0715)
    print(f"CASE 1 (07:15 - First 30 mins): can_submit={eval1['can_submit']}, code={eval1['status_code']}")
    assert eval1['can_submit'] is True
    assert eval1['status_code'] == 'OPEN_MULTIPLE'

    # Simulate submission 1 at 07:15
    AttendanceSubmissionLog.objects.create(
        classroom=cls_7a,
        date=today_date,
        session='MORNING',
        period_number=1,
        recorded_by=user_teacher,
        submission_count=1
    )

    # TEST CASE 2: 07:25 (Still within first 30 mins after 1st submission) -> OPEN_MULTIPLE (Can edit multiple times!)
    dt_0725 = datetime.combine(today_date, time(7, 25))
    eval2 = evaluate_attendance_timing_window(teacher, cls_7a, 1, today_date, current_dt=dt_0725)
    print(f"CASE 2 (07:25 - Still in first 30 mins): can_submit={eval2['can_submit']}, code={eval2['status_code']}")
    assert eval2['can_submit'] is True
    assert eval2['status_code'] == 'OPEN_MULTIPLE'

    # TEST CASE 3: 07:45 (After first 30 mins, already submitted) -> LOCKED_ALREADY_SUBMITTED
    dt_0745 = datetime.combine(today_date, time(7, 45))
    eval3 = evaluate_attendance_timing_window(teacher, cls_7a, 1, today_date, current_dt=dt_0745)
    print(f"CASE 3 (07:45 - After 30 mins, already submitted): can_submit={eval3['can_submit']}, code={eval3['status_code']}")
    assert eval3['can_submit'] is False
    assert eval3['status_code'] == 'LOCKED_ALREADY_SUBMITTED'

    # TEST CASE 4: Period 2 (08:00 - 09:00), teacher did NOT submit at all during first 30 mins.
    # At 08:40 (After first 30 mins, NOT submitted yet) -> Grace Period: OPEN_ONCE (1-time submission only!)
    AttendanceSubmissionLog.objects.filter(classroom=cls_7a, date=today_date, period_number=2).delete()
    dt_0840 = datetime.combine(today_date, time(8, 40))
    eval4 = evaluate_attendance_timing_window(teacher, cls_7a, 2, today_date, current_dt=dt_0840)
    print(f"CASE 4 (08:40 - After 30 mins, not submitted yet): can_submit={eval4['can_submit']}, code={eval4['status_code']}")
    assert eval4['can_submit'] is True
    assert eval4['status_code'] == 'OPEN_ONCE'

    # Simulate 1-time grace submission for Period 2
    AttendanceSubmissionLog.objects.create(
        classroom=cls_7a,
        date=today_date,
        session='MORNING',
        period_number=2,
        recorded_by=user_teacher,
        submission_count=1
    )

    # Immediately after at 08:45 -> LOCKED_ALREADY_SUBMITTED
    dt_0845 = datetime.combine(today_date, time(8, 45))
    eval4_after = evaluate_attendance_timing_window(teacher, cls_7a, 2, today_date, current_dt=dt_0845)
    print(f"CASE 4b (08:45 - Immediately after 1-time grace submission): can_submit={eval4_after['can_submit']}, code={eval4_after['status_code']}")
    assert eval4_after['can_submit'] is False
    assert eval4_after['status_code'] == 'LOCKED_ALREADY_SUBMITTED'

    # TEST CASE 5: 08:05 (Period 1 ended at 08:00) -> LOCKED_EXPIRED
    dt_0805 = datetime.combine(today_date, time(8, 5))
    eval5 = evaluate_attendance_timing_window(teacher, cls_7a, 1, today_date, current_dt=dt_0805)
    print(f"CASE 5 (08:05 - After Period 1 ended): can_submit={eval5['can_submit']}, code={eval5['status_code']}")
    assert eval5['can_submit'] is False
    assert eval5['status_code'] == 'LOCKED_EXPIRED'

    # TEST CASE 6: PER-PERIOD CUSTOM DEADLINE (e.g. Period 1 = 20m, Period 5 = 45m)
    from apps.attendance.models import AttendanceSetting
    att_settings = AttendanceSetting.get_settings()
    att_settings.period_grace_minutes = {
        "1": 20,
        "2": 30,
        "3": 30,
        "4": 30,
        "5": 45,
        "6": 30,
        "7": 30,
        "8": 30,
    }
    att_settings.save()

    AttendanceSubmissionLog.objects.filter(classroom=cls_7a, date=today_date).delete()

    # Period 1 (07:00 - 08:00): At 07:22 (22 mins in > 20 mins grace cutoff)
    # If already submitted -> should be LOCKED
    AttendanceSubmissionLog.objects.create(
        classroom=cls_7a,
        date=today_date,
        session='MORNING',
        period_number=1,
        recorded_by=user_teacher,
        submission_count=1
    )
    dt_0722 = datetime.combine(today_date, time(7, 22))
    eval6_p1 = evaluate_attendance_timing_window(teacher, cls_7a, 1, today_date, current_dt=dt_0722)
    print(f"CASE 6a (P1 with 20m grace at 07:22): can_submit={eval6_p1['can_submit']}, code={eval6_p1['status_code']}")
    assert eval6_p1['can_submit'] is False
    assert eval6_p1['status_code'] == 'LOCKED_ALREADY_SUBMITTED'
    assert '២០' in eval6_p1['status_message'] or '20' in eval6_p1['status_message']

    # Period 5 (13:00 - 14:00): At 13:40 (40 mins in <= 45 mins grace cutoff)
    # Even after submitted -> should still be OPEN_MULTIPLE!
    AttendanceSubmissionLog.objects.create(
        classroom=cls_7a,
        date=today_date,
        session='AFTERNOON',
        period_number=5,
        recorded_by=user_teacher,
        submission_count=1
    )
    dt_1340 = datetime.combine(today_date, time(13, 40))
    eval6_p5 = evaluate_attendance_timing_window(teacher, cls_7a, 5, today_date, current_dt=dt_1340)
    print(f"CASE 6b (P5 with 45m grace at 13:40): can_submit={eval6_p5['can_submit']}, code={eval6_p5['status_code']}")
    assert eval6_p5['can_submit'] is True
    assert eval6_p5['status_code'] == 'OPEN_MULTIPLE'
    assert '45' in eval6_p5['status_label']

    # Cleanup test data
    Timetable.objects.filter(id=tt_p1.id).delete()
    AttendanceSubmissionLog.objects.filter(classroom=cls_7a, date=today_date).delete()

    print("==========================================================================")
    print("🎉 ALL ATTENDANCE TIMING WINDOW & 2-SESSION TESTS PASSED 100%!")
    print("==========================================================================")

if __name__ == '__main__':
    test_attendance_timing_window()

