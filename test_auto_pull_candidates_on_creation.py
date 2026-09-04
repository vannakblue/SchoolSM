import os
import sys
import django
from datetime import date

sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.examinations.models import StandardizedExam, ExamCandidate, ExamRoom, CandidateSubjectScore
from apps.academics.models import AcademicYear, Classroom
from apps.students.models import Student
from apps.academics.utils import get_active_academic_year

def run_tests():
    print("=" * 80)
    print("TEST: AUTO-PULL CANDIDATES BY GRADE LEVEL ON EXAM CREATION & SESSION BATCH PULL")
    print("=" * 80)

    admin_user = User.objects.filter(role='ADMIN').first()
    assert admin_user is not None, "Admin user must exist"

    active_year = get_active_academic_year()
    if not active_year:
        active_year = AcademicYear.objects.first()

    # Ensure we have a test classroom and students in Grade 11
    cr11 = Classroom.objects.filter(academic_year=active_year, grade_level=11).first()
    if not cr11:
        cr11 = Classroom.objects.create(
            name="11A-Test",
            code="11A-T",
            academic_year=active_year,
            grade_level=11
        )

    Student.objects.filter(student_id__in=["STU-TEST-001", "STU-TEST-002"]).delete()

    # Ensure at least 2 active students in this classroom
    s1 = Student.objects.filter(classroom=cr11, status='ACTIVE').first()
    if not s1:
        s1 = Student.objects.create(
            student_id="STU-TEST-001",
            khmer_name="សុខ ចាន់ដារា",
            latin_name="Sok Chandara",
            gender="M",
            date_of_birth=date(2008, 1, 15),
            status="ACTIVE",
            classroom=cr11
        )
    s2 = Student.objects.filter(classroom=cr11, status='ACTIVE').exclude(id=s1.id).first()
    if not s2:
        s2 = Student.objects.create(
            student_id="STU-TEST-002",
            khmer_name="មាស ស្រីលក្ខណ៍",
            latin_name="Meas Sreyleak",
            gender="F",
            date_of_birth=date(2008, 5, 20),
            status="ACTIVE",
            classroom=cr11
        )

    active_count = Student.objects.filter(classroom=cr11, status='ACTIVE', is_exam_suspended=False).count()
    print(f"✅ Found {active_count} active students in Grade 11 ({cr11.name})")

    client = Client()
    client.force_login(admin_user)

    # 1. Clean up any previous test exam
    StandardizedExam.objects.filter(name__icontains="Auto Pull Test").delete()

    # 2. Test Exam Creation with Auto-Pull Enabled (Default)
    print("\n--- 1. Testing Standardized Exam Creation with Default Auto-Pull ---")
    res_create = client.post('/examinations/standardized/create/', {
        'name': 'សម័យប្រឡង Auto Pull Test',
        'academic_year': active_year.id,
        'selected_grades': ['11'],
        'exam_date': date.today().strftime('%Y-%m-%d'),
        'candidates_per_room': 25,
        'auto_pull_candidates': 'on'
    }, follow=True)
    assert res_create.status_code == 200, f"Expected 200, got {res_create.status_code}"

    created_exam = StandardizedExam.objects.filter(name__icontains="Auto Pull Test", grade_level=11).first()
    assert created_exam is not None, "Exam must be created"
    
    cand_count = created_exam.candidates.count()
    print(f"✅ Exam created: ID={created_exam.id}, Name={created_exam.name}")
    print(f"✅ Auto-pulled candidates count = {cand_count} (Expected >= {active_count})")
    assert cand_count >= active_count, f"Candidates count {cand_count} should be >= {active_count}"

    # Verify CandidateSubjectScore rows created for subjects
    subject_count = created_exam.exam_subjects.count()
    total_scores_rows = CandidateSubjectScore.objects.filter(candidate__exam=created_exam).count()
    print(f"✅ Exam has {subject_count} subjects. Total candidate score rows = {total_scores_rows}")
    if subject_count > 0 and cand_count > 0:
        assert total_scores_rows == subject_count * cand_count, f"Expected {subject_count * cand_count} score rows, got {total_scores_rows}"

    # 3. Test Session Batch Candidate Pull for an Exam that has 0 candidates
    print("\n--- 2. Testing 1-Click Session Batch Candidate Pull ---")
    # Clear candidates from this exam
    created_exam.candidates.all().delete()
    assert created_exam.candidates.count() == 0, "Candidates cleared"

    res_batch_pull = client.post('/examinations/standardized/session/pull-candidates/', {
        'exam_ids': str(created_exam.id),
        'session_title': 'Auto Pull Test'
    }, follow=True)
    assert res_batch_pull.status_code == 200

    re_pulled_count = created_exam.candidates.count()
    print(f"✅ After 1-click batch pull: candidate count = {re_pulled_count}")
    assert re_pulled_count >= active_count, f"Expected re-pulled >= {active_count}, got {re_pulled_count}"

    # 4. Test exam_list HTML rendering contains batch pull button
    res_list = client.get('/examinations/standardized/')
    html = res_list.content.decode('utf-8')
    assert '/examinations/standardized/session/pull-candidates/' in html, "Batch pull candidates URL must be in exam_list.html"
    assert 'ទាញឈ្មោះសិស្ស' in html, "Batch pull button text must be in exam_list.html"
    print("✅ Verified UI rendering: 1-Click Batch Pull Candidates button is present in standardized_exam_list")

    # Clean up test exam
    created_exam.delete()
    print("✅ Test exam cleaned up.")

    print("\n" + "=" * 80)
    print("ALL AUTO-PULL TESTS PASSED SUCCESSFULLY! 🎉")
    print("=" * 80)

if __name__ == '__main__':
    run_tests()
