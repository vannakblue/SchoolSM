import os
import sys
sys.path.insert(0, 'e:/SchoolSM')
sys.stdout.reconfigure(encoding='utf-8')
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
import re

User = get_user_model()
admin = User.objects.filter(is_superuser=True).first()

c = Client()
c.force_login(admin)

resp = c.get('/examinations/results/semester/?classroom=147&semester=1&year=3')
content = resp.content.decode('utf-8')

# Find all monthly term header columns under sub-header
th_matches = re.findall(r'<th style="min-width: 80px;">([^<]+)</th>', content)
print('Monthly term headers in semester table for 7A:')
for i, h in enumerate(th_matches, 1):
    print(f"  Column {i}: '{h.strip()}'")
