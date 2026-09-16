import os
import sys
import django
import json

sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from django.test.utils import setup_test_environment
from apps.accounts.models import SchoolProfile, User
from apps.academics.models import AcademicYear, Classroom, GradeLevel
from apps.students.models import Student
from apps.students.forms import StudentEnrollmentForm, MoeysIndividualStudentForm

setup_test_environment()

def run_tests():
    print("=== STARTING GRADE-LEVEL REGISTRATION CONTROL TESTS ===")
    client = Client()
    profile = SchoolProfile.get_settings()
    profile.is_registration_open = True
    profile.registration_start_date = None
    profile.registration_end_date = None
    profile.save()

    admin_user = User.objects.filter(role=User.Role.ADMIN).first()
    if not admin_user:
        admin_user = User.objects.create_user(
            username='test_admin_grade_reg',
            password='password123',
            role=User.Role.ADMIN,
            is_staff=True
        )

    acad_year = AcademicYear.objects.filter(is_current=True).first() or AcademicYear.objects.first()
    if not acad_year:
        acad_year = AcademicYear.objects.create(name='2025-2026', is_current=True)

    # 1. Setup two GradeLevels: Grade 7 (Open) and Grade 8 (Closed)
    gl7, _ = GradeLevel.objects.get_or_create(grade_number=7, track='GENERAL', defaults={'name': 'ថ្នាក់ទី ៧', 'order': 1})
    gl7.is_registration_open = True
    gl7.registration_closed_message = ''
    gl7.save()

    gl8, _ = GradeLevel.objects.get_or_create(grade_number=8, track='GENERAL', defaults={'name': 'ថ្នាក់ទី ៨', 'order': 2})
    gl8.is_registration_open = False
    gl8.registration_closed_message = 'ការចុះឈ្មោះសម្រាប់ថ្នាក់ទី ៨ បានពេញអស់ហើយ!'
    gl8.save()

    cls7 = Classroom.objects.filter(grade_level=7, academic_year=acad_year).first()
    if not cls7:
        cls7 = Classroom.objects.create(name='7A', code='7A', grade_level=7, academic_year=acad_year)

    cls8 = Classroom.objects.filter(grade_level=8, academic_year=acad_year).first()
    if not cls8:
        cls8 = Classroom.objects.create(name='8A', code='8A', grade_level=8, academic_year=acad_year)

    # ----------------- 1. Test Model Logic -----------------
    print("\n--- 1. Testing GradeLevel Model Attributes & Helpers ---")
    assert gl7.is_admission_allowed is True
    is_allowed7, msg7 = gl7.get_admission_status()
    assert is_allowed7 is True and msg7 == ''
    print("  [PASS] Grade 7 is open -> is_admission_allowed=True")

    assert gl8.is_admission_allowed is False
    is_allowed8, msg8 = gl8.get_admission_status()
    assert is_allowed8 is False and 'បានពេញអស់ហើយ' in msg8
    print("  [PASS] Grade 8 is closed -> is_admission_allowed=False, correct notice returned")

    # ----------------- 2. Test Form Validation & Filtering -----------------
    print("\n--- 2. Testing StudentEnrollmentForm & MoeysIndividualStudentForm ---")
    # For non-staff public enrollment, classrooms of closed grades should be filtered out
    form_public = StudentEnrollmentForm(academic_year=acad_year, filter_closed_grades=True, is_staff=False)
    available_classes = list(form_public.fields['classroom'].queryset)
    assert cls7 in available_classes, "Class 7A should be available"
    assert cls8 not in available_classes, "Class 8A should be filtered out because Grade 8 is closed"
    print("  [PASS] StudentEnrollmentForm filters out classrooms belonging to closed Grade 8")

    # Form submission validation: if someone tries to submit class 8A, it should fail validation
    invalid_data = {
        'khmer_name': 'កែវ មករា',
        'gender': 'M',
        'date_of_birth': '2010-01-01',
        'classroom': cls8.id,
        'academic_year': acad_year.id,
        'scholarship_type': 'NONE',
        'status': 'ACTIVE',
    }
    form_submit = StudentEnrollmentForm(data=invalid_data, academic_year=acad_year, filter_closed_grades=True, is_staff=False)
    assert not form_submit.is_valid()
    assert 'classroom' in form_submit.errors
    print(f"  [PASS] Form validation rejected closed grade: {form_submit.errors['classroom']}")

    # ----------------- 3. Test Web Portal Views & AJAX APIs -----------------
    print("\n--- 3. Testing Admin QR Code Page & AJAX APIs ---")
    client.force_login(admin_user)

    # QR page loads with grade controls
    resp = client.get('/students/enroll/qr/')
    assert resp.status_code == 200
    assert 'all_grade_levels' in resp.context
    assert 'gradeRegControlCard' in resp.content.decode('utf-8')
    print("  [PASS] /students/enroll/qr/ loads successfully with Grade-Level Registration Card")

    # AJAX Toggle Single Grade API
    toggle_resp = client.post('/students/enroll/api/grade-registration/toggle/', {
        'grade_id': gl8.id,
        'is_registration_open': 'true',
        'registration_closed_message': 'បើកសាជាថ្មី'
    })
    assert toggle_resp.status_code == 200
    json_toggle = toggle_resp.json()
    assert json_toggle['success'] is True
    assert json_toggle['is_registration_open'] is True
    gl8.refresh_from_db()
    assert gl8.is_registration_open is True
    print("  [PASS] AJAX Toggle Grade: successfully opened Grade 8")

    # Re-close Grade 8 for next tests
    client.post('/students/enroll/api/grade-registration/toggle/', {
        'grade_id': gl8.id,
        'is_registration_open': 'false',
        'registration_closed_message': 'បានបិទការចុះឈ្មោះសម្រាប់ថ្នាក់ទី ៨'
    })
    gl8.refresh_from_db()
    assert gl8.is_registration_open is False

    # AJAX Bulk Toggle Grades API
    bulk_resp = client.post('/students/enroll/api/grade-registration/bulk/', {'action': 'open_all'})
    assert bulk_resp.status_code == 200
    assert GradeLevel.objects.filter(is_registration_open=False).count() == 0
    print("  [PASS] AJAX Bulk Toggle: open_all successfully opened all grade levels")

    # Close grade 8 again for testing public blocking
    gl8.is_registration_open = False
    gl8.registration_closed_message = 'ការចុះឈ្មោះសម្រាប់ថ្នាក់ទី ៨ បានបិទ!'
    gl8.save()

    client.logout()

    # Public user visiting closed grade direct URL ?grade=8
    resp_closed_grade = client.get('/students/enroll/online/?grade=8')
    assert resp_closed_grade.status_code == 200
    assert any('registration_closed.html' in t.name for t in resp_closed_grade.templates if t.name)
    assert 'ថ្នាក់ទី ៨' in resp_closed_grade.content.decode('utf-8')
    print("  [PASS] Public GET /students/enroll/online/?grade=8 renders registration_closed.html")

    # Public user visiting open grade direct URL ?grade=7
    resp_open_grade = client.get('/students/enroll/online/?grade=7')
    assert resp_open_grade.status_code == 200
    assert not any('registration_closed.html' in t.name for t in resp_open_grade.templates if t.name)
    print("  [PASS] Public GET /students/enroll/online/?grade=7 renders open admission form")

    # ----------------- 4. Test Mobile API Endpoints -----------------
    print("\n--- 4. Testing Mobile API Endpoints ---")
    # GET /api/v1/students/registration-period/ includes grade_levels
    resp_mobile_period = client.get('/api/v1/students/registration-period/')
    assert resp_mobile_period.status_code == 200
    period_json = resp_mobile_period.json()
    assert 'grade_levels' in period_json
    found_gl8 = next((g for g in period_json['grade_levels'] if g['id'] == gl8.id), None)
    assert found_gl8 is not None and found_gl8['is_registration_open'] is False
    print("  [PASS] Mobile GET /registration-period/ returns grade_levels with registration statuses")

    # GET /api/v1/students/enroll/ includes is_registration_open in classrooms and grade_form_configs
    resp_mobile_enroll = client.get('/api/v1/students/enroll/')
    assert resp_mobile_enroll.status_code == 200
    enroll_json = resp_mobile_enroll.json()
    cls8_data = next((c for c in enroll_json['classrooms'] if c['id'] == cls8.id), None)
    assert cls8_data is not None and cls8_data['is_registration_open'] is False
    cls7_data = next((c for c in enroll_json['classrooms'] if c['id'] == cls7.id), None)
    assert cls7_data is not None and cls7_data['is_registration_open'] is True
    print("  [PASS] Mobile GET /enroll/ classrooms data correctly tags is_registration_open")

    # POST /api/v1/students/enroll/ with closed grade level 8 -> 403 GRADE_CLOSED
    post_closed_payload = {
        'khmer_name': 'ចាន់ តារា',
        'gender': 'M',
        'date_of_birth': '2010-05-10',
        'classroom_id': cls8.id,
        'academic_year_id': acad_year.id,
    }
    resp_post_closed = client.post('/api/v1/students/enroll/', post_closed_payload, content_type='application/json')
    assert resp_post_closed.status_code == 403, f"Expected 403, got {resp_post_closed.status_code}"
    err_json = resp_post_closed.json()
    assert err_json['status_code'] == 'GRADE_CLOSED'
    print(f"  [PASS] Mobile POST /enroll/ for closed grade returns 403 ({err_json['status_code']}: {err_json['message']})")

    # POST /api/v1/students/enroll/ with open grade level 7 -> 201 Created
    post_open_payload = {
        'khmer_name': 'សុខ វិសាល',
        'gender': 'M',
        'date_of_birth': '2011-03-15',
        'classroom_id': cls7.id,
        'academic_year_id': acad_year.id,
    }
    resp_post_open = client.post('/api/v1/students/enroll/', post_open_payload, content_type='application/json')
    assert resp_post_open.status_code == 201, f"Expected 201, got {resp_post_open.status_code}: {resp_post_open.content}"
    success_json = resp_post_open.json()
    assert success_json['status'] == 'success'
    print(f"  [PASS] Mobile POST /enroll/ for open grade succeeded with 201 Created (ID: {success_json['student']['student_id']})")

    # Clean up test students
    Student.objects.filter(khmer_name__in=['សុខ វិសាល', 'ចាន់ តារា']).delete()

    # Re-open Grade 8 to leave DB clean
    gl8.is_registration_open = True
    gl8.save()

    print("\n=======================================================")
    print(" ALL GRADE-LEVEL REGISTRATION CONTROL TESTS PASSED (100%)!")
    print("=======================================================")

if __name__ == '__main__':
    run_tests()
