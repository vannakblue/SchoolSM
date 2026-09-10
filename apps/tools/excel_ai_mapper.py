"""
AI-Powered Excel / CSV Smart Column Mapping & Data Normalization Engine
for SchoolSM (Students and Teachers Import).
Supports Google Gemini 3.8 Flash analysis + offline Khmer/English Semantic Heuristic Engine.
"""

import io
import os
import re
import json
import csv
from datetime import datetime, date
from decimal import Decimal
import openpyxl
from openpyxl.utils import datetime as openpyxl_dt
import requests
from django.conf import settings

# ---------------------------------------------------------
# 1. KHMER DIGITS & SMART NORMALIZERS
# ---------------------------------------------------------

KHMER_DIGIT_MAP = {
    '០': '0', '១': '1', '២': '2', '៣': '3', '៤': '4',
    '៥': '5', '៦': '6', '៧': '7', '៨': '8', '៩': '9',
}

KHMER_MONTHS = {
    'មករា': 1, 'កុម្ភៈ': 2, 'មីនា': 3, 'មេសា': 4,
    'ឧសភា': 5, 'មិថុនា': 6, 'កក្កដា': 7, 'សីហា': 8,
    'កញ្ញា': 9, 'តុលា': 10, 'វិច្ឆិកា': 11, 'ធ្នូ': 12,
}


def convert_khmer_digits(val):
    """Converts Khmer numeral characters into standard ASCII digits."""
    if val is None:
        return ''
    s = str(val)
    for k, v in KHMER_DIGIT_MAP.items():
        s = s.replace(k, v)
    return s.strip()


def parse_date_smart(val):
    """
    Intelligently parses dates from strings, Excel serial numbers,
    Khmer text dates (e.g. '15 ឧសភា 2005'), and multiple date formats.
    """
    if not val:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val

    # Openpyxl serial float / int (days since 1900)
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        try:
            if 1000 <= val <= 3000:
                # Likely just a year
                return date(int(val), 1, 1)
            return openpyxl_dt.from_excel(val).date()
        except Exception:
            pass

    clean_str = convert_khmer_digits(str(val)).strip()
    if not clean_str:
        return None

    # Check for Khmer month string like '15 ឧសភា 2008' or '15-ឧសភា-2008'
    for km_month, m_num in KHMER_MONTHS.items():
        if km_month in clean_str:
            parts = re.split(r'[\s\-/.]+', clean_str.replace(km_month, f"-{m_num}-"))
            parts = [p for p in parts if p.strip()]
            if len(parts) >= 3:
                try:
                    d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
                    if y < 100:
                        y += 2000 if y < 50 else 1900
                    return date(y, m, d)
                except Exception:
                    pass

    # Common formats
    date_formats = [
        '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%Y/%m/%d',
        '%d.%m.%Y', '%Y.%m.%d', '%m/%d/%Y', '%m-%d-%Y',
        '%d %b %Y', '%d %B %Y', '%Y%m%d'
    ]
    for fmt in date_formats:
        try:
            return datetime.strptime(clean_str, fmt).date()
        except ValueError:
            continue

    # Regex search for d/m/y or y/m/d
    match = re.search(r'(\d{1,4})[\/\-\.](\d{1,2})[\/\-\.](\d{1,4})', clean_str)
    if match:
        p1, p2, p3 = int(match.group(1)), int(match.group(2)), int(match.group(3))
        try:
            if p1 > 1900:  # YYYY-MM-DD
                return date(p1, p2, p3)
            elif p3 > 1900:  # DD-MM-YYYY
                return date(p3, p2, p1)
            elif p3 < 100:
                p3 += 2000 if p3 < 50 else 1900
                return date(p3, p2, p1)
        except Exception:
            pass

    return None


def parse_gender_smart(val):
    """
    Intelligently parses gender into 'M' or 'F'.
    Supports Khmer: ប្រុស, ស្រី, ប, ស, កញ្ញា, លោក
    English: M, F, Male, Female, Boy, Girl, Man, Woman, 1, 2
    """
    if not val:
        return 'M'
    val_str = str(val).strip().lower()
    val_clean = convert_khmer_digits(val_str)
    female_keywords = ['ស', 'ស.', 'ស្រី', 'ស្រី្ត', 'ស្ត្រី', 'កញ្ញា', 'f', 'female', 'girl', 'woman', '2']
    if any(k == val_clean or k == val_str for k in female_keywords):
        return 'F'
    return 'M'


