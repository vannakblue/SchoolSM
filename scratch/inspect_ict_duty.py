import os, sys
if sys.stdout and sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

import openpyxl

wb = openpyxl.load_workbook(r'E:\SchoolSM\Data.xlsx', data_only=True)
ws_duty = wb['duty']

print("=== ALL TEACHERS IN SHEET 'duty' ===")
for idx, r in enumerate(list(ws_duty.iter_rows(values_only=True))[1:], start=2):
    no, sym, name, g, cls_str = r[0], r[1], r[2], r[3], r[4]
    if sym or name:
        sym_str = str(sym).strip() if sym is not None else ''
        name_str = str(name).strip() if name is not None else ''
        cls_val = str(cls_str).strip() if cls_str is not None else ''
        if any(k in sym_str.upper() for k in ['I', 'COM', 'IT']) or any(c in cls_val for c in ['7A', '8A', '9A']):
            print(f"Row {idx:2d} | Sym: {sym_str:8s} | Name: {name_str:20s} | Classes: '{cls_val}'")
