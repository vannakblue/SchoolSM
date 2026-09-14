import os
import sys
if sys.stdout and sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import django
import json
from datetime import date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from django.urls import reverse
from apps.accounts.models import User, SchoolProfile
from apps.academics.models import AcademicYear, GradeLevel, Classroom, GradeEnrollmentOption
from apps.students.models import Student
from apps.students.forms import StudentEnrollmentForm, MoeysIndividualStudentForm

def run_tests():
    print("==================================================================")
    print("   TESTING DEFAULT BASIC ENROLLMENT FIELDS & ADMIN FLEXIBILITY   ")
    print("==================================================================")

    # 1. Setup Academic Year, Grade Levels, Classroom, Admin User
    academic_year, _ = AcademicYear.objects.get_or_create(
        name="2025-2026",
        defaults={'start_date': date(2025, 10, 1), 'end_date': date(2026, 8, 31), 'is_current': True}
    )
    grade_7, _ = GradeLevel.objects.get_or_create(
        grade_number=7,
        defaults={'name': 'ថ្នាក់ទី ៧', 'level_type': 'LOWER_SECONDARY'}
    )
    classroom_7a, _ = Classroom.objects.get_or_create(
        code="7A-DEFAULT-TEST",
        academic_year=academic_year,
        defaults={'name': '7A Default Test', 'grade_level': 7, 'capacity': 40}
    )
    admin_user, _ = User.objects.get_or_create(
        username="admin_default_test",
        defaults={'role': 'ADMIN', 'is_staff': True, 'is_superuser': True}
    )
    admin_user.set_password("Admin@12345")
    admin_user.role = 'ADMIN'
    admin_user.save()

    client = Client()
    client.force_login(admin_user)

    # Clean up test students
    Student.objects.filter(khmer_name__in=['ហេង សុវណ្ណារ៉ា', 'ហេង សុវណ្ណារ៉ា កែប្រែ', 'ចាន់ បុប្ផា', 'ស៊ុន ដារ៉ា']).delete()
    Student.objects.filter(student_id__in=["STU-DEF-001", "STU-DEF-002", "STU-DEF-MOB-001"]).delete()

    # TEST 1: Model & StudentEnrollmentForm with Default Basic Fields
    print("\n[TEST 1] Testing StudentEnrollmentForm with 5 Core Default Basic Fields...")
    form_data = {
        'student_id': 'STU-DEF-001',
        'khmer_name': 'ហេង សុវណ្ណារ៉ា',
        'latin_name': 'HENG SOVANNARA',
        'gender': 'M',
        'date_of_birth': '2012-04-15',
        'previous_school': 'បឋមសិក្សា វត្តភ្នំ (២០២៤-២០២៥)',
        'phone': '012334455',
        'classroom': classroom_7a.id,
        'academic_year': academic_year.id,
        'status': 'ACTIVE',
        'scholarship_type': 'FULL_PAY',
    }
    form = StudentEnrollmentForm(data=form_data, academic_year=academic_year)
    assert form.is_valid(), f"StudentEnrollmentForm errors: {form.errors}"
    student1 = form.save()

    assert student1.khmer_name == 'ហេង សុវណ្ណារ៉ា'
    assert student1.latin_name == 'HENG SOVANNARA'
    assert student1.gender == 'M'
    assert student1.date_of_birth == date(2012, 4, 15)
    assert student1.previous_school == 'បឋមសិក្សា វត្តភ្នំ (២០២៤-២០២៥)'
    assert student1.phone == '012334455'
    print("  ✔ Successfully created student with all 5 default basic fields via StudentEnrollmentForm.")

    # TEST 2: Admin Editing / Replacing Basic Fields via Form
    print("\n[TEST 2] Testing Admin Editing / Replacing Default Basic Fields...")
    edit_form_data = {
        'student_id': 'STU-DEF-001',
        'khmer_name': 'ហេង សុវណ្ណារ៉ា កែប្រែ',
        'latin_name': 'HENG SOVANNARA MODIFIED',
        'gender': 'M',
        'date_of_birth': '2012-04-15',
        'previous_school': 'សាលាអន្តរជាតិ សុវណ្ណភូមិ (ផ្ទេរចូល)',
        'phone': '098776655',
        'classroom': classroom_7a.id,
        'academic_year': academic_year.id,
        'status': 'ACTIVE',
        'scholarship_type': 'FULL_PAY',
    }
    edit_form = StudentEnrollmentForm(data=edit_form_data, instance=student1, academic_year=academic_year)
    assert edit_form.is_valid(), f"Edit form errors: {edit_form.errors}"
    updated_student = edit_form.save()
    assert updated_student.khmer_name == 'ហេង សុវណ្ណារ៉ា កែប្រែ'
    assert updated_student.previous_school == 'សាលាអន្តរជាតិ សុវណ្ណភូមិ (ផ្ទេរចូល)'
    assert updated_student.phone == '098776655'
    print("  ✔ Admin successfully edited & replaced previous_school, phone, and name.")

    # TEST 3: MoeysIndividualStudentForm with Previous School Sync
    print("\n[TEST 3] Testing MoeysIndividualStudentForm Previous School Sync...")
    moeys_data = {
        'student_id': 'STU-DEF-002',
        'surname': 'ចាន់',
        'given_name': 'បុប្ផា',
        'latin_name': 'CHAN BOPHA',
        'gender': 'F',
        'date_of_birth': '2011-09-20',
        'primary_school': 'បឋមសិក្សា ចាក់អង្រែ',
        'phone': '011223344',
        'classroom': classroom_7a.id,
        'academic_year': academic_year.id,
        'track': 'ទូទៅ',
    }
    moeys_form = MoeysIndividualStudentForm(data=moeys_data, academic_year=academic_year)
    assert moeys_form.is_valid(), f"Moeys form errors: {moeys_form.errors}"
    student2 = moeys_form.save()
    assert student2.khmer_name == 'ចាន់ បុប្ផា'
    assert student2.previous_school == 'បឋមសិក្សា ចាក់អង្រែ'
    assert student2.phone == '011223344'
    print("  ✔ MoeysIndividualStudentForm automatically synced primary_school into previous_school.")

    # TEST 4: Mobile API Metadata includes default_basic_fields schema
    print("\n[TEST 4] Testing Mobile API GET metadata for default_basic_fields...")
    res_meta = client.get(reverse('mobile_api_student_enroll'))
    assert res_meta.status_code == 200, f"Failed GET mobile meta: {res_meta.content}"
    meta_json = res_meta.json()
    assert 'default_basic_fields' in meta_json, "default_basic_fields not found in mobile meta"
    default_fields = [f['field_name'] for f in meta_json['default_basic_fields']]
    assert 'khmer_name' in default_fields
    assert 'gender' in default_fields
    assert 'date_of_birth' in default_fields
    assert 'previous_school' in default_fields
    assert 'phone' in default_fields
    print(f"  ✔ Mobile API provides default_basic_fields schema: {default_fields}")

    # TEST 5: Mobile API POST with Default Basic Fields
    print("\n[TEST 5] Testing Mobile API POST student enrollment with previous_school...")
    mobile_enroll_payload = {
        'khmer_name': 'ស៊ុន ដារ៉ា',
        'latin_name': 'SUN DARA',
        'gender': 'M',
        'date_of_birth': '2012-01-10',
        'phone': '017889900',
        'previous_school': 'អនុវិទ្យាល័យ ហ៊ុន សែន ព្រែកប្រា (២០២៤-២០២៥)',
        'classroom_id': classroom_7a.id,
        'academic_year_id': academic_year.id,
    }
    res_post = client.post(
        reverse('mobile_api_student_enroll'),
        data=json.dumps(mobile_enroll_payload),
        content_type='application/json'
    )
    assert res_post.status_code in [200, 201], f"Mobile POST failed: {res_post.content}"
    post_json = res_post.json()
    assert post_json['status'] == 'success'
    stu_id = post_json['student']['id']
    saved_stu = Student.objects.get(id=stu_id)
    assert saved_stu.khmer_name == 'ស៊ុន ដារ៉ា'
    assert saved_stu.gender == 'M'
    assert saved_stu.previous_school == 'អនុវិទ្យាល័យ ហ៊ុន សែន ព្រែកប្រា (២០២៤-២០២៥)'
    assert saved_stu.phone == '017889900'
    print(f"  ✔ Student enrolled via Mobile API with previous_school saved directly: {saved_stu.previous_school}")

    # TEST 6: Web Template Rendering (student_form.html & student_detail.html)
    print("\n[TEST 6] Testing Web Templates Rendering for previous_school...")
    res_form_page = client.get(reverse('student_enroll'))
    assert res_form_page.status_code == 200
    form_html = res_form_page.content.decode('utf-8')
    assert 'previous_school' in form_html
    assert 'ឆ្នាំសិក្សាចាស់មកពីសាលា' in form_html

    res_detail_page = client.get(reverse('student_detail', kwargs={'pk': saved_stu.pk}))
    assert res_detail_page.status_code == 200
    detail_html = res_detail_page.content.decode('utf-8')
    assert 'ឆ្នាំសិក្សាចាស់មកពីសាលា' in detail_html
    assert saved_stu.previous_school in detail_html
    print("  ✔ Web enrollment form and student detail page render 'ឆ្នាំសិក្សាចាស់មកពីសាលា' successfully.")

    print("\n==================================================================")
    print("   ALL TESTS PASSED (6/6)! DEFAULT BASIC FIELDS FULLY VERIFIED   ")
    print("==================================================================")

if __name__ == '__main__':
    run_tests()
