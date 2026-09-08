"""
Comprehensive Automated Tests for Customizable MoEYS Student Age Roster Reports.
Validates:
1. Web view for Format A (Image 1 replica: Grade split + Age column, Age 13-14)
2. Web view for Format B (Image 2 replica: Class + 4-part Address hierarchy, Age 15+)
3. Custom filter combinations (Grade, Gender, Mode, Range, Custom Title & School Name)
4. Excel export (.xlsx) generation and column structure for Format A & Format B
5. Dedicated Print / PDF template rendering
"""

import os
import sys
import io
if sys.stdout and sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

import openpyxl
from django.test import RequestFactory
from django.urls import reverse
from apps.accounts.models import User
from apps.academics.models import AcademicYear, Classroom
from apps.students.models import Student
from apps.students.views import (
    student_age_custom_roster,
    student_age_custom_roster_export_excel,
    student_age_custom_roster_print,
    _format_khmer_dob_short,
    _split_classroom,
    _parse_student_address,
)

def run_tests():
    print("=" * 70)
    print("Starting MoEYS Customizable Student Age Roster Reports Test Suite...")
    print("=" * 70)

    factory = RequestFactory()

    # Retrieve or create test admin user
    user = User.objects.filter(role='ADMIN').first()
    if not user:
        user = User.objects.filter(is_superuser=True).first()
    if not user:
        user = User.objects.create_user(username='test_admin_roster', role='ADMIN', is_staff=True)

    # -------------------------------------------------------------------------
    # Phase 1: Unit Test Helpers
    # -------------------------------------------------------------------------
    print("\n[Phase 1] Testing Helper Functions...")
    from datetime import date
    test_dob = date(2013, 1, 24)
    dob_kh = _format_khmer_dob_short(test_dob)
    assert dob_kh == '២៤/០១/១៣', f"Expected '២៤/០១/១៣', got '{dob_kh}'"
    print("  ✓ _format_khmer_dob_short correctly formatted 2013-01-24 as '២៤/០១/១៣'")

    test_dob2 = date(2010, 7, 28)
    dob_kh2 = _format_khmer_dob_short(test_dob2)
    assert dob_kh2 == '២៨/០៧/១០', f"Expected '២៨/០៧/១០', got '{dob_kh2}'"
    print("  ✓ _format_khmer_dob_short correctly formatted 2010-07-28 as '២៨/០៧/១០'")

    # Test address resolution for known sample student 26020
    addr_tuple = _parse_student_address('', '26020')
    # Should resolve to Cheung Koeub / Kandal Stung
    assert addr_tuple[2] == 'កណ្ដាលស្ទឹង', f"Expected district 'កណ្ដាលស្ទឹង', got '{addr_tuple[2]}'"
    assert addr_tuple[3] == 'កណ្ដាល', f"Expected province 'កណ្ដាល', got '{addr_tuple[3]}'"
    print(f"  ✓ _parse_student_address for ID 26020: {addr_tuple}")

    # -------------------------------------------------------------------------
    # Phase 2: Format A Web View (Screenshot 1 Replica: Age 13-14)
    # -------------------------------------------------------------------------
    print("\n[Phase 2] Testing Format A Web View (Age 13 to 14)...")
    req = factory.get(reverse('student_age_custom_roster'), {
        'format': 'format_a',
        'mode': 'range',
        'min_age': 13,
        'max_age': 14,
    })
    req.user = user
    resp = student_age_custom_roster(req)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    content = resp.content.decode('utf-8')
    assert 'បញ្ជីសម្រង់ឈ្មោះសិស្សអាយុ ១៣ ដល់ ១៤ ឆ្នាំ' in content, "Missing auto title for Age 13 to 14"
    assert 'ថ្នាក់ទី' in content, "Missing 'ថ្នាក់ទី' header"
    assert 'អាយុ' in content, "Missing 'អាយុ' header"
    assert 'ព្រះរាជាណាចក្រកម្ពុជា' in content, "Missing official MoEYS header"
    assert 'ជាតិ សាសនា ព្រះមហាក្សត្រ' in content, "Missing official MoEYS motto"
    print("  ✓ Format A loaded with HTTP 200 and correct Khmer headers and title")

    # -------------------------------------------------------------------------
    # Phase 3: Format B Web View (Screenshot 2 Replica: Age 15+)
    # -------------------------------------------------------------------------
    print("\n[Phase 3] Testing Format B Web View (Age 15+ with Address hierarchy)...")
    req_b = factory.get(reverse('student_age_custom_roster'), {
        'format': 'format_b',
        'mode': 'threshold',
        'min_age': 15,
    })
    req_b.user = user
    resp_b = student_age_custom_roster(req_b)
    assert resp_b.status_code == 200, f"Expected 200, got {resp_b.status_code}"
    content_b = resp_b.content.decode('utf-8')
    assert 'បញ្ជីសម្រង់សិស្សអាយុ ១៥ ឆ្នាំឡើង' in content_b, "Missing auto title for Age 15+"
    assert 'អាសយដ្ឋានបច្ចុប្បន្ន' in content_b, "Missing 'អាសយដ្ឋានបច្ចុប្បន្ន' header"
    assert 'ភូមិ' in content_b, "Missing 'ភូមិ' subheader"
    assert 'ឃុំ/សង្កាត់' in content_b, "Missing 'ឃុំ/សង្កាត់' subheader"
    assert 'ស្រុក/ខណ្ឌ' in content_b, "Missing 'ស្រុក/ខណ្ឌ' subheader"
    assert 'ខេត្ត/ក្រុង' in content_b, "Missing 'ខេត្ត/ក្រុង' subheader"
    print("  ✓ Format B loaded with HTTP 200 and complete 4-part address subheaders")

    # -------------------------------------------------------------------------
    # Phase 4: Custom Title & Custom School Name
    # -------------------------------------------------------------------------
    print("\n[Phase 4] Testing Customization (User-defined Title & School Name)...")
    custom_title_text = "បញ្ជីសម្រង់សិស្សឆ្នើមថ្នាក់ទី១០"
    custom_school_text = "វិទ្យាល័យ គំរូក្រុងតាខ្មៅ"
    req_c = factory.get(reverse('student_age_custom_roster'), {
        'format': 'format_b',
        'mode': 'range',
        'min_age': 14,
        'max_age': 16,
        'custom_title': custom_title_text,
        'school_name': custom_school_text,
    })
    req_c.user = user
    resp_c = student_age_custom_roster(req_c)
    assert resp_c.status_code == 200
    content_c = resp_c.content.decode('utf-8')
    assert custom_title_text in content_c, "Custom title did not render"
    assert custom_school_text in content_c, "Custom school name did not render"
    print("  ✓ User-defined custom title and school name rendered perfectly")

    # -------------------------------------------------------------------------
    # Phase 5: Excel Export (.xlsx) for Format A & Format B
    # -------------------------------------------------------------------------
    print("\n[Phase 5] Testing Excel Export (.xlsx)...")
    # 5.1 Format A Excel
    req_xl_a = factory.get(reverse('student_age_custom_roster_export_excel'), {
        'format': 'format_a',
        'mode': 'range',
        'min_age': 13,
        'max_age': 14,
    })
    req_xl_a.user = user
    resp_xl_a = student_age_custom_roster_export_excel(req_xl_a)
    assert resp_xl_a.status_code == 200
    assert 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' in resp_xl_a['Content-Type']
    assert 'moeys_student_roster_format_a_13_14.xlsx' in resp_xl_a['Content-Disposition']

    wb_a = openpyxl.load_workbook(io.BytesIO(resp_xl_a.content))
    ws_a = wb_a.active
    assert ws_a['A5'].value == 'បញ្ជីសម្រង់ឈ្មោះសិស្សអាយុ ១៣ ដល់ ១៤ ឆ្នាំ', f"Title cell incorrect: {ws_a['A5'].value}"
    assert ws_a['A7'].value == 'លរ'
    assert ws_a['B7'].value == 'អត្តលេខ'
    assert ws_a['C7'].value == 'គោត្តនាម និងនាម'
    assert ws_a['F7'].value == 'ថ្នាក់ទី'
    assert ws_a['H7'].value == 'អាយុ'
    print(f"  ✓ Format A Excel export verified: title '{ws_a['A5'].value}', total rows: {ws_a.max_row}")

    # 5.2 Format B Excel
    req_xl_b = factory.get(reverse('student_age_custom_roster_export_excel'), {
        'format': 'format_b',
        'mode': 'threshold',
        'min_age': 15,
    })
    req_xl_b.user = user
    resp_xl_b = student_age_custom_roster_export_excel(req_xl_b)
    assert resp_xl_b.status_code == 200
    assert 'moeys_student_roster_format_b_15_' in resp_xl_b['Content-Disposition']

    wb_b = openpyxl.load_workbook(io.BytesIO(resp_xl_b.content))
    ws_b = wb_b.active
    assert ws_b['A5'].value == 'បញ្ជីសម្រង់សិស្សអាយុ ១៥ ឆ្នាំឡើង', f"Title cell incorrect: {ws_b['A5'].value}"
    assert ws_b['G7'].value == 'អាសយដ្ឋានបច្ចុប្បន្ន'
    assert ws_b['G8'].value == 'ភូមិ'
    assert ws_b['H8'].value == 'ឃុំ/សង្កាត់'
    assert ws_b['I8'].value == 'ស្រុក/ខណ្ឌ'
    assert ws_b['J8'].value == 'ខេត្ត/ក្រុង'
    print(f"  ✓ Format B Excel export verified: title '{ws_b['A5'].value}', 2-tier headers present, total rows: {ws_b.max_row}")

    # -------------------------------------------------------------------------
    # Phase 6: Print / PDF Template
    # -------------------------------------------------------------------------
    print("\n[Phase 6] Testing Print / PDF View...")
    req_pr = factory.get(reverse('student_age_custom_roster_print'), {
        'format': 'format_a',
        'mode': 'range',
        'min_age': 13,
        'max_age': 14,
    })
    req_pr.user = user
    resp_pr = student_age_custom_roster_print(req_pr)
    assert resp_pr.status_code == 200
    pr_content = resp_pr.content.decode('utf-8')
    assert '@page' in pr_content, "Missing @page stylesheet for printing"
    assert 'បញ្ឈប់បញ្ជីត្រឹមលេខរៀងទី' in pr_content, "Missing stop line text"
    assert 'នាយកសាលា' in pr_content, "Missing principal signature block"
    print("  ✓ Dedicated print sheet verified with clean @media print styles and official signatures")

    print("\n" + "=" * 70)
    print("ALL 6 PHASES OF TEST SUITE PASSED SUCCESSFULLY! (100% OK)")
    print("=" * 70)

if __name__ == '__main__':
    run_tests()
