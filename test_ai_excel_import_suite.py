import os
import sys
import io
import django
import openpyxl

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.accounts.models import User
from apps.students.models import Student
from apps.teachers.models import Teacher
from apps.academics.models import AcademicYear, Classroom
from apps.tools.excel_ai_mapper import (
    extract_sheet_rows_and_headers,
    detect_column_mapping_with_ai,
    parse_date_smart,
    parse_gender_smart,
    convert_khmer_digits,
    normalize_row_data
)


def test_ai_excel_import_capabilities():
    print("=== TESTING AI EXCEL SMART MAPPING & IMPORTER FOR STUDENTS & TEACHERS ===")

    # Setup admin user
    admin_user, _ = User.objects.get_or_create(
        username='admin_ai_excel_tester',
        defaults={'role': User.Role.ADMIN, 'khmer_name': 'Admin AI Tester'}
    )

    client = Client()
    client.force_login(admin_user)

    # 1. Test unit normalizers (Khmer digits, dates, gender)
    assert convert_khmer_digits('១៥/០៥/២០០៩') == '15/05/2009'
    assert str(parse_date_smart('១៥ ឧសភា ២០០៩')) == '2009-05-15'
    assert str(parse_date_smart('15/05/2009')) == '2009-05-15'
    assert parse_gender_smart('ស្រី') == 'F'
    assert parse_gender_smart('ប្រុស') == 'M'
    assert parse_gender_smart('ស') == 'F'
    print("  [PASS] 1. Khmer digit conversion, smart date parsing, and gender normalizer verified.")

    # 2. Test Non-Standard Student Excel File
    # Columns in arbitrary order, different Khmer names, Khmer digits in DOB
    wb_s = openpyxl.Workbook()
    ws_s = wb_s.active
    ws_s.title = "StudentList2026"
    # Preamble rows simulating ministry document
    ws_s.append(["ព្រះរាជាណាចក្រកម្ពុជា", "", ""])
    ws_s.append(["ជាតិ សាសនា ព្រះមហាក្សត្រ", "", ""])
    ws_s.append(["បញ្ជីរាយនាមសិស្សថ្នាក់ទី១០ (ទម្រង់ក្រៅស្តង់ដារ)", "", ""])
    # Real Header row (Column order: No, Full Name, Class, Gender, DOB with Khmer numbers, Phone)
    ws_s.append(["ល.រ", "ឈ្មោះសិស្ស", "ថ្នាក់", "ភេទ", "ថ្ងៃខែឆ្នាំកំណើត", "លេខទូរស័ព្ទ"])
    ws_s.append([1, "ជា សុភ័ក្រ", "10-SCI", "ប្រុស", "១២/០៤/២០០៨", "012345678"])
    ws_s.append([2, "គង់ ចិន្តា", "10-SCI", "ស្រី", "២៥-០៨-២០០៨", "096999888"])

    buf_s = io.BytesIO()
    wb_s.save(buf_s)
    buf_s.seek(0)

    up_s = SimpleUploadedFile('students_custom_format.xlsx', buf_s.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    # Test Student AI Preview Endpoint
    res_s_prev = client.post(reverse('student_import_ai_preview'), {'file': up_s})
    assert res_s_prev.status_code == 200
    data_s_prev = res_s_prev.json()
    assert data_s_prev['success'] is True
    assert 'ឈ្មោះសិស្ស' in data_s_prev['headers']
    print(f"  [PASS] 2. Student AI Preview detected {len(data_s_prev['headers'])} headers: {data_s_prev['headers']}")

    # Test Student Import with Auto-AI Mapping
    buf_s.seek(0)
    up_s_import = SimpleUploadedFile('students_custom_format.xlsx', buf_s.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    res_s_import = client.post(reverse('student_import'), {'file': up_s_import}, follow=True)
    assert res_s_import.status_code == 200

    s1 = Student.objects.filter(khmer_name="ជា សុភ័ក្រ").first()
    s2 = Student.objects.filter(khmer_name="គង់ ចិន្តា").first()
    assert s1 is not None, "Student 1 should be created via AI mapping"
    assert s2 is not None, "Student 2 should be created via AI mapping"
    assert s1.gender == Student.Gender.MALE
    assert s2.gender == Student.Gender.FEMALE
    assert str(s1.date_of_birth) == "2008-04-12"
    assert str(s2.date_of_birth) == "2008-08-25"
    print(f"  [PASS] 3. Student Auto-Import created: «{s1.khmer_name}» (DOB: {s1.date_of_birth}, Gender: {s1.gender}) & «{s2.khmer_name}» (DOB: {s2.date_of_birth}, Gender: {s2.gender}).")

    # 3. Test Non-Standard Teacher Excel File
    # Custom headers, no Teacher ID, different column order: [ឈ្មោះគ្រូ, ឯកទេសបង្រៀន, ភេទ, ថ្ងៃកំណើត, លេខទូរស័ព្ទ, ប្រាក់ខែ]
    wb_t = openpyxl.Workbook()
    ws_t = wb_t.active
    ws_t.title = "TeacherList"
    ws_t.append(["ឈ្មោះគ្រូ", "ឯកទេសបង្រៀន", "ភេទ", "ថ្ងៃខែឆ្នាំកំណើត", "លេខទូរស័ព្ទ", "ប្រាក់ខែ"])
    ws_t.append(["ហេង វិសាល", "គីមីវិទ្យា", "ប្រុស", "18-06-1987", "012777666", "600"])
    ws_t.append(["លឹម ស្រីមុំ", "ជីវវិទ្យា", "ស្រី", "22-11-1992", "097111222", "550"])

    buf_t = io.BytesIO()
    wb_t.save(buf_t)
    buf_t.seek(0)

    up_t = SimpleUploadedFile('teachers_custom_format.xlsx', buf_t.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    # Test Teacher AI Preview Endpoint
    res_t_prev = client.post(reverse('teacher_import_ai_preview'), {'file': up_t})
    assert res_t_prev.status_code == 200
    data_t_prev = res_t_prev.json()
    assert data_t_prev['success'] is True
    assert 'ឈ្មោះគ្រូ' in data_t_prev['headers']
    print(f"  [PASS] 4. Teacher AI Preview detected {len(data_t_prev['headers'])} headers: {data_t_prev['headers']}")

    # Test Teacher Import with Auto-AI Mapping
    buf_t.seek(0)
    up_t_import = SimpleUploadedFile('teachers_custom_format.xlsx', buf_t.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    res_t_import = client.post(reverse('teacher_import'), {'file': up_t_import}, follow=True)
    assert res_t_import.status_code == 200

    t1 = Teacher.objects.filter(khmer_name="ហេង វិសាល").first()
    t2 = Teacher.objects.filter(khmer_name="លឹម ស្រីមុំ").first()
    assert t1 is not None, "Teacher 1 should be created via AI mapping"
    assert t2 is not None, "Teacher 2 should be created via AI mapping"
    assert t1.specialization == "គីមីវិទ្យា"
    assert t2.specialization == "ជីវវិទ្យា"
    assert t1.gender == Teacher.Gender.MALE
    assert t2.gender == Teacher.Gender.FEMALE
    assert t1.teacher_id.startswith('T-')
    assert t1.user is not None
    print(f"  [PASS] 5. Teacher Auto-Import created: «{t1.khmer_name}» ({t1.teacher_id}, Spec: {t1.specialization}, Salary: ${t1.base_salary}, User: {t1.user.username}) & «{t2.khmer_name}» ({t2.teacher_id}).")

    # Cleanup test data
    if s1: s1.delete()
    if s2: s2.delete()
    if t1 and t1.user: t1.user.delete()
    if t1: t1.delete()
    if t2 and t2.user: t2.user.delete()
    if t2: t2.delete()

    print("=== ALL AI EXCEL MAPPING & IMPORTER TESTS PASSED SUCCESSFULLY! ===")


if __name__ == '__main__':
    test_ai_excel_import_capabilities()
