import os
import sys
import base64
import django

if sys.stdout and sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from django.urls import reverse
from apps.accounts.models import User, SchoolProfile
from django.core.files.uploadedfile import SimpleUploadedFile


def run_tests():
    print("=== STARTING SCHOOL PROFILE LOGO CROP & ZOOM VERIFICATION ===")

    # 1. Setup Admin User
    admin_user, _ = User.objects.get_or_create(
        username='crop_admin_tester',
        defaults={'role': User.Role.ADMIN, 'khmer_name': 'Admin Crop Tester'}
    )

    client = Client()
    client.force_login(admin_user)

    # 2. Test GET School Profile Settings page
    res_get = client.get(reverse('school_profile_settings'))
    assert res_get.status_code == 200, f"GET school_profile_settings returned {res_get.status_code}"
    content = res_get.content.decode('utf-8')

    # Verify Cropper.js CSS and JS are included
    assert 'cropper.min.css' in content, "Cropper CSS must be included in extra_css"
    assert 'cropper.min.js' in content, "Cropper JS must be included in extra_js"

    # Verify Crop Modal elements are present
    assert 'schoolLogoCropModal' in content, "Modal schoolLogoCropModal must be present in HTML"
    assert 'logoCropperImage' in content, "logoCropperImage element must be present in modal"
    assert 'logoZoomSlider' in content, "Zoom range slider must be present in modal"
    assert 'crop-circle-preview' in content, "Circular preview must be present in modal"
    assert 'cropped_logo_data' in content, "cropped_logo_data hidden field must be present in form"
    assert 'openCropModalForExistingOrNew' in content, "Crop modal opener must be wired in template"

    print("  [PASS] 1. GET /accounts/settings/school/ renders Cropper.js, Crop Modal, Zoom Slider & Circular Preview!")

    # 3. Test POST with base64 cropped_logo_data
    # 1x1 transparent PNG base64
    tiny_png_b64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

    post_data = {
        'name_kh': 'វិទ្យាល័យ ហ៊ុន សែន កំពង់កន្ទួត',
        'name_en': 'Hun Sen Kampong Kantuot High School',
        'short_name': 'វិទ្យាល័យ កំពង់កន្ទួត',
        'school_code': '08010306901',
        'school_type': 'វិទ្យាល័យចំណេះទូទៅ',
        'institution_type': 'PUBLIC',
        'education_levels': 'អនុវិទ្យាល័យ, វិទ្យាល័យ',
        'motto': 'ចំណេះដឹង វិន័យ សីលធម៌ គុណធម៌',
        'ministry_name': 'ក្រសួងអប់រំ យុវជន និងកីឡា',
        'poe_name': 'មន្ទីរអប់រំ យុវជន និងកីឡា ខេត្តកណ្តាល',
        'doe_name': 'ការិយាល័យអប់រំ យុវជន និងកីឡា ស្រុកកណ្តាលស្ទឹង',
        'province': 'ខេត្តកណ្តាល',
        'district': 'ស្រុកកណ្តាលស្ទឹង',
        'commune': 'ឃុំបារគូ',
        'village': 'ភូមិស្វាយមីង',
        'street_address': 'ផ្លូវលេខ១០៥',
        'latitude': 11.428703,
        'longitude': 104.815356,
        'gps_radius_meters': 150,
        'principal_name': 'លោក ផេង រឹទ្ធីយ៉ា',
        'phone': '093 995 947',
        'email': 'info@schoolsm.edu.kh',
        'date_format': 'dd-mm-yyyy',
        'time_format': 'HH:mm',
        'display_font': 'Khmer OS Battambang',
        'report_header_font': 'Moul',
        'theme_primary_color': '#991b1b',
        'header_bg_color': '#450a0a',
        'footer_bg_color': '#1f0404',
        'body_bg_color': '#fff5f5',
        'student_id_pattern': 'YEAR_END_4D',
        'student_id_digits': 4,
        'registration_mode': 'ADMIN_CUSTOM',
        'cropped_logo_data': tiny_png_b64,
    }

    res_post = client.post(reverse('school_profile_settings'), data=post_data, follow=True)
    assert res_post.status_code == 200, f"POST school_profile_settings failed with {res_post.status_code}"

    # 4. Verify DB was updated with the cropped logo
    profile = SchoolProfile.get_settings()
    profile.refresh_from_db()

    assert profile.logo, "profile.logo must be populated from cropped_logo_data!"
    assert 'school_logo_cropped' in profile.logo.name, f"Expected cropped logo name, got {profile.logo.name}"
    print("  [PASS] 2. Cropped Base64 Logo successfully decoded, converted to ContentFile and saved to SchoolProfile.logo!")

    print("=== ALL SCHOOL PROFILE LOGO CROP & PIN-TO-ZOOM TESTS PASSED (2/2) ===")


if __name__ == '__main__':
    run_tests()
