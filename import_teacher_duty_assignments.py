import sys
import openpyxl
import django
import os
import re
import datetime

sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.db import transaction
from apps.accounts.models import User
from apps.teachers.models import Teacher
from apps.academics.models import AcademicYear, Classroom, Subject, ClassSubject, GradeLevelRule, Timetable

def normalize_kh(s):
    if not s:
        return ''
    s = s.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '').replace('\xa0', ' ')
    s = s.replace(':', 'ៈ').replace('៖', 'ៈ')
    return re.sub(r'\s+', ' ', s).strip()

def parse_classes(s):
    matches = re.findall(r'(10|11|12|[789])([A-Za-z]+)', str(s).strip())
    res = []
    for grade, letters in matches:
        for letter in letters.upper():
            res.append(f"{grade}{letter}")
    return res

def run_import():
    print("=" * 80)
    print("IMPORT TEACHER DUTY ASSIGNMENTS (បំណែងចែកភារកិច្ចគ្រូ ឆ្នាំ២០២៦-២០២៧)")
    print("=" * 80)

    # 1. Get current active academic year
    ay = AcademicYear.objects.filter(is_current=True).first()
    if not ay:
        ay = AcademicYear.objects.filter(name__icontains='2026-2027').first()
    print(f"Target Academic Year: {ay.id} - {ay.name}")

    # 2. Get Classrooms for this academic year
    classrooms_qs = Classroom.objects.filter(academic_year=ay)
    classrooms_map = {}
    for c in classrooms_qs:
        short_name = c.name.replace('ថ្នាក់ទី ', '').strip()
        classrooms_map[short_name] = c
    print(f"Classrooms found in DB ({len(classrooms_map)} classes): {sorted(list(classrooms_map.keys()))}")

    # 3. Ensure Subject instances exist for ED (Physical Ed) and AG (Agriculture/Tech)
    sub_ed, _ = Subject.objects.get_or_create(
        code='ED',
        defaults={'name_kh': 'អប់រំកាយ និងកីឡា', 'name_en': 'Physical Education & Sport', 'order': 15}
    )
    sub_ag, _ = Subject.objects.get_or_create(
        code='AG',
        defaults={'name_kh': 'កសិកម្ម', 'name_en': 'Agriculture & Tech', 'order': 16}
    )

    # Map prefixes to Subject codes in DB
    prefix_to_subcode = {
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

    subjects_by_code = {s.code: s for s in Subject.objects.all()}
    sub_r = subjects_by_code.get('R')
    sub_d = subjects_by_code.get('D')
    sub_k = subjects_by_code.get('K')

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

    # 4. Teacher Name Mapping (Exact database names)
    manual_map = {
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
    }

    db_teachers = list(Teacher.objects.all())
    def find_teacher(raw_name):
        target = manual_map.get(raw_name, raw_name)
        target_norm = normalize_kh(target)
        target_nospc = target_norm.replace(' ', '')
        for t in db_teachers:
            if t.khmer_name.strip() == target:
                return t
        for t in db_teachers:
            t_norm = normalize_kh(t.khmer_name)
            if t_norm == target_norm or t_norm.replace(' ', '') == target_nospc:
                return t
        return None

    # 5. Load duty assignments from data.xlsx (which contains teacher codes M1..AG8 and class lists)
    wb_data = openpyxl.load_workbook('data.xlsx', data_only=True)
    ws_duty = wb_data['duty']

    duty_records = []
    for idx, r in enumerate(list(ws_duty.iter_rows(values_only=True))[1:105], start=1):
        code = str(r[1]).strip()
        raw_name = str(r[2]).strip()
        classes_str = str(r[4]).strip() if r[4] else ''

        if code.startswith('I9G'):
            prefix = 'G'
        else:
            prefix = re.match(r'^([A-Za-z]+)', code).group(1).upper()

        sub_code = prefix_to_subcode.get(prefix)
        subject_obj = subjects_by_code.get(sub_code)

        t_obj = find_teacher(raw_name)
        if not t_obj:
            raise ValueError(f"Teacher '{raw_name}' in row {idx} could not be found in database!")

        c_list = parse_classes(classes_str)

        duty_records.append({
            'row': idx,
            'code': code,
            'prefix': prefix,
            'subject': subject_obj,
            'raw_name': raw_name,
            'teacher': t_obj,
            'classes_str': classes_str,
            'classes': c_list,
        })

    print(f"Loaded {len(duty_records)} teacher duty records.")

    # 6. Atomic Database Update
    with transaction.atomic():
        cs_created = 0
        cs_updated = 0
        assigned_teachers = set()

        for rec in duty_records:
            t_obj = rec['teacher']
            sub_obj = rec['subject']
            assigned_teachers.add(t_obj.id)

            # Ensure teacher max weekly hours are set
            if t_obj.training_level and 'ទុតិយភូមិ' in t_obj.training_level:
                t_obj.max_weekly_hours = 16
            else:
                t_obj.max_weekly_hours = 18
            t_obj.save(update_fields=['max_weekly_hours'])

            for c_name in rec['classes']:
                cls_obj = classrooms_map.get(c_name)
                if not cls_obj:
                    print(f"Warning: classroom {c_name} not found!")
                    continue

                # Assign main subject
                cs, created = ClassSubject.objects.update_or_create(
                    classroom=cls_obj,
                    subject=sub_obj,
                    defaults={'teacher': t_obj}
                )
                if created:
                    cs_created += 1
                else:
                    cs_updated += 1

                # If subject is Khmer (K) and class is in Grade 7, 8, 9, also assign R and D
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

        print(f"\n[CLASS-SUBJECT ASSIGNMENT COMPLETE]")
        print(f"  Total ClassSubject Created: {cs_created}")
        print(f"  Total ClassSubject Updated: {cs_updated}")
        print(f"  Unique Teachers Assigned: {len(assigned_teachers)} / {len(duty_records)}")

        # 7. Import Timetable Slots from GT sheet if available
        if 'GT' in wb_data.sheetnames:
            ws_gt = wb_data['GT']
            print("\n[IMPORTING MASTER TIMETABLE SLOTS FROM GT SHEET] ...")
            # GT columns:
            # Day mapping in GT sheet:
            # Col 1: Class (7A)
            # Cols 1-8: Monday (periods 1-8)
            # Col 9: separator
            # Cols 10: Class
            # Cols 11-18: Tuesday (periods 1-8)
            # etc.
            # Let's inspect column layout of GT
            # Days: Monday(1) to Saturday(6)
            days_periods = []
            # Day 1 (Monday): cols 1..4 (morning), col 5 (break/info), cols 6..9 (afternoon)
            # Let's parse all day/period headers from row 1
            headers = [c for c in ws_gt[1]]
            col_slot_map = {}
            # Day map: ច=1, អ=2, ព=3, ព្រ=4, សុ=5, ស=6
            day_kh_map = {'ច': 1, 'អ': 2, 'ព': 3, 'ព្រ': 4, 'សុ': 5, 'ស': 6}
            for col_idx, cell in enumerate(headers):
                val = str(cell.value or '').strip()
                m = re.match(r'^(ច|អ|ព|ព្រ|សុ|ស)(\d+)$', val)
                if m:
                    d_kh, p_num = m.group(1), int(m.group(2))
                    d_num = day_kh_map.get(d_kh, 1)
                    col_slot_map[col_idx] = (d_num, p_num)

            print(f"  Detected {len(col_slot_map)} timetable period columns across Monday-Saturday.")

            duty_by_code = {rec['code'].upper(): rec for rec in duty_records}
            # Add HE aliases
            duty_by_code['HE1'] = duty_by_code.get('HE1')
            duty_by_code['HE2'] = duty_by_code.get('HE2')
            duty_by_code['HE3'] = duty_by_code.get('HE3')
            duty_by_code['HE4'] = duty_by_code.get('HE4')

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

            tt_created = 0
            tt_updated = 0
            for r in ws_gt.iter_rows(min_row=2, values_only=True):
                cname = str(r[0] or '').strip()
                cls_obj = classrooms_map.get(cname)
                if not cls_obj:
                    continue

                for col_idx, (d_num, p_num) in col_slot_map.items():
                    if col_idx < len(r):
                        token = str(r[col_idx] or '').strip()
                        if not token or token == 'None':
                            continue
                        # If token matches teacher duty code (e.g. M1, P2, I9G1...)
                        token_upper = token.upper()
                        rec = duty_by_code.get(token_upper)
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

            print(f"  Timetable entries created: {tt_created}, updated: {tt_updated}")

    print("\n" + "=" * 80)
    print("SUCCESS: ALL 104 TEACHER ASSIGNMENTS PERMANENTLY SAVED TO DATABASE!")
    print("=" * 80)

if __name__ == '__main__':
    run_import()
