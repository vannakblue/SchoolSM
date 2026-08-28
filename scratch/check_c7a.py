import os, sys, django
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from apps.academics.models import Classroom, GradeLevelRule, ClassSubject, Subject, AcademicYear
from apps.teachers.models import Teacher
from apps.accounts.models import User
from django.test import Client

ay = AcademicYear.objects.filter(is_current=True).first()
c7a = Classroom.objects.filter(code='7A', academic_year=ay).first()
print(f"c7a: {c7a}, id: {c7a.id if c7a else 'None'}")
teachers = list(Teacher.objects.filter(status='ACTIVE'))
print(f"Total active teachers in DB: {len(teachers)}")
for idx, cs in enumerate(c7a.assigned_subjects.all()):
    if not cs.teacher and teachers:
        cs.teacher = teachers[idx % len(teachers)]
        cs.save(update_fields=['teacher'])
    print(f"  CS: {cs.subject.code} ({cs.subject.name_kh}) -> teacher: {cs.teacher}")
    print("Grade 7 rules:")
    for r in GradeLevelRule.objects.filter(grade_level=7, track='GENERAL'):
        print(f"  Rule: {r.subject.code} ({r.subject.name_kh}) -> weekly_hours: {r.weekly_hours}, max_score: {r.max_score}")

client = Client()
admin = User.objects.filter(role=User.Role.ADMIN).first()
client.force_login(admin)
res = client.post('/academics/timetable/auto-generate/', {
    'classroom_id': c7a.id,
    'clear_existing': 'true',
}, follow=True)
print("Auto-generate status:", res.status_code)
from apps.academics.models import Timetable
print("Timetable slots for 7A:", Timetable.objects.filter(classroom=c7a).count())
