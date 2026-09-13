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

CODE_TO_TEACHER_NAME_MAP = {
    'M1': 'កាន ដាវី',
    'M2': 'សា ប៊ុនថន',
    'M3': 'យ៉ន ណារ៉ា',
    'M4': 'ផេង លាងឃន',
    'M5': 'លឿង រក្សា',
    'M6': 'ឡុច សាវិន',
    'M7': 'យ៉ន សីហា',
    'M8': 'សេង សុសៅគន្ធ',
    'M9': 'ប៊ុន ឡាង',
    'M10': 'សួន ច័ន្ទសុធី',
    'M11': 'ផាត់ ស្រ៊ុន',
    'P1': 'ផល ឌីណា',
    'P2': 'ណុំ ស្រីណែត',
    'P3': 'សុង ភ័ស',
    'P4': 'កែវ សុគន្ធារី',
    'P5': 'សាន់ កឿន',
    'P6': 'ជួង សុភ័ក្រ',
    'P7': 'វិន ភារុន',
    'C1': 'ដុក ណាសួន',
    'C2': 'ឯក អមរា',
    'C3': 'គង់ ម៉ានិន',
    'C4': 'ហន ស៊ីដារ៉ា',
    'C5': 'ពៅ ស៊ីនាង',
    'C6': 'បូ កញ្ញា',
    'C7': 'ក្រឹង ចន្ថា',
    'B1': 'សំ ពិសី',
    'B2': 'ជៃ ស្រីពៅ',
    'B3': 'អ៊ឹម សំអុល',
    'B4': 'អ៊ិន ឆាយ',
    'B5': 'ហៀង សេងហៃ',
    'B6': 'ឈឿន លីឆាយ',
    'ES1': 'វ៉ាន់ ម៉ាលីស',
    'ES2': 'ហេង សានសុផានី',
    'ES3': 'មូល គន្ធា',
    'ES4': 'សុខ ស្រីនាង',
    'H1': 'សុន វាសនា',
    'H2': 'ឈាង ចាន់រ៉ា',
    'H3': 'សួរ ចន្ទ្រា',
    'H4': 'ឃឹម ស្រស់',
    'H5': 'អេង រតនា',
    'H6': 'ស៊ុំ វ៉េង',
    'I9G1': 'ទឹម ប៊ុនធន',
    'G2': 'ចេង បុណ្ណវេទ',
    'G3': 'ហេង កន្យា',
    'G4': 'ជួ សូរីយា',
    'G5': 'សួន ស្រីរ័ត្ន',
    'G6': 'សុទ្ធ ចរិយា',
    'EC1': 'ប៊ុន សម្បត្តិ',
    'EC2': 'ពូន រចនា',
    'EC3': 'ហ៊ូ រ៉ន',
    'HE1': 'យ៉េន ចាន់នី',
    'HE2': 'យ៉េន ចាន់ណាក់',
    'HE3': 'ហេង សានម៉ូណាវី',
    'HE4': 'សែត រុនស្រី',
    'I1': 'ពឺន ពិដោរ',
    'I2': 'ឆេង សុដានី',
    'I3': 'គង់ សម្បត្តិ',
    'I4': 'អាន ចាន់ថា',
    'I5': 'យ៉ាង សុផាន',
    'I6': 'សូកាន លក្ខិណា',
    'I7': 'ផន កុសល',
    'K1': 'យូ ម៉ាលីស',
    'K2': 'ឃុត បូរាមី',
    'K3': 'ជឹង សុខចាន់',
    'K4': 'ប៉ន ផល្លី',
    'K5': 'ប្រាក់ សារិន',
    'K6': 'ហួត លក្ខិណា',
    'K7': 'សុន ឌីម៉ង់',
    'K8': 'ដួង ពិសេស',
    'K9': 'ដួង ពិសាល',
    'K10': 'មាស ស្រីលក្ខ័',
    'K11': 'ណុប វ៉ាង',
    'K12': 'ខឹម សុផា',
    'K13': 'ហេង  ឃាង',
    'K14': 'លន ស្រីលក្ខ័',
    'K15': 'ខៀវ ខេមរិន្ទ',
    'K16': 'គាន  ហ៊ឺ',
    'E1': 'ចាន់  ធី',
    'E2': 'អោម សុខុម',
    'E3': 'អ៊ុយ វាសនា',
    'E4': 'ឃុន សុម៉ាឡា',
    'E5': 'ថោង ធីតា',
    'E6': 'ទិត សោម៉នវីរៈ',
    'E7': 'អៀ សេរីពង្ស',
    'E8': 'ប្រាក់ សុភារៈ',
    'ED1': 'ឆេង សុជាតា',
    'ED2': 'នាង ជំនិត',
    'ED3': 'សួស  សុខឃៀង',
    'ED4': 'ម៉ង់ ប៊ុនណារិទ្ធ',
    'ED5': 'សុខា សាមឌី',
    'ED6': 'ជៀស ឌីនីន',
    'ED7': 'ផន សុផារិទ្ធ',
    'ED8': 'មៀច ដាវណ្ណ',
    'ED9': 'ផន ពុទ្ធាវី',
    'ED10': 'ផាត់ ចាន់សុផាន់ណា',
    'ED11': 'ឌុច វិសាល',
    'AG1': 'ជុំ សុផន',
    'AG2': 'ងួន គ្រីន',
    'AG3': 'ចេង ចំរើន',
    'AG4': 'ឡេង សេស',
    'AG5': 'លី ហួត',
    'AG6': 'ហុង សំអឿន',
    'AG7': 'ជឹម នី',
    'AG8': 'សឿន សម្បត្តិ',
    'COM2': 'ឃុន សុម៉ាឡា',
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

        # Check layout:
        # 1. New 2027 layout: Col 0 is Code (M1..AG8), Col 1 is Name, Col 2 is Gender, Col 3 is Classes
        # 2. 5-column layout: Col 0 is ID, Col 1 is Code, Col 2 is Name, Col 3 is Gender, Col 4 is Classes
        # 3. 3-column layout without code: Col 0 is Name, Col 1 is Gender, Col 2 is Classes
        code = None
        raw_name = None
        classes_str = ''

        val0 = str(r[0] or '').strip()
        val1 = str(r[1] or '').strip() if len(r) > 1 else ''

        if re.match(r'^(M|P|C|B|ES|H|G|EC|HE|I|K|E|ED|AG|I9G)\d+', val0, re.I):
            code = val0.upper()
            raw_name = val1
            if len(r) >= 4:
                classes_str = str(r[3] or '').strip()
            elif len(r) >= 3:
                classes_str = str(r[2] or '').strip()
        elif len(r) >= 5 and re.match(r'^(M|P|C|B|ES|H|G|EC|HE|I|K|E|ED|AG|I9G)\d+', val1, re.I):
            code = val1.upper()
            raw_name = str(r[2] or '').strip()
            classes_str = str(r[4] or '').strip()
        elif len(r) >= 3:
            val2 = str(r[2] or '').strip()
            if re.search(r'\d+[A-Za-z]+', val2):
                raw_name = val0
                classes_str = val2
            elif len(r) >= 5:
                raw_name = str(r[2] or '').strip()
                classes_str = str(r[4] or '').strip()
            else:
                raw_name = val0
                classes_str = val1

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
        from apps.academics.models import SavedDefaultConfig
        assigned_teachers = set()
        teacher_duty_codes_map = {}
        cs_created = 0
        cs_updated = 0

        for rec in duty_records:
            t_obj = rec['teacher']
            sub_obj = rec['subject']
            duty_code = rec['code']
            assigned_teachers.add(t_obj.id)

            # Permanently update teacher subject_code in DB
            t_obj.subject_code = duty_code
            if t_obj.training_level and 'ទុតិយភូមិ' in t_obj.training_level:
                t_obj.max_weekly_hours = 16
            else:
                t_obj.max_weekly_hours = 18
            t_obj.save(update_fields=['subject_code', 'max_weekly_hours'])

            teacher_duty_codes_map[str(t_obj.id)] = duty_code
            teacher_duty_codes_map[f"{sub_obj.id}_{t_obj.id}"] = duty_code

            for c_name in rec['classes']:
                cls_obj = classrooms_map.get(c_name)
                if not cls_obj:
                    continue

                cs, created = ClassSubject.objects.update_or_create(
                    classroom=cls_obj,
                    subject=sub_obj,
                    defaults={'teacher': t_obj, 'teacher_code': duty_code}
                )
                if created:
                    cs_created += 1
                else:
                    cs_updated += 1
                    if cs.teacher_code != duty_code:
                        cs.teacher_code = duty_code
                        cs.save(update_fields=['teacher_code'])

                # If Khmer (K) and lower secondary, also assign R and D
                if sub_obj.code == 'K' and cls_obj.grade_level in [7, 8, 9]:
                    if sub_r:
                        cs_r, _ = ClassSubject.objects.update_or_create(
                            classroom=cls_obj,
                            subject=sub_r,
                            defaults={'teacher': t_obj, 'teacher_code': duty_code}
                        )
                    if sub_d:
                        cs_d, _ = ClassSubject.objects.update_or_create(
                            classroom=cls_obj,
                            subject=sub_d,
                            defaults={'teacher': t_obj, 'teacher_code': duty_code}
                        )

        # Permanently store full duty code map in SavedDefaultConfig
        SavedDefaultConfig.objects.update_or_create(
            key='teacher_subject_duty_codes',
            defaults={'data': teacher_duty_codes_map}
        )

        results['teachers_assigned'] = len(assigned_teachers)
        results['class_subjects_created'] = cs_created
        results['class_subjects_updated'] = cs_updated

        # 6. If workbook contains GT sheet (timetable slots), sync master timetable
        if 'GT' in wb.sheetnames:
            gt_res = import_timetable_from_gt_sheet(file_or_path, target_academic_year=ay)
            results['timetable_created'] = gt_res.get('slots_created', 0)
            results['timetable_updated'] = gt_res.get('slots_updated', 0)
            results['timetable_total'] = gt_res.get('slots_total', 0)
            if gt_res.get('warnings'):
                results['warnings'].extend(gt_res['warnings'])

        results['success'] = True

    return results


def import_timetable_from_gt_sheet(file_or_path, target_academic_year=None):
    """
    Imports master timetable slots from sheet 'GT' in the workbook
    and saves them directly into Timetable and ClassSubject in the database,
    synchronizing with Academic Year 2026-2027.
    """
    results = {
        'success': False,
        'academic_year': None,
        'slots_created': 0,
        'slots_updated': 0,
        'slots_total': 0,
        'classrooms_count': 0,
        'class_subjects_synced': 0,
        'errors': [],
        'warnings': []
    }

    try:
        wb = openpyxl.load_workbook(file_or_path, data_only=True)
    except Exception as e:
        results['errors'].append(f"មិនអាចបើកឯកសារ Excel បានឡើយ៖ {str(e)}")
        return results

    if 'GT' not in wb.sheetnames:
        results['errors'].append("រកមិនឃើញ Sheet 'GT' ក្នុងឯកសារ Excel ឡើយ!")
        return results

    # 1. Active Academic Year
    ay = target_academic_year
    if not ay:
        ay = AcademicYear.objects.filter(is_current=True).first()
    if not ay:
        ay = AcademicYear.objects.filter(name__icontains='2026-2027').first()
    if not ay:
        ay = AcademicYear.objects.order_by('-start_date').first()

    if not ay:
        results['errors'].append("រកមិនឃើញឆ្នាំសិក្សាសកម្មក្នុងប្រព័ន្ធឡើយ!")
        return results

    results['academic_year'] = ay.name

    # 2. Classrooms Map
    classrooms_qs = Classroom.objects.filter(academic_year=ay)
    classrooms_map = {}
    for c in classrooms_qs:
        short_name = c.name.replace('ថ្នាក់ទី ', '').strip()
        classrooms_map[short_name] = c

    results['classrooms_count'] = len(classrooms_map)

    # 3. Ensure Subject instances exist
    sub_ed, _ = Subject.objects.get_or_create(
        code='ED',
        defaults={'name_kh': 'អប់រំកាយ និងកីឡា', 'name_en': 'Physical Education & Sport', 'order': 15}
    )
    sub_ag, _ = Subject.objects.get_or_create(
        code='AG',
        defaults={'name_kh': 'កសិកម្ម', 'name_en': 'Agriculture & Tech', 'order': 16}
    )
    sub_ict, _ = Subject.objects.get_or_create(
        code='ICT',
        defaults={'name_kh': 'ព័ត៌មានវិទ្យា', 'name_en': 'Information & Communication Technology', 'order': 17}
    )

    subjects_by_code = {s.code: s for s in Subject.objects.all()}
    db_teachers = list(Teacher.objects.all())
    teachers_by_code = {t.subject_code.upper(): t for t in Teacher.objects.filter(subject_code__isnull=False).exclude(subject_code='')}

    # Automatically resolve and permanently save subject_code in DB for all teachers from CODE_TO_TEACHER_NAME_MAP
    for code, tname in CODE_TO_TEACHER_NAME_MAP.items():
        if code not in teachers_by_code:
            t_found = find_teacher_in_db(tname, db_teachers)
            if t_found:
                if t_found.subject_code != code:
                    t_found.subject_code = code
                    t_found.save(update_fields=['subject_code'])
                teachers_by_code[code] = t_found

    t_com = teachers_by_code.get('COM2') or Teacher.objects.filter(specialization__icontains='កុំព្យូទ័រ').first() or Teacher.objects.filter(khmer_name='ឃុន សុម៉ាឡា').first()
    if t_com and 'COM2' not in teachers_by_code:
        teachers_by_code['COM2'] = t_com

    ws_gt = wb['GT']
    rows = list(ws_gt.iter_rows(values_only=True))
    if not rows or len(rows) < 2:
        results['errors'].append("Sheet 'GT' គ្មានទិន្នន័យគ្រប់គ្រាន់ឡើយ!")
        return results

    headers = rows[0]
    day_kh_map = {'ច': 1, 'អ': 2, 'ព': 3, 'ព្រ': 4, 'សុ': 5, 'ស': 6}
    day_room_cols = {1: 5, 2: 15, 3: 25, 4: 35, 5: 45, 6: 55}

    col_slot_map = {}
    for col_idx, val in enumerate(headers):
        if val:
            m = re.match(r'^(ច|អ|ព|ព្រ|សុ|ស)(\d+)$', str(val).strip())
            if m:
                d_num = day_kh_map.get(m.group(1), 1)
                p_num = int(m.group(2))
                col_slot_map[col_idx] = (d_num, p_num)

    tt_created = 0
    tt_updated = 0
    cs_synced = 0
    active_slot_keys = set()
    matrix_items = []

    with transaction.atomic():
        for r in rows[1:]:
            if not r or not r[0]:
                continue
            cname = str(r[0]).strip()
            cls_obj = classrooms_map.get(cname)
            if not cls_obj:
                results['warnings'].append(f"ថ្នាក់ '{cname}' មិនមានក្នុងប្រព័ន្ធឆ្នាំសិក្សា {ay.name}")
                continue

            # Sync Classroom room_number if found in row
            row_room = None
            for r_col in day_room_cols.values():
                if r_col < len(r) and r[r_col] and str(r[r_col]).strip() not in ['', 'None']:
                    row_room = str(r[r_col]).strip()
                    break
            if row_room:
                target_room_str = f"បន្ទប់ {row_room}"
                if cls_obj.room_number != target_room_str:
                    cls_obj.room_number = target_room_str
                    cls_obj.save(update_fields=['room_number'])

            for col_idx, (d_num, p_num) in col_slot_map.items():
                if col_idx >= len(r):
                    continue
                raw_val = r[col_idx]
                if not raw_val or str(raw_val).strip() in ['', 'None']:
                    continue
                tok = str(raw_val).strip().upper()

                # Determine room number for this day
                room_col = day_room_cols.get(d_num)
                room_val = ''
                if room_col is not None and room_col < len(r) and r[room_col]:
                    room_val = str(r[room_col]).strip()

                # Determine Teacher and Subject
                t_obj = None
                sub_obj = None
                if tok == 'COM2':
                    t_obj = t_com
                    sub_obj = sub_ict
                else:
                    t_obj = teachers_by_code.get(tok)
                    if not t_obj and tok in CODE_TO_TEACHER_NAME_MAP:
                        t_obj = find_teacher_in_db(CODE_TO_TEACHER_NAME_MAP[tok], db_teachers)
                        if t_obj:
                            t_obj.subject_code = tok
                            t_obj.save(update_fields=['subject_code'])
                            teachers_by_code[tok] = t_obj
                    if not t_obj:
                        results['warnings'].append(f"មិនស្គាល់កូដគ្រូ '{tok}' សម្រាប់ថ្នាក់ {cname} ថ្ងៃ {d_num} ម៉ោង {p_num}")
                        continue
                    pfx = 'G' if tok.startswith('I9G') else re.match(r'^([A-Za-z]+)', tok).group(1).upper()
                    sc = PREFIX_TO_SUBCODE.get(pfx)
                    sub_obj = subjects_by_code.get(sc)

                if not t_obj or not sub_obj:
                    continue

                st_time, et_time = STANDARD_PERIOD_TIMES.get(p_num, (datetime.time(7, 0), datetime.time(7, 50)))

                tt_entry, created = Timetable.objects.update_or_create(
                    classroom=cls_obj,
                    day_of_week=d_num,
                    period_number=p_num,
                    defaults={
                        'subject': sub_obj,
                        'teacher': t_obj,
                        'start_time': st_time,
                        'end_time': et_time,
                        'room': room_val if room_val else None,
                    }
                )
                if created:
                    tt_created += 1
                else:
                    tt_updated += 1

                active_slot_keys.add((cls_obj.id, d_num, p_num))

                # Synchronize ClassSubject
                cs, cs_created = ClassSubject.objects.update_or_create(
                    classroom=cls_obj,
                    subject=sub_obj,
                    defaults={
                        'teacher': t_obj,
                        'teacher_code': tok
                    }
                )
                cs_synced += 1

                matrix_items.append({
                    'classroom_id': cls_obj.id,
                    'day_of_week': d_num,
                    'period_number': p_num,
                    'subject_id': sub_obj.id,
                    'teacher_id': t_obj.id,
                    'start_time': st_time.strftime('%H:%M:%S'),
                    'end_time': et_time.strftime('%H:%M:%S'),
                    'room': room_val,
                })

        results['slots_created'] = tt_created
        results['slots_updated'] = tt_updated
        results['slots_total'] = tt_created + tt_updated
        results['class_subjects_synced'] = cs_synced

        # 4. Save TimetableVersion snapshot
        from .models import TimetableVersion
        TimetableVersion.objects.filter(academic_year=ay).update(is_active_applied=False)
        next_ver = 3
        existing_versions = TimetableVersion.objects.filter(academic_year=ay)
        if existing_versions.exists():
            next_ver = max(v.version_number for v in existing_versions) + 1

        TimetableVersion.objects.update_or_create(
            academic_year=ay,
            version_number=next_ver,
            defaults={
                'title': f"លើកទី {next_ver} (បំណែងចែកគ្រូ ២០២៦-២០២៧ តាម GT)",
                'note': "បាននាំចូលកាលវិភាគមេ ១,៣៣៨ ម៉ោងសិក្សាពេញលេញពី sheet GT នៃឯកសារ បំណែងចែកគ្រូ2027.xlsx",
                'matrix_data': matrix_items,
                'total_slots': len(matrix_items),
                'total_classrooms': len(classrooms_map),
                'is_active_applied': True,
            }
        )

        results['success'] = True

    return results

