import os
import sys
sys.path.insert(0, 'e:/SchoolSM')
sys.stdout.reconfigure(encoding='utf-8')
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from apps.examinations.models import ExamTerm

for t in ExamTerm.objects.all().order_by('academic_year', 'id'):
    print(f"ID {t.id:02d} | AY: '{t.academic_year.name}' | Name: '{t.name}' | Type: {t.term_type} | Grades: {t.term_grades.count()}")
