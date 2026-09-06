import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
import django
django.setup()

from django.test import Client
from apps.accounts.models import User, SchoolProfile
from django.urls import reverse

def run_tests():
    print("==================================================")
    print("TEST SUITE: THEME, FONTS & COLOR CUSTOMIZATION")
    print("==================================================")

    client = Client()
    admin_user = User.objects.filter(is_superuser=True).first() or User.objects.filter(role='ADMIN').first()
    if not admin_user:
        admin_user = User.objects.create_superuser('admin_theme_tester', 'theme@schoolsm.kh', 'pass123')
    client.force_login(admin_user)

    school = SchoolProfile.get_settings()
    print(f"Initial State: Font={school.display_font}, ReportFont={school.report_header_font}, PrimaryColor={school.theme_primary_color}")

    # TEST 1: GET School Profile Settings Page
    print("\n[TEST 1] Accessing School Profile Settings view...")
    res = client.get(reverse('school_profile_settings'))
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    content = res.content.decode('utf-8')
    assert "ពុម្ពអក្សរ & រចនាប័ទ្មពណ៌" in content, "Theme & Typography tab should exist in settings template"
    assert "themeLivePreviewCard" in content, "Live preview card should exist"
    print(" -> School Profile settings page rendered successfully with Theme tab.")

    # TEST 2: POST update School Profile with new font & custom colors
    print("\n[TEST 2] Updating Theme to Khmer OS Siemreap & Emerald Green Theme...")
    post_data = {
        'name_kh': school.name_kh,
        'name_en': school.name_en,
        'short_name': school.short_name,
        'school_code': school.school_code,
        'school_type': school.school_type,
        'institution_type': school.institution_type,
        'education_levels': school.education_levels,
        'date_format': school.date_format,
        'time_format': school.time_format,
        'motto': school.motto,
        'student_id_pattern': school.student_id_pattern,
        'student_id_prefix': school.student_id_prefix,
        'student_id_custom_template': school.student_id_custom_template,
        'student_id_digits': school.student_id_digits,
        'ministry_name': school.ministry_name,
        'poe_name': school.poe_name,
        'province': school.province,
        'district': school.district,
        'commune': school.commune,
        'street_address': school.street_address,
        'principal_name': school.principal_name,
        'phone': school.phone,
        'email': school.email,
        # The new theme customization fields:
        'display_font': 'Khmer OS Siemreap',
        'report_header_font': 'Moul',
        'theme_primary_color': '#059669',
        'header_bg_color': '#064e3b',
        'footer_bg_color': '#022c22',
        'body_bg_color': '#f0fdf4',
    }
    res = client.post(reverse('school_profile_settings'), data=post_data, follow=True)
    assert res.status_code == 200, f"Expected 200 on post, got {res.status_code}"

    school.refresh_from_db()
    assert school.display_font == 'Khmer OS Siemreap', f"Expected Khmer OS Siemreap, got {school.display_font}"
    assert school.report_header_font == 'Moul', f"Expected Moul, got {school.report_header_font}"
    assert school.theme_primary_color == '#059669', f"Expected #059669, got {school.theme_primary_color}"
    assert school.header_bg_color == '#064e3b', f"Expected #064e3b, got {school.header_bg_color}"
    assert school.footer_bg_color == '#022c22', f"Expected #022c22, got {school.footer_bg_color}"
    assert school.body_bg_color == '#f0fdf4', f"Expected #f0fdf4, got {school.body_bg_color}"
    print(" -> Successfully saved custom font and theme colors into database!")

    # TEST 3: CSS property helpers verification
    print("\n[TEST 3] Verifying CSS font properties on model...")
    assert "Khmer OS Siemreap" in school.display_font_css
    assert "Moul" in school.report_font_css
    print(f" -> display_font_css: {school.display_font_css}")
    print(f" -> report_font_css: {school.report_font_css}")

    # TEST 4: Verification on Web App Portal (/dashboard/admin/)
    print("\n[TEST 4] Verifying Web App Portal reflects custom fonts & colors...")
    res = client.get('/dashboard/admin/')
    assert res.status_code == 200
    content = res.content.decode('utf-8')
    assert "Khmer OS Siemreap" in content, "Admin portal should output the selected font"
    assert "#059669" in content, "Admin portal should output the primary color #059669"
    assert "#f0fdf4" in content, "Admin portal should output the body bg color #f0fdf4"
    print(" -> Web App Portal successfully loaded custom font & colors in root CSS variables!")

    # TEST 5: Verification on Public Website (/)
    print("\n[TEST 5] Verifying Public Website reflects custom fonts & colors...")
    client.logout()
    res = client.get('/')
    assert res.status_code == 200
    content = res.content.decode('utf-8')
    assert "Khmer OS Siemreap" in content, "Website should output selected font"
    assert "#059669" in content, "Website should output primary color #059669"
    assert "#064e3b" in content, "Website should output header bg color #064e3b"
    assert "#022c22" in content, "Website should output footer bg color #022c22"
    print(" -> Public Website successfully loaded custom font, header, footer & primary colors!")

    # TEST 6: Change to Khmer OS Battambang and Crimson Maroon preset
    print("\n[TEST 6] Testing another font: Khmer OS Battambang & Crimson Maroon...")
    client.force_login(admin_user)
    post_data['display_font'] = 'Khmer OS Battambang'
    post_data['theme_primary_color'] = '#991b1b'
    post_data['header_bg_color'] = '#450a0a'
    post_data['footer_bg_color'] = '#1f0404'
    post_data['body_bg_color'] = '#fff5f5'
    res = client.post(reverse('school_profile_settings'), data=post_data, follow=True)
    assert res.status_code == 200
    school.refresh_from_db()
    assert school.display_font == 'Khmer OS Battambang'
    assert school.theme_primary_color == '#991b1b'

    res = client.get('/')
    assert res.status_code == 200
    content = res.content.decode('utf-8')
    assert "Khmer OS Battambang" in content
    assert "#991b1b" in content
    print(" -> Khmer OS Battambang and Crimson Maroon applied everywhere successfully!")

    print("\n==================================================")
    print("ALL THEME & FONT CUSTOMIZATION TESTS PASSED 100%!")
    print("==================================================")

if __name__ == '__main__':
    run_tests()