def parse_phone_smart(val):
    """Normalizes phone numbers to standard format e.g. 012 345 678."""
    if not val:
        return ''
    digits = re.sub(r'[^\d]', '', convert_khmer_digits(str(val)))
    if not digits:
        return ''
    if digits.startswith('855') and len(digits) > 8:
        digits = '0' + digits[3:]
    elif not digits.startswith('0') and 8 <= len(digits) <= 9:
        digits = '0' + digits
    
    if len(digits) == 9:
        return f"{digits[:3]} {digits[3:6]} {digits[6:]}"
    elif len(digits) == 10:
        return f"{digits[:3]} {digits[3:6]} {digits[6:]}"
    return digits


# ---------------------------------------------------------
# 2. FIELD SPECIFICATIONS (STUDENT & TEACHER)
# ---------------------------------------------------------

STUDENT_TARGET_FIELDS = [
    {'name': 'khmer_name', 'label': 'ឈ្មោះខ្មែរ (Khmer Name)', 'required': True, 'icon': 'fa-user'},
    {'name': 'first_name_kh', 'label': 'នាមខ្លួន (First Name KH)', 'required': False, 'icon': 'fa-signature'},
    {'name': 'last_name_kh', 'label': 'គោត្តនាម (Last Name KH)', 'required': False, 'icon': 'fa-signature'},
    {'name': 'latin_name', 'label': 'ឈ្មោះឡាតាំង (Latin Name)', 'required': False, 'icon': 'fa-font'},
    {'name': 'gender', 'label': 'ភេទ (Gender)', 'required': True, 'icon': 'fa-venus-mars'},
    {'name': 'date_of_birth', 'label': 'ថ្ងៃខែឆ្នាំកំណើត (DOB)', 'required': True, 'icon': 'fa-calendar-days'},
    {'name': 'student_id', 'label': 'កូដសម្គាល់សិស្ស (Student ID)', 'required': False, 'icon': 'fa-id-card'},
    {'name': 'classroom', 'label': 'ថ្នាក់រៀន/កម្រិត (Class / Grade)', 'required': False, 'icon': 'fa-chalkboard-user'},
    {'name': 'phone', 'label': 'លេខទូរស័ព្ទសិស្ស (Phone)', 'required': False, 'icon': 'fa-phone'},
    {'name': 'place_of_birth', 'label': 'ទីកន្លែងកំណើត (POB)', 'required': False, 'icon': 'fa-map-pin'},
    {'name': 'current_address', 'label': 'អាសយដ្ឋានបច្ចុប្បន្ន (Address)', 'required': False, 'icon': 'fa-location-dot'},
    {'name': 'father_name', 'label': 'ឈ្មោះឪពុក (Father Name)', 'required': False, 'icon': 'fa-person'},
    {'name': 'father_phone', 'label': 'ទូរស័ព្ទឪពុក (Father Phone)', 'required': False, 'icon': 'fa-phone-volume'},
    {'name': 'father_job', 'label': 'មុខរបរឪពុក (Father Job)', 'required': False, 'icon': 'fa-briefcase'},
    {'name': 'mother_name', 'label': 'ឈ្មោះម្តាយ (Mother Name)', 'required': False, 'icon': 'fa-person-dress'},
    {'name': 'mother_phone', 'label': 'ទូរស័ព្ទម្តាយ (Mother Phone)', 'required': False, 'icon': 'fa-phone-volume'},
    {'name': 'mother_job', 'label': 'មុខរបរម្តាយ (Mother Job)', 'required': False, 'icon': 'fa-briefcase'},
    {'name': 'guardian_name', 'label': 'ឈ្មោះអាណាព្យាបាល (Guardian Name)', 'required': False, 'icon': 'fa-hands-holding'},
    {'name': 'emergency_phone', 'label': 'លេខទូរស័ព្ទបន្ទាន់ (Emergency Phone)', 'required': False, 'icon': 'fa-phone-flip'},
    {'name': 'scholarship_type', 'label': 'ប្រភេទកម្រៃ/អាហារូបករណ៍ (Scholarship)', 'required': False, 'icon': 'fa-award'},
    {'name': 'ignore', 'label': '✖ រំលងជួរឈរនេះ (Ignore Column)', 'required': False, 'icon': 'fa-ban'},
]

