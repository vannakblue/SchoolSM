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
from apps.academics.models import AcademicYear

for ay in AcademicYear.objects.all():
    print(f"AY {ay.id}: '{ay.name}'")

# Request with year=all and year=3
resp = c.get('/examinations/standardized/?year=3')
content = resp.content.decode('utf-8')

# Find exam names and stats
exam_cards = re.findall(r'<a href="/examinations/standardized/(\d+)/manage/"[^>]*>\s*([^<]+)\s*</a>.*?fs-6">(\d+)</div>\s*<div class="text-muted" style="font-size: 0\.7rem;">បេក្ខជន \(ស្រី (\d+)\)</div>', content, re.DOTALL)
print(f"\nExam Cards for AY 2026-2027 (found {len(exam_cards)}):")
for ex_id, ex_name, total, fem in exam_cards:
    print(f"  Exam {ex_id}: {ex_name.strip()} -> Total: {total}, Female: {fem}")


