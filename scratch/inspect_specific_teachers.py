import os, sys
if sys.stdout and sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

import openpyxl

wb = openpyxl.load_workbook('moeys_teachers_2026.xlsx', data_only=True)
ws = wb['2026']

for idx, r in enumerate(list(ws.iter_rows(values_only=True))[7:], start=8):
    if not r or not any(r):
        continue
    name = str(r[2]).strip() if r[2] is not None else ''
    tid = str(r[1]).strip() if r[1] is not None else ''
    spec = str(r[6]).strip() if r[6] is not None else ''
    if any(k in name for k in ['ភឿន', 'កញ្ញា', 'កន្យា', 'សាន់', 'បូរ']):
        print(f"Row {idx:3d} | TID: {tid:12s} | Name: '{name:25s}' | Spec: '{spec}'")