TEACHER_TARGET_FIELDS = [
    {'name': 'teacher_id', 'label': 'កូដសម្គាល់គ្រូ (Teacher ID)', 'required': False, 'icon': 'fa-id-badge'},
    {'name': 'khmer_name', 'label': 'ឈ្មោះខ្មែរ (Khmer Name)', 'required': True, 'icon': 'fa-user-tie'},
    {'name': 'first_name_kh', 'label': 'នាមខ្លួន (First Name KH)', 'required': False, 'icon': 'fa-signature'},
    {'name': 'last_name_kh', 'label': 'គោត្តនាម (Last Name KH)', 'required': False, 'icon': 'fa-signature'},
    {'name': 'latin_name', 'label': 'ឈ្មោះឡាតាំង (Latin Name)', 'required': False, 'icon': 'fa-font'},
    {'name': 'gender', 'label': 'ភេទ (Gender)', 'required': True, 'icon': 'fa-venus-mars'},
    {'name': 'date_of_birth', 'label': 'ថ្ងៃខែឆ្នាំកំណើត (DOB)', 'required': False, 'icon': 'fa-calendar-days'},
    {'name': 'phone', 'label': 'លេខទូរស័ព្ទចម្បង (Phone)', 'required': False, 'icon': 'fa-phone'},
    {'name': 'email', 'label': 'អ៊ីមែល (Email)', 'required': False, 'icon': 'fa-envelope'},
    {'name': 'specialization', 'label': 'ឯកទេសបង្រៀន (Specialization)', 'required': False, 'icon': 'fa-book-open-reader'},
    {'name': 'primary_subject', 'label': 'មុខវិជ្ជាទី១ (Primary Subject)', 'required': False, 'icon': 'fa-book'},
    {'name': 'secondary_subject', 'label': 'មុខវិជ្ជាទី២ (Secondary Subject)', 'required': False, 'icon': 'fa-book'},
    {'name': 'qualification', 'label': 'កម្រិតវប្បធម៌ (Qualification)', 'required': False, 'icon': 'fa-graduation-cap'},
    {'name': 'training_level', 'label': 'កម្រិតបណ្តុះបណ្តាលគរុកោសល្យ (Pedagogy)', 'required': False, 'icon': 'fa-certificate'},
    {'name': 'current_duty', 'label': 'ភារកិច្ចបច្ចុប្បន្ន (Current Duty)', 'required': False, 'icon': 'fa-user-gear'},
    {'name': 'prakas_category', 'label': 'ប្រភេទក្របខ័ណ្ឌ (Prakas Category)', 'required': False, 'icon': 'fa-award'},
    {'name': 'prakas_year', 'label': 'ឆ្នាំប្រកាស (Prakas Year)', 'required': False, 'icon': 'fa-calendar'},
    {'name': 'prakas_number', 'label': 'ប្រកាសលេខ (Prakas Number)', 'required': False, 'icon': 'fa-file-invoice'},
    {'name': 'base_salary', 'label': 'ប្រាក់ខែគោល (Base Salary $)', 'required': False, 'icon': 'fa-dollar-sign'},
    {'name': 'state_hire_date', 'label': 'ថ្ងៃចូលបម្រើការងាររដ្ឋ (State Hire Date)', 'required': False, 'icon': 'fa-calendar-check'},
    {'name': 'permanent_date', 'label': 'ថ្ងៃខែឆ្នាំតែងតាំងស៊ប់ (Permanent Date)', 'required': False, 'icon': 'fa-calendar-star'},
    {'name': 'address', 'label': 'អាសយដ្ឋាន (Address)', 'required': False, 'icon': 'fa-location-dot'},
    {'name': 'status', 'label': 'ស្ថានភាព (Status)', 'required': False, 'icon': 'fa-toggle-on'},
    {'name': 'ignore', 'label': '✖ រំលងជួរឈរនេះ (Ignore Column)', 'required': False, 'icon': 'fa-ban'},
]


# ---------------------------------------------------------
# 3. EXCEL / CSV EXTRACTION & HEADER DETECTION
# ---------------------------------------------------------

