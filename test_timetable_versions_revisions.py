import os
import sys
import django
import json

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.academics.models import AcademicYear, Classroom, Subject, ClassSubject, Timetable, TimetableVersion
from apps.teachers.models import Teacher
from datetime import time, date

def run_tests():
    print("=== STARTING TIMETABLE VERSIONING & REVISION SYSTEM TESTS ===")
    
    # 1. Setup Admin User & Client
    admin_user, _ = User.objects.get_or_create(
        username='test_admin_tt_ver',
        defaults={'role': 'ADMIN', 'is_staff': True, 'is_superuser': True}
    )
    admin_user.set_password('Admin@123456')
    admin_user.role = 'ADMIN'
    admin_user.save()

    client = Client()
    client.force_login(admin_user)

    # 2. Setup Academic Year, Class, Teacher, Subject
    year, _ = AcademicYear.objects.get_or_create(
        name='2026-2027 TEST',
        defaults={'start_date': date(2026, 1, 1), 'end_date': date(2026, 12, 31), 'is_current': True}
    )
    
    teachers = list(Teacher.objects.filter(status='ACTIVE')[:2])
    if len(teachers) >= 2:
        teacher1, teacher2 = teachers[0], teachers[1]
    else:
        teacher1, _ = Teacher.objects.get_or_create(
            teacher_id='T_TEST_VER_1',
            defaults={'khmer_name': 'លោកគ្រូ តេស្ត ១', 'latin_name': 'Teacher Test 1', 'status': 'ACTIVE'}
        )
        teacher2, _ = Teacher.objects.get_or_create(
            teacher_id='T_TEST_VER_2',
            defaults={'khmer_name': 'អ្នកគ្រូ តេស្ត ២', 'latin_name': 'Teacher Test 2', 'status': 'ACTIVE', 'gender': 'F'}
        )

    cls_7a, _ = Classroom.objects.get_or_create(
        name='7A_TEST_VER',
        academic_year=year,
        defaults={'grade_level': 7, 'code': '7A_TEST'}
    )

    sub_kh, _ = Subject.objects.get_or_create(
        code='K_TEST_VER',
        defaults={'name_kh': 'ភាសាខ្មែរ តេស្ត', 'name_en': 'Khmer Test', 'category': 'GENERAL'}
    )
    sub_math, _ = Subject.objects.get_or_create(
        code='M_TEST_VER',
        defaults={'name_kh': 'គណិតវិទ្យា តេស្ត', 'name_en': 'Math Test', 'category': 'SCIENCE'}
    )

    # Clean existing test versions
    TimetableVersion.objects.filter(academic_year=year).delete()
    Timetable.objects.filter(classroom=cls_7a).delete()

    print("1. [PASS] Setup test environment and baseline fixtures.")

    # 3. Test GET Timetable Versions List (Empty)
    resp = client.get(f'/academics/timetable/versions/?academic_year_id={year.id}')
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    assert data['status'] == 'success'
    assert data['count'] == 0
    assert data['next_version_number'] == 1
    print("2. [PASS] GET /academics/timetable/versions/ returns empty list with next_version_number=1.")

    # 4. Create Version 1 (លើកទី ១)
    matrix_v1 = [
        {
            'classroom_id': cls_7a.id,
            'subject_id': sub_kh.id,
            'teacher_id': teacher1.id,
            'day_of_week': 1,
            'period_number': 1,
            'room': 'Room 101'
        },
        {
            'classroom_id': cls_7a.id,
            'subject_id': sub_kh.id,
            'teacher_id': teacher1.id,
            'day_of_week': 1,
            'period_number': 2,
            'room': 'Room 101'
        }
    ]

    resp_v1 = client.post(
        '/academics/timetable/versions/save/',
        data=json.dumps({
            'academic_year_id': year.id,
            'version_number': 1,
            'title': 'លើកទី ១ - កាលវិភាគដើមឆ្នាំ',
            'note': 'រៀបចំម៉ោងដំបូងសម្រាប់ឆមាសទី១',
            'set_active': True,
            'matrix': matrix_v1,
            'blocked_slots': [{'classroom_id': cls_7a.id, 'day_of_week': 6, 'period_number': 5, 'is_blocked': True}],
        }),
        content_type='application/json'
    )
    assert resp_v1.status_code == 200, f"Expected 200, got {resp_v1.status_code}: {resp_v1.content}"
    data_v1 = resp_v1.json()
    assert data_v1['status'] == 'success'
    assert data_v1['version']['version_number'] == 1
    assert data_v1['version']['total_slots'] == 2
    assert data_v1['version']['is_active_applied'] == True

    v1_obj = TimetableVersion.objects.get(academic_year=year, version_number=1)
    assert v1_obj.total_slots == 2
    assert v1_obj.is_active_applied == True
    print("3. [PASS] Created Version 1 (លើកទី ១) in database with 2 slots and is_active_applied=True.")

    # 5. Create Version 2 (លើកទី ២)
    matrix_v2 = [
        {
            'classroom_id': cls_7a.id,
            'subject_id': sub_math.id,
            'teacher_id': teacher2.id,
            'day_of_week': 2,
            'period_number': 1,
            'room': 'Room 102'
        },
        {
            'classroom_id': cls_7a.id,
            'subject_id': sub_math.id,
            'teacher_id': teacher2.id,
            'day_of_week': 2,
            'period_number': 2,
            'room': 'Room 102'
        },
        {
            'classroom_id': cls_7a.id,
            'subject_id': sub_math.id,
            'teacher_id': teacher2.id,
            'day_of_week': 2,
            'period_number': 3,
            'room': 'Room 102'
        }
    ]

    resp_v2 = client.post(
        '/academics/timetable/versions/save/',
        data=json.dumps({
            'academic_year_id': year.id,
            'version_number': 2,
            'title': 'លើកទី ២ - កែសម្រួលគ្រូគណិត',
            'note': 'ប្តូរគ្រូគណិតវិទ្យាទៅអ្នកគ្រូតេស្ត២',
            'set_active': True,
            'matrix': matrix_v2,
        }),
        content_type='application/json'
    )
    assert resp_v2.status_code == 200
    data_v2 = resp_v2.json()
    assert data_v2['status'] == 'success'
    assert data_v2['version']['version_number'] == 2
    assert data_v2['version']['total_slots'] == 3

    v1_obj.refresh_from_db()
    v2_obj = TimetableVersion.objects.get(academic_year=year, version_number=2)
    assert v1_obj.is_active_applied == False, "V1 should no longer be active"
    assert v2_obj.is_active_applied == True, "V2 should now be active"
    print("4. [PASS] Created Version 2 (លើកទី ២) with 3 slots and properly updated active flags.")

    # 6. Test GET List of Versions
    resp_list = client.get(f'/academics/timetable/versions/?academic_year_id={year.id}')
    assert resp_list.status_code == 200
    list_data = resp_list.json()
    assert list_data['count'] == 2
    assert list_data['next_version_number'] == 3
    print("5. [PASS] GET versions list shows 2 revisions and next_version_number=3.")

    # 7. Test RESTORE Version 1 (ទាញយកលើកទី១ មកប្រើ)
    resp_restore1 = client.post(f'/academics/timetable/versions/{v1_obj.id}/restore/')
    assert resp_restore1.status_code == 200
    r1_data = resp_restore1.json()
    assert r1_data['status'] == 'success'
    assert r1_data['count'] == 2

    # Verify Timetable table now has exactly the 2 slots from Version 1
    tt_entries_v1 = list(Timetable.objects.filter(classroom=cls_7a))
    assert len(tt_entries_v1) == 2
    assert tt_entries_v1[0].subject_id == sub_kh.id
    assert tt_entries_v1[0].teacher_id == teacher1.id
    assert tt_entries_v1[0].day_of_week == 1

    v1_obj.refresh_from_db()
    v2_obj.refresh_from_db()
    assert v1_obj.is_active_applied == True
    assert v2_obj.is_active_applied == False
    print("6. [PASS] Restored Version 1 (លើកទី ១) into live Timetable table (2 slots matching V1).")

    # 8. Test RESTORE Version 2 (ទាញយកលើកទី២ មកប្រើ)
    resp_restore2 = client.post(f'/academics/timetable/versions/{v2_obj.id}/restore/')
    assert resp_restore2.status_code == 200
    r2_data = resp_restore2.json()
    assert r2_data['status'] == 'success'
    assert r2_data['count'] == 3

    # Verify Timetable table now has exactly the 3 slots from Version 2
    tt_entries_v2 = list(Timetable.objects.filter(classroom=cls_7a))
    assert len(tt_entries_v2) == 3
    assert tt_entries_v2[0].subject_id == sub_math.id
    assert tt_entries_v2[0].teacher_id == teacher2.id
    assert tt_entries_v2[0].day_of_week == 2
    print("7. [PASS] Restored Version 2 (លើកទី ២) into live Timetable table (3 slots matching V2).")

    # 9. Test UPDATE Version (កែប្រែចំណងជើង/កំណត់សម្គាល់)
    resp_upd = client.post(
        f'/academics/timetable/versions/{v1_obj.id}/update/',
        data=json.dumps({'title': 'លើកទី ១ (កែឈ្មោះថ្មី)', 'note': 'កំណត់សម្គាល់ថ្មី'}),
        content_type='application/json'
    )
    assert resp_upd.status_code == 200
    v1_obj.refresh_from_db()
    assert v1_obj.title == 'លើកទី ១ (កែឈ្មោះថ្មី)'
    assert v1_obj.note == 'កំណត់សម្គាល់ថ្មី'
    print("8. [PASS] Updated Version 1 title and note successfully.")

    # 10. Test EXPORT Version (ទាញយក JSON)
    resp_exp = client.get(f'/academics/timetable/versions/{v1_obj.id}/export/')
    assert resp_exp.status_code == 200
    assert 'application/json' in resp_exp['Content-Type']
    exp_json = json.loads(resp_exp.content.decode('utf-8'))
    assert exp_json['type'] == 'timetable_version_snapshot'
    assert exp_json['version_number'] == 1
    assert exp_json['total_slots'] == 2
    print("9. [PASS] Exported Version 1 JSON file successfully.")

    # 11. Test DELETE Version (លុបកំណែ)
    resp_del = client.post(f'/academics/timetable/versions/{v2_obj.id}/delete/')
    assert resp_del.status_code == 200
    assert not TimetableVersion.objects.filter(id=v2_obj.id).exists()
    print("10. [PASS] Deleted Version 2 successfully.")

    # 12. Test Timetable View HTML Rendering
    resp_html = client.get(f'/academics/timetable/?year={year.id}')
    assert resp_html.status_code == 200
    html_content = resp_html.content.decode('utf-8')
    assert 'selectTimetableVersion' in html_content
    assert 'saveTimetableVersionModal' in html_content
    assert 'timetableVersionsModal' in html_content
    assert 'រក្សាទុកលើកថ្មី' in html_content
    assert 'កំណែកាលវិភាគ' in html_content
    print("11. [PASS] Timetable View renders with version switcher, save version modal, and versions history modal.")

    # Clean up test records
    TimetableVersion.objects.filter(academic_year=year).delete()
    Timetable.objects.filter(classroom=cls_7a).delete()
    cls_7a.delete()
    sub_kh.delete()
    sub_math.delete()
    teacher1.delete()
    teacher2.delete()
    year.delete()

    print("\n=== ALL 11 TIMETABLE VERSIONING TESTS PASSED 100%! ===")

if __name__ == '__main__':
    run_tests()
