import os
import sys
import django

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from django.urls import reverse
from apps.accounts.models import User
from apps.accounts.menu_registry import MENU_SECTIONS_CATALOG

admin_u = User.objects.filter(role=User.Role.ADMIN).first()
client = Client()
client.force_login(admin_u)

failed_routes = []
passed_routes = []

for sec in MENU_SECTIONS_CATALOG:
    print(f"\n=== Section: {sec['name_kh']} ({sec['name_en']}) ===")
    for item in sec.get('items', []):
        url_name = item.get('url_name')
        if not url_name:
            continue
        try:
            url = reverse(url_name)
            res = client.get(url, follow=True)
            if res.status_code == 200:
                print(f"  [200 OK] {item['name_kh']} -> {url}")
                passed_routes.append((item['name_kh'], url))
            else:
                print(f"  [FAILED {res.status_code}] {item['name_kh']} -> {url}")
                failed_routes.append((item['name_kh'], url, f"Status {res.status_code}"))
        except Exception as e:
            print(f"  [ERROR] {item['name_kh']} ({url_name}): {e}")
            failed_routes.append((item['name_kh'], url_name, str(e)))

print("\n" + "="*60)
print(f"TOTAL PASSED: {len(passed_routes)}")
print(f"TOTAL FAILED: {len(failed_routes)}")
if failed_routes:
    print("\nFAILED ROUTES DETAILS:")
    for name, url, err in failed_routes:
        print(f" - {name} ({url}): {err}")
print("="*60)
