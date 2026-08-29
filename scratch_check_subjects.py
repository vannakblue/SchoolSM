import os
import sys
import django

sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from apps.academics.models import Subject, GradeLevel, GradeLevelRule

print(f"=== SUBJECTS ({Subject.objects.count()}) ===")
for s in Subject.objects.all().order_by('order', 'id'):
    print(f"ID: {s.id} | Code: {s.code:4s} | Name: {s.name_kh} ({s.name_en})")

print(f"\n=== GRADE LEVELS ({GradeLevel.objects.count()}) ===")
for g in GradeLevel.objects.all().order_by('order', 'grade_number'):
    print(f"ID: {g.id} | Grade: {g.grade_number} | Track: {g.track} | Name: {g.name}")

print(f"\n=== RULES COUNT ({GradeLevelRule.objects.count()}) ===")
for r in GradeLevelRule.objects.filter(weekly_hours__gt=0):
    print(f"Subject: {r.subject.code} | Grade: {r.grade_level} {r.track} -> {r.weekly_hours} hrs")
