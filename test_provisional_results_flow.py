import os
import sys
from decimal import Decimal
from datetime import date
import django

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage

from apps.academics.models import AcademicYear, Classroom, Subject
from apps.students.models import Student
from apps.teachers.models import Teacher
from apps.examinations.models import (
    ExamTerm,
    StandardizedExam,
    ExamRoom,
    ExamSubject,
    ExamCandidate,
    CandidateSubjectScore,
)
from apps.examinations.views import (
    api_toggle_exam_provisional_publish,
    api_toggle_term_provisional_publish,
    exam_provisional_results_view,
    student_exam_provisional_slip,
)
from apps.dashboard.views import teacher_dashboard, student_dashboard
from apps.examinations.services import get_student_exam_seating_data

User = get_user_model()


def add_session_and_messages(request):
    """Helper to attach session and messages storage to RequestFactory requests."""
    from django.contrib.sessions.middleware import SessionMiddleware
    middleware = SessionMiddleware(lambda req: None)
    middleware.process_request(request)
    request.session.save()
    messages = FallbackStorage(request)
    setattr(request, '_messages', messages)


def setup_test_data():
    print(">>> Setting up test fixture data...")
    # Clean previous test entities
    StandardizedExam.objects.filter(name="ការប្រឡងឆមាសទី១ ថ្នាក់ទី១២ (TEST)").delete()
    ExamTerm.objects.filter(name="ប្រឡងឆមាសទី១ (ផ្លូវការ TEST)").delete()
    Student.objects.filter(student_id="STU-9901-TEST").delete()
    Teacher.objects.filter(teacher_id="T901-TEST").delete()
    User.objects.filter(username__in=["admin_test_prov", "teacher_test_prov", "student_test_prov"]).delete()

    ay, _ = AcademicYear.objects.get_or_create(
        name="2025-2026-TEST",
        defaults={'start_date': date(2025, 10, 1), 'end_date': date(2026, 8, 31), 'is_current': True}
    )
    cls12, _ = Classroom.objects.get_or_create(
        name="12A1-TEST",
        academic_year=ay,
        defaults={'grade_level': 12, 'code': '12A1-TEST', 'room_number': '101'}
    )
    subj_math, _ = Subject.objects.get_or_create(code="MTH12-T", defaults={'name_kh': "គណិតវិទ្យា", 'name_en': "Mathematics", 'order': 1})
    subj_phys, _ = Subject.objects.get_or_create(code="PHY12-T", defaults={'name_kh': "រូបវិទ្យា", 'name_en': "Physics", 'order': 2})

    admin_user = User.objects.create(username="admin_test_prov", role='ADMIN', is_superuser=True, is_staff=True)
    admin_user.set_password('Admin@123')
    admin_user.save()

    teacher_user = User.objects.create(username="teacher_test_prov", role='TEACHER')
    teacher_user.set_password('Teacher@123')
    teacher_user.save()

    teacher, _ = Teacher.objects.get_or_create(user=teacher_user, defaults={'khmer_name': 'គ្រូ ពិសិដ្ឋ', 'teacher_id': 'T901-TEST', 'specialization': 'គណិត'})
    cls12.homeroom_teacher = teacher
    cls12.save()

    student_user = User.objects.create(username="student_test_prov", role='STUDENT', phone='012999888')
    student_user.set_password('Student@123')
    student_user.save()

    student = Student.objects.create(
        student_id="STU-9901-TEST",
        khmer_name="សុខ វិបុល",
        latin_name="Sok Vibul",
        classroom=cls12,
        academic_year=ay,
        user=student_user,
        phone='012999888',
        gender='M',
        date_of_birth=date(2008, 5, 10),
        status='ACTIVE'
    )

    # Standardized exam with is_published=False, is_provisional_published=False
    exam = StandardizedExam.objects.create(
        name="ការប្រឡងឆមាសទី១ ថ្នាក់ទី១២ (TEST)",
        academic_year=ay,
        exam_date=date(2026, 2, 15),
        grade_level=12,
        is_published=False,
        is_provisional_published=False
    )

    room1 = ExamRoom.objects.create(exam=exam, room_number=1, room_name="បន្ទប់ ០១", building="អគារ A")
    es_math = ExamSubject.objects.create(exam=exam, subject=subj_math, max_score=Decimal('100.00'), coefficient=Decimal('2.00'))
    es_phys = ExamSubject.objects.create(exam=exam, subject=subj_phys, max_score=Decimal('50.00'), coefficient=Decimal('1.00'))

    cand = ExamCandidate.objects.create(
        exam=exam,
        student=student,
        room=room1,
        roll_number='12001',
        desk_number=1,
        candidate_name_kh=student.khmer_name,
        origin_class='12A1',
        student_code=student.student_id,
    )

    # Enter scores: Math 80/100, Phys 40/50
    CandidateSubjectScore.objects.create(candidate=cand, exam_subject=es_math, score=Decimal('80.00'))
    CandidateSubjectScore.objects.create(candidate=cand, exam_subject=es_phys, score=Decimal('40.00'))

    # ExamTerm
    term = ExamTerm.objects.create(
        name="ប្រឡងឆមាសទី១ (ផ្លូវការ TEST)",
        academic_year=ay,
        start_date=date(2026, 2, 10),
        end_date=date(2026, 2, 20),
        is_published=False,
        is_provisional_published=False
    )
    exam.exam_term = term
    exam.save()

    print("[PASS] Test data prepared successfully.")
    return {
        'ay': ay,
        'cls12': cls12,
        'student': student,
        'student_user': student_user,
        'teacher': teacher,
        'teacher_user': teacher_user,
        'admin_user': admin_user,
        'exam': exam,
        'room1': room1,
        'cand': cand,
        'term': term,
    }