def extract_sheet_rows_and_headers(file_obj, max_sample_rows=5):
    """
    Reads an Excel (.xlsx, .xls, .xlsm) or CSV file.
    Automatically finds the table header row by skipping preamble banners,
    and returns dict with (sheet_name, header_index, headers, sample_rows, rows).
    """
    filename = getattr(file_obj, 'name', 'file.xlsx').lower()
    raw_matrix = []

    if filename.endswith(('.xlsx', '.xlsm', '.xls')):
        if hasattr(file_obj, 'seek'):
            file_obj.seek(0)
        wb = openpyxl.load_workbook(file_obj, data_only=True)
        target_sheet = '2026' if '2026' in wb.sheetnames else wb.sheetnames[0]
        ws = wb[target_sheet]
        for row in ws.iter_rows(values_only=True):
            if row and any(c is not None and str(c).strip() != '' for c in row):
                raw_matrix.append(list(row))
        wb.close()
    elif filename.endswith('.csv'):
        if hasattr(file_obj, 'seek'):
            file_obj.seek(0)
        content = file_obj.read()
        if isinstance(content, bytes):
            decoded = content.decode('utf-8-sig', errors='replace')
        else:
            decoded = content
        reader = csv.reader(io.StringIO(decoded))
        for row in reader:
            if row and any(c.strip() for c in row):
                raw_matrix.append(row)
        target_sheet = 'CSV'
    else:
        raise ValueError("ទម្រង់ឯកសារមិនត្រូវបានគាំទ្រ! សូមប្រើ .xlsx, .xls ឬ .csv")

    if not raw_matrix:
        return {'sheet_name': 'Sheet1', 'header_index': 0, 'headers': [], 'sample_rows': [], 'rows': []}

    header_keywords = [
        'ឈ្មោះ', 'name', 'ភេទ', 'gender', 'sex', 'ថ្ងៃ', 'dob', 'birth',
        'ថ្នាក់', 'class', 'grade', 'អត្តលេខ', 'id', 'ល.រ', 'លរ', 'no',
        'ទូរស័ព្ទ', 'phone', 'ឯកទេស', 'មុខវិជ្ជា', 'subject', 'specialization',
        'ក្របខ័ណ្ឌ', 'ប្រាក់ខែ', 'salary', 'ឪពុក', 'father', 'ម្តាយ', 'mother'
    ]

    best_row_idx = 0
    max_score = -1

    for idx, r in enumerate(raw_matrix[:15]):
        row_str = ' '.join(str(c or '').lower() for c in r)
        score = sum(1 for kw in header_keywords if kw in row_str)
        if any(w in row_str for w in ['ព្រះរាជាណាចក្រកម្ពុជា', 'ជាតិ សាសនា ព្រះមហាក្សត្រ', 'បញ្ជីរាយនាម', 'ស្ថិតិ', 'ក្រសួងអប់រំ']):
            score -= 5
        if score > max_score:
            max_score = score
            best_row_idx = idx

    if max_score <= 0:
        best_row_idx = 0

    header_raw = raw_matrix[best_row_idx]
    headers = []
    for col_i, h in enumerate(header_raw):
        val_str = str(h or '').replace('\n', ' ').strip()
        if not val_str:
            val_str = f"ជួរឈរ {openpyxl.utils.get_column_letter(col_i + 1)}"
        headers.append(val_str)

    data_rows = raw_matrix[best_row_idx + 1:]
    clean_data_rows = []
    for r in data_rows:
        if not any(c is not None and str(c).strip() != '' for c in r):
            continue
        row_str = ' '.join(str(c or '').lower() for c in r)
        if any(kw in row_str for kw in ['សរុប', 'total', 'ក្នុងនោះស្រី', 'បញ្ឈប់']):
            continue
        clean_data_rows.append(r)

    sample_rows = clean_data_rows[:max_sample_rows]

    return {
        'sheet_name': target_sheet,
        'header_index': best_row_idx,
        'headers': headers,
        'sample_rows': sample_rows,
        'rows': clean_data_rows
    }


# ---------------------------------------------------------
# 4. SEMANTIC & HEURISTIC COLUMN DETECTOR
# ---------------------------------------------------------

