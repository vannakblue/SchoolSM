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
    subject_requirements_manager,
    subject_requirements_restore_moeys,
    subject_requirements_save_custom_default,
    subject_requirements_restore_custom_default,
    subject_requirements_reset,
)
from apps.academics.models import GradeLevelRule, Subject, GradeLevel, SavedDefaultConfig

User = get_user_model()
admin_user = User.objects.filter(role='ADMIN').first()
if not admin_user:
    admin_user = User.objects.create_superuser('admin_test', 'admin@test.com', 'adminpass', role='ADMIN')

rf = RequestFactory()

print("1. Testing GET subject_requirements_manager view...")
req = rf.get('/academics/subject-requirements/')
req.user = admin_user
req.session = {}
setattr(req, '_messages', FallbackStorage(req))
res = subject_requirements_manager(req)
assert res.status_code == 200, f"Expected 200, got {res.status_code}"
print("   [PASS] Matrix view rendered with 200 OK!")

print("2. Testing subject_requirements_restore_moeys...")
req = rf.get('/academics/subject-requirements/restore-moeys/')
req.user = admin_user
req.session = {}
setattr(req, '_messages', FallbackStorage(req))
res = subject_requirements_restore_moeys(req)
assert res.status_code == 302, f"Expected 302 redirect, got {res.status_code}"

# Check that Math in 11SC is 6 hours, Khmer in 11SS is 6 hours
math_sub = Subject.objects.get(code='M')
kh_sub = Subject.objects.get(code='K')
math_11sc = GradeLevelRule.objects.get(grade_level=11, track='SCIENCE', subject=math_sub)
kh_11ss = GradeLevelRule.objects.get(grade_level=11, track='SOCIAL', subject=kh_sub)
assert math_11sc.weekly_hours == 6, f"Expected 6 Math hours in 11SC, got {math_11sc.weekly_hours}"
assert kh_11ss.weekly_hours == 6, f"Expected 6 Khmer hours in 11SS, got {kh_11ss.weekly_hours}"
print(f"   [PASS] MoEYS restore successful! (11SC Math = {math_11sc.weekly_hours}h, 11SS Khmer = {kh_11ss.weekly_hours}h)")

print("3. Testing subject_requirements_save_custom_default...")
req = rf.get('/academics/subject-requirements/save-default/')
req.user = admin_user
req.session = {}
setattr(req, '_messages', FallbackStorage(req))
res = subject_requirements_save_custom_default(req)
assert res.status_code == 302
preset = SavedDefaultConfig.objects.filter(key='custom_subject_requirements').first()
assert preset is not None and len(preset.data) > 0
print(f"   [PASS] Custom default saved with {len(preset.data)} rules!")

print("4. Testing subject_requirements_reset and restore_custom_default...")
req = rf.get('/academics/subject-requirements/reset/')
req.user = admin_user
req.session = {}
setattr(req, '_messages', FallbackStorage(req))
res = subject_requirements_reset(req)
assert GradeLevelRule.objects.filter(weekly_hours__gt=0).count() == 0

req = rf.get('/academics/subject-requirements/restore-custom/')
req.user = admin_user
req.session = {}
setattr(req, '_messages', FallbackStorage(req))
res = subject_requirements_restore_custom_default(req)
assert GradeLevelRule.objects.filter(weekly_hours__gt=0).count() > 0
print("   [PASS] Reset and Restore custom default passed!")

print("\n=== ALL SUBJECT REQUIREMENTS TESTS PASSED 100%! ===")