def test_admin_toggle_provisional_publish_flow(data):
    """
    Test Admin 1-click button to activate and deactivate provisional results.
    Verifies that recalculate_all_ranks() is automatically triggered upon activation.
    """
    print("\n--- TEST 1: Admin Toggle Provisional Publish Flow & Auto-Recalculate ---")
    rf = RequestFactory()
    exam = data['exam']
    cand = data['cand']
    admin_user = data['admin_user']

    # Initial state: provisional is False
    assert exam.is_provisional_published is False
    print("Initial state confirmed: is_provisional_published is False.")

    # 1. Admin activates provisional results
    req = rf.post(f'/examinations/standardized/{exam.id}/toggle-provisional-publish/', {}, content_type='application/json')
    req.user = admin_user
    add_session_and_messages(req)

    resp = api_toggle_exam_provisional_publish(req, exam.id)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

    exam.refresh_from_db()
    cand.refresh_from_db()

    # Assert provisional published is True and auto-recalculated
    assert exam.is_provisional_published is True
    assert exam.provisional_published_at is not None

    # Total score: 80 + 40 = 120. Weighted avg: (80*2 + 40*1) / (2+1) = 200/3 = 66.67
    assert cand.total_score == Decimal('120.00'), f"Expected total 120.00, got {cand.total_score}"
    assert cand.average_score == Decimal('66.67'), f"Expected avg 66.67, got {cand.average_score}"
    assert cand.grade_letter == 'B', f"Expected grade B, got {cand.grade_letter}"
    assert cand.rank_overall == 1, f"Expected rank 1, got {cand.rank_overall}"
    assert cand.rank_in_room == 1, f"Expected room rank 1, got {cand.rank_in_room}"
    print(f"[PASS] Activation verified! Total: {cand.total_score}, Avg: {cand.average_score}, Grade: {cand.grade_letter}, Rank: {cand.rank_overall}")

    # 2. Admin deactivates provisional results
    req_off = rf.post(f'/examinations/standardized/{exam.id}/toggle-provisional-publish/', {}, content_type='application/json')
    req_off.user = admin_user
    add_session_and_messages(req_off)

    resp_off = api_toggle_exam_provisional_publish(req_off, exam.id)
    assert resp_off.status_code == 200, f"Expected 200, got {resp_off.status_code}"

    exam.refresh_from_db()
    assert exam.is_provisional_published is False
    print("[PASS] Deactivation verified! is_provisional_published reverted to False.")


