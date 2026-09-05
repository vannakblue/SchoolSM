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
from apps.teachers.models import Teacher
from apps.examinations.models import StandardizedExam, ExamRoom, ExamInvigilatorPlan, ExamShiftSlot, TeacherShiftRegistration

User = get_user_model()

def test_invigilator_exam_session_integration():
    print("=== STARTING EXAM SESSION & INVIGILATOR INTEGRATION TEST SUITE ===")

    # 1. Setup Admin & Teacher users
    admin_user, _ = User.objects.get_or_create(username='admin_test', defaults={'role': 'ADMIN', 'is_staff': True, 'is_superuser': True})
    admin_user.role = 'ADMIN'
    admin_user.set_password('Admin@1234')
    admin_user.save()

    client = Client()
    client.force_login(admin_user)

    ay, _ = AcademicYear.objects.get_or_create(name='2026-2027', defaults={'is_active': True})
    ay.is_active = True
    ay.save()

    # 2. Clean previous test items
    StandardizedExam.objects.filter(name__icontains='តេស្តអនុរក្សសម័យប្រឡង').delete()
    ExamInvigilatorPlan.objects.filter(title__icontains='តេស្តអនុរក្សសម័យប្រឡង').delete()

    # 3. Create a test StandardizedExam with 3 rooms
    exam = StandardizedExam.objects.create(
        name='តេស្តអនុរក្សសម័យប្រឡង ឆមាសទី១ ថ្នាក់ទី ១២',
        academic_year=ay,
        grade_level=12,
        track='ALL',
        session='MORNING',
        exam_date=datetime.date(2026, 9, 20),
        candidates_per_room=25,
        is_published=True
    )
    for i in range(1, 4):
        ExamRoom.objects.create(exam=exam, room_number=i, room_name=f"បន្ទប់ {i:02d}")
    assert exam.rooms.count() == 3
    print("1. [PASS] Created StandardizedExam with 3 rooms.")

    # 4. Create an ExamInvigilatorPlan linked to this exam
    # When 3 rooms exist, default capacity should be 3 * 2 = 6 invigilators per shift
    plan = ExamInvigilatorPlan.objects.create(
        academic_year=ay,
        standardized_exam=exam,
        session_key=f"{ay.id}_{exam.exam_date}_តេស្តអនុរក្សសម័យប្រឡង ឆមាសទី១",
        title=f"វេនអនុរក្ស៖ {exam.name}",
        start_date=exam.exam_date,
        end_date=exam.exam_date,
        is_active=True,
        allow_teacher_registration=True,
        default_regular_quota=4,
        default_office_quota=5
    )
    ExamInvigilatorPlan.objects.exclude(id=plan.id).update(is_active=False)

    slot_morning = ExamShiftSlot.objects.create(
        plan=plan,
        date=exam.exam_date,
        session='MORNING',
        session_name="ថ្ងៃទី១ - 🌅 ពេលព្រឹក",
        start_time=datetime.time(7, 0),
        end_time=datetime.time(11, 0),
        max_invigilators=6,
        order=1
    )
    print(f"2. [PASS] Created ExamInvigilatorPlan linked to StandardizedExam ID={exam.id}, slot max={slot_morning.max_invigilators}.")

    # 5. Test standardized_exam_manage view renders the invigilator button & info
    res_manage = client.get(f'/examinations/standardized/{exam.id}/manage/')
    assert res_manage.status_code == 200
    content_manage = res_manage.content.decode('utf-8')
    assert 'វេនអនុរក្ស' in content_manage
    assert str(plan.id) in content_manage
    print("3. [PASS] standardized_exam_manage correctly displays invigilator plan link & details.")

    # 6. Test standardized_exam_list view matches invigilator plan to session
    res_list = client.get(f'/examinations/standardized/?year={ay.id}')
    assert res_list.status_code == 200
    content_list = res_list.content.decode('utf-8')
    assert 'វេនអនុរក្ស' in content_list
    assert 'openSessionInvigilatorModal' in content_list
    assert 'invigilatorModal_' in content_list
    assert 'តារាងម៉ាទ្រីសអនុរក្ស' in content_list
    print("4. [PASS] standardized_exam_list correctly associates invigilator plan and renders interactive modal.")

    # 7. Test teacher portal shows linked exam session title
    # Create or get teacher
    teacher, _ = Teacher.objects.get_or_create(
        teacher_id='T_INVIG_TEST',
        defaults={'khmer_name': 'ស៊ុំ វិបុល', 'gender': 'M', 'status': Teacher.Status.ACTIVE}
    )
    teacher_user, _ = User.objects.get_or_create(username='teacher_invig_test', defaults={'role': 'TEACHER'})
    teacher_user.role = 'TEACHER'
    teacher_user.save()
    teacher.user = teacher_user
    teacher.save()

    client_teacher = Client()
    client_teacher.force_login(teacher_user)
    res_portal = client_teacher.get('/examinations/invigilator-request/')
    assert res_portal.status_code == 200
    content_portal = res_portal.content.decode('utf-8')
    assert 'សម័យប្រឡង៖' in content_portal
    assert plan.display_session_name in content_portal
    assert 'សម័យប្រឡងទាំងមូល (គ្រប់កម្រិតថ្នាក់)' in content_portal
    print("5. [PASS] Teacher portal prominently displays linked exam session name and whole-session badge.")

    # 8. Test slot toggle registration
    reg_res = client_teacher.post('/examinations/api/invigilator-slot/toggle/', {
        'slot_id': slot_morning.id
    }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
    assert reg_res.status_code == 200
    reg_json = reg_res.json()
    assert reg_json['success'] is True
    assert reg_json['is_registered'] is True
    print("6. [PASS] Teacher successfully registered for slot in exam session.")

    # Clean up
    exam.delete()
    plan.delete()
    print("7. [PASS] Cleaned up test data.")

    print("\n=== ALL 7 EXAM SESSION & INVIGILATOR TESTS PASSED 100%! ===")

if __name__ == '__main__':
    test_invigilator_exam_session_integration()
