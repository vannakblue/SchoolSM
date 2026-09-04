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
print(f"Academic year: {ay} (ID: {ay.id if ay else None})")

terms = ExamTerm.objects.filter(academic_year=ay).order_by('semester', 'start_date', 'id')
print(f"Total terms for {ay}: {terms.count()}\n")
for t in terms:
    print(f"ID: {t.id:03d} | Name: '{t.name}' | TermType: {t.term_type} | Semester: {t.semester} | is_counted: {t.is_counted_in_semester} | start: {t.start_date} | end: {t.end_date}")
