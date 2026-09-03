import os, sys, django
if sys.stdout and sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

import openpyxl
import difflib
from apps.teachers.models import Teacher

file_path = r'E:\SchoolSM\Data.xlsx'
wb = openpyxl.load_workbook(file_path, data_only=True)
ws = wb['duty']

db_teachers = list(Teacher.objects.all().order_by('id'))
db_names = [t.khmer_name.strip() for t in db_teachers]

print("=== ALL 109 TEACHERS IN DATABASE ===")
for t in db_teachers:
    print(f"ID: {t.id:3d} | TeacherID: '{t.teacher_id:12s}' | Name: '{t.khmer_name:25s}' | Latin: '{t.latin_name:20s}' | Spec: '{t.specialization}'")

print("\n=== FINDING BEST MATCHES FOR UNMATCHED EXCEL NAMES ===")
excel_unmatched = [
    'ផាត ស៊្រុន', 'សុង ភស្ស', 'សាន់ ភឿន', 'ជួង សុភក្រ័', 'បូរ កញ្ញា',
    'អឹម សំអុល', 'ហៀង សេងហៃ', 'ស៊ុំ វ៉េង', 'ចេង ប៊ុណ្ណវេទ', 'ជួ សូរិយា',
    'សួន ស្រីរត្ត័', 'ឃុត  បូរ៉ាមី', 'ជឹង សុចាន់', 'មាស ស្រីល័ក្ខ', 'ហេង ឃាង',
    'លន ស្រីល័ក្ខ', 'ខៀវ ខេមរិន្ទ', 'ចាន់ ធី', 'ទិត សាម៉នវីរ:', 'ប្រាក់ សុភារ:',
    'នាង ជំនិត', 'ផាត់ ចាន់សុផាណា', 'ជុំ សុផន', 'ងួន គ្រីន', 'ចេង ចំរើន',
    'ឡេង សេស', 'លី ហួត', 'សឿន សម្បត្តិ', 'ស៊ីន ម៉ូនីដា', 'សូ វណ្ណ:',
    'ទុន វណ្ណ:', 'ទូច សុខម៉េត', 'ផេង រិទ្ធីយ៉ា', 'ទិន សុភី'
]

for name in excel_unmatched:
    clean_target = name.replace(':', 'ៈ').replace('\u200b', ' ').strip()
    # Find close matches in db_names
    matches = difflib.get_close_matches(clean_target, db_names, n=5, cutoff=0.3)
    # Also check if surname matches
    surname = clean_target.split()[0] if clean_target.split() else ''
    surname_matches = [t.khmer_name for t in db_teachers if t.khmer_name.startswith(surname)]
    print(f"\nExcel Name: '{name}'")
    print(f"   Closest text matches: {matches}")
    print(f"   Same surname ({surname}) matches: {surname_matches}")
