import os
import sys
import django
import json
from datetime import date, time

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.accounts.models import User
from apps.teachers.models import Teacher
from apps.academics.models import AcademicYear
from apps.examinations.models import (
    ExamInvigilatorPlan, ExamShiftSlot, TeacherDutyGroup,
    TeacherDutyQuota, TeacherShiftRegistration, ExamCommitteeRole
)
from apps.examinations.views import (
    api_toggle_invigilator_slot,
    api_finalize_invigilator_request,
    api_unlock_invigilator_request,
    exam_invigilator_teacher_portal
)
from apps.mobile_api.views import (
    MobileExamInvigilatorToggleAPIView,
    MobileExamInvigilatorFinalizeAPIView,
    MobileExamInvigilatorStatusAPIView
)

def run_tests():
    print("=" * 70)
    print("STARTING STRICT EXACT TEACHER SHIFT QUOTA TESTS")
    print("=" * 70)

    # 1. Setup AcademicYear & Active Plan
    year, _ = AcademicYear.objects.get_or_create(name="2025-2026", defaults={'start_date': date(2025, 10, 1), 'end_date': date(2026, 8, 31)})
    
    # Deactivate existing active plans for clean test environment
    ExamInvigilatorPlan.objects.all().update(is_active=False)

    plan = ExamInvigilatorPlan.objects.create(
        title="សម័យប្រឡងសាកល្បងកូតាគ្រូ",
        academic_year=year,
        start_date=date(2026, 9, 10),
        end_date=date(2026, 9, 12),
        default_regular_quota=4,  # REQUIRED QUOTA = 4 SHIFTS
        is_active=True,
        allow_teacher_registration=True
    )
    plan.ensure_default_role_settings()

    # Create 6 shift slots (so there are enough slots to test attempting > 4)
    slots = []
    for i in range(1, 7):
        s = ExamShiftSlot.objects.create(
            plan=plan,
            date=date(2026, 9, 10 + (i // 3)),
            session=ExamShiftSlot.Session.MORNING if i % 2 != 0 else ExamShiftSlot.Session.AFTERNOON,
            session_name=f"វេនទី {i} (Slot {i})",
            start_time=time(7, 0) if i % 2 != 0 else time(13, 0),
            end_time=time(11, 0) if i % 2 != 0 else time(17, 0),
            max_invigilators=10,
            order=i
        )
        slots.append(s)

    # Create Test Teacher & User
    user, _ = User.objects.get_or_create(
        username="test_quota_teacher_2026",
        defaults={'role': 'TEACHER', 'first_name': 'គ្រូ', 'last_name': 'តេស្ត'}
    )
    user.set_password('pass123')
    user.save()

    teacher, _ = Teacher.objects.get_or_create(
        user=user,
        defaults={'teacher_id': 'T-QUOTA-001', 'khmer_name': 'លោកគ្រូ សុខ ពិសិដ្ឋ', 'status': Teacher.Status.ACTIVE}
    )

    factory = RequestFactory()

    # -------------------------------------------------------------
    # TEST 1: Teacher Quota is 4 shifts. Selecting 1 to 4 shifts succeeds.
    # -------------------------------------------------------------
    print("\n--- TEST 1: Selecting 1 to 4 shifts (up to exact quota 4) ---")
    for i in range(4):
        req = factory.post('/examinations/api/invigilator-slot/toggle/', {'slot_id': slots[i].id})
        req.user = user
        resp = api_toggle_invigilator_slot(req)
        data = json.loads(resp.content)
        assert resp.status_code == 200, f"Slot {i+1} toggle failed: {data}"
        assert data['success'] is True
        assert data['is_registered'] is True
        assert data['current_count'] == i + 1
        print(f"  ✓ Slot {i+1} selected successfully. Current count: {data['current_count']}/{data['required_shifts']}")

    assert TeacherShiftRegistration.objects.filter(slot__plan=plan, teacher=teacher).count() == 4
    print("  ✓ DB count is exactly 4.")

    # -------------------------------------------------------------
    # TEST 2: Attempting to select 5th shift (CANNOT EXCEED: មិនអាចលើស)
    # -------------------------------------------------------------
    print("\n--- TEST 2: Attempting to select 5th shift (Exceed Quota Guard) ---")
    req5 = factory.post('/examinations/api/invigilator-slot/toggle/', {'slot_id': slots[4].id})
    req5.user = user
    resp5 = api_toggle_invigilator_slot(req5)
    data5 = json.loads(resp5.content)
    assert resp5.status_code == 400, f"Expected HTTP 400 rejection, got {resp5.status_code}"
    assert data5['success'] is False
    assert "មិនអាចជ្រើសរើសលើសពីនេះបានទេ" in data5['error'], f"Unexpected error message: {data5['error']}"
    assert TeacherShiftRegistration.objects.filter(slot__plan=plan, teacher=teacher).count() == 4
    print(f"  ✓ Rejection verified! HTTP 400 returned.")
    print(f"  ✓ Error message: {data5['error']}")
    print("  ✓ Shift 5 was NOT added. Count remains 4/4.")

    # -------------------------------------------------------------
    # TEST 3: Attempting to finalize when under quota (CANNOT FALL SHORT: មិនអាចខ្វះ)
    # -------------------------------------------------------------
    print("\n--- TEST 3: Finalize when under quota (e.g. 3/4 shifts) ---")
    # Deselect slot 4 so count becomes 3
    req_del = factory.post('/examinations/api/invigilator-slot/toggle/', {'slot_id': slots[3].id})
    req_del.user = user
    resp_del = api_toggle_invigilator_slot(req_del)
    data_del = json.loads(resp_del.content)
    assert data_del['current_count'] == 3

    # Try to finalize with 3 shifts
    req_fin_fail = factory.post('/examinations/api/invigilator-request/finalize/')
    req_fin_fail.user = user
    resp_fin_fail = api_finalize_invigilator_request(req_fin_fail)
    data_fin_fail = json.loads(resp_fin_fail.content)
    assert resp_fin_fail.status_code == 400, f"Expected HTTP 400 rejection, got {resp_fin_fail.status_code}"
    assert data_fin_fail['success'] is False
    assert "នៅខ្វះ 1 វេនទៀត" in data_fin_fail['error']
    print(f"  ✓ Rejection verified! HTTP 400 returned.")
    print(f"  ✓ Error message: {data_fin_fail['error']}")

    quota_obj = TeacherDutyQuota.objects.filter(plan=plan, teacher=teacher).first()
    assert quota_obj is not None
    assert quota_obj.is_finalized is False
    print("  ✓ is_finalized remains False in DB.")

    # -------------------------------------------------------------
    # TEST 4: Selecting back to exact 4 shifts and Finalizing (SUCCESS)
    # -------------------------------------------------------------
    print("\n--- TEST 4: Reaching exact 4/4 shifts and Finalizing successfully ---")
    req_add_back = factory.post('/examinations/api/invigilator-slot/toggle/', {'slot_id': slots[3].id})
    req_add_back.user = user
    resp_add_back = api_toggle_invigilator_slot(req_add_back)
    data_add_back = json.loads(resp_add_back.content)
    assert data_add_back['current_count'] == 4
    assert data_add_back['can_finalize'] is True
    print("  ✓ Count back to 4/4. can_finalize is True.")

    # Call finalize
    req_fin_ok = factory.post('/examinations/api/invigilator-request/finalize/')
    req_fin_ok.user = user
    resp_fin_ok = api_finalize_invigilator_request(req_fin_ok)
    data_fin_ok = json.loads(resp_fin_ok.content)
    assert resp_fin_ok.status_code == 200, f"Expected HTTP 200, got {resp_fin_ok.status_code}: {data_fin_ok}"
    assert data_fin_ok['success'] is True
    assert data_fin_ok['is_finalized'] is True
    print(f"  ✓ Finalize successful! Message: {data_fin_ok['message']}")

    quota_obj.refresh_from_db()
    assert quota_obj.is_finalized is True
    assert quota_obj.finalized_at is not None
    print(f"  ✓ DB verified: is_finalized=True, finalized_at={quota_obj.finalized_at}")

    # -------------------------------------------------------------
    # TEST 5: While finalized, cannot add more slots without unlocking
    # -------------------------------------------------------------
    print("\n--- TEST 5: While finalized, locked against adding slots ---")
    req_locked = factory.post('/examinations/api/invigilator-slot/toggle/', {'slot_id': slots[5].id})
    req_locked.user = user
    resp_locked = api_toggle_invigilator_slot(req_locked)
    data_locked = json.loads(resp_locked.content)
    assert resp_locked.status_code == 400
    assert "បានបញ្ចប់ការស្នើសុំរួចរាល់ហើយ" in data_locked['error']
    print(f"  ✓ Blocked with message: {data_locked['error']}")

    # -------------------------------------------------------------
    # TEST 6: Unlock request to adjust shifts
    # -------------------------------------------------------------
    print("\n--- TEST 6: Unlock request and swap shifts ---")
    req_unlock = factory.post('/examinations/api/invigilator-request/unlock/')
    req_unlock.user = user
    resp_unlock = api_unlock_invigilator_request(req_unlock)
    data_unlock = json.loads(resp_unlock.content)
    assert resp_unlock.status_code == 200
    assert data_unlock['is_finalized'] is False
    
    quota_obj.refresh_from_db()
    assert quota_obj.is_finalized is False
    print("  ✓ Unlocked successfully! Teacher can now modify shifts.")

    # Swap slot 4 for slot 5
    req_rm4 = factory.post('/examinations/api/invigilator-slot/toggle/', {'slot_id': slots[3].id})
    req_rm4.user = user
    api_toggle_invigilator_slot(req_rm4)
    
    req_add5 = factory.post('/examinations/api/invigilator-slot/toggle/', {'slot_id': slots[4].id})
    req_add5.user = user
    api_toggle_invigilator_slot(req_add5)

    assert TeacherShiftRegistration.objects.filter(slot__plan=plan, teacher=teacher).count() == 4
    # Finalize again
    resp_refin = api_finalize_invigilator_request(req_fin_ok)
    assert resp_refin.status_code == 200
    quota_obj.refresh_from_db()
    assert quota_obj.is_finalized is True
    print("  ✓ Shift swapped and re-finalized with exactly 4 shifts!")

    # -------------------------------------------------------------
    # TEST 7: Mobile APIs (Toggle, Finalize, Status)
    # -------------------------------------------------------------
    print("\n--- TEST 7: Mobile REST APIs Quota Verification ---")
    from rest_framework.test import APIClient
    # Unlock for mobile testing
    api_unlock_invigilator_request(req_unlock)

    client = APIClient()
    client.force_authenticate(user=user)

    # Teacher currently has 4 shifts (slots 0, 1, 2, 4)
    # Attempting to add slot 6 on mobile -> must reject with HTTP 400!
    resp_mob_exceed = client.post('/api/v1/exam-invigilator/toggle/', {'slot_id': slots[5].id}, format='json')
    assert resp_mob_exceed.status_code == 400, f"Expected 400, got {resp_mob_exceed.status_code}: {resp_mob_exceed.data}"
    assert "មិនអាចជ្រើសរើសលើសពីនេះបានទេ" in resp_mob_exceed.data['message']
    print(f"  ✓ Mobile Toggle rejected excess shift: {resp_mob_exceed.data['message']}")

    # Finalize on mobile
    resp_mob_fin = client.post('/api/v1/exam-invigilator/finalize/', {}, format='json')
    assert resp_mob_fin.status_code == 200, f"Expected 200, got {resp_mob_fin.status_code}: {resp_mob_fin.data}"
    assert resp_mob_fin.data['status'] == 'success'
    assert resp_mob_fin.data['is_finalized'] is True
    print(f"  ✓ Mobile Finalize succeeded: {resp_mob_fin.data['message']}")

    # Check Mobile Status
    resp_mob_stat = client.get('/api/v1/exam-invigilator/status/')
    assert resp_mob_stat.status_code == 200
    t_data = resp_mob_stat.data['teacher']
    assert t_data['current_count'] == 4
    assert t_data['required_shifts'] == 4
    assert t_data['is_exact_matched'] is True
    assert t_data['is_finalized'] is True
    print(f"  ✓ Mobile Status verified: count={t_data['current_count']}/{t_data['required_shifts']}, is_finalized={t_data['is_finalized']}")


    # -------------------------------------------------------------
    # TEST 8: Teacher Portal View Rendering
    # -------------------------------------------------------------
    print("\n--- TEST 8: Teacher Portal Web View Rendering ---")
    req_portal = factory.get('/examinations/invigilator-request/')
    req_portal.user = user
    resp_portal = exam_invigilator_teacher_portal(req_portal)
    assert resp_portal.status_code == 200
    content = resp_portal.content.decode('utf-8')
    assert "វឌ្ឍនភាពនៃការជ្រើសរើស" in content
    assert "finalizeConfirmModal" in content
    assert "បានបញ្ចប់ការស្នើសុំរួចរាល់" in content or "គ្រប់ 4 វេន" in content
    print("  ✓ Web Teacher Portal rendered successfully with finalize modal and status!")

    print("\n" + "=" * 70)
    print("🎉 ALL 8 STRICT EXACT TEACHER QUOTA TESTS PASSED 100%!")
    print("=" * 70)

if __name__ == '__main__':
    run_tests()
