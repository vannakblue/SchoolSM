import os
import sys
import django

sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

import json
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
from apps.accounts.models import SchoolProfile, User
from apps.academics.models import AcademicYear, GradeLevel, Classroom
from apps.students.models import GradeVerificationFormConfig
from apps.students.views import public_student_enroll, api_get_grade_options
from apps.mobile_api.views import MobileStudentEnrollAPIView

def run_tests():
    print("=== STARTING ADMIN ENFORCED REGISTRATION MODE VERIFICATION ===")
    factory = RequestFactory()

    # 1. Base Setup
    year = AcademicYear.objects.filter(is_current=True).first()
    if not year:
        year = AcademicYear.objects.create(name="2025-2026", is_current=True, start_date="2025-10-01", end_date="2026-07-31")

    profile = SchoolProfile.get_settings()
    profile.is_registration_open = True
    profile.registration_start_date = None
    profile.registration_end_date = None
    profile.registration_mode = SchoolProfile.RegistrationMode.ADMIN_CUSTOM
    profile.save()

    gl7, _ = GradeLevel.objects.get_or_create(grade_number=7, track='GENERAL', defaults={'name': 'ថ្នាក់ទី ៧', 'order': 7})
    gl7.is_registration_open = True
    gl7.save()
    c7, _ = Classroom.objects.get_or_create(code="07A-TEST", defaults={'name': 'ថ្នាក់ទី ៧A', 'grade_level': 7, 'academic_year': year, 'track': 'GENERAL'})
    c7.academic_year = year
    c7.save()

    gl10, _ = GradeLevel.objects.get_or_create(grade_number=10, track='GENERAL', defaults={'name': 'ថ្នាក់ទី ១០', 'order': 10})
    gl10.is_registration_open = True
    gl10.save()
    c10, _ = Classroom.objects.get_or_create(code="10A-ENF", defaults={'name': 'ថ្នាក់ទី ១០A', 'grade_level': 10, 'academic_year': year, 'track': 'GENERAL'})
    c10.academic_year = year
    c10.save()

    # Configure Grade 10 to strictly use MOEYS_INDIVIDUAL via Admin config
    cfg10, _ = GradeVerificationFormConfig.objects.get_or_create(
        grade_level=gl10,
        defaults={'form_template': GradeVerificationFormConfig.FormTemplate.MOEYS_INDIVIDUAL, 'is_active': True}
    )
    cfg10.form_template = GradeVerificationFormConfig.FormTemplate.MOEYS_INDIVIDUAL
    cfg10.save()

    # 2. Test Public Portal GET: Student cannot choose mode via ?mode=
    req = factory.get(f'/students/enroll/online/?classroom={c7.id}&mode=MOEYS_INDIVIDUAL')
    req.user = AnonymousUser()
    resp = public_student_enroll(req)
    assert resp.status_code == 200
    html_content = resp.content.decode('utf-8')

    # Verify that the choice selector card ("សូមជ្រើសរើសវិធីសាស្ត្រចុះឈ្មោះ") and indicator banner are NOT present
    assert "សូមជ្រើសរើសវិធីសាស្ត្រចុះឈ្មោះ" not in html_content, "Applicant choice card should NOT be in HTML"
    assert "វិធីសាស្ត្រចុះឈ្មោះកំណត់ដោយរដ្ឋបាលសាលា" not in html_content, "Admin Enforced banner has been removed as requested"
    assert 'value="ADMIN_CUSTOM"' in html_content
    print("  ✓ Public portal prevents student selection cards and removed admin banner.")

    # 3. Test Grade 10 automatically enforces Admin's MOEYS_INDIVIDUAL template
    req10 = factory.get(f'/students/enroll/online/?classroom={c10.id}&mode=ADMIN_CUSTOM')
    req10.user = AnonymousUser()
    resp10 = public_student_enroll(req10)
    assert resp10.status_code == 200
    assert 'value="MOEYS_INDIVIDUAL"' in resp10.content.decode('utf-8')
    print("  ✓ Public portal strictly enforced Grade 10 Admin template (MOEYS_INDIVIDUAL), ignoring ?mode=ADMIN_CUSTOM.")

    # 4. Test api_get_grade_options returns assigned_template
    req_api = factory.get(f'/students/api/grade-options/?classroom_id={c10.id}')
    resp_api = api_get_grade_options(req_api)
    data_api = json.loads(resp_api.content)
    assert data_api['assigned_template'] == 'MOEYS_INDIVIDUAL', f"Expected MOEYS_INDIVIDUAL, got {data_api.get('assigned_template')}"
    print("  ✓ api_get_grade_options returned assigned_template: MOEYS_INDIVIDUAL.")

    # 5. Test Mobile Enrollment Metadata API View
    req_mob = factory.get('/api/v1/students/enroll/')
    req_mob.user = AnonymousUser()
    mob_view = MobileStudentEnrollAPIView.as_view()
    resp_mob = mob_view(req_mob)
    assert resp_mob.status_code == 200
    mob_data = resp_mob.data
    assert mob_data['can_student_choose_mode'] is False, "can_student_choose_mode must be False"
    assert 'admin_enforced_mode' in mob_data, "admin_enforced_mode must be in mobile metadata"
    print(f"  ✓ Mobile API returned can_student_choose_mode=False and admin_enforced_mode={mob_data['admin_enforced_mode']}.")

    print("=== ALL ADMIN ENFORCED REGISTRATION TESTS PASSED! ===")

if __name__ == '__main__':
    run_tests()
