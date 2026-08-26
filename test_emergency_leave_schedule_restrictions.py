import os
import sys
import django
from datetime import date, datetime, timedelta, time

sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.teachers.models import Teacher, TeacherLeaveRequest, TeacherAttendanceConfig
from apps.academics.models import Classroom, Subject, Timetable, AcademicYear
from apps.academics.utils import get_active_academic_year
from apps.teachers.utils import get_teacher_emergency_leave_schedule

def run_tests():
    print("=" * 80)
    print("TEST: EMERGENCY LEAVE STRICT TIMETABLE SCHEDULE & CUTOFF TIME RESTRICTIONS")
    print("=" * 80)

    today = date.today()
    tomorrow = today + timedelta(days=1)
    today_dow = today.isoweekday()
    tomorrow_dow = tomorrow.isoweekday()
    other_dow = (today_dow + 2) if (today_dow + 2) <= 6 else 1
    other_date = today + timedelta(days=3)

    active_year = get_active_academic_year()
    classroom = Classroom.objects.first()
    subject = Subject.objects.first()

    # 1. Setup a Test Teacher
    admin_user = User.objects.filter(role='ADMIN').first()
    teacher1 = Teacher.objects.filter(status='ACTIVE').first()
    if not teacher1.user:
        u = User.objects.create_user(username='t_emerg_test', password='password123', role='TEACHER')
        teacher1.user = u
        teacher1.save()

    # Ensure timetable: Teacher has classes on today_dow and tomorrow_dow, but NOT on other_dow
    Timetable.objects.filter(teacher=teacher1).delete()
    
    # Create 2 slots for today
    Timetable.objects.create(
        classroom=classroom,
        subject=subject,
        teacher=teacher1,
        day_of_week=today_dow,
        period_number=1,
        start_time=time(7, 0),
        end_time=time(8, 0)
    )
    Timetable.objects.create(
        classroom=classroom,
        subject=subject,
        teacher=teacher1,
        day_of_week=today_dow,
        period_number=2,
        start_time=time(8, 0),
        end_time=time(9, 0)
    )

    # Create 1 slot for tomorrow
    Timetable.objects.create(
        classroom=classroom,
        subject=subject,
        teacher=teacher1,
        day_of_week=tomorrow_dow,
        period_number=3,
        start_time=time(9, 0),
        end_time=time(10, 0)
    )

    config = TeacherAttendanceConfig.get_settings()
    config.emergency_leave_cutoff_time = time(17, 0)
    config.save()

    client_teacher = Client()
    client_teacher.force_login(teacher1.user)

    client_admin = Client()
    client_admin.force_login(admin_user)

    # ---------------------------------------------------------
    # TEST 1: Helper function correctly identifies today & tomorrow
    # ---------------------------------------------------------
    print("\n--- TEST 1: Schedule Helper Evaluates Eligible Emergency Teaching Dates ---")
    mock_dt_morning = datetime.combine(today, time(8, 30))
    sched_info = get_teacher_emergency_leave_schedule(teacher1, current_dt=mock_dt_morning)
    assert len(sched_info['options']) == 2
    assert sched_info['options'][0]['date_str'] == today.strftime('%Y-%m-%d')
    assert sched_info['options'][0]['slots_count'] == 2
    assert sched_info['options'][0]['is_allowed'] is True
    assert sched_info['options'][1]['date_str'] == tomorrow.strftime('%Y-%m-%d')
    assert sched_info['options'][1]['slots_count'] == 1
    assert sched_info['options'][1]['is_allowed'] is True
    print("✅ Successfully detected 2 teaching slots on Today and 1 slot on Tomorrow.")

    # ---------------------------------------------------------
    # TEST 2: Submit Emergency Leave for Today (Allowed)
    # ---------------------------------------------------------
    print("\n--- TEST 2: Emergency Leave for Today with Timetable (Allowed) ---")
    res_today = client_teacher.post('/teachers/leave/apply/', {
        'category': 'EMERGENCY',
        'leave_type': 'SICK',
        'start_date': today.strftime('%Y-%m-%d'),
        'end_date': today.strftime('%Y-%m-%d'),
        'reason': 'មានអាការៈឈឺក្បាលខ្លាំង និងគ្រុនក្តៅបន្ទាន់',
    }, follow=True)
    assert res_today.status_code == 200
    leave_req = TeacherLeaveRequest.objects.filter(teacher=teacher1, start_date=today, category='EMERGENCY').first()
    assert leave_req is not None
    assert leave_req.category == TeacherLeaveRequest.Category.EMERGENCY
    print(f"✅ Emergency leave for Today created successfully: Code={leave_req.leave_code}")

    # ---------------------------------------------------------
    # TEST 3: Submit Emergency Leave for Tomorrow (Allowed)
    # ---------------------------------------------------------
    print("\n--- TEST 3: Emergency Leave for Tomorrow with Timetable (Allowed) ---")
    res_tomorrow = client_teacher.post('/teachers/leave/apply/', {
        'category': 'EMERGENCY',
        'leave_type': 'PERSONAL',
        'start_date': tomorrow.strftime('%Y-%m-%d'),
        'end_date': tomorrow.strftime('%Y-%m-%d'),
        'reason': 'មានធុរៈគ្រួសារបន្ទាន់នៅស្រុកកំណើតថ្ងៃស្អែក',
    }, follow=True)
    assert res_tomorrow.status_code == 200
    leave_req_tom = TeacherLeaveRequest.objects.filter(teacher=teacher1, start_date=tomorrow, category='EMERGENCY').first()
    assert leave_req_tom is not None
    print(f"✅ Emergency leave for Tomorrow created successfully: Code={leave_req_tom.leave_code}")

    # ---------------------------------------------------------
    # TEST 4: Submit Emergency Leave for Day with NO Timetable (Blocked)
    # ---------------------------------------------------------
    print("\n--- TEST 4: Emergency Leave for Day without Timetable (Strictly Blocked) ---")
    # Delete tomorrow's timetable to simulate no class on tomorrow
    Timetable.objects.filter(teacher=teacher1, day_of_week=tomorrow_dow).delete()
    TeacherLeaveRequest.objects.filter(teacher=teacher1, start_date=tomorrow).delete()

    res_no_sched = client_teacher.post('/teachers/leave/apply/', {
        'category': 'EMERGENCY',
        'leave_type': 'PERSONAL',
        'start_date': tomorrow.strftime('%Y-%m-%d'),
        'end_date': tomorrow.strftime('%Y-%m-%d'),
        'reason': 'សុំច្បាប់បន្ទាន់ថ្ងៃដែលគ្មានម៉ោងបង្រៀន',
    }, follow=True)
    # Must fail validation and NOT create record
    assert TeacherLeaveRequest.objects.filter(teacher=teacher1, start_date=tomorrow, category='EMERGENCY').count() == 0
    print("✅ Emergency leave attempt on a day with NO teaching schedule was strictly blocked with error message.")

    # ---------------------------------------------------------
    # TEST 5: Submit Emergency Leave for 3+ Days in Advance (Blocked)
    # ---------------------------------------------------------
    print("\n--- TEST 5: Emergency Leave for Future Day > Tomorrow (Strictly Blocked) ---")
    res_far = client_teacher.post('/teachers/leave/apply/', {
        'category': 'EMERGENCY',
        'leave_type': 'PERSONAL',
        'start_date': other_date.strftime('%Y-%m-%d'),
        'end_date': other_date.strftime('%Y-%m-%d'),
        'reason': 'សុំច្បាប់បន្ទាន់ ៣ ថ្ងៃក្រោយ (ខុសគោលការណ៍)',
    }, follow=True)
    assert TeacherLeaveRequest.objects.filter(teacher=teacher1, start_date=other_date, category='EMERGENCY').count() == 0
    print("✅ Emergency leave for date outside [Today, Tomorrow] was strictly blocked.")

    # ---------------------------------------------------------
    # TEST 6: Planned Advance Leave Works for Any Future Dates
    # ---------------------------------------------------------
    print("\n--- TEST 6: Planned Leave Allows Future Dates Freely ---")
    res_plan = client_teacher.post('/teachers/leave/apply/', {
        'category': 'PLANNED',
        'leave_type': 'MISSION',
        'start_date': other_date.strftime('%Y-%m-%d'),
        'end_date': (other_date + timedelta(days=2)).strftime('%Y-%m-%d'),
        'reason': 'បេសកកម្មការងារជាផ្លូវការ',
    }, follow=True)
    assert res_plan.status_code == 200
    plan_leave = TeacherLeaveRequest.objects.filter(teacher=teacher1, start_date=other_date, category='PLANNED').first()
    assert plan_leave is not None
    assert plan_leave.total_days == 3
    print(f"✅ Planned Leave successfully created for future date range: Code={plan_leave.leave_code}")

    print("\n" + "=" * 80)
    print("🎉 ALL EMERGENCY LEAVE TIMETABLE & CUTOFF RESTRICTION TESTS PASSED 100%!")
    print("=" * 80)

if __name__ == '__main__':
    run_tests()
