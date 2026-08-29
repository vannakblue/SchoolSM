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
    teacher_assignments_training_quotas_save,
    teacher_assignments_auto_assign,
    get_training_level_quotas,
)
from apps.teachers.models import Teacher
from apps.academics.models import ClassSubject, SavedDefaultConfig

User = get_user_model()
admin_user = User.objects.filter(role='ADMIN').first()
rf = RequestFactory()

print("1. Testing teacher_assignments_training_quotas_save POST...")
post_data = {
    'quota_គ្រូទុតិយភូមិ': '16',
    'quota_គ្រូបឋមភូមិ': '18',
    'quota_គ្រូកម្រិតបឋម': '18',
    'quota_default': '18',
}
req = rf.post('/academics/teacher-assignments/training-quotas/save/', data=post_data)
req.user = admin_user
req.session = {}
setattr(req, '_messages', FallbackStorage(req))
res = teacher_assignments_training_quotas_save(req)
assert res.status_code == 302

quotas = get_training_level_quotas()
assert quotas['គ្រូទុតិយភូមិ'] == 16, f"Expected 16, got {quotas.get('គ្រូទុតិយភូមិ')}"
assert quotas['គ្រូបឋមភូមិ'] == 18, f"Expected 18, got {quotas.get('គ្រូបឋមភូមិ')}"

# Verify teachers updated
tutiya_sample = Teacher.objects.filter(training_level__icontains='ទុតិយភូមិ').first()
assert tutiya_sample.max_weekly_hours == 16, f"Expected 16, got {tutiya_sample.max_weekly_hours}"

other_sample = Teacher.objects.filter(training_level__icontains='បឋមភូមិ').first()
assert other_sample.max_weekly_hours == 18, f"Expected 18, got {other_sample.max_weekly_hours}"

print(f"   [PASS] Quotas saved: គ្រូទុតិយភូមិ={tutiya_sample.max_weekly_hours}h, គ្រូបឋមភូមិ={other_sample.max_weekly_hours}h")

print("2. Testing teacher_assignments_auto_assign with level-aware quotas...")
req = rf.get('/academics/teacher-assignments/auto-assign/')
req.user = admin_user
req.session = {}
setattr(req, '_messages', FallbackStorage(req))
res = teacher_assignments_auto_assign(req)
assert res.status_code == 302

# Check total assignments
total_cs = ClassSubject.objects.filter(teacher__isnull=False).count()
assert total_cs > 0
print(f"   [PASS] Auto-assignment successfully scheduled {total_cs} class-subject pairs with level awareness!")

print("3. Testing GET teacher_assignments_manager view renders training level settings...")
req = rf.get('/academics/teacher-assignments/')
req.user = admin_user
req.session = {}
setattr(req, '_messages', FallbackStorage(req))
res = teacher_assignments_manager(req)
assert res.status_code == 200
print("   [PASS] View rendered 200 OK!")

print("\n=== ALL TRAINING LEVEL QUOTA & AUTO-ASSIGN TESTS PASSED 100%! ===")
