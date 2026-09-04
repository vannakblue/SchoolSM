import os
import sys
sys.path.insert(0, 'e:/SchoolSM')
sys.stdout.reconfigure(encoding='utf-8')
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from apps.examinations.models import ExamTerm
from apps.academics.models import AcademicYear

ay = AcademicYear.objects.filter(name='2026-2027').first()
terms = ExamTerm.objects.filter(academic_year=ay).order_by('id')

for t in terms:
    grades_count = t.term_grades.count()
    exams_count = t.standardized_exams.count()
    print(f"Term ID {t.id:02d} | Name: '{t.name}' | Type: {t.term_type} | Grades: {grades_count} | StandardizedExams: {exams_count} | created: {t.created_at}")