STUDENT_SEMANTIC_RULES = {
    'khmer_name': {
        'keywords': ['ឈ្មោះខ្មែរ', 'ឈ្មោះសិស្ស', 'គោត្តនាមនិងនាម', 'គោត្តនាម និងនាម', 'គោត្តនាម-នាម', 'ឈ្មោះពេញ', 'student_name', 'name_kh', 'full_name', 'khmer_name', 'ឈ្មោះ', 'name'],
        'weight': 10
    },
    'first_name_kh': {
        'keywords': ['នាមខ្លួន', 'នាម', 'first_name', 'firstname', 'given_name'],
        'weight': 8
    },
    'last_name_kh': {
        'keywords': ['គោត្តនាម', 'ត្រកូល', 'last_name', 'lastname', 'family_name', 'surname'],
        'weight': 8
    },
    'latin_name': {
        'keywords': ['ឈ្មោះឡាតាំង', 'ឈ្មោះជាអក្សរឡាតាំង', 'ឈ្មោះអង់គ្លេស', 'latin_name', 'latin name', 'english_name', 'name_en', 'full_name_en'],
        'weight': 9
    },
    'gender': {
        'keywords': ['ភេទ', 'gender', 'sex', 'g', 'ប្រុស/ស្រី'],
        'weight': 10
    },
    'date_of_birth': {
        'keywords': ['ថ្ងៃខែឆ្នាំកំណើត', 'ថ្ងៃកំណើត', 'កាលបរិច្ឆេទកំណើត', 'date_of_birth', 'date of birth', 'dob', 'birth_date', 'birthdate'],
        'weight': 10
    },
    'student_id': {
        'keywords': ['កូដសិស្ស', 'អត្តលេខសិស្ស', 'អត្តលេខ', 'student_id', 'student id', 'id_card', 'code_student', 'កូដ'],
        'weight': 9
    },
    'classroom': {
        'keywords': ['ថ្នាក់រៀន', 'ថ្នាក់', 'កូដថ្នាក់', 'ឈ្មោះថ្នាក់', 'classroom', 'class', 'class_code', 'grade', 'កម្រិតថ្នាក់', 'ថ្នាក់ទី'],
        'weight': 8
    },
    'phone': {
        'keywords': ['លេខទូរស័ព្ទសិស្ស', 'ទូរស័ព្ទសិស្ស', 'លេខទូរស័ព្ទ', 'ទូរស័ព្ទ', 'phone', 'phone_number', 'student_phone', 'tel', 'mobile'],
        'weight': 7
    },
    'place_of_birth': {
        'keywords': ['ទីកន្លែងកំណើត', 'ទីកន្លែងកើត', 'ស្រុកកំណើត', 'place_of_birth', 'pob', 'birth_place'],
        'weight': 8
    },
    'current_address': {
        'keywords': ['អាសយដ្ឋានបច្ចុប្បន្ន', 'អាសយដ្ឋាន', 'ទីលំនៅបច្ចុប្បន្ន', 'current_address', 'address', 'residence'],
        'weight': 8
    },
    'father_name': {
        'keywords': ['ឈ្មោះឪពុក', 'ឪពុក', 'father_name', 'father', 'dad_name'],
        'weight': 9
    },
    'father_phone': {
        'keywords': ['លេខទូរស័ព្ទឪពុក', 'ទូរស័ព្ទឪពុក', 'father_phone', 'father_tel'],
        'weight': 9
    },
    'father_job': {
        'keywords': ['មុខរបរឪពុក', 'father_job', 'father_occupation'],
        'weight': 8
    },
    'mother_name': {
        'keywords': ['ឈ្មោះម្តាយ', 'ម្តាយ', 'mother_name', 'mother', 'mom_name'],
        'weight': 9
    },
    'mother_phone': {
        'keywords': ['លេខទូរស័ព្ទម្តាយ', 'ទូរស័ព្ទម្តាយ', 'mother_phone', 'mother_tel'],
        'weight': 9
    },
    'mother_job': {
        'keywords': ['មុខរបរម្តាយ', 'mother_job', 'mother_occupation'],
        'weight': 8
    },
    'guardian_name': {
        'keywords': ['ឈ្មោះអាណាព្យាបាល', 'អាណាព្យាបាល', 'guardian_name', 'guardian'],
        'weight': 8
    },
    'emergency_phone': {
        'keywords': ['លេខទាក់ទងបន្ទាន់', 'ទូរស័ព្ទបន្ទាន់', 'emergency_phone', 'emergency_contact'],
        'weight': 8
    },
    'scholarship_type': {
        'keywords': ['ប្រភេទកម្រៃ', 'ប្រភេទកម្រៃសិក្សា', 'អាហារូបករណ៍', 'scholarship', 'scholarship_type', 'fee_type'],
        'weight': 8
    }
}

