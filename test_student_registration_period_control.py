import os
import django
import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.utils import timezone
from django.test import Client
from django.test.utils import setup_test_environment
from apps.accounts.models import SchoolProfile, User
from apps.academics.models import AcademicYear, Classroom, GradeLevel

setup_test_environment()

def run_tests():
    print("=== STARTING STUDENT REGISTRATION PERIOD CONTROL TESTS ===")
    client = Client()
    profile = SchoolProfile.get_settings()
    now = timezone.now()

    # Create admin user if not exists
    admin_user = User.objects.filter(role=User.Role.ADMIN).first()
    if not admin_user:
        admin_user = User.objects.create_user(
            username='test_admin_reg',
            password='password123',
            role=User.Role.ADMIN,
            is_staff=True
        )

    # 1. Test Model Logic
    print("\n--- 1. Testing SchoolProfile.is_student_registration_allowed() ---")
    
    # Test A: Manually closed
    profile.is_registration_open = False
    profile.registration_start_date = None
    profile.registration_end_date = None
    profile.save()
    allowed, reason, code = profile.is_student_registration_allowed()
    assert not allowed and code == 'CLOSED_MANUAL', f"Expected CLOSED_MANUAL, got {code}"
    print("  [PASS] Closed manually -> CLOSED_MANUAL")

    # Test B: Unrestricted open
    profile.is_registration_open = True
    profile.registration_start_date = None
    profile.registration_end_date = None
    profile.save()
    allowed, reason, code = profile.is_student_registration_allowed()
    assert allowed and code == 'OPEN', f"Expected OPEN, got {code}"
    print("  [PASS] Open unrestricted -> OPEN")

    # Test C: Future start date
    profile.is_registration_open = True
    profile.registration_start_date = now + datetime.timedelta(days=2)
    profile.registration_end_date = now + datetime.timedelta(days=10)
    profile.save()
    allowed, reason, code = profile.is_student_registration_allowed()
    assert not allowed and code == 'NOT_STARTED', f"Expected NOT_STARTED, got {code}"
    print("  [PASS] Future start date -> NOT_STARTED")

    # Test D: Expired end date
    profile.is_registration_open = True
    profile.registration_start_date = now - datetime.timedelta(days=10)
    profile.registration_end_date = now - datetime.timedelta(days=1)
    profile.save()
    allowed, reason, code = profile.is_student_registration_allowed()
    assert not allowed and code == 'EXPIRED', f"Expected EXPIRED, got {code}"
    print("  [PASS] Expired end date -> EXPIRED")

    # Test E: Active window
    profile.is_registration_open = True
    profile.registration_start_date = now - datetime.timedelta(days=1)
    profile.registration_end_date = now + datetime.timedelta(days=5)
    profile.save()
    allowed, reason, code = profile.is_student_registration_allowed()
    assert allowed and code == 'OPEN', f"Expected OPEN, got {code}"
    print("  [PASS] Active window -> OPEN")

    # 2. Test Web Portal
    print("\n--- 2. Testing Web Portal Views ---")
    
    # Portal when OPEN
    resp = client.get('/students/enroll/online/')
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    assert 'is_reg_allowed' in resp.context and resp.context['is_reg_allowed'] is True
    print("  [PASS] Public enroll GET when OPEN -> renders enrollment form (is_reg_allowed=True)")

    # Portal when CLOSED
    profile.is_registration_open = False
    profile.save()
    resp = client.get('/students/enroll/online/')
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    # Should render registration_closed.html template
    assert any('registration_closed.html' in t.name for t in resp.templates if t.name)
    print("  [PASS] Public enroll GET when CLOSED -> renders registration_closed.html")

    # Staff preview when CLOSED
    client.force_login(admin_user)
    resp = client.get('/students/enroll/online/')
    assert resp.status_code == 200
    assert resp.context.get('is_staff_preview') is True
    print("  [PASS] Staff enroll GET when CLOSED -> renders with is_staff_preview=True")

    # QR Code page includes control data
    resp = client.get('/students/enroll/qr/')
    assert resp.status_code == 200
    assert 'reg_status' in resp.context
    print("  [PASS] Admin QR Code page loads with registration period context")

    # AJAX save registration period endpoint
    post_data = {
        'is_registration_open': 'true',
        'registration_start_date': (now - datetime.timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'),
        'registration_end_date': (now + datetime.timedelta(days=14)).strftime('%Y-%m-%dT%H:%M'),
        'registration_closed_message': 'ការចុះឈ្មោះត្រូវបានបិទជាបណ្ដោះអាសន្ន។'
    }
    resp = client.post('/students/enroll/api/registration-period/save/', post_data)
    assert resp.status_code == 200
    json_data = resp.json()
    assert json_data['status'] == 'success'
    assert json_data['is_allowed'] is True
    print("  [PASS] AJAX save registration period -> saved successfully")

    # 3. Test Mobile API
    print("\n--- 3. Testing Mobile API Endpoints ---")
    client.logout()

    # Mobile registration-period GET
    resp = client.get('/api/v1/students/registration-period/')
    assert resp.status_code == 200
    json_data = resp.json()
    assert json_data['status'] == 'success'
    assert json_data['is_allowed'] is True
    print(f"  [PASS] Mobile GET /api/v1/students/registration-period/ -> {json_data['status_code']}")

    # Mobile enroll GET
    resp = client.get('/api/v1/students/enroll/')
    assert resp.status_code == 200
    json_data = resp.json()
    assert 'registration_period' in json_data
    assert json_data['registration_period']['is_allowed'] is True
    print("  [PASS] Mobile GET /api/v1/students/enroll/ includes registration_period")

    # Now close registration and verify mobile POST is blocked with 403
    profile.refresh_from_db()
    profile.is_registration_open = False
    profile.save()

    mobile_student_payload = {
        'khmer_name': 'សុក សប្បាយ',
        'latin_name': 'Sok Sabay',
        'gender': 'M',
        'date_of_birth': '2008-05-12',
    }
    resp = client.post('/api/v1/students/enroll/', mobile_student_payload, content_type='application/json')
    assert resp.status_code == 403, f"Expected 403 Forbidden, got {resp.status_code}"
    json_data = resp.json()
    assert json_data['status'] == 'error'
    assert json_data['status_code'] == 'CLOSED_MANUAL'
    print(f"  [PASS] Mobile POST /api/v1/students/enroll/ when closed -> 403 Forbidden ({json_data['status_code']})")

    # Re-open registration and verify mobile POST succeeds or creates student
    profile.is_registration_open = True
    profile.registration_start_date = None
    profile.registration_end_date = None
    profile.save()

    # Get or create academic year and classroom for enrollment
    acad_year = AcademicYear.objects.filter(is_current=True).first() or AcademicYear.objects.first()
    cls = Classroom.objects.filter(academic_year=acad_year).first()
    if not cls:
        gl, _ = GradeLevel.objects.get_or_create(code='10', defaults={'name': 'ថ្នាក់ទី ១០'})
        cls = Classroom.objects.create(name='10A', grade_level=gl, academic_year=acad_year)

    mobile_student_payload.update({
        'academic_year_id': acad_year.id if acad_year else None,
        'classroom_id': cls.id if cls else None,
    })
    resp = client.post('/api/v1/students/enroll/', mobile_student_payload, content_type='application/json')
    assert resp.status_code == 201, f"Expected 201 Created, got {resp.status_code}: {resp.content}"
    json_data = resp.json()
    assert json_data['status'] == 'success'
    print(f"  [PASS] Mobile POST /api/v1/students/enroll/ when open -> 201 Created (Student ID: {json_data['student']['student_id']})")

    # Clean up test student
    from apps.students.models import Student
    Student.objects.filter(khmer_name='សុក សប្បាយ').delete()

    print("\n=======================================================")
    print(" ALL VERIFICATION TESTS PASSED SUCCESSFULLY! (100%)")
    print("=======================================================")

if __name__ == '__main__':
    run_tests()
