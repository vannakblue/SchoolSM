import os
import sys
import django

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client, RequestFactory
from django.template import Template, Context
from apps.accounts.models import User
from apps.accounts.translation_service import get_current_language, set_current_language, t, TranslationProxy
from apps.accounts.context_processors import user_role_context
from apps.accounts.menu_registry import sync_system_menus_to_db
from apps.students.views import student_list

def run_tests():
    print("=== STARTING BILINGUAL SYSTEM & CLEAN SEPARATION TEST SUITE ===")

    # Sync latest cleaned menu definitions to DB
    sync_system_menus_to_db()

    # 1. Setup Admin User
    admin_user, _ = User.objects.get_or_create(
        username='test_admin_bilingual',
        defaults={'role': 'ADMIN', 'is_staff': True, 'is_superuser': True}
    )
    admin_user.set_password('Admin@123456')
    admin_user.role = 'ADMIN'
    admin_user.language_preference = 'km'
    admin_user.save()

    client = Client()
    client.force_login(admin_user)
    rf = RequestFactory()

    print("1. [PASS] Setup test user environment.")

    # 2. Test Default Language Resolution
    req_default = rf.get('/')
    req_default.user = admin_user
    req_default.session = {}
    assert get_current_language(req_default) == 'km'
    print("2. [PASS] Default language correctly resolved to 'km' (Khmer).")

    # 3. Test Language Switching Endpoint
    resp_switch_en = client.get('/accounts/set-language/?lang=en&next=/students/')
    assert resp_switch_en.status_code == 302
    assert resp_switch_en.url == '/students/'
    assert client.cookies.get('django_language').value == 'en'
    assert client.session.get('django_language') == 'en'
    
    # Reload user from DB
    admin_user.refresh_from_db()
    assert admin_user.language_preference == 'en'
    print("3. [PASS] Switched to English: Cookie, Session, and User preference updated to 'en'.")

    # Switch back to Khmer
    resp_switch_km = client.get('/accounts/set-language/?lang=km&next=/students/')
    assert resp_switch_km.status_code == 302
    assert client.cookies.get('django_language').value == 'km'
    admin_user.refresh_from_db()
    assert admin_user.language_preference == 'km'
    print("4. [PASS] Switched back to Khmer: Cookie, Session, and User preference updated to 'km'.")

    # 5. Test Context Processor under Khmer (km)
    req_km = rf.get('/students/')
    req_km.user = admin_user
    req_km.session = {'django_language': 'km'}
    ctx_km = user_role_context(req_km)

    assert ctx_km['current_language'] == 'km'
    assert ctx_km['is_khmer'] == True
    assert ctx_km['is_english'] == False
    assert ctx_km['current_role_name'] == 'អ្នកគ្រប់គ្រងប្រព័ន្ធ'
    assert ctx_km['current_language_flag'] == '🇰🇭'

    # Check Sidebar Clean Separation (Pure Khmer)
    sec_students_km = next(s for s in ctx_km['sidebar_catalog'] if s['key'] == 'sec_students')
    assert '/' not in sec_students_km['display_name']
    assert sec_students_km['display_name'] == 'គ្រប់គ្រងសិស្ស & ការសិក្សា'
    
    item_student_list_km = next(i for i in sec_students_km['visible_items'] if i['key'] == 'student_list')
    assert '(' not in item_student_list_km['display_name']
    assert item_student_list_km['display_name'] == 'បញ្ជីសិស្ស'
    print("5. [PASS] Khmer Context: Sidebar displays Pure Khmer without English slashes or parentheses.")

    # 6. Test Context Processor under English (en)
    req_en = rf.get('/students/')
    req_en.user = admin_user
    req_en.session = {'django_language': 'en'}
    ctx_en = user_role_context(req_en)

    assert ctx_en['current_language'] == 'en'
    assert ctx_en['is_khmer'] == False
    assert ctx_en['is_english'] == True
    assert ctx_en['current_role_name'] == 'Super Admin'
    assert ctx_en['current_language_flag'] == '🇬🇧'

    # Check Sidebar Clean Separation (Pure English)
    sec_students_en = next(s for s in ctx_en['sidebar_catalog'] if s['key'] == 'sec_students')
    assert sec_students_en['display_name'] == 'Students & Academics'

    item_student_list_en = next(i for i in sec_students_en['visible_items'] if i['key'] == 'student_list')
    assert item_student_list_en['display_name'] == 'Student Directory'
    print("6. [PASS] English Context: Sidebar displays Pure English.")

    # 7. Test Translation Proxy & Template Tags
    proxy_km = TranslationProxy('km')
    assert proxy_km.all_students == 'បញ្ជីសិស្សទាំងអស់'
    assert proxy_km.enroll_student == 'ចុះឈ្មោះសិស្សថ្មី'
    assert proxy_km.save == 'រក្សាទុក'

    proxy_en = TranslationProxy('en')
    assert proxy_en.all_students == 'All Students Directory'
    assert proxy_en.enroll_student == 'Enroll New Student'
    assert proxy_en.save == 'Save'

    tpl_str = """
    {% load i18n_extras %}
    {% lang_switch "បញ្ជីសិស្ស" "Student Directory" %} | {{ 'enroll_student'|t:current_language }}
    """
    tpl = Template(tpl_str)
    rendered_km = tpl.render(Context({'current_language': 'km'})).strip()
    assert 'បញ្ជីសិស្ស | ចុះឈ្មោះសិស្សថ្មី' in rendered_km

    rendered_en = tpl.render(Context({'current_language': 'en'})).strip()
    assert 'Student Directory | Enroll New Student' in rendered_en
    print("7. [PASS] Translation Proxy and Template Tags {% lang_switch %} & filter |t executed perfectly.")

    # 8. Test Student List Page HTML Rendering in Khmer
    req_view_km = rf.get('/students/')
    req_view_km.user = admin_user
    req_view_km.session = {'django_language': 'km'}
    resp_km = student_list(req_view_km)
    assert resp_km.status_code == 200
    html_km = resp_km.content.decode('utf-8')
    assert 'បញ្ជីសិស្សទាំងអស់' in html_km
    assert 'ចុះឈ្មោះសិស្សថ្មី' in html_km
    assert 'បញ្ជីសិស្សទាំងអស់ (Student Directory)' not in html_km
    print("8. [PASS] Student List View rendered in pure Khmer with no mixed bilingual clutter.")

    # 9. Test Student List Page HTML Rendering in English
    req_view_en = rf.get('/students/')
    req_view_en.user = admin_user
    req_view_en.session = {'django_language': 'en'}
    resp_en = student_list(req_view_en)
    assert resp_en.status_code == 200
    html_en = resp_en.content.decode('utf-8')
    assert 'All Students Directory' in html_en
    assert 'Enroll New Student' in html_en
    assert 'Export Excel' in html_en
    print("9. [PASS] Student List View rendered in pure English.")

    # Cleanup
    admin_user.delete()

    print("\n=== ALL 9 BILINGUAL SYSTEM & CLEAN SEPARATION TESTS PASSED 100%! ===")

if __name__ == '__main__':
    run_tests()
