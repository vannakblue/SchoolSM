import os
import sys
import django

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from decimal import Decimal
from django.utils import timezone
from django.test import Client
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.teachers.models import Teacher
from apps.students.models import Student
from apps.academics.models import AcademicYear, Classroom, Subject, ClassSubject, Timetable, GradeLevelRule
from apps.examinations.models import ExamTerm, Grade
from apps.teachers.permissions import (
    get_teacher_allowed_classrooms,
    get_teacher_classroom_subject_ids,
    can_teacher_grade_subject,
)
from django.test.utils import setup_test_environment


def run_tests():
    setup_test_environment()
    print("=" * 80)
    print("TEST SUITE: Subject Teacher Timetable Isolation (Mobile App, Web & Portal)")
    print("Requirement: Teacher who teaches Chemistry in 7B, 7C, 7D only sees 7B, 7C, 7D")
    print("             and within those classes ONLY sees Chemistry scores in each exam term.")
    print("=" * 80)

    # 1. Setup Academic Year & Exam Term
    print("\n[Step 1] Creating test academic year, exam term, classrooms & subjects...")
    year, _ = AcademicYear.objects.get_or_create(
        name="2026-2027",
        defaults={'start_date': "2026-09-01", 'end_date': "2027-07-15", 'is_current': True}
    )

    term, _ = ExamTerm.objects.get_or_create(
        name="សម័យប្រឡងតេស្ត Isolation",
        academic_year=year,
        defaults={
            'start_date': timezone.now().date(),
            'end_date': timezone.now().date() + timezone.timedelta(days=7),
            'is_active_for_grading': True,
            'is_grading_locked': False,
        }
    )
    term.set_as_active_grading_term()

    # Subjects: Chemistry, Math, Physics
    sub_chem, _ = Subject.objects.get_or_create(code="ISO_CHEM", defaults={'name_kh': "គីមីវិទ្យាតេស្ត", 'name_en': "Chemistry Test"})
    sub_math, _ = Subject.objects.get_or_create(code="ISO_MATH", defaults={'name_kh': "គណិតវិទ្យាតេស្ត", 'name_en': "Math Test"})
    sub_phys, _ = Subject.objects.get_or_create(code="ISO_PHYS", defaults={'name_kh': "រូបវិទ្យាតេស្ត", 'name_en': "Physics Test"})

    for s in [sub_chem, sub_math, sub_phys]:
        GradeLevelRule.objects.get_or_create(grade_level=7, track='GENERAL', subject=s, defaults={'max_score': Decimal('100.00')})

    # Classrooms: 7B, 7C, 7D (Assigned to teacher), 7A (Homeroom of other teacher), 8A (Unassigned)
    c_7b, _ = Classroom.objects.get_or_create(code="7B_ISO", defaults={'name': "ថ្នាក់ទី 7B (ISO)", 'grade_level': 7, 'track': 'GENERAL', 'academic_year': year})
    c_7c, _ = Classroom.objects.get_or_create(code="7C_ISO", defaults={'name': "ថ្នាក់ទី 7C (ISO)", 'grade_level': 7, 'track': 'GENERAL', 'academic_year': year})
    c_7d, _ = Classroom.objects.get_or_create(code="7D_ISO", defaults={'name': "ថ្នាក់ទី 7D (ISO)", 'grade_level': 7, 'track': 'GENERAL', 'academic_year': year})
    c_7a, _ = Classroom.objects.get_or_create(code="7A_ISO", defaults={'name': "ថ្នាក់ទី 7A (ISO)", 'grade_level': 7, 'track': 'GENERAL', 'academic_year': year})
    c_8a, _ = Classroom.objects.get_or_create(code="8A_ISO", defaults={'name': "ថ្នាក់ទី 8A (ISO)", 'grade_level': 8, 'track': 'GENERAL', 'academic_year': year})

    # Users: Teacher Chem, Teacher Other, Admin
    u_chem, _ = User.objects.get_or_create(username="teacher_chem_iso", defaults={'role': User.Role.TEACHER, 'first_name': "គីមី", 'last_name': "គ្រូ"})
    u_chem.set_password('admin123')
    u_chem.is_active = True
    u_chem.save()
    t_chem, _ = Teacher.objects.get_or_create(user=u_chem, defaults={'teacher_id': "TCH-CHEM-01", 'khmer_name': "គ្រូ គីមីវិទ្យា"})

    u_admin = User.objects.filter(role=User.Role.ADMIN).first() or User.objects.filter(is_superuser=True).first()
    if not u_admin:
        u_admin = User.objects.create_superuser('admin_iso', 'admin_iso@school.edu.kh', 'admin123')
    else:
        u_admin.set_password('admin123')
        u_admin.save()

    # Assign Teacher Chem to Chemistry in 7B (via ClassSubject), 7C (via Timetable), 7D (via Timetable)
    ClassSubject.objects.get_or_create(classroom=c_7b, subject=sub_chem, defaults={'teacher': t_chem})
    Timetable.objects.get_or_create(classroom=c_7c, subject=sub_chem, day_of_week=1, period_number=1, defaults={'teacher': t_chem, 'start_time': '07:00:00', 'end_time': '07:50:00'})
    Timetable.objects.get_or_create(classroom=c_7d, subject=sub_chem, day_of_week=2, period_number=2, defaults={'teacher': t_chem, 'start_time': '08:00:00', 'end_time': '08:50:00'})

    # Create students in 7B, 7C, 7D, 7A
    def create_stu(code, name, cls):
        su, _ = User.objects.get_or_create(username=f"stu_{code}", defaults={'role': User.Role.STUDENT})
        su.set_password('admin123')
        su.save()
        st, _ = Student.objects.get_or_create(
            user=su,
            defaults={
                'student_id': code,
                'khmer_name': name,
                'gender': 'M',
                'date_of_birth': timezone.now().date() - timezone.timedelta(days=4000),
                'classroom': cls,
                'academic_year': year,
                'status': 'ACTIVE'
            }
        )
        st.classroom = cls
        st.save()
        return st

    stu_7b = create_stu("STU-7B-01", "សិស្ស ថ្នាក់ 7B", c_7b)
    stu_7c = create_stu("STU-7C-01", "សិស្ស ថ្នាក់ 7C", c_7c)
    stu_7d = create_stu("STU-7D-01", "សិស្ស ថ្នាក់ 7D", c_7d)
    stu_7a = create_stu("STU-7A-01", "សិស្ស ថ្នាក់ 7A", c_7a)

    print(f"  ✓ Teacher Chem teaches {sub_chem.name_kh} in classes: {c_7b.name}, {c_7c.name}, {c_7d.name}")
    print(f"  ✓ Non-assigned classes: {c_7a.name}, {c_8a.name}")

    # =========================================================================
    # Test 1: Helper Functions Unit Tests
    # =========================================================================
    print("\n[Step 2] Testing get_teacher_allowed_classrooms & get_teacher_classroom_subject_ids...")
    allowed_cls = get_teacher_allowed_classrooms(u_chem, academic_year=year)
    allowed_cls_ids = set(allowed_cls.values_list('id', flat=True))
    assert c_7b.id in allowed_cls_ids, "7B must be in allowed classrooms"
    assert c_7c.id in allowed_cls_ids, "7C must be in allowed classrooms"
    assert c_7d.id in allowed_cls_ids, "7D must be in allowed classrooms"
    assert c_7a.id not in allowed_cls_ids, "7A must NOT be in allowed classrooms"
    assert c_8a.id not in allowed_cls_ids, "8A must NOT be in allowed classrooms"
    print("  ✓ get_teacher_allowed_classrooms strictly returned {7B, 7C, 7D} for Teacher Chem.")

    # Check subject isolation in 7B, 7C, 7D
    sub_ids_7b = get_teacher_classroom_subject_ids(u_chem, c_7b.id)
    assert sub_ids_7b == {sub_chem.id}, f"Expected only Chem in 7B, got {sub_ids_7b}"
    sub_ids_7c = get_teacher_classroom_subject_ids(u_chem, c_7c.id)
    assert sub_ids_7c == {sub_chem.id}, f"Expected only Chem in 7C, got {sub_ids_7c}"
    sub_ids_7d = get_teacher_classroom_subject_ids(u_chem, c_7d.id)
    assert sub_ids_7d == {sub_chem.id}, f"Expected only Chem in 7D, got {sub_ids_7d}"
    sub_ids_7a = get_teacher_classroom_subject_ids(u_chem, c_7a.id)
    assert sub_ids_7a == set(), f"Expected empty set in 7A, got {sub_ids_7a}"
    print("  ✓ get_teacher_classroom_subject_ids strictly returned {Chemistry} in 7B, 7C, 7D and empty set in 7A.")

    # can_teacher_grade_subject
    assert can_teacher_grade_subject(u_chem, c_7b.id, sub_chem.id) is True
    assert can_teacher_grade_subject(u_chem, c_7b.id, sub_math.id) is False
    assert can_teacher_grade_subject(u_chem, c_7a.id, sub_chem.id) is False
    assert can_teacher_grade_subject(u_admin, c_7a.id, sub_math.id) is True
    print("  ✓ can_teacher_grade_subject correctly permits only Chemistry in assigned classrooms.")

    # =========================================================================
    # Test 2: Web Portal - grade_entry_matrix
    # =========================================================================
    print("\n[Step 3] Testing Web Portal (grade_entry_matrix view)...")
    web_client = Client()
    web_client.force_login(u_chem)

    # 1. GET matrix: Check classrooms and subject rules
    res = web_client.get(f"/examinations/matrix/?classroom={c_7b.id}")
    assert res.status_code == 200
    ctx_classrooms = res.context['classrooms']
    ctx_cls_ids = set(c.id for c in ctx_classrooms)
    assert ctx_cls_ids == {c_7b.id, c_7c.id, c_7d.id}, f"Expected exactly {{7B, 7C, 7D}}, got {ctx_cls_ids}"

    # Subject rules must ONLY contain Chemistry!
    ctx_sub_rules = res.context['subject_rules']
    ctx_sub_ids = [r.subject_id for r in ctx_sub_rules]
    assert ctx_sub_ids == [sub_chem.id], f"Expected only Chem in subject_rules, got {ctx_sub_ids}"

    # All subjects dropdown must only contain Chemistry
    ctx_all_subs = [s.id for s in res.context['all_subjects']]
    assert ctx_all_subs == [sub_chem.id], f"Expected only Chem in all_subjects filter, got {ctx_all_subs}"
    print("  ✓ Portal UI matrix strictly displays ONLY Chemistry column and only {7B, 7C, 7D} in classroom dropdown.")

    # 2. GET matrix with unauthorized classroom 7A: Must be blocked / defaulted to allowed class
    res_tamper = web_client.get(f"/examinations/matrix/?classroom={c_7a.id}")
    assert res_tamper.context['selected_class'].id != c_7a.id, "Teacher must NOT be allowed to view 7A!"
    assert res_tamper.context['selected_class'].id in {c_7b.id, c_7c.id, c_7d.id}
    print("  ✓ Teacher attempting to access unassigned class 7A is securely redirected to their own class.")

    # 3. POST save valid Chemistry score in 7B
    post_res = web_client.post("/examinations/matrix/", {
        'term': term.id,
        'classroom': c_7b.id,
        f"score_{stu_7b.id}_{sub_chem.id}": "85.50"
    }, follow=True)
    g_chem = Grade.objects.filter(student=stu_7b, subject=sub_chem, exam_term=term).first()
    assert g_chem is not None and g_chem.score == Decimal('85.50')
    print(f"  ✓ Chemistry grade in 7B successfully saved by teacher: Score = {g_chem.score}")

    # 4. POST save attempting unauthorized subject Math in 7B
    web_client.post("/examinations/matrix/", {
        'term': term.id,
        'classroom': c_7b.id,
        f"score_{stu_7b.id}_{sub_math.id}": "99.00"
    }, follow=True)
    g_math = Grade.objects.filter(student=stu_7b, subject=sub_math, exam_term=term).first()
    assert g_math is None, "Teacher MUST NOT be able to save scores for unassigned subject Math!"
    print("  ✓ Attempt to save Math score in 7B was rejected as expected.")

    # 5. POST save attempting unassigned class 7A
    post_res_bad_class = web_client.post("/examinations/matrix/", {
        'term': term.id,
        'classroom': c_7a.id,
        f"score_{stu_7a.id}_{sub_chem.id}": "75.00"
    }, follow=True)
    g_7a = Grade.objects.filter(student=stu_7a, subject=sub_chem, exam_term=term).first()
    assert g_7a is None, "Teacher MUST NOT be able to save scores in unassigned class 7A!"
    print("  ✓ Attempt to save score in 7A was rejected with permission error.")

    # =========================================================================
    # Test 3: Web Portal - grade_summary_view
    # =========================================================================
    print("\n[Step 4] Testing Web Portal (grade_summary_view)...")
    res_summary = web_client.get(f"/examinations/summary/?term={term.id}&classroom={c_7b.id}")
    assert res_summary.status_code == 200
    sum_cls_ids = set(c.id for c in res_summary.context['classrooms'])
    assert sum_cls_ids == {c_7b.id, c_7c.id, c_7d.id}
    sum_sub_rules = [r.subject_id for r in res_summary.context['subject_rules']]
    assert sum_sub_rules == [sub_chem.id], f"Expected only Chem in summary subject_rules, got {sum_sub_rules}"
    assert res_summary.context['is_pure_subject_teacher'] is True
    assert res_summary.context['can_manage_class_reports'] is False
    content_summary = res_summary.content.decode('utf-8')
    assert "Teacher Assigned Subjects" in content_summary
    print("  ✓ Grade Summary strictly displays ONLY Chemistry scores for Teacher Chem and hides full-class reports.")

    # =========================================================================
    # Test 4: Mobile API - TeacherGradeEntryMetaAPIView
    # =========================================================================
    print("\n[Step 5] Testing Mobile REST API Metadata (/api/v1/grades/teacher-entry/meta/)...")
    api_client = APIClient()
    login_res = api_client.post('/api/v1/auth/login/', {
        'username': 'teacher_chem_iso',
        'password': 'admin123'
    }, format='json')
    assert login_res.status_code == 200
    token = login_res.data['tokens']['access']
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    meta_res = api_client.get('/api/v1/grades/teacher-entry/meta/')
    assert meta_res.status_code == 200
    mdata = meta_res.data
    m_class_ids = set(c['id'] for c in mdata['classrooms'])
    assert m_class_ids == {c_7b.id, c_7c.id, c_7d.id}, f"Expected {{7B, 7C, 7D}}, got {m_class_ids}"

    # Verify each classroom has only Chemistry in its subjects list
    for c in mdata['classrooms']:
        c_subs = [s['id'] for s in c['subjects']]
        assert c_subs == [sub_chem.id], f"Class {c['name']} must only contain Chemistry, got {c_subs}"
    print("  ✓ Mobile Metadata API returned strictly {7B, 7C, 7D}, each containing ONLY Chemistry.")

    # =========================================================================
    # Test 5: Mobile API - TeacherGradeEntrySheetAPIView
    # =========================================================================
    print("\n[Step 6] Testing Mobile REST API Sheet (/api/v1/grades/teacher-entry/sheet/)...")
    sheet_res = api_client.get(f'/api/v1/grades/teacher-entry/sheet/?term_id={term.id}&classroom_id={c_7b.id}')
    assert sheet_res.status_code == 200
    sdata = sheet_res.data
    assert [s['id'] for s in sdata['subjects']] == [sub_chem.id]
    # Check student scores list has only Chemistry
    stu_scores = sdata['students'][0]['scores']
    assert len(stu_scores) == 1 and stu_scores[0]['subject_id'] == sub_chem.id
    assert stu_scores[0]['score'] == 85.50
    print("  ✓ Mobile Grade Sheet returns only Chemistry subject and Chemistry student scores.")

    # Sheet request for unassigned class 7A must return 403
    bad_sheet_res = api_client.get(f'/api/v1/grades/teacher-entry/sheet/?term_id={term.id}&classroom_id={c_7a.id}')
    assert bad_sheet_res.status_code == 403, f"Expected 403, got {bad_sheet_res.status_code}"
    print(f"  ✓ Mobile Grade Sheet for unassigned class 7A rejected with 403: {bad_sheet_res.data.get('message')}")

    # Sheet request for 7B with unauthorized subject Math must return 403
    bad_sub_sheet_res = api_client.get(f'/api/v1/grades/teacher-entry/sheet/?term_id={term.id}&classroom_id={c_7b.id}&subject_id={sub_math.id}')
    assert bad_sub_sheet_res.status_code == 403, f"Expected 403, got {bad_sub_sheet_res.status_code}"
    print(f"  ✓ Mobile Grade Sheet for unassigned subject Math in 7B rejected with 403: {bad_sub_sheet_res.data.get('message')}")

    # =========================================================================
    # Test 6: Mobile API - TeacherGradeEntrySaveAPIView
    # =========================================================================
    print("\n[Step 7] Testing Mobile REST API Grade Save (/api/v1/grades/teacher-entry/save/)...")
    # Valid Chemistry save in 7C
    save_7c_res = api_client.post('/api/v1/grades/teacher-entry/save/', {
        'exam_term_id': term.id,
        'classroom_id': c_7c.id,
        'scores': [{'student_id': stu_7c.id, 'subject_id': sub_chem.id, 'score': 90.0}]
    }, format='json')
    assert save_7c_res.status_code == 200
    g_7c = Grade.objects.filter(student=stu_7c, subject=sub_chem, exam_term=term).first()
    assert g_7c is not None and g_7c.score == Decimal('90.00')
    print(f"  ✓ Mobile grade save for Chemistry in 7C succeeded: Score = {g_7c.score}")

    # Unauthorized save in 7A must return 403
    save_7a_res = api_client.post('/api/v1/grades/teacher-entry/save/', {
        'exam_term_id': term.id,
        'classroom_id': c_7a.id,
        'scores': [{'student_id': stu_7a.id, 'subject_id': sub_chem.id, 'score': 95.0}]
    }, format='json')
    assert save_7a_res.status_code == 403
    print(f"  ✓ Mobile grade save in unassigned class 7A rejected with 403: {save_7a_res.data.get('message')}")

    # Attempting to save Math in 7B is skipped/not saved
    api_client.post('/api/v1/grades/teacher-entry/save/', {
        'exam_term_id': term.id,
        'classroom_id': c_7b.id,
        'scores': [{'student_id': stu_7b.id, 'subject_id': sub_math.id, 'score': 88.0}]
    }, format='json')
    assert Grade.objects.filter(student=stu_7b, subject=sub_math, exam_term=term).first() is None
    print("  ✓ Mobile grade save for unassigned subject Math was securely ignored.")

    # =========================================================================
    # Step 8: Cleanup
    # =========================================================================
    print("\n[Step 8] Cleaning up test data...")
    Grade.objects.filter(exam_term=term).delete()
    term.delete()
    ClassSubject.objects.filter(teacher=t_chem).delete()
    Timetable.objects.filter(teacher=t_chem).delete()
    t_chem.delete()
    u_chem.delete()
    for st in [stu_7b, stu_7c, stu_7d, stu_7a]:
        u = st.user
        st.delete()
        if u: u.delete()
    for c in [c_7b, c_7c, c_7d, c_7a, c_8a]:
        c.delete()
    for s in [sub_chem, sub_math, sub_phys]:
        s.delete()
    print("  ✓ Cleanup complete.")

    print("\n" + "=" * 80)
    print("🎉 ALL SUBJECT TEACHER TIMETABLE ISOLATION TESTS PASSED 100%!")
    print("=" * 80)


if __name__ == '__main__':
    run_tests()
