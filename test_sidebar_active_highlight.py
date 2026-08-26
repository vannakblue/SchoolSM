import os
import sys
import django

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import RequestFactory
from apps.accounts.models import User
from apps.accounts.context_processors import user_role_context


def test_single_active_highlight():
    print("=== TESTING SIDEBAR SINGLE SUBMENU ACTIVE HIGHLIGHT ===")

    admin_user, _ = User.objects.get_or_create(
        username='admin_highlight_tester',
        defaults={'role': User.Role.ADMIN, 'khmer_name': 'Admin Tester'}
    )

    rf = RequestFactory()

    # 1. Test Request to Blind Scoring Portal (/examinations/standardized/blind-scoring/)
    req_blind = rf.get('/examinations/standardized/blind-scoring/')
    req_blind.user = admin_user
    # Mock resolver_match
    class MockMatch:
        url_name = 'exam_blind_scoring_portal'
    req_blind.resolver_match = MockMatch()

    ctx_blind = user_role_context(req_blind)
    active_items_blind = []
    for sec in ctx_blind['sidebar_catalog']:
        for item in sec['visible_items']:
            if item.get('is_current_active'):
                active_items_blind.append(item['key'])

    print(f"  When on Blind Scoring: Active Items = {active_items_blind}")
    assert len(active_items_blind) == 1, f"Expected 1 active item, got {len(active_items_blind)}"
    assert active_items_blind[0] == 'exam_blind_scoring_portal', f"Expected 'exam_blind_scoring_portal', got {active_items_blind[0]}"
    print("  [PASS] 1. Exactly ONE submenu highlighted on Blind Scoring page.")

    # 2. Test Request to Standardized Exam List (/examinations/standardized/)
    req_std = rf.get('/examinations/standardized/')
    req_std.user = admin_user
    class MockMatchStd:
        url_name = 'standardized_exam_list'
    req_std.resolver_match = MockMatchStd()

    ctx_std = user_role_context(req_std)
    active_items_std = []
    for sec in ctx_std['sidebar_catalog']:
        for item in sec['visible_items']:
            if item.get('is_current_active'):
                active_items_std.append(item['key'])

    print(f"  When on Standardized Exams: Active Items = {active_items_std}")
    assert len(active_items_std) == 1, f"Expected 1 active item, got {len(active_items_std)}"
    assert active_items_std[0] == 'standardized_exam_list', f"Expected 'standardized_exam_list', got {active_items_std[0]}"
    print("  [PASS] 2. Exactly ONE submenu highlighted on Standardized Exams page.")

    # 3. Test Request to Menu Permissions Portal (/accounts/settings/menu-permissions/)
    from django.test import Client
    client = Client()
    client.force_login(admin_user)
    res_perm = client.get('/accounts/settings/menu-permissions/')
    assert res_perm.status_code == 200
    html_perm = res_perm.content.decode('utf-8')
    
    # Count occurrences of active menu link inside sidebar
    import re
    active_matches = re.findall(r'class="menu-link\s+active"', html_perm)
    print(f"  When on Menu Permissions page: Rendered Active Links in HTML = {len(active_matches)}")
    assert len(active_matches) == 1, f"Expected exactly 1 active link in sidebar HTML, got {len(active_matches)}"
    # Verify no duplicate 'កំណត់សិទ្ធិ Menu' links in sidebar
    assert html_perm.count('កំណត់សិទ្ធិ Menu (Permissions)') == 0, "Hardcoded duplicate link should not exist"
    assert html_perm.count('កំណត់សិទ្ធិ Menu & Submenu') >= 1, "Dynamic menu item should be present"
    print("  [PASS] 3. Exactly ONE submenu highlighted on Menu Permissions page (No duplicate sidebar link).")

    print("=== ALL SIDEBAR ACTIVE HIGHLIGHT TESTS PASSED 100% ===")


if __name__ == '__main__':
    test_single_active_highlight()
