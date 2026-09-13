import os
import re
import sys
import datetime
import openpyxl
from django.db import transaction
from apps.teachers.models import Teacher
from apps.academics.models import AcademicYear, Classroom, Subject, ClassSubject, GradeLevelRule, Timetable

def normalize_kh(s):
    if not s:
        return ''
    s = str(s)
    # Remove zero-width spaces and non-breaking spaces
    s = s.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '').replace('\xa0', ' ')
    # Normalize colons and signs
    s = s.replace(':', 'ៈ').replace('៖', 'ៈ')
    # Collapse duplicate whitespace
    return re.sub(r'\s+', ' ', s).strip()

def parse_classes(s):
    """
    Parses class strings like '7ABCD', '11I12EFGH', '10DFH', '8ABCD'
    into lists of class names ['7A', '7B', '7C', '7D'].
    """
    if not s:
        return []
    matches = re.findall(r'(10|11|12|[789])([A-Za-z]+)', str(s).strip())
    res = []
    for grade, letters in matches:
        for letter in letters.upper():
            res.append(f"{grade}{letter}")
    return res

# Known spelling and diacritic differences between the Excel duty files and database Teacher records
DUTY_TEACHER_NAME_MAP = {
    'ផាត ស៊្រុន': 'ផាត់ ស្រ៊ុន',
    'សុង ភស្ស': 'សុង ភ័ស',
    'សាន់ ភឿន': 'សាន់ កឿន',
    'ជួង សុភក្រ័': 'ជួង សុភ័ក្រ',
    'បូរ កញ្ញា': 'បូ កញ្ញា',
    'អឹម សំអុល': 'អ៊ឹម សំអុល',
    'ចេង ប៊ុណ្ណវេទ': 'ចេង បុណ្ណវេទ',
    'ជួ សូរិយា': 'ជួ សូរីយា',
    'សួន ស្រីរត្ត័': 'សួន ស្រីរ័ត្ន',
    'ឃុត\u200b បូរ៉ាមី': 'ឃុត បូរាមី',
    'ជឹង សុចាន់': 'ជឹង សុខចាន់',
    'មាស ស្រីល័ក្ខ': 'មាស ស្រីលក្ខ័',
    'លន ស្រីល័ក្ខ': 'លន ស្រីលក្ខ័',
    'ទិត សាម៉នវីរ:': 'ទិត សោម៉នវីរៈ',
    'ផាត់ ចាន់សុផាណា': 'ផាត់ ចាន់សុផាន់ណា',
    'ហេងសាន សុផានី': 'ហេង សានសុផានី',
    'ប្រាក់ សុភារ:': 'ប្រាក់ សុភារៈ',
    'ឆេង\u200b សុជាតា': 'ឆេង សុជាតា',
}

# Standard 104 teacher order duty prefix map (when Excel does not have code column)
ORDERED_104_DUTY_CODES = (
    ['M'] * 11 +       # M1..M11
    ['P'] * 7 +        # P1..P7
    ['C'] * 7 +        # C1..C7
    ['B'] * 6 +        # B1..B6
    ['ES'] * 4 +       # ES1..ES4
    ['H'] * 6 +        # H1..H6
    ['G'] * 6 +        # G1..G6
    ['EC'] * 3 +       # EC1..EC3
    ['HE'] * 4 +       # HE1..HE4
    ['I'] * 7 +        # I1..I7
    ['K'] * 16 +       # K1..K16
    ['E'] * 8 +        # E1..E8
    ['ED'] * 11 +      # ED1..ED11
    ['AG'] * 8         # AG1..AG8
)

PREFIX_TO_SUBCODE = {
    'M': 'M',
    'P': 'P',
    'C': 'C',
    'B': 'B',
    'ES': 'Es',
    'H': 'H',
    'G': 'G',
    'I9G': 'G',
    'EC': 'Ec',
    'HE': 'He',
    'I': 'I',
    'K': 'K',
    'E': 'E',
    'ED': 'ED',
    'AG': 'AG',
}

