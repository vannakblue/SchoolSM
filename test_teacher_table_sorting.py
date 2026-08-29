import os, sys
sys.stdout.reconfigure(encoding='utf-8')
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.teachers.models import Teacher

admin_user, _ = User.objects.get_or_create(username='admin_test_sorting', defaults={'role': User.Role.ADMIN})
client = Client()
client.force_login(admin_user)

print("1. Testing GET /teachers/ (Default teacher list)...")
res = client.get('/teachers/')
assert res.status_code == 200
assert 'sortable-th' in res.content.decode('utf-8')
print("   [PASS] Default list rendered with sortable column headers!")

print("2. Testing GET /teachers/?sort=khmer_name&order=asc (Sort by Khmer Name Asc)...")
res_name_asc = client.get('/teachers/?sort=khmer_name&order=asc')
assert res_name_asc.status_code == 200
print("   [PASS] Sort by name asc executed 200 OK!")

print("3. Testing GET /teachers/?sort=khmer_name&order=desc (Sort by Khmer Name Desc)...")
res_name_desc = client.get('/teachers/?sort=khmer_name&order=desc')
assert res_name_desc.status_code == 200
print("   [PASS] Sort by name desc executed 200 OK!")

print("4. Testing GET /teachers/?sort=specialization&order=asc (Sort by Specialization)...")
res_spec = client.get('/teachers/?sort=specialization&order=asc')
assert res_spec.status_code == 200
print("   [PASS] Sort by specialization executed 200 OK!")

print("5. Testing GET /teachers/?sort=date_of_birth&order=desc (Sort by DOB)...")
res_dob = client.get('/teachers/?sort=date_of_birth&order=desc')
assert res_dob.status_code == 200
print("   [PASS] Sort by DOB executed 200 OK!")

print("6. Testing GET /teachers/?sort=state_hire_date&order=asc (Sort by State Hire Date)...")
res_hire = client.get('/teachers/?sort=state_hire_date&order=asc')
assert res_hire.status_code == 200
print("   [PASS] Sort by Hire Date executed 200 OK!")

print("\n=== ALL TEACHER TABLE HEADER SORTING TESTS PASSED 100%! ===")
