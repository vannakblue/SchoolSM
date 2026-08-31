import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User

admin_u = User.objects.filter(role=User.Role.ADMIN).first()
client = Client()
client.force_login(admin_u)

pages = [
    '/academics/timetable/',
    '/academics/timetable/student-teacher/',
    '/academics/duty-schedule/',
    '/academics/teacher-assignments/',
    '/academics/subject-requirements/',
    '/academics/scoring-rules/',
    '/academics/classrooms/',
    '/academics/subjects/',
    '/academics/academic-years/',
    '/academics/grade-levels/',
    '/academics/tracks/',
    '/academics/grade-options/',
    '/academics/locations/',
    '/academics/promotion/',
]

for p in pages:
    try:
        r = client.get(p)
        print(f"[{r.status_code}] {p}")
        if r.status_code != 200:
            print(f"  Error on {p}: Status {r.status_code}")
    except Exception as e:
        print(f"[EXCEPTION] {p}: {e}")
