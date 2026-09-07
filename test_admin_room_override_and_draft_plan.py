import os
import sys
import django
import datetime

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.messages.storage.fallback import FallbackStorage

from apps.accounts.models import User
from apps.academics.models import AcademicYear
from apps.examinations.models import (
    ExamInvigilatorPlan,
    ExamShiftSlot,
    TeacherShiftRegistration,
    ExamCommitteeRole,
    TeacherDutyQuota,
    StandardizedExam,
)
from apps.examinations.views import (
    exam_invigilator_plan_create,
    exam_invigilator_plan_edit,
    exam_invigilator_roster_view,
    exam_invigilator_plan_toggle_active,
    api_toggle_invigilator_slot,
    allocate_rooms_for_slot,
)
from apps.teachers.models import Teacher


def run_tests():
    print("=" * 80)
    print("RUNNING VERIFICATION: ADMIN ROOM EDITING & DRAFT PLAN MULTIPLE EDITS")
    print("=" * 80)

    factory = RequestFactory()

    # 1. Setup Admin & Teachers
    admin_user, _ = User.objects.get_or_create(
        username="admin_override_verifier",
        defaults={"role": User.Role.ADMIN, "is_staff": True, "is_superuser": True}
    )
    admin_user.role = User.Role.ADMIN
    admin_user.is_staff = True
    admin_user.is_superuser = True
    admin_user.save()

    teacher_user, _ = User.objects.get_or_create(
        username="teacher_override_01",
        defaults={"role": User.Role.TEACHER}
    )
    t_main, _ = Teacher.objects.get_or_create(
        teacher_id="T_VERIF_01",
        defaults={
            "khmer_name": "សុខ ពិសិដ្ឋ",
            "latin_name": "Sok Piseth",
            "user": teacher_user,
            "status": Teacher.Status.ACTIVE,
        }
    )

    ay = AcademicYear.objects.filter(is_current=True).first() or AcademicYear.objects.first()
    if not ay:
        ay, _ = AcademicYear.objects.get_or_create(
            name="2025-2026",
            defaults={
                "start_date": datetime.date(2025, 10, 1),
                "end_date": datetime.date(2026, 8, 31),
                "is_active": True,
            }
        )

    # -------------------------------------------------------------------------
    # TEST 0: Admin Creates Plan using Form with days_count (e.g. 3 days)
    # -------------------------------------------------------------------------
    print("\n--- TEST 0: Admin Creates Plan using Form with days_count ---")
    ExamInvigilatorPlan.objects.filter(title__contains="បង្កើតថ្មី ៣ ថ្ងៃ").delete()
    req_create = factory.post("/examinations/invigilator-plans/create/", {
        "title": "គម្រោងវេនអនុរក្សប្រឡង សាកល្បងបង្កើតថ្មី ៣ ថ្ងៃ",
        "academic_year": ay.id,
        "start_date": "2026-09-10",
        "days_count": "3",
        "auto_create_slots": "on",
        "rooms_count": "4",
        "invigilators_per_room": "2",
        "capacity_invigilator": "8",
    })
    req_create.user = admin_user
    setattr(req_create, 'session', {})
    setattr(req_create, '_messages', FallbackStorage(req_create))

    resp_create = exam_invigilator_plan_create(req_create)
    created_plan = ExamInvigilatorPlan.objects.filter(title="គម្រោងវេនអនុរក្សប្រឡង សាកល្បងបង្កើតថ្មី ៣ ថ្ងៃ").first()
    assert created_plan is not None, "Created plan must exist in database"
    assert created_plan.duration_days == 3, f"Expected duration_days=3, got {created_plan.duration_days}"
    assert created_plan.end_date == datetime.date(2026, 9, 12), f"Expected end_date=2026-09-12, got {created_plan.end_date}"
    assert created_plan.shift_slots.count() == 6, f"Expected 6 slots for 3 days, got {created_plan.shift_slots.count()}"
    print(f"0. [PASS] Plan successfully created via form: 3 days, end_date={created_plan.end_date}, {created_plan.shift_slots.count()} shift slots.")

    # -------------------------------------------------------------------------
    # TEST 1: Admin Creates Plan in DRAFT Mode (is_active=False)
    # -------------------------------------------------------------------------
    print("\n--- TEST 1: Admin Creates Plan in DRAFT Mode ---")
    ExamInvigilatorPlan.objects.filter(title__contains="សាកល្បងព្រាងទុក").delete()
    plan = ExamInvigilatorPlan.objects.create(
        title="គម្រោងវេនអនុរក្សប្រឡង សាកល្បងព្រាងទុក",
        academic_year=ay,
        start_date=datetime.date(2026, 9, 10),
        end_date=datetime.date(2026, 9, 11),
        is_active=False,  # Draft Mode
        allow_teacher_registration=False,
        invigilators_per_room=2,
        rooms_count=4,
        default_regular_quota=4,
    )
    plan.ensure_default_role_settings()

    slot1 = ExamShiftSlot.objects.create(
        plan=plan,
        date=datetime.date(2026, 9, 10),
        session=ExamShiftSlot.Session.MORNING,
        session_name="10/09/2026 - ព្រឹក",
        start_time=datetime.time(7, 0),
        end_time=datetime.time(11, 0),
        max_invigilators=8,
        order=1
    )

    assert not plan.is_active, "Plan must start inactive (Draft Mode)"
    assert not plan.allow_teacher_registration, "Teacher registration must be closed in Draft Mode"
    print("1. [PASS] Plan created in DRAFT mode (is_active=False, allow_teacher_registration=False).")

    # -------------------------------------------------------------------------
    # TEST 2: Teachers CANNOT register while plan is in DRAFT mode / inactive
    # -------------------------------------------------------------------------
    print("\n--- TEST 2: Teacher registration blocked when plan is inactive/draft ---")
    req = factory.post("/examinations/api/invigilator-slot/toggle/", {"slot_id": slot1.id})
    req.user = teacher_user
    setattr(req, 'session', {})
    resp = api_toggle_invigilator_slot(req)
    assert resp.status_code in [400, 403], f"Expected 400 or 403 Forbidden, got {resp.status_code}"
    print(f"2. [PASS] Teacher registration strictly blocked (HTTP {resp.status_code}) while plan is inactive/draft.")

    # -------------------------------------------------------------------------
    # TEST 3: Admin Edits Plan Multiple Times in Draft Mode
    # -------------------------------------------------------------------------
    print("\n--- TEST 3: Admin Updates Plan Multiple Times in Draft Mode ---")
    
    # 3.1 First edit: update dates, rooms, and guidelines
    req1 = factory.post(f"/examinations/invigilator-plans/{plan.id}/edit/", {
        "form_action": "update_plan",
        "title": "គម្រោងវេនអនុរក្សប្រឡង (កែប្រែលើកទី ១)",
        "academic_year": ay.id,
        "start_date": "2026-09-12",
        "end_date": "2026-09-13",
        "rooms_count": "5",
        "invigilators_per_room": "2",
        "capacity_invigilator": "10",
        "sync_all_slots": "on",
        "description": "សេចក្តីណែនាំលើកទី ១: គោរពវិន័យឱ្យបានខ្ជាប់ខ្ជួន",
    })
    req1.user = admin_user
    setattr(req1, 'session', {})
    setattr(req1, '_messages', FallbackStorage(req1))

    exam_invigilator_plan_edit(req1, plan.id)
    plan.refresh_from_db()
    assert plan.rooms_count == 5
    assert plan.start_date == datetime.date(2026, 9, 12)
    assert plan.end_date == datetime.date(2026, 9, 13)
    assert plan.description == "សេចក្តីណែនាំលើកទី ១: គោរពវិន័យឱ្យបានខ្ជាប់ខ្ជួន"
    print("3.1 [PASS] First edit saved: start_date=Sep 12, end_date=Sep 13, rooms_count=5.")

    # 3.2 Second edit: change dates again and REGENERATE slots across new range
    req2 = factory.post(f"/examinations/invigilator-plans/{plan.id}/edit/", {
        "form_action": "update_plan",
        "title": "គម្រោងវេនអនុរក្សប្រឡង (កែប្រែលើកទី ២)",
        "academic_year": ay.id,
        "start_date": "2026-09-15",
        "end_date": "2026-09-16",
        "rooms_count": "6",
        "invigilators_per_room": "2",
        "capacity_invigilator": "12",
        "regenerate_slots": "on",
        "description": "សេចក្តីណែនាំលើកទី ២: កាលបរិច្ឆេទថ្មី និងវេនថ្មី",
    })
    req2.user = admin_user
    setattr(req2, 'session', {})
    setattr(req2, '_messages', FallbackStorage(req2))

    exam_invigilator_plan_edit(req2, plan.id)
    plan.refresh_from_db()
    assert plan.start_date == datetime.date(2026, 9, 15)
    assert plan.end_date == datetime.date(2026, 9, 16)
    assert plan.rooms_count == 6
    
    # Check regenerated slots: Sep 15 & 16 -> 2 days * 2 slots/day = 4 slots
    regenerated_slots = plan.shift_slots.all().order_by('date', 'session')
    assert regenerated_slots.count() == 4, f"Expected 4 slots, got {regenerated_slots.count()}"
    assert plan.duration_days == 2, f"Expected duration_days=2, got {plan.duration_days}"
    print(f"3.2 [PASS] Second edit with regenerate_slots: 4 new slots generated across Sep 15-16. duration_days={plan.duration_days}.")

    # 3.2.1 Verify GET rendering of edit page does NOT revert days to 4
    req_get = factory.get(f"/examinations/invigilator-plans/{plan.id}/edit/")
    req_get.user = admin_user
    setattr(req_get, 'session', {})
    setattr(req_get, '_messages', FallbackStorage(req_get))
    resp_get = exam_invigilator_plan_edit(req_get, plan.id)
    assert resp_get.status_code == 200
    html_content = resp_get.content.decode('utf-8')
    assert 'id="plan_days_count"' in html_content
    assert 'value="2"' in html_content, "Days count in HTML input MUST be 2 (duration_days of Sep 15 to Sep 16), not hardcoded 4!"
    print("3.2.1 [PASS] GET /edit/ renders days_count input with value='2' matching duration_days! No reverting to 4.")

    # 3.2.2 Third edit: Change days to 5 using days_count parameter
    req_days = factory.post(f"/examinations/invigilator-plans/{plan.id}/edit/", {
        "form_action": "update_plan",
        "title": "គម្រោងវេនអនុរក្សប្រឡង (៥ ថ្ងៃ)",
        "academic_year": ay.id,
        "start_date": "2026-09-15",
        "days_count": "5",
        "rooms_count": "6",
        "capacity_invigilator": "12",
        "regenerate_slots": "on",
    })
    req_days.user = admin_user
    setattr(req_days, 'session', {})
    setattr(req_days, '_messages', FallbackStorage(req_days))
    exam_invigilator_plan_edit(req_days, plan.id)
    plan.refresh_from_db()
    assert plan.duration_days == 5, f"Expected duration_days=5, got {plan.duration_days}"
    assert plan.end_date == datetime.date(2026, 9, 19), f"Expected end_date=2026-09-19, got {plan.end_date}"
    slots_5d = plan.shift_slots.all().order_by('date', 'session')
    assert slots_5d.count() == 10, f"Expected 10 slots for 5 days, got {slots_5d.count()}"
    print("3.2.2 [PASS] Updated to 5 days: end_date=2026-09-19, 10 shift slots generated. duration_days=5.")

    # Reset back to 2 days for remaining tests
    req_reset = factory.post(f"/examinations/invigilator-plans/{plan.id}/edit/", {
        "form_action": "update_plan",
        "title": "គម្រោងវេនអនុរក្សប្រឡង (២ ថ្ងៃ)",
        "academic_year": ay.id,
        "start_date": "2026-09-15",
        "end_date": "2026-09-16",
        "days_count": "2",
        "rooms_count": "6",
        "capacity_invigilator": "12",
        "regenerate_slots": "on",
    })
    req_reset.user = admin_user
    setattr(req_reset, 'session', {})
    setattr(req_reset, '_messages', FallbackStorage(req_reset))
    exam_invigilator_plan_edit(req_reset, plan.id)
    plan.refresh_from_db()

    # 3.3 Admin clicks 1-Click Publish to open for teachers
    req_pub = factory.post(f"/examinations/invigilator-plans/{plan.id}/toggle-active/")
    req_pub.user = admin_user
    setattr(req_pub, 'session', {})
    setattr(req_pub, '_messages', FallbackStorage(req_pub))

    exam_invigilator_plan_toggle_active(req_pub, plan.id)
    plan.refresh_from_db()
    assert plan.is_active is True
    assert plan.allow_teacher_registration is True
    print("3.3 [PASS] Admin published plan: is_active=True, allow_teacher_registration=True.")

    # 3.4 Admin clicks 1-Click Pause to make quick adjustment
    req_pause = factory.post(f"/examinations/invigilator-plans/{plan.id}/toggle-active/")
    req_pause.user = admin_user
    setattr(req_pause, 'session', {})
    setattr(req_pause, '_messages', FallbackStorage(req_pause))

    exam_invigilator_plan_toggle_active(req_pause, plan.id)
    plan.refresh_from_db()
    assert plan.is_active is False
    print("3.4 [PASS] Admin paused plan: is_active=False. Can edit repeatedly without disruption.")

    # Re-activate for testing room allocations
    plan.is_active = True
    plan.allow_teacher_registration = True
    plan.save()

    # -------------------------------------------------------------------------
    # TEST 4: Auto-Allocation and Admin Manual Room Override
    # -------------------------------------------------------------------------
    print("\n--- TEST 4: Auto-Allocation and Admin Manual Room Override ---")
    active_slot = regenerated_slots.first()

    # Create 5 teachers and register them in active_slot
    teachers = []
    regs = []
    for i in range(1, 6):
        u, _ = User.objects.get_or_create(username=f"t_override_user_{i}", defaults={"role": User.Role.TEACHER})
        t, _ = Teacher.objects.get_or_create(
            teacher_id=f"T_OVERRIDE_{i}",
            defaults={"khmer_name": f"គ្រូ តេស្ត {i:02d}", "user": u, "status": Teacher.Status.ACTIVE}
        )
        teachers.append(t)
        TeacherDutyQuota.objects.get_or_create(plan=plan, teacher=t, defaults={"custom_required_shifts": 4})
        reg, _ = TeacherShiftRegistration.objects.get_or_create(
            slot=active_slot,
            teacher=t,
            defaults={"role": ExamCommitteeRole.INVIGILATOR, "status": "CONFIRMED"}
        )
        regs.append(reg)

    # 4.1 Trigger Random Auto-Allocation for active_slot
    req_auto = factory.post(f"/examinations/invigilator-plans/{plan.id}/roster/", {
        "action": "auto_assign_rooms_slot",
        "slot_id": active_slot.id,
    })
    req_auto.user = admin_user
    setattr(req_auto, 'session', {})
    setattr(req_auto, '_messages', FallbackStorage(req_auto))

    exam_invigilator_roster_view(req_auto, plan.id)
    for r in regs:
        r.refresh_from_db()
        assert r.room_assignment != "", f"Registration for {r.teacher.khmer_name} should have room allocated"
    print(f"4.1 [PASS] Auto-allocation randomly assigned rooms to all {len(regs)} teachers:")
    for r in regs:
        print(f"    -> {r.teacher.khmer_name}: Room = '{r.room_assignment}', Role = '{r.role}'")

    # 4.2 Admin manually changes room for teacher 1 to a specific new room (e.g. 'បន្ទប់ 05 (អនុរក្ស ២)')
    target_reg = regs[0]
    original_room = target_reg.room_assignment
    new_room = "បន្ទប់ 05 (អនុរក្ស ២)"

    req_update = factory.post(f"/examinations/invigilator-plans/{plan.id}/roster/", {
        "action": "admin_update_registration",
        "registration_id": target_reg.id,
        "room_assignment": new_room,
        "role": ExamCommitteeRole.INVIGILATOR,
    })
    req_update.user = admin_user
    setattr(req_update, 'session', {})
    setattr(req_update, '_messages', FallbackStorage(req_update))

    exam_invigilator_roster_view(req_update, plan.id)
    target_reg.refresh_from_db()
    assert target_reg.room_assignment == new_room, f"Expected '{new_room}', got '{target_reg.room_assignment}'"
    assert target_reg.status == "ADMIN_ASSIGNED", f"Expected ADMIN_ASSIGNED, got '{target_reg.status}'"
    print(f"4.2 [PASS] Admin manually edited room from '{original_room}' to '{new_room}'.")
    print(f"    -> Status updated to '{target_reg.status}'.")

    # 4.3 Admin manually changes room via AJAX (JSON response)
    ajax_room = "បន្ទប់ពិសេស VIP 01"
    req_ajax = factory.post(
        f"/examinations/invigilator-plans/{plan.id}/roster/",
        {
            "action": "admin_update_registration",
            "registration_id": target_reg.id,
            "room_assignment": ajax_room,
            "role": ExamCommitteeRole.INVIGILATOR,
        },
        HTTP_X_REQUESTED_WITH='XMLHttpRequest'
    )
    req_ajax.user = admin_user
    setattr(req_ajax, 'session', {})
    setattr(req_ajax, '_messages', FallbackStorage(req_ajax))

    resp_ajax = exam_invigilator_roster_view(req_ajax, plan.id)
    assert resp_ajax.status_code == 200
    target_reg.refresh_from_db()
    assert target_reg.room_assignment == ajax_room
    print(f"4.3 [PASS] Admin AJAX room update to '{ajax_room}' returned 200 OK and saved successfully.")

    # -------------------------------------------------------------------------
    # TEST 5: Direct Room Assignment for Surplus Teachers
    # -------------------------------------------------------------------------
    print("\n--- TEST 5: Direct Room Assignment for Surplus Teachers ---")
    surplus_reg = regs[4]
    surplus_reg.room_assignment = ""  # No room (surplus)
    surplus_reg.save()

    req_surplus = factory.post(f"/examinations/invigilator-plans/{plan.id}/roster/", {
        "action": "reassign_surplus_teachers",
        "registration_id": surplus_reg.id,
        "target_room": "បន្ទប់ 03 (អនុរក្ស ១)",
    })
    req_surplus.user = admin_user
    setattr(req_surplus, 'session', {})
    setattr(req_surplus, '_messages', FallbackStorage(req_surplus))

    exam_invigilator_roster_view(req_surplus, plan.id)
    surplus_reg.refresh_from_db()
    assert surplus_reg.room_assignment == "បន្ទប់ 03 (អនុរក្ស ១)", f"Expected 'បន្ទប់ 03 (អនុរក្ស ១)', got '{surplus_reg.room_assignment}'"
    assert surplus_reg.role == ExamCommitteeRole.INVIGILATOR
    assert surplus_reg.status == "ADMIN_ASSIGNED"
    print(f"5. [PASS] Surplus teacher directly assigned to '{surplus_reg.room_assignment}' as '{surplus_reg.role}'.")

    print("\n" + "=" * 80)
    print("🎉 ALL TESTS PASSED (100%)! Admin manual room edits & draft plan editing fully verified.")
    print("=" * 80)


if __name__ == "__main__":
    run_tests()
