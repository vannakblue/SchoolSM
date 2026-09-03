import os, sys, time, django
if sys.stdout and sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

import openpyxl
from apps.academics.models import AcademicYear, Classroom
from apps.students.models import Student
from apps.students.khmer_romanizer import romanize_khmer_name

file_path = r'E:\SchoolSM\2026-2027.xlsm'
t0 = time.time()
wb = openpyxl.load_workbook(file_path, data_only=True)
t_load = time.time() - t0
print(f"Workbook loaded in {t_load:.2f}s across sheets: {wb.sheetnames}")

ay = AcademicYear.objects.filter(name='2026-2027').first() or AcademicYear.objects.filter(is_current=True).first()

# Pre-fetch existing classrooms and students
classrooms_map = {c.code.upper().strip(): c for c in Classroom.objects.filter(academic_year=ay)}
existing_by_id = {s.student_id.lower().strip(): s for s in Student.objects.all() if s.student_id}

print(f"Pre-fetched {len(classrooms_map)} classrooms and {len(existing_by_id)} existing students.")
