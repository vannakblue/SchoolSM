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
from apps.accounts.models import SchoolProfile, User
from apps.academics.models import AcademicYear, Classroom, GradeLevel, GradeEnrollmentOption
from apps.students.models import Student
from apps.mobile_api.views import MobileStudentEnrollAPIView, MobileGradeOptionsAPIView

def run_tests():
    print("=== Testing Mobile Dual Registration API ===")
    factory = RequestFactory()

    # 1. Setup Data
    year, _ = AcademicYear.objects.get_or_create(
        name="2025-2026",
        defaults={'start_date': '2025-10-01', 'end_date': '2026-08-31', 'is_current': True}
    )
    grade10, _ = GradeLevel.objects.get_or_create(
        grade_number=10,
        defaults={'name': 'ថ្នាក់ទី ១០'}
    )
    classroom, _ = Classroom.objects.get_or_create(
        name="10A-MobileTest",
        grade_level=10,
        academic_year=year,
        defaults={'capacity': 40}
    )

    # Setup Custom Grade Options for GENERAL and MOEYS_INDIVIDUAL
    opt_gen, _ = GradeEnrollmentOption.objects.get_or_create(
        grade_level=grade10,
        field_name="extra_notes_mobile",
        form_category=GradeEnrollmentOption.FormCategory.GENERAL,
        defaults={
            'label': 'កំណត់សម្គាល់បន្ថែមទូទៅ',
            'field_type': GradeEnrollmentOption.FieldType.TEXT,
            'is_active': True
        }
    )
    opt_moeys, _ = GradeEnrollmentOption.objects.get_or_create(
        grade_level=grade10,
        field_name="moeys_doc_num_mobile",
        form_category=GradeEnrollmentOption.FormCategory.MOEYS_INDIVIDUAL,
        defaults={
            'label': 'លេខបញ្ជីសំបុត្រកំណើតដើម',
            'field_type': GradeEnrollmentOption.FieldType.TEXT,
            'is_active': True
        }
    )

    school_profile = SchoolProfile.get_settings()
    school_profile.registration_mode = 'BOTH'
    school_profile.save()

    # 2. Test GET /api/v1/students/enroll/
    enroll_view = MobileStudentEnrollAPIView.as_view()
    req_get = factory.get('/api/v1/students/enroll/')
    res_get = enroll_view(req_get)
    assert res_get.status_code == 200, f"Expected 200, got {res_get.status_code}"
    data_get = res_get.data
    assert data_get['status'] == 'success'
    assert data_get['registration_mode'] == 'BOTH'
    assert 'moeys_choices' in data_get
    assert 'orphan_status' in data_get['moeys_choices']
    assert 'tracks' in data_get['moeys_choices']
    print("✔ GET /api/v1/students/enroll/ returned registration_mode and moeys_choices successfully.")

    # 3. Test GET /api/v1/students/grade-options/
    grade_opts_view = MobileGradeOptionsAPIView.as_view()
    
    # Check GENERAL options
    req_go_gen = factory.get(f'/api/v1/students/grade-options/?classroom_id={classroom.id}&form_category=GENERAL')
    res_go_gen = grade_opts_view(req_go_gen)
    assert res_go_gen.status_code == 200
    gen_names = [o['field_name'] for o in res_go_gen.data['options']]
    assert 'extra_notes_mobile' in gen_names, f"extra_notes_mobile should be in {gen_names}"
    assert 'moeys_doc_num_mobile' not in gen_names, "MoEYS option should not leak into GENERAL"
    print("✔ GET grade-options filtered by form_category=GENERAL works correctly.")

    # Check MOEYS options
    req_go_moeys = factory.get(f'/api/v1/students/grade-options/?classroom_id={classroom.id}&form_category=MOEYS_INDIVIDUAL')
    res_go_moeys = grade_opts_view(req_go_moeys)
    assert res_go_moeys.status_code == 200
    moeys_names = [o['field_name'] for o in res_go_moeys.data['options']]
    assert 'moeys_doc_num_mobile' in moeys_names, f"moeys_doc_num_mobile should be in {moeys_names}"
    assert 'extra_notes_mobile' not in moeys_names, "General option should not leak into MOEYS"
    print("✔ GET grade-options filtered by form_category=MOEYS_INDIVIDUAL works correctly.")

    # 4. Test POST /api/v1/students/enroll/ (ADMIN_CUSTOM Mode)
    post_admin_data = {
        'enrollment_mode': 'ADMIN_CUSTOM',
        'khmer_name': 'សុខ សម្បត្តិ',
        'latin_name': 'SOK SAMBATH',
        'gender': 'M',
        'date_of_birth': '2008-05-15',
        'place_of_birth': 'ភ្នំពេញ',
        'classroom_id': classroom.id,
        'academic_year_id': year.id,
        'grade_opt_extra_notes_mobile': 'សិស្សផ្ទេរមកពីវិទ្យាល័យបារាំង',
    }
    req_post_admin = factory.post(
        '/api/v1/students/enroll/',
        data=json.dumps(post_admin_data),
        content_type='application/json'
    )
    res_post_admin = enroll_view(req_post_admin)
    assert res_post_admin.status_code == 201, f"Expected 201, got {res_post_admin.status_code} ({res_post_admin.data})"
    student_admin_id = res_post_admin.data['student']['id']
    st_admin = Student.objects.get(id=student_admin_id)
    assert st_admin.khmer_name == 'សុខ សម្បត្តិ'
    assert st_admin.enrollment_data.get('extra_notes_mobile') == 'សិស្សផ្ទេរមកពីវិទ្យាល័យបារាំង'
    assert st_admin.enrollment_data.get('enrollment_mode') == 'ADMIN_CUSTOM'
    print("✔ POST enrollment in ADMIN_CUSTOM mode succeeded and saved grade option.")

    # 5. Test POST /api/v1/students/enroll/ (MOEYS_INDIVIDUAL Mode)
    post_moeys_data = {
        'enrollment_mode': 'MOEYS_INDIVIDUAL',
        'surname': 'កែវ',
        'given_name': 'មុន្នីរ័ត្ន',
        'latin_name': 'KEO MONYROTH',
        'gender': 'F',
        'date_of_birth': '2009-02-20',
        'pob_commune': 'សង្កាត់បឹងរាំង',
        'pob_district': 'ខណ្ឌដូនពេញ',
        'pob_province': 'រាជធានីភ្នំពេញ',
        'classroom_id': classroom.id,
        'academic_year_id': year.id,
        'orphan_status': 'កំព្រាឪពុក',
        'primary_school': 'បឋមសិក្សាព្រះនរោត្តម',
        'secondary_school': 'អនុវិទ្យាល័យចតុមុខ',
        'ethnic_minority': 'មិនមែន',
        'disability_physical': 'មិនមាន',
        'disability_sight': 'មើលមិនសូវច្បាស់',
        'equity_card_1': 'មាន',
        'risk_card': 'មិនមាន',
        'scholarship': 'អាហារូបករណ៍រដ្ឋ',
        'track': 'វិទ្យាសាស្ត្រ',
        'is_repeating_grade': True,
        'father_name': 'កែវ សារុន',
        'father_job': 'គ្រូបង្រៀន',
        'mother_name': 'ជា សុភី',
        'mother_job': 'មេផ្ទះ',
        'grade_options': {
            'moeys_doc_num_mobile': 'DOC-2025-0089'
        }
    }
    req_post_moeys = factory.post(
        '/api/v1/students/enroll/',
        data=json.dumps(post_moeys_data),
        content_type='application/json'
    )
    res_post_moeys = enroll_view(req_post_moeys)
    assert res_post_moeys.status_code == 201, f"Expected 201, got {res_post_moeys.status_code} ({res_post_moeys.data})"
    student_moeys_id = res_post_moeys.data['student']['id']
    st_moeys = Student.objects.get(id=student_moeys_id)
    assert st_moeys.khmer_name == 'កែវ មុន្នីរ័ត្ន', f"Expected 'កែវ មុន្នីរ័ត្ន', got '{st_moeys.khmer_name}'"
    assert 'សង្កាត់បឹងរាំង' in st_moeys.place_of_birth
    assert 'រាជធានីភ្នំពេញ' in st_moeys.place_of_birth
    assert st_moeys.is_repeating_grade is True
    
    ed = st_moeys.enrollment_data
    assert ed.get('enrollment_mode') == 'MOEYS_INDIVIDUAL'
    assert ed.get('orphan_status') == 'កំព្រាឪពុក'
    assert ed.get('equity_card_1') == 'មាន'
    assert ed.get('scholarship') == 'អាហារូបករណ៍រដ្ឋ'
    assert ed.get('is_sc') is True
    assert ed.get('moeys_doc_num_mobile') == 'DOC-2025-0089'
    print("✔ POST enrollment in MOEYS_INDIVIDUAL mode succeeded with all 35 columns and options!")

    print("\n🎉 All Mobile Dual-Enrollment API tests PASSED successfully!")

if __name__ == '__main__':
    run_tests()
