import os
import sys
sys.path.insert(0, 'e:/SchoolSM')
sys.stdout.reconfigure(encoding='utf-8')
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from apps.examinations.models import ExamTerm

for tid in [4, 6, 8, 14, 5, 7, 9, 15]:
    t = ExamTerm.objects.filter(id=tid).first()
    if t:
        print(f"Term {t.id} '{t.name}': exclusions={t.student_exclusions.count()}, subject_settings={t.subject_settings.count()}")
