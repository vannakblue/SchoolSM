import os
import django

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
        'name_kh': 'វិទ្យាល័យអន្តរជាតិ សាលារៀន SM គំរូ',
        'name_en': 'SchoolSM Model International High School',
        'short_name': 'សាលារៀន SM',
        'school_code': '080101',
        'school_type': 'វិទ្យាល័យចំណេះទូទៅ',
        'institution_type': 'INTERNATIONAL',
        'education_levels': 'មត្តេយ្យ, បឋមសិក្សា, អនុវិទ្យាល័យ, វិទ្យាល័យ',
        'motto': 'ចំណេះដឹង វិន័យ សីលធម៌ គុណធម៌',
        'ministry_name': 'ក្រសួងអប់រំ យុវជន និងកីឡា',
        'poe_name': 'មន្ទីរអប់រំ យុវជន និងកីឡា រាជធានីភ្នំពេញ',
        'doe_name': 'ការិយាល័យអប់រំ យុវជន និងកីឡា ខណ្ឌដូនពេញ',
        'province': 'រាជធានីភ្នំពេញ',
        'district': 'ខណ្ឌដូនពេញ',
        'commune': 'សង្កាត់វត្តភ្នំ',
        'village': 'ភូមិ១',
        'street_address': 'មហាវិថីព្រះនរោត្តម សង្កាត់វត្តភ្នំ',
        'latitude': 11.576543,
        'longitude': 104.923456,
        'google_maps_url': 'https://www.google.com/maps?q=11.576543,104.923456',
        'gps_radius_meters': 150,
        'principal_name': 'លោកបណ្ឌិត សុខ ចាន់ថន',
        'phone': '023 888 999',
        'email': 'contact@schoolsm.edu.kh',
        'website': 'https://schoolsm.edu.kh',
        'facebook_page': 'https://facebook.com/schoolsm',
        'telegram_channel': 'https://t.me/schoolsm_official',
    }

    res_post = client.post(reverse('school_profile_settings'), data=post_data, follow=True)
    assert res_post.status_code == 200, f"POST school_profile_settings failed with {res_post.status_code}"

    # 4. Verify DB updates
    profile = SchoolProfile.get_settings()
    profile.refresh_from_db()

    assert profile.name_kh == 'វិទ្យាល័យអន្តរជាតិ សាលារៀន SM គំរូ'
    assert profile.institution_type == 'INTERNATIONAL'
    assert profile.education_levels == 'មត្តេយ្យ, បឋមសិក្សា, អនុវិទ្យាល័យ, វិទ្យាល័យ'
    assert abs(profile.latitude - 11.576543) < 0.0001, f"Latitude mismatch: {profile.latitude}"
    assert abs(profile.longitude - 104.923456) < 0.0001, f"Longitude mismatch: {profile.longitude}"
    assert profile.gps_radius_meters == 150
    assert profile.google_maps_url == 'https://www.google.com/maps?q=11.576543,104.923456'
    assert profile.telegram_channel == 'https://t.me/schoolsm_official'
    assert profile.google_maps_direct_url == 'https://www.google.com/maps?q=11.576543,104.923456'
    print("  [PASS] 2. School Profile GPS & Google Maps saved and verified in Database!")

    # 5. Test Fallback Google Maps Direct URL Property
    profile.google_maps_url = ""
    assert "https://www.google.com/maps?q=11.576543,104.923456" in profile.google_maps_direct_url
    print("  [PASS] 3. Property google_maps_direct_url accurately constructs URL from coordinates!")

    # 6. Test Context Processor Global Sync
    factory = RequestFactory()
    req = factory.get('/')
    req.user = admin_user
    ctx = user_role_context(req)
    assert 'school_info' in ctx
    assert ctx['school_info'].name_kh == 'វិទ្យាល័យអន្តរជាតិ សាលារៀន SM គំរូ'
    assert ctx['school_info'].institution_type == 'INTERNATIONAL'
    print("  [PASS] 4. Context processor synchronizes updated SchoolProfile globally to all templates!")

    print("=== ALL SCHOOL PROFILE & GOOGLE MAPS GPS TESTS PASSED (4/4) ===")


if __name__ == '__main__':
    run_tests()