TEACHER_SEMANTIC_RULES = {
    'teacher_id': {
        'keywords': ['កូដសម្គាល់គ្រូ', 'អត្តលេខមន្ត្រី', 'អត្តលេខគ្រូ', 'អត្តលេខ', 'teacher id', 'teacher_id', 'staff_id', 'id'],
        'weight': 10
    },
    'khmer_name': {
        'keywords': ['ឈ្មោះខ្មែរ', 'ឈ្មោះគ្រូ', 'ឈ្មោះលោកគ្រូ', 'គោត្តនាមនិងនាម', 'គោត្តនាម និងនាម', 'គោត្តនាម-នាម', 'teacher_name', 'khmer_name', 'name_kh', 'full_name', 'ឈ្មោះ', 'name'],
        'weight': 10
    },
    'first_name_kh': {
        'keywords': ['នាមខ្លួន', 'នាម', 'first_name', 'firstname'],
        'weight': 8
    },
    'last_name_kh': {
        'keywords': ['គោត្តនាម', 'ត្រកូល', 'last_name', 'lastname'],
        'weight': 8
    },
    'latin_name': {
        'keywords': ['ឈ្មោះឡាតាំង', 'ឈ្មោះជាអក្សរឡាតាំង', 'ឈ្មោះអង់គ្លេស', 'latin_name', 'latin name', 'english_name', 'name_en'],
        'weight': 9
    },
    'gender': {
        'keywords': ['ភេទ', 'gender', 'sex', 'g', 'ប្រុស/ស្រី'],
        'weight': 10
    },
    'date_of_birth': {
        'keywords': ['ថ្ងៃខែឆ្នាំកំណើត', 'ថ្ងៃកំណើត', 'កាលបរិច្ឆេទកំណើត', 'date_of_birth', 'dob', 'birth_date'],
        'weight': 10
    },
    'phone': {
        'keywords': ['លេខទូរស័ព្ទ', 'ទូរស័ព្ទ', 'phone', 'mobile', 'tel', 'phone_number'],
        'weight': 8
    },
    'email': {
        'keywords': ['អ៊ីមែល', 'អ៊ីម៉ែល', 'email', 'e-mail', 'mail'],
        'weight': 9
    },
    'specialization': {
        'keywords': ['ឯកទេសបង្រៀន', 'ឯកទេស', 'មុខវិជ្ជាឯកទេស', 'specialization', 'major', 'subject'],
        'weight': 9
    },
    'primary_subject': {
        'keywords': ['មុខវិជ្ជាទី១', 'មុខវិជ្ជាចម្បង', 'primary_subject', 'subject 1'],
        'weight': 8
    },
    'secondary_subject': {
        'keywords': ['មុខវិជ្ជាទី២', 'មុខវិជ្ជាបន្ទាប់បន្សំ', 'secondary_subject', 'subject 2'],
        'weight': 8
    },
    'qualification': {
        'keywords': ['កម្រិតវប្បធម៌', 'សញ្ញាបត្រ', 'qualification', 'degree', 'education'],
        'weight': 8
    },
    'training_level': {
        'keywords': ['កម្រិតបណ្តុះបណ្តាល', 'គរុកោសល្យ', 'training_level', 'pedagogy'],
        'weight': 8
    },
    'current_duty': {
        'keywords': ['ភារកិច្ចបច្ចុប្បន្ន', 'មុខតំណែង', 'តួនាទី', 'current_duty', 'duty', 'position', 'role'],
        'weight': 8
    },
    'base_salary': {
        'keywords': ['ប្រាក់ខែគោល', 'ប្រាក់ខែ', 'ប្រាក់បៀវត្ស', 'base_salary', 'salary', 'wage'],
        'weight': 8
    },
    'prakas_category': {
        'keywords': ['ប្រភេទក្របខ័ណ្ឌ', 'ក្របខ័ណ្ឌ', 'prakas_category', 'category'],
        'weight': 8
    },
    'prakas_year': {
        'keywords': ['ឆ្នាំប្រកាស', 'prakas_year', 'decree_year'],
        'weight': 8
    },
    'prakas_number': {
        'keywords': ['ប្រកាសលេខ', 'លេខប្រកាស', 'prakas_number', 'prakas_no'],
        'weight': 8
    },
    'state_hire_date': {
        'keywords': ['ថ្ងៃចូលបម្រើការងាររដ្ឋ', 'ថ្ងៃចូលរដ្ឋ', 'state_hire_date', 'hire_date'],
        'weight': 8
    },
    'permanent_date': {
        'keywords': ['ថ្ងៃតែងតាំងស៊ប់', 'permanent_date'],
        'weight': 8
    },
    'address': {
        'keywords': ['អាសយដ្ឋាន', 'address', 'residence'],
        'weight': 7
    },
    'status': {
        'keywords': ['ស្ថានភាព', 'status'],
        'weight': 7
    }
}


