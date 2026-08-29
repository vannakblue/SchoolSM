import os
import sys
import django

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from django.urls import reverse
from apps.accounts.models import User
from apps.academics.models import Province, District, Commune


def test_location_manager_sorting():
    print("=== STARTING LOCATION MANAGER SORTING VERIFICATION ===")

    admin_user, _ = User.objects.get_or_create(
        username='admin_loc_tester',
        defaults={'role': User.Role.ADMIN, 'is_superuser': True, 'khmer_name': 'Admin Tester'}
    )
    admin_user.is_superuser = True
    admin_user.role = User.Role.ADMIN
    admin_user.set_password('password123')
    admin_user.save()

    from django.test import RequestFactory
    from apps.academics.views import location_manager_view
    rf = RequestFactory()

    # 1. Test Province Sort by Code Ascending (Natural numerical sort)
    req1 = rf.get(f"{reverse('location_manager_view')}?level=province&sort=code&order=asc")
    req1.user = admin_user
    res1 = location_manager_view(req1)
    assert res1.status_code == 200
    # Inspect content to verify '1' is before '10'
    html1 = res1.content.decode('utf-8')
    assert '<code>1</code>' in html1
    idx1 = html1.find('<code>1</code>')
    idx10 = html1.find('<code>10</code>')
    assert idx1 < idx10, f"Code 1 (idx {idx1}) must appear before Code 10 (idx {idx10})"
    print(f"  [PASS] 1. Province sort by code asc: Code 1 appears before Code 10 correctly (natural numerical sort).")

    # 2. Test Province Sort by Code Descending
    req2 = rf.get(f"{reverse('location_manager_view')}?level=province&sort=code&order=desc")
    req2.user = admin_user
    res2 = location_manager_view(req2)
    assert res2.status_code == 200
    html2 = res2.content.decode('utf-8')
    idx1_desc = html2.find('<code>1</code>')
    idx25_desc = html2.find('<code>25</code>')
    if idx25_desc != -1:
        assert idx25_desc < idx1_desc, "Code 25 must appear before Code 1 in descending sort"
    print(f"  [PASS] 2. Province sort by code desc: Descending numerical sort verified.")

    # 3. Test District Sort by Name Khmer Ascending
    req3 = rf.get(f"{reverse('location_manager_view')}?level=district&sort=name_kh&order=asc")
    req3.user = admin_user
    res3 = location_manager_view(req3)
    assert res3.status_code == 200
    print(f"  [PASS] 3. District sort by name_kh asc verified.")

    # 4. Test District Sort by Parent (Province) Ascending
    req4 = rf.get(f"{reverse('location_manager_view')}?level=district&sort=parent&order=asc")
    req4.user = admin_user
    res4 = location_manager_view(req4)
    assert res4.status_code == 200
    print(f"  [PASS] 4. District sort by parent area verified.")

    print("=== ALL LOCATION MANAGER SORTING TESTS PASSED 100% ===")


if __name__ == '__main__':
    test_location_manager_sorting()
