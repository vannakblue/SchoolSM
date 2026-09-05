import os
import sys
import django
import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from apps.academics.models import AcademicYear
from apps.examinations.models import (
    StandardizedExam, ExamRoom, ExamInvigilatorPlan, ExamShiftSlot,
    ExamPlanRoleSetting, ExamCommitteeRole
)

User = get_user_model()

def test_invigilator_shift_allocation():
    print("=== STARTING INVIGILATOR SHIFT ALLOCATION TEST SUITE ===")

    admin_user, _ = User.objects.get_or_create(
        username='admin_shift_test',
        defaults={'role': 'ADMIN', 'is_staff': True, 'is_superuser': True}
    )
    admin_user.role = 'ADMIN'
    admin_user.is_staff = True
    admin_user.is_superuser = True
    admin_user.save()

    client = Client()
    client.force_login(admin_user)

    ay, _ = AcademicYear.objects.get_or_create(name='2026-2027', defaults={'is_active': True})

    # Clean up previous test instances
    ExamInvigilatorPlan.objects.filter(title__icontains='តេស្តបែងចែកវេន').delete()
    StandardizedExam.objects.filter(name__icontains='តេស្តបែងចែកវេន').delete()

    # Create test exam with 83 rooms (like user's screenshot)
    exam = StandardizedExam.objects.create(
        name='ការប្រឡងតេស្តដើមឆ្នាំ តេស្តបែងចែកវេន',
        academic_year=ay,
        grade_level=12,
        exam_date=datetime.date(2026, 10, 6),
        is_published=True
    )
    for r_num in range(1, 84):
        ExamRoom.objects.create(exam=exam, room_number=r_num, room_name=f"បន្ទប់ {r_num:02d}")
    
    assert exam.rooms.count() == 83
    print(f"1. [PASS] Created StandardizedExam with {exam.rooms.count()} rooms.")

    # 1. Test GET plan_create with invigilators_per_room=1
    res_get_1 = client.get(f'/examinations/invigilator-plans/create/?exam_id={exam.id}&rooms=83&invigilators_per_room=1')
    assert res_get_1.status_code == 200
    content_get_1 = res_get_1.content.decode('utf-8')
    assert '83 បន្ទប់ប្រឡង' in content_get_1
    assert '១ នាក់ / បន្ទប់' in content_get_1
    print("2. [PASS] GET plan_create correctly handles 83 rooms with 1 invigilator per room.")

    # 2. Test POST plan_create with 2 invigilators per room (83 * 2 = 166 per shift)
    # AND manual allocation: invigilator=166, secretariat=4, inspector=6
    post_data = {
        'title': 'វេនអនុរក្ស៖ ការប្រឡងតេស្តដើមឆ្នាំ តេស្តបែងចែកវេន',
        'academic_year': ay.id,
        'standardized_exam': exam.id,
        'start_date': '2026-10-06',
        'end_date': '2026-10-06',
        'is_active': 'on',
        'allow_teacher_registration': 'on',
        'default_regular_quota': 4,
        'default_office_quota': 5,
        'invigilators_per_room': 2,
        'rooms_count': 83,
        'capacity_invigilator': 166,
        'capacity_secretariat': 4,
        'capacity_building_inspector': 6,
        'auto_create_slots': 'on',
    }
    res_create = client.post('/examinations/invigilator-plans/create/', data=post_data, follow=True)
    assert res_create.status_code == 200

    plan = ExamInvigilatorPlan.objects.filter(title__icontains='តេស្តបែងចែកវេន').first()
    assert plan is not None, "❌ Plan should be created in DB"
    assert plan.invigilators_per_room == 2
    assert plan.rooms_count == 83
    print("3. [PASS] Created plan with invigilators_per_room=2 and rooms_count=83.")

    # Check shift slots (Morning & Afternoon)
    slots = list(plan.shift_slots.all().order_by('order'))
    assert len(slots) == 2, f"❌ Expected 2 slots (morning & afternoon), got {len(slots)}"
    m_slot, a_slot = slots[0], slots[1]
    assert m_slot.session == 'MORNING'
    assert m_slot.max_invigilators == 166
    assert a_slot.session == 'AFTERNOON'
    assert a_slot.max_invigilators == 166
    print(f"4. [PASS] Morning & Afternoon slots auto-created with 166 invigilators each (83 rooms * 2).")

    # Check role capacities in slots
    assert m_slot.get_role_capacity(ExamCommitteeRole.INVIGILATOR) == 166
    assert m_slot.get_role_capacity(ExamCommitteeRole.SECRETARIAT) == 4
    assert m_slot.get_role_capacity(ExamCommitteeRole.BUILDING_INSPECTOR) == 6
    print(f"5. [PASS] Manual role allocations verified: Invigilator=166, Secretariat=4, Inspector=6 per shift.")

    # 3. Test Editing Plan (Change to 1 per room = 83 invigilators, secretariat=3, inspector=4, with sync_all_slots)
    edit_data = {
        'form_action': 'update_plan',
        'title': plan.title,
        'academic_year': ay.id,
        'invigilators_per_room': 1,
        'rooms_count': 83,
        'capacity_invigilator': 83,
        'capacity_secretariat': 3,
        'capacity_building_inspector': 4,
        'sync_all_slots': 'on',
        'is_active': 'on',
        'allow_teacher_registration': 'on',
        'default_regular_quota': 4,
        'default_office_quota': 5,
    }
    res_edit = client.post(f'/examinations/invigilator-plans/{plan.id}/edit/', data=edit_data, follow=True)
    assert res_edit.status_code == 200

    plan.refresh_from_db()
    assert plan.invigilators_per_room == 1
    m_slot.refresh_from_db()
    a_slot.refresh_from_db()
    assert m_slot.max_invigilators == 83
    assert a_slot.max_invigilators == 83
    assert m_slot.get_role_capacity(ExamCommitteeRole.SECRETARIAT) == 3
    assert m_slot.get_role_capacity(ExamCommitteeRole.BUILDING_INSPECTOR) == 4
    print("6. [PASS] Plan edited: invigilators synced to 83, Secretariat to 3, Inspector to 4.")

    # 4. Test individual slot edit
    edit_slot_data = {
        'form_action': 'edit_slot',
        'slot_id': m_slot.id,
        'slot_date': '2026-10-06',
        'slot_session': 'MORNING',
        'slot_name': 'ថ្ងៃទី១ - 🌅 ពេលព្រឹក (Custom)',
        'slot_start': '07:30',
        'slot_end': '11:30',
        'slot_capacity': 90
    }
    res_slot_edit = client.post(f'/examinations/invigilator-plans/{plan.id}/edit/', data=edit_slot_data, follow=True)
    assert res_slot_edit.status_code == 200
    m_slot.refresh_from_db()
    assert m_slot.max_invigilators == 90
    assert m_slot.session_name == 'ថ្ងៃទី១ - 🌅 ពេលព្រឹក (Custom)'
    print("7. [PASS] Individual slot successfully modified to capacity=90.")

    # 5. Test standardized_exam_list modal rendering (for session without a plan yet)
    plan.delete()
    res_list = client.get(f'/examinations/standardized/?year={ay.id}')
    assert res_list.status_code == 200
    html_list = res_list.content.decode('utf-8')
    assert 'selectInvigPerRoom' in html_list
    assert '១ នាក់ / បន្ទប់' in html_list
    assert '២ នាក់ / បន្ទប់' in html_list
    print("8. [PASS] Exam list displays interactive 1 vs 2 invigilators/room choices and JS calculation.")

    print("\n=== ALL INVIGILATOR SHIFT ALLOCATION TESTS PASSED 100%! ===")

if __name__ == '__main__':
    test_invigilator_shift_allocation()
