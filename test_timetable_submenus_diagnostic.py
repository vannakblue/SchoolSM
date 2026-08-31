import os
import django
import sys
import traceback

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.conf import settings
from django.test import RequestFactory, Client
from apps.accounts.models import User
from apps.academics import views as ac_views
from apps.teachers.models import Teacher
from apps.academics.models import AcademicYear, Classroom, Subject, ClassSubject, GradeLevelRule

def run_diagnostics():
    print("=== RUNNING TIMETABLE & ASSIGNMENT SUBMENUS DIAGNOSTIC (DEBUG=False) ===")
    settings.DEBUG = False
    
    admin_user = User.objects.filter(role='ADMIN').first()
    if not admin_user:
        admin_user = User.objects.create_superuser('admin_diag', 'diag@school.com', 'adminpass123')

    client = Client()
    client.force_login(admin_user)

    urls_to_test = [
        ('/academics/timetable/', 'Master Timetable'),
        ('/academics/timetable/daily-reports/', 'Daily Duty Reports'),
        ('/academics/timetable/student-teacher/', 'Student-Teacher Timetable'),
        ('/academics/subject-requirements/', 'Subject Requirements Matrix'),
        ('/academics/teacher-assignments/', 'Teacher Assignments Manager'),
        ('/academics/duty-schedule/', 'Teacher Duty Manager'),
    ]

    for url, name in urls_to_test:
        try:
            resp = client.get(url)
            print(f"[{name}] {url} -> Status: {resp.status_code}")
            if resp.status_code != 200:
                print(f"  ❌ ERROR CONTENT:\n{resp.content.decode('utf-8', errors='ignore')[:500]}")
        except Exception as e:
            print(f"  ❌ EXCEPTION in {name} ({url}): {e}")
            traceback.print_exc()

if __name__ == '__main__':
    run_diagnostics()
