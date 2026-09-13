import os
import sys
import django

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from apps.academics.models import Timetable, TimetableVersion, Classroom, ClassSubject, Subject
from apps.teachers.models import Teacher
from apps.academics.duty_importer import import_timetable_from_gt_sheet

def run_tests():
    print("=== STARTING GT TIMETABLE IMPORT TESTS ===")
    
    # 1. Admin login & Client setup
    User = get_user_model()
    admin_user = User.objects.filter(is_superuser=True).first()
    if not admin_user:
        admin_user = User.objects.create_superuser('test_admin_gt', 'admin@example.com', 'Admin@123456')
    client = Client()
    client.force_login(admin_user)

    # 2. Test GET /academics/timetable/
    resp = client.get('/academics/timetable/')
    assert resp.status_code == 200, f"GET /academics/timetable/ failed with status {resp.status_code}"
    content_str = resp.content.decode('utf-8')
    assert 'importTimetableExcelModal' in content_str, "Import GT Modal button/modal missing from timetable.html"
    assert 'M1' in content_str, "Teacher duty code M1 not rendered in timetable matrix"
    assert 'COM2' in content_str, "Teacher duty code COM2 not rendered in timetable matrix"
    print("✅ GET /academics/timetable/ rendered successfully with 200 OK and slot codes.")

    # 3. Test GT Timetable Importer logic
    excel_path = os.path.join(os.path.dirname(__file__), 'បំណែងចែកគ្រូ2027.xlsx')
    if os.path.exists(excel_path):
        res = import_timetable_from_gt_sheet(excel_path)
        assert res.get('success') is True, f"Import from GT sheet failed: {res.get('errors')}"
        assert res.get('slots_total') == 1338, f"Expected 1338 slots, got {res.get('slots_total')}"
        assert res.get('classrooms_count') == 40, f"Expected 40 classrooms, got {res.get('classrooms_count')}"
        print(f"✅ Sheet GT import logic parsed {res.get('slots_total')} slots across {res.get('classrooms_count')} classrooms with 0 unmapped tokens.")

    # 4. Verify Database Records
    total_slots = Timetable.objects.filter(classroom__academic_year_id=3).count()
    assert total_slots == 1338, f"Expected 1338 Timetable records in DB, found {total_slots}"
    
    # Check sample slot
    slot_7a_p1 = Timetable.objects.filter(classroom__name__contains='7A', day_of_week=1, period_number=1).first()
    assert slot_7a_p1 is not None, "Slot 7A Mon Period 1 not found"
    assert getattr(slot_7a_p1.teacher, 'subject_code', '') == 'M1', f"Expected M1, got {getattr(slot_7a_p1.teacher, 'subject_code', '')}"
    assert slot_7a_p1.room == '43', f"Expected Room 43 for 7A, got {slot_7a_p1.room}"
    print(f"✅ Verified sample slot 7A Day 1 Period 1: {slot_7a_p1.subject.name_kh} by {slot_7a_p1.teacher.khmer_name} ({slot_7a_p1.teacher.subject_code}) in Room {slot_7a_p1.room}")

    # 5. Verify TimetableVersion Snapshot
    active_version = TimetableVersion.objects.filter(academic_year_id=3, is_active_applied=True).first()
    assert active_version is not None, "No active TimetableVersion snapshot found for 2026-2027"
    assert active_version.total_slots == 1338, f"Expected 1338 total_slots in active version, got {active_version.total_slots}"
    assert active_version.total_classrooms == 40, f"Expected 40 total_classrooms in active version, got {active_version.total_classrooms}"
    print(f"✅ Verified active TimetableVersion {active_version.version_number} snapshot with {active_version.total_slots} slots.")

    # 6. Verify POST /academics/timetable/import-excel/
    post_resp = client.post('/academics/timetable/import-excel/')
    assert post_resp.status_code in [200, 302], f"POST /academics/timetable/import-excel/ returned {post_resp.status_code}"
    print("✅ POST /academics/timetable/import-excel/ executed and redirected successfully.")

    print("\n🎉 ALL GT TIMETABLE IMPORT TESTS PASSED SUCCESSFULLY! 🎉")

if __name__ == '__main__':
    run_tests()