def semantic_match_column(header_text, sample_values, target_type='student'):
    """
    Evaluates a column header and its sample data values to determine the best target field match.
    """
    clean_h = str(header_text or '').lower().replace('_', ' ').replace('-', ' ').strip()
    rules = STUDENT_SEMANTIC_RULES if target_type == 'student' else TEACHER_SEMANTIC_RULES

    if clean_h in ['ល.រ', 'លរ', 'លរ.', 'no', 'no.', '#', 'num', 'number', 'លំដាប់']:
        return 'ignore', 99, 'ជួរឈរលេខរៀងលំដាប់ (Serial No. - ignored)'

    best_field = 'ignore'
    best_score = 0
    best_reason = 'មិនច្បាស់លាស់'

    for field, cfg in rules.items():
        score = 0
        matched_kw = None
        for kw in cfg['keywords']:
            if kw == clean_h:
                score += cfg['weight'] * 10
                matched_kw = kw
                break
            elif kw in clean_h:
                score += cfg['weight'] * 6
                matched_kw = kw
            elif clean_h in kw and len(clean_h) >= 3:
                score += cfg['weight'] * 4
                matched_kw = kw

        sample_texts = [str(v or '').strip() for v in sample_values if v is not None and str(v).strip() != '']
        if sample_texts:
            if field == 'gender' and any(s.lower() in ['ប្រុស', 'ស្រី', 'm', 'f', 'ប', 'ស'] for s in sample_texts):
                score += 30
            elif field in ['date_of_birth', 'state_hire_date', 'permanent_date']:
                if any(parse_date_smart(s) is not None for s in sample_texts):
                    score += 25
            elif 'phone' in field and any(re.search(r'0\d{8,9}', re.sub(r'\s+', '', convert_khmer_digits(s))) for s in sample_texts):
                score += 25
            elif 'id' in field and any(re.search(r'^[a-zA-Z0-9\-_]{2,15}$', s) for s in sample_texts):
                score += 15

        if score > best_score:
            best_score = score
            best_field = field
            best_reason = f"ផ្គូផ្គងជាមួយពាក្យគន្លឹះ «{matched_kw}»" if matched_kw else "វិភាគតាមតម្លៃគំរូ"

    confidence = min(99, int(best_score * 1.5)) if best_score > 0 else 0
    if confidence < 35:
        best_field = 'ignore'
        confidence = 0
        best_reason = 'មិនអាចកំណត់បាន (សូមជ្រើសរើសដោយផ្ទាល់)'

    return best_field, confidence, best_reason


# ---------------------------------------------------------
# 5. GEMINI AI COLUMN DETECTION ASSISTANT
# ---------------------------------------------------------

