import os
import sys
import django

sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from apps.teachers.models import Teacher
from collections import Counter

counts = Counter(Teacher.objects.values_list('training_level', flat=True))
print("Teacher Training Level Distribution:")
for level, cnt in counts.items():
    print(f"  - '{level}': {cnt} teachers")
