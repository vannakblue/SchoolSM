import os
import sys
import django
from datetime import time as dtime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import RequestFactory
from apps.accounts.models import User
from apps.attendance.models import AttendanceSetting
from apps.attendance.views import assembly_attendance_view

def test_assembly_view():
    print("=" * 60)
    print("TEST: Assembly Attendance Time Window String vs Time Bug Fix")
    print("=" * 60)

    # 1. Force strings into AttendanceSetting to reproduce bug condition
    att_settings = AttendanceSetting.get_settings()
    att_settings.assembly_morning_start = "06:30"
    att_settings.assembly_morning_end = "06:50"
    att_settings.assembly_afternoon_start = "12:30"
    att_settings.assembly_afternoon_end = "12:50"
    # Do NOT call clean so attributes remain strings in memory
    print(f"  [Setup] In-memory times set to strings: {type(att_settings.assembly_morning_start)}")

    # 2. Test Properties return datetime.time
    assert isinstance(att_settings.morning_start_time, dtime), "morning_start_time must be dtime!"
    assert isinstance(att_settings.morning_end_time, dtime), "morning_end_time must be dtime!"
    assert isinstance(att_settings.afternoon_start_time, dtime), "afternoon_start_time must be dtime!"
    assert isinstance(att_settings.afternoon_end_time, dtime), "afternoon_end_time must be dtime!"
    print("  ✓ Property helpers correctly parsed strings to datetime.time")

    # 3. Simulate Admin Request to /attendance/assembly/
    admin_user = User.objects.filter(is_superuser=True).first() or User.objects.filter(role=User.Role.ADMIN).first()
    if not admin_user:
        admin_user = User.objects.create_superuser('admin_test_assembly', 'admin@test.com', 'admin123')

    factory = RequestFactory()

    # Morning Session
    req_morning = factory.get('/attendance/assembly/?session=MORNING')
    req_morning.user = admin_user
    res_morning = assembly_attendance_view(req_morning)
    assert res_morning.status_code == 200, f"Morning assembly view failed with status {res_morning.status_code}"
    print("  ✓ /attendance/assembly/?session=MORNING returned 200 OK (no TypeError!)")

    # Afternoon Session
    req_afternoon = factory.get('/attendance/assembly/?session=AFTERNOON')
    req_afternoon.user = admin_user
    res_afternoon = assembly_attendance_view(req_afternoon)
    assert res_afternoon.status_code == 200, f"Afternoon assembly view failed with status {res_afternoon.status_code}"
    print("  ✓ /attendance/assembly/?session=AFTERNOON returned 200 OK (no TypeError!)")

    # 4. Save and verify clean() ensures database records are converted to dtime
    att_settings.save()
    att_settings.refresh_from_db()
    assert isinstance(att_settings.assembly_morning_start, dtime), "assembly_morning_start should be dtime after save!"
    print("  ✓ clean() and save() converted persisted values to datetime.time")

    print("\n" + "=" * 60)
    print("🎉 ALL ASSEMBLY ATTENDANCE BUG FIX TESTS PASSED 100%!")
    print("=" * 60)

if __name__ == '__main__':
    test_assembly_view()
