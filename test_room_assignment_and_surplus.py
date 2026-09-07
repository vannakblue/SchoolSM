import os
import sys
import django
import datetime
import json

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.messages.storage.fallback import FallbackStorage
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import User
from apps.academics.models import AcademicYear
from apps.examinations.models import (
    ExamInvigilatorPlan, ExamShiftSlot, TeacherShiftRegistration, ExamCommitteeRole, TeacherDutyQuota
)
from apps.examinations.views import (
    allocate_rooms_for_slot, exam_invigilator_roster_view,
    api_toggle_invigilator_slot, api_finalize_invigilator_request, api_unlock_invigilator_request
)
from apps.mobile_api.views import (
    MobileExamInvigilatorToggleAPIView, MobileExamInvigilatorFinalizeAPIView, MobileExamInvigilatorUnlockAPIView
)
from apps.teachers.models import Teacher


def run_tests():
    print("================================================================================")
    print("RUNNING TESTS: RANDOM ROOM ALLOCATION, SHORTAGE, SURPLUS & 1-TIME SUBMISSION")
    print("================================================================================")

    factory = RequestFactory()
    api_factory = APIRequestFactory()

    # Users
    admin_user, _ = User.objects.get_or_create(
        username='admin_room_test',
        defaults={'role': User.Role.ADMIN, 'is_staff': True, 'is_superuser': True}
    )

    teacher_user, _ = User.objects.get_or_create(
        username='teacher_portal_user',
        defaults={'role': User.Role.TEACHER}
    )

    t_main, _ = Teacher.objects.get_or_create(
        teacher_id='T_MAIN_TEST',
        defaults={
            'khmer_name': 'សុខ សប្បាយ',
            'latin_name': 'Sok Sabay',
            'user': teacher_user,
            'status': Teacher.Status.ACTIVE
        }
    )
    if not t_main.user:
        t_main.user = teacher_user
        t_main.save(update_fields=['user'])

    ay = AcademicYear.objects.filter(is_current=True).first() or AcademicYear.objects.first()

    ExamInvigilatorPlan.objects.all().update(is_active=False)

    # Create plan with 5 rooms, 2 invigilators per room (total capacity = 10)
    plan, _ = ExamInvigilatorPlan.objects.get_or_create(
        title="តេស្តចាត់បន្ទប់ និងលើសអនុរក្ស",
        academic_year=ay,
        defaults={
            'start_date': datetime.date(2026, 8, 10),
            'end_date': datetime.date(2026, 8, 10),
            'is_active': True,
            'allow_teacher_registration': True,
            'rooms_count': 5,
            'invigilators_per_room': 2,
            'default_regular_quota': 2,
        }
    )
    plan.rooms_count = 5
    plan.invigilators_per_room = 2
    plan.is_active = True
    plan.allow_teacher_registration = True
    plan.save()
    ExamInvigilatorPlan.objects.exclude(id=plan.id).update(is_active=False)

    # Create Shift Slot
    slot, _ = ExamShiftSlot.objects.get_or_create(
        plan=plan,
        date=datetime.date(2026, 8, 10),
        session=ExamShiftSlot.Session.MORNING,
        defaults={
            'session_name': 'ថ្ងៃទី១ - ព្រឹក (Slot Test)',
            'order': 1,
            'max_invigilators': 20
        }
    )

    # Clean prior registrations for this slot
    TeacherShiftRegistration.objects.filter(slot=slot).delete()

    # Create 14 teachers
    teachers = []
    for i in range(1, 15):
        t, _ = Teacher.objects.get_or_create(
            teacher_id=f'T_TEST_{i:02d}',
            defaults={
                'khmer_name': f'គ្រូ តេស្ត {i:02d}',
                'latin_name': f'Teacher Test {i:02d}',
                'status': Teacher.Status.ACTIVE
            }
        )
        teachers.append(t)

    # -------------------------------------------------------------------------
    # TEST 1: Shortage Case (6 teachers available for 5 rooms x 2 = 10 spots)
    # -------------------------------------------------------------------------
    print("\n--- TEST 1: Shortage Case (6 teachers for 10 spots) ---")
    for t in teachers[:6]:
        TeacherShiftRegistration.objects.create(
            slot=slot, teacher=t, role=ExamCommitteeRole.INVIGILATOR, status='CONFIRMED'
        )

    res_short = allocate_rooms_for_slot(slot, plan)
    assert res_short['total_rooms'] == 5, f"Expected 5 rooms, got {res_short['total_rooms']}"
    assert res_short['required_invigilators'] == 10
    assert res_short['total_invigilators'] == 6
    assert res_short['assigned_count'] == 6
    assert res_short['missing_count'] == 4
    assert res_short['surplus_count'] == 0
    assert len(res_short['missing_rooms']) > 0
    print(f"1. [PASS] Shortage detected: missing 4 invigilators on {len(res_short['missing_rooms'])} rooms.")
    for m in res_short['missing_rooms']:
        print(f"   -> {m['room']}: Assigned={m['assigned']}, Required={m['required']}, Missing={m['missing']}")

    # -------------------------------------------------------------------------
    # TEST 2: Surplus Case (13 teachers for 10 room spots -> 3 surplus)
    # -------------------------------------------------------------------------
    print("\n--- TEST 2: Surplus Case (13 teachers for 10 spots) ---")
    for t in teachers[6:13]:
        TeacherShiftRegistration.objects.create(
            slot=slot, teacher=t, role=ExamCommitteeRole.INVIGILATOR, status='CONFIRMED'
        )

    res_surplus = allocate_rooms_for_slot(slot, plan)
    assert res_surplus['total_invigilators'] == 13
    assert res_surplus['assigned_count'] == 10
    assert res_surplus['missing_count'] == 0
    assert res_surplus['surplus_count'] == 3
    print(f"2. [PASS] Surplus detected: exactly 10 rooms filled, 3 teachers marked as surplus.")

    # Check that the 3 surplus teachers have room_assignment == ""
    surplus_db = slot.registrations.filter(role=ExamCommitteeRole.INVIGILATOR, room_assignment="")
    assert surplus_db.count() == 3, f"Expected 3 surplus in DB, got {surplus_db.count()}"

    # -------------------------------------------------------------------------
    # TEST 3: Single Surplus Reassignment
    # -------------------------------------------------------------------------
    print("\n--- TEST 3: Single Surplus Reassignment ---")
    first_surplus = surplus_db.first()
    req_single = factory.post(f'/examinations/invigilator-plans/{plan.id}/roster/', {
        'action': 'reassign_surplus_teachers',
        'registration_id': str(first_surplus.id),
        'target_role': ExamCommitteeRole.SECRETARIAT,
    })
    req_single.user = admin_user
    req_single.session = SessionStore()
    setattr(req_single, '_messages', FallbackStorage(req_single))

    exam_invigilator_roster_view(req_single, plan_id=plan.id)
    first_surplus.refresh_from_db()
    assert first_surplus.role == ExamCommitteeRole.SECRETARIAT, f"Expected SECRETARIAT, got {first_surplus.role}"
    assert first_surplus.status == 'ADMIN_ASSIGNED'
    assert first_surplus.room_assignment == ""
    print(f"3. [PASS] Single surplus teacher {first_surplus.teacher.khmer_name} reassigned to SECRETARIAT.")

    # -------------------------------------------------------------------------
    # TEST 4: Batch Surplus Reassignment
    # -------------------------------------------------------------------------
    print("\n--- TEST 4: Batch Surplus Reassignment ---")
    remaining_surplus = list(slot.registrations.filter(role=ExamCommitteeRole.INVIGILATOR, room_assignment=""))
    assert len(remaining_surplus) == 2, f"Expected 2 remaining surplus, got {len(remaining_surplus)}"

    batch_ids = [str(r.id) for r in remaining_surplus]
    req_batch = factory.post(f'/examinations/invigilator-plans/{plan.id}/roster/', {
        'action': 'reassign_surplus_teachers',
        'selected_reg_ids': batch_ids,
        'target_role': ExamCommitteeRole.BUILDING_INSPECTOR,
    })
    req_batch.user = admin_user
    req_batch.session = SessionStore()
    setattr(req_batch, '_messages', FallbackStorage(req_batch))

    exam_invigilator_roster_view(req_batch, plan_id=plan.id)
    for r in remaining_surplus:
        r.refresh_from_db()
        assert r.role == ExamCommitteeRole.BUILDING_INSPECTOR, f"Expected BUILDING_INSPECTOR, got {r.role}"
        assert r.status == 'ADMIN_ASSIGNED'
    print(f"4. [PASS] Batch reassigned {len(remaining_surplus)} surplus teachers to BUILDING_INSPECTOR.")

    # -------------------------------------------------------------------------
    # TEST 5: Strict One-Time Teacher Submission & Locking
    # -------------------------------------------------------------------------
    print("\n--- TEST 5: Strict One-Time Teacher Submission & Locking ---")
    # Clean up t_main
    TeacherShiftRegistration.objects.filter(slot__plan=plan, teacher=t_main).delete()
    quota_main, _ = TeacherDutyQuota.objects.get_or_create(plan=plan, teacher=t_main)
    quota_main.is_finalized = False
    quota_main.custom_required_shifts = 1
    quota_main.save()

    # Create slot 2 for testing
    slot2, _ = ExamShiftSlot.objects.get_or_create(
        plan=plan,
        date=datetime.date(2026, 8, 10),
        session=ExamShiftSlot.Session.AFTERNOON,
        defaults={
            'session_name': 'ថ្ងៃទី១ - រសៀល (Slot 2)',
            'order': 2,
            'max_invigilators': 20
        }
    )

    # Step 1: Teacher registers 1 slot
    req_toggle = factory.post('/examinations/invigilator-plans/api/toggle-slot/', {
        'slot_id': str(slot.id)
    })
    req_toggle.user = teacher_user
    req_toggle.session = SessionStore()
    resp_toggle = api_toggle_invigilator_slot(req_toggle)
    data_toggle = json.loads(resp_toggle.content.decode('utf-8'))
    assert data_toggle['success'] is True, f"Toggle failed: {data_toggle}"
    print("5.1 [PASS] Teacher registered 1 slot.")

    # Step 2: Teacher finalizes
    req_final = factory.post('/examinations/invigilator-plans/api/finalize/')
    req_final.user = teacher_user
    req_final.session = SessionStore()
    resp_final = api_finalize_invigilator_request(req_final)
    data_final = json.loads(resp_final.content.decode('utf-8'))
    assert data_final['success'] is True, f"Finalize failed: {data_final}"
    quota_main.refresh_from_db()
    assert quota_main.is_finalized is True
    print("5.2 [PASS] Teacher finalized shift submission.")

    # Step 3: Teacher attempts to finalize AGAIN -> REJECTED (cannot create > once)
    resp_final_again = api_finalize_invigilator_request(req_final)
    data_final_again = json.loads(resp_final_again.content.decode('utf-8'))
    assert data_final_again['success'] is False
    assert "លើសពីម្តង" in data_final_again['error']
    print("5.3 [PASS] Submitting more than once strictly blocked.")

    # Step 4: Teacher attempts to toggle OFF while finalized -> REJECTED
    req_toggle_off = factory.post('/examinations/invigilator-plans/api/toggle-slot/', {
        'slot_id': str(slot.id)
    })
    req_toggle_off.user = teacher_user
    req_toggle_off.session = SessionStore()
    resp_toggle_off = api_toggle_invigilator_slot(req_toggle_off)
    data_toggle_off = json.loads(resp_toggle_off.content.decode('utf-8'))
    assert data_toggle_off['success'] is False
    assert "មិនអាចកែប្រែ" in data_toggle_off['error'] or "លើសពីម្តង" in data_toggle_off['error']
    print("5.4 [PASS] Modifying/toggling slots while finalized strictly blocked for teacher.")

    # Step 5: Regular teacher attempts to unlock themselves -> REJECTED (403)
    req_unlock_teacher = factory.post('/examinations/invigilator-plans/api/unlock/')
    req_unlock_teacher.user = teacher_user
    req_unlock_teacher.session = SessionStore()
    resp_unlock_teacher = api_unlock_invigilator_request(req_unlock_teacher)
    assert resp_unlock_teacher.status_code == 403
    print("5.5 [PASS] Teacher self-unlock strictly prohibited (HTTP 403).")

    # Step 6: Admin unlocks teacher via roster matrix POST action
    req_admin_unlock = factory.post(f'/examinations/invigilator-plans/{plan.id}/roster/', {
        'action': 'admin_unlock_teacher',
        'quota_id': str(quota_main.id)
    })
    req_admin_unlock.user = admin_user
    req_admin_unlock.session = SessionStore()
    setattr(req_admin_unlock, '_messages', FallbackStorage(req_admin_unlock))
    exam_invigilator_roster_view(req_admin_unlock, plan_id=plan.id)
    quota_main.refresh_from_db()
    assert quota_main.is_finalized is False
    print("5.6 [PASS] Admin successfully unlocked teacher submission.")

    # -------------------------------------------------------------------------
    # TEST 6: Mobile API One-Time Submission & Locking Verification
    # -------------------------------------------------------------------------
    print("\n--- TEST 6: Mobile API Verification ---")
    # Teacher finalizes via mobile API
    req_mob_final = api_factory.post('/api/v1/mobile/examinations/invigilators/finalize/', {}, format='json')
    force_authenticate(req_mob_final, user=teacher_user)
    resp_mob_final = MobileExamInvigilatorFinalizeAPIView.as_view()(req_mob_final)
    assert resp_mob_final.status_code == 200
    quota_main.refresh_from_db()
    assert quota_main.is_finalized is True
    print("6.1 [PASS] Mobile API finalize succeeded.")

    # Second finalize on mobile -> 400
    resp_mob_again = MobileExamInvigilatorFinalizeAPIView.as_view()(req_mob_final)
    assert resp_mob_again.status_code == 400
    assert "លើសពីម្តង" in resp_mob_again.data['message']
    print("6.2 [PASS] Mobile API second finalize rejected (400).")

    # Mobile toggle while finalized -> 400
    req_mob_toggle = api_factory.post('/api/v1/mobile/examinations/invigilators/toggle/', {'slot_id': slot.id}, format='json')
    force_authenticate(req_mob_toggle, user=teacher_user)
    resp_mob_toggle = MobileExamInvigilatorToggleAPIView.as_view()(req_mob_toggle)
    assert resp_mob_toggle.status_code == 400
    print("6.3 [PASS] Mobile API toggle while finalized rejected (400).")

    # Mobile unlock as teacher -> 403
    req_mob_unlock = api_factory.post('/api/v1/mobile/examinations/invigilators/unlock/', {}, format='json')
    force_authenticate(req_mob_unlock, user=teacher_user)
    resp_mob_unlock = MobileExamInvigilatorUnlockAPIView.as_view()(req_mob_unlock)
    assert resp_mob_unlock.status_code == 403
    print("6.4 [PASS] Mobile API unlock as regular teacher rejected (403).")

    # Mobile unlock as admin -> 200
    force_authenticate(req_mob_unlock, user=admin_user)
    req_mob_unlock_admin = api_factory.post('/api/v1/mobile/examinations/invigilators/unlock/', {'teacher_id': t_main.id}, format='json')
    force_authenticate(req_mob_unlock_admin, user=admin_user)
    resp_mob_unlock_admin = MobileExamInvigilatorUnlockAPIView.as_view()(req_mob_unlock_admin)
    assert resp_mob_unlock_admin.status_code == 200
    quota_main.refresh_from_db()
    assert quota_main.is_finalized is False
    print("6.5 [PASS] Mobile API unlock as Admin allowed (200).")

    print("\n================================================================================")
    print("🎉 ALL TESTS PASSED (100%)! ROOM ALLOCATION, SHORTAGE, SURPLUS & 1-TIME RULES COMPLIANT.")
    print("================================================================================")


if __name__ == '__main__':
    run_tests()
