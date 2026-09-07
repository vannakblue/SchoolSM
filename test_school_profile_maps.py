import os
import sys
import django

if sys.stdout and sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client, RequestFactory
from django.urls import reverse
from apps.accounts.models import User, SchoolProfile
from apps.accounts.context_processors import user_role_context


def run_tests():
    print("=== STARTING SCHOOL PROFILE & GOOGLE MAPS GPS VERIFICATION ===")

    # 1. Setup Admin User
    admin_user, _ = User.objects.get_or_create(
        username='maps_admin_tester',
        defaults={'role': User.Role.ADMIN, 'khmer_name': 'Admin Maps Tester'}
    )

    client = Client()
    client.force_login(admin_user)

    # 2. Test GET School Profile Settings page
    res_get = client.get(reverse('school_profile_settings'))
    assert res_get.status_code == 200, f"GET school_profile_settings returned {res_get.status_code}"
    content = res_get.content.decode('utf-8')
    assert 'ផែនទីទីតាំង Google Maps & GPS' in content, "Map section must be rendered in HTML"
    assert 'QR Code ទីតាំងសាលារៀន' in content, "QR code modal must be rendered in HTML"
    print("  [PASS] 1. GET /accounts/settings/school/ -> 200 OK (Rendered Map & QR Code components)")

    # 3. Test POST Updating School Profile with GPS Coordinates & Google Maps Link
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
        'street_address': 'ផ្លូវលេខ១០៥ ភូមិស្វាយមីង ឃុំបារគូ ស្រុកកណ្តាលស្ទឹង ខេត្តកណ្តាល',
        'latitude': 11.428703,
        'longitude': 104.815356,
        'google_maps_url': 'https://www.google.com/maps?q=11.428703,104.815356',
        'gps_radius_meters': 150,
        'principal_name': 'លោក ផេង រឹទ្ធីយ៉ា',
        'phone': '093 995 947 / 089 995 947',
        'email': 'info@schoolsm.edu.kh',
        'website': 'https://schoolsm.edu.kh',
        'facebook_page': 'https://facebook.com/schoolsm',
        'telegram_channel': 'https://t.me/schoolsm_official',
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
    }

    res_post = client.post(reverse('school_profile_settings'), data=post_data, follow=True)
    assert res_post.status_code == 200, f"POST school_profile_settings failed with {res_post.status_code}"

    # 4. Verify DB updates
    profile = SchoolProfile.get_settings()
    profile.refresh_from_db()

    assert profile.name_kh == 'វិទ្យាល័យ ហ៊ុន សែន កំពង់កន្ទួត'
    assert profile.institution_type == 'PUBLIC'
    assert abs(profile.latitude - 11.428703) < 0.0001, f"Latitude mismatch: {profile.latitude}"
    assert abs(profile.longitude - 104.815356) < 0.0001, f"Longitude mismatch: {profile.longitude}"
    assert profile.gps_radius_meters == 150
    assert profile.google_maps_direct_url == 'https://www.google.com/maps?q=11.428703,104.815356'
    print("  [PASS] 2. School Profile GPS & Google Maps saved and verified in Database!")

    # 5. Test Fallback Google Maps Direct URL Property
    profile.google_maps_url = ""
    assert "https://www.google.com/maps?q=11.428703,104.815356" in profile.google_maps_direct_url
    print("  [PASS] 3. Property google_maps_direct_url accurately constructs URL from coordinates!")

    # 6. Test google_maps_embed_url uses strictly dots (no L10N commas)
    embed_url = profile.google_maps_embed_url
    assert "11.428703,104.815356" in embed_url, f"Expected dots in embed_url, got {embed_url}"
    assert "11,428703" not in embed_url, f"Commas must not exist in embed_url: {embed_url}"
    print("  [PASS] 4. Property google_maps_embed_url formats coordinates with dots strictly (immune to km-kh locale)!")

    # 7. Test website contact page iframe rendering
    res_contact = client.get(reverse('website_contact'))
    assert res_contact.status_code == 200
    contact_html = res_contact.content.decode('utf-8')
    assert 'q=11.428703,104.815356' in contact_html, "Contact page iframe must contain dot coordinates"
    assert 'q=11,428703' not in contact_html, "Contact page iframe must NOT contain comma coordinates"
    print("  [PASS] 5. GET /contact/ renders iframe with exact dot coordinates: q=11.428703,104.815356")

    # 8. Test website home page iframe rendering
    res_home = client.get(reverse('website_home'))
    assert res_home.status_code == 200
    home_html = res_home.content.decode('utf-8')
    assert 'q=11.428703,104.815356' in home_html, "Home page iframe must contain dot coordinates"
    assert 'q=11,428703' not in home_html, "Home page iframe must NOT contain comma coordinates"
    print("  [PASS] 6. GET / (Home) renders iframe with exact dot coordinates: q=11.428703,104.815356")

    # 9. Test Context Processor Global Sync
    factory = RequestFactory()
    req = factory.get('/')
    req.user = admin_user
    ctx = user_role_context(req)
    assert 'school_info' in ctx
    assert ctx['school_info'].name_kh == 'វិទ្យាល័យ ហ៊ុន សែន កំពង់កន្ទួត'
    print("  [PASS] 7. Context processor synchronizes updated SchoolProfile globally to all templates!")

    print("=== ALL SCHOOL PROFILE & GOOGLE MAPS GPS TESTS PASSED (7/7) ===")


if __name__ == '__main__':
    run_tests()
