import os
import sys
import django
from datetime import date, datetime, timedelta

sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()
from django.test.utils import setup_test_environment
setup_test_environment()

from django.test import Client
from apps.accounts.models import User
from apps.academics.models import Classroom, Subject, Timetable, AcademicYear
from apps.academics.utils import get_active_academic_year
from apps.students.models import Student
from apps.teachers.models import Teacher
from apps.attendance.models import StudentAttendance, AttendanceSetting, AttendanceSubmissionLog

def run_tests():
    print("=" * 80)
    print("TEST: TEACHER HOURLY ATTENDANCE TIMETABLE SCHEDULE ENFORCEMENT & ALERTS")
    print("=" * 80)

    client = Client()
    active_year = get_active_academic_year()

    # 1. Setup Test Teacher, Admin, and Classrooms
    teacher_user, _ = User.objects.get_or_create(
        username='test_teacher_sched',
        defaults={'role': 'TEACHER', 'first_name': 'គ្រូ', 'last_name': 'តេស្ត'}
    )
    teacher_user.set_password('password123')
    teacher_user.role = 'TEACHER'
    teacher_user.save()

    teacher_prof, _ = Teacher.objects.get_or_create(
        user=teacher_user,
        defaults={
            'teacher_id': 'T-SCHED-01',
            'khmer_name': 'គ្រូ តេស្ត',
            'latin_name': 'Teacher Test',
            'gender': 'M',
            'status': 'ACTIVE'
        }
    )

    admin_user, _ = User.objects.get_or_create(
        username='test_admin_sched',
        defaults={'role': 'ADMIN', 'first_name': 'Admin', 'last_name': 'Test'}
    )
    admin_user.set_password('password123')
    admin_user.role = 'ADMIN'
    admin_user.save()

    # Create two classrooms
    class_a, _ = Classroom.objects.get_or_create(
        code='TEST-10A',
        academic_year=active_year,
        defaults={'name': 'ថ្នាក់ទី 10A (Sched)', 'grade_level': 10}
    )
    class_b, _ = Classroom.objects.get_or_create(
        code='TEST-10B',
        academic_year=active_year,
        defaults={'name': 'ថ្នាក់ទី 10B (Sched)', 'grade_level': 10}
    )

    # Students for class_a and class_b
    student_a, _ = Student.objects.get_or_create(
        student_id='STU-A-01',
        classroom=class_a,
        defaults={'khmer_name': 'សិស្ស ថ្នាក់អេ', 'gender': 'M', 'date_of_birth': date(2008, 1, 1), 'status': 'ACTIVE'}
    )
    student_b, _ = Student.objects.get_or_create(
        student_id='STU-B-01',
        classroom=class_b,
        defaults={'khmer_name': 'សិស្ស ថ្នាក់ប៊ី', 'gender': 'F', 'date_of_birth': date(2008, 2, 2), 'status': 'ACTIVE'}
    )

    subject_math, _ = Subject.objects.get_or_create(
        code='MATH-SCHED',
        defaults={'name_kh': 'គណិតវិទ្យា', 'name_en': 'Mathematics'}
    )

    # Clean existing timetables and attendance logs for test classrooms
    Timetable.objects.filter(teacher=teacher_prof).delete()
    AttendanceSubmissionLog.objects.filter(classroom__in=[class_a, class_b]).delete()
    StudentAttendance.objects.filter(student__in=[student_a, student_b]).delete()

    from apps.attendance.views import get_current_period_info
    current_dt = datetime.now()
    today = current_dt.date()
    curr_period, curr_session = get_current_period_info(current_dt.time())
    curr_dow = today.isoweekday()
    other_period = 1 if curr_period != 1 else 2
    test_sunday = today - timedelta(days=(curr_dow % 7)) # Sunday

    slot_start = (current_dt - timedelta(minutes=5)).strftime("%H:%M")
    slot_end = (current_dt + timedelta(minutes=45)).strftime("%H:%M")

    # Create timetable entry: Teacher teaches Class A at curr_period on today's day of week
    timetable_slot = Timetable.objects.create(
        teacher=teacher_prof,
        classroom=class_a,
        subject=subject_math,
        day_of_week=curr_dow,
        period_number=curr_period,
        start_time=slot_start,
        end_time=slot_end
    )

    # -------------------------------------------------------------
    # TEST 1: WEB PORTAL - Teacher Accessing Scheduled Classroom & Period
    # -------------------------------------------------------------
    print(f"\n[TEST 1] Web Portal: Teacher on Scheduled Slot (Class A, Period {curr_period}, Today)")
    client.force_login(teacher_user)
    resp = client.get(f'/attendance/?classroom={class_a.id}&period={curr_period}&date={today.strftime("%Y-%m-%d")}')
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    ctx = resp.context
    assert ctx['is_form_disabled'] == False, f"Form should NOT be disabled for scheduled teacher slot (timing_eval: {ctx['timing_eval']})"
    assert ctx['teacher_schedule_alert'] is None, "teacher_schedule_alert should be None for scheduled slot"
    print("  ✓ Form is enabled (is_form_disabled = False) and no schedule alert for scheduled slot.")

    # -------------------------------------------------------------
    # TEST 2: WEB PORTAL - Teacher Accessing Unscheduled Classroom (Class B, Period curr_period)
    # -------------------------------------------------------------
    print(f"\n[TEST 2] Web Portal: Teacher on Wrong Classroom (Class B, Period {curr_period}, Today)")
    resp = client.get(f'/attendance/?classroom={class_b.id}&period={curr_period}&date={today.strftime("%Y-%m-%d")}')
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    ctx = resp.context
    assert ctx['is_form_disabled'] == True, "Form MUST be disabled when teacher has no slot in this classroom!"
    assert ctx['teacher_schedule_alert'] is not None, "teacher_schedule_alert MUST be present!"
    assert ctx['teacher_schedule_alert']['alert_type'] == 'CLASS_MISMATCH', f"Expected CLASS_MISMATCH, got {ctx['teacher_schedule_alert']['alert_type']}"
    assert ctx['teacher_schedule_alert']['show_modal'] == True, "Modal must be marked to show"
    assert 'teacherScheduleModal' in resp.content.decode('utf-8'), "Template must contain #teacherScheduleModal"
    print("  ✓ Form is disabled (is_form_disabled = True), alert_type=CLASS_MISMATCH, and modal is rendered.")

    # -------------------------------------------------------------
    # TEST 3: WEB PORTAL - Teacher Accessing Unscheduled Period (Class A, Period other_period)
    # -------------------------------------------------------------
    print(f"\n[TEST 3] Web Portal: Teacher on Unscheduled Period (Class A, Period {other_period}, Today)")
    resp = client.get(f'/attendance/?classroom={class_a.id}&period={other_period}&date={today.strftime("%Y-%m-%d")}')
    assert resp.status_code == 200
    ctx = resp.context
    assert ctx['is_form_disabled'] == True, f"Form MUST be disabled when teacher has no slot in period {other_period}!"
    assert ctx['teacher_schedule_alert'] is not None
    assert ctx['teacher_schedule_alert']['alert_type'] in ['NO_CLASS_THIS_PERIOD', 'NO_CLASS_THIS_SESSION']
    print(f"  ✓ Form is disabled (is_form_disabled = True), alert_type={ctx['teacher_schedule_alert']['alert_type']}.")

    # -------------------------------------------------------------
    # TEST 4: WEB PORTAL - Teacher on Day with No Classes (Sunday)
    # -------------------------------------------------------------
    print("\n[TEST 4] Web Portal: Teacher on Day without any timetable classes (Sunday)")
    resp = client.get(f'/attendance/?classroom={class_a.id}&period={curr_period}&date={test_sunday.strftime("%Y-%m-%d")}')
    assert resp.status_code == 200
    ctx = resp.context
    assert ctx['is_form_disabled'] == True
    assert ctx['teacher_schedule_alert'] is not None
    assert ctx['teacher_schedule_alert']['alert_type'] == 'NO_CLASS_TODAY'
    print("  ✓ Form is disabled (is_form_disabled = True), alert_type=NO_CLASS_TODAY.")

    # -------------------------------------------------------------
    # TEST 5: WEB PORTAL POST - Unauthorized Submission Rejection
    # -------------------------------------------------------------
    print("\n[TEST 5] Web Portal POST: Unauthorized submission blocked")
    StudentAttendance.objects.filter(classroom=class_b, date=today).delete()
    post_data = {
        'classroom': class_b.id,
        'date': today.strftime("%Y-%m-%d"),
        'session': curr_session,
        'period': str(curr_period),
        f'is_absent_{student_b.id}': '1',
        f'status_{student_b.id}': 'ABSENT',
        f'notes_{student_b.id}': 'Hacked absence',
    }
    resp = client.post('/attendance/', post_data, follow=True)
    # Attendance should NOT be created!
    b_att_count = StudentAttendance.objects.filter(classroom=class_b, student=student_b, date=today, period_number=curr_period).count()
    assert b_att_count == 0, "Unscheduled teacher POST must NOT create attendance!"
    print("  ✓ Unscheduled teacher POST was rejected and no attendance record was written.")

    # -------------------------------------------------------------
    # TEST 6: WEB PORTAL POST - Authorized Submission Success
    # -------------------------------------------------------------
    print("\n[TEST 6] Web Portal POST: Authorized submission succeeds")
    StudentAttendance.objects.filter(classroom=class_a, date=today).delete()
    post_data_valid = {
        'classroom': class_a.id,
        'date': today.strftime("%Y-%m-%d"),
        'session': curr_session,
        'period': str(curr_period),
        f'is_absent_{student_a.id}': '1',
        f'status_{student_a.id}': 'PERMISSION',
        f'notes_{student_a.id}': 'Valid permission',
    }
    resp = client.post('/attendance/', post_data_valid, follow=True)
    a_att = StudentAttendance.objects.filter(classroom=class_a, student=student_a, date=today, period_number=curr_period).first()
    assert a_att is not None, "Scheduled teacher POST must create attendance!"
    assert a_att.status == 'PERMISSION', f"Expected PERMISSION, got {a_att.status}"
    print("  ✓ Scheduled teacher POST successfully saved attendance.")

    # -------------------------------------------------------------
    # TEST 7: MOBILE API ROSTER - can_record & schedule_alert payload
    # -------------------------------------------------------------
    print("\n[TEST 7] Mobile API Roster: Verification of can_record & schedule_alert")
    # Scheduled slot: Class A, Period curr_period
    resp = client.get(f'/api/v1/attendance/hourly/roster/?classroom_id={class_a.id}&period_number={curr_period}&date={today.strftime("%Y-%m-%d")}')
    assert resp.status_code == 200
    roster_data = resp.json()
    assert roster_data['can_record'] == True, "Scheduled teacher must have can_record: true"
    assert roster_data['is_teacher_scheduled'] == True
    assert roster_data['schedule_alert'] is None
    print("  ✓ Scheduled slot returns can_record: true, schedule_alert: null.")

    # Unscheduled slot: Class B, Period curr_period
    resp = client.get(f'/api/v1/attendance/hourly/roster/?classroom_id={class_b.id}&period_number={curr_period}&date={today.strftime("%Y-%m-%d")}')
    assert resp.status_code == 200
    roster_data_b = resp.json()
    assert roster_data_b['can_record'] == False, "Unscheduled teacher must have can_record: false"
    assert roster_data_b['is_teacher_scheduled'] == False
    assert roster_data_b['schedule_alert'] is not None, "schedule_alert must be present"
    assert roster_data_b['schedule_alert']['alert_type'] == 'CLASS_MISMATCH'
    assert 'title' in roster_data_b['schedule_alert']
    assert 'message' in roster_data_b['schedule_alert']
    print(f"  ✓ Unscheduled slot returns can_record: false and alert: '{roster_data_b['schedule_alert']['title']}'.")

    # -------------------------------------------------------------
    # TEST 8: MOBILE API SAVE - 403 Forbidden on Unscheduled Slot
    # -------------------------------------------------------------
    print("\n[TEST 8] Mobile API Save: Enforce 403 Forbidden for unscheduled teacher")
    save_payload = {
        'classroom_id': class_b.id,
        'date': today.strftime("%Y-%m-%d"),
        'period_number': curr_period,
        'session': curr_session,
        'attendances': [{'student_id': student_b.id, 'status': 'ABSENT', 'notes': ''}]
    }
    resp = client.post('/api/v1/attendance/hourly/save/', save_payload, content_type='application/json')
    assert resp.status_code == 403, f"Expected 403 Forbidden, got {resp.status_code}"
    err_json = resp.json()
    assert err_json.get('error_code') == 'TEACHER_NOT_SCHEDULED'
    print(f"  ✓ Correctly rejected with 403 Forbidden: {err_json.get('message')}")

    # Scheduled slot save should succeed
    save_payload_valid = {
        'classroom_id': class_a.id,
        'date': today.strftime("%Y-%m-%d"),
        'period_number': curr_period,
        'session': curr_session,
        'attendances': [{'student_id': student_a.id, 'status': 'ABSENT', 'notes': 'Sick'}]
    }
    resp = client.post('/api/v1/attendance/hourly/save/', save_payload_valid, content_type='application/json')
    assert resp.status_code == 200, f"Expected 200 OK, got {resp.status_code}"
    print("  ✓ Scheduled slot save succeeded with 200 OK.")

    # -------------------------------------------------------------
    # TEST 9: ADMIN OVERRIDE - Admins can record anytime
    # -------------------------------------------------------------
    print("\n[TEST 9] Admin Override: Admin user is never blocked")
    client.force_login(admin_user)
    # Admin checks Class B (no timetable for admin)
    resp = client.get(f'/attendance/?classroom={class_b.id}&period={curr_period}&date={today.strftime("%Y-%m-%d")}')
    assert resp.status_code == 200
    assert resp.context['is_form_disabled'] == False, "Admin should never be disabled"
    assert resp.context['teacher_schedule_alert'] is None

    # Admin Mobile API roster
    resp = client.get(f'/api/v1/attendance/hourly/roster/?classroom_id={class_b.id}&period_number={curr_period}&date={today.strftime("%Y-%m-%d")}')
    assert resp.status_code == 200
    assert resp.json()['can_record'] == True

    # Admin Mobile API save
    resp = client.post('/api/v1/attendance/hourly/save/', save_payload, content_type='application/json')
    assert resp.status_code == 200, f"Admin save should succeed with 200, got {resp.status_code}"
    print("  ✓ Admin override verified: Admin can view, edit, and save attendance across any classroom and period.")

    print("\n" + "=" * 80)
    print("ALL TESTS PASSED SUCCESSFULLY! (100% PASS RATE)")
    print("=" * 80)

if __name__ == '__main__':
    run_tests()
