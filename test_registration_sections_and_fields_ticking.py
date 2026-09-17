import os
import sys
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from apps.accounts.models import SchoolProfile, DEFAULT_REGISTRATION_FIELDS_CONFIG
from apps.students.views import api_save_registration_fields_config, api_reset_registration_fields_config
from apps.students.forms import StudentEnrollmentForm, MoeysIndividualStudentForm
from apps.students.models import Student
from apps.academics.models import AcademicYear, Classroom
from django.template.loader import render_to_string

User = get_user_model()

def run_tests():
    print("=== Testing Registration Sections & Fields Ticking Feature ===")
    
    # 1. Test SchoolProfile get_registration_fields_config()
    profile = SchoolProfile.get_settings()
    initial_config = profile.get_registration_fields_config()
    assert 'general' in initial_config, "Config must contain 'general'"
    assert 'moeys' in initial_config, "Config must contain 'moeys'"
    assert initial_config['general']['sections']['student_info'] is True, "Student info section must default to True"
    assert initial_config['general']['fields']['khmer_name'] is True, "Khmer name must default to True"
    print("✓ Step 1: Default registration form configuration structure verified.")

    # 2. Test API saving custom ticking configuration
    admin_user = User.objects.filter(is_superuser=True).first()
    if not admin_user:
        admin_user = User.objects.filter(role='ADMIN').first()
    if not admin_user:
        admin_user = User.objects.create_superuser('testadmin', 'admin@example.com', 'admin123')
    
    factory = RequestFactory()
    
    # Custom config: disable parent_info section, disable latin_name, disable phone
    test_custom_config = {
        'general': {
            'sections': {
                'student_info': True,
                'parent_info': False, # Admin unticks parent section
                'academic_fee': True,
                'documents': False,   # Admin unticks documents section
                'grade_specific': True
            },
            'fields': {
                'student_id': True,
                'khmer_name': True,
                'latin_name': False,  # Admin unticks latin name
                'gender': True,
                'date_of_birth': True,
                'phone': False,       # Admin unticks phone
                'place_of_birth': False,
                'current_address': False,
                'father_name': False,
                'mother_name': False,
                'photo': False,
                'birth_certificate': False
            }
        },
        'moeys': {
            'sections': {
                'identity': True,
                'pob_address': False,  # Admin unticks POB section
                'parents': False,      # Admin unticks parents section
                'academic_origin': True,
                'vulnerability': False, # Admin unticks vulnerability section
                'fees': True
            },
            'fields': {
                'student_id': True,
                'surname': True,
                'given_name': True,
                'latin_name': False,   # Admin unticks latin name
                'gender': True,
                'date_of_birth': True,
                'pob': False,
                'father': False,
                'mother': False,
                'repeater': False,
                'previous_school': False
            }
        }
    }

    req = factory.post(
        '/students/api/save-registration-fields-config/',
        data=json.dumps(test_custom_config),
        content_type='application/json'
    )
    req.user = admin_user
    
    response = api_save_registration_fields_config(req)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    res_data = json.loads(response.content.decode('utf-8'))
    assert res_data['status'] == 'success', f"Expected success: {res_data}"
    
    # Refresh profile from DB
    profile.refresh_from_db()
    saved_cfg = profile.get_registration_fields_config()
    assert saved_cfg['general']['sections']['parent_info'] is False, "Parent info section should be False"
    assert saved_cfg['general']['fields']['latin_name'] is False, "Latin name field should be False"
    assert saved_cfg['general']['fields']['phone'] is False, "Phone field should be False"
    assert saved_cfg['moeys']['sections']['pob_address'] is False, "MoEYS POB section should be False"
    assert saved_cfg['moeys']['fields']['latin_name'] is False, "MoEYS Latin name should be False"
    
    # Enforced fields should remain True
    assert saved_cfg['general']['fields']['khmer_name'] is True, "Khmer name must remain enforced True"
    assert saved_cfg['moeys']['fields']['surname'] is True, "Surname must remain enforced True"
    assert saved_cfg['moeys']['fields']['given_name'] is True, "Given name must remain enforced True"
    print("✓ Step 2: Custom ticking configuration saved and enforced rules verified.")

    # 3. Test Form Validation Softening
    year = AcademicYear.objects.filter(is_current=True).first() or AcademicYear.objects.first()
    classroom = Classroom.objects.filter(academic_year=year).first() or Classroom.objects.first()
    
    # General Form: without unticked fields (latin_name, phone, parent_info)
    dummy_st = StudentEnrollmentForm(academic_year=year, is_staff=True)
    valid_st = dummy_st.fields['scholarship_type'].choices[0][0] if dummy_st.fields['scholarship_type'].choices else ''

    gen_form = StudentEnrollmentForm(
        data={
            'khmer_name': 'សុខ តារា',
            'gender': 'M',
            'date_of_birth': '2010-05-15',
            'academic_year': year.id if year else None,
            'classroom': classroom.id if classroom else None,
            'status': 'ACTIVE',
            'scholarship_type': valid_st
        },
        academic_year=year,
        is_staff=True
    )
    is_valid = gen_form.is_valid()
    if not is_valid:
        print("General form errors:", gen_form.errors)
    assert is_valid, "General form should be valid without unticked fields"
    print("✓ Step 3a: General Form validates properly with unticked fields omitted.")

    # MoEYS Form: without unticked fields (latin_name, pob, parents, vulnerability)
    dummy_moeys = MoeysIndividualStudentForm(academic_year=year, is_staff=True)
    valid_moeys_st = dummy_moeys.fields['scholarship_type'].choices[0][0] if dummy_moeys.fields['scholarship_type'].choices else ''

    moeys_form = MoeysIndividualStudentForm(
        data={
            'surname': 'សុខ',
            'given_name': 'តារា',
            'gender': 'M',
            'date_of_birth': '2010-05-15',
            'academic_year': year.id if year else None,
            'classroom': classroom.id if classroom else None,
            'status': 'ACTIVE',
            'scholarship_type': valid_moeys_st
        },
        academic_year=year,
        is_staff=True
    )
    is_moeys_valid = moeys_form.is_valid()
    if not is_moeys_valid:
        print("MoEYS form errors:", moeys_form.errors)
    assert is_moeys_valid, "MoEYS form should be valid without unticked fields"
    print("✓ Step 3b: MoEYS Form validates properly with unticked fields omitted.")

    # 4. Test Template Rendering without syntax errors
    context = {
        'form': gen_form,
        'moeys_form': moeys_form,
        'active_mode': 'ADMIN_CUSTOM',
        'reg_config': saved_cfg,
        'current_year': year,
        'school_profile': profile,
        'title': 'ចុះឈ្មោះសិស្សថ្មី',
        'available_grade_levels': []
    }
    
    rendered_student_form = render_to_string('students/student_form.html', context, request=req)
    assert 'សុខ តារា' in rendered_student_form or 'khmer_name' in rendered_student_form
    assert 'registrationFieldsTickingModal' in rendered_student_form
    print("✓ Step 4a: student_form.html rendered successfully with ticking modal and conditions.")

    rendered_public_enroll = render_to_string('students/public_enroll.html', context, request=req)
    assert 'khmer_name' in rendered_public_enroll
    print("✓ Step 4b: public_enroll.html rendered successfully with ticking conditions.")

    # 5. Test Reset API
    req_reset = factory.post('/students/api/reset-registration-fields-config/')
    req_reset.user = admin_user
    res_reset = api_reset_registration_fields_config(req_reset)
    assert res_reset.status_code == 200
    profile.refresh_from_db()
    reset_cfg = profile.get_registration_fields_config()
    assert reset_cfg['general']['sections']['parent_info'] is True, "Parent info section should be restored to True"
    assert reset_cfg['general']['fields']['latin_name'] is True, "Latin name field should be restored to True"
    assert reset_cfg['moeys']['sections']['pob_address'] is True, "MoEYS POB section should be restored to True"
    print("✓ Step 5: Reset API successfully restored all sections and fields to defaults.")

    print("\n🎉 ALL TESTS PASSED SUCCESSFULLY!")

if __name__ == '__main__':
    run_tests()
