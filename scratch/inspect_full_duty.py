import os, sys, django
if sys.stdout and sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

import openpyxl
from apps.teachers.models import Teacher
from apps.academics.models import Classroom, Subject, ClassSubject, AcademicYear

file_path = r'E:\SchoolSM\Data.xlsx'
wb = openpyxl.load_workbook(file_path, data_only=True)
ws = wb['duty']

excel_rows = []
for r_idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
    if not row or not any(row):
        continue
    # col 0: No, col 1: symbol (និម្មិតសញ្ញា), col 2: name, col 3: gender, col 4: classes
    if r_idx == 1:
        headers = [str(c) if c is not None else '' for c in row]
        print("Duty Headers:", headers)
        continue
    
    no = row[0]
    symbol = str(row[1]).strip() if row[1] is not None else ''
    name = str(row[2]).strip().replace('\u200b', ' ').replace('\xa0', ' ') if row[2] is not None else ''
    gender = str(row[3]).strip() if row[3] is not None else ''
    classes = str(row[4]).strip() if row[4] is not None else ''
    
    if symbol or name:
        excel_rows.append({
            'row_num': r_idx,
            'no': no,
            'symbol': symbol,
            'name': name,
            'gender': gender,
            'classes': classes
        })

print(f"\nTotal teacher duty entries in sheet 'duty': {len(excel_rows)}")

# Check DB Teachers
db_teachers = list(Teacher.objects.all().order_by('id'))
print(f"Total Teachers in DB: {len(db_teachers)}")

db_name_map = {}
for t in db_teachers:
    clean_name = t.khmer_name.strip().replace('\u200b', ' ').replace('\xa0', ' ')
    db_name_map[clean_name] = t
    db_name_map[clean_name.replace(' ', '')] = t

print("\n=== MATCHING DUTY SHEET ROWS WITH DB TEACHERS ===")
matched = []
unmatched = []

for item in excel_rows:
    raw_name = item['name']
    clean_name = raw_name.replace('\u200b', ' ').replace('\xa0', ' ').strip()
    clean_no_space = clean_name.replace(' ', '')
    
    t_obj = db_name_map.get(clean_name) or db_name_map.get(clean_no_space)
    if not t_obj:
        # Partial match
        for k, v in db_name_map.items():
            if clean_no_space in k or k in clean_no_space:
                t_obj = v
                break
                
    if t_obj:
        matched.append((item, t_obj))
        diff_name = "" if t_obj.khmer_name.strip() == clean_name else f" [DB Name: '{t_obj.khmer_name}']"
        print(f"✅ Row {item['row_num']:2d}: Code={item['symbol']:5s} | Excel Name: '{clean_name:20s}'{diff_name} => DB ID: {t_obj.id:2d}, DB IDCode: '{t_obj.teacher_id}', Spec: '{t_obj.specialization}', Classes: '{item['classes']}'")
    else:
        unmatched.append(item)
        print(f"❌ Row {item['row_num']:2d}: Code={item['symbol']:5s} | Excel Name: '{clean_name}' | Gender: '{item['gender']}' | Classes: '{item['classes']}' -> NOT FOUND IN DB!")

print(f"\n==========================================")
print(f"Summary: {len(matched)} matched, {len(unmatched)} unmatched out of {len(excel_rows)} duty rows.")
print(f"==========================================")
if unmatched:
    print("Unmatched entries:")
    for u in unmatched:
        print("  ", u)
