import os, sys, time, django
if sys.stdout and sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath('.'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

import re
from datetime import datetime, date
import openpyxl
from django.db import transaction
from django.contrib.auth.hashers import make_password
from apps.accounts.models import User
from apps.academics.models import AcademicYear, Classroom
from apps.students.models import Student
from apps.students.khmer_romanizer import romanize_khmer_name
from apps.students.views import _normalize_header, _parse_gender, _parse_date, _clean_str

file_path = r'E:\SchoolSM\2026-2027.xlsm'
t_start = time.time()

wb = openpyxl.load_workbook(file_path, data_only=True)
raw_rows = []

for sheet in wb.worksheets:
    sheet_title_clean = sheet.title.strip()
    headers = []
    found_header = False
    for r in sheet.iter_rows(values_only=True):
        if not r or not any(r):
            continue
        if not found_header:
            row_str = ' '.join([str(c) for c in r if c is not None])
            if 'ឈ្មោះ' in row_str or 'name' in row_str.lower() or 'អត្តលេខ' in row_str or 'student_id' in row_str.lower():
                headers = [_normalize_header(c) for c in r]
                found_header = True
                continue
        else:
            row_dict = {}
            for idx, val in enumerate(r):
                if idx < len(headers) and headers[idx] and val is not None and str(val).strip() != '':
                    row_dict[headers[idx]] = _clean_str(val) if not isinstance(val, (datetime, date)) else val
            if row_dict.get('khmer_name'):
                if sheet_title_clean.isdigit():
                    row_dict.setdefault('_sheet_grade', sheet_title_clean)
                raw_rows.append(row_dict)

wb.close()
t_read = time.time() - t_start
print(f"Extracted {len(raw_rows)} valid student rows from all sheets in {t_read:.2f}s!")

ay = AcademicYear.objects.filter(name='2026-2027').first() or AcademicYear.objects.filter(is_current=True).first()

# Pre-fetch existing classrooms and students
classrooms_map = {c.code.upper().strip(): c for c in Classroom.objects.filter(academic_year=ay)}
all_students = list(Student.objects.filter(academic_year=ay))
existing_by_id = {s.student_id.lower().strip(): s for s in all_students if s.student_id}
existing_by_name_dob = {(s.khmer_name.strip(), s.date_of_birth): s for s in all_students}

to_create_students = []
to_update_students = []

for idx, row in enumerate(raw_rows, start=2):
    khmer_name = row.get('khmer_name', '').strip()
    if not khmer_name:
        continue

    latin_name = str(row.get('latin_name', '')).strip()
    if not latin_name or re.search(r'[\u1780-\u17FF]', latin_name):
        latin_name = romanize_khmer_name(khmer_name)

    gender = _parse_gender(row.get('gender'))
    dob = _parse_date(row.get('date_of_birth'))
    if not dob:
        dob = date(datetime.now().year - 15, 1, 1)

    class_input = str(row.get('classroom', '')).strip()
    grade_level_val = str(row.get('grade_level') or row.get('_sheet_grade') or '').strip()
    class_letter_val = str(row.get('class_letter', '')).strip()

    if not class_input and (grade_level_val or class_letter_val):
        class_input = f"{grade_level_val}{class_letter_val}".strip()
    elif class_input and class_input.isalpha() and grade_level_val:
        class_input = f"{grade_level_val}{class_input}".strip()

    classroom = classrooms_map.get(class_input.upper())
    if not classroom and class_input and ay:
        m = re.search(r'(\d+)\s*([A-Za-z]*)', class_input)
        g_num = int(m.group(1)) if m else 10
        t_track = 'SCIENCE' if g_num in [11, 12] and class_input.upper().endswith(('A','B','C','D','E')) else ('SOCIAL' if g_num in [11, 12] else 'GENERAL')
        classroom = Classroom.objects.create(
            academic_year=ay,
            code=class_input.upper().strip(),
            name=f"ថ្នាក់ទី {class_input}".strip(),
            grade_level=g_num,
            track=t_track,
            capacity=50
        )
        classrooms_map[class_input.upper()] = classroom

    student_id_custom = str(row.get('student_id', '')).strip()
    student = None
    if student_id_custom:
        student = existing_by_id.get(student_id_custom.lower())
    if not student:
        student = existing_by_name_dob.get((khmer_name, dob))

    if student:
        student.khmer_name = khmer_name
        student.latin_name = latin_name
        student.gender = gender
        student.date_of_birth = dob
        if classroom:
            student.classroom = classroom
        student.status = 'ACTIVE'
        to_update_students.append(student)
    else:
        new_s = Student(
            student_id=student_id_custom if student_id_custom else '',
            khmer_name=khmer_name,
            latin_name=latin_name,
            gender=gender,
            date_of_birth=dob,
            classroom=classroom,
            academic_year=ay,
            status='ACTIVE'
        )
        to_create_students.append(new_s)

with transaction.atomic():
    if to_create_students:
        Student.objects.bulk_create(to_create_students, batch_size=500)
    if to_update_students:
        Student.objects.bulk_update(
            to_update_students,
            fields=['khmer_name', 'latin_name', 'gender', 'date_of_birth', 'classroom', 'status'],
            batch_size=500
        )

t_total = time.time() - t_start
print(f"Total time for {len(raw_rows)} students: {t_total:.2f} seconds!")
print(f"Created: {len(to_create_students)}, Updated: {len(to_update_students)}")
