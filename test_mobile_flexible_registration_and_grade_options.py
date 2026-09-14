import os
import sys
import django
import json

if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import RequestFactory
from rest_framework.test import force_authenticate
from apps.accounts.models import SchoolProfile, User
from apps.academics.models import AcademicYear, Classroom, GradeLevel, GradeEnrollmentOption
from apps.students.models import Student, GradeVerificationFormConfig
from apps.mobile_api.views import (
    MobileStudentEnrollAPIView,
    MobileGradeOptionsAPIView,
    MobileStudentRegistrationPeriodAPIView
)

def run_tests():
    print("=== Testing Mobile Flexible Registration & Grade-Level Options ===")
    factory = RequestFactory()

    # 1. Setup Base Data
    admin_user = User.objects.filter(role=User.Role.ADMIN).first()
    if not admin_user:
        admin_user = User.objects.create_superuser('test_mobile_admin', 'admin_mob@school.com', 'pass123')

    year, _ = AcademicYear.objects.get_or_create(
        name="2026-2027",
        defaults={'start_date': '2026-10-01', 'end_date': '2027-08-31', 'is_current': True}
    )

    # Clean up test students from previous runs
    Student.objects.filter(khmer_name__in=['ស៊ុន វាសនា', 'លី សុភ័ក្ត្រ']).delete()

    grade10 = GradeLevel.objects.filter(grade_number=10).first()
    if not grade10:
        grade10 = GradeLevel.objects.create(grade_number=10, name='ថ្នាក់ទី ១០', order=10)

    grade11 = GradeLevel.objects.filter(grade_number=11).first()
    if not grade11:
        grade11 = GradeLevel.objects.create(grade_number=11, name='ថ្នាក់ទី ១១', order=11)

    classroom10, _ = Classroom.objects.get_or_create(
        code="10A-FLEX",
        defaults={'name': '10A-FlexTest', 'grade_level': 10, 'academic_year': year, 'capacity': 40}
    )

    # 2. Test Admin Updating Registration Mode via Mobile API
    print("\n--- Test 1: MobileStudentRegistrationPeriodAPIView (Admin Mode Switch) ---")
    reg_period_view = MobileStudentRegistrationPeriodAPIView.as_view()

    # Switch to MOEYS_INDIVIDUAL
    req_sw1 = factory.post(
        '/api/v1/students/registration-period/',
        data=json.dumps({'registration_mode': 'MOEYS_INDIVIDUAL'}),
        content_type='application/json'
    )
    req_sw1.user = admin_user
    force_authenticate(req_sw1, user=admin_user)
    res_sw1 = reg_period_view(req_sw1)
    assert res_sw1.status_code == 200, f"Expected 200, got {res_sw1.status_code}"
    assert res_sw1.data['registration_mode'] == 'MOEYS_INDIVIDUAL'
    profile = SchoolProfile.get_settings()
    assert profile.registration_mode == 'MOEYS_INDIVIDUAL'
    print("✔ Successfully switched registration_mode to MOEYS_INDIVIDUAL via Mobile API.")

    # Switch back to BOTH
    req_sw2 = factory.post(
        '/api/v1/students/registration-period/',
        data=json.dumps({'registration_mode': 'BOTH'}),
        content_type='application/json'
    )
    req_sw2.user = admin_user
    force_authenticate(req_sw2, user=admin_user)
    res_sw2 = reg_period_view(req_sw2)
    assert res_sw2.status_code == 200
    assert res_sw2.data['registration_mode'] == 'BOTH'
    print("✔ Successfully switched registration_mode to BOTH via Mobile API.")

    # 3. Test Admin Configuring Grade-Level Form Templates via Mobile API
    print("\n--- Test 2: MobileGradeOptionsAPIView (Admin Form Template Configuration) ---")
    grade_opts_view = MobileGradeOptionsAPIView.as_view()

    # Configure Grade 10 to require MOEYS_INDIVIDUAL with custom instructions
    req_tpl = factory.post(
        '/api/v1/students/grade-options/',
        data=json.dumps({
            'action': 'update_template',
            'grade_number': 10,
            'form_template': 'MOEYS_INDIVIDUAL',
            'custom_instructions': 'សេចក្តីណែនាំពីរដ្ឋបាល៖ សូមភ្ជាប់សំបុត្រកំណើតច្បាប់ដើម'
        }),
        content_type='application/json'
    )
    req_tpl.user = admin_user
    force_authenticate(req_tpl, user=admin_user)
    res_tpl = grade_opts_view(req_tpl)
    assert res_tpl.status_code == 200, f"Expected 200, got {res_tpl.status_code}: {res_tpl.data}"
    assert res_tpl.data['form_template'] == 'MOEYS_INDIVIDUAL'
    assert 'សំបុត្រកំណើត' in res_tpl.data['custom_instructions']

    cfg10 = GradeVerificationFormConfig.objects.filter(grade_level=grade10).first()
    assert cfg10 is not None
    assert cfg10.form_template == 'MOEYS_INDIVIDUAL'
    print("✔ Admin successfully configured Grade 10 to MOEYS_INDIVIDUAL with instructions via Mobile API.")

    # 4. Test Admin Adding Dynamic Grade Options via Mobile API
    print("\n--- Test 3: MobileGradeOptionsAPIView (Admin Add Custom Option) ---")
    req_add_opt = factory.post(
        '/api/v1/students/grade-options/',
        data=json.dumps({
            'action': 'save_option',
            'grade_number': 10,
            'label': 'ភាសាបរទេសទី២',
            'field_name': 'foreign_lang_2',
            'field_type': 'MULTISELECT',
            'form_category': 'GENERAL',
            'choices': ['បារាំង', 'ចិន', 'ជប៉ុន', 'ថៃ'],
            'placeholder': 'ជ្រើសរើសភាសាដែលចេះ',
            'is_required': False,
            'col_width': 6
        }),
        content_type='application/json'
    )
    req_add_opt.user = admin_user
    force_authenticate(req_add_opt, user=admin_user)
    res_add_opt = grade_opts_view(req_add_opt)
    assert res_add_opt.status_code == 200, f"Expected 200, got {res_add_opt.status_code}: {res_add_opt.data}"
    created_opt = res_add_opt.data['option']
    assert created_opt['field_name'] == 'foreign_lang_2'
    assert created_opt['field_type'] == 'MULTISELECT'
    assert 'បារាំង' in created_opt['choices']
    print("✔ Admin successfully created custom MULTISELECT GradeEnrollmentOption via Mobile API.")

    # Also add a MOEYS specific option
    opt_moeys_doc, _ = GradeEnrollmentOption.objects.get_or_create(
        grade_level=grade10,
        field_name='birth_cert_book_num',
        form_category=GradeEnrollmentOption.FormCategory.MOEYS_INDIVIDUAL,
        defaults={
            'label': 'លេខកត់ត្រាសំបុត្រកំណើត',
            'field_type': GradeEnrollmentOption.FieldType.TEXT,
            'is_active': True,
        }
    )

    # 5. Test GET MobileGradeOptionsAPIView with flexible lookup
    print("\n--- Test 4: MobileGradeOptionsAPIView Flexible Querying ---")

    # A) Query by classroom_id
    req_get_cls = factory.get(f'/api/v1/students/grade-options/?classroom_id={classroom10.id}&form_category=GENERAL')
    res_get_cls = grade_opts_view(req_get_cls)
    assert res_get_cls.status_code == 200
    assert res_get_cls.data['assigned_template'] == 'MOEYS_INDIVIDUAL'
    assert 'សំបុត្រកំណើត' in res_get_cls.data['custom_instructions']
    opt_names = [o['field_name'] for o in res_get_cls.data['options']]
    assert 'foreign_lang_2' in opt_names
    print("✔ GET grade-options by classroom_id successfully resolved template & custom instructions.")

    # B) Query directly by grade_level=10 (WITHOUT classroom_id)
    req_get_gl = factory.get('/api/v1/students/grade-options/?grade_level=10&form_category=GENERAL')
    res_get_gl = grade_opts_view(req_get_gl)
    assert res_get_gl.status_code == 200
    assert res_get_gl.data['grade_level'] == 10
    assert res_get_gl.data['assigned_template'] == 'MOEYS_INDIVIDUAL'
    assert any(o['field_name'] == 'foreign_lang_2' for o in res_get_gl.data['options'])
    print("✔ GET grade-options by grade_level=10 (without classroom_id) worked flexibly and accurately.")

    # C) Query with form_category=ALL / BOTH
    req_get_all = factory.get(f'/api/v1/students/grade-options/?classroom_id={classroom10.id}&form_category=ALL')
    res_get_all = grade_opts_view(req_get_all)
    assert res_get_all.status_code == 200
    assert 'general_options' in res_get_all.data
    assert 'moeys_options' in res_get_all.data
    assert any(o['field_name'] == 'foreign_lang_2' for o in res_get_all.data['general_options'])
    assert any(o['field_name'] == 'birth_cert_book_num' for o in res_get_all.data['moeys_options'])
    print("✔ GET grade-options with form_category=ALL returned both separated partitions.")

    # 6. Test GET MobileStudentEnrollAPIView (Admission Form Metadata)
    print("\n--- Test 5: MobileStudentEnrollAPIView Metadata Enhancement ---")
    enroll_view = MobileStudentEnrollAPIView.as_view()
    req_enroll_meta = factory.get(f'/api/v1/students/enroll/?classroom_id={classroom10.id}')
    res_enroll_meta = enroll_view(req_enroll_meta)
    assert res_enroll_meta.status_code == 200
    d = res_enroll_meta.data
    assert d['status'] == 'success'
    assert 'grade_form_configs' in d
    assert len(d['grade_form_configs']) > 0
    assert 'grade_options_by_grade' in d
    assert str(10) in d['grade_options_by_grade']
    assert d['active_grade_template'] == 'MOEYS_INDIVIDUAL'
    assert 'សំបុត្រកំណើត' in d['active_grade_instructions']
    assert any(o['field_name'] == 'foreign_lang_2' for o in d['active_grade_options'])
    print("✔ GET /api/v1/students/enroll/ returns rich grade_form_configs, grade_options_by_grade, and active template.")

    # 7. Test POST MobileStudentEnrollAPIView (Flexible Enrollment Submission)
    print("\n--- Test 6: MobileStudentEnrollAPIView Flexible Submission ---")

    # A) Enroll with CUSTOM_COMBINED mode (Preserving both general grade options & MoEYS census columns)
    post_combined_data = {
        'enrollment_mode': 'CUSTOM_COMBINED',
        'surname': 'ស៊ុន',
        'given_name': 'វាសនា',
        'latin_name': 'SUN VEASNA',
        'gender': 'M',
        'date_of_birth': '2010-08-14',
        'pob_commune': 'សង្កាត់ទួលទំពូង១',
        'pob_district': 'ខណ្ឌចំការមន',
        'pob_province': 'រាជធានីភ្នំពេញ',
        'classroom_id': classroom10.id,
        'academic_year_id': year.id,
        'orphan_status': 'កំព្រាម្តាយ',
        'track': 'វិទ្យាសាស្ត្រ',
        'grade_options': {
            'foreign_lang_2': 'បារាំង, ចិន',
            'birth_cert_book_num': 'BOOK-2026-999'
        }
    }
    req_post_comb = factory.post(
        '/api/v1/students/enroll/',
        data=json.dumps(post_combined_data),
        content_type='application/json'
    )
    res_post_comb = enroll_view(req_post_comb)
    assert res_post_comb.status_code in [200, 201], f"Expected 200/201, got {res_post_comb.status_code}: {res_post_comb.data}"
    st_id = res_post_comb.data['student']['id']
    st = Student.objects.get(id=st_id)
    assert st.khmer_name == 'ស៊ុន វាសនា'
    assert st.enrollment_data.get('orphan_status') == 'កំព្រាម្តាយ'
    assert st.enrollment_data.get('foreign_lang_2') == 'បារាំង, ចិន'
    assert st.enrollment_data.get('birth_cert_book_num') == 'BOOK-2026-999'
    print("✔ POST enrollment in CUSTOM_COMBINED mode succeeded with both census data & custom options preserved.")

    # B) Enroll with omitted enrollment_mode (Auto-inference from GradeVerificationFormConfig)
    post_inferred_data = {
        # enrollment_mode omitted intentionally!
        'khmer_name': 'លី សុភ័ក្ត្រ',
        'latin_name': 'LY SOPHEAK',
        'gender': 'F',
        'date_of_birth': '2010-12-05',
        'classroom_id': classroom10.id,
        'academic_year_id': year.id,
        'birth_cert_book_num': 'BOOK-AUTO-123',  # direct key
    }
    req_post_inf = factory.post(
        '/api/v1/students/enroll/',
        data=json.dumps(post_inferred_data),
        content_type='application/json'
    )
    res_post_inf = enroll_view(req_post_inf)
    assert res_post_inf.status_code in [200, 201], f"Expected 200/201, got {res_post_inf.status_code}: {res_post_inf.data}"
    st_inf_id = res_post_inf.data['student']['id']
    st_inf = Student.objects.get(id=st_inf_id)
    assert st_inf.khmer_name == 'លី សុភ័ក្ត្រ'
    assert st_inf.enrollment_data.get('enrollment_mode') == 'MOEYS_INDIVIDUAL'  # inferred from Grade 10 config!
    assert st_inf.enrollment_data.get('birth_cert_book_num') == 'BOOK-AUTO-123'
    print("✔ POST enrollment with omitted mode automatically inferred MOEYS_INDIVIDUAL from Grade 10 config.")

    print("\n🎉 All Mobile Flexible Registration & Grade Options tests PASSED successfully!")

if __name__ == '__main__':
    run_tests()