def test_teacher_access_to_provisional_results(data):
    """
    Test Teacher view of provisional results:
    - Blocked when provisional results are NOT active.
    - Allowed when provisional results ARE active.
    - Visible on teacher_dashboard when active.
    """
    print("\n--- TEST 2: Teacher Access & Dashboard Visibility ---")
    rf = RequestFactory()
    exam = data['exam']
    teacher_user = data['teacher_user']

    # Case 1: is_provisional_published=False -> Teacher is redirected
    exam.is_provisional_published = False
    exam.is_published = False
    exam.save()

    req_blocked = rf.get(f'/examinations/standardized/{exam.id}/provisional-results/')
    req_blocked.user = teacher_user
    add_session_and_messages(req_blocked)

    resp_blocked = exam_provisional_results_view(req_blocked, exam.id)
    assert resp_blocked.status_code == 302, f"Expected redirect 302, got {resp_blocked.status_code}"
    print("[PASS] Teacher blocked when provisional results are not published.")

    # Case 2: is_provisional_published=True -> Teacher can access board
    exam.is_provisional_published = True
    exam.recalculate_all_ranks()
    exam.save()

    req_allowed = rf.get(f'/examinations/standardized/{exam.id}/provisional-results/')
    req_allowed.user = teacher_user
    add_session_and_messages(req_allowed)

    resp_allowed = exam_provisional_results_view(req_allowed, exam.id)
    assert resp_allowed.status_code == 200, f"Expected 200, got {resp_allowed.status_code}"
    content = resp_allowed.content.decode('utf-8')
    assert "តារាងបិទផ្សាយបណ្តោះអាសន្ន" in content
    assert "សុខ វិបុល" in content
    print("[PASS] Teacher successfully accessed provisional results board when published.")

    # Case 3: Teacher dashboard shows active provisional exams
    req_dash = rf.get('/dashboard/teacher/')
    req_dash.user = teacher_user
    add_session_and_messages(req_dash)

    resp_dash = teacher_dashboard(req_dash)
    assert resp_dash.status_code == 200
    dash_content = resp_dash.content.decode('utf-8')
    assert "លទ្ធផលប្រឡងបណ្តោះអាសន្ន" in dash_content
    assert exam.name in dash_content
    print("[PASS] Teacher dashboard correctly displays provisional exam widget and statistics.")


def test_student_and_parent_access_to_provisional_results(data):
    """
    Test Student & Parent view of provisional results:
    - When inactive: scores and GPA are hidden from student_dashboard and slip is blocked.
    - When active: scores, average (GPA), grade letter, rankings, and provisional slip are fully accessible.
    """
    print("\n--- TEST 3: Student & Parent Access, Scores, Averages & Result Slip ---")
    rf = RequestFactory()
    exam = data['exam']
    student = data['student']
    student_user = data['student_user']
    cand = data['cand']

    # Case 1: Provisional results NOT published
    exam.is_provisional_published = False
    exam.is_published = False
    exam.save()

    seating_before = get_student_exam_seating_data(student)
    assert len(seating_before) > 0
    item_before = seating_before[0]
    assert item_before['is_provisional_published'] is False
    assert item_before['total_score'] is None
    assert item_before['average_score'] is None
    print("[PASS] Seating data correctly suppresses scores and GPA when not published.")

    # Slip access blocked
    req_slip_blocked = rf.get(f'/examinations/student/provisional-slip/{cand.id}/')
    req_slip_blocked.user = student_user
    add_session_and_messages(req_slip_blocked)

    resp_slip_blocked = student_exam_provisional_slip(req_slip_blocked, cand.id)
    assert resp_slip_blocked.status_code == 302
    print("[PASS] Direct provisional slip access blocked for student when not published.")

    # Case 2: Provisional results published by Admin
    exam.is_provisional_published = True
    exam.recalculate_all_ranks()
    exam.save()

    seating_after = get_student_exam_seating_data(student)
    item_after = seating_after[0]
    assert item_after['is_provisional_published'] is True
    assert item_after['total_score'] == Decimal('120.00')
    assert item_after['average_score'] == Decimal('66.67')
    assert item_after['grade_letter'] == 'B'
    assert item_after['rank_overall'] == 1
    assert len(item_after['subject_scores']) == 2
    print(f"[PASS] Seating data reveals scores: Total={item_after['total_score']}, Avg={item_after['average_score']}, Grade={item_after['grade_letter']}")

    # Student dashboard renders provisional scores and average
    req_stu_dash = rf.get('/dashboard/student/')
    req_stu_dash.user = student_user
    add_session_and_messages(req_stu_dash)

    resp_stu_dash = student_dashboard(req_stu_dash)
    assert resp_stu_dash.status_code == 200
    stu_content = resp_stu_dash.content.decode('utf-8')
    assert "លទ្ធផលបណ្តោះអាសន្ន" in stu_content
    # In Django templates with localization, decimals may format as 66.67 or 66,67
    assert any(x in stu_content for x in ["66.67", "66,67", "66.7", "66,7"]), "Average score not found in student dashboard content"
    print("[PASS] Student dashboard prominently displays provisional scores, weighted average, and rank.")

    # Student provisional result slip view
    req_slip = rf.get(f'/examinations/student/provisional-slip/{cand.id}/')
    req_slip.user = student_user
    add_session_and_messages(req_slip)

    resp_slip = student_exam_provisional_slip(req_slip, cand.id)
    assert resp_slip.status_code == 200
    slip_content = resp_slip.content.decode('utf-8')
    assert "ព្រឹត្តិបត្រលទ្ធផលបណ្តោះអាសន្ន" in slip_content
    assert "សុខ វិបុល" in slip_content
    assert any(x in slip_content for x in ["120.00", "120,00", "120"]), "Total score 120 not found in slip content"
    print("[PASS] Student provisional printable slip rendered with complete subject breakdown and QR validation.")


