import os
import sys
import django
import json

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from apps.academics.models import AcademicYear
from apps.examinations.models import StandardizedExam, StandardizedExamType
import datetime

User = get_user_model()

def run_tests():
    print("=== STARTING STANDARDIZED EXAM TYPES CRUD TEST SUITE ===")

    # 1. Setup Admin and Teacher users
    admin_user, _ = User.objects.get_or_create(
        username='admin_exam_type_test',
        defaults={'role': 'ADMIN', 'is_staff': True, 'is_superuser': True}
    )
    admin_user.role = 'ADMIN'
    admin_user.is_superuser = True
    admin_user.save()

    teacher_user, _ = User.objects.get_or_create(
        username='teacher_exam_type_test',
        defaults={'role': 'TEACHER', 'is_staff': False, 'is_superuser': False}
    )
    teacher_user.role = 'TEACHER'
    teacher_user.is_superuser = False
    teacher_user.save()

    client_admin = Client()
    client_admin.force_login(admin_user)

    client_teacher = Client()
    client_teacher.force_login(teacher_user)

    from apps.academics.utils import get_active_academic_year
    ay = get_active_academic_year(None) or AcademicYear.objects.filter(is_active=True).first()

    # 2. Test auto-seeding of default types
    StandardizedExamType.ensure_defaults()
    all_types = StandardizedExamType.objects.all()
    assert all_types.count() >= 6, f"Expected at least 6 default types, got {all_types.count()}"
    codes = list(all_types.values_list('code', flat=True))
    assert 'BASELINE' in codes
    assert 'SEMESTER_1' in codes
    assert 'SEMESTER_2' in codes
    assert 'MOCK' in codes
    assert 'ENDLINE' in codes
    assert 'MONTHLY' in codes
    print("1. [PASS] Default exam types auto-seeded properly.")

    # 3. Test Admin GET standardized_exam_type_list (HTML & JSON)
    res_html = client_admin.get('/examinations/standardized/types/')
    assert res_html.status_code == 200
    html_content = res_html.content.decode('utf-8')
    assert 'គ្រប់គ្រងប្រភេទសម័យប្រឡង' in html_content
    assert 'តេស្តដើមឆ្នាំ' in html_content

    res_json = client_admin.get('/examinations/standardized/types/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
    assert res_json.status_code == 200
    json_data = res_json.json()
    assert json_data['status'] == 'success'
    assert len(json_data['types']) >= 6
    print("2. [PASS] Admin can view exam types list via both HTML and JSON.")

    # 4. Test Non-Admin (Teacher) forbidden from managing exam types
    res_teacher_get = client_teacher.get('/examinations/standardized/types/')
    assert res_teacher_get.status_code in [302, 403]
    res_teacher_post = client_teacher.post('/examinations/standardized/types/create/', {
        'name': 'Hacked Type',
        'code': 'HACK'
    })
    assert res_teacher_post.status_code in [302, 403]
    assert not StandardizedExamType.objects.filter(code='HACK').exists()
    print("3. [PASS] Non-admin users are strictly denied from managing exam types.")

    # 5. Test Admin POST standardized_exam_type_create (Add new type)
    StandardizedExamType.objects.filter(code='MIDTERM_TEST').delete()
    res_create = client_admin.post('/examinations/standardized/types/create/', {
        'name': 'ប្រឡងពាក់កណ្តាលឆមាស',
        'code': 'MIDTERM_TEST',
        'icon': '🏆',
        'default_title': 'ការប្រឡងពាក់កណ្តាលឆមាស',
        'order': '8',
        'is_active': 'on'
    })
    assert res_create.status_code in [200, 302]
    new_type = StandardizedExamType.objects.filter(code='MIDTERM_TEST').first()
    assert new_type is not None
    assert new_type.name == 'ប្រឡងពាក់កណ្តាលឆមាស'
    assert new_type.icon == '🏆'
    assert new_type.order == 8
    print("4. [PASS] Admin successfully added a new custom exam type.")

    # 6. Test Admin POST standardized_exam_type_edit (Edit existing type)
    res_edit = client_admin.post(f'/examinations/standardized/types/{new_type.id}/edit/', {
        'name': 'ប្រឡងពាក់កណ្តាលឆមាស កែប្រែ',
        'code': 'MIDTERM_EDITED',
        'icon': '🥇',
        'default_title': 'ការប្រឡងពាក់កណ្តាលឆមាស កែប្រែថ្មី',
        'order': '9',
        'is_active': 'on'
    })
    assert res_edit.status_code in [200, 302]
    new_type.refresh_from_db()
    assert new_type.name == 'ប្រឡងពាក់កណ្តាលឆមាស កែប្រែ'
    assert new_type.code == 'MIDTERM_EDITED'
    assert new_type.icon == '🥇'
    assert new_type.order == 9
    print("5. [PASS] Admin successfully edited custom exam type.")

    # 7. Test creating a StandardizedExam with the newly created custom exam type
    StandardizedExam.objects.filter(name__icontains='ប្រឡងពាក់កណ្តាលឆមាស ថ្នាក់ទី១២').delete()
    res_create_exam = client_admin.post('/examinations/standardized/create/', {
        'name': 'ការប្រឡងពាក់កណ្តាលឆមាស ថ្នាក់ទី១២',
        'academic_year': ay.id,
        'exam_type': 'MIDTERM_EDITED',
        'selected_grades': ['12'],
        'track': 'ALL',
        'session': 'MORNING',
        'exam_date': '2026-12-15',
        'candidates_per_room': '25'
    })
    assert res_create_exam.status_code in [200, 302]
    exam = StandardizedExam.objects.filter(name__icontains='ប្រឡងពាក់កណ្តាលឆមាស ថ្នាក់ទី១២').first()
    assert exam is not None
    assert exam.exam_type == 'MIDTERM_EDITED'
    print("6. [PASS] StandardizedExam successfully created using custom exam type.")

    # 8. Test exam_form.html renders custom preset button and manage modal
    res_form = client_admin.get('/examinations/standardized/create/')
    assert res_form.status_code == 200
    form_html = res_form.content.decode('utf-8')
    assert 'MIDTERM_EDITED' in form_html
    assert '🥇' in form_html
    assert 'ប្រឡងពាក់កណ្តាលឆមាស កែប្រែ' in form_html
    assert 'manageExamTypesModal' in form_html
    assert 'គ្រប់គ្រងប្រភេទ' in form_html
    print("7. [PASS] exam_form.html dynamically renders custom preset button and manage modal.")

    # 9. Test Admin POST standardized_exam_type_delete (Delete type with safe exam fallback)
    type_to_del_id = new_type.id
    res_delete = client_admin.post(f'/examinations/standardized/types/{type_to_del_id}/delete/')
    assert res_delete.status_code in [200, 302]
    assert not StandardizedExamType.objects.filter(id=type_to_del_id).exists()
    
    # Verify exam using that code was safely updated to 'OTHER'
    exam.refresh_from_db()
    assert exam.exam_type == 'OTHER', f"Expected exam_type to fallback to 'OTHER', got {exam.exam_type}"
    print("8. [PASS] Admin successfully deleted custom exam type with safe exam fallback to 'OTHER'.")

    # 10. Clean up test data
    exam.delete()
    print("9. [PASS] Cleaned up test data.")

    print("\n=== ALL 9 EXAM TYPES CRUD TESTS PASSED 100%! ===")

if __name__ == '__main__':
    run_tests()