STANDARD_PERIOD_TIMES = {
    1: (datetime.time(7, 0), datetime.time(7, 50)),
    2: (datetime.time(7, 55), datetime.time(8, 45)),
    3: (datetime.time(9, 5), datetime.time(9, 55)),
    4: (datetime.time(10, 0), datetime.time(10, 50)),
    5: (datetime.time(13, 0), datetime.time(13, 50)),
    6: (datetime.time(13, 55), datetime.time(14, 45)),
    7: (datetime.time(15, 5), datetime.time(15, 55)),
    8: (datetime.time(16, 0), datetime.time(16, 50)),
}

def find_teacher_in_db(raw_name, db_teachers=None):
    if not raw_name:
        return None
    if db_teachers is None:
        db_teachers = list(Teacher.objects.all())

    raw_clean = str(raw_name).strip()
    target = DUTY_TEACHER_NAME_MAP.get(raw_clean, raw_clean)
    target_norm = normalize_kh(target)
    target_nospc = target_norm.replace(' ', '')

    # 1. Exact match with mapped or raw name
    for t in db_teachers:
        if t.khmer_name and t.khmer_name.strip() == target:
            return t

    # 2. Normalized match (ignoring whitespace differences & zero-width characters)
    for t in db_teachers:
        if not t.khmer_name:
            continue
        t_norm = normalize_kh(t.khmer_name)
        if t_norm == target_norm or t_norm.replace(' ', '') == target_nospc:
            return t

    return None

