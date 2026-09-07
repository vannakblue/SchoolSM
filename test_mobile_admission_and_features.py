import os
import sys
import django

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.students.models import Student
from apps.academics.models import AcademicYear, Classroom

def run_tests():
    print("=== TESTING MOBILE ADMISSION & EXTENDED FEATURES ===")
    client = Client()

    # 1. Test GET /api/v1/students/enroll/ (Metadata without login)
    print("1. Testing GET /api/v1/students/enroll/...")
    resp = client.get('/api/v1/students/enroll/')
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.content}"
    data = resp.json()
    assert data['status'] == 'success'
    assert 'suggested_id' in data and data['suggested_id']
    assert 'academic_years' in data
    assert 'classrooms' in data
    assert 'genders' in data
    assert 'scholarship_types' in data
    print(f"   ✅ Enrollment Metadata OK! Suggested ID: {data['suggested_id']}, Classrooms: {len(data['classrooms'])}")

    # 2. Test Romanize API
    print("2. Testing GET /api/v1/students/romanize/...")
    resp_rom = client.get('/api/v1/students/romanize/?name=សុខ_សម្បត្តិ')
    assert resp_rom.status_code == 200
    print(f"   ✅ Romanize API OK: {resp_rom.json()}")

    # 3. Test Student Check ID API
    print("3. Testing GET /api/v1/students/check-id/...")
    resp_chk = client.get(f"/api/v1/students/check-id/?student_id={data['suggested_id']}")
    assert resp_chk.status_code == 200
    chk_json = resp_chk.json()
    assert chk_json['is_available'] is True
    print(f"   ✅ Check ID OK! Status: {chk_json['status']}")

    # 4. Test POST /api/v1/students/enroll/ (Submitting new student)
    print("4. Testing POST /api/v1/students/enroll/...")
    current_year = AcademicYear.objects.filter(is_current=True).first() or AcademicYear.objects.first()
    first_class = Classroom.objects.filter(academic_year=current_year).first() or Classroom.objects.first()

    enroll_payload = {
        'student_id': data['suggested_id'],
        'khmer_name': 'សិស្ស ពិសោធន៍ ម៉ូបាល',
        'latin_name': 'Piseth Mobile',
        'gender': 'M',
        'date_of_birth': '2009-03-12',
        'phone': '012888999',
        'place_of_birth': 'ភ្នំពេញ',
        'current_address': 'ខណ្ឌទួលគោក',
        'classroom_id': first_class.id if first_class else None,
        'academic_year_id': current_year.id if current_year else None,
        'scholarship_type': 'FULL_PAY',
        'father_name': 'ឪពុក ពិសោធន៍',
        'father_phone': '012111222',
        'mother_name': 'ម្តាយ ពិសោធន៍',
        'mother_phone': '012333444',
    }
    resp_enroll = client.post('/api/v1/students/enroll/', enroll_payload, content_type='application/json')
    assert resp_enroll.status_code == 201, f"Expected 201, got {resp_enroll.status_code}: {resp_enroll.content}"
    enroll_res = resp_enroll.json()
    assert enroll_res['status'] == 'success'
    created_sid = enroll_res['student']['student_id']
    print(f"   ✅ Enrolled student successfully! Student ID: {created_sid}")

    # Verify user account created
    u = User.objects.filter(username=created_sid.lower().replace('-', '_')).first()
    assert u is not None
    assert u.role == User.Role.STUDENT
    assert u.check_password('p123456')
    print(f"   ✅ Auto-created user credentials verified: {u.username} with role {u.role}")

    # 5. Test GET /api/v1/students/ (Student List & Search)
    print("5. Testing GET /api/v1/students/...")
    admin_user = User.objects.filter(role=User.Role.ADMIN).first()
    if not admin_user:
        admin_user = User.objects.create_superuser('test_admin_auto', 'admin@auto.test', 'pass123')
    client.force_login(admin_user)

    resp_list = client.get('/api/v1/students/?search=ពិសោធន៍')
    assert resp_list.status_code == 200
    list_json = resp_list.json()
    assert list_json['status'] == 'success'
    assert list_json['total_count'] >= 1
    found_student = any(s['student_id'] == created_sid for s in list_json['students'])
    assert found_student, f"Created student {created_sid} not found in search results"
    print(f"   ✅ Student list and search verified! Total found: {list_json['total_count']}")

    print("\n🎉 ALL MOBILE ADMISSION & EXTENDED FEATURES PASSED 100%!")

if __name__ == '__main__':
    run_tests()
