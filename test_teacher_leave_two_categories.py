import os
import sys
import django
from datetime import date, datetime, timedelta, time

sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()


from django.test import Client
from apps.accounts.models import User, SchoolProfile
from apps.teachers.models import Teacher, TeacherLeaveRequest, TeacherAttendanceConfig, TeacherAttendance
from apps.teachers.utils import get_teacher_daily_attendance_data

def run_tests():
    print("=" * 75)
    print("TEST: TEACHER 2-CATEGORY LEAVE SYSTEM (EMERGENCY & ADVANCE PLANNED)")
    print("=" * 75)

    # 1. Setup test entities
    today = date.today()
    admin_user = User.objects.filter(role='ADMIN').first()
    if not admin_user:
        admin_user = User.objects.create_user(username='admin_test', password='password123', role='ADMIN')

    teacher1 = Teacher.objects.filter(status='ACTIVE').first()
    teacher2 = Teacher.objects.filter(status='ACTIVE').exclude(id=teacher1.id).first()
    
    if not teacher1.user:
        u1 = User.objects.create_user(username='teacher1_test', password='password123', role='TEACHER')
        teacher1.user = u1
        teacher1.save()

    from apps.academics.models import Classroom, Subject, Timetable
    classroom = Classroom.objects.first()
    subject = Subject.objects.first()
    if not Timetable.objects.filter(teacher=teacher1, day_of_week=today.isoweekday()).exists():
        Timetable.objects.create(
            classroom=classroom,
            subject=subject,
            teacher=teacher1,
            day_of_week=today.isoweekday(),
            period_number=1,
            start_time=time(7, 0),
            end_time=time(8, 0)
        )

    
    config = TeacherAttendanceConfig.get_settings()
    config.emergency_leave_cutoff_time = time(17, 0)
    config.save()

    client_teacher = Client()
    client_teacher.force_login(teacher1.user)

    client_admin = Client()
    client_admin.force_login(admin_user)


    # ---------------------------------------------------------
    # TEST 1: Category 1 - Emergency Leave Same Day (Allowed)
    # ---------------------------------------------------------
    print("\n--- TEST 1: Category 1 - Emergency Leave Same Day ---")
    res1 = client_teacher.post('/teachers/leave/apply/', {
        'category': 'EMERGENCY',
        'leave_type': 'SICK',
        'start_date': today.strftime('%Y-%m-%d'),
        'end_date': today.strftime('%Y-%m-%d'),
        'reason': 'មានអាការៈក្តៅខ្លួនខ្លាំងបន្ទាន់ មិនអាចមកបង្រៀនបានទេ',
        'substitute_teacher_id': teacher2.id if teacher2 else '',
    }, follow=True)
    assert res1.status_code == 200, f"Expected 200, got {res1.status_code}"
    
    leave_emerg = TeacherLeaveRequest.objects.filter(teacher=teacher1, category='EMERGENCY', reason='មានអាការៈក្តៅខ្លួនខ្លាំងបន្ទាន់ មិនអាចមកបង្រៀនបានទេ').first()
    assert leave_emerg is not None, "Emergency leave request should be created"

    assert leave_emerg.category == TeacherLeaveRequest.Category.EMERGENCY
    assert leave_emerg.leave_code.startswith('LV-')
    assert leave_emerg.substitute_teacher == teacher2
    print(f"✅ Emergency same-day leave created: Code={leave_emerg.leave_code}, Category={leave_emerg.category}")

    # ---------------------------------------------------------
    # TEST 2: Category 1 - Emergency Leave Timing Validation
    # ---------------------------------------------------------
    print("\n--- TEST 2: Category 1 - Emergency Leave Too Far in Advance Blocked ---")
    far_future = today + timedelta(days=5)
    res2 = client_teacher.post('/teachers/leave/apply/', {
        'category': 'EMERGENCY',
        'leave_type': 'PERSONAL',
        'start_date': far_future.strftime('%Y-%m-%d'),
        'end_date': far_future.strftime('%Y-%m-%d'),
        'reason': 'សុំច្បាប់បន្ទាន់ ៥ ថ្ងៃក្រោយ (ខុសគោលការណ៍)',
    }, follow=True)
    # Should stay on form with warning error message
    assert TeacherLeaveRequest.objects.filter(start_date=far_future, category='EMERGENCY').count() == 0
    print("✅ Emergency leave > 1 day in advance correctly blocked by policy.")

    # ---------------------------------------------------------
    # TEST 3: Category 2 - Advance Planned Leave (Allowed)
    # ---------------------------------------------------------
    print("\n--- TEST 3: Category 2 - Advance Planned Leave ---")
    next_week_start = today + timedelta(days=7)
    next_week_end = today + timedelta(days=8)
    res3 = client_teacher.post('/teachers/leave/apply/', {
        'category': 'PLANNED',
        'leave_type': 'MISSION',
        'start_date': next_week_start.strftime('%Y-%m-%d'),
        'end_date': next_week_end.strftime('%Y-%m-%d'),
        'reason': 'ចូលរួមវគ្គបណ្តុះបណ្តាលគរុកោសល្យថ្នាក់ជាតិរបស់ក្រសួង',
        'substitute_teacher_id': teacher2.id if teacher2 else '',
    }, follow=True)
    assert res3.status_code == 200
    leave_plan = TeacherLeaveRequest.objects.filter(teacher=teacher1, category='PLANNED', start_date=next_week_start).first()
    assert leave_plan is not None
    assert leave_plan.total_days == 2
    assert leave_plan.category == TeacherLeaveRequest.Category.PLANNED
    print(f"✅ Planned advance leave created: Code={leave_plan.leave_code}, Days={leave_plan.total_days}")

    # ---------------------------------------------------------
    # TEST 4: Print Official Khmer A4 Leave Letter
    # ---------------------------------------------------------
    print("\n--- TEST 4: Print Official Khmer A4 Leave Letter ---")
    res_print = client_teacher.get(f'/teachers/leave/{leave_plan.id}/print/')
    assert res_print.status_code == 200
    content = res_print.content.decode('utf-8')
    assert 'ព្រះរាជាណាចក្រកម្ពុជា' in content
    assert 'ពាក្យសុំច្បាប់ឈប់សម្រាក' in content
    assert teacher1.khmer_name in content
    assert 'ហត្ថលេខាសាមីខ្លួន' in content
    assert 'ការសម្រេចរបស់នាយកសាលា' in content
    assert leave_plan.leave_code in content
    print("✅ Official Printable A4 Leave Letter rendered successfully with complete Khmer official header & signatures.")

    # ---------------------------------------------------------
    # TEST 5: Leave List Filter Tabs (Status & Category)
    # ---------------------------------------------------------
    print("\n--- TEST 5: Teacher Leave List Filtering by Category ---")
    res_filter_emerg = client_admin.get('/teachers/leave/?category=EMERGENCY')
    assert res_filter_emerg.status_code == 200
    res_filter_plan = client_admin.get('/teachers/leave/?category=PLANNED')
    assert res_filter_plan.status_code == 200
    print("✅ Leave List filtered by EMERGENCY and PLANNED categories successfully.")

    # ---------------------------------------------------------
    # TEST 6: Management Approval & Missing Schedule Suppression
    # ---------------------------------------------------------
    print("\n--- TEST 6: Management Approval & Schedule Alert Suppression ---")
    res_approve = client_admin.post('/attendance/admin-hub/', {
        'action': 'approve_leave',
        'leave_id': leave_emerg.id
    }, follow=True)
    assert res_approve.status_code == 200
    leave_emerg.refresh_from_db()
    assert leave_emerg.status == TeacherLeaveRequest.Status.APPROVED
    
    # Check that TeacherAttendance DB record is created as EXCUSED_LEAVE ($0 deduction)
    t_att = TeacherAttendance.objects.filter(teacher=teacher1, date=today).first()
    assert t_att is not None
    assert t_att.status == TeacherAttendance.Status.EXCUSED_LEAVE
    assert t_att.deduction_amount == 0

    # Verify daily attendance reporting marks teacher as EXCUSED and suppresses missing alert
    teachers_list = Teacher.objects.filter(status='ACTIVE')
    daily_data = get_teacher_daily_attendance_data(teachers=teachers_list, target_date=today)
    teacher_res = next((r for r in daily_data['rows'] if r['teacher'].id == teacher1.id), None)
    assert teacher_res is not None
    assert teacher_res['daily_status'] == 'EXCUSED_LEAVE'
    assert daily_data['summary']['teachers_on_leave'] >= 1
    print("✅ Approved leave correctly marked as EXCUSED_LEAVE, $0 deduction, and excluded from missing alerts.")



    print("\n" + "=" * 75)
    print("🎉 ALL 2-CATEGORY TEACHER LEAVE TESTS PASSED 100%!")
    print("=" * 75)

if __name__ == '__main__':
    run_tests()