def import_teacher_duty_from_excel(file_or_path, target_academic_year=None):
    """
    Imports teacher duty assignments from an Excel workbook (.xlsx) into the database.
    Can accept a file path or a Django UploadedFile / BytesIO stream.
    Supports both:
      - 'បំណែងចែកគ្រូ2027.xlsx' format (3 columns: Name, Gender, Classes)
      - 'data.xlsx' format (5 columns: ID, Code, Name, Gender, Classes)
    """
    results = {
        'success': False,
        'academic_year': None,
        'teachers_assigned': 0,
        'class_subjects_created': 0,
        'class_subjects_updated': 0,
        'timetable_created': 0,
        'timetable_updated': 0,
        'warnings': [],
        'errors': []
    }

    try:
        wb = openpyxl.load_workbook(file_or_path, data_only=True)
    except Exception as e:
        results['errors'].append(f"មិនអាចបើកឯកសារ Excel បានឡើយ៖ {str(e)}")
        return results

    # 1. Determine Target Academic Year
    ay = target_academic_year
    if not ay:
        ay = AcademicYear.objects.filter(is_current=True).first()
    if not ay:
        ay = AcademicYear.objects.filter(name__icontains='2026-2027').first()
    if not ay:
        ay = AcademicYear.objects.order_by('-start_date').first()

    if not ay:
        results['errors'].append("រកមិនឃើញឆ្នាំសិក្សាសកម្ម (Active Academic Year) ក្នុងប្រព័ន្ធឡើយ!")
        return results

    results['academic_year'] = ay.name

    # 2. Classrooms Map for this academic year
    classrooms_qs = Classroom.objects.filter(academic_year=ay)
    classrooms_map = {}
    for c in classrooms_qs:
        short_name = c.name.replace('ថ្នាក់ទី ', '').strip()
        classrooms_map[short_name] = c

    # 3. Ensure Subject instances exist for ED (Physical Ed) and AG (Agriculture/Tech)
    sub_ed, _ = Subject.objects.get_or_create(
        code='ED',
        defaults={'name_kh': 'អប់រំកាយ និងកីឡា', 'name_en': 'Physical Education & Sport', 'order': 15}
    )
    sub_ag, _ = Subject.objects.get_or_create(
        code='AG',
        defaults={'name_kh': 'កសិកម្ម', 'name_en': 'Agriculture & Tech', 'order': 16}
    )

    subjects_by_code = {s.code: s for s in Subject.objects.all()}
    sub_r = subjects_by_code.get('R')
    sub_d = subjects_by_code.get('D')

    # Ensure GradeLevelRules exist for ED and AG across grades 7 to 12
    for g in [7, 8, 9, 10, 11, 12]:
        for track in ['GENERAL', 'SCIENCE', 'SOCIAL']:
            GradeLevelRule.objects.get_or_create(
                subject=sub_ed, grade_level=g, track=track,
                defaults={'weekly_hours': 2, 'order': 15}
            )
            GradeLevelRule.objects.get_or_create(
                subject=sub_ag, grade_level=g, track=track,
                defaults={'weekly_hours': 2, 'order': 16}
            )

    # 4. Parse Duty Sheet
    sheet_name = 'duty' if 'duty' in wb.sheetnames else wb.sheetnames[0]
    ws_duty = wb[sheet_name]
    raw_rows = list(ws_duty.iter_rows(values_only=True))

    if not raw_rows:
        results['errors'].append("ឯកសារ Excel គ្មានទិន្នន័យក្នុង Sheet ឡើយ!")
        return results

    # Determine header offset and layout
    # Check first row to see if it's headers or data
    first_row = [str(x or '').strip() for x in raw_rows[0]]
    has_header = any(h in first_row for h in ['ឈ្មោះ', 'គោត្តនាម', 'កូដ', 'Code', 'Name', 'ថ្នាក់'])
    data_rows = raw_rows[1:] if has_header else raw_rows

    db_teachers = list(Teacher.objects.all())
    duty_records = []

    for row_idx, r in enumerate(data_rows):
        if not r or not any(r):
            continue

        # Check if 5-column layout (ID, Code, Name, Gender, Classes)
        # or 3-column layout (Name, Gender, Classes)
        code = None
        raw_name = None
        classes_str = ''

        if len(r) >= 5 and r[1] and re.match(r'^(M|P|C|B|ES|H|G|EC|HE|I|K|E|ED|AG|I9G)\d+', str(r[1]).strip(), re.I):
            code = str(r[1]).strip().upper()
            raw_name = str(r[2] or '').strip()
            classes_str = str(r[4] or '').strip()
        elif len(r) >= 3:
            # Check if col 0 or col 1 is the name
            val0 = str(r[0] or '').strip()
            val2 = str(r[2] or '').strip()
            # If val2 looks like classes (e.g. 7ABCD, 10DFH...)
            if re.search(r'\d+[A-Za-z]+', val2):
                raw_name = val0
                classes_str = val2
            elif len(r) >= 5:
                raw_name = str(r[2] or '').strip()
                classes_str = str(r[4] or '').strip()
            else:
                raw_name = val0
                classes_str = str(r[1] or '').strip()

        if not raw_name:
            continue

        t_obj = find_teacher_in_db(raw_name, db_teachers)
        if not t_obj:
            results['warnings'].append(f"ជួរទី {row_idx + 1}: មិនអាចស្វែងរកគ្រូឈ្មោះ «{raw_name}» ក្នុងប្រព័ន្ធបានឡើយ")
            continue

        # Determine subject code
        sub_code = None
        if code:
            if code.startswith('I9G'):
                prefix = 'G'
            else:
                m_pfx = re.match(r'^([A-Za-z]+)', code)
                prefix = m_pfx.group(1).upper() if m_pfx else ''
            sub_code = PREFIX_TO_SUBCODE.get(prefix)
        else:
            # Fallback to standard 104 order if index matches
            if row_idx < len(ORDERED_104_DUTY_CODES):
                prefix = ORDERED_104_DUTY_CODES[row_idx]
                sub_code = PREFIX_TO_SUBCODE.get(prefix)
            elif t_obj.specialization:
                # Deduce from specialization
                spec = t_obj.specialization
                for pfx, sc in PREFIX_TO_SUBCODE.items():
                    sub = subjects_by_code.get(sc)
                    if sub and (sub.name_kh in spec or spec in sub.name_kh):
                        sub_code = sc
                        break

        subject_obj = subjects_by_code.get(sub_code)
        if not subject_obj:
            results['warnings'].append(f"មិនអាចកំណត់មុខវិជ្ជាសម្រាប់គ្រូ {t_obj.khmer_name} (Code: {code})")
            continue

        c_list = parse_classes(classes_str)

        duty_records.append({
            'row': row_idx + 1,
            'code': code or f"{sub_code}{row_idx+1}",
            'subject': subject_obj,
            'teacher': t_obj,
            'classes': c_list,
        })

    if not duty_records:
        results['errors'].append("ពុំមានទិន្នន័យចាត់តាំងត្រឹមត្រូវណាមួយត្រូវបានរកឃើញក្នុងឯកសារឡើយ!")
        return results

    # 5. Database Save in Atomic Transaction
    with transaction.atomic():
        assigned_teachers = set()
        cs_created = 0
        cs_updated = 0

        for rec in duty_records:
            t_obj = rec['teacher']
            sub_obj = rec['subject']
            assigned_teachers.add(t_obj.id)

            # Sync max weekly hours according to pedagogical training level
            if t_obj.training_level and 'ទុតិយភូមិ' in t_obj.training_level:
                t_obj.max_weekly_hours = 16
            else:
                t_obj.max_weekly_hours = 18
            t_obj.save(update_fields=['max_weekly_hours'])

            for c_name in rec['classes']:
                cls_obj = classrooms_map.get(c_name)
                if not cls_obj:
                    continue

                cs, created = ClassSubject.objects.update_or_create(
                    classroom=cls_obj,
                    subject=sub_obj,
                    defaults={'teacher': t_obj}
                )
                if created:
                    cs_created += 1
                else:
                    cs_updated += 1

                # If Khmer (K) and lower secondary, also assign R and D
                if sub_obj.code == 'K' and cls_obj.grade_level in [7, 8, 9]:
                    if sub_r:
                        ClassSubject.objects.update_or_create(
                            classroom=cls_obj,
                            subject=sub_r,
                            defaults={'teacher': t_obj}
                        )
                    if sub_d:
                        ClassSubject.objects.update_or_create(
                            classroom=cls_obj,
                            subject=sub_d,
                            defaults={'teacher': t_obj}
                        )

        results['teachers_assigned'] = len(assigned_teachers)
        results['class_subjects_created'] = cs_created
        results['class_subjects_updated'] = cs_updated

        # 6. If workbook contains GT sheet (timetable slots), sync timetable slots
        if 'GT' in wb.sheetnames:
            ws_gt = wb['GT']
            headers = [c for c in ws_gt[1]]
            col_slot_map = {}
            day_kh_map = {'ច': 1, 'អ': 2, 'ព': 3, 'ព្រ': 4, 'សុ': 5, 'ស': 6}
            for col_idx, cell in enumerate(headers):
                val = str(cell.value or '').strip()
                m = re.match(r'^(ច|អ|ព|ព្រ|សុ|ស)(\d+)$', val)
                if m:
                    d_kh, p_num = m.group(1), int(m.group(2))
                    d_num = day_kh_map.get(d_kh, 1)
                    col_slot_map[col_idx] = (d_num, p_num)

            duty_by_code = {rec['code'].upper(): rec for rec in duty_records}
            tt_created = 0
            tt_updated = 0

            for r in ws_gt.iter_rows(min_row=2, values_only=True):
                cname = str(r[0] or '').strip()
                cls_obj = classrooms_map.get(cname)
                if not cls_obj:
                    continue

                for col_idx, (d_num, p_num) in col_slot_map.items():
                    if col_idx < len(r):
                        token = str(r[col_idx] or '').strip().upper()
                        if not token or token == 'NONE':
                            continue
                        rec = duty_by_code.get(token)
                        if rec:
                            st_time, et_time = STANDARD_PERIOD_TIMES.get(p_num, (datetime.time(7, 0), datetime.time(7, 50)))
                            tt_entry, created = Timetable.objects.update_or_create(
                                classroom=cls_obj,
                                day_of_week=d_num,
                                period_number=p_num,
                                defaults={
                                    'subject': rec['subject'],
                                    'teacher': rec['teacher'],
                                    'start_time': st_time,
                                    'end_time': et_time,
                                }
                            )
                            if created:
                                tt_created += 1
                            else:
                                tt_updated += 1

            results['timetable_created'] = tt_created
            results['timetable_updated'] = tt_updated

        results['success'] = True

    return results
