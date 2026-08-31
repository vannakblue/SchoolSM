import os
import sys
import django

sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from apps.academics.views import (
    teacher_assignments_manager,
    teacher_assignments_auto_assign,
    teacher_assignments_reset_teacher,
    teacher_assignments_reset_all,
)
from apps.teachers.models import Teacher
from apps.academics.models import ClassSubject, Classroom, Subject

User = get_user_model()
admin_user = User.objects.filter(role='ADMIN').first()
rf = RequestFactory()

print("1. Testing teacher_assignments_auto_assign...")
req = rf.get('/academics/teacher-assignments/auto-assign/')
req.user = admin_user
req.session = {}
setattr(req, '_messages', FallbackStorage(req))
res = teacher_assignments_auto_assign(req)
assert res.status_code == 302
assigned_total = ClassSubject.objects.filter(teacher__isnull=False).count()
assert assigned_total > 0, "Expected some classes assigned"
print(f"   [PASS] Auto-assigned {assigned_total} class-subject pairs!")

first_tch = Teacher.objects.filter(subject_assignments__isnull=False).distinct().first()
assert first_tch is not None
print(f"2. Testing teacher_assignments_reset_teacher for {first_tch.khmer_name}...")
req = rf.get(f'/academics/teacher-assignments/reset-teacher/{first_tch.id}/')
req.user = admin_user
req.session = {}
setattr(req, '_messages', FallbackStorage(req))
res = teacher_assignments_reset_teacher(req, first_tch.id)
assert res.status_code == 302
assert ClassSubject.objects.filter(teacher=first_tch).count() == 0
print(f"   [PASS] Reset single teacher {first_tch.khmer_name} successful (0 assigned)!")

print("3. Testing teacher_assignments_reset_all...")
req = rf.get('/academics/teacher-assignments/reset-all/')
req.user = admin_user
req.session = {}
setattr(req, '_messages', FallbackStorage(req))
res = teacher_assignments_reset_all(req)
assert res.status_code == 302
from apps.academics.utils import get_active_academic_year
ay = get_active_academic_year(req)
if ay:
    assert ClassSubject.objects.filter(classroom__academic_year=ay, teacher__isnull=False).count() == 0
else:
    assert ClassSubject.objects.filter(teacher__isnull=False).count() == 0
print("   [PASS] Reset all assignments successful (0 assigned across active academic year)!")

print("\n=== ALL TEACHER ASSIGNMENT RESET & AUTO-ASSIGN TESTS PASSED 100%! ===")
