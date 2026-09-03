import os, sys, django
if sys.stdout and sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

import json
from django.test import RequestFactory
from apps.students.khmer_romanizer import romanize_khmer_name
from apps.students.views import api_romanize_khmer_name

rf = RequestFactory()

test_cases = [
    ('សុខ ចាន់ណា', 'SOK CHANNA'),
    ('សុខ ចាន់ ណា', 'SOK CHANNA'),
    ('សុខចាន់ណា', 'SOK CHANNA'),
    ('សុខ ចិន្តា', 'SOK CHINDA'),
    ('ជា វណ្ណៈ', 'CHEA VANNAK'),
    ('ទុន វណ្ណាក់', 'TUN VANNAK'),
    ('អ៊ុក សុជាតា', 'OUK SOCHEATA'),
    ('ហេង ពិសី', 'HENG PISEY'),
    ('ឡេង សាវឿន', 'LENG SAVOEUN'),
    ('គង់ សុខុម', 'KONG SOKHOM'),
    ('កែវ ស្រីពៅ', 'KEO SREYPOV'),
]

print("--- RUNNING VERIFICATION ON DJANGO ROMANIZE API ---")
all_passed = True
for kh, expected in test_cases:
    req = rf.get('/students/api/romanize/', {'name': kh})
    resp = api_romanize_khmer_name(req)
    data = json.loads(resp.content.decode('utf-8'))
    actual = data.get('latin_name')
    match = (actual == expected)
    if not match:
        all_passed = False
    print(f"[{'PASS' if match else 'FAIL'}] Khmer: {kh:16} => Actual: {actual:16} (Expected: {expected})")

if all_passed:
    print("\n✅ ALL TESTS PASSED PERFECTLY!")
else:
    print("\n❌ SOME TESTS FAILED")
