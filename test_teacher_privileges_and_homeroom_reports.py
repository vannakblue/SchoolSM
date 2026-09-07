import os
import sys
import django
from decimal import Decimal

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from apps.teachers.models import Teacher
from apps.students.models import Student
from apps.academics.models import AcademicYear, Classroom, Subject, ClassSubject
from apps.examinations.models import ExamTerm, Grade
from apps.teachers.permissions import (
    get_teacher_privileges,
    can_teacher_manage_homeroom,
    can_teacher_grade_subject
)
from apps.examinations.services import get_student_cumulative_dossier_data
from apps.examinations.views import (
    monthly_results_print_view,
    homeroom_study_tracking_book_view,
    slow_learners_report_view,
    student_cumulative_dossier_view,
    homeroom_cumulative_dossier_batch_view,
    grade_entry_matrix
)
from apps.attendance.views import homeroom_attendance_roster_view
from apps.dashboard.views import teacher_dashboard

User = get_user_model()

def setup_request(request, user):
    request.user = user
    setattr(request, 'session', {})
    messages = FallbackStorage(request)
    setattr(request, '_messages', messages)
    return request

def run_tests():
    print("=== STARTING TEACHER PRIVILEGES & HOMEROOM REPORTS TEST SUITE ===")
    
    # 1. Setup Academic Year
    academic_year, _ = AcademicYear.objects.get_or_create(
        name="2025-2026",
        defaults={
            "start_date": "2025-10-01",
            "end_date": "2026-08-31",
            "is_current": True
        }
    )
    if not academic_year.is_current:
        academic_year.is_current = True
        academic_year.save()
    
    # 2. Setup Users & Teachers
    # Teacher 1: Homeroom teacher of Class 10A, teaches Math
    user_t1, _ = User.objects.get_or_create(
        username="teacher_homeroom_math",
        defaults={"first_name": "Sok", "last_name": "Chan", "role": "TEACHER", "is_staff": False}
    )
    user_t1.role = "TEACHER"
    user_t1.save()
    teacher_1, _ = Teacher.objects.get_or_create(
        user=user_t1,
        defaults={
            "teacher_id": "T001",
            "phone": "012111111",
            "khmer_name": "សុក ចាន់",
            "latin_name": "Sok Chan",
            "specialization": "Mathematics"
        }
    )
    
    # Teacher 2: Subject teacher only (teaches Physics in 10A, not homeroom)
    user_t2, _ = User.objects.get_or_create(
        username="teacher_subject_physics",
        defaults={"first_name": "Keo", "last_name": "Dara", "role": "TEACHER", "is_staff": False}
    )
    user_t2.role = "TEACHER"
    user_t2.save()
    teacher_2, _ = Teacher.objects.get_or_create(
        user=user_t2,
        defaults={
            "teacher_id": "T002",
            "phone": "012222222",
            "khmer_name": "កែវ តារា",
            "latin_name": "Keo Dara",
            "specialization": "Physics"
        }
    )
    
    # Admin user
    user_admin, _ = User.objects.get_or_create(
        username="admin_test_user",
        defaults={"first_name": "Admin", "last_name": "System", "role": "ADMIN", "is_staff": True, "is_superuser": True}
    )
    user_admin.role = "ADMIN"
    user_admin.save()
    
    # 3. Setup Subjects & Rules
    from apps.academics.models import GradeLevelRule
    math_subj, _ = Subject.objects.get_or_create(
        code="MATH-10",
        defaults={"name_en": "Mathematics", "name_kh": "គណិតវិទ្យា", "credit": 4}
    )
    phys_subj, _ = Subject.objects.get_or_create(
        code="PHYS-10",
        defaults={"name_en": "Physics", "name_kh": "រូបវិទ្យា", "credit": 2}
    )
    chem_subj, _ = Subject.objects.get_or_create(
        code="CHEM-10",
        defaults={"name_en": "Chemistry", "name_kh": "គីមីវិទ្យា", "credit": 2}
    )
    GradeLevelRule.objects.get_or_create(
        grade_level=10,
        track='GENERAL',
        subject=math_subj,
        defaults={"max_score": Decimal("100.00"), "weekly_hours": 4}
    )
    GradeLevelRule.objects.get_or_create(
        grade_level=10,
        track='GENERAL',
        subject=phys_subj,
        defaults={"max_score": Decimal("50.00"), "weekly_hours": 2}
    )
    
    # 4. Setup Classroom
    classroom_10a, _ = Classroom.objects.get_or_create(
        code="10A",
        academic_year=academic_year,
        defaults={
            "name": "ថ្នាក់ទី ១០A",
            "grade_level": 10,
            "homeroom_teacher": teacher_1,
            "capacity": 40
        }
    )
    if classroom_10a.homeroom_teacher != teacher_1:
        classroom_10a.homeroom_teacher = teacher_1
        classroom_10a.save()
        
    classroom_10b, _ = Classroom.objects.get_or_create(
        code="10B",
        academic_year=academic_year,
        defaults={
            "name": "ថ្នាក់ទី ១០B",
            "grade_level": 10,
            "homeroom_teacher": teacher_2,
            "capacity": 40
        }
    )
    
    # 5. Assign Subject Teaching via ClassSubject
    # Teacher 1 teaches Math in 10A
    cs_math, _ = ClassSubject.objects.get_or_create(
        classroom=classroom_10a,
        subject=math_subj,
        defaults={"teacher": teacher_1, "weekly_hours": 4}
    )
    if cs_math.teacher != teacher_1:
        cs_math.teacher = teacher_1
        cs_math.save()

    # Teacher 2 teaches Physics in 10A
    cs_phys, _ = ClassSubject.objects.get_or_create(
        classroom=classroom_10a,
        subject=phys_subj,
        defaults={"teacher": teacher_2, "weekly_hours": 2}
    )
    if cs_phys.teacher != teacher_2:
        cs_phys.teacher = teacher_2
        cs_phys.save()
        
    # 6. Setup Students
    user_s1, _ = User.objects.get_or_create(
        username="student_roth",
        defaults={"first_name": "Roth", "last_name": "Sok", "role": "student"}
    )
    student_1, _ = Student.objects.get_or_create(
        user=user_s1,
        defaults={
            "student_id": "STU1001",
            "classroom": classroom_10a,
            "academic_year": academic_year,
            "gender": "F",
            "khmer_name": "សុខ រ័ត្ន",
            "latin_name": "Sok Roth",
            "date_of_birth": "2010-05-15"
        }
    )
    if student_1.classroom != classroom_10a:
        student_1.classroom = classroom_10a
        student_1.save()

    user_s2, _ = User.objects.get_or_create(
        username="student_vibol",
        defaults={"first_name": "Vibol", "last_name": "Chan", "role": "student"}
    )
    student_2, _ = Student.objects.get_or_create(
        user=user_s2,
        defaults={
            "student_id": "STU1002",
            "classroom": classroom_10a,
            "academic_year": academic_year,
            "gender": "M",
            "khmer_name": "ចាន់ វិបុល",
            "latin_name": "Chan Vibol",
            "date_of_birth": "2010-08-20"
        }
    )
    if student_2.classroom != classroom_10a:
        student_2.classroom = classroom_10a
        student_2.save()

    # 7. Setup ExamTerm and Grades
    exam_term, _ = ExamTerm.objects.get_or_create(
        name="October Monthly Exam 2025",
        academic_year=academic_year,
        defaults={
            "term_type": ExamTerm.TermType.MONTHLY,
            "start_date": "2025-10-01",
            "end_date": "2025-10-31",
            "is_published": True,
            "is_provisional_published": True
        }
    )
    
    # Grade for student 1: Math = 85 (pass), Physics = 20 (slow learner: 20/50 = 40% < 50%)
    Grade.objects.update_or_create(
        student=student_1,
        subject=math_subj,
        exam_term=exam_term,
        classroom=classroom_10a,
        defaults={"score": Decimal("85.00"), "max_score": Decimal("100.00")}
    )
    Grade.objects.update_or_create(
        student=student_1,
        subject=phys_subj,
        exam_term=exam_term,
        classroom=classroom_10a,
        defaults={"score": Decimal("20.00"), "max_score": Decimal("50.00")}
    )
    
    # Grade for student 2: Math = 35 (slow learner: 35/100 = 35% < 50%), Physics = 45 (pass)
    Grade.objects.update_or_create(
        student=student_2,
        subject=math_subj,
        exam_term=exam_term,
        classroom=classroom_10a,
        defaults={"score": Decimal("35.00"), "max_score": Decimal("100.00")}
    )
    Grade.objects.update_or_create(
        student=student_2,
        subject=phys_subj,
        exam_term=exam_term,
        classroom=classroom_10a,
        defaults={"score": Decimal("45.00"), "max_score": Decimal("50.00")}
    )

    factory = RequestFactory()
    
    print("\n--- TEST 1: Permissions Helper (get_teacher_privileges) ---")
    p1 = get_teacher_privileges(user_t1)
    print(f"Teacher 1 privileges: is_homeroom={p1['is_homeroom_teacher']}, homeroom_classrooms={[c.code for c in p1['homeroom_classrooms']]}, teaching_subject_ids={p1['teaching_subject_ids']}")
    assert p1['is_homeroom_teacher'] is True, "Teacher 1 must be detected as homeroom teacher"
    assert classroom_10a in p1['homeroom_classrooms'], "Teacher 1 must have 10A in homeroom classes"
    assert math_subj.id in p1['teaching_subject_ids'], "Teacher 1 teaches Math"
    
    p2 = get_teacher_privileges(user_t2)
    print(f"Teacher 2 privileges: is_homeroom={p2['is_homeroom_teacher']}, homeroom_classrooms={[c.code for c in p2['homeroom_classrooms']]}, teaching_subject_ids={p2['teaching_subject_ids']}")
    assert classroom_10a not in p2['homeroom_classrooms'], "Teacher 2 is NOT homeroom teacher of 10A"
    assert phys_subj.id in p2['teaching_subject_ids'], "Teacher 2 teaches Physics"
    assert math_subj.id not in p2['teaching_subject_ids'], "Teacher 2 does NOT teach Math"
    print("✓ Test 1 Passed: Privilege helper correctly categorizes homeroom and subject teaching rights.")

    print("\n--- TEST 2: Authorization Functions (can_teacher_manage_homeroom & can_teacher_grade_subject) ---")
    # Homeroom check
    assert can_teacher_manage_homeroom(user_t1, classroom_10a.id) is True, "T1 can manage 10A homeroom"
    assert can_teacher_manage_homeroom(user_t2, classroom_10a.id) is False, "T2 CANNOT manage 10A homeroom"
    assert can_teacher_manage_homeroom(user_admin, classroom_10a.id) is True, "Admin can manage any homeroom"
    
    # Subject grade check: Teacher 2 is Physics teacher in 10A (NOT homeroom of 10A)
    assert can_teacher_grade_subject(user_t2, classroom_10a.id, phys_subj.id) is True, "T2 can grade Physics in 10A"
    assert can_teacher_grade_subject(user_t2, classroom_10a.id, math_subj.id) is False, "T2 CANNOT grade Math in 10A"
    assert can_teacher_grade_subject(user_admin, classroom_10a.id, math_subj.id) is True, "Admin can grade Math in 10A"
    print("✓ Test 2 Passed: can_teacher_manage_homeroom and can_teacher_grade_subject strictly enforced.")

    print("\n--- TEST 3: Grade Entry View Privilege Enforcement ---")
    # T2 (Subject teacher for Physics only) tries to post grades for Physics (Allowed)
    post_data_phys = {
        'classroom': classroom_10a.id,
        'term': exam_term.id,
        'subject': phys_subj.id,
        f'score_{student_1.id}_{phys_subj.id}': '48.00'
    }
    req_phys = factory.post('/examinations/grades/entry/', post_data_phys)
    setup_request(req_phys, user_t2)
    res_phys = grade_entry_matrix(req_phys)
    assert res_phys.status_code == 302, f"Expected 302 redirect on success, got {res_phys.status_code}"
    # Check student_1 physics score updated
    g_phys = Grade.objects.get(exam_term=exam_term, subject=phys_subj, student=student_1)
    assert g_phys.score == Decimal("48.00"), f"Score should be 48.00, got {g_phys.score}"
    
    # T2 tries to post grades for Math (Forbidden/Blocked)
    post_data_math = {
        'classroom': classroom_10a.id,
        'term': exam_term.id,
        'subject': math_subj.id,
        f'score_{student_1.id}_{math_subj.id}': '10.00'
    }
    req_math = factory.post('/examinations/grades/entry/', post_data_math)
    setup_request(req_math, user_t2)
    res_math = grade_entry_matrix(req_math)
    # Check that Math score was NOT changed
    g1 = Grade.objects.get(exam_term=exam_term, subject=math_subj, student=student_1)
    assert g1.score == Decimal("85.00"), f"Math score should remain 85.00, but was changed to {g1.score}"
    print("✓ Test 3 Passed: Grade entry view prevents unauthorized subject grade manipulation.")

    print("\n--- TEST 4: Monthly Results Print View ---")
    # Homeroom teacher T1 accesses 10A monthly print
    req_print = factory.get(f'/examinations/results/monthly/print/?classroom={classroom_10a.id}&term={exam_term.id}')
    setup_request(req_print, user_t1)
    res_print = monthly_results_print_view(req_print)
    assert res_print.status_code == 200, f"Expected 200, got {res_print.status_code}"
    content_print = res_print.content.decode('utf-8')
    assert "តារាងលទ្ធផល" in content_print or "ចំណាត់ថ្នាក់" in content_print, "Header missing in print template"
    assert (classroom_10a.name in content_print or classroom_10a.code in content_print), "Classroom name missing in print template"
    print("✓ Test 4 Passed: Monthly results printout rendered successfully with code 200.")

    print("\n--- TEST 5: Homeroom Study Tracking Book View (Carnet de Notes) ---")
    req_carnet = factory.get(f'/examinations/homeroom/{classroom_10a.id}/tracking-book/?term={exam_term.id}')
    setup_request(req_carnet, user_t1)
    res_carnet = homeroom_study_tracking_book_view(req_carnet, classroom_id=classroom_10a.id)
    assert res_carnet.status_code == 200, f"Expected 200, got {res_carnet.status_code}"
    content_carnet = res_carnet.content.decode('utf-8')
    assert "សៀវភៅតាមដានការសិក្សា" in content_carnet, "Study tracking book title missing"
    assert student_1.khmer_name in content_carnet or student_1.user.get_full_name() in content_carnet, "Student 1 missing in carnet"
    print("✓ Test 5 Passed: Homeroom Study Tracking Book rendered successfully with code 200.")

    print("\n--- TEST 6: Monthly Attendance Roll Call Sheet (បញ្ជីហៅឈ្មោះ) ---")
    req_att = factory.get(f'/attendance/homeroom/{classroom_10a.id}/roster-print/?month=10&year=2025')
    setup_request(req_att, user_t1)
    res_att = homeroom_attendance_roster_view(req_att, classroom_id=classroom_10a.id)
    assert res_att.status_code == 200, f"Expected 200, got {res_att.status_code}"
    content_att = res_att.content.decode('utf-8')
    assert "បញ្ជីហៅឈ្មោះសិស្ស" in content_att, "Attendance roster title missing"
    assert (classroom_10a.name in content_att or classroom_10a.code in content_att), "Class 10A missing in attendance roster"
    print("✓ Test 6 Passed: Monthly Attendance Roll Call Sheet rendered successfully with code 200.")

    print("\n--- TEST 7: Slow Learners Report (បញ្ជីសិស្សរៀនយឺតតាមមុខវិជ្ជា) ---")
    # Filter for Math slow learners in 10A -> Student 2 scored 40/100 (40% < 50%), Student 1 scored 90/100 (pass)
    req_slow = factory.get(f'/examinations/reports/slow-learners/?classroom_id={classroom_10a.id}&subject_id={math_subj.id}&exam_term_id={exam_term.id}')
    setup_request(req_slow, user_t1)
    res_slow = slow_learners_report_view(req_slow)
    assert res_slow.status_code == 200, f"Expected 200, got {res_slow.status_code}"
    content_slow = res_slow.content.decode('utf-8')
    assert "បញ្ជីសិស្សរៀនយឺតតាមមុខវិជ្ជា" in content_slow, "Slow learners title missing"
    assert "STU1002" in content_slow, "Student 2 (Vibol) should be in slow learners for Math"
    assert "STU1001" not in content_slow, "Student 1 (Roth) scored 90% and should NOT be in slow learners for Math"
    print("✓ Test 7 Passed: Slow learners report correctly identifies deficit/failing scores (< 50%).")

    print("\n--- TEST 8: Cumulative Dossier Service & Single/Batch Views (សៀវភៅសិក្ខាគារិក) ---")
    dossier_data = get_student_cumulative_dossier_data(student_1)
    assert dossier_data['student'] == student_1, "Student mismatch in dossier data"
    assert len(dossier_data['grade_records']) == 6, f"Expected 6 grade levels (7 to 12), got {len(dossier_data['grade_records'])}"
    grade_10_entry = next((g for g in dossier_data['grade_records'] if g['grade_level'] == 10), None)
    assert grade_10_entry is not None, "Grade 10 entry should exist in dossier"
    assert grade_10_entry['is_current'] is True, "Grade 10 entry must be marked as current grade"
    print(f"Dossier compiled successfully. Current grade: {grade_10_entry['grade_label']} (active={grade_10_entry['is_current']})")
    
    # Single student dossier view
    req_dossier_single = factory.get(f'/examinations/students/{student_1.id}/cumulative-dossier/')
    setup_request(req_dossier_single, user_t1)
    res_dossier_single = student_cumulative_dossier_view(req_dossier_single, student_id=student_1.id)
    assert res_dossier_single.status_code == 200, f"Expected 200, got {res_dossier_single.status_code}"
    content_single = res_dossier_single.content.decode('utf-8')
    assert "សៀវភៅសិក្ខាគារិក" in content_single, "Dossier title missing in single view"
    
    # Batch homeroom dossier view
    req_dossier_batch = factory.get(f'/examinations/homeroom/{classroom_10a.id}/cumulative-dossier/')
    setup_request(req_dossier_batch, user_t1)
    res_dossier_batch = homeroom_cumulative_dossier_batch_view(req_dossier_batch, classroom_id=classroom_10a.id)
    assert res_dossier_batch.status_code == 200, f"Expected 200, got {res_dossier_batch.status_code}"
    content_batch = res_dossier_batch.content.decode('utf-8')
    assert "សៀវភៅសិក្ខាគារិក" in content_batch, "Dossier title missing in batch view"
    print("✓ Test 8 Passed: Cumulative dossier (Grades 7 to 12) rendered for single and batch prints.")

    print("\n--- TEST 9: Teacher Dashboard Integration ---")
    req_dash = factory.get('/dashboard/teacher/')
    setup_request(req_dash, user_t1)
    res_dash = teacher_dashboard(req_dash)
    assert res_dash.status_code == 200, f"Expected 200, got {res_dash.status_code}"
    content_dash = res_dash.content.decode('utf-8')
    assert ("មជ្ឈមណ្ឌលគ្រប់គ្រងថ្នាក់បន្ទុក" in content_dash or "Homeroom" in content_dash), "Homeroom Academic Hub missing in dashboard"
    assert ("សិស្សរៀនយឺត" in content_dash or "Slow Learners" in content_dash), "Slow learners quick link missing in dashboard"
    print("✓ Test 9 Passed: Teacher Dashboard correctly displays Homeroom Academic Hub and Teaching Classes.")

    print("\n=======================================================")
    print(" ALL 9 TESTS PASSED SUCCESSFULLY! EVERYTHING VERIFIED. ")
    print("=======================================================")

if __name__ == "__main__":
    run_tests()
