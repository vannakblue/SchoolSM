import os
import json
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from django.urls import reverse
from apps.accounts.models import User, RoleMenuPermission, MenuSection, MenuItem
from apps.accounts.menu_registry import (
    sync_system_menus_to_db,
    get_menu_catalog,
    get_default_permissions_for_role,
    get_role_permissions_map,
    is_menu_allowed,
    set_role_permission,
    reset_role_permissions
)
from apps.accounts.context_processors import user_role_context
from django.test import RequestFactory


def run_tests():
    print("=== STARTING ROLE MENU & SUBMENU DATABASE CRUD & PERMISSIONS VERIFICATION ===")

    # 1. Sync System Menus to Database
    sync_system_menus_to_db()
    total_sections = MenuSection.objects.count()
    total_items = MenuItem.objects.count()
    assert total_sections >= 8, f"Expected at least 8 sections in DB, found {total_sections}"
    assert total_items >= 35, f"Expected at least 35 items in DB, found {total_items}"
    print(f"  [PASS] 1. Synchronized {total_sections} Sections and {total_items} Submenus into Database!")

    # 2. Test Users Setup
    admin_user, _ = User.objects.get_or_create(
        username='perm_admin_tester',
        defaults={'role': User.Role.ADMIN, 'khmer_name': 'Admin Tester'}
    )
    teacher_user, _ = User.objects.get_or_create(
        username='perm_teacher_tester',
        defaults={'role': User.Role.TEACHER, 'khmer_name': 'Teacher Tester'}
    )
    student_user, _ = User.objects.get_or_create(
        username='perm_student_tester',
        defaults={'role': User.Role.STUDENT, 'khmer_name': 'Student Tester'}
    )
    accountant_user, _ = User.objects.get_or_create(
        username='perm_accountant_tester',
        defaults={'role': User.Role.ACCOUNTANT, 'khmer_name': 'Accountant Tester'}
    )

    # 3. Test Database Sourced Menu Catalog Structure
    catalog = get_menu_catalog()
    assert len(catalog) >= 8, f"Expected at least 8 sections, found {len(catalog)}"
    section_keys = [s['key'] for s in catalog]
    for required_sec in ['sec_dashboard', 'sec_students', 'sec_timetable', 'sec_attendance', 'sec_examinations', 'sec_tools', 'sec_settings']:
        assert required_sec in section_keys, f"Missing section {required_sec}"
    print(f"  [PASS] 2. Menu Catalog correctly loaded from Database ({len(catalog)} sections).")

    # 4. Test Dynamic DB Permission Overrides
    reset_role_permissions('TEACHER')
    assert is_menu_allowed(teacher_user, 'timetable_view') is True, "Timetable view should be allowed initially"

    # Turn OFF timetable_view for teacher
    set_role_permission('TEACHER', 'timetable_view', False)
    assert is_menu_allowed(teacher_user, 'timetable_view') is False, "Timetable view should now be forbidden after override"

    # Turn ON timetable_view again
    set_role_permission('TEACHER', 'timetable_view', True)
    assert is_menu_allowed(teacher_user, 'timetable_view') is True, "Timetable view should now be allowed again"
    print("  [PASS] 3. Database permission overrides function seamlessly.")

    # 5. Test Superadmin Global Access Override
    set_role_permission('ADMIN', 'teacher_attendance', False)
    assert is_menu_allowed(admin_user, 'teacher_attendance') is True, "Admin should always have access to all menus"
    assert is_menu_allowed(admin_user, 'non_existent_key_xyz') is True, "Admin should always bypass all checks"
    print("  [PASS] 4. Superadmin retains global bypass access.")

    # 6. Test Client Admin Portal Access
    client = Client()
    client.force_login(admin_user)
    res_admin = client.get(reverse('menu_permissions'))
    assert res_admin.status_code == 200, f"Admin menu permissions page failed with {res_admin.status_code}"
    assert 'កំណត់សិទ្ធិ Menu & Submenu តាមតួនាទី' in res_admin.content.decode('utf-8')
    print("  [PASS] 5. Admin portal GET /settings/menu-permissions/ -> 200 OK")

    # 7. Test Admin Adding New Custom Submenu to Database via API
    sec_extras = MenuSection.objects.get(code='sec_extras')
    # Clean previous test item if exists
    MenuItem.objects.filter(code='test_custom_portal').delete()

    res_add = client.post(
        reverse('api_create_menu_item'),
        data=json.dumps({
            'section_id': sec_extras.id,
            'code': 'test_custom_portal',
            'name_kh': 'វិបផតថលពិសេស (Test Portal)',
            'name_en': 'Test Custom Portal',
            'icon': 'fa-solid fa-star text-warning',
            'custom_url': '/portals/test-custom/',
            'roles': ['TEACHER', 'STUDENT']
        }),
        content_type='application/json'
    )
    assert res_add.status_code == 200, f"Add API failed with {res_add.status_code}: {res_add.content.decode('utf-8')}"
    json_add = res_add.json()
    assert json_add.get('status') == 'success'
    created_item_id = json_add.get('item_id')

    # Verify created in DB
    item_in_db = MenuItem.objects.get(id=created_item_id)
    assert item_in_db.name_kh == 'វិបផតថលពិសេស (Test Portal)'
    assert item_in_db.code == 'test_custom_portal'
    assert item_in_db.get_url == '/portals/test-custom/'
    print("  [PASS] 6. Admin created new custom Submenu in Database via API successfully!")

    # 8. Test Admin Editing Existing Submenu in Database via API
    res_edit = client.post(
        reverse('api_edit_menu_item', kwargs={'item_id': created_item_id}),
        data=json.dumps({
            'name_kh': 'វិបផតថលកែប្រែថ្មី',
            'name_en': 'Updated Custom Portal',
            'icon': 'fa-solid fa-gem text-success',
            'custom_url': '/portals/updated-url/',
            'is_admin_only': False
        }),
        content_type='application/json'
    )
    assert res_edit.status_code == 200
    json_edit = res_edit.json()
    assert json_edit.get('status') == 'success'

    # Verify updated in DB
    item_in_db.refresh_from_db()
    assert item_in_db.name_kh == 'វិបផតថលកែប្រែថ្មី'
    assert item_in_db.name_en == 'Updated Custom Portal'
    assert item_in_db.custom_url == '/portals/updated-url/'
    print("  [PASS] 7. Admin edited Submenu in Database via API successfully!")

    # 9. Test Context Processor Dynamic Sidebar Output for Users
    factory = RequestFactory()
    req = factory.get('/')
    req.user = teacher_user
    ctx = user_role_context(req)
    assert 'sidebar_catalog' in ctx
    # Look for the edited custom item in teacher's sidebar
    extras_sec = next((s for s in ctx['sidebar_catalog'] if s['key'] == 'sec_extras'), None)
    assert extras_sec is not None, "sec_extras must be in sidebar_catalog"
    found_item = any(i['name_kh'] == 'វិបផតថលកែប្រែថ្មី' for i in extras_sec['visible_items'])
    assert found_item is True, "Newly added/edited menu must be immediately visible in teacher's dynamic sidebar"
    print("  [PASS] 8. Dynamic sidebar immediately includes database-added/edited items for active roles!")

    # 10. Test Admin Deleting Custom Submenu from Database via API
    res_delete = client.post(
        reverse('api_delete_menu_item', kwargs={'item_id': created_item_id}),
        content_type='application/json'
    )
    assert res_delete.status_code == 200
    json_del = res_delete.json()
    assert json_del.get('status') == 'success'
    assert not MenuItem.objects.filter(id=created_item_id).exists(), "Submenu should be deleted from DB"
    print("  [PASS] 9. Admin deleted custom Submenu from Database via API successfully!")

    # 11. Cleanup test role overrides
    reset_role_permissions()
    print("=== ALL 9 DATABASE CRUD & DYNAMIC PERMISSION TESTS PASSED PERFECTLY ===")


if __name__ == '__main__':
    run_tests()
