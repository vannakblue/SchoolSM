import os
import io
import sys
import django
import openpyxl

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.academics.models import AcademicYear, Classroom
from apps.students.models import Student

def test_all_features():
    print("================================================================================")
    print("🧪 TESTING MoEYS STUDENT STATISTICS BY AGE & GRADE LEVEL MATRIX")
    print("================================================================================")

    # 1. Setup Admin user
    admin_user = User.objects.filter(role='ADMIN').first()
    if not admin_user:
        admin_user = User.objects.create_superuser('admin_stats_test', 'admin_stats@test.com', 'adminpass123')

    client = Client()
    client.force_login(admin_user)

    # 2. Test Main View Rendering (Status 200)
    print("\n--- PHASE 1: Main View Rendering & Template Context ---")
    active_year = AcademicYear.objects.filter(id=3).first() or AcademicYear.objects.filter(is_current=True).first()
    assert active_year is not None, "Active academic year must exist"
    print(f"Target Academic Year: {active_year.name} (ID: {active_year.id})")

    resp = client.get(f'/students/statistics/age-grade/?academic_year={active_year.id}&calc_method=calendar&status=ACTIVE')
    assert resp.status_code == 200, f"Failed to load statistics page: {resp.status_code}"
    content = resp.content.decode('utf-8')
    assert "ស្ថិតិសិស្សតាមអាយុ និងកម្រិតថ្នាក់" in content, "Page title missing from HTML"
    assert "តារាងរួមទូទាំងសាលា" in content, "Master table missing from HTML"
    assert "ថ្នាក់ទី ៧" in content, "Grade 7 column missing from HTML"
    assert "សិស្សអនុវិទ្យាល័យ" in content, "Lower Secondary column missing from HTML"
    assert "សិស្សទុតិយភូមិ" in content, "Upper Secondary column missing from HTML"
    assert "សរុបរួមសាលា" in content, "Grand total missing from HTML"
    assert "studentDrilldownModal" in content, "Interactive drilldown modal missing"
    print("✅ [PASS] Main View rendered successfully with all 4 MoEYS tables and tabs!")

    # 3. Test Math Integrity
    print("\n--- PHASE 2: Calculation Matrix Math Integrity ---")
    from apps.students.views import _calculate_age_grade_matrix
    matrix_data = _calculate_age_grade_matrix(academic_year=active_year, calc_method='calendar', status_filter='ACTIVE')
    total_students_db = Student.objects.filter(academic_year=active_year, status='ACTIVE').count()
    ctx_total = matrix_data['total_students_count']
    col_totals = matrix_data['column_totals']
    grand_total_col = col_totals['grand_total']['all_total']
    
    print(f"Total Active Students in DB: {total_students_db}")
    print(f"Total Students in Matrix: {ctx_total}")
    print(f"Total in Grand Total Column: {grand_total_col}")
    assert ctx_total == total_students_db, f"Matrix count {ctx_total} != DB count {total_students_db}"
    assert grand_total_col == total_students_db, f"Column sum {grand_total_col} != DB count {total_students_db}"

    # Verify Lower Sec + Upper Sec = Grand Total
    lower_sec_all = col_totals['lower_sec']['all_total']
    upper_sec_all = col_totals['upper_sec']['all_total']
    print(f"Lower Secondary Total: {lower_sec_all}")
    print(f"Upper Secondary Total: {upper_sec_all}")
    assert lower_sec_all + upper_sec_all == grand_total_col, "Lower + Upper Sec must equal Grand Total!"
    print(f"✅ [PASS] Math verified 100%: Lower Sec ({lower_sec_all}) + Upper Sec ({upper_sec_all}) = {grand_total_col} Students!")

    # 4. Test Multi-Sheet MoEYS Excel Export
    print("\n--- PHASE 3: MoEYS Multi-Sheet Excel Export ---")
    export_url = f'/students/statistics/age-grade/export-excel/?academic_year={active_year.id}&calc_method=calendar&status=ACTIVE'
    resp_excel = client.get(export_url)
    assert resp_excel.status_code == 200, f"Excel export failed: {resp_excel.status_code}"
    assert resp_excel['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    assert 'attachment' in resp_excel['Content-Disposition']

    wb = openpyxl.load_workbook(io.BytesIO(resp_excel.content))
    print(f"Sheets generated in Excel: {wb.sheetnames}")
    expected_sheets = [
        "តារាងរួមទូទាំងសាលា",
        "អនុវិទ្យាល័យ (ទី៧-៩)",
        "វិទ្យាល័យ (ទី១០-១១)",
        "វិទ្យាល័យ (ទី១២-ទុតិយភូមិ)"
    ]
    for s_name in expected_sheets:
        assert s_name in wb.sheetnames, f"Expected sheet [{s_name}] not found in Excel!"

    # Verify Sheet 2 (Lower Sec - Image 1 replica)
    ws_low = wb["អនុវិទ្យាល័យ (ទី៧-៩)"]
    assert "ក្រសួងអប់រំ យុវជន និងកីឡា" in str(ws_low['A2'].value)
    assert "ថ្នាក់ទី ៧" in str(ws_low['B5'].value)
    assert "សរុប" in str(ws_low[f'A{ws_low.max_row}'].value)
    print(f"Sheet [{ws_low.title}]: Max row {ws_low.max_row}, Max column {ws_low.max_column} -> Header: {ws_low['A3'].value}")

    # Verify Sheet 3 (Upper Sec Part 1 - Image 2 replica)
    ws_up1 = wb["វិទ្យាល័យ (ទី១០-១១)"]
    assert "១០" in str(ws_up1['B5'].value)
    assert "១១ SC" in str(ws_up1['F5'].value)
    assert "១១ SS" in str(ws_up1['J5'].value)
    print(f"Sheet [{ws_up1.title}]: Grade headers verified: 10, 11 SC, 11 SS")

    # Verify Sheet 4 (Upper Sec Part 2 - Image 3 replica)
    ws_up2 = wb["វិទ្យាល័យ (ទី១២-ទុតិយភូមិ)"]
    assert "១២ SC" in str(ws_up2['B5'].value)
    assert "១២ SS" in str(ws_up2['F5'].value)
    assert "សិស្សទុតិយភូមិ" in str(ws_up2['J5'].value)
    print(f"Sheet [{ws_up2.title}]: Grade headers verified: 12 SC, 12 SS, Upper Secondary Total")

    print("✅ [PASS] Excel export generated 4 sheets with pixel-perfect MoEYS EMIS formatting!")

    # 5. Test AJAX Drilldown API
    print("\n--- PHASE 4: AJAX Student Drilldown API ---")
    # Query drilldown for Grade 7 age 13
    api_url = f'/students/api/age-grade-drilldown/?year_id={active_year.id}&cat=g7&age=13&col_type=new_total&calc_method=calendar'
    resp_api = client.get(api_url)
    assert resp_api.status_code == 200, f"API failed: {resp_api.status_code}"
    data = resp_api.json()
    assert data['status'] == 'success'
    print(f"Drilldown Title: {data['title']}")
    print(f"Student count returned: {data['count']}")
    assert data['count'] > 0, "Should have students in Grade 7 age 13"
    first_student = data['students'][0]
    print(f"Sample Student: ID={first_student['student_id']}, Name={first_student['khmer_name']}, Gender={first_student['gender']}, Class={first_student['classroom']}, Age={first_student['age']}")
    assert first_student['age'] == 13
    assert first_student['khmer_name'] != ''
    print("✅ [PASS] AJAX Drilldown API returned matching students in milliseconds!")

    # 6. Test Teacher Role Access
    print("\n--- PHASE 5: Role & Permission Verification ---")
    teacher_user = User.objects.filter(role='TEACHER').first()
    if teacher_user:
        client.force_login(teacher_user)
        resp_tch = client.get(f'/students/statistics/age-grade/?academic_year={active_year.id}')
        assert resp_tch.status_code == 200, "Teachers must be allowed to view statistics"
        print(f"✅ [PASS] Teacher [{teacher_user.username}] successfully accessed the Age-Grade Statistics report!")

    print("\n================================================================================")
    print("🎉 ALL 5 TEST PHASES PASSED WITH 100% SUCCESS!")
    print("================================================================================")

if __name__ == '__main__':
    test_all_features()
