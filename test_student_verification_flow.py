import os
import sys
if sys.stdout and sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
import django
import json
from datetime import date, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.urls import reverse
from django.test import RequestFactory, Client
from django.utils import timezone
from apps.accounts.models import User
from apps.academics.models import AcademicYear, GradeLevel, Classroom
from apps.students.models import (
    Student,
    StudentVerificationCampaign,
    GradeVerificationFormConfig,
    StudentVerificationLog
)

def run_tests():
    print("==================================================================")
    print("   TESTING STUDENT BEGINNING-OF-YEAR VERIFICATION & CONFIRMATION   ")
    print("==================================================================")

    # 1. Setup Academic Year, Grade Levels, Classroom, and Admin User
    academic_year, _ = AcademicYear.objects.get_or_create(
        name="2025-2026",
        defaults={'start_date': date(2025, 10, 1), 'end_date': date(2026, 8, 31), 'is_current': True}
    )
    academic_year.is_current = True
    academic_year.save()

    grade_7, _ = GradeLevel.objects.get_or_create(
        grade_number=7,
        defaults={'name': 'ថ្នាក់ទី ៧', 'level_type': 'LOWER_SECONDARY'}
    )
    grade_10, _ = GradeLevel.objects.get_or_create(
        grade_number=10,
        defaults={'name': 'ថ្នាក់ទី ១០', 'level_type': 'UPPER_SECONDARY'}
    )

    classroom_7a, _ = Classroom.objects.get_or_create(
        code="7A-VERIF",
        academic_year=academic_year,
        defaults={'name': '7A', 'grade_level': 7, 'capacity': 45}
    )

    admin_user, _ = User.objects.get_or_create(
        username="test_admin_verif",
        defaults={'role': 'ADMIN', 'is_staff': True, 'is_superuser': True}
    )
    admin_user.set_password("Admin@12345")
    admin_user.role = 'ADMIN'
    admin_user.save()

    client = Client()
    client.force_login(admin_user)

    # 2. Test Multiple Rounds / Campaigns (ជុំទី១, ជុំទី២...)
    print("\n[TEST 1] Testing Admin Multiple Verification Rounds (ជុំទី១, ជុំទី២)...")
    camp1 = StudentVerificationCampaign.objects.create(
        title="ផ្ទៀងផ្ទាត់ទិន្នន័យដើមឆ្នាំ ជុំទី១",
        academic_year=academic_year,
        round_number=1,
        start_date=timezone.now(),
        end_date=timezone.now() + timedelta(days=15),
        is_active=True,
        instructions="សូមពិនិត្យ និងកែប្រែព័ត៌មានឱ្យបានត្រឹមត្រូវ",
        created_by=admin_user
    )
    assert camp1.round_number == 1
    assert camp1.is_active is True

    camp2 = StudentVerificationCampaign.objects.create(
        title="ផ្ទៀងផ្ទាត់ទិន្នន័យដើមឆ្នាំ ជុំទី២",
        academic_year=academic_year,
        round_number=2,
        start_date=timezone.now() + timedelta(days=16),
        end_date=timezone.now() + timedelta(days=31),
        is_active=False,
        instructions="ផ្ទៀងផ្ទាត់ឡើងវិញសម្រាប់សិស្សដែលខកខានជុំទី១",
        created_by=admin_user
    )
    assert camp2.round_number == 2
    print(f"  -> Successfully created Campaign Round 1 ({camp1.title}) and Round 2 ({camp2.title})")

    # 3. Test Admin Grade-level Form Template Selection (បែបបទតាមកម្រិតថ្នាក់ & Auto DB Update)
    print("\n[TEST 2] Testing Grade-Level Form Template Selection & Auto DB Update...")
    res = client.post(
        reverse('api_save_grade_form_config'),
        data=json.dumps({
            'grade_level_id': grade_7.id,
            'form_template': 'GENERAL'
        }),
        content_type='application/json'
    )
    assert res.status_code == 200, f"Failed saving grade 7 config: {res.content}"
    data = res.json()
    assert data['status'] == 'success'
    assert data['form_template'] == 'GENERAL'

    res_10 = client.post(
        reverse('api_save_grade_form_config'),
        data=json.dumps({
            'grade_level_id': grade_10.id,
            'form_template': 'MOEYS_INDIVIDUAL'
        }),
        content_type='application/json'
    )
    assert res_10.status_code == 200, f"Failed saving grade 10 config: {res_10.content}"
    assert res_10.json()['form_template'] == 'MOEYS_INDIVIDUAL'

    # Verify directly from DB
    tpl_7 = GradeVerificationFormConfig.get_template_for_grade(grade_7, academic_year=academic_year)
    tpl_10 = GradeVerificationFormConfig.get_template_for_grade(grade_10, academic_year=academic_year)
    assert tpl_7 == 'GENERAL'
    assert tpl_10 == 'MOEYS_INDIVIDUAL'
    print("  -> Grade 7 assigned to GENERAL template; Grade 10 assigned to MOEYS_INDIVIDUAL template in DB.")

    # 4. Create an Existing Student
    print("\n[TEST 3] Creating Pre-existing Student Record...")
    student_test_id = "STU-VERIF-001"
    existing_student, _ = Student.objects.update_or_create(
        student_id=student_test_id,
        defaults={
            'khmer_name': 'កែវ វិបុល',
            'latin_name': 'KEO VIBOL',
            'gender': 'M',
            'date_of_birth': date(2011, 5, 10),
            'place_of_birth': 'ខេត្តកណ្តាល',
            'current_address': 'ភ្នំពេញ',
            'phone': '012345678',
            'classroom': classroom_7a,
            'academic_year': academic_year,
            'father_name': 'កែវ សុខ',
            'father_phone': '012999888',
            'mother_name': 'ម៉េង ធីតា',
            'mother_phone': '012777666',
            'is_verified': False
        }
    )
    print(f"  -> Created student: {existing_student.khmer_name} (ID: {existing_student.student_id})")

    # 5. Web Portal Live Student Lookup
    print("\n[TEST 4] Testing Web Portal Student Lookup (AJAX)...")
    res_lookup = client.get(f"{reverse('api_verification_lookup_student')}?student_id={student_test_id}")
    assert res_lookup.status_code == 200
    lookup_data = res_lookup.json()
    assert lookup_data['status'] == 'found'
    assert lookup_data['is_existing'] is True
    assert lookup_data['student']['khmer_name'] == 'កែវ វិបុល'
    assert lookup_data['assigned_form_template'] == 'GENERAL'
    assert lookup_data['confirmation_required'] is True
    print("  -> Lookup returned existing student data with confirmation_required=True and assigned template GENERAL")

    # 6. Web Portal Submit WITHOUT Confirmation (Must be rejected)
    print("\n[TEST 5] Submitting Update to Existing Student WITHOUT Confirmation (Should Require Confirmation)...")
    res_unconfirmed = client.post(reverse('student_verification_submit'), {
        'student_pk': existing_student.pk,
        'student_id': existing_student.student_id,
        'khmer_name': 'កែវ វិបុល កែប្រែ',
        'gender': 'M',
        'date_of_birth': '2011-05-10',
        'classroom': classroom_7a.pk,
        # confirm_edit is MISSING
    })
    # Should redirect back with error message
    existing_student.refresh_from_db()
    assert existing_student.khmer_name == 'កែវ វិបុល', "Data should NOT change without confirmation!"
    print("  -> Correctly blocked unconfirmed edit for existing student!")

    # 7. Web Portal Submit WITH Parent Confirmation (Should update DB & create audit log)
    print("\n[TEST 6] Submitting Update to Existing Student WITH Parent Confirmation (Should Update DB)...")
    res_confirmed = client.post(reverse('student_verification_submit'), {
        'student_pk': existing_student.pk,
        'student_id': existing_student.student_id,
        'khmer_name': 'កែវ វិបុល (ផ្ទៀងផ្ទាត់រួច)',
        'latin_name': 'KEO VIBOL CONFIRMED',
        'gender': 'M',
        'date_of_birth': '2011-05-10',
        'classroom': classroom_7a.pk,
        'phone': '099112233',
        # Mandatory Confirmation
        'confirm_edit': 'on',
        'confirmed_by_role': 'PARENT',
        'confirmed_by_name': 'កែវ សុខ (ឪពុក)',
        'confirmed_by_phone': '012999888',
        'relationship_to_student': 'ឪពុកបង្កើត',
        'confirmation_notes': 'បានពិនិត្យ និងកែប្រែលេខទូរស័ព្ទថ្មីរបស់កូន'
    })
    assert res_confirmed.status_code in [200, 302]
    existing_student.refresh_from_db()
    assert existing_student.khmer_name == 'កែវ វិបុល (ផ្ទៀងផ្ទាត់រួច)'
    assert existing_student.phone == '099112233'
    assert existing_student.is_verified is True
    assert existing_student.last_verified_by_role == 'PARENT'
    assert existing_student.last_verified_by_name == 'កែវ សុខ (ឪពុក)'

    # Check StudentVerificationLog
    log = StudentVerificationLog.objects.filter(student=existing_student).latest('id')
    assert log.confirmed_by_role == 'PARENT'
    assert log.confirmed_by_name == 'កែវ សុខ (ឪពុក)'
    assert log.channel == 'PORTAL'
    print("  -> Portal Confirmation Success: DB updated automatically and audit log created!")

    # 8. Mobile API Verification Tests
    print("\n[TEST 7] Testing Mobile API Campaigns List...")
    res_m_camps = client.get('/api/v1/students/verification/campaigns/')
    assert res_m_camps.status_code == 200
    m_camps_data = res_m_camps.json()
    assert m_camps_data['status'] == 'success'
    assert len(m_camps_data['campaigns']) >= 2
    assert len(m_camps_data['grade_form_configs']) >= 2
    print(f"  -> Mobile Campaigns API returned {len(m_camps_data['campaigns'])} rounds and grade configs.")

    print("\n[TEST 8] Testing Mobile API Student Lookup...")
    res_m_lookup = client.get(f'/api/v1/students/verification/lookup/?student_id={student_test_id}')
    assert res_m_lookup.status_code == 200
    m_lookup_data = res_m_lookup.json()
    assert m_lookup_data['status'] == 'success'
    assert m_lookup_data['is_existing_student'] is True
    assert m_lookup_data['confirmation_required'] is True
    print("  -> Mobile Lookup API successfully returned student details and confirmation_required=True")

    print("\n[TEST 9] Testing Mobile API Submit WITHOUT Confirmation...")
    res_m_unconfirmed = client.post(
        '/api/v1/students/verification/submit/',
        data=json.dumps({
            'student_id': student_test_id,
            'khmer_name': 'កែវ វិបុល Mobile Hack',
            'confirm_edit': False
        }),
        content_type='application/json'
    )
    assert res_m_unconfirmed.status_code == 400
    m_err = res_m_unconfirmed.json()
    assert m_err['error'] == 'CONFIRMATION_REQUIRED'
    print("  -> Mobile API correctly blocked unconfirmed edit with CONFIRMATION_REQUIRED!")

    print("\n[TEST 10] Testing Mobile API Submit WITH Teacher Confirmation (គ្រូបង្រៀន)...")
    res_m_confirmed = client.post(
        '/api/v1/students/verification/submit/',
        data=json.dumps({
            'student_id': student_test_id,
            'khmer_name': 'កែវ វិបុល (ផ្ទៀងផ្ទាត់ដោយគ្រូ)',
            'latin_name': 'KEO VIBOL TEACHER VERIFIED',
            'gender': 'M',
            'date_of_birth': '2011-05-10',
            'classroom_id': classroom_7a.pk,
            'phone': '088998877',
            # Teacher confirmation
            'confirm_edit': True,
            'confirmed_by_role': 'TEACHER',
            'confirmed_by_name': 'អ្នកគ្រូ ចាន់ សុភា',
            'confirmed_by_phone': '011223344',
            'relationship_to_student': 'គ្រូបន្ទុកថ្នាក់ទី ៧A',
            'confirmation_notes': 'បានផ្ទៀងផ្ទាត់ជាមួយសំបុត្រកំណើតច្បាប់ដើម'
        }),
        content_type='application/json'
    )
    assert res_m_confirmed.status_code == 200, f"Error: {res_m_confirmed.content}"
    m_success = res_m_confirmed.json()
    assert m_success['status'] == 'success'
    assert m_success['verified'] is True

    existing_student.refresh_from_db()
    assert existing_student.khmer_name == 'កែវ វិបុល (ផ្ទៀងផ្ទាត់ដោយគ្រូ)'
    assert existing_student.last_verified_by_role == 'TEACHER'
    assert existing_student.last_verified_by_name == 'អ្នកគ្រូ ចាន់ សុភា'

    m_log = StudentVerificationLog.objects.filter(student=existing_student).latest('id')
    assert m_log.confirmed_by_role == 'TEACHER'
    assert m_log.confirmed_by_name == 'អ្នកគ្រូ ចាន់ សុភា'
    assert m_log.channel == 'MOBILE_APP'
    print("  -> Mobile Teacher Confirmation Success: DB updated automatically and mobile audit log saved!")

    print("\n[TEST 11] Testing Student Confirmation (សិស្សផ្ទាល់)...")
    res_stu_confirmed = client.post(
        '/api/v1/students/verification/submit/',
        data=json.dumps({
            'student_id': student_test_id,
            'khmer_name': 'កែវ វិបុល (ផ្ទៀងផ្ទាត់ដោយសិស្សផ្ទាល់)',
            'gender': 'M',
            'date_of_birth': '2011-05-10',
            # Student confirmation
            'confirm_edit': True,
            'confirmed_by_role': 'STUDENT',
            'confirmed_by_name': 'កែវ វិបុល (សិស្ស)',
            'relationship_to_student': 'សាមីខ្លួន',
            'confirmation_notes': 'ខ្ញុំបានពិនិត្យឈ្មោះ និងថ្ងៃខែឆ្នាំកំណើតត្រឹមត្រូវហើយ'
        }),
        content_type='application/json'
    )
    assert res_stu_confirmed.status_code == 200
    existing_student.refresh_from_db()
    assert existing_student.khmer_name == 'កែវ វិបុល (ផ្ទៀងផ្ទាត់ដោយសិស្សផ្ទាល់)'
    assert existing_student.last_verified_by_role == 'STUDENT'
    print("  -> Student Direct Confirmation Success: DB updated automatically!")

    print("\n[TEST 12] Testing Verification Logs API...")
    res_logs = client.get('/api/v1/students/verification/logs/')
    assert res_logs.status_code == 200
    logs_data = res_logs.json()
    assert logs_data['status'] == 'success'
    assert logs_data['count'] >= 3
    print(f"  -> Verification Logs API returned {logs_data['count']} audit logs covering Parent, Teacher, and Student.")

    print("\n==================================================================")
    print("   ALL TESTS PASSED! (12/12) VERIFICATION & CONFIRMATION VERIFIED   ")
    print("==================================================================")

if __name__ == '__main__':
    run_tests()