def detect_column_mapping_with_ai(headers, sample_rows, target_type='student'):
    """
    Uses Google Gemini 3.8 Flash (if available) with intelligent prompt
    to analyze arbitrary Excel headers and sample data, falling back gracefully
    to the offline Khmer semantic matcher.
    """
    fields_spec = STUDENT_TARGET_FIELDS if target_type == 'student' else TEACHER_TARGET_FIELDS
    allowed_field_names = [f['name'] for f in fields_spec]

    # Run semantic matching first as a solid baseline
    semantic_mappings = {}
    for col_idx, h in enumerate(headers):
        col_samples = [r[col_idx] for r in sample_rows if len(r) > col_idx]
        field, conf, reason = semantic_match_column(h, col_samples, target_type=target_type)
        semantic_mappings[str(col_idx)] = {
            'field': field,
            'confidence': conf,
            'reason': reason
        }

    api_key = getattr(settings, 'GEMINI_API_KEY', '') or os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        return semantic_mappings

    model_name = getattr(settings, 'GEMINI_MODEL', '') or os.environ.get('GEMINI_MODEL', 'gemini-3.8-flash')
    target_label = "សិស្ស (Student)" if target_type == 'student' else "គ្រូបង្រៀន (Teacher)"
    
    samples_table = []
    for r in sample_rows:
        samples_table.append([str(c or '') for c in r])

    prompt_data = {
        "target_type": target_type,
        "allowed_fields": allowed_field_names,
        "columns": [{"index": i, "header": h} for i, h in enumerate(headers)],
        "sample_rows": samples_table
    }

    system_instruction = (
        f"You are an expert Cambodian School Database AI for {target_label} roster Excel files. "
        "Analyze the uploaded Excel column headers and sample data. "
        "Map each column index to the most appropriate database field from allowed_fields. "
        "If a column contains serial numbers (No, ល.រ) or irrelevant data, map it to 'ignore'. "
        "If last name (គោត្តនាម) and first name (នាម) are in separate columns, map them to 'last_name_kh' and 'first_name_kh'. "
        "Return STRICT JSON only matching this format: "
        '{"mappings": {"0": {"field": "khmer_name", "confidence": 95, "reason": "Names matched"}}}'
    )

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": json.dumps(prompt_data, ensure_ascii=False)}]}],
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json"
            }
        }
        resp = requests.post(url, json=payload, timeout=8)
        if resp.status_code == 200:
            result_json = resp.json()
            candidate = result_json.get('candidates', [{}])[0]
            parts = candidate.get('content', {}).get('parts', [])
            answer_text = parts[0].get('text', '') if parts else ''
            parsed_ai = json.loads(answer_text)
            ai_mappings = parsed_ai.get('mappings', {})
            
            for idx_str, info in ai_mappings.items():
                target_f = info.get('field')
                if target_f in allowed_field_names:
                    semantic_mappings[idx_str] = {
                        'field': target_f,
                        'confidence': info.get('confidence', 95),
                        'reason': f"✨ Gemini AI: {info.get('reason', 'កំណត់ដោយស្វ័យប្រវត្តិ')}"
                    }
    except Exception:
        pass

    return semantic_mappings


# ---------------------------------------------------------
# 6. ROW DATA NORMALIZER WITH CUSTOM MAPPINGS
# ---------------------------------------------------------

def normalize_row_data(row, col_mapping, target_type='student'):
    """
    Applies the column mapping dictionary to a raw Excel data row,
    handling split first/last names, date normalization, gender conversion,
    and phone normalization.
    """
    record = {}
    last_name = ''
    first_name = ''
    last_name_en = ''
    first_name_en = ''

    for idx, val in enumerate(row):
        idx_str = str(idx)
        field = col_mapping.get(idx_str)
        if not field or field == 'ignore':
            continue

        clean_val = str(val).strip() if val is not None else ''

        if field == 'first_name_kh':
            first_name = clean_val
        elif field == 'last_name_kh':
            last_name = clean_val
        elif field == 'first_name_en':
            first_name_en = clean_val
        elif field == 'last_name_en':
            last_name_en = clean_val
        elif field == 'khmer_name':
            record['khmer_name'] = clean_val
        elif field == 'latin_name':
            record['latin_name'] = clean_val
        elif field == 'gender':
            record['gender'] = parse_gender_smart(clean_val)
        elif field in ['date_of_birth', 'state_hire_date', 'permanent_date']:
            record[field] = parse_date_smart(val)
        elif 'phone' in field:
            record[field] = parse_phone_smart(clean_val)
        elif field == 'base_salary':
            digits = re.sub(r'[^\d.]', '', clean_val)
            try:
                record['base_salary'] = Decimal(digits) if digits else Decimal('500.00')
            except Exception:
                record['base_salary'] = Decimal('500.00')
        else:
            record[field] = clean_val

    # Combine split names if full khmer_name was not explicitly given
    if not record.get('khmer_name') and (last_name or first_name):
        record['khmer_name'] = f"{last_name} {first_name}".strip()

    if not record.get('latin_name') and (last_name_en or first_name_en):
        record['latin_name'] = f"{last_name_en} {first_name_en}".strip()

    return record
