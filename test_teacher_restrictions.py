import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from rest_framework.test import APIRequestFactory

from apps.accounts.models import User
from apps.teachers.models import Teacher
from apps.academics.models import AcademicYear, Classroom, Subject, Timetable
from apps.students.models import Student
from apps.academics.utils import get_teacher_allowed_classroom_ids
from apps.students.views import student_list, student_detail
from apps.academics.views import student_promotion_view
from apps.mobile_api.views import (
    MobileStudentListView,
    MobileStudentPromotionMetaAPIView,
    MobileStudentPromotionClassStudentsAPIView,
    MobileStudentPromotionSubmitAPIView
)

def run_tests():
    print("=== STARTING TEACHER RESTRICTION TEST SUITE ===")
    rf = RequestFactory()
    apif = APIRequestFactory()

    # 1. Setup Academic Year
    ay, _ = AcademicYear.objects.get_or_create(
        name="2026-2027",
        defaults={'start_date': '2026-01-01', 'end_date': '2026-12-31', 'is_current': True}
    )

    # 2. Setup Classrooms: Class A (taught by teacher), Class B (taught by other)
    class_a, _ = Classroom.objects.get_or_create(
        code="TEST-10A",
        academic_year=ay,
        defaults={'name': 'ថ្នាក់ទី១០A', 'grade_level': 10}
    )
    class_b, _ = Classroom.objects.get_or_create(
        code="TEST-10B",
        academic_year=ay,
        defaults={'name': 'ថ្នាក់ទី១០B', 'grade_level': 10}
    )

    # 3. Setup Users & Teachers
    teacher_user, _ = User.objects.get_or_create(
        username="test_regular_teacher",
        defaults={'role': User.Role.TEACHER, 'email': 'teacher_reg@test.com'}
    )
    teacher_user.role = User.Role.TEACHER
    teacher_user.is_superuser = False
    teacher_user.is_staff = False
    teacher_user.save()

    teacher_prof, _ = Teacher.objects.get_or_create(
        teacher_id="T_REG_001",
        defaults={
            'user': teacher_user,
            'khmer_name': 'គ្រូ ធម្មតា',
            'latin_name': 'Regular Teacher',
            'phone': '012000111'
        }
    )
    teacher_prof.user = teacher_user
    teacher_prof.save()

    admin_user, _ = User.objects.get_or_create(
        username="test_admin_user",
        defaults={'role': User.Role.ADMIN, 'email': 'admin_reg@test.com', 'is_staff': True, 'is_superuser': True}
    )
    admin_user.role = User.Role.ADMIN
    admin_user.is_superuser = True
    admin_user.save()

    # 4. Subject and Timetable for Class A
    subject, _ = Subject.objects.get_or_create(code="SUB-TEST", defaults={'name_kh': 'គណិតវិទ្យា', 'name_en': 'Math'})
    tt, _ = Timetable.objects.get_or_create(
        classroom=class_a,
        teacher=teacher_prof,
        day_of_week=Timetable.DayOfWeek.MONDAY,
        period_number=1,
        defaults={'subject': subject, 'start_time': '07:00:00', 'end_time': '08:00:00'}
    )

    # 5. Setup Students: Student A in Class A, Student B in Class B
    student_a, _ = Student.objects.get_or_create(
        student_id="ST_TEST_A",
        defaults={
            'classroom': class_a,
            'academic_year': ay,
            'khmer_name': 'សិស្ស ថ្នាក់ A',
            'latin_name': 'Student Class A',
            'date_of_birth': '2010-05-15',
            'gender': 'M',
            'status': Student.Status.ACTIVE
        }
    )
    student_a.classroom = class_a
    student_a.save()

    student_b, _ = Student.objects.get_or_create(
        student_id="ST_TEST_B",
        defaults={
            'classroom': class_b,
            'academic_year': ay,
            'khmer_name': 'សិស្ស ថ្នាក់ B',
            'latin_name': 'Student Class B',
            'date_of_birth': '2010-06-20',
            'gender': 'F',
            'status': Student.Status.ACTIVE
        }
    )
    student_b.classroom = class_b
    student_b.save()

    # TEST 1: Helper function get_teacher_allowed_classroom_ids
    allowed_ids = get_teacher_allowed_classroom_ids(teacher_user)
    print(f"Test 1 - get_teacher_allowed_classroom_ids: {allowed_ids}")
    assert class_a.id in allowed_ids, "Class A must be in allowed classroom IDs"
    assert class_b.id not in allowed_ids, "Class B must NOT be in allowed classroom IDs"
    print("[PASS] Test 1 Passed: Timetable classroom properly resolved.")

    # TEST 2: Web student_list for Teacher
    req = rf.get(f'/students/?academic_year={ay.id}')
    req.user = teacher_user
    req.session = {}
    setattr(req, '_messages', FallbackStorage(req))
    resp = student_list(req)
    assert resp.status_code == 200
    content = resp.content.decode('utf-8')
    assert student_a.khmer_name in content, "Student A should be rendered in HTML for teacher"
    assert student_b.khmer_name not in content, "Student B from unassigned class must NOT be rendered in HTML"
    assert class_a.name in content, "Class A should be in classroom filter dropdown"
    assert class_b.name not in content, "Class B must NOT be in classroom filter dropdown"
    print("[PASS] Test 2 Passed: Web student_list strictly filters students & classrooms for teacher.")

    # TEST 3: Web student_list URL tampering attempt with ?classroom=<class_b.id>
    req = rf.get(f'/students/?academic_year={ay.id}&classroom={class_b.id}')
    req.user = teacher_user
    req.session = {}
    setattr(req, '_messages', FallbackStorage(req))
    resp = student_list(req)
    assert resp.status_code == 200
    content_tampered = resp.content.decode('utf-8')
    assert student_b.khmer_name not in content_tampered, "Teacher tampering with ?classroom=Class_B must not see Student B"
    print("[PASS] Test 3 Passed: URL tampering on classroom filter blocked.")

    # TEST 4: Web student_detail access control
    # 4a. Teacher viewing own student (Class A) -> Allowed (200)
    req = rf.get(f'/students/{student_a.id}/')
    req.user = teacher_user
    req.session = {}
    resp = student_detail(req, pk=student_a.id)
    assert resp.status_code == 200, "Teacher must be allowed to view own student"

    # 4b. Teacher viewing unassigned student (Class B) -> Denied (Redirect + error message)
    req = rf.get(f'/students/{student_b.id}/')
    req.user = teacher_user
    req.session = {}
    setattr(req, '_messages', FallbackStorage(req))
    resp = student_detail(req, pk=student_b.id)
    assert resp.status_code == 302, "Teacher must be redirected when trying to view unassigned student"
    assert resp.url == '/students/', f"Expected redirect to student_list, got {resp.url}"
    print("[PASS] Test 4 Passed: Web student_detail protects unassigned students from teacher access.")

    # TEST 5: Web student_promotion_view access control
    # 5a. Teacher accessing promotion view -> Forbidden / Redirected
    req = rf.get('/academics/promotion/')
    req.user = teacher_user
    req.session = {}
    setattr(req, '_messages', FallbackStorage(req))
    resp = student_promotion_view(req)
    assert resp.status_code in [302, 403], f"Teacher should be denied access to promotion, got {resp.status_code}"

    # 5b. Admin accessing promotion view -> Allowed (200)
    req = rf.get('/academics/promotion/')
    req.user = admin_user
    req.session = {}
    resp = student_promotion_view(req)
    assert resp.status_code == 200, "Admin must have access to student_promotion_view"
    print("[PASS] Test 5 Passed: Web Student Promotion locked to Admin only.")

    # TEST 6: Mobile API Student List (/api/v1/students/)
    view = MobileStudentListView.as_view()
    req = apif.get(f'/api/v1/students/?academic_year_id={ay.id}')
    req.user = teacher_user
    resp = view(req)
    assert resp.status_code == 200
    mobile_data = resp.data
    m_student_ids = [s['id'] for s in mobile_data['students']]
    assert student_a.id in m_student_ids, "Student A must be in mobile list for teacher"
    assert student_b.id not in m_student_ids, "Student B must NOT be in mobile list for teacher"
    m_class_ids = [c['id'] for c in mobile_data['classrooms']]
    assert class_a.id in m_class_ids, "Class A must be in mobile classrooms list for teacher"
    assert class_b.id not in m_class_ids, "Class B must NOT be in mobile classrooms list for teacher"
    print("[PASS] Test 6 Passed: Mobile API student list strictly filtered for teacher.")

    # TEST 7: Mobile API Student Promotion Endpoints
    # 7a. Meta endpoint
    meta_view = MobileStudentPromotionMetaAPIView.as_view()
    req = apif.get('/api/v1/students/promotion/meta/')
    req.user = teacher_user
    resp = meta_view(req)
    assert resp.status_code == 403, f"Expected 403 for teacher in meta view, got {resp.status_code}"
    assert resp.data.get('error_code') == 'TEACHER_PROMOTION_FORBIDDEN'

    req.user = admin_user
    resp = meta_view(req)
    assert resp.status_code == 200, f"Expected 200 for admin in meta view, got {resp.status_code}"

    # 7b. Students endpoint
    stud_view = MobileStudentPromotionClassStudentsAPIView.as_view()
    req = apif.get(f'/api/v1/students/promotion/students/?source_class_id={class_a.id}')
    req.user = teacher_user
    resp = stud_view(req)
    assert resp.status_code == 403, f"Expected 403 for teacher in class students view, got {resp.status_code}"
    assert resp.data.get('error_code') == 'TEACHER_PROMOTION_FORBIDDEN'

    # 7c. Submit endpoint
    submit_view = MobileStudentPromotionSubmitAPIView.as_view()
    req = apif.post('/api/v1/students/promotion/submit/', data={'source_class_id': class_a.id, 'students': []}, format='json')
    req.user = teacher_user
    resp = submit_view(req)
    assert resp.status_code == 403, f"Expected 403 for teacher in submit view, got {resp.status_code}"
    assert resp.data.get('error_code') == 'TEACHER_PROMOTION_FORBIDDEN'
    print("[PASS] Test 7 Passed: Mobile API promotion endpoints return 403 TEACHER_PROMOTION_FORBIDDEN for teachers.")

    print("\nALL 7 RESTRICTION TESTS PASSED PERFECTLY!")

if __name__ == '__main__':
    run_tests()
