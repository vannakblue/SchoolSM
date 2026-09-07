import os
import sys

if sys.stdout and sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import RequestFactory
from django.template.loader import render_to_string
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from apps.examinations.models import ExamInvigilatorPlan, TeacherDutyQuota, TeacherDutyGroup, StandardizedExam
from apps.examinations.views import exam_invigilator_plan_create, exam_invigilator_roster_view, exam_invigilator_quotas_manage
from apps.academics.models import AcademicYear
from apps.teachers.models import Teacher

User = get_user_model()

def run_tests():
    print("=== START INTEGRATION TESTS ===")

    # 1. Test roster_matrix.html rendering
    print("\n--- Test 1: roster_matrix.html Template Rendering ---")
    plan = ExamInvigilatorPlan.objects.first()
    if plan:
        print(f"Found existing plan ID: {plan.id} ('{plan.title}')")
        factory = RequestFactory()
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            admin_user = User.objects.first()
        
        request = factory.get(f'/examinations/invigilator-plans/{plan.id}/roster/')
        request.user = admin_user
        setattr(request, 'session', {})
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)

        response = exam_invigilator_roster_view(request, plan_id=plan.id)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert b"TemplateSyntaxError" not in response.content
        print("✅ PASS: roster_matrix.html rendered successfully without syntax error! (Length:", len(response.content), "bytes)")
    else:
        print("⚠️ No existing plan found, testing template directly...")
        context = {
            'plan': None,
            'slots': [],
            'matrix_data': [],
            'active_teachers': [],
            'duty_groups': [],
        }
        content = render_to_string('examinations/invigilators/roster_matrix.html', context)
        print("✅ PASS: roster_matrix.html rendered cleanly from context! (Length:", len(content), "bytes)")

    # 2. Test Unified Quota Model Logic
    print("\n--- Test 2: Unified Quota vs Group Quota Model Logic ---")
    academic_year = AcademicYear.objects.first()
    test_plan, created = ExamInvigilatorPlan.objects.get_or_create(
        title="Test Unified Quota Plan",
        academic_year=academic_year,
        defaults={
            'start_date': '2026-09-15',
            'end_date': '2026-09-16',
            'is_unified_quota': True,
            'unified_quota': 5,
        }
    )
    test_plan.is_unified_quota = True
    test_plan.unified_quota = 5
    test_plan.save()

    # Create duty group with required_shifts = 3
    group, _ = TeacherDutyGroup.objects.get_or_create(
        plan=test_plan,
        name="ក្រុមទី១ (គ្រូបង្រៀនទូទៅ)",
        defaults={'required_shifts': 3}
    )
    group.required_shifts = 3
    group.save()

    admin_user = User.objects.filter(is_superuser=True).first()
    teacher = Teacher.objects.first()
    if not teacher:
        from apps.accounts.models import User as AccUser
        u = AccUser.objects.first()
        teacher = Teacher.objects.create(user=u, teacher_id="T9999", full_name_kh="គ្រូសាកល្បង")
    
    quota, _ = TeacherDutyQuota.objects.get_or_create(
        plan=test_plan,
        teacher=teacher,
        defaults={'duty_group': group}
    )
    quota.duty_group = group
    quota.custom_required_shifts = None
    quota.is_exempt = False
    quota.save()

    # When is_unified_quota = True, effective_required_shifts must be 5 (plan.unified_quota)
    assert quota.effective_required_shifts == 5, f"Expected 5, got {quota.effective_required_shifts}"
    print(f"✅ PASS: When is_unified_quota=True, effective_required_shifts is {quota.effective_required_shifts} (unified_quota=5)")

    # When is_unified_quota = False, effective_required_shifts must fall back to group required_shifts (3)
    test_plan.is_unified_quota = False
    test_plan.save()
    quota.refresh_from_db()
    assert quota.effective_required_shifts == 3, f"Expected 3, got {quota.effective_required_shifts}"
    print(f"✅ PASS: When is_unified_quota=False, effective_required_shifts falls back to group quota {quota.effective_required_shifts} (group=3)")

    # 3. Test Duplicate Plan Creation Prevention
    print("\n--- Test 3: Duplicate Plan Creation Prevention ---")
    factory = RequestFactory()
    request = factory.get(f'/examinations/invigilator-plans/create/?clean_session_name=Test Unified Quota Plan&academic_year={academic_year.id if academic_year else ""}')
    request.user = admin_user
    setattr(request, 'session', {})
    messages = FallbackStorage(request)
    setattr(request, '_messages', messages)

    response = exam_invigilator_plan_create(request)
    # Should redirect because a plan with title "Test Unified Quota Plan" already exists!
    assert response.status_code == 302, f"Expected 302 redirect, got {response.status_code}"
    print(f"✅ PASS: Creating a duplicate plan redirected to: {response.url} (Prevented duplicate screen!)")

    # 4. Test Quotas Manage Action 'set_unified_quota'
    print("\n--- Test 4: Quotas Manage set_unified_quota action ---")
    post_data = {
        'action': 'set_unified_quota',
        'is_unified_quota': 'on',
        'unified_quota': '6',
    }
    request = factory.post(f'/examinations/invigilator-plans/{test_plan.id}/quotas/', data=post_data)
    request.user = admin_user
    setattr(request, 'session', {})
    messages = FallbackStorage(request)
    setattr(request, '_messages', messages)

    response = exam_invigilator_quotas_manage(request, plan_id=test_plan.id)
    assert response.status_code == 302
    test_plan.refresh_from_db()
    group.refresh_from_db()
    assert test_plan.is_unified_quota is True
    assert test_plan.unified_quota == 6
    assert group.required_shifts == 6
    print(f"✅ PASS: set_unified_quota successfully updated plan (is_unified={test_plan.is_unified_quota}, quota={test_plan.unified_quota}) and synchronized group required_shifts={group.required_shifts}!")

    # Clean up test plan
    test_plan.delete()
    print("✅ Cleaned up test plan.")

    print("\n=== ALL INTEGRATION TESTS PASSED SUCCESSFULLY! ===")

if __name__ == '__main__':
    run_tests()
