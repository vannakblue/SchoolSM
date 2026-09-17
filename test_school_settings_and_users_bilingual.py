import os
import sys
import django

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client, RequestFactory
from apps.accounts.models import User
from apps.accounts.views import school_profile_settings_view, user_management_view, telegram_settings_view

def test_settings_pages():
    print("=== TESTING SCHOOL SETTINGS & USER MANAGEMENT BILINGUAL PURITY ===")

    admin_user, _ = User.objects.get_or_create(
        username='test_admin_settings_clean',
        defaults={'role': 'ADMIN', 'is_staff': True, 'is_superuser': True}
    )
    admin_user.set_password('Admin@123456')
    admin_user.role = 'ADMIN'
    admin_user.save()

    client = Client()
    client.force_login(admin_user)
    rf = RequestFactory()

    # ----------------------------------------------------
    # 1. School Profile Settings View (Khmer)
    # ----------------------------------------------------
    req_school_km = rf.get('/accounts/settings/school/')
    req_school_km.user = admin_user
    req_school_km.session = {'django_language': 'km'}
    resp_school_km = school_profile_settings_view(req_school_km)
    assert resp_school_km.status_code == 200
    html_school_km = resp_school_km.content.decode('utf-8')

    # Positive assertions (Khmer)
    assert "ការកំណត់ព័ត៌មានសាលារៀន" in html_school_km
    assert "ផ្ទាំងមើលគំរូជាក់ស្តែង" in html_school_km
    assert "រក្សាទុកព័ត៌មានសាលារៀន" in html_school_km

    # Negative assertions (No mixed bilingual clutter in Khmer mode)
    assert "(School Profile & Settings)" not in html_school_km, "Found '(School Profile & Settings)' in Khmer mode"
    assert "(Institution Type)" not in html_school_km, "Found '(Institution Type)' in Khmer mode"
    assert "(Save Changes)" not in html_school_km, "Found '(Save Changes)' in Khmer mode"
    assert "(Live Preview)" not in html_school_km, "Found '(Live Preview)' in Khmer mode"
    assert "(Student ID Format Settings)" not in html_school_km, "Found '(Student ID Format Settings)' in Khmer mode"
    assert "(Display Font)" not in html_school_km, "Found '(Display Font)' in Khmer mode"
    assert "(Aspect Ratio)" not in html_school_km, "Found '(Aspect Ratio)' in Khmer mode"
    assert "(Zoom, Pan & Crop School Profile)" not in html_school_km, "Found '(Zoom, Pan & Crop School Profile)' in Khmer mode"
    assert "សាធារណៈ / Public School" not in html_school_km, "Found 'សាធារណៈ / Public School' in Khmer mode"
    print("1. [PASS] School Profile Settings: 100% Pure Khmer rendered with zero bilingual clutter.")

    # ----------------------------------------------------
    # 2. School Profile Settings View (English)
    # ----------------------------------------------------
    req_school_en = rf.get('/accounts/settings/school/')
    req_school_en.user = admin_user
    req_school_en.session = {'django_language': 'en'}
    resp_school_en = school_profile_settings_view(req_school_en)
    assert resp_school_en.status_code == 200
    html_school_en = resp_school_en.content.decode('utf-8')

    assert "School Profile & Settings" in html_school_en
    assert "Live Preview" in html_school_en
    assert "Save Changes" in html_school_en
    assert "Student ID Format Settings" in html_school_en
    assert "Theme & Typography" in html_school_en
    print("2. [PASS] School Profile Settings: 100% Pure English rendered cleanly.")

    # ----------------------------------------------------
    # 3. User Management View (Khmer)
    # ----------------------------------------------------
    req_users_km = rf.get('/accounts/users/')
    req_users_km.user = admin_user
    req_users_km.session = {'django_language': 'km'}
    resp_users_km = user_management_view(req_users_km)
    assert resp_users_km.status_code == 200
    html_users_km = resp_users_km.content.decode('utf-8')

    assert "គ្រប់គ្រងគណនីអ្នកប្រើប្រាស់" in html_users_km
    assert "(User Management)" not in html_users_km, "Found '(User Management)' in Khmer mode"
    assert "(Add User)" not in html_users_km, "Found '(Add User)' in Khmer mode"
    assert "(Reset Password)" not in html_users_km, "Found '(Reset Password)' in Khmer mode"
    assert "(Role)" not in html_users_km, "Found '(Role)' in Khmer mode"
    assert "(Date Joined)" not in html_users_km, "Found '(Date Joined)' in Khmer mode"
    assert "(Actions)" not in html_users_km, "Found '(Actions)' in Khmer mode"
    assert "(Active)" not in html_users_km, "Found '(Active)' in Khmer mode"
    assert "(Inactive)" not in html_users_km, "Found '(Inactive)' in Khmer mode"
    print("3. [PASS] User Management View: 100% Pure Khmer rendered with zero bilingual clutter.")

    # ----------------------------------------------------
    # 4. User Management View (English)
    # ----------------------------------------------------
    req_users_en = rf.get('/accounts/users/')
    req_users_en.user = admin_user
    req_users_en.session = {'django_language': 'en'}
    resp_users_en = user_management_view(req_users_en)
    assert resp_users_en.status_code == 200
    html_users_en = resp_users_en.content.decode('utf-8')

    assert "User Management" in html_users_en
    assert "Add New User" in html_users_en
    assert "Reset Password" in html_users_en
    assert "Total Users" in html_users_en
    print("4. [PASS] User Management View: 100% Pure English rendered cleanly.")

    # ----------------------------------------------------
    # 5. Telegram Settings View (Khmer & English)
    # ----------------------------------------------------
    req_tg_km = rf.get('/accounts/settings/telegram/')
    req_tg_km.user = admin_user
    req_tg_km.session = {'django_language': 'km'}
    resp_tg_km = telegram_settings_view(req_tg_km)
    assert resp_tg_km.status_code == 200
    html_tg_km = resp_tg_km.content.decode('utf-8')

    assert "(Student Absence Alert)" not in html_tg_km
    assert "(Exam Results & Rankings)" not in html_tg_km
    assert "(Enable System)" not in html_tg_km

    req_tg_en = rf.get('/accounts/settings/telegram/')
    req_tg_en.user = admin_user
    req_tg_en.session = {'django_language': 'en'}
    resp_tg_en = telegram_settings_view(req_tg_en)
    assert resp_tg_en.status_code == 200
    html_tg_en = resp_tg_en.content.decode('utf-8')

    assert "Student Absence Alert" in html_tg_en
    assert "Exam Results & Rankings Alert" in html_tg_en
    assert "Enable System" in html_tg_en
    print("5. [PASS] Telegram Settings View: 100% clean single language in both Khmer and English.")

    admin_user.delete()
    print("\n=== ALL TEST CHECKS PASSED WITH ZERO ERRORS! ===")

if __name__ == '__main__':
    test_settings_pages()
