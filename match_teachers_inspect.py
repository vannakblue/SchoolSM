import sys
import openpyxl
import django
import os
import unicodedata
import re

sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from apps.teachers.models import Teacher

def normalize_kh(s):
    if not s:
        return ''
    s = s.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '').replace('\xa0', ' ')
    s = s.replace(':', 'ៈ').replace('៖', 'ៈ')
    s = re.sub(r'\s+', ' ', s).strip()
    return s

wb = openpyxl.load_workbook('បំណែងចែកគ្រូ2027.xlsx', data_only=True)
ws = wb['duty']

db_teachers = list(Teacher.objects.all())

excel_rows = []
for i, row in enumerate(ws.iter_rows(values_only=True), start=1):
    if row[0]:
        excel_rows.append((i, str(row[0]).strip(), str(row[1]).strip() if row[1] else '', str(row[2]).strip() if row[2] else ''))

print(f"Total rows in Excel: {len(excel_rows)}")
print(f"Total teachers in DB: {len(db_teachers)}")

unmatched = []
matched = []

for idx, name, gender, classes in excel_rows:
    norm_name = normalize_kh(name)
    cand = None
    # 1. Exact match
    for t in db_teachers:
        if t.khmer_name.strip() == name:
            cand = t
            break
    # 2. Normalized match (whitespace, zero-width space, colon)
    if not cand:
        for t in db_teachers:
            if normalize_kh(t.khmer_name) == norm_name:
                cand = t
                break
    # 3. Space-stripped match
    if not cand:
        for t in db_teachers:
            if normalize_kh(t.khmer_name).replace(' ', '') == norm_name.replace(' ', ''):
                cand = t
                break

    if cand:
        matched.append((idx, name, cand))
    else:
        unmatched.append((idx, name, gender, classes))

print(f"Matched after normalization: {len(matched)} / {len(excel_rows)}")
print(f"Remaining unmatched: {len(unmatched)}")

if unmatched:
    print("\n--- DETAILED INSPECTION OF REMAINING UNMATCHED ---")
    for idx, name, gender, classes in unmatched:
        norm = normalize_kh(name)
        print(f"\nRow {idx}: '{name}' (Norm: '{norm}', Gender: '{gender}', Classes: '{classes}')")
        # Search for similar in DB
        first_token = norm.split(' ')[0] if ' ' in norm else norm[:3]
        last_token = norm.split(' ')[-1] if ' ' in norm else norm[-3:]
        similar = []
        for t in db_teachers:
            t_norm = normalize_kh(t.khmer_name)
            if first_token in t_norm or last_token in t_norm:
                similar.append((t.id, t.khmer_name, t.gender, t.specialization))
        print("  Possible candidates in DB:")
        for s in similar[:6]:
            print(f"    ID: {s[0]} | Name: '{s[1]}' | Gender: {s[2]} | Spec: {s[3]}")
