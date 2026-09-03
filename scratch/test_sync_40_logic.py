import os, sys, django, re
if sys.stdout and sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath('.'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from datetime import datetime, date
import openpyxl
from django.db import transaction
from apps.academics.models import AcademicYear, Classroom, Subject, ClassSubject
from apps.students.models import Student
from apps.students.khmer_romanizer import romanize_khmer_name
from apps.students.views import _normalize_header, _parse_gender, _parse_date, _clean_str
from apps.teachers.models import Teacher

def run_sync_40():
    ay, _ = AcademicYear.objects.get_or_create(
        name='2026-2027',
        defaults={
            'start_date': date(2026, 11, 1),
            'end_date': date(2027, 8, 31),
            'is_current': True
        }
    )
    AcademicYear.objects.exclude(id=ay.id).update(is_current=False)
    ay.is_current = True
    ay.save()

    # Exact 40 classrooms specification
    official_40 = [
        # Grade 7 (5 classes)
        ('7A', 7, 'GENERAL'), ('7B', 7, 'GENERAL'), ('7C', 7, 'GENERAL'), ('7D', 7, 'GENERAL'), ('7E', 7, 'GENERAL'),
        # Grade 8 (4 classes)
        ('8A', 8, 'GENERAL'), ('8B', 8, 'GENERAL'), ('8C', 8, 'GENERAL'), ('8D', 8, 'GENERAL'),
        # Grade 9 (4 classes)
        ('9A', 9, 'GENERAL'), ('9B', 9, 'GENERAL'), ('9C', 9, 'GENERAL'), ('9D', 9, 'GENERAL'),
        # Grade 10 (9 classes)
        ('10A', 10, 'GENERAL'), ('10B', 10, 'GENERAL'), ('10C', 10, 'GENERAL'), ('10D', 10, 'GENERAL'),
        ('10E', 10, 'GENERAL'), ('10F', 10, 'GENERAL'), ('10G', 10, 'GENERAL'), ('10H', 10, 'GENERAL'), ('10I', 10, 'GENERAL'),
        # Grade 11 (9 classes)
        ('11A', 11, 'SCIENCE'), ('11B', 11, 'SCIENCE'), ('11C', 11, 'SCIENCE'), ('11D', 11, 'SCIENCE'), ('11E', 11, 'SCIENCE'),
        ('11F', 11, 'SOCIAL'), ('11G', 11, 'SOCIAL'), ('11H', 11, 'SOCIAL'), ('11I', 11, 'SOCIAL'),
        # Grade 12 (9 classes)
        ('12A', 12, 'SCIENCE'), ('12B', 12, 'SCIENCE'), ('12C', 12, 'SCIENCE'), ('12D', 12, 'SCIENCE'),
        ('12E', 12, 'SOCIAL'), ('12F', 12, 'SOCIAL'), ('12G', 12, 'SOCIAL'), ('12H', 12, 'SOCIAL'), ('12I', 12, 'SOCIAL'),
    ]

    valid_codes = {item[0].upper() for item in official_40}

    # 1. Create or update the 40 official classrooms
    classrooms_map = {}
    for code, g_num, track in official_40:
        c_obj, _ = Classroom.objects.update_or_create(
            academic_year=ay,
            code=code,
            defaults={
                'name': f"ថ្នាក់ទី {code}",
                'grade_level': g_num,
                'track': track,
                'capacity': 50
            }
        )
        classrooms_map[code.upper()] = c_obj

    # 2. Re-assign or remove redundant classrooms in 2026-2027
    redundant = Classroom.objects.filter(academic_year=ay).exclude(code__in=valid_codes)
    for rc in redundant:
        # Move any students if possible or delete empty
        rc.students.update(classroom=None)
        rc.delete()

    print(f"Cleaned classrooms in 2026-2027: Exactly {Classroom.objects.filter(academic_year=ay).count()} classrooms exist.")

    # 3. Read 2026-2027.xlsm and assign students
    xlsm_path = r'E:\SchoolSM\2026-2027.xlsm'
    if os.path.exists(xlsm_path):
        wb = openpyxl.load_workbook(xlsm_path, data_only=True)
        raw_rows = []
        for sheet in wb.worksheets:
            sheet_title = sheet.title.strip()
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
                        if sheet_title.isdigit():
                            row_dict.setdefault('_sheet_grade', sheet_title)
                        raw_rows.append(row_dict)
        wb.close()

        all_students = list(Student.objects.all())
        existing_by_id = {s.student_id.lower().strip(): s for s in all_students if s.student_id}
        existing_by_name_dob = {(s.khmer_name.strip(), s.date_of_birth): s for s in all_students}

        to_create = []
        to_update = []

        for row in raw_rows:
            khmer_name = row.get('khmer_name', '').strip()
            if not khmer_name:
                continue
            latin_name = str(row.get('latin_name', '')).strip()
            if not latin_name or re.search(r'[\u1780-\u17FF]', latin_name):
                latin_name = romanize_khmer_name(khmer_name)
            gender = _parse_gender(row.get('gender'))
            dob = _parse_date(row.get('date_of_birth')) or date(datetime.now().year - 15, 1, 1)

            grade_val = str(row.get('grade_level') or row.get('_sheet_grade') or '').strip()
            letter_val = str(row.get('class_letter', '')).strip()
            class_code = f"{grade_val}{letter_val}".upper().strip()

            target_class = classrooms_map.get(class_code)

            student_id = str(row.get('student_id', '')).strip()
            s = existing_by_id.get(student_id.lower()) if student_id else None
            if not s:
                s = existing_by_name_dob.get((khmer_name, dob))

            if s:
                s.khmer_name = khmer_name
                s.latin_name = latin_name
                s.gender = gender
                s.date_of_birth = dob
                s.classroom = target_class
                s.academic_year = ay
                s.status = 'ACTIVE'
                to_update.append(s)
            else:
                new_s = Student(
                    student_id=student_id,
                    khmer_name=khmer_name,
                    latin_name=latin_name,
                    gender=gender,
                    date_of_birth=dob,
                    classroom=target_class,
                    academic_year=ay,
                    status='ACTIVE'
                )
                to_create.append(new_s)

        with transaction.atomic():
            if to_create:
                Student.objects.bulk_create(to_create, batch_size=500)
            if to_update:
                Student.objects.bulk_update(
                    to_update,
                    fields=['khmer_name', 'latin_name', 'gender', 'date_of_birth', 'classroom', 'academic_year', 'status'],
                    batch_size=500
                )
        print(f"Roster Synchronized: {len(to_create)} Created, {len(to_update)} Updated. Total Active in 2026-2027: {Student.objects.filter(academic_year=ay, status='ACTIVE').count()}")

run_sync_40()
