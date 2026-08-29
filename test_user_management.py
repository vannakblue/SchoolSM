import os
import sys
import json
import django

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from django.urls import reverse
from apps.accounts.models import User, MenuItem, MenuSection
from apps.accounts.menu_registry import sync_system_menus_to_db
from apps.accounts.search_service import global_omnisearch


def run_tests():
    print("=== STARTING USER MANAGEMENT PORTAL AUTOMATED TESTS ===")

    # 1. Setup Test Users
    admin_user, _ = User.objects.get_or_create(
        username='test_um_admin',
        defaults={'role': User.Role.ADMIN, 'is_superuser': True, 'khmer_name': 'Admin UM Tester'}
    )
    admin_user.set_password('admin123')
    admin_user.is_staff = True
    admin_user.is_superuser = True
    admin_user.save()

    teacher_user, _ = User.objects.get_or_create(
        username='test_um_teacher',
        defaults={'role': User.Role.TEACHER, 'khmer_name': 'Teacher UM Tester'}
    )
    teacher_user.set_password('teacher123')
    teacher_user.save()

    # 2. Access Control Tests
    print("\n--- 1. Testing Access Control ---")
    admin_client = Client()
    admin_client.force_login(admin_user)

    teacher_client = Client()
    teacher_client.force_login(teacher_user)

    anon_client = Client()

    # Anonymous -> Redirect to login
    res = anon_client.get(reverse('user_management'))
    assert res.status_code == 302, f"Expected 302 for anon, got {res.status_code}"
    print("  [PASS] Anonymous user redirected to login.")

    # Teacher -> Redirect / Access Denied
    res = teacher_client.get(reverse('user_management'))
    assert res.status_code == 302, f"Expected 302 for teacher, got {res.status_code}"
    print("  [PASS] Teacher forbidden from accessing user management.")

    # Admin -> 200 OK
    res = admin_client.get(reverse('user_management'))
    assert res.status_code == 200, f"Expected 200 for admin, got {res.status_code}"
    assert 'គ្រប់គ្រងគណនីអ្នកប្រើប្រាស់' in res.content.decode('utf-8')
    print("  [PASS] Admin granted full access to user management portal.")

    # 3. Test Menu Registry Sync & Search Integration
    print("\n--- 2. Testing Menu & Search Integration ---")
    sync_system_menus_to_db()
    menu_item = MenuItem.objects.filter(code='user_management').first()
    assert menu_item is not None, "Expected 'user_management' MenuItem in DB after sync"
    print(f"  [PASS] Menu Item '{menu_item.name_kh}' synced to database successfully.")

    search_res = global_omnisearch('គ្រប់គ្រងគណនី', user=admin_user)
    found_search = any('/accounts/users/' in item.get('url', '') or 'គ្រប់គ្រងគណនី' in item.get('title_kh', '') for item in search_res)
    assert found_search, f"Expected user_management in omnisearch results, got {search_res}"
    print("  [PASS] Global Omnisearch (Ctrl+K) indexes User Management portal.")

    # 4. Test API Create User
    print("\n--- 3. Testing API Create User ---")
    # Clean up if existed
    User.objects.filter(username__in=['new_created_user_1', 'new_created_user_2']).delete()

    res = admin_client.post(reverse('api_create_user'), {
        'username': 'new_created_user_1',
        'password': 'custompass123',
        'role': 'TEACHER',
        'khmer_name': 'គ្រូ សាកល្បង',
        'latin_name': 'Teacher Test',
        'phone': '012999888',
        'email': 'newteacher@school.edu.kh',
        'is_active': '1'
    })
    assert res.status_code == 200, f"Create user failed: {res.content.decode('utf-8')}"
    data = json.loads(res.content.decode('utf-8'))
    assert data['status'] == 'success', f"Expected success status: {data}"
    
    created_u = User.objects.get(username='new_created_user_1')
    assert created_u.check_password('custompass123'), "Password was not hashed properly"
    assert created_u.role == User.Role.TEACHER
    assert created_u.phone == '012999888'
    print("  [PASS] User created with securely hashed password and full profile.")

    # Duplicate username validation
    res_dup = admin_client.post(reverse('api_create_user'), {
        'username': 'new_created_user_1',
        'password': 'password123',
        'role': 'STUDENT'
    })
    assert res_dup.status_code == 400, f"Expected 400 for duplicate username, got {res_dup.status_code}"
    print("  [PASS] Duplicate username registration correctly rejected.")

    # 5. Test API Edit User & Change Username
    print("\n--- 4. Testing API Edit User & Change Username ---")
    res_edit = admin_client.post(f"/accounts/api/users/{created_u.id}/edit/", {
        'username': 'new_created_user_renamed',
        'role': 'ACCOUNTANT',
        'khmer_name': 'គណនេយ្យករ ថ្មី',
        'latin_name': 'New Accountant',
        'phone': '088777666',
        'email': 'acct@school.edu.kh',
        'is_active': '1'
    })
    assert res_edit.status_code == 200, f"Edit user failed: {res_edit.content.decode('utf-8')}"
    created_u.refresh_from_db()
    assert created_u.username == 'new_created_user_renamed'
    assert created_u.role == User.Role.ACCOUNTANT
    assert created_u.khmer_name == 'គណនេយ្យករ ថ្មី'
    print("  [PASS] User successfully renamed and profile fields updated.")

    # 6. Test API Reset Password
    print("\n--- 5. Testing API Reset Password ---")
    res_reset = admin_client.post(f"/accounts/api/users/{created_u.id}/reset-password/", {
        'new_password': 'supernewpassword999'
    })
    assert res_reset.status_code == 200, f"Reset password failed: {res_reset.content.decode('utf-8')}"
    created_u.refresh_from_db()
    assert created_u.check_password('supernewpassword999'), "New password hash does not match"
    
    # Verify login with new password works
    verify_client = Client()
    login_success = verify_client.login(username='new_created_user_renamed', password='supernewpassword999')
    assert login_success, "User failed to authenticate with newly reset password"
    print("  [PASS] Password reset successfully and authenticated against Django auth system.")

    # 7. Test API Toggle Active / Inactive (Status Switch)
    print("\n--- 6. Testing API Toggle Active / Inactive ---")
    # Deactivate user
    res_toggle1 = admin_client.post(f"/accounts/api/users/{created_u.id}/toggle-active/")
    assert res_toggle1.status_code == 200
    created_u.refresh_from_db()
    assert created_u.is_active is False, "User should be deactivated"
    print("  [PASS] User successfully deactivated (is_active = False).")

    # Activate user back
    res_toggle2 = admin_client.post(f"/accounts/api/users/{created_u.id}/toggle-active/")
    assert res_toggle2.status_code == 200
    created_u.refresh_from_db()
    assert created_u.is_active is True, "User should be reactivated"
    print("  [PASS] User successfully reactivated (is_active = True).")

    # Self-deactivation guard test
    res_self_toggle = admin_client.post(f"/accounts/api/users/{admin_user.id}/toggle-active/")
    assert res_self_toggle.status_code == 400, "Admin should not be able to deactivate own account"
    print("  [PASS] Safety guard prevents Admin from deactivating own logged-in account.")

    # 8. Test API Delete User
    print("\n--- 7. Testing API Delete User ---")
    # Self-deletion guard test
    res_self_del = admin_client.post(f"/accounts/api/users/{admin_user.id}/delete/")
    assert res_self_del.status_code == 400, "Admin should not be able to delete own account"
    print("  [PASS] Safety guard prevents Admin from deleting own account.")

    # Delete the created user
    target_id = created_u.id
    res_del = admin_client.post(f"/accounts/api/users/{target_id}/delete/")
    assert res_del.status_code == 200
    assert not User.objects.filter(id=target_id).exists(), "User should be deleted from DB"
    print("  [PASS] User successfully deleted from database.")

    # 9. Test Search and Filtering queries
    print("\n--- 8. Testing Search & Filtering on User Management View ---")
    res_filter_role = admin_client.get(reverse('user_management') + '?role=TEACHER')
    assert res_filter_role.status_code == 200
    assert 'Teacher Accounts' in res_filter_role.content.decode('utf-8')

    res_search = admin_client.get(reverse('user_management') + '?q=test_um_teacher')
    assert res_search.status_code == 200
    assert 'test_um_teacher' in res_search.content.decode('utf-8')
    print("  [PASS] Search by query and filter by role executed cleanly.")

    print("\n=== ALL USER MANAGEMENT PORTAL TESTS PASSED SUCCESSFULLY! ===")


if __name__ == '__main__':
    run_tests()
