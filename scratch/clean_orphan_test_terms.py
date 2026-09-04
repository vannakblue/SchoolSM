import os
import sys
sys.path.insert(0, 'e:/SchoolSM')
sys.stdout.reconfigure(encoding='utf-8')
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from apps.examinations.models import ExamTerm
from apps.academics.models import AcademicYear

test_term_ids = [4, 6, 8, 14, 5, 7, 9, 15]
qs = ExamTerm.objects.filter(id__in=test_term_ids)
print(f"Found {qs.count()} orphan test terms to delete:")
for t in qs:
    print(f"  - Term ID {t.id:02d}: '{t.name}' (Type: {t.term_type})")

deleted_count, _ = qs.delete()
print(f"\nSuccessfully deleted {deleted_count} orphan test terms.")

ay = AcademicYear.objects.filter(name='2026-2027').first()
remaining = ExamTerm.objects.filter(academic_year=ay).order_by('id')
print(f"\nRemaining legitimate ExamTerms for {ay}:")
for t in remaining:
    print(f"  - Term ID {t.id:02d}: '{t.name}' (Type: {t.term_type}, is_counted: {t.is_counted_in_semester})")
