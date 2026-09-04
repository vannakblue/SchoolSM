import os
import sys
sys.path.insert(0, 'e:/SchoolSM')
sys.stdout.reconfigure(encoding='utf-8')
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from apps.academics.models import Classroom, AcademicYear
from apps.examinations.models import ExamTerm
from apps.examinations.services import AcademicResultService

ay = AcademicYear.objects.filter(name='2026-2027').first()
cls_7a = Classroom.objects.filter(academic_year=ay, name__icontains='7A').first()
print(f"Classroom: {cls_7a} (ID: {cls_7a.id if cls_7a else None}) in AY {ay}")

data = AcademicResultService.compute_semester_results(cls_7a, ay, 1)
print(f"Monthly terms count: {len(data['monthly_terms'])}")
for t in data['monthly_terms']:
    print(f"  - Term {t.id}: '{t.name}'")
