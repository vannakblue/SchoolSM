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
from apps.teachers.models import Teacher


def test_teacher_import_and_export():
    print("=== STARTING TEACHER IMPORT & EXPORT VERIFICATION ===")

    admin_user, _ = User.objects.get_or_create(
        username='admin_import_tester',
        defaults={'role': User.Role.ADMIN, 'khmer_name': 'Admin Import Tester'}
    )

    client = Client()
    client.force_login(admin_user)

    # 1. Test Download Sample Excel Template
    res_tpl_xlsx = client.get(reverse('teacher_import_template_excel'))
    assert res_tpl_xlsx.status_code == 200
    assert 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' in res_tpl_xlsx['Content-Type']
    print("  [PASS] 1. Downloaded Teacher Import Excel Template successfully.")

    # 2. Test Download Sample CSV Template
    res_tpl_csv = client.get(reverse('teacher_import_template_csv'))
    assert res_tpl_csv.status_code == 200
    assert 'text/csv' in res_tpl_csv['Content-Type']
    print("  [PASS] 2. Downloaded Teacher Import CSV Template successfully.")

    # 3. Test Bulk Importing Teachers from Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Teachers"
    ws.append([
        "Teacher ID *", "Khmer Name *", "Latin Name *", "Gender (M/F) *",
        "DOB (DD-MM-YYYY)", "Phone *", "Email", "Specialization *",
        "Qualification", "Max Weekly Hours", "Base Salary ($)", "Status (ACTIVE/ON_LEAVE/RESIGNED)"
    ])
    ws.append(["T-TEST-001", "គ្រូ តេស្ត ១", "Teacher Test 1", "M", "12-04-1988", "012888111", "test1@school.edu.kh", "គណិតវិទ្យា", "បរិញ្ញាបត្រ", 18, 550, "ACTIVE"])
    ws.append(["T-TEST-002", "គ្រូ តេស្ត ២", "Teacher Test 2", "F", "24/09/1991", "096999222", "test2@school.edu.kh", "រូបវិទ្យា & ICT", "អនុបណ្ឌិត", 16, 600, "ACTIVE"])

    excel_buffer = io.BytesIO()
    wb.save(excel_buffer)
    excel_buffer.seek(0)

    uploaded_file = SimpleUploadedFile(
        'teachers_bulk.xlsx',
        excel_buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

    res_import = client.post(reverse('teacher_import'), {'file': uploaded_file}, follow=True)
    assert res_import.status_code == 200

    t1 = Teacher.objects.filter(teacher_id='T-TEST-001').first()
    t2 = Teacher.objects.filter(teacher_id='T-TEST-002').first()

    assert t1 is not None, "Teacher T-TEST-001 should be created"
    assert t1.khmer_name == "គ្រូ តេស្ត ១"
    assert t1.specialization == "គណិតវិទ្យា"
    assert t1.max_weekly_hours == 18
    assert str(t1.date_of_birth) == "1988-04-12"
    assert t1.user is not None, "Teacher User account should be created"
    print(f"  [PASS] 3. Imported Teacher: «{t1.khmer_name}» ({t1.teacher_id}), Specialization: {t1.specialization}, DOB: {t1.date_of_birth}, User Account: {t1.user.username}.")

    assert t2 is not None, "Teacher T-TEST-002 should be created"
    assert t2.khmer_name == "គ្រូ តេស្ត ២"
    assert t2.gender == Teacher.Gender.FEMALE
    assert t2.specialization == "រូបវិទ្យា & ICT"
    assert t2.max_weekly_hours == 16
    assert str(t2.date_of_birth) == "1991-09-24"
    print(f"  [PASS] 4. Imported Teacher: «{t2.khmer_name}» ({t2.teacher_id}), Specialization: {t2.specialization}, DOB: {t2.date_of_birth}, Max Hours: {t2.max_weekly_hours}.")

    # 4. Test Export All Teachers to Excel
    res_export = client.get(reverse('teacher_export_excel'))
    assert res_export.status_code == 200
    assert 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' in res_export['Content-Type']
    print(f"  [PASS] 5. Exported All Teachers Directory to Excel successfully ({res_export['Content-Disposition']}).")

    # Clean up test teachers
    if t1 and t1.user:
        t1.user.delete()
    if t1:
        t1.delete()
    if t2 and t2.user:
        t2.user.delete()
    if t2:
        t2.delete()

    print("=== ALL TEACHER IMPORT & EXPORT TESTS PASSED 100% ===")


if __name__ == '__main__':
    test_teacher_import_and_export()
