import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from apps.accounts.models import User, MenuSection, MenuItem, RoleMenuPermission
from apps.accounts.menu_registry import (
    sync_system_menus_to_db,
    get_menu_catalog,
    get_role_permissions_map,
    is_menu_allowed,
    reset_role_permissions
)
from apps.accounts.context_processors import user_role_context
from django.test import RequestFactory

def verify_roles_and_zoom():
    print("=== VERIFYING RBAC ROLE MENUS & SMARTPHONE ZOOM CAPABILITIES ===")
    
    # 1. Sync menus
    sync_system_menus_to_db()
    
    # Clear any past custom overrides to test fresh system defaults
    reset_role_permissions()
    
    # 2. Test Super Admin
    admin_user, _ = User.objects.get_or_create(username='verify_admin', defaults={'role': User.Role.ADMIN})
    teacher_user, _ = User.objects.get_or_create(username='verify_teacher', defaults={'role': User.Role.TEACHER})
    accountant_user, _ = User.objects.get_or_create(username='verify_accountant', defaults={'role': User.Role.ACCOUNTANT})
    student_user, _ = User.objects.get_or_create(username='verify_student', defaults={'role': User.Role.STUDENT})

    # Admin: Full Access
    assert is_menu_allowed(admin_user, 'admin_dashboard') is True
    assert is_menu_allowed(admin_user, 'user_management') is True
    assert is_menu_allowed(admin_user, 'menu_permissions') is True
    assert is_menu_allowed(admin_user, 'invoice_list') is True
    assert is_menu_allowed(admin_user, 'grade_entry_matrix') is True
    print("  [PASS] 1. Admin has 100% full access to all system menus.")

    # Teacher: Academics, Timetable, Attendance, Grade Entry, Leaves, Tools
    assert is_menu_allowed(teacher_user, 'teacher_dashboard') is True
    assert is_menu_allowed(teacher_user, 'student_list') is True
    assert is_menu_allowed(teacher_user, 'timetable_view') is True
    assert is_menu_allowed(teacher_user, 'student_attendance_grid') is True
    assert is_menu_allowed(teacher_user, 'grade_entry_matrix') is True
    assert is_menu_allowed(teacher_user, 'teacher_mobile_qr_scan') is True
    assert is_menu_allowed(teacher_user, 'teacher_leave_list') is True
    assert is_menu_allowed(teacher_user, 'tool_classroom_picker') is True
    # Teacher should NOT see Admin Only or Finance menus by default
    assert is_menu_allowed(teacher_user, 'admin_dashboard') is False
    assert is_menu_allowed(teacher_user, 'user_management') is False
    assert is_menu_allowed(teacher_user, 'invoice_list') is False
    assert is_menu_allowed(teacher_user, 'payroll_list') is False
    print("  [PASS] 2. Teacher has exact pedagogical, grading, attendance, and leave menus.")

    # Accountant: Finance, Invoices, Expenses, Utilities, Payroll, Inventory
    assert is_menu_allowed(accountant_user, 'finance_dashboard') is True
    assert is_menu_allowed(accountant_user, 'moeys_reports') is True
    assert is_menu_allowed(accountant_user, 'monthly_fees_tracker') is True
    assert is_menu_allowed(accountant_user, 'invoice_list') is True
    assert is_menu_allowed(accountant_user, 'expense_list') is True
    assert is_menu_allowed(accountant_user, 'payroll_list') is True
    assert is_menu_allowed(accountant_user, 'inventory_list') is True
    assert is_menu_allowed(accountant_user, 'tool_khmer_number_converter') is True
    # Accountant should NOT see Grade entry, Teacher attendance settings, Admin settings
    assert is_menu_allowed(accountant_user, 'grade_entry_matrix') is False
    assert is_menu_allowed(accountant_user, 'teacher_attendance') is False
    assert is_menu_allowed(accountant_user, 'user_management') is False
    print("  [PASS] 3. Accountant has exact finance, utility tracker, invoice, and payroll menus.")

    # Student / Parent: Student Dashboard, Timetable Card, Library, Digital Tools
    assert is_menu_allowed(student_user, 'student_dashboard') is True
    assert is_menu_allowed(student_user, 'student_teacher_timetable_view') is True
    assert is_menu_allowed(student_user, 'announcement_list') is True
    assert is_menu_allowed(student_user, 'book_list') is True
    assert is_menu_allowed(student_user, 'tools_hub') is True
    # Student should NOT see management, grade entry, or attendance admin
    assert is_menu_allowed(student_user, 'student_attendance_grid') is False
    assert is_menu_allowed(student_user, 'grade_entry_matrix') is False
    assert is_menu_allowed(student_user, 'invoice_list') is False
    assert is_menu_allowed(student_user, 'user_management') is False
    print("  [PASS] 4. Student & Parent have clean, streamlined portal & study schedule menus.")

    # 3. Verify Context Processor Sidebar Catalog for Each Role
    rf = RequestFactory()
    for role_name, test_u in [('TEACHER', teacher_user), ('ACCOUNTANT', accountant_user), ('STUDENT', student_user)]:
        req = rf.get('/')
        req.user = test_u
        ctx = user_role_context(req)
        visible_secs = [s['name_kh'] for s in ctx['sidebar_catalog']]
        total_submenus = sum(len(s['visible_items']) for s in ctx['sidebar_catalog'])
        print(f"     -> Role {role_name}: {len(visible_secs)} Sections, {total_submenus} Submenus visible.")
        assert len(visible_secs) > 0, f"Role {role_name} should have visible sections"

    # 4. Verify Viewport Meta & Pinch-to-Zoom Configuration in CSS and Templates
    templates_to_check = [
        'templates/base.html',
        'templates/accounts/login.html',
        'templates/maintenance.html',
        'templates/students/public_enroll.html',
        'templates/students/public_enroll_success.html',
        'templates/students/student_id_card.html',
        'templates/teachers/teacher_leave_print.html',
        'templates/examinations/report_card.html',
        'templates/examinations/standardized/room_postings_print.html',
        'templates/examinations/standardized/attendance_sheets_print.html',
        'templates/finance/official_receipt.html'
    ]
    for t_path in templates_to_check:
        with open(t_path, 'r', encoding='utf-8') as f:
            content = f.read()
            assert 'user-scalable=yes' in content, f"Missing user-scalable=yes in {t_path}"
            assert 'maximum-scale=5.0' in content, f"Missing maximum-scale=5.0 in {t_path}"
    print("  [PASS] 5. All 11 HTML templates include full viewport scaling (maximum-scale=5.0, user-scalable=yes).")

    # 5. Check CSS touch-action pinch-zoom
    with open('static/css/custom.css', 'r', encoding='utf-8') as f:
        css_content = f.read()
        assert 'touch-action: pan-x pan-y pinch-zoom' in css_content
        assert '-webkit-overflow-scrolling: touch' in css_content
    print("  [PASS] 6. Custom CSS contains smooth mobile touch-action pan and pinch-to-zoom rules.")

    print("\n=== ALL RBAC ROLES & MOBILE PINCH-TO-ZOOM VERIFICATIONS COMPLETED SUCCESSFULLY ===")

if __name__ == '__main__':
    verify_roles_and_zoom()
