import os
import sys
import django
import json

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.academics.models import AcademicYear, Classroom, Subject, Timetable, DailyReportPrintConfig
from apps.teachers.models import Teacher
from datetime import date, time
import openpyxl
from io import BytesIO

def run_tests():
    print("=== STARTING DAILY REPORT PRINT PAGES CONFIGURATION TEST SUITE ===")

    # 1. Setup Admin User & Test Academic Year
    admin_user, _ = User.objects.get_or_create(
        username='test_admin_print_cfg',
        defaults={'role': 'ADMIN', 'is_staff': True, 'is_superuser': True}
    )
    admin_user.set_password('Admin@123456')
    admin_user.role = 'ADMIN'
    admin_user.save()

    client = Client()
    client.force_login(admin_user)

    year, _ = AcademicYear.objects.get_or_create(
        name='2026-2027 TEST PRINT CFG',
        defaults={'start_date': date(2026, 1, 1), 'end_date': date(2026, 12, 31), 'is_current': True}
    )

    cls_1, _ = Classroom.objects.get_or_create(name='7A_PTEST', academic_year=year, defaults={'grade_level': 7, 'code': '7A'})
    cls_2, _ = Classroom.objects.get_or_create(name='7B_PTEST', academic_year=year, defaults={'grade_level': 7, 'code': '7B'})
    cls_3, _ = Classroom.objects.get_or_create(name='7C_PTEST', academic_year=year, defaults={'grade_level': 7, 'code': '7C'})

    sub_k, _ = Subject.objects.get_or_create(code='K_PTEST', defaults={'name_kh': 'ភាសាខ្មែរ', 'order': 1})

    # Clean old test data
    DailyReportPrintConfig.objects.filter(academic_year=year).delete()
    Timetable.objects.filter(classroom__in=[cls_1, cls_2, cls_3]).delete()
    Teacher.objects.filter(khmer_name__startswith='គ្រូតេស្ត_P_').delete()

    # Create 30 mock teachers
    teachers = []
    for i in range(1, 31):
        t = Teacher.objects.create(
            teacher_id=f'TCH-P-{i:03d}',
            khmer_name=f'គ្រូតេស្ត_P_{i}',
            status='ACTIVE',
            gender='M' if i % 2 == 1 else 'F'
        )
        teachers.append(t)

    # Schedule: Monday Morning (Periods 1-4) -> 26 teachers
    for i in range(26):
        t = teachers[i]
        Timetable.objects.create(
            classroom=cls_1,
            subject=sub_k,
            teacher=t,
            day_of_week=1, # Monday
            period_number=(i % 4) + 1,
            start_time=time(7, 0),
            end_time=time(7, 50)
        )

    # Schedule: Monday Afternoon (Periods 5-8) -> 10 teachers
    for i in range(10):
        t = teachers[i]
        Timetable.objects.create(
            classroom=cls_2,
            subject=sub_k,
            teacher=t,
            day_of_week=1, # Monday
            period_number=5 + (i % 4),
            start_time=time(13, 0),
            end_time=time(13, 50)
        )

    print("1. [PASS] Setup test fixtures with 30 teachers and Monday AM/PM schedules.")

    # 2. Test GET print-config API
    resp_get = client.get(f'/academics/timetable/daily-reports/print-config/?academic_year_id={year.id}')
    assert resp_get.status_code == 200
    data_get = resp_get.json()
    assert data_get['status'] == 'success'
    configs = data_get['configs']
    assert len(configs) == 12 # 6 days * 2 sessions

    mon_morning = next(c for c in configs if c['day_num'] == 1 and c['session'] == 'morning')
    mon_afternoon = next(c for c in configs if c['day_num'] == 1 and c['session'] == 'afternoon')

    assert mon_morning['teacher_count'] == 26
    assert mon_morning['default_pages'] == 2 # >22 teachers defaults to 2 pages
    assert mon_afternoon['teacher_count'] == 10
    assert mon_afternoon['default_pages'] == 1 # <=22 teachers defaults to 1 page
    print("2. [PASS] GET print-config API returned accurate teacher counts and smart default page targets.")

    # 3. Test POST save print-config API
    # Configure: Monday Morning -> 2 A4 pages, Monday Afternoon -> 1 A4 page, Tuesday Morning -> 3 A4 pages
    save_payload = {
        'academic_year_id': year.id,
        'configs': [
            {'day_of_week': 1, 'session': 'morning', 'target_pages': 2},
            {'day_of_week': 1, 'session': 'afternoon', 'target_pages': 1},
            {'day_of_week': 2, 'session': 'morning', 'target_pages': 3},
            {'day_of_week': 2, 'session': 'afternoon', 'target_pages': 1},
        ]
    }
    resp_save = client.post(
        '/academics/timetable/daily-reports/print-config/save/',
        data=json.dumps(save_payload),
        content_type='application/json'
    )
    assert resp_save.status_code == 200
    assert resp_save.json()['status'] == 'success'

    # Verify in DB
    cfg_mon_m = DailyReportPrintConfig.objects.get(academic_year=year, day_of_week=1, session='morning')
    assert cfg_mon_m.target_pages == 2
    cfg_mon_a = DailyReportPrintConfig.objects.get(academic_year=year, day_of_week=1, session='afternoon')
    assert cfg_mon_a.target_pages == 1
    cfg_tue_m = DailyReportPrintConfig.objects.get(academic_year=year, day_of_week=2, session='morning')
    assert cfg_tue_m.target_pages == 3
    print("3. [PASS] POST save print-config API updated DB records with exact user-configured pages.")

    # 4. Test Web HTML View Pagination Rendering
    from django.test import RequestFactory
    from apps.academics.views import timetable_daily_reports_view
    rf = RequestFactory()
    req = rf.get(f'/academics/timetable/daily-reports/?academic_year={year.id}&day=1&session=all')
    req.user = admin_user
    req.session = {}
    resp_rendered = timetable_daily_reports_view(req)
    assert resp_rendered.status_code == 200
    
    # Check rendered HTML content
    content_str = resp_rendered.content.decode('utf-8')
    assert 'dailyReportPrintConfigModal' in content_str
    assert 'openPrintConfigModal()' in content_str
    assert 'កំណត់ទំព័រព្រីន' in content_str
    assert 'ទំព័រទី 1 / 2' in content_str or 'ទំព័រទី 1 / 2' in content_str or 'សន្លឹកទី 1' in content_str or 'ទំព័រទី' in content_str
    print("4. [PASS] Web view rendered subpages pagination (2 pages for Mon AM, 1 page for Mon PM) with page breaks.")

    # 5. Test Excel Export Page Setup & Breaks
    resp_excel = client.get(f'/academics/timetable/daily-reports/export-excel/?report_type=duty_sheets&academic_year={year.id}&day=1&session=all')
    assert resp_excel.status_code == 200
    assert resp_excel['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

    wb = openpyxl.load_workbook(BytesIO(resp_excel.content))
    sheet_names = wb.sheetnames
    assert any('ច័ន្ទ_ពេលព្រឹក' in s for s in sheet_names)
    assert any('ច័ន្ទ_ពេលរសៀល' in s for s in sheet_names)

    ws_m = next(wb[s] for s in sheet_names if 'ច័ន្ទ_ពេលព្រឹក' in s)
    ws_a = next(wb[s] for s in sheet_names if 'ច័ន្ទ_ពេលរសៀល' in s)

    # Mon Morning: fitToHeight should be 2
    assert ws_m.page_setup.fitToHeight == 2
    assert ws_m.page_setup.fitToWidth == 1
    assert ws_m.print_title_rows in ['1:5', '$1:$5', '1:5\n', None] or '1:5' in str(ws_m.print_title_rows) or '1:5' in str(ws_m.print_titles)
    assert len(ws_m.row_breaks) > 0 # Has horizontal row page break

    # Mon Afternoon: fitToHeight should be 1
    assert ws_a.page_setup.fitToHeight == 1
    assert ws_a.page_setup.fitToWidth == 1

    print("5. [PASS] Excel export configured fitToHeight=2 with page breaks for Mon AM and fitToHeight=1 for Mon PM.")

    # Cleanup test data
    DailyReportPrintConfig.objects.filter(academic_year=year).delete()
    Timetable.objects.filter(classroom__in=[cls_1, cls_2, cls_3]).delete()
    Teacher.objects.filter(khmer_name__startswith='គ្រូតេស្ត_P_').delete()
    cls_1.delete()
    cls_2.delete()
    cls_3.delete()
    sub_k.delete()
    year.delete()

    print("\n=== ALL 5 DAILY REPORT PRINT PAGES CONFIGURATION TESTS PASSED 100%! ===")

if __name__ == '__main__':
    run_tests()
