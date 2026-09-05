import os
import sys
import django
import datetime

sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import RequestFactory
from apps.accounts.models import User
from apps.academics.models import AcademicYear
from apps.teachers.models import Teacher
from apps.examinations.models import (
    StandardizedExam, ExamInvigilatorPlan, TeacherDutyGroup,
    TeacherDutyQuota, ExamShiftSlot, TeacherShiftRegistration, ExamCommitteeRole
)
from apps.examinations.views import (
    exam_invigilator_plan_create,
    exam_invigilator_quotas_manage,
    exam_invigilator_teacher_portal,
    api_toggle_invigilator_slot
)
import json

def run_tests():
    print("=== STARTING EXAM DAYS, SHIFTS & TEACHER GROUPS TEST SUITE ===")
    factory = RequestFactory()

    # 1. Setup Data
    admin_user, _ = User.objects.get_or_create(username='admin_test_user', defaults={'role': 'ADMIN', 'is_staff': True, 'is_superuser': True})
    ay, _ = AcademicYear.objects.get_or_create(name='2026-2027', defaults={'start_date': datetime.date(2026, 9, 1), 'end_date': datetime.date(2027, 7, 31), 'is_current': True})

    teacher_regular, _ = Teacher.objects.get_or_create(
        teacher_id='T_REG_001',
        defaults={'khmer_name': 'សុខ ចាន់ដារ៉ា', 'latin_name': 'Sok Chandara', 'gender': 'M', 'current_duty': 'គ្រូបង្រៀនគណិតវិទ្យា', 'status': Teacher.Status.ACTIVE}
    )
    teacher_office, _ = Teacher.objects.get_or_create(
        teacher_id='T_OFF_002',
        defaults={'khmer_name': 'គង់ សុភា', 'latin_name': 'Kong Sophea', 'gender': 'F', 'current_duty': 'បុគ្គលិករដ្ឋបាល និងបណ្ណារក្ស', 'status': Teacher.Status.ACTIVE}
    )

    # 2. Test Plan Creation with 4 days: 2026-09-07 (Mon) to 2026-09-10 (Thu)
    start_date = datetime.date(2026, 9, 7)
    end_date = datetime.date(2026, 9, 10)

    post_data = {
        'title': 'សម័យប្រឡងតេស្តស្តង់ដា ឆមាសទី១ ឆ្នាំ២០២៦',
        'academic_year': ay.id,
        'start_date': '2026-09-07',
        'end_date': '2026-09-10',
        'description': 'ការប្រឡង ៤ ថ្ងៃ ស្មើនឹង ៨ វេន',
        'is_active': 'on',
        'allow_teacher_registration': 'on',
        'default_regular_quota': '4',
        'default_office_quota': '5',
        'invigilators_per_room': '2',
        'capacity_invigilator': '20',
        'capacity_secretariat': '2',
        'capacity_building_inspector': '2',
        'auto_create_slots': 'on',
    }
    req = factory.post('/examinations/invigilator-plans/create/', post_data)
    req.user = admin_user
    # Attach session and messages
    from django.contrib.messages.storage.fallback import FallbackStorage
    from django.contrib.sessions.backends.db import SessionStore
    req.session = SessionStore()
    setattr(req, '_messages', FallbackStorage(req))

    resp = exam_invigilator_plan_create(req)
    assert resp.status_code == 302, f"Expected redirect, got {resp.status_code}"

    plan = ExamInvigilatorPlan.objects.filter(title='សម័យប្រឡងតេស្តស្តង់ដា ឆមាសទី១ ឆ្នាំ២០២៦').first()
    assert plan is not None, "Plan was not created!"
    print(f"1. [PASS] Plan created: {plan.title} (From {plan.start_date} to {plan.end_date})")

    # 3. Verify Shift Slots: Exactly 8 shifts (4 Morning + 4 Afternoon) with Khmer Weekday names
    slots = list(plan.shift_slots.order_by('order'))
    assert len(slots) == 8, f"Expected 8 shift slots, got {len(slots)}"

    expected_labels = [
        ("2026-09-07", "MORNING", "ចន្ទ", "07/09", "ព្រឹក"),
        ("2026-09-07", "AFTERNOON", "ចន្ទ", "07/09", "រសៀល"),
        ("2026-09-08", "MORNING", "អង្គារ", "08/09", "ព្រឹក"),
        ("2026-09-08", "AFTERNOON", "អង្គារ", "08/09", "រសៀល"),
        ("2026-09-09", "MORNING", "ពុធ", "09/09", "ព្រឹក"),
        ("2026-09-09", "AFTERNOON", "ពុធ", "09/09", "រសៀល"),
        ("2026-09-10", "MORNING", "ព្រហស្បតិ៍", "10/09", "ព្រឹក"),
        ("2026-09-10", "AFTERNOON", "ព្រហស្បតិ៍", "10/09", "រសៀល"),
    ]

    for idx, (exp_date, exp_sess, exp_day_kh, exp_d_m, exp_time_kh) in enumerate(expected_labels):
        slot = slots[idx]
        assert slot.date.strftime('%Y-%m-%d') == exp_date, f"Slot {idx+1} date mismatch: {slot.date}"
        assert slot.session == exp_sess, f"Slot {idx+1} session mismatch: {slot.session}"
        assert exp_day_kh in slot.session_name, f"Expected {exp_day_kh} in slot name: {slot.session_name}"
        assert exp_d_m in slot.session_name, f"Expected {exp_d_m} in slot name: {slot.session_name}"
        assert exp_time_kh in slot.session_name, f"Expected {exp_time_kh} in slot name: {slot.session_name}"
        print(f"   - Slot {idx+1}: {slot.session_name}")

    print("2. [PASS] Verified 4 days = 8 shifts with Khmer day labels (ចន្ទ ទី ៧ ដល់ ព្រហស្បតិ៍ ទី ១០)")

    # 4. Verify Duty Groups: Group 1 (4 shifts) and Group 2 (5 shifts)
    group1 = plan.duty_groups.filter(name__icontains='ប្រភេទទី១').first()
    group2 = plan.duty_groups.filter(name__icontains='ប្រភេទទី២').first()

    assert group1 is not None, "Duty Group 1 (ប្រភេទទី១) not found!"
    assert group2 is not None, "Duty Group 2 (ប្រភេទទី២) not found!"
    assert group1.required_shifts == 4, f"Expected Group 1 required_shifts=4, got {group1.required_shifts}"
    assert group2.required_shifts == 5, f"Expected Group 2 required_shifts=5, got {group2.required_shifts}"
    print(f"3. [PASS] Duty Groups verified: {group1.name} = {group1.required_shifts} វេន, {group2.name} = {group2.required_shifts} វេន")

    # 5. Verify Auto-Classify and Quotas
    quota_reg = TeacherDutyQuota.objects.filter(plan=plan, teacher=teacher_regular).first()
    quota_off = TeacherDutyQuota.objects.filter(plan=plan, teacher=teacher_office).first()

    assert quota_reg is not None and quota_reg.duty_group == group1, f"Regular teacher should be in Group 1, got {quota_reg.duty_group if quota_reg else None}"
    assert quota_off is not None and quota_off.duty_group == group2, f"Office teacher should be in Group 2, got {quota_off.duty_group if quota_off else None}"
    assert quota_reg.effective_required_shifts == 4, f"Regular teacher quota should be 4, got {quota_reg.effective_required_shifts}"
    assert quota_off.effective_required_shifts == 5, f"Office teacher quota should be 5, got {quota_off.effective_required_shifts}"
    print("4. [PASS] Teachers automatically classified into Group 1 (4 shifts) & Group 2 (5 shifts)")

    # 6. Test Admin Batch Assigning Teachers to Group 2
    req_batch = factory.post(f'/examinations/invigilator-plans/{plan.id}/quotas/', {
        'action': 'batch_assign_group',
        'target_group_id': str(group2.id),
        'selected_quota_ids': [str(quota_reg.id)]
    })
    req_batch.user = admin_user
    req_batch.session = SessionStore()
    setattr(req_batch, '_messages', FallbackStorage(req_batch))

    resp_batch = exam_invigilator_quotas_manage(req_batch, plan.id)
    assert resp_batch.status_code == 302
    quota_reg.refresh_from_db()
    assert quota_reg.duty_group == group2, f"Batch assign failed, expected Group 2, got {quota_reg.duty_group}"
    assert quota_reg.effective_required_shifts == 5, f"Expected effective shifts=5 after moving to Group 2, got {quota_reg.effective_required_shifts}"
    print("5. [PASS] Batch assign successfully updated teacher from Group 1 to Group 2 (Quota now 5 shifts)")

    # 7. Test Batch Re-assign back to Group 1
    req_batch2 = factory.post(f'/examinations/invigilator-plans/{plan.id}/quotas/', {
        'action': 'batch_assign_group',
        'target_group_id': str(group1.id),
        'selected_quota_ids': [str(quota_reg.id)]
    })
    req_batch2.user = admin_user
    req_batch2.session = SessionStore()
    setattr(req_batch2, '_messages', FallbackStorage(req_batch2))
    resp_batch2 = exam_invigilator_quotas_manage(req_batch2, plan.id)
    quota_reg.refresh_from_db()
    assert quota_reg.duty_group == group1
    assert quota_reg.effective_required_shifts == 4
    print("6. [PASS] Batch assign moved teacher back to Group 1 (Quota restored to 4 shifts)")

    # 8. Test Teacher Portal Registration honors assigned group quota
    # Create user for regular teacher
    reg_user, _ = User.objects.get_or_create(username='teacher_reg_test', defaults={'role': 'TEACHER'})
    teacher_regular.user = reg_user
    teacher_regular.save()

    # Teacher portal view
    req_portal = factory.get(f'/examinations/invigilator-plans/portal/?plan_id={plan.id}')
    req_portal.user = reg_user
    req_portal.session = SessionStore()
    setattr(req_portal, '_messages', FallbackStorage(req_portal))
    resp_portal = exam_invigilator_teacher_portal(req_portal)
    assert "4" in resp_portal.content.decode('utf-8'), "Expected 4 shifts in portal HTML"
    print(f"7. [PASS] Teacher portal reflects Group 1 quota of 4 shifts for {teacher_regular.khmer_name}")

    # Teacher registers for slot 1
    slot1 = slots[0]
    req_toggle = factory.post('/examinations/invigilator-plans/api/toggle-slot/', {'slot_id': str(slot1.id)})
    req_toggle.user = reg_user
    resp_toggle = api_toggle_invigilator_slot(req_toggle)
    data = json.loads(resp_toggle.content)
    assert data['success'] is True
    assert data['is_registered'] is True
    assert data['current_count'] == 1
    assert data['required_shifts'] == 4
    assert data['remaining_to_choose'] == 3
    print("8. [PASS] Teacher registered for slot 1: 1/4 completed, 3 remaining")

    print("\n=== ALL EXAM DAYS, SHIFTS & TEACHER GROUPS TESTS PASSED 100%! ===")

if __name__ == '__main__':
    run_tests()
