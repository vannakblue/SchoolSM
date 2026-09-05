import os
import sys
import django
import datetime
from decimal import Decimal

sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.messages.storage.fallback import FallbackStorage
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import User
from apps.academics.models import AcademicYear, Classroom, Subject
from apps.students.models import Student
from apps.teachers.models import Teacher
from apps.examinations.models import (
    StandardizedExam, ExamSubject, ExamRoom, ExamCandidate,
    ExamInvigilatorPlan, TeacherDutyGroup
)
from apps.examinations.views import (
    exam_invigilator_plan_create,
    exam_invigilator_plan_edit,
    student_exam_admission_slip,
    partition_exam_rooms
)
from apps.dashboard.views import student_dashboard
from apps.mobile_api.views import (
    MobileDashboardSummaryView,
    MobileStudentExamSeatingAPIView,
    UserProfileView
)

def run_tests():
    print("================================================================================")
    print("RUNNING TESTS: TEACHER QUOTA GROUPS (ADD/EDIT/DELETE) & AUTO EXAM SEATING")
    print("================================================================================")
    factory = RequestFactory()
    api_factory = APIRequestFactory()

    # -------------------------------------------------------------------------
    # PART 1: TEST TEACHER QUOTA GROUPS (ADD, EDIT, DELETE)
    # -------------------------------------------------------------------------
    print("\n--- PART 1: TESTING TEACHER QUOTA GROUPS (ADD, EDIT, DELETE) ---")
    admin_user, _ = User.objects.get_or_create(
        username='admin_quota_test',
        defaults={'role': User.Role.ADMIN, 'is_staff': True, 'is_superuser': True}
    )
    ay, _ = AcademicYear.objects.get_or_create(
        name='2026-2027-QUOTA',
        defaults={'start_date': datetime.date(2026, 9, 1), 'end_date': datetime.date(2027, 7, 31), 'is_current': True}
    )

    # 1.1 Create plan with 3 custom groups
    post_create_data = {
        'title': 'គម្រោងវេនអនុរក្ស សម័យប្រឡងសាកល្បង',
        'academic_year': ay.id,
        'start_date': '2026-10-01',
        'end_date': '2026-10-04',
        'description': 'សាកល្បងបង្កើតប្រភេទក្រុមគ្រូ ៣ ផ្សេងគ្នា',
        'is_active': 'on',
        'allow_teacher_registration': 'on',
        'invigilators_per_room': '2',
        'capacity_invigilator': '20',
        'capacity_secretariat': '2',
        'capacity_building_inspector': '2',
        # Dynamic Quota Groups
        'quota_group_name[]': [
            'ក្រុមគ្រូប្រភេទទី១ (គ្រូបង្រៀនទូទៅ)',
            'ក្រុមគ្រូប្រភេទទី២ (គ្រូការិយាល័យ និងរដ្ឋបាល)',
            'ក្រុមគ្រូប្រភេទទី៣ (គ្រូបច្ចេកវិទ្យា និងពិសោធន៍)'
        ],
        'quota_group_shifts[]': ['4', '5', '3'],
        'quota_group_description[]': [
            'កូតា ៤ វេន សម្រាប់គ្រូបង្រៀន',
            'កូតា ៥ វេន សម្រាប់រដ្ឋបាល',
            'កូតា ៣ វេន សម្រាប់គ្រូបច្ចេកវិទ្យា'
        ]
    }

    req_create = factory.post('/examinations/invigilator-plans/create/', post_create_data)
    req_create.user = admin_user
    req_create.session = SessionStore()
    setattr(req_create, '_messages', FallbackStorage(req_create))

    resp_create = exam_invigilator_plan_create(req_create)
    assert resp_create.status_code == 302, f"Expected 302 redirect, got {resp_create.status_code}"

    plan = ExamInvigilatorPlan.objects.filter(title='គម្រោងវេនអនុរក្ស សម័យប្រឡងសាកល្បង').first()
    assert plan is not None, "Plan was not created!"
    groups = list(plan.duty_groups.order_by('order', 'id'))
    assert len(groups) == 3, f"Expected 3 duty groups, found {len(groups)}"
    assert groups[0].name == 'ក្រុមគ្រូប្រភេទទី១ (គ្រូបង្រៀនទូទៅ)' and groups[0].required_shifts == 4
    assert groups[1].name == 'ក្រុមគ្រូប្រភេទទី២ (គ្រូការិយាល័យ និងរដ្ឋបាល)' and groups[1].required_shifts == 5
    assert groups[2].name == 'ក្រុមគ្រូប្រភេទទី៣ (គ្រូបច្ចេកវិទ្យា និងពិសោធន៍)' and groups[2].required_shifts == 3
    print(f"1.1 [PASS] Created plan with 3 custom groups: {[g.name for g in groups]}")

    # 1.2 Edit plan: Update group 1, delete group 3, add new group 4
    g1_id = groups[0].id
    g2_id = groups[1].id
    # g3 is omitted from the submission to test deletion!

    post_edit_data = {
        'form_action': 'update_plan',
        'title': 'គម្រោងវេនអនុរក្ស សម័យប្រឡងសាកល្បង (កែសម្រួល)',
        'academic_year': ay.id,
        'start_date': '2026-10-01',
        'end_date': '2026-10-04',
        'description': 'បានកែប្រែកូតាក្រុមទី១ លុបក្រុមទី៣ និងបន្ថែមក្រុមទី៤',
        'is_active': 'on',
        'allow_teacher_registration': 'on',
        'invigilators_per_room': '2',
        'capacity_invigilator': '20',
        'capacity_secretariat': '2',
        'capacity_building_inspector': '2',
        # Submitting updated group 1, unchanged group 2, and new group 4
        'quota_group_id[]': [str(g1_id), str(g2_id), ''],
        'quota_group_name[]': [
            'ក្រុមគ្រូប្រភេទទី១ (គ្រូបង្រៀនទូទៅ - បង្កើនកូតា)',
            'ក្រុមគ្រូប្រភេទទី២ (គ្រូការិយាល័យ និងរដ្ឋបាល)',
            'ក្រុមគ្រូប្រភេទទី៤ (គ្រូបម្រើការងារបណ្ណាល័យ)'
        ],
        'quota_group_shifts[]': ['6', '5', '2'],
        'quota_group_description[]': [
            'កែប្រែកូតាឡើងដល់ ៦ វេន',
            'កូតា ៥ វេន ដដែល',
            'ក្រុមថ្មីទើបបង្កើត កូតា ២ វេន'
        ]
    }

    req_edit = factory.post(f'/examinations/invigilator-plans/{plan.id}/edit/', post_edit_data)
    req_edit.user = admin_user
    req_edit.session = SessionStore()
    setattr(req_edit, '_messages', FallbackStorage(req_edit))

    resp_edit = exam_invigilator_plan_edit(req_edit, plan_id=plan.id)
    assert resp_edit.status_code == 302, f"Expected 302 redirect, got {resp_edit.status_code}"

    plan.refresh_from_db()
    updated_groups = list(plan.duty_groups.order_by('order', 'id'))
    assert len(updated_groups) == 3, f"Expected 3 duty groups after edit, found {len(updated_groups)}"

    # Verify group 1 updated
    assert updated_groups[0].id == g1_id
    assert 'បង្កើនកូតា' in updated_groups[0].name
    assert updated_groups[0].required_shifts == 6

    # Verify group 3 was deleted
    assert not plan.duty_groups.filter(name__icontains='ពិសោធន៍').exists(), "Group 3 should have been deleted!"

    # Verify new group 4 was added
    assert plan.duty_groups.filter(name__icontains='បណ្ណាល័យ').exists(), "Group 4 was not created!"
    g4 = plan.duty_groups.filter(name__icontains='បណ្ណាល័យ').first()
    assert g4.required_shifts == 2
    print(f"1.2 [PASS] Successfully Edited G1 (quota=6), Deleted G3, and Added G4 (quota=2): {[g.name for g in updated_groups]}")

    # -------------------------------------------------------------------------
    # PART 2: TEST AUTO STUDENT & PARENT EXAM SEATING ON WEB & MOBILE API
    # -------------------------------------------------------------------------
    print("\n--- PART 2: TESTING AUTO STUDENT & PARENT EXAM SEATING ---")

    # 2.1 Setup Classroom, Student, and Parents
    classroom, _ = Classroom.objects.get_or_create(
        name='12A-AutoTest',
        academic_year=ay,
        defaults={'grade_level': 12, 'track': 'SCIENCE'}
    )

    parent_phone = '012888777'
    student_phone = '012333444'

    # Student 1: Sok Visal
    student_visal, _ = Student.objects.get_or_create(
        student_id='STU-AUTO-01',
        defaults={
            'khmer_name': 'សុខ វិសាល',
            'latin_name': 'SOK VISAL',
            'gender': Student.Gender.MALE,
            'date_of_birth': datetime.date(2008, 5, 15),
            'classroom': classroom,
            'academic_year': ay,
            'phone': student_phone,
            'father_name': 'សុខ វិបុល',
            'father_phone': parent_phone,
            'status': Student.Status.ACTIVE
        }
    )

    # Student 2: Sok Sreypov (same father phone to test multi-child parent!)
    student_sreypov, _ = Student.objects.get_or_create(
        student_id='STU-AUTO-02',
        defaults={
            'khmer_name': 'សុខ ស្រីពៅ',
            'latin_name': 'SOK SREYPOV',
            'gender': Student.Gender.FEMALE,
            'date_of_birth': datetime.date(2010, 8, 20),
            'classroom': classroom,
            'academic_year': ay,
            'phone': '012999000',
            'father_name': 'សុខ វិបុល',
            'father_phone': parent_phone,
            'status': Student.Status.ACTIVE
        }
    )

    # Create Users
    # Student User
    user_student, _ = User.objects.get_or_create(
        username='stu_visal',
        defaults={'role': User.Role.STUDENT, 'phone': student_phone, 'khmer_name': 'សុខ វិសាល'}
    )
    student_visal.user = user_student
    student_visal.save(update_fields=['user'])

    # Parent User (uses father phone as username or phone)
    user_parent, _ = User.objects.get_or_create(
        username='parent_vibol',
        defaults={'role': User.Role.STUDENT, 'phone': parent_phone, 'khmer_name': 'សុខ វិបុល'}
    )

    # 2.2 Create Standardized Exam for Grade 12
    std_exam, _ = StandardizedExam.objects.get_or_create(
        name='សម័យប្រឡងឆមាសទី១ ថ្នាក់ទី១២ (Auto Seating Test)',
        academic_year=ay,
        defaults={
            'grade_level': 12,
            'session': StandardizedExam.Session.MORNING,
            'track': StandardizedExam.Track.ALL,
            'exam_date': datetime.date(2026, 11, 20),
            'candidates_per_room': 25,
            'is_published': True
        }
    )

    # Add Exam Subject
    math_subj = Subject.objects.filter(name_kh='គណិតវិទ្យា').first() or Subject.objects.first()
    ExamSubject.objects.get_or_create(
        exam=std_exam,
        subject=math_subj,
        defaults={'max_score': Decimal('100.00'), 'order': 1}
    )

    # Clean up any leftover candidates/rooms from prior test runs to ensure idempotency
    ExamCandidate.objects.filter(exam=std_exam).delete()
    ExamRoom.objects.filter(exam=std_exam).delete()

    # 2.3 TEST BEFORE ROOM PARTITION
    # Student Web Dashboard before room partition
    req_stu_before = factory.get('/dashboard/student/')
    req_stu_before.user = user_student
    req_stu_before.session = SessionStore()
    setattr(req_stu_before, '_messages', FallbackStorage(req_stu_before))
    resp_stu_before = student_dashboard(req_stu_before)
    assert resp_stu_before.status_code == 200
    html_before = resp_stu_before.content.decode('utf-8')
    assert "រង់ចាំចែកបន្ទប់" in html_before, "Before partition, HTML should display waiting badge"
    
    from apps.examinations.services import resolve_student_and_children_for_user, get_student_exam_seating_data
    seating_before = get_student_exam_seating_data(student_visal)
    assert len(seating_before) > 0, "Exam should appear in student seating data"
    assert seating_before[0]['has_room'] is False, "Before partition, has_room should be False"
    assert seating_before[0]['room_name'] == "មិនទាន់កំណត់"
    print("2.1 [PASS] Web Dashboard before partition: displays waiting badge (has_room=False)")

    # 2.4 RUN ROOM PARTITION
    from apps.examinations.views import pull_candidates_for_exam
    pulled_count = pull_candidates_for_exam(std_exam)
    print(f"Pulled {pulled_count} candidates for exam")

    # Partition rooms for Grade 12
    total_cands, needed_rooms, _, _ = partition_exam_rooms(
        exam=std_exam,
        start_room_number=1,
        start_roll_number=1,
        cap=25,
        building='អគារ A'
    )
    assert total_cands >= 2, f"Expected at least 2 candidates partitioned, got {total_cands}"
    print(f"2.2 [PASS] Partitioned {total_cands} candidates into {needed_rooms} rooms")

    # Verify candidate records
    cand_visal = ExamCandidate.objects.filter(student=student_visal, exam=std_exam).first()
    assert cand_visal is not None, "Visal candidacy not found"
    assert cand_visal.room is not None, "Candidate must have room assigned"
    assert cand_visal.desk_number > 0, "Candidate must have desk number assigned"
    assert cand_visal.roll_number != "", "Candidate must have roll number"
    print(f"2.3 [PASS] Candidate partitioned: Room={cand_visal.room.room_name}, Desk={cand_visal.desk_number}, Roll={cand_visal.roll_number}")

    # 2.5 TEST AFTER ROOM PARTITION: STUDENT WEB DASHBOARD
    resp_stu_after = student_dashboard(req_stu_before)
    assert resp_stu_after.status_code == 200
    html_after = resp_stu_after.content.decode('utf-8')
    assert cand_visal.room.room_name in html_after, "Room name must appear in student dashboard HTML"
    assert f"តុលេខ {cand_visal.desk_number:02d}" in html_after, "Desk number display must appear in HTML"
    assert "ប័ណ្ណអនុញ្ញាតប្រឡង" in html_after, "Admission pass button must appear in HTML"

    seating_after = get_student_exam_seating_data(student_visal)
    match_visal = next((s for s in seating_after if s['exam_id'] == std_exam.id), None)
    assert match_visal is not None
    assert match_visal['has_room'] is True, "has_room must be True after partition"
    assert match_visal['room_name'] == cand_visal.room.room_name
    assert match_visal['building'] == "អគារ A"
    assert match_visal['desk_number'] == cand_visal.desk_number
    assert match_visal['desk_number_display'] == f"តុលេខ {cand_visal.desk_number:02d}"
    assert match_visal['roll_number'] == cand_visal.roll_number
    assert match_visal['admission_slip_url'] is not None
    print(f"2.4 [PASS] Student Web Dashboard: Room={match_visal['room_name']}, Desk={match_visal['desk_number_display']}, Roll={match_visal['roll_number']}")

    # 2.6 TEST AFTER ROOM PARTITION: PARENT WEB DASHBOARD
    req_parent = factory.get('/dashboard/student/')
    req_parent.user = user_parent
    req_parent.session = SessionStore()
    setattr(req_parent, '_messages', FallbackStorage(req_parent))
    resp_parent = student_dashboard(req_parent)
    assert resp_parent.status_code == 200
    html_parent = resp_parent.content.decode('utf-8')
    parent_child, parent_children = resolve_student_and_children_for_user(user_parent)
    assert len(parent_children) >= 2, f"Parent should resolve 2 children by phone, found {len(parent_children)}"
    cand_parent_child = ExamCandidate.objects.filter(student=parent_child, exam=std_exam).first()
    assert cand_parent_child is not None, "Candidate record for resolved primary child must exist"
    assert cand_parent_child.room.room_name in html_parent, "Child Room name must appear in Parent dashboard"
    assert f"តុលេខ {cand_parent_child.desk_number:02d}" in html_parent, "Child Desk number must appear in Parent dashboard"
    print(f"2.5 [PASS] Parent Web Dashboard: Resolved {len(parent_children)} children, Primary={parent_child.khmer_name}, Room={cand_parent_child.room.room_name}, Desk=តុលេខ {cand_parent_child.desk_number:02d}")

    # 2.7 TEST PARENT CHILD SWITCHER (?student_id=...)
    req_parent_switch = factory.get(f'/dashboard/student/?student_id={student_sreypov.id}')
    req_parent_switch.user = user_parent
    req_parent_switch.session = SessionStore()
    setattr(req_parent_switch, '_messages', FallbackStorage(req_parent_switch))
    resp_parent_switch = student_dashboard(req_parent_switch)
    assert resp_parent_switch.status_code == 200
    html_switch = resp_parent_switch.content.decode('utf-8')
    assert "សុខ ស្រីពៅ" in html_switch, "Switched child name must appear in dashboard HTML"

    switched_child, _ = resolve_student_and_children_for_user(user_parent, str(student_sreypov.id))
    assert switched_child.id == student_sreypov.id, "Parent switcher should resolve child 2"
    print(f"2.6 [PASS] Parent Child Switcher: Successfully switched to child {switched_child.khmer_name}")

    # 2.8 TEST PARENT ACCESS TO ADMISSION SLIP
    req_slip = factory.get(f'/examinations/student/admission-slip/{cand_visal.id}/')
    req_slip.user = user_parent
    req_slip.session = SessionStore()
    setattr(req_slip, '_messages', FallbackStorage(req_slip))
    resp_slip = student_exam_admission_slip(req_slip, candidate_id=cand_visal.id)
    assert resp_slip.status_code == 200, f"Parent should be permitted to view admission slip, got {resp_slip.status_code}"
    print("2.7 [PASS] Parent Permission: Parent can open and print child admission slip successfully")

    # 2.9 TEST MOBILE API: GET /api/v1/dashboard/
    req_m_dash = api_factory.get('/api/v1/dashboard/')
    force_authenticate(req_m_dash, user=user_student)
    resp_m_dash = MobileDashboardSummaryView.as_view()(req_m_dash)
    assert resp_m_dash.status_code == 200
    m_data = resp_m_dash.data['dashboard']['stats']
    assert m_data['has_exam_seating'] is True, "Mobile dashboard stats must have has_exam_seating=True"
    assert m_data['latest_exam_seating'] is not None
    assert m_data['latest_exam_seating']['room_name'] == cand_visal.room.room_name
    assert m_data['latest_exam_seating']['desk_number_display'] == f"តុលេខ {cand_visal.desk_number:02d}"
    print(f"2.8 [PASS] Mobile Dashboard API: room_name={m_data['latest_exam_seating']['room_name']}, desk={m_data['latest_exam_seating']['desk_number_display']}")

    # 2.10 TEST MOBILE API: GET /api/v1/exams/seating/ (DEDICATED ENDPOINT)
    # Test for Student
    req_m_seat = api_factory.get('/api/v1/exams/seating/')
    force_authenticate(req_m_seat, user=user_student)
    resp_m_seat = MobileStudentExamSeatingAPIView.as_view()(req_m_seat)
    assert resp_m_seat.status_code == 200
    assert resp_m_seat.data['status'] == 'success'
    assert resp_m_seat.data['has_seating'] is True
    seatings = resp_m_seat.data['exam_seating']
    assert len(seatings) > 0
    assert seatings[0]['room_name'] == cand_visal.room.room_name
    assert seatings[0]['desk_number_display'] == f"តុលេខ {cand_visal.desk_number:02d}"
    assert len(seatings[0]['subjects']) > 0
    print(f"2.9 [PASS] Mobile Dedicated Seating API (Student): Received {len(seatings)} exams, desk={seatings[0]['desk_number_display']}, subjects={len(seatings[0]['subjects'])}")

    # Test for Parent on Mobile API
    req_m_parent_seat = api_factory.get('/api/v1/exams/seating/')
    force_authenticate(req_m_parent_seat, user=user_parent)
    resp_m_parent_seat = MobileStudentExamSeatingAPIView.as_view()(req_m_parent_seat)
    assert resp_m_parent_seat.status_code == 200
    assert resp_m_parent_seat.data['status'] == 'success'
    assert len(resp_m_parent_seat.data['children']) >= 2, "Parent mobile seating API must return children list"
    assert resp_m_parent_seat.data['has_seating'] is True
    print(f"2.10 [PASS] Mobile Dedicated Seating API (Parent): Resolved {len(resp_m_parent_seat.data['children'])} children, has_seating=True")

    # Test Parent switching child on Mobile API
    req_m_parent_child2 = api_factory.get(f'/api/v1/exams/seating/?student_id={student_sreypov.id}')
    force_authenticate(req_m_parent_child2, user=user_parent)
    resp_m_parent_child2 = MobileStudentExamSeatingAPIView.as_view()(req_m_parent_child2)
    assert resp_m_parent_child2.status_code == 200
    assert resp_m_parent_child2.data['student']['id'] == student_sreypov.id
    print(f"2.11 [PASS] Mobile Dedicated Seating API (Parent Switch): Successfully switched to {resp_m_parent_child2.data['student']['khmer_name']}")

    print("\n================================================================================")
    print("ALL TESTS PASSED SUCCESSFULLY (100%)!")
    print("================================================================================")

if __name__ == '__main__':
    run_tests()
