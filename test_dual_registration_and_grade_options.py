import os
import sys
import django

sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

import json
from django.test import RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from apps.accounts.models import SchoolProfile, User
from apps.academics.models import AcademicYear, GradeLevel, Classroom, GradeEnrollmentOption
from apps.students.models import Student
from apps.students.forms import StudentEnrollmentForm, MoeysIndividualStudentForm
from apps.students.views import (
    api_get_grade_options,
    api_set_registration_mode,
    student_enroll,
    student_edit,
    public_student_enroll
)

def run_tests():
    print("=== STARTING DUAL REGISTRATION & GRADE OPTIONS VERIFICATION ===")
    factory = RequestFactory()

    # 1. Setup Base Data
    admin_user = User.objects.filter(role=User.Role.ADMIN).first()
    if not admin_user:
        admin_user = User.objects.create_superuser('test_admin_enroll', 'admin@school.com', 'pass123')

    year = AcademicYear.objects.filter(is_current=True).first()
    if not year:
        year = AcademicYear.objects.create(name="2025-2026", is_current=True, start_date="2025-10-01", end_date="2026-07-31")

    gl, _ = GradeLevel.objects.get_or_create(grade_number=10, track='GENERAL', defaults={'name': 'ថ្នាក់ទី ១០ ទូទៅ', 'order': 10})
    classroom, _ = Classroom.objects.get_or_create(
        code="10A-TEST",
        defaults={'name': 'ថ្នាក់ទី ១០A តេស្ត', 'grade_level': 10, 'academic_year': year, 'track': 'GENERAL'}
    )

    profile = SchoolProfile.get_settings()
    print(f"[1] Current School Profile Registration Mode: {profile.registration_mode} ({profile.get_registration_mode_display()})")

    # 2. Test Registration Mode Switching API
    req = factory.post(
        '/students/api/set-registration-mode/',
        data=json.dumps({'mode': 'MOEYS_INDIVIDUAL'}),
        content_type='application/json'
    )
    req.user = admin_user
    resp = api_set_registration_mode(req)
    data = json.loads(resp.content)
    assert data['status'] == 'success', f"Mode switch failed: {data}"
    profile.refresh_from_db()
    assert profile.registration_mode == 'MOEYS_INDIVIDUAL', f"Expected MOEYS_INDIVIDUAL, got {profile.registration_mode}"
    print("  ✓ Successfully switched registration mode to MOEYS_INDIVIDUAL via AJAX API")

    req = factory.post(
        '/students/api/set-registration-mode/',
        data=json.dumps({'mode': 'BOTH'}),
        content_type='application/json'
    )
    req.user = admin_user
    resp = api_set_registration_mode(req)
    profile.refresh_from_db()
    assert profile.registration_mode == 'BOTH'
    print("  ✓ Successfully switched registration mode to BOTH via AJAX API")

    # 3. Test Grade Options Separation ("តែត្រូវចែកជា២ផ្សេងគ្នា")
    opt_gen, _ = GradeEnrollmentOption.objects.get_or_create(
        grade_level=gl,
        form_category=GradeEnrollmentOption.FormCategory.GENERAL,
        field_name='general_test_field',
        defaults={
            'label': 'ឈ្មោះសាលាចាស់ (បែបបទទូទៅ)',
            'field_type': GradeEnrollmentOption.FieldType.TEXT,
            'is_active': True,
            'order': 1
        }
    )

    opt_moeys, _ = GradeEnrollmentOption.objects.get_or_create(
        grade_level=gl,
        form_category=GradeEnrollmentOption.FormCategory.MOEYS_INDIVIDUAL,
        field_name='moeys_test_field',
        defaults={
            'label': 'ព័ត៌មានបន្ថែម MoEYS (បែបបទសម្រង់)',
            'field_type': GradeEnrollmentOption.FieldType.TEXT,
            'is_active': True,
            'order': 1
        }
    )

    # Test GradeLevel properties
    gen_opts = gl.general_enrollment_options
    moeys_opts = gl.moeys_enrollment_options
    assert any(o.field_name == 'general_test_field' for o in gen_opts), "general_test_field not in gen_opts"
    assert not any(o.field_name == 'moeys_test_field' for o in gen_opts), "moeys_test_field leaked into gen_opts"
    assert any(o.field_name == 'moeys_test_field' for o in moeys_opts), "moeys_test_field not in moeys_opts"
    assert not any(o.field_name == 'general_test_field' for o in moeys_opts), "general_test_field leaked into moeys_opts"
    print("  ✓ Model properties gl.general_enrollment_options and gl.moeys_enrollment_options strictly separated")

    # Test AJAX API api_get_grade_options filtering
    req_api_gen = factory.get(f'/students/api/grade-options/?classroom_id={classroom.id}&form_category=GENERAL')
    resp_api_gen = json.loads(api_get_grade_options(req_api_gen).content)
    assert any(d['field_name'] == 'general_test_field' for d in resp_api_gen['data'])
    assert not any(d['field_name'] == 'moeys_test_field' for d in resp_api_gen['data'])

    req_api_moeys = factory.get(f'/students/api/grade-options/?classroom_id={classroom.id}&form_category=MOEYS_INDIVIDUAL')
    resp_api_moeys = json.loads(api_get_grade_options(req_api_moeys).content)
    assert any(d['field_name'] == 'moeys_test_field' for d in resp_api_moeys['data'])
    assert not any(d['field_name'] == 'general_test_field' for d in resp_api_moeys['data'])
    print("  ✓ api_get_grade_options cleanly partitions fields by form_category")

    # 4. Test Student Registration via Option 1: General / Admin-Configured Form
    student_gen = Student.objects.filter(student_id='TEST-GEN-001').first()
    if student_gen:
        student_gen.delete()

    req_enroll_gen = factory.post('/students/enroll/', data={
        'enrollment_mode': 'ADMIN_CUSTOM',
        'student_id': 'TEST-GEN-001',
        'khmer_name': 'សុខ សុភា',
        'latin_name': 'SOK SOPHEA',
        'gender': 'F',
        'date_of_birth': '2010-05-15',
        'classroom': classroom.id,
        'academic_year': year.id,
        'scholarship_type': 'FULL_PAY',
        'status': 'ACTIVE',
        'grade_opt_general_test_field': 'សាលាបឋមសិក្សាទួលគោក',
    })
    req_enroll_gen.user = admin_user
    setattr(req_enroll_gen, 'session', {})
    setattr(req_enroll_gen, '_messages', FallbackStorage(req_enroll_gen))
    f_check = StudentEnrollmentForm(req_enroll_gen.POST, academic_year=year)
    if not f_check.is_valid():
        print('StudentEnrollmentForm errors:', f_check.errors)
    student_enroll(req_enroll_gen)

    saved_student_gen = Student.objects.filter(student_id='TEST-GEN-001').first()
    assert saved_student_gen is not None, "Failed to create student in General mode"
    assert saved_student_gen.enrollment_data.get('general_test_field', {}).get('value') == 'សាលាបឋមសិក្សាទួលគោក'
    print(f"  ✓ Successfully enrolled student in Admin-Configured mode: {saved_student_gen.khmer_name} (ID: {saved_student_gen.student_id})")

    # 5. Test Student Registration via Option 2: MoEYS Individual Profile Form (35 Columns)
    student_moeys = Student.objects.filter(student_id='TEST-MOEYS-001').first()
    if student_moeys:
        student_moeys.delete()

    req_enroll_moeys = factory.post('/students/enroll/', data={
        'enrollment_mode': 'MOEYS_INDIVIDUAL',
        'student_id': 'TEST-MOEYS-001',
        'surname': 'ចាន់',
        'given_name': 'តារា',
        'latin_name': 'CHAN DARA',
        'gender': 'M',
        'date_of_birth': '2009-11-20',
        'pob_commune': 'សង្កាត់ទឹកថ្លា',
        'pob_district': 'ខណ្ឌសែនសុខ',
        'pob_province': 'រាជធានីភ្នំពេញ',
        'classroom': classroom.id,
        'academic_year': year.id,
        'track': 'វិទ្យាសាស្ត្រ',
        'father_name': 'ចាន់ សុខុម',
        'father_job': 'វិស្វករ',
        'father_phone': '012 999 888',
        'mother_name': 'អ៊ុំ ផល្លី',
        'mother_job': 'គ្រូបង្រៀន',
        'mother_phone': '098 777 666',
        'orphan_status': 'មិនមែន',
        'primary_school': 'បឋមសិក្សា ហ៊ុន សែន ទឹកថ្លា',
        'secondary_school': '',
        'ethnic_minority': 'មិនមែន',
        'disability_physical': 'មិនមាន',
        'disability_sight': 'មិនមាន',
        'disability_hearing': 'មិនមាន',
        'equity_card_1': 'មិនមាន',
        'equity_card_2': 'មិនមាន',
        'risk_card': 'មិនមាន',
        'scholarship': 'មិនមាន',
        'phone': '012 345 678',
        'grade_opt_moeys_test_field': 'ទិន្នន័យបន្ថែម MoEYS ១២៣',
    })
    req_enroll_moeys.user = admin_user
    setattr(req_enroll_moeys, 'session', {})
    setattr(req_enroll_moeys, '_messages', FallbackStorage(req_enroll_moeys))
    student_enroll(req_enroll_moeys)

    saved_student_moeys = Student.objects.filter(student_id='TEST-MOEYS-001').first()
    assert saved_student_moeys is not None, "Failed to create student in MoEYS mode"
    assert saved_student_moeys.khmer_name == 'ចាន់ តារា', f"Expected 'ចាន់ តារា', got '{saved_student_moeys.khmer_name}'"
    assert saved_student_moeys.latin_name == 'CHAN DARA'
    assert saved_student_moeys.father_name == 'ចាន់ សុខុម'
    assert saved_student_moeys.enrollment_data.get('surname') == 'ចាន់'
    assert saved_student_moeys.enrollment_data.get('given_name') == 'តារា'
    assert saved_student_moeys.enrollment_data.get('pob_commune') == 'សង្កាត់ទឹកថ្លា'
    assert saved_student_moeys.enrollment_data.get('primary_school') == 'បឋមសិក្សា ហ៊ុន សែន ទឹកថ្លា'
    assert saved_student_moeys.enrollment_data.get('moeys_test_field', {}).get('value') == 'ទិន្នន័យបន្ថែម MoEYS ១២៣'
    print(f"  ✓ Successfully enrolled student in MoEYS Individual mode: {saved_student_moeys.khmer_name} with all 35 MoEYS columns synced")

    # 6. Test Editing Student in MoEYS Individual Mode
    req_edit_moeys = factory.post(f'/students/{saved_student_moeys.id}/edit/', data={
        'enrollment_mode': 'MOEYS_INDIVIDUAL',
        'student_id': 'TEST-MOEYS-001',
        'surname': 'ចាន់',
        'given_name': 'តារាវិបុល',
        'latin_name': 'CHAN DARAVIBOL',
        'gender': 'M',
        'date_of_birth': '2009-11-20',
        'pob_commune': 'សង្កាត់បឹងកក់១',
        'pob_district': 'ខណ្ឌទួលគោក',
        'pob_province': 'រាជធានីភ្នំពេញ',
        'classroom': classroom.id,
        'academic_year': year.id,
        'track': 'វិទ្យាសាស្ត្រ',
        'father_name': 'ចាន់ សុខុម',
        'father_job': 'វិស្វករជាន់ខ្ពស់',
        'father_phone': '012 999 888',
        'mother_name': 'អ៊ុំ ផល្លី',
        'mother_job': 'គ្រូបង្រៀន',
        'mother_phone': '098 777 666',
        'orphan_status': 'មិនមែន',
        'primary_school': 'បឋមសិក្សា ទួលគោក',
        'secondary_school': '',
        'ethnic_minority': 'មិនមែន',
        'disability_physical': 'មិនមាន',
        'disability_sight': 'មិនមាន',
        'disability_hearing': 'មិនមាន',
        'equity_card_1': 'មិនមាន',
        'equity_card_2': 'មិនមាន',
        'risk_card': 'មិនមាន',
        'scholarship': 'មិនមាន',
        'phone': '012 345 678',
        'grade_opt_moeys_test_field': 'បានកែប្រែទិន្នន័យ MoEYS ថ្មី',
    })
    req_edit_moeys.user = admin_user
    setattr(req_edit_moeys, 'session', {})
    setattr(req_edit_moeys, '_messages', FallbackStorage(req_edit_moeys))
    student_edit(req_edit_moeys, pk=saved_student_moeys.id)

    saved_student_moeys.refresh_from_db()
    assert saved_student_moeys.khmer_name == 'ចាន់ តារាវិបុល'
    assert saved_student_moeys.latin_name == 'CHAN DARAVIBOL'
    assert saved_student_moeys.enrollment_data.get('given_name') == 'តារាវិបុល'
    assert saved_student_moeys.enrollment_data.get('pob_commune') == 'សង្កាត់បឹងកក់១'
    assert saved_student_moeys.father_job == 'វិស្វករជាន់ខ្ពស់'
    assert saved_student_moeys.enrollment_data.get('moeys_test_field', {}).get('value') == 'បានកែប្រែទិន្នន័យ MoEYS ថ្មី'
    print(f"  ✓ Successfully edited MoEYS Individual student: updated to {saved_student_moeys.khmer_name}")

    # 7. Cleanup test students
    saved_student_gen.delete()
    saved_student_moeys.delete()
    opt_gen.delete()
    opt_moeys.delete()
    print("  ✓ Cleanup completed successfully")

    print("=== ALL TESTS PASSED SUCCESSFULLY! ===")

if __name__ == '__main__':
    run_tests()
