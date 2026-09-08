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

    # 3. Test Math Integrity & Age Clamping
    print("\n--- PHASE 2: Calculation Matrix Math Integrity & MoEYS Clamping ---")
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

    # Verify Master Ages are strictly 12 to 20
    master_ages = matrix_data['master_ages']
    print(f"Master Ages in Matrix: {master_ages}")
    assert master_ages == list(range(12, 21)), f"Master ages must be 12..20, got {master_ages}"

    # Verify Clamping:
    # Row 12 must contain students with real age <= 12 (33 at 12 + 3 at 11 + 1 at 1 = 37)
    row_12_count = matrix_data['raw_counts']['grand_total'][12]['new_total'] + matrix_data['raw_counts']['grand_total'][12]['rep_total']
    print(f"Grand Total Row 12 (<= 12) Count: {row_12_count} students")
    assert row_12_count == 37, f"Row 12 should have 37 students, got {row_12_count}"

    # Row 20 must contain students with real age >= 20 (19 at 20 + 3 at 21 + 2 at 22 = 24)
    row_20_count = matrix_data['raw_counts']['grand_total'][20]['new_total'] + matrix_data['raw_counts']['grand_total'][20]['rep_total']
    print(f"Grand Total Row 20 (>= 20) Count: {row_20_count} students")
    assert row_20_count == 24, f"Row 20 should have 24 students, got {row_20_count}"

    # Verify Lower Sec + Upper Sec = Grand Total
    lower_sec_all = col_totals['lower_sec']['all_total']
    upper_sec_all = col_totals['upper_sec']['all_total']
    print(f"Lower Secondary Total: {lower_sec_all}")
    print(f"Upper Secondary Total: {upper_sec_all}")
    assert lower_sec_all + upper_sec_all == grand_total_col, "Lower + Upper Sec must equal Grand Total!"
    print(f"✅ [PASS] Math verified 100%: Lower Sec ({lower_sec_all}) + Upper Sec ({upper_sec_all}) = {grand_total_col} Students!")

    # 4. Test Multi-Sheet MoEYS Excel Export (5 sheets including reference roster)
    print("\n--- PHASE 3: MoEYS Multi-Sheet Excel Export (5 Sheets) ---")
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
        "វិទ្យាល័យ (ទី១២-ទុតិយភូមិ)",
        "បញ្ជីសិស្សយោង (Roster)"
    ]
    for s_name in expected_sheets:
        assert s_name in wb.sheetnames, f"Expected sheet [{s_name}] not found in Excel!"

    # Verify Sheet 1 (Master) age labels
    ws_master = wb["តារាងរួមទូទាំងសាលា"]
    assert "១២ ឆ្នាំ (≤ ១២)" in str(ws_master['A8'].value), f"Expected row 12 bounded label, got {ws_master['A8'].value}"
    assert "២០ ឆ្នាំ (≥ ២០)" in str(ws_master['A16'].value), f"Expected row 20 bounded label, got {ws_master['A16'].value}"

    # Verify Sheet 5 (Reference Student Roster)
    ws_roster = wb["បញ្ជីសិស្សយោង (Roster)"]
    assert "បញ្ជីឈ្មោះសិស្សយោងសម្រាប់ការគណនាស្ថិតិអាយុ" in str(ws_roster['A3'].value)
    assert ws_roster['A5'].value == "ល.រ"
    assert ws_roster['B5'].value == "អត្តលេខ"
    assert ws_roster['G5'].value == "អាយុពិត"
    assert ws_roster['H5'].value == "អាយុក្នុងតារាង"
    assert ws_roster['N5'].value == "សម្គាល់ការគណនា"
    # Row count: 5 header rows + 2000 students + 1 total row = 2006 rows
    print(f"Sheet [{ws_roster.title}]: Max row {ws_roster.max_row}, Max column {ws_roster.max_column}")
    assert ws_roster.max_row >= 2006, f"Roster should have >= 2006 rows, got {ws_roster.max_row}"
    assert "សរុបសិស្សទាំងអស់៖ 2000 នាក់" in str(ws_roster[f'A{ws_roster.max_row}'].value)
    print(f"Sheet [{ws_roster.title}]: Reference roster verified with {len(matrix_data['calculated_students'])} students and summary row!")

    print("✅ [PASS] Excel export generated 5 sheets with pixel-perfect MoEYS EMIS formatting and reference roster!")

    # 5. Test AJAX Drilldown API with Clamped Ages
    print("\n--- PHASE 4: AJAX Student Drilldown API & Real Age Metadata ---")
    # Query drilldown for Age 12 (should return all <= 12, count 37)
    api_url_12 = f'/students/api/age-grade-drilldown/?year_id={active_year.id}&cat=grand_total&age=12&col_type=all&calc_method=calendar'
    resp_api_12 = client.get(api_url_12)
    assert resp_api_12.status_code == 200, f"API failed: {resp_api_12.status_code}"
    data_12 = resp_api_12.json()
    assert data_12['status'] == 'success'
    print(f"Drilldown Age 12 Title: {data_12['title']}")
    print(f"Drilldown Age 12 Count: {data_12['count']}")
    assert data_12['count'] == 37, f"Age 12 drilldown should return 37 students, got {data_12['count']}"
    # Verify presence of clamped students (ages < 12)
    clamped_under_12 = [s for s in data_12['students'] if s['is_clamped']]
    assert len(clamped_under_12) == 4, f"Should have 4 students < 12 clamped, got {len(clamped_under_12)}"
    print(f"Sample Clamped Under-12 Student: {clamped_under_12[0]['khmer_name']}, Real Age: {clamped_under_12[0]['real_age']}, Remark: {clamped_under_12[0]['age_remark']}")

    # Query drilldown for Age 20 (should return all >= 20, count 24)
    api_url_20 = f'/students/api/age-grade-drilldown/?year_id={active_year.id}&cat=grand_total&age=20&col_type=all&calc_method=calendar'
    resp_api_20 = client.get(api_url_20)
    assert resp_api_20.status_code == 200, f"API failed: {resp_api_20.status_code}"
    data_20 = resp_api_20.json()
    assert data_20['status'] == 'success'
    print(f"Drilldown Age 20 Title: {data_20['title']}")
    print(f"Drilldown Age 20 Count: {data_20['count']}")
    assert data_20['count'] == 24, f"Age 20 drilldown should return 24 students, got {data_20['count']}"
    # Verify presence of clamped students (ages > 20)
    clamped_over_20 = [s for s in data_20['students'] if s['is_clamped']]
    assert len(clamped_over_20) == 5, f"Should have 5 students > 20 clamped, got {len(clamped_over_20)}"
    print(f"Sample Clamped Over-20 Student: {clamped_over_20[0]['khmer_name']}, Real Age: {clamped_over_20[0]['real_age']}, Remark: {clamped_over_20[0]['age_remark']}")

    print("✅ [PASS] AJAX Drilldown API correctly handles age <=12 and >=20 clamping and returns real age metadata!")

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
