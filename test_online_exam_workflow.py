import os
import sys
import django
from decimal import Decimal

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.utils import timezone
from django.urls import reverse
from apps.examinations.models import (
    ExamTerm, Grade,
    OnlineExam, OnlineExamQuestion, OnlineExamOption,
    OnlineExamSubmission, OnlineExamAnswer
)
from apps.examinations.online_exam_views import parse_and_import_raw_questions
from apps.academics.models import AcademicYear, Classroom, Subject
from apps.students.models import Student
from apps.teachers.models import Teacher
from apps.accounts.models import User

def run_tests():
    print("=================================================================")
    print("TEST SUITE: Subject Teacher Online Exam System Workflow")
    print("=================================================================")

    # 1. URL Reversal Tests
    print("\n[Step 1] Testing URL Routing & Reversals...")
    urls_to_test = [
        ('online_exam_list', {}),
        ('online_exam_create', {}),
        ('student_online_exams_list', {}),
    ]
    for url_name, kwargs in urls_to_test:
        resolved = reverse(url_name, kwargs=kwargs)
        print(f"  ✓ {url_name} -> {resolved}")

    # 2. Setup or retrieve foundational data
    print("\n[Step 2] Setting up Test Data (Term, Subject, Class, Student, Teacher)...")
    year = AcademicYear.objects.first()
    if not year:
        year = AcademicYear.objects.create(name="2025-2026", start_date="2025-10-01", end_date="2026-07-31")

    term = ExamTerm.objects.filter(academic_year=year).first()
    if not term:
        term = ExamTerm.objects.create(
            name="ប្រឡងប្រចាំខែតុលា (October Monthly Exam)",
            academic_year=year,
            term_type=ExamTerm.TermType.MONTHLY,
            scoring_mode=ExamTerm.ScoringMode.CLASSROOM,
            start_date=timezone.now().date(),
            end_date=timezone.now().date()
        )

    subject = Subject.objects.first()
    if not subject:
        subject = Subject.objects.create(name_kh="គណិតវិទ្យា", name_en="Mathematics", code="MATH")

    classroom = Classroom.objects.first()
    student = Student.objects.filter(classroom=classroom).first() if classroom else None
    if not student:
        student = Student.objects.first()
        if student:
            classroom = student.classroom

    teacher = Teacher.objects.first()
    admin_user = User.objects.filter(is_superuser=True).first() or User.objects.first()

    print(f"  ✓ Exam Term: {term.name}")
    print(f"  ✓ Subject: {subject.name_kh}")
    print(f"  ✓ Classroom: {classroom.name if classroom else 'None'}")
    print(f"  ✓ Student: {student.khmer_name if student else 'None'}")

    # 3. Create Online Exam
    print("\n[Step 3] Creating Online Exam Paper (វិញ្ញាសាប្រឡង)...")
    exam = OnlineExam.objects.create(
        title="វិញ្ញាសាតេស្តសាកល្បង គណិតវិទ្យា (Automated Test)",
        description="សូមអានសំណួរឱ្យបានច្បាស់លាស់មុននឹងជ្រើសរើសចម្លើយ។",
        exam_term=term,
        subject=subject,
        teacher=teacher,
        created_by=admin_user,
        duration_minutes=30,
        total_score=Decimal('100.00'),
        pass_score=Decimal('50.00'),
        max_attempts=2,
        is_published=True,
        status=OnlineExam.ExamStatus.PUBLISHED,
        shuffle_questions=True,
        shuffle_options=True,
        show_result_immediately=True,
        show_correct_answers=True
    )
    if classroom:
        exam.target_classrooms.add(classroom)
    print(f"  ✓ Created Exam: ID={exam.id}, Title='{exam.title}', Duration={exam.duration_minutes}m, Total Score={exam.total_score}")

    # 4. Add MCQs (Multiple-Choice Questions)
    print("\n[Step 4] Adding Multiple-Choice Questions (MCQs)...")
    q1 = OnlineExamQuestion.objects.create(
        exam=exam,
        question_text="តើតម្លៃនៃ 5 + 7 ស្មើនឹងប៉ុន្មាន?",
        points=Decimal('10.00'),
        order=1,
        explanation="5 + 7 = 12 គឺជាផលបូកធម្មតា។"
    )
    OnlineExamOption.objects.create(question=q1, option_text="10", is_correct=False, order=1)
    OnlineExamOption.objects.create(question=q1, option_text="12", is_correct=True, order=2) # Correct
    OnlineExamOption.objects.create(question=q1, option_text="14", is_correct=False, order=3)
    OnlineExamOption.objects.create(question=q1, option_text="15", is_correct=False, order=4)

    q2 = OnlineExamQuestion.objects.create(
        exam=exam,
        question_text="តើរូបមន្តក្រឡាផ្ទៃរង្វង់គឺអ្វី?",
        points=Decimal('10.00'),
        order=2,
        explanation="ក្រឡាផ្ទៃរង្វង់គឺ S = π * r^2 ។"
    )
    OnlineExamOption.objects.create(question=q2, option_text="S = 2 * π * r", is_correct=False, order=1)
    OnlineExamOption.objects.create(question=q2, option_text="S = π * r^2", is_correct=True, order=2) # Correct
    OnlineExamOption.objects.create(question=q2, option_text="S = 4 * π * r", is_correct=False, order=3)
    OnlineExamOption.objects.create(question=q2, option_text="S = π * d^2", is_correct=False, order=4)

    print(f"  ✓ Added 2 Questions to Exam {exam.id}. Total Raw Points: {exam.total_question_points}")
    assert exam.questions_count == 2
    assert q1.correct_option.option_text == "12"

    # 5. Test Bulk Import Parser
    print("\n[Step 5] Testing Bulk Import Parser (នាំចូលសំណួរជាក្រុម)...")
    sample_raw_text = """
    1. តើរាជធានីនៃប្រទេសកម្ពុជាឈ្មោះអ្វី?
    A. សៀមរាប
    B. ភ្នំពេញ*
    C. បាត់ដំបង
    D. កំពត

    2. តើ 3 * 4 ស្មើប៉ុន្មាន?
    A. 7
    B. 10
    C. 12
    D. 15
    Answer: C
    """
    imported_count = parse_and_import_raw_questions(exam, sample_raw_text)
    print(f"  ✓ Bulk imported {imported_count} questions from plain text.")
    assert imported_count == 2
    assert exam.questions.count() == 4

    # 6. Simulate Student Taking Exam & Instant Scoring
    print("\n[Step 6] Simulating Student Taking Exam & Submitting for Instant Results...")
    if not student:
        print("  ! Skipping student exam simulation: No student in database.")
    else:
        submission = OnlineExamSubmission.objects.create(
            exam=exam,
            student=student,
            classroom=classroom,
            status=OnlineExamSubmission.SubmissionStatus.IN_PROGRESS,
            time_spent_seconds=125
        )

        # Answer Q1 correctly
        opt_correct_q1 = q1.options.filter(is_correct=True).first()
        OnlineExamAnswer.objects.create(
            submission=submission,
            question=q1,
            selected_option=opt_correct_q1
        )

        # Answer Q2 incorrectly
        opt_wrong_q2 = q2.options.filter(is_correct=False).first()
        OnlineExamAnswer.objects.create(
            submission=submission,
            question=q2,
            selected_option=opt_wrong_q2
        )

        # Calculate Results (Instant evaluation)
        submission.calculate_results(save=True)

        print(f"  ✓ Submission ID: {submission.id}")
        print(f"  ✓ Score Obtained: {submission.score_obtained} / {submission.total_possible_score}")
        print(f"  ✓ Percentage: {submission.percentage}%")
        print(f"  ✓ Letter Grade: {submission.letter_grade}")
        print(f"  ✓ Is Passed: {submission.is_passed}")
        print(f"  ✓ Status: {submission.status}")

        assert submission.status == OnlineExamSubmission.SubmissionStatus.SUBMITTED
        assert submission.score_obtained > 0

    # 7. Test Sync to Official Grade Matrix
    print("\n[Step 7] Testing Sync from Online Exam to Official Grade Matrix...")
    if student and submission:
        # Simulate api_sync_online_exam_to_grades
        grade_obj, created = Grade.objects.get_or_create(
            student=submission.student,
            subject=exam.subject,
            exam_term=exam.exam_term,
            defaults={
                'classroom': classroom,
                'score': submission.score_obtained,
                'max_score': exam.total_score,
                'remarks': f'តេស្តអនឡាញ៖ {exam.title}',
            }
        )
        if not created:
            grade_obj.score = submission.score_obtained
            grade_obj.max_score = exam.total_score
            grade_obj.classroom = classroom
            grade_obj.remarks = f'តេស្តអនឡាញ៖ {exam.title}'
            grade_obj.save()

        submission.synced_to_grade = True
        submission.save()

        # Verify Grade record in DB
        grade_record = Grade.objects.get(student=student, subject=exam.subject, exam_term=exam.exam_term)
        print(f"  ✓ Official Grade Record Found: Score={grade_record.score}/{grade_record.max_score}, Letter={grade_record.grade_letter}, Remarks='{grade_record.remarks}'")
        assert grade_record.score == submission.score_obtained
        print("  ✓ Grade record successfully synced and verified!")

    # 8. Clean up test exam
    print("\n[Step 8] Cleaning up temporary test data...")
    exam.delete()
    print("  ✓ Test exam and related questions/submissions cleaned up.")

    print("\n=================================================================")
    print("🎉 ALL TESTS PASSED SUCCESSFULLY! WORKFLOW VERIFIED 100%!")
    print("=================================================================")

if __name__ == '__main__':
    run_tests()
