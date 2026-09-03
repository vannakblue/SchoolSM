import os, sys, django
if sys.stdout and sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

import openpyxl
from apps.teachers.models import Teacher

wb_moeys = openpyxl.load_workbook('moeys_teachers_2026.xlsx', data_only=True)
ws_moeys = wb_moeys['2026']

print("=== MOEYS TEACHERS 2026 PREVIEW ===")
for idx, r in enumerate(list(ws_moeys.iter_rows(values_only=True))[:25], start=1):
    non_empty = [c for c in r if c is not None]
    if non_empty:
        print(f"Row {idx:2d}: {[str(c) if c is not None else '' for c in r[:10]]}")
