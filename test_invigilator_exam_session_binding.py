import os
import sys
import django

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import RequestFactory, Client
from django.urls import reverse
from apps.accounts.models import User
from apps.accounts.menu_registry import MENU_SECTIONS_CATALOG
from apps.accounts.context_processors import user_role_context
from apps.examinations.models import StandardizedExam, ExamInvigilatorPlan
from apps.academics.models import AcademicYear


def test_invigilator_exam_session_binding():
    print("=" * 80)
    print("TESTING INVIGILATOR PLAN EXAM SESSION BINDING & SUBMENU REMOVAL")
    print("=" * 80)

    # 1. Verify MENU_SECTIONS_CATALOG does NOT contain exam_invigilator_admin
    catalog_item_keys = [
        item['key']
        for sec in MENU_SECTIONS_CATALOG
        for item in sec.get('items', [])
    ]
    assert 'exam_invigilator_admin' not in catalog_item_keys, (
        "exam_invigilator_admin should NOT be in MENU_SECTIONS_CATALOG"
    )
    print("1. [PASS] 'exam_invigilator_admin' ('គ្រប់គ្រងវេនអនុរក្សប្រឡង') is absent from MENU_SECTIONS_CATALOG.")

    # 2. Check exam_invigilator_request is restricted to TEACHER only
    request_item = None
    for sec in MENU_SECTIONS_CATALOG:
        for item in sec.get('items', []):
            if item['key'] == 'exam_invigilator_request':
                request_item = item
                break
    assert request_item is not None, "exam_invigilator_request should exist for teachers"
    assert request_item['default_roles'] == ['TEACHER'], (
        f"exam_invigilator_request default_roles should be ['TEACHER'], got {request_item['default_roles']}"
    )
    print("2. [PASS] 'exam_invigilator_request' is strictly restricted to ['TEACHER'].")

    # 3. Verify Admin and Teacher sidebar items
    admin_user, _ = User.objects.get_or_create(
        username='admin_invig_test',
        defaults={'role': User.Role.ADMIN, 'khmer_name': 'Admin Invig Test'}
    )
    teacher_user, _ = User.objects.get_or_create(
        username='teacher_invig_test',
        defaults={'role': User.Role.TEACHER, 'khmer_name': 'Teacher Invig Test'}
    )

    rf = RequestFactory()
    req_admin = rf.get('/examinations/standardized/')
    req_admin.user = admin_user
    ctx_admin = user_role_context(req_admin)
    admin_visible_keys = [
        item['key']
        for sec in ctx_admin['sidebar_catalog']
        for item in sec['visible_items']
    ]
    assert 'exam_invigilator_admin' not in admin_visible_keys
    assert 'exam_invigilator_request' not in admin_visible_keys
    assert 'standardized_exam_list' in admin_visible_keys
    print("3. [PASS] Admin sidebar has NO standalone invigilator submenu, only 'standardized_exam_list'.")

    req_teacher = rf.get('/examinations/invigilator-request/')
    req_teacher.user = teacher_user
    ctx_teacher = user_role_context(req_teacher)
    teacher_visible_keys = [
        item['key']
        for sec in ctx_teacher['sidebar_catalog']
        for item in sec['visible_items']
    ]
    assert 'exam_invigilator_admin' not in teacher_visible_keys
    assert 'exam_invigilator_request' in teacher_visible_keys
    print("4. [PASS] Teacher sidebar has 'exam_invigilator_request' ('ស្នើសុំវេនអនុរក្សប្រឡង') and no admin submenu.")

    # 4. Verify Active Menu Highlighting when navigating invigilator URLs
    invig_urls = [
        ('exam_invigilator_plans_list', '/examinations/invigilator-plans/'),
        ('exam_invigilator_plan_create', '/examinations/invigilator-plans/create/'),
        ('exam_invigilator_plan_edit', '/examinations/invigilator-plans/1/edit/'),
        ('exam_invigilator_quotas_manage', '/examinations/invigilator-plans/1/quotas/'),
        ('exam_invigilator_roster_view', '/examinations/invigilator-plans/1/roster/'),
    ]

    for url_name, path in invig_urls:
        req = rf.get(path)
        req.user = admin_user
        class MockMatch:
            pass
        match = MockMatch()
        match.url_name = url_name
        req.resolver_match = match

        ctx = user_role_context(req)
        active_keys = [
            item['key']
            for sec in ctx['sidebar_catalog']
            for item in sec['visible_items']
            if item.get('is_current_active')
        ]
        assert active_keys == ['standardized_exam_list'], (
            f"For url {url_name}, expected active key ['standardized_exam_list'], got {active_keys}"
        )
    print("5. [PASS] All invigilator views highlight 'standardized_exam_list' ('សម័យប្រឡង') as active sidebar menu.")

    # 5. Client integration test: Redirects & Guard checks
    client = Client()
    client.force_login(admin_user)

    # 5a. /examinations/invigilator-plans/ -> redirects to /examinations/standardized/
    res_list = client.get(reverse('exam_invigilator_plans_list'))
    assert res_list.status_code == 302
    assert res_list.url == reverse('standardized_exam_list')
    print("6. [PASS] GET /examinations/invigilator-plans/ redirects (302) to standardized_exam_list.")

    # 5b. /examinations/invigilator-plans/create/ without parameters -> redirects to standardized_exam_list with guard message
    res_create_orphan = client.get(reverse('exam_invigilator_plan_create'))
    assert res_create_orphan.status_code == 302
    assert res_create_orphan.url == reverse('standardized_exam_list')
    print("7. [PASS] GET /examinations/invigilator-plans/create/ without exam session parameter is BLOCKED and redirects to standardized_exam_list.")

    # 5c. /examinations/invigilator-plans/create/ WITH session parameters -> successfully opens creation form (200)
    ay = AcademicYear.objects.first()
    res_create_with_param = client.get(reverse('exam_invigilator_plan_create'), {
        'session_key': 'test-session-2026',
        'title': 'សម័យប្រឡងសាកល្បង',
        'year': ay.id if ay else 1,
        'date': '2026-10-01',
        'rooms': '5'
    })
    assert res_create_with_param.status_code == 200
    print("8. [PASS] GET /examinations/invigilator-plans/create/ WITH session parameter allows creating invigilator plan (200).")

    print("\n" + "=" * 80)
    print("🎉 ALL TESTS PASSED (100%)! INVIGILATOR PLAN IS STRICTLY BOUND TO EXAM SESSIONS.")
    print("=" * 80)


if __name__ == '__main__':
    test_invigilator_exam_session_binding()
