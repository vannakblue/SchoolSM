import os
import sys
import django
from datetime import datetime, date, time, timedelta
from decimal import Decimal

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from django.core.management import call_command
from apps.accounts.models import User, TelegramConfig, NotificationLog
from apps.academics.models import AcademicYear, Classroom, Subject, Timetable, AcademicCalendarRestriction
from apps.students.models import Student
from apps.teachers.models import Teacher, TeacherAttendance, TeacherLeaveRequest
from apps.attendance.models import StudentAttendance, AttendanceSubmissionLog, AttendanceSetting
from apps.attendance.views import evaluate_attendance_timing_window
from apps.attendance.telegram_utils import (
    send_classroom_attendance_telegram,
    send_missing_teachers_telegram,
    send_daily_summary_telegram,
    send_teacher_leave_notification_telegram,
)

def run_all_tests():
    print("==========================================================================")
    print("TEST: ATTENDANCE TELEGRAM AUTOMATION, RESTRICTIONS & LEAVE MANAGEMENT")
    print("==========================================================================")

    # 1. Setup Academic Year & Base Data
    ay, _ = AcademicYear.objects.get_or_create(
        name="2025-2026",
        defaults={'start_date': '2025-09-01', 'end_date': '2026-07-15', 'is_current': True}
    )
    AcademicYear.objects.filter(id=ay.id).update(is_current=True)
    AcademicYear.objects.exclude(id=ay.id).update(is_current=False)

    cls_10a, _ = Classroom.objects.get_or_create(
        code='10A-TELE-TEST',
        defaults={'name': 'ថ្នាក់ទី ១០A', 'grade_level': 10, 'academic_year': ay, 'telegram_chat_id': '-100999888777'}
    )
    cls_10a.telegram_chat_id = '-100999888777'
    cls_10a.save()

    sub_khmer, _ = Subject.objects.get_or_create(
        code='KH-TELE',
        defaults={'name_kh': 'ភាសាខ្មែរ', 'name_en': 'Khmer Literature', 'category': 'SOCIAL'}
    )

    u_admin, _ = User.objects.get_or_create(
        username='admin_tele_test',
        defaults={'role': User.Role.ADMIN, 'khmer_name': 'អ្នកគ្រប់គ្រង តេស្ត', 'is_superuser': True}
    )

    u_teacher, _ = User.objects.get_or_create(
        username='teacher_tele_test',
        defaults={'role': User.Role.TEACHER, 'khmer_name': 'លោកគ្រូ សុវណ្ណ'}
    )
    teacher, _ = Teacher.objects.get_or_create(
        teacher_id='T-TELE-01',
        defaults={'user': u_teacher, 'khmer_name': 'លោកគ្រូ សុវណ្ណ', 'latin_name': 'SOVANN', 'status': 'ACTIVE', 'phone': '012999000'}
    )
    if teacher.user != u_teacher:
        teacher.user = u_teacher
        teacher.save()

    stu1, _ = Student.objects.get_or_create(
        student_id='ST-TELE-01',
        defaults={'khmer_name': 'សិស្ស ពិសិដ្ឋ', 'latin_name': 'PISETH', 'classroom': cls_10a, 'status': 'ACTIVE', 'date_of_birth': date(2010, 1, 1), 'gender': 'M'}
    )
    stu2, _ = Student.objects.get_or_create(
        student_id='ST-TELE-02',
        defaults={'khmer_name': 'សិស្ស ធារី', 'latin_name': 'THEARY', 'classroom': cls_10a, 'status': 'ACTIVE', 'date_of_birth': date(2010, 2, 2), 'gender': 'F'}
    )


    t_cfg, _ = TelegramConfig.objects.get_or_create(
        id=1,
        defaults={'bot_token': 'FAKE_BOT_TOKEN', 'chat_id': '-100111222333', 'is_active': True}
    )

    att_settings = AttendanceSetting.get_settings()
    att_settings.management_chat_id = '-100555666777'
    att_settings.submission_grace_minutes = 30
    att_settings.is_maintenance_mode = False
    att_settings.save()

    test_date = date(2026, 8, 17) # Monday

    # -------------------------------------------------------------------------
    # TEST 1: CLASSROOM TELEGRAM ATTENDANCE DISPATCH
    # -------------------------------------------------------------------------
    print("\n--- TEST 1: Classroom Attendance Telegram Dispatch ---")
    StudentAttendance.objects.filter(classroom=cls_10a, date=test_date).delete()
    StudentAttendance.objects.create(
        student=stu1, classroom=cls_10a, date=test_date, session='MORNING', period_number=1,
        status=StudentAttendance.Status.ABSENT, subject=sub_khmer, recorded_by=u_teacher, notes='ឈឺក្បាល'
    )
    StudentAttendance.objects.create(
        student=stu2, classroom=cls_10a, date=test_date, session='MORNING', period_number=1,
        status=StudentAttendance.Status.PRESENT, subject=sub_khmer, recorded_by=u_teacher
    )

    res_cls = send_classroom_attendance_telegram(
        classroom=cls_10a,
        target_date=test_date,
        session='MORNING',
        period_number=1,
        sender_user=u_teacher
    )
    assert res_cls['success'] is True
    assert res_cls['chat_id'] == '-100999888777'
    latest_log = NotificationLog.objects.first()
    assert 'ថ្នាក់ទី ១០A' in latest_log.title or 'ថ្នាក់ទី ១០A' in latest_log.message
    assert 'សិស្ស ពិសិដ្ឋ' in latest_log.message
    print(f"✅ Test 1 Passed: Dispatched classroom attendance to {res_cls['chat_id']}.")

    # -------------------------------------------------------------------------
    # TEST 2: VACATION & PUBLIC HOLIDAY RESTRICTIONS (ATTENDANCE LOCKOUT)
    # -------------------------------------------------------------------------
    print("\n--- TEST 2: Vacation & Public Holiday Attendance Lockout ---")
    vacation_start = date(2026, 8, 20)
    vacation_end = date(2026, 8, 25)
    AcademicCalendarRestriction.objects.filter(title__contains='Test Vacation').delete()
    vacation = AcademicCalendarRestriction.objects.create(
        restriction_type=AcademicCalendarRestriction.RestrictionType.VACATION,
        title='Test Vacation វិស្សមកាល',
        start_date=vacation_start,
        end_date=vacation_end,
        block_attendance=True,
        is_active=True
    )

    # Date inside vacation
    eval_vacation = evaluate_attendance_timing_window(teacher, cls_10a, 1, date(2026, 8, 22), current_dt=datetime(2026, 8, 22, 7, 15))
    assert eval_vacation['can_submit'] is False
    assert 'LOCKED_VACATION' in eval_vacation['status_code']
    assert 'វិស្សមកាល' in eval_vacation['status_label']
    print(f"✅ Test 2a Passed: Locked attendance during vacation ({eval_vacation['status_label']}).")

    # Date outside vacation (e.g. 2026-08-17)
    eval_normal = evaluate_attendance_timing_window(teacher, cls_10a, 1, test_date, current_dt=datetime(2026, 8, 17, 7, 15))
    assert eval_normal['can_submit'] is True
    print("✅ Test 2b Passed: Attendance open normally outside vacation.")

    # -------------------------------------------------------------------------
    # TEST 3: SYSTEM MAINTENANCE MODE LOCKOUT
    # -------------------------------------------------------------------------
    print("\n--- TEST 3: System Maintenance Mode Lockout ---")
    att_settings.is_maintenance_mode = True
    att_settings.maintenance_message = "ប្រព័ន្ធកំពុងបិទថែទាំជាបណ្តោះអាសន្ន។"
    att_settings.save()

    eval_maint = evaluate_attendance_timing_window(teacher, cls_10a, 1, test_date, current_dt=datetime(2026, 8, 17, 7, 15))
    assert eval_maint['can_submit'] is False
    assert eval_maint['status_code'] == 'LOCKED_MAINTENANCE'
    print("✅ Test 3 Passed: System Maintenance Mode successfully locked attendance.")

    att_settings.is_maintenance_mode = False
    att_settings.save()

    # -------------------------------------------------------------------------
    # TEST 4: CONFIGURABLE GRACE WINDOW (DEADLINE)
    # -------------------------------------------------------------------------
    print("\n--- TEST 4: Configurable Submission Grace Window ---")
    # Set grace window to 25 minutes (Period 1: 07:00 - 08:00)
    att_settings.submission_grace_minutes = 25
    att_settings.save()

    # Time at 07:20 (20 mins into class <= 25 mins) -> OPEN_MULTIPLE
    eval_grace_open = evaluate_attendance_timing_window(teacher, cls_10a, 1, test_date, current_dt=datetime(2026, 8, 17, 7, 20))
    assert eval_grace_open['can_submit'] is True
    assert eval_grace_open['status_code'] == 'OPEN_MULTIPLE'
    print("✅ Test 4a Passed: Open within 25-minute grace window.")

    # Time at 07:28 (28 mins into class > 25 mins) -> If already submitted -> LOCKED
    AttendanceSubmissionLog.objects.update_or_create(
        classroom=cls_10a, date=test_date, session='MORNING', period_number=1,
        defaults={'submission_count': 1, 'recorded_by': u_teacher}
    )
    eval_grace_locked = evaluate_attendance_timing_window(teacher, cls_10a, 1, test_date, current_dt=datetime(2026, 8, 17, 7, 28))
    assert eval_grace_locked['can_submit'] is False
    assert eval_grace_locked['status_code'] == 'LOCKED_ALREADY_SUBMITTED'
    print("✅ Test 4b Passed: Locked after 25-minute grace cutoff.")

    # -------------------------------------------------------------------------
    # TEST 5: TEACHER LEAVE REQUEST & SUPPRESSION OF MISSING ALERTS
    # -------------------------------------------------------------------------
    print("\n--- TEST 5: Teacher Leave Request & Compliance Sync ---")
    # Create Teacher 2 with slot on Monday Period 1
    u_teacher2, _ = User.objects.get_or_create(username='teacher_tele_test2', defaults={'role': User.Role.TEACHER, 'khmer_name': 'អ្នកគ្រូ ចិន្តា'})
    teacher2, _ = Teacher.objects.get_or_create(teacher_id='T-TELE-02', defaults={'user': u_teacher2, 'khmer_name': 'អ្នកគ្រូ ចិន្តា', 'latin_name': 'CHINDA', 'status': 'ACTIVE', 'phone': '012888999'})
    if teacher2.user != u_teacher2:
        teacher2.user = u_teacher2
        teacher2.save()

    Timetable.objects.filter(classroom=cls_10a).delete()
    Timetable.objects.create(classroom=cls_10a, subject=sub_khmer, teacher=teacher2, day_of_week=1, period_number=1, start_time=time(7,0), end_time=time(8,0))
    AttendanceSubmissionLog.objects.filter(classroom=cls_10a, date=test_date).delete()

    # Teacher 2 has NOT taken attendance, but applies for approved leave on test_date
    TeacherLeaveRequest.objects.filter(teacher=teacher2).delete()
    leave = TeacherLeaveRequest.objects.create(
        teacher=teacher2,
        leave_type=TeacherLeaveRequest.LeaveType.SICK,
        start_date=test_date,
        end_date=test_date,
        reason='គ្រុនផ្តាសាយធ្ងន់ធ្ងរ',
        status=TeacherLeaveRequest.Status.APPROVED,
        approved_by=u_admin
    )

    # Missing teacher alert should EXCLUDE teacher2 because she has approved leave!
    res_missing = send_missing_teachers_telegram(target_date=test_date, period_number=1)
    print("res_missing:", res_missing)
    # Check that teacher2 is NOT in the missing notification message
    assert teacher2.khmer_name not in NotificationLog.objects.first().message
    print("✅ Test 5 Passed: Teacher on approved leave successfully excluded from missing attendance alerts.")


    # -------------------------------------------------------------------------
    # TEST 6: DAILY SUMMARY DISPATCH & MANAGEMENT COMMAND
    # -------------------------------------------------------------------------
    print("\n--- TEST 6: Daily Summary Telegram Dispatch & Scheduled Command ---")
    res_summary = send_daily_summary_telegram(target_date=test_date, send_students=True, send_teachers=True)
    assert res_summary['success'] is True
    print(f"✅ Test 6a Passed: Daily summary dispatch successful ({res_summary['message']}).")

    call_command('dispatch_scheduled_attendance_telegram', force=True, date=test_date.strftime('%Y-%m-%d'))
    print("✅ Test 6b Passed: Management command executed successfully.")

    # -------------------------------------------------------------------------
    # TEST 7: ADMIN HUB & LEAVE VIEWS HTTP 200 OK & RULES SAVE
    # -------------------------------------------------------------------------
    print("\n--- TEST 7: Admin Hub & Teacher Leave Views Rendering & Form Save ---")
    client = Client()
    client.force_login(u_admin)

    res_hub = client.get('/attendance/admin-hub/')
    assert res_hub.status_code == 200
    assert 'Attendance &amp; Telegram Automation Hub' in res_hub.content.decode('utf-8') or 'Attendance & Telegram' in res_hub.content.decode('utf-8')
    assert 'period_grace_1' in res_hub.content.decode('utf-8')
    assert 'period_grace_8' in res_hub.content.decode('utf-8')
    print("✅ Test 7a Passed: /attendance/admin-hub/ rendered 200 OK with 8 period inputs.")

    # Test POST save_rules with 8 periods and multiple management Chat IDs
    post_data = {
        'action': 'save_rules',
        'submission_grace_minutes': '30',
        'period_grace_1': '20',
        'period_grace_2': '25',
        'period_grace_3': '30',
        'period_grace_4': '35',
        'period_grace_5': '40',
        'period_grace_6': '45',
        'period_grace_7': '50',
        'period_grace_8': '55',
        'management_chat_id': '-100999000111, -100888000222, @school_management',
        'auto_daily_dispatch_enabled': 'on',
        'auto_send_student_summary': 'on',
        'auto_send_teacher_summary': 'on',
    }
    res_post_rules = client.post('/attendance/admin-hub/', post_data)
    assert res_post_rules.status_code == 302
    reloaded_setting = AttendanceSetting.get_settings()
    assert reloaded_setting.get_grace_minutes_for_period(1) == 20
    assert reloaded_setting.get_grace_minutes_for_period(4) == 35
    assert reloaded_setting.get_grace_minutes_for_period(8) == 55
    assert '-100888000222' in reloaded_setting.management_chat_id
    print("✅ Test 7b Passed: Admin Hub POST saved all 8 period grace windows & multiple Chat IDs successfully.")

    # Test Multi Chat ID Dispatch
    res_multi = send_daily_summary_telegram(target_date=test_date, send_students=True, send_teachers=True)
    assert res_multi['success'] is True
    log_multi = NotificationLog.objects.first()
    assert '-100999000111' in log_multi.recipient_name
    assert '-100888000222' in log_multi.recipient_name
    assert '@school_management' in log_multi.recipient_name
    print(f"✅ Test 7c Passed: Multiple Chat IDs dispatched and logged: {log_multi.recipient_name}")

    res_leaves = client.get('/teachers/leave/')
    assert res_leaves.status_code == 200
    assert 'ពាក្យសុំច្បាប់គ្រូបង្រៀន' in res_leaves.content.decode('utf-8')
    print("✅ Test 7d Passed: /teachers/leave/ rendered 200 OK.")

    res_leave_apply = client.get('/teachers/leave/apply/')
    assert res_leave_apply.status_code == 200
    assert 'ពាក្យសុំច្បាប់ឈប់សម្រាកគ្រូបង្រៀន' in res_leave_apply.content.decode('utf-8')
    print("✅ Test 7e Passed: /teachers/leave/apply/ rendered 200 OK.")

    # Cleanup
    vacation.delete()
    leave.delete()
    Timetable.objects.filter(classroom=cls_10a).delete()
    StudentAttendance.objects.filter(classroom=cls_10a).delete()
    AttendanceSubmissionLog.objects.filter(classroom=cls_10a).delete()
    stu1.delete()
    stu2.delete()
    cls_10a.delete()
    sub_khmer.delete()
    teacher.delete()
    teacher2.delete()
    u_teacher.delete()
    u_teacher2.delete()
    u_admin.delete()

    print("\n==========================================================================")
    print("🎉 ALL TELEGRAM AUTOMATION, RESTRICTION & LEAVE TESTS PASSED 100%!")
    print("==========================================================================")

if __name__ == '__main__':
    run_all_tests()
