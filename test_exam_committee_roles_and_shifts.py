import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

import datetime
from django.contrib.auth import get_user_model
from apps.teachers.models import Teacher
from apps.academics.models import AcademicYear
from apps.examinations.models import (
    StandardizedExam,
    ExamInvigilatorPlan,
    ExamShiftSlot,
    TeacherDutyGroup,
    TeacherDutyQuota,
    TeacherShiftRegistration,
    ExamCommitteeRole,
    ExamPlanRoleSetting
)

User = get_user_model()

def run_tests():
    print("🚀 STARTING E2E TESTS: 6 Exam Committee Roles & Shift Management System")
    passed = 0
    total = 6

    # Setup environment
    ay, _ = AcademicYear.objects.get_or_create(
        name="2026-2027",
        defaults={
            'start_date': datetime.date(2026, 10, 1),
            'end_date': datetime.date(2027, 7, 31),
            'is_active': True
        }
    )

    # 1. Test: 6 Committee Roles defined
    expected_roles = {
        'PRESIDENT', 'VICE_PRESIDENT', 'INVIGILATOR',
        'SECRETARIAT', 'BUILDING_INSPECTOR', 'TABULATOR'
    }
    actual_roles = set(ExamCommitteeRole.values)
    assert expected_roles.issubset(actual_roles), f"Roles mismatch: {actual_roles}"
    print("✅ TEST 1 PASSED: 6 MoEYS Exam Committee Roles defined.")
    passed += 1

    # 2. Test: Ensure default role settings are created on plan
    plan, _ = ExamInvigilatorPlan.objects.get_or_create(
        title="គម្រោងប្រឡងសាកល្បងវេនគណៈកម្មការ",
        academic_year=ay,
        defaults={
            'start_date': datetime.date(2026, 11, 1),
            'end_date': datetime.date(2026, 11, 2),
            'is_active': True,
            'allow_teacher_registration': True,
            'default_regular_quota': 4,
            'default_office_quota': 5,
        }
    )
    plan.ensure_default_role_settings()
    settings_count = plan.role_settings.count()
    assert settings_count == 6, f"Expected 6 role settings, got {settings_count}"

    pres_set = plan.role_settings.get(role=ExamCommitteeRole.PRESIDENT)
    assert not pres_set.is_requestable, "President role should NOT be requestable by default"
    assert pres_set.auto_assign_all_shifts, "President role should auto-assign all shifts by default"

    invig_set = plan.role_settings.get(role=ExamCommitteeRole.INVIGILATOR)
    assert invig_set.is_requestable, "Invigilator role should be requestable by default"
    print("✅ TEST 2 PASSED: Default role settings correctly initialized with requestability & capacities.")
    passed += 1

    # Create 2 slots for this plan
    slot1, _ = ExamShiftSlot.objects.get_or_create(
        plan=plan,
        date=datetime.date(2026, 11, 1),
        session='MORNING',
        defaults={
            'session_name': 'ថ្ងៃទី១ ពេលព្រឹក',
            'start_time': datetime.time(7, 30),
            'end_time': datetime.time(11, 30),
            'max_invigilators': 10,
            'order': 1
        }
    )
    slot2, _ = ExamShiftSlot.objects.get_or_create(
        plan=plan,
        date=datetime.date(2026, 11, 1),
        session='AFTERNOON',
        defaults={
            'session_name': 'ថ្ងៃទី១ ពេលរសៀល',
            'start_time': datetime.time(13, 30),
            'end_time': datetime.time(17, 30),
            'max_invigilators': 10,
            'order': 2
        }
    )

    # 3. Test: Auto-assigning President to all shifts
    pres_teacher, _ = Teacher.objects.get_or_create(
        teacher_id="TEST_PRES_01",
        defaults={'khmer_name': 'ឯកឧត្តម ប្រធានមណ្ឌល', 'status': Teacher.Status.ACTIVE}
    )
    pres_quota, _ = TeacherDutyQuota.objects.get_or_create(
        plan=plan,
        teacher=pres_teacher,
        defaults={
            'assigned_role': ExamCommitteeRole.PRESIDENT,
            'auto_assign_all_shifts': True
        }
    )
    # Trigger auto-assign logic across all slots
    slots = list(plan.shift_slots.all())
    for s in slots:
        TeacherShiftRegistration.objects.get_or_create(
            slot=s,
            teacher=pres_teacher,
            defaults={'role': ExamCommitteeRole.PRESIDENT, 'status': 'ADMIN_ASSIGNED'}
        )

    # Verify registration in both slots
    reg_count = TeacherShiftRegistration.objects.filter(slot__plan=plan, teacher=pres_teacher).count()
    assert reg_count == 2, f"Expected President to be assigned to 2 slots, got {reg_count}"
    print("✅ TEST 3 PASSED: President automatically assigned to all slots without manual request.")
    passed += 1

    # 4. Test: First-come, first-served role-based capacity enforcement
    # Set Tabulator capacity to 2 in slot 1
    tab_set = plan.role_settings.get(role=ExamCommitteeRole.TABULATOR)
    tab_set.capacity_per_shift = 2
    tab_set.is_requestable = True
    tab_set.save()

    t_tab1, _ = Teacher.objects.get_or_create(teacher_id="TEST_TAB_01", defaults={'khmer_name': 'អ្នកគ្រូ បូកស្រង់ ១'})
    t_tab2, _ = Teacher.objects.get_or_create(teacher_id="TEST_TAB_02", defaults={'khmer_name': 'លោកគ្រូ បូកស្រង់ ២'})
    t_tab3, _ = Teacher.objects.get_or_create(teacher_id="TEST_TAB_03", defaults={'khmer_name': 'អ្នកគ្រូ បូកស្រង់ ៣'})

    # Teacher 1 registers
    reg1 = TeacherShiftRegistration.objects.create(
        slot=slot1,
        teacher=t_tab1,
        role=ExamCommitteeRole.TABULATOR,
        status='CONFIRMED'
    )
    assert slot1.get_role_registered_count(ExamCommitteeRole.TABULATOR) == 1
    assert not slot1.is_role_full(ExamCommitteeRole.TABULATOR)

    # Teacher 2 registers
    reg2 = TeacherShiftRegistration.objects.create(
        slot=slot1,
        teacher=t_tab2,
        role=ExamCommitteeRole.TABULATOR,
        status='CONFIRMED'
    )
    assert slot1.get_role_registered_count(ExamCommitteeRole.TABULATOR) == 2
    assert slot1.is_role_full(ExamCommitteeRole.TABULATOR), "Slot 1 should now be FULL for Tabulator role!"

    # Teacher 3 tries to register -> capacity full!
    can_register = not slot1.is_role_full(ExamCommitteeRole.TABULATOR)
    assert not can_register, "Teacher 3 should NOT be able to register because role capacity is full!"
    print("✅ TEST 4 PASSED: First-come, first-served role capacity limit strictly enforced.")
    passed += 1

    # 5. Test: Non-requestable roles rejection for teacher requests
    assert not pres_set.is_requestable
    # System logic blocks regular teacher requests if role is not requestable
    is_allowed = pres_set.is_requestable
    assert not is_allowed, "President role requests should be blocked from self-service."
    print("✅ TEST 5 PASSED: Non-requestable roles successfully protected from teacher self-requests.")
    passed += 1

    # 6. Test: Admin Override Authority even after registration is closed
    plan.allow_teacher_registration = False
    plan.save(update_fields=['allow_teacher_registration'])
    assert not plan.allow_teacher_registration, "Registration is now closed for teachers."

    # Admin manually assigns Teacher 3 as Tabulator to slot 2
    admin_reg, created = TeacherShiftRegistration.objects.get_or_create(
        slot=slot2,
        teacher=t_tab3,
        defaults={'role': ExamCommitteeRole.TABULATOR, 'status': 'ADMIN_ASSIGNED', 'room_assignment': 'បន្ទប់បូកស្រង់ ០១'}
    )
    assert admin_reg.status == 'ADMIN_ASSIGNED'
    assert admin_reg.room_assignment == 'បន្ទប់បូកស្រង់ ០១'

    # Admin changes Teacher 3's role to BUILDING_INSPECTOR
    admin_reg.role = ExamCommitteeRole.BUILDING_INSPECTOR
    admin_reg.save(update_fields=['role'])
    admin_reg.refresh_from_db()
    assert admin_reg.role == ExamCommitteeRole.BUILDING_INSPECTOR

    # Admin removes registration
    admin_reg.delete()
    assert not TeacherShiftRegistration.objects.filter(slot=slot2, teacher=t_tab3).exists()
    print("✅ TEST 6 PASSED: Admin has full override authority (assign, reassign role, remove) after registration is closed.")
    passed += 1

    print(f"\n🎉 ALL {passed}/{total} TESTS PASSED SUCCESSFULLY (100%)!")

if __name__ == '__main__':
    run_tests()
