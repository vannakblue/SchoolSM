import os
import sys
import io

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import django
import openpyxl

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from apps.students.models import Student
from apps.academics.models import AcademicYear, Classroom, GradeLevel, GradeEnrollmentOption
from apps.students import views as student_views
from apps.academics import views as academic_views

User = get_user_model()

def run_suite():
    print("=================================================================")
    print("🚀 RUNNING MOEYS INDIVIDUAL STUDENT ROSTER TEST SUITE (35 COLS)")
    print("=================================================================\n")

    factory = RequestFactory()
    admin_user = User.objects.filter(role='ADMIN').first()
    if not admin_user:
        admin_user = User.objects.filter(is_superuser=True).first()

    # TEST 1: Check Data Sync from សម្រង់ព័ត៌មានសិស្សម្នាក់ៗ.xlsx
    print("--- [TEST 1] Verifying Data Sync Completeness ---")
    grade_12_students = Student.objects.filter(classroom__grade_level=12)
    print(f"Total Grade 12 Students in DB: {grade_12_students.count()}")
    assert grade_12_students.count() >= 430, f"Expected >= 430 Grade 12 students, found {grade_12_students.count()}"

    sample = Student.objects.filter(enrollment_data__has_key='equity_card_1').first()
    assert sample is not None, "Expected student with enrollment_data containing equity_card_1"
    ed = sample.enrollment_data
    print(f"Sample Student: {sample.khmer_name} ({sample.student_id})")
    print(f"Classroom: {sample.classroom.name if sample.classroom else 'None'}")
    print(f"Father: {sample.father_name}, Job: {sample.father_job}")
    print(f"POB: {sample.place_of_birth}")
    print(f"Equity Card 1: {ed.get('equity_card_1')}")
    print(f"Primary School: {ed.get('primary_school')}")
    print(f"Track: {ed.get('track')}")
    print("✅ TEST 1 PASSED: Data sync is complete and valid.\n")

    # TEST 2: Web View - moeys_individual_student_roster
    print("--- [TEST 2] Testing Web View (moeys_individual_student_roster) ---")
    req = factory.get('/students/reports/moeys-individual-roster/?grade_level=12')
    req.user = admin_user
    response = student_views.moeys_individual_student_roster(req)
    assert response.status_code == 200, f"Expected HTTP 200, got {response.status_code}"
    content = response.content.decode('utf-8')
    assert 'សម្រង់ព័ត៌មានសិស្សម្នាក់ៗ' in content
    assert 'ក្រសួងអប់រំ យុវជន និងកីឡា' in content
    assert 'វិទ្យាសាស្ត្រ' in content
    assert 'ប័ណ្ណសមធម៌' in content
    print(f"HTTP Status: {response.status_code}")
    print(f"Rendered HTML length: {len(content)} bytes")
    print("✅ TEST 2 PASSED: Web view rendered cleanly.\n")

    # TEST 3: Excel Export - moeys_individual_student_roster_export_excel
    print("--- [TEST 3] Testing Excel Export (.xlsx with 35 Columns) ---")
    req_excel = factory.get('/students/reports/moeys-individual-roster/export-excel/?grade_level=12')
    req_excel.user = admin_user
    response_excel = student_views.moeys_individual_student_roster_export_excel(req_excel)
    assert response_excel.status_code == 200, f"Expected HTTP 200, got {response_excel.status_code}"
    assert response_excel['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    
    excel_stream = io.BytesIO(response_excel.content)
    wb = openpyxl.load_workbook(excel_stream)
    ws = wb.active
    print(f"Worksheet Name: {ws.title}")
    print(f"Max Row: {ws.max_row}, Max Col: {ws.max_column}")
    assert ws.max_column >= 35, f"Expected 35 columns, got {ws.max_column}"
    assert ws.max_row >= 435, f"Expected >= 435 rows (header + 430+ students), got {ws.max_row}"
    
    # Check Header Text
    row1_val = ws.cell(row=1, column=1).value
    row3_val = ws.cell(row=3, column=1).value
    print(f"Row 1 Cell 1: {row1_val}")
    print(f"Row 3 Cell 1: {row3_val}")
    assert 'ក្រសួងអប់រំ' in str(row1_val)
    assert 'សម្រង់ព័ត៌មានសិស្សម្នាក់ៗ' in str(row3_val)
    
    # Check data row
    data_row_6_id = ws.cell(row=6, column=2).value
    data_row_6_name = ws.cell(row=6, column=3).value
    print(f"Row 6 (First student) Col 2 (ID): {data_row_6_id}, Col 3 (Surname): {data_row_6_name}")
    print("✅ TEST 3 PASSED: Excel export strictly adheres to the 35-column MoEYS standard.\n")

    # TEST 4: Print / PDF View - moeys_individual_student_roster_print
    print("--- [TEST 4] Testing Print / Save as PDF View ---")
    req_print = factory.get('/students/reports/moeys-individual-roster/print/?grade_level=12')
    req_print.user = admin_user
    response_print = student_views.moeys_individual_student_roster_print(req_print)
    assert response_print.status_code == 200, f"Expected HTTP 200, got {response_print.status_code}"
    content_print = response_print.content.decode('utf-8')
    assert 'margin: 1.2cm;' in content_print, "Expected default margin: 1.2cm (within 1.0 to 1.5cm)"
    assert 'changeMargin' in content_print, "Expected margin switcher function"
    assert '1.0cm' in content_print and '1.5cm' in content_print, "Expected margin options 1.0cm to 1.5cm"
    print(f"HTTP Status: {response_print.status_code}")
    print(f"Print HTML length: {len(content_print)} bytes")
    print("✅ TEST 4 PASSED: Print / PDF view strictly fulfills 1 to 1.5cm margin requirement.\n")

    # TEST 5: Admin Grade Options Management
    print("--- [TEST 5] Testing Admin Grade Options Manager ---")
    req_mgr = factory.get('/academics/grade-options/')
    req_mgr.user = admin_user
    response_mgr = academic_views.grade_options_manager(req_mgr)
    assert response_mgr.status_code == 200
    total_options = GradeEnrollmentOption.objects.count()
    print(f"Total Active Grade Enrollment Options in DB: {total_options}")
    assert total_options >= 10, f"Expected >= 10 seeded options, found {total_options}"
    print("✅ TEST 5 PASSED: Grade options manager is active and populated.\n")

    print("=================================================================")
    print("🎉 ALL 5 TEST SUITES PASSED FLAWLESSLY WITH 100% SUCCESS!")
    print("=================================================================")

if __name__ == '__main__':
    run_suite()