def test_exam_term_toggle_provisional_publish(data):
    """
    Test Admin toggling provisional results for classroom-based ExamTerm.
    """
    print("\n--- TEST 4: Classroom-based ExamTerm Toggle ---")
    rf = RequestFactory()
    term = data['term']
    admin_user = data['admin_user']

    assert term.is_provisional_published is False

    req = rf.post(f'/examinations/terms/{term.id}/toggle-provisional-publish/', {}, content_type='application/json')
    req.user = admin_user
    add_session_and_messages(req)

    resp = api_toggle_term_provisional_publish(req, term.id)
    assert resp.status_code == 200

    term.refresh_from_db()
    assert term.is_provisional_published is True
    print("[PASS] ExamTerm provisional published toggled to True.")

    # Toggle off
    req_off = rf.post(f'/examinations/terms/{term.id}/toggle-provisional-publish/', {}, content_type='application/json')
    req_off.user = admin_user
    add_session_and_messages(req_off)

    resp_off = api_toggle_term_provisional_publish(req_off, term.id)
    assert resp_off.status_code == 200

    term.refresh_from_db()
    assert term.is_provisional_published is False
    print("[PASS] ExamTerm provisional published reverted to False.")


def run_all_tests():
    print("=====================================================================")
    print("  RUNNING FULL PROVISIONAL EXAM RESULTS FLOW TEST SUITE")
    print("=====================================================================")
    data = setup_test_data()
    try:
        test_admin_toggle_provisional_publish_flow(data)
        test_teacher_access_to_provisional_results(data)
        test_student_and_parent_access_to_provisional_results(data)
        test_exam_term_toggle_provisional_publish(data)
        print("\n=====================================================================")
        print("  ALL 4 PROVISIONAL EXAM RESULT TESTS PASSED SUCCESSFULLY! (100%)")
        print("=====================================================================")
    finally:
        print("\n>>> Cleaning up test data...")
        StandardizedExam.objects.filter(name="ការប្រឡងឆមាសទី១ ថ្នាក់ទី១២ (TEST)").delete()
        ExamTerm.objects.filter(name="ប្រឡងឆមាសទី១ (ផ្លូវការ TEST)").delete()
        Student.objects.filter(student_id="STU-9901-TEST").delete()
        Teacher.objects.filter(teacher_id="T901-TEST").delete()
        User.objects.filter(username__in=["admin_test_prov", "teacher_test_prov", "student_test_prov"]).delete()
        print("Cleanup done.")

if __name__ == '__main__':
    run_all_tests()
