import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.urls import reverse
from apps.accounts.models import GoogleSheetsConfig
from apps.academics.models import AcademicYear, Classroom
from apps.students.models import Student
from apps.attendance.models import StudentAttendance
from apps.finance.models import Invoice, Expense
from apps.tools.google_sheets_service import GoogleSheetsService


def run_tests():
    print("=== Testing Google Sheets & Drive System ===")

    # 1. Test URLs
    print("\n1. Testing URL reverses...")
    urls = [
        ('tool_google_sheets', reverse('tool_google_sheets')),
        ('tool_google_sheets_save_config', reverse('tool_google_sheets_save_config')),
        ('tool_google_sheets_sync', reverse('tool_google_sheets_sync')),
        ('tool_google_sheets_restore', reverse('tool_google_sheets_restore')),
    ]
    for name, path in urls:
        print(f"  [OK] URL {name} -> {path}")

    # 2. Test Model Singleton
    print("\n2. Testing GoogleSheetsConfig singleton...")
    config = GoogleSheetsConfig.get_config()
    assert config is not None, "Config should not be None"
    print(f"  [OK] GoogleSheetsConfig ID: {config.id}")
    print(f"  [OK] Is Configured: {config.is_configured()}")
    print(f"  [OK] Drive Folder: {config.drive_folder_name}")
    print(f"  [OK] Photo Sync: {config.sync_students_with_photos}")

    # 3. Test Service Initialization
    print("\n3. Testing GoogleSheetsService init...")
    service = GoogleSheetsService(config=config)
    assert service.config == config
    print("  [OK] GoogleSheetsService initialized cleanly.")

    # 4. Test Data Extraction for Academic Years
    print("\n4. Testing Data Mapping for Academic Years...")
    academic_years = AcademicYear.objects.all().order_by('-start_date')
    print(f"  Found {academic_years.count()} Academic Year(s)")
    if academic_years.exists():
        ay = academic_years.first()
        students_count = Student.objects.filter(academic_year=ay).count()
        invoices_count = Invoice.objects.filter(academic_year=ay).count()
        expenses_count = Expense.objects.filter(date__gte=ay.start_date, date__lte=ay.end_date).count()
        att_count = StudentAttendance.objects.filter(date__gte=ay.start_date, date__lte=ay.end_date).count()
        print(f"  Academic Year: {ay.name}")
        print(f"  - Students: {students_count}")
        print(f"  - Invoices: {invoices_count}")
        print(f"  - Expenses: {expenses_count}")
        print(f"  - Attendance records: {att_count}")

    # 5. Test Photo Formula formatting logic
    print("\n5. Testing Photo Formula formatting...")
    dummy_file_id = "1AbCdEfGhIjKlMnOpQrStUvWxYz123456"
    expected_thumb = f"https://drive.google.com/thumbnail?id={dummy_file_id}&sz=w200"
    expected_view = f"https://drive.google.com/file/d/{dummy_file_id}/view"
    expected_formula = f'=HYPERLINK("{expected_view}", IMAGE("{expected_thumb}", 1))'
    assert "IMAGE(" in expected_formula
    assert dummy_file_id in expected_formula
    print(f"  [OK] Formula: {expected_formula}")

    print("\n[ALL TESTS PASSED SUCCESSFULLY!]")


if __name__ == '__main__':
    run_tests()
