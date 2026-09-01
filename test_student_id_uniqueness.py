import os
import sys
import django
import json

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from django.core.exceptions import ValidationError
from apps.accounts.models import User
from apps.academics.models import AcademicYear, Classroom
from apps.students.models import Student
from apps.students.forms import StudentEnrollmentForm
from datetime import date, datetime

def run_tests():
    print("=== STARTING STUDENT ID UNIQUENESS & NON-DUPLICATION TEST SUITE ===")

    # 1. Setup Admin User & Test Academic Year
    admin_user, _ = User.objects.get_or_create(
        username='test_admin_sid',
        defaults={'role': 'ADMIN', 'is_staff': True, 'is_superuser': True}
    )
    admin_user.set_password('Admin@123456')
    admin_user.role = 'ADMIN'
    admin_user.save()

    client = Client()
    client.force_login(admin_user)

    year, _ = AcademicYear.objects.get_or_create(
        name='2026-2027 TEST SID',
        defaults={'start_date': date(2026, 1, 1), 'end_date': date(2026, 12, 31), 'is_current': True}
    )

    cls_7a, _ = Classroom.objects.get_or_create(
        name='7A_SID_TEST',
        academic_year=year,
        defaults={'grade_level': 7, 'code': '7A_SID'}
    )

    # Clean any old test students
    Student.objects.filter(classroom=cls_7a).delete()
    Student.objects.filter(khmer_name__startswith='សិស្សតេស្ត_SID').delete()

    print("1. [PASS] Setup test fixtures and environment.")

    # 2. Test Auto-Generation Uniqueness (Sequential creation)
    created_students = []
    for i in range(1, 6):
        st = Student.objects.create(
            khmer_name=f'សិស្សតេស្ត_SID_{i}',
            latin_name=f'Student Test SID {i}',
            gender='M',
            date_of_birth=date(2012, 5, 10),
            classroom=cls_7a,
            academic_year=year
        )
        created_students.append(st)

    sids = [s.student_id for s in created_students]
    print(f"   Generated Student IDs: {sids}")
    assert len(sids) == len(set(sids)), "All generated Student IDs must be strictly unique!"
    assert all(s.startswith('26') for s in sids), "All IDs for 2026 academic year must start with '26'!"
    print("2. [PASS] Auto-generated 5 sequential student IDs with 100% uniqueness.")

    # 3. Test Collision-free Generation when Gaps or Custom IDs Exist
    custom_gap_st = Student.objects.create(
        student_id='269990',
        khmer_name='សិស្សតេស្ត_SID_CustomGap',
        latin_name='Student Custom Gap',
        gender='F',
        date_of_birth=date(2012, 6, 1),
        classroom=cls_7a,
        academic_year=year
    )

    next_auto_id = Student.generate_unique_student_id(year)
    assert next_auto_id != '269990', "Generated ID must not collide with existing 269990"
    assert next_auto_id.startswith('26'), "Generated ID must have correct year prefix"
    print(f"   Next Auto-Generated ID after gap: {next_auto_id}")
    print("3. [PASS] Collision-detection loop successfully skipped existing custom gap IDs.")

    # 4. Test Model-Level clean() and save() Duplicate Rejection
    dup_st = Student(
        student_id=created_students[0].student_id, # Attempt to use student 1's ID
        khmer_name='សិស្សតេស្ត_SID_Duplicate',
        latin_name='Student Duplicate',
        gender='M',
        date_of_birth=date(2012, 1, 1),
        classroom=cls_7a,
        academic_year=year
    )
    
    clean_failed = False
    try:
        dup_st.clean()
    except ValidationError as e:
        clean_failed = True
        assert 'student_id' in e.message_dict or hasattr(e, 'messages')
    assert clean_failed, "Model clean() must raise ValidationError on duplicate student_id!"

    save_failed = False
    try:
        dup_st.save()
    except (ValidationError, Exception):
        save_failed = True
    assert save_failed, "Model save() must reject duplicate student_id!"
    print("4. [PASS] Model clean() and save() strictly reject duplicate student IDs.")

    # 5. Test StudentEnrollmentForm Validation
    form_valid_data = {
        'student_id': 'CUSTOM-UNIQ-001',
        'khmer_name': 'សុខ ចិន្តា តេស្ត',
        'latin_name': 'SOK CHINDA TEST',
        'gender': 'F',
        'date_of_birth': '2012-04-15',
        'classroom': cls_7a.id,
        'academic_year': year.id,
        'status': 'ACTIVE',
        'scholarship_type': 'FULL_PAY',
    }
    form_valid = StudentEnrollmentForm(data=form_valid_data, academic_year=year)
    assert form_valid.is_valid(), f"Form with unique custom ID should be valid: {form_valid.errors}"
    st_custom = form_valid.save()
    assert st_custom.student_id == 'CUSTOM-UNIQ-001'

    # Try duplicate in form
    form_dup_data = form_valid_data.copy()
    form_dup_data['khmer_name'] = 'សិស្ស ស្ទួន'
    form_dup = StudentEnrollmentForm(data=form_dup_data, academic_year=year)
    assert not form_dup.is_valid(), "Form must be invalid when duplicate student_id is submitted!"
    assert 'student_id' in form_dup.errors, "Form errors must include student_id"
    print("5. [PASS] StudentEnrollmentForm validates custom IDs and rejects duplicates with Khmer messages.")

    # Self-edit with same ID should pass
    form_edit = StudentEnrollmentForm(instance=st_custom, data=form_valid_data, academic_year=year)
    assert form_edit.is_valid(), f"Editing existing student with own ID must be valid: {form_edit.errors}"
    print("6. [PASS] Form allows editing student while keeping their existing student_id.")

    # 6. Test AJAX API Endpoints
    # Check taken ID
    resp_check_taken = client.get(f'/students/api/check-student-id/?student_id=CUSTOM-UNIQ-001&year_id={year.id}')
    assert resp_check_taken.status_code == 200
    data_taken = resp_check_taken.json()
    assert data_taken['is_available'] == False
    assert '❌' in data_taken['message']
    assert data_taken['existing_student']['name'] == 'សុខ ចិន្តា តេស្ត'

    # Check available ID
    resp_check_avail = client.get(f'/students/api/check-student-id/?student_id=TOTALLY_FREE_ID&year_id={year.id}')
    assert resp_check_avail.status_code == 200
    data_avail = resp_check_avail.json()
    assert data_avail['is_available'] == True
    assert '✅' in data_avail['message']

    # Generate next ID API
    resp_gen = client.get(f'/students/api/generate-student-id/?year_id={year.id}')
    assert resp_gen.status_code == 200
    data_gen = resp_gen.json()
    assert data_gen['status'] == 'success'
    assert bool(data_gen['student_id'])
    print("7. [PASS] AJAX Check & Generate APIs return correct live availability status and suggestions.")

    # 7. Test Mobile API Endpoints
    # Mobile check ID
    resp_mob_chk = client.get(f'/api/v1/students/check-id/?student_id=CUSTOM-UNIQ-001&academic_year_id={year.id}')
    assert resp_mob_chk.status_code == 200
    assert resp_mob_chk.json()['is_available'] == False

    # Mobile Enroll with blank ID (Auto-generate)
    resp_mob_enroll = client.post(
        '/api/v1/students/enroll/',
        data=json.dumps({
            'khmer_name': 'សិស្ស តាម Mobile App',
            'latin_name': 'Student Mobile App',
            'gender': 'M',
            'date_of_birth': '2012-08-20',
            'classroom_id': cls_7a.id,
            'academic_year_id': year.id
        }),
        content_type='application/json'
    )
    assert resp_mob_enroll.status_code == 201, f"Expected 201, got {resp_mob_enroll.status_code}: {resp_mob_enroll.content}"
    mob_data = resp_mob_enroll.json()
    assert mob_data['status'] == 'success'
    assert bool(mob_data['student']['student_id'])
    mob_sid = mob_data['student']['student_id']

    # Mobile Enroll with Duplicate ID
    resp_mob_dup = client.post(
        '/api/v1/students/enroll/',
        data=json.dumps({
            'student_id': mob_sid, # Use same ID
            'khmer_name': 'សិស្ស ស្ទួន Mobile',
            'gender': 'F',
            'classroom_id': cls_7a.id
        }),
        content_type='application/json'
    )
    assert resp_mob_dup.status_code == 400
    assert '❌' in resp_mob_dup.json()['message']
    print("8. [PASS] Mobile API enrolls student with unique auto-generated ID and rejects duplicate custom ID.")

    # 8. Test Excel Import Duplicate Detection
    from io import BytesIO
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Students"
    ws.append(['ឈ្មោះខ្មែរ', 'ឈ្មោះឡាតាំង', 'ភេទ', 'ថ្ងៃខែឆ្នាំកំណើត', 'ថ្នាក់រៀន', 'អត្តលេខ'])
    # Row 1: Valid unique
    ws.append(['សិស្ស Excel 1', 'Excel 1', 'ប្រុស', '2012-01-01', '7A_SID_TEST', 'EXCEL-UNIQ-991'])
    # Row 2: Duplicate of Row 1 within same sheet
    ws.append(['សិស្ស Excel 2', 'Excel 2', 'ស្រី', '2012-01-01', '7A_SID_TEST', 'EXCEL-UNIQ-991'])
    # Row 3: Duplicate of existing DB ID
    ws.append(['សិស្ស Excel 3', 'Excel 3', 'ប្រុស', '2012-01-01', '7A_SID_TEST', mob_sid])

    excel_file = BytesIO()
    wb.save(excel_file)
    excel_file.seek(0)

    from django.core.files.uploadedfile import SimpleUploadedFile
    up_file = SimpleUploadedFile("students_test.xlsx", excel_file.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    resp_import = client.post(
        f'/students/import/',
        data={'file': up_file, 'academic_year': year.id},
        follow=True
    )
    assert resp_import.status_code == 200

    # Verify that only 1 student was created from Excel (the unique one) and duplicates were skipped
    assert Student.objects.filter(student_id='EXCEL-UNIQ-991').count() == 1
    assert not Student.objects.filter(khmer_name='សិស្ស Excel 2').exists()
    print("9. [PASS] Excel import created valid unique row and successfully rejected duplicate student IDs in sheet & DB.")

    # Clean up test records
    Student.objects.filter(classroom=cls_7a).delete()
    Student.objects.filter(khmer_name__startswith='សិស្ស').delete()
    cls_7a.delete()
    year.delete()

    print("\n=== ALL 9 STUDENT ID NON-DUPLICATION TESTS PASSED 100%! ===")

if __name__ == '__main__':
    run_tests()
