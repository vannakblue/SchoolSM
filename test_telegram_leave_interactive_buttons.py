import os
import sys
import json
import django
from datetime import datetime, date, timedelta

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User, TelegramConfig, NotificationLog
from apps.academics.models import AcademicYear
from apps.teachers.models import Teacher, TeacherLeaveRequest, TeacherAttendance
from apps.attendance.models import AttendanceSetting
from apps.attendance.telegram_utils import (
    send_teacher_leave_notification_telegram,
    process_teacher_leave_action,
    format_teacher_leave_telegram_message
)

def test_telegram_leave_interactive_buttons():
    print("==========================================================================")
    print("TEST: INTERACTIVE TELEGRAM BUTTONS FOR TEACHER LEAVE APPROVE / REJECT")
    print("==========================================================================")

    # 1. Setup Academic Year & Teacher
    ay, _ = AcademicYear.objects.get_or_create(
        name="2026-2027",
        defaults={'start_date': '2026-09-01', 'end_date': '2027-07-15', 'is_current': True}
    )
    AcademicYear.objects.filter(id=ay.id).update(is_current=True)
    AcademicYear.objects.exclude(id=ay.id).update(is_current=False)

    u_admin, _ = User.objects.get_or_create(username='admin_leave_test', defaults={'role': User.Role.ADMIN, 'khmer_name': 'អ្នកគ្រប់គ្រង'})
    u_teacher, _ = User.objects.get_or_create(username='teacher_leave_btn_test', defaults={'role': User.Role.TEACHER, 'khmer_name': 'លោកគ្រូ សុវណ្ណ'})
    
    teacher, _ = Teacher.objects.get_or_create(
        teacher_id='TCH-BTN-01',
        defaults={'user': u_teacher, 'khmer_name': 'លោកគ្រូ សុវណ្ណ', 'status': 'ACTIVE', 'phone': '012999888'}
    )
    teacher.user = u_teacher
    teacher.save()

    TelegramConfig.objects.update_or_create(
        id=1,
        defaults={'bot_token': 'TEST_TOKEN_123', 'chat_id': '-100999000111', 'is_active': True}
    )

    att_settings = AttendanceSetting.get_settings()
    att_settings.management_chat_id = '-100999000111'
    att_settings.save()

    # Clean existing leave requests for this teacher
    TeacherLeaveRequest.objects.filter(teacher=teacher).delete()
    TeacherAttendance.objects.filter(teacher=teacher).delete()

    # -------------------------------------------------------------------------
    # TEST 1: NOTIFICATION DISPATCH WITH INLINE KEYBOARD
    # -------------------------------------------------------------------------
    print("\n--- TEST 1: Leave Request Creation & Inline Buttons Attachment ---")
    start_d = date(2026, 8, 24)
    end_d = date(2026, 8, 25) # 2 days

    leave_pending = TeacherLeaveRequest.objects.create(
        teacher=teacher,
        leave_type=TeacherLeaveRequest.LeaveType.SICK,
        start_date=start_d,
        end_date=end_d,
        reason='គ្រុនក្តៅខ្លាំង ត្រូវសម្រាកព្យាបាល ២ ថ្ងៃ',
        status=TeacherLeaveRequest.Status.PENDING
    )

    res_dispatch = send_teacher_leave_notification_telegram(leave_pending)
    assert res_dispatch['success'] is True
    print(f"✅ Test 1 Passed: Leave notification dispatched to Telegram with Inline Keyboard buttons.")

    # -------------------------------------------------------------------------
    # TEST 2: PROCESS APPROVE ACTION VIA BUTTON CALLBACK
    # -------------------------------------------------------------------------
    print("\n--- TEST 2: Process Leave Approval & Sync TeacherAttendance DB ---")
    res_approve = process_teacher_leave_action(
        leave_id=leave_pending.id,
        action='approve',
        approver_name='នាយកសាលា (Admin តាម Telegram)'
    )
    assert res_approve['success'] is True
    assert res_approve['action'] == 'approved'
    assert '✅ បានអនុម័ត' in res_approve['message']
    
    # Verify DB Status
    leave_pending.refresh_from_db()
    assert leave_pending.status == TeacherLeaveRequest.Status.APPROVED
    
    # Verify TeacherAttendance sync for both dates (Aug 24 and Aug 25)
    att_day1 = TeacherAttendance.objects.filter(teacher=teacher, date=start_d).first()
    att_day2 = TeacherAttendance.objects.filter(teacher=teacher, date=end_d).first()
    assert att_day1 is not None, "TeacherAttendance for start_date must exist!"
    assert att_day2 is not None, "TeacherAttendance for end_date must exist!"
    assert att_day1.status == TeacherAttendance.Status.EXCUSED_LEAVE
    assert att_day1.deduction_amount == 0
    assert att_day2.status == TeacherAttendance.Status.EXCUSED_LEAVE
    assert att_day2.deduction_amount == 0
    print(f"✅ Test 2 Passed: TeacherLeaveRequest status updated to APPROVED and 2 days synced to TeacherAttendance (EXCUSED_LEAVE, $0 deduction).")

    # -------------------------------------------------------------------------
    # TEST 3: PROCESS REJECT ACTION VIA BUTTON CALLBACK
    # -------------------------------------------------------------------------
    print("\n--- TEST 3: Process Leave Rejection ---")
    leave_pending2 = TeacherLeaveRequest.objects.create(
        teacher=teacher,
        leave_type=TeacherLeaveRequest.LeaveType.PERSONAL,
        start_date=date(2026, 8, 28),
        end_date=date(2026, 8, 28),
        reason='ការងារផ្ទាល់ខ្លួន',
        status=TeacherLeaveRequest.Status.PENDING
    )

    res_reject = process_teacher_leave_action(
        leave_id=leave_pending2.id,
        action='reject',
        approver_name='Admin តាម Telegram'
    )
    assert res_reject['success'] is True
    assert res_reject['action'] == 'rejected'
    
    leave_pending2.refresh_from_db()
    assert leave_pending2.status == TeacherLeaveRequest.Status.REJECTED
    assert 'បដិសេធ' in leave_pending2.rejection_reason
    print(f"✅ Test 3 Passed: TeacherLeaveRequest #{leave_pending2.id} successfully REJECTED via callback action.")

    # -------------------------------------------------------------------------
    # TEST 4: PREVENT DOUBLE-ACTION ON ALREADY PROCESSED LEAVE
    # -------------------------------------------------------------------------
    print("\n--- TEST 4: Prevent Duplicate Execution on Already Processed Leave ---")
    res_dup = process_teacher_leave_action(
        leave_id=leave_pending2.id,
        action='approve',
        approver_name='Admin តាម Telegram'
    )
    assert res_dup['success'] is False
    assert 'ត្រូវបាន' in res_dup['message']
    print(f"✅ Test 4 Passed: Duplicate execution safely prevented ({res_dup['message']}).")

    # -------------------------------------------------------------------------
    # TEST 5: TELEGRAM WEBHOOK HTTP ENDPOINT
    # -------------------------------------------------------------------------
    print("\n--- TEST 5: Telegram Webhook HTTP Endpoint & Callback Query Routing ---")
    leave_pending3 = TeacherLeaveRequest.objects.create(
        teacher=teacher,
        leave_type=TeacherLeaveRequest.LeaveType.SICK,
        start_date=date(2026, 8, 30),
        end_date=date(2026, 8, 30),
        reason='គ្រុនផ្តាសាយ',
        status=TeacherLeaveRequest.Status.PENDING
    )

    client = Client()
    mock_webhook_payload = {
        "update_id": 998877,
        "callback_query": {
            "id": "cb_query_123456",
            "from": {
                "id": 12345678,
                "first_name": "លោកនាយក",
                "username": "principal_kh"
            },
            "message": {
                "message_id": 4321,
                "chat": {
                    "id": -100999000111,
                    "title": "School Management Group"
                },
                "text": "Existing message"
            },
            "data": f"leave:approve:{leave_pending3.id}"
        }
    }

    response = client.post(
        '/api/telegram/webhook/',
        data=json.dumps(mock_webhook_payload),
        content_type='application/json'
    )
    assert response.status_code == 200
    res_data = response.json()
    assert res_data['status'] == 'ok'
    assert res_data['result']['success'] is True

    leave_pending3.refresh_from_db()
    assert leave_pending3.status == TeacherLeaveRequest.Status.APPROVED
    print(f"✅ Test 5 Passed: Webhook successfully processed Telegram CallbackQuery and approved Leave #{leave_pending3.id}.")

    # Cleanup
    leave_pending.delete()
    leave_pending2.delete()
    leave_pending3.delete()
    TeacherAttendance.objects.filter(teacher=teacher).delete()

    print("==========================================================================")
    print("🎉 ALL INTERACTIVE TELEGRAM BUTTON TESTS PASSED 100%!")
    print("==========================================================================")

if __name__ == '__main__':
    test_telegram_leave_interactive_buttons()
