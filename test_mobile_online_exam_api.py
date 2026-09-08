import os
import sys
import django
from decimal import Decimal

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.students.models import Student
from apps.teachers.models import Teacher
from apps.academics.models import Classroom, Subject, AcademicYear, GradeLevelRule
from apps.examinations.models import (
    ExamTerm, Grade, OnlineExam, OnlineExamQuestion, OnlineExamOption,
    OnlineExamSubmission, OnlineExamAnswer
)

def run_tests():
    print("=" * 65)
    print("TEST SUITE: Mobile Online Examination REST API Workflow")
    print("=" * 65)

    client = APIClient()

    # 1. Setup / Lookup Test Entities
    print("\n[Step 1] Preparing Test Environment & Data...")
    active_year = AcademicYear.objects.filter(is_current=True).first() or AcademicYear.objects.first()
    if not active_year:
        active_year = AcademicYear.objects.create(name="2026-2027", start_date="2026-10-01", end_date="2027-07-31", is_current=True)

    classroom = Classroom.objects.filter(academic_year=active_year).first()
    if not classroom:
        classroom = Classroom.objects.create(name="ថ្នាក់ទី ៨B", academic_year=active_year, grade_level=8, capacity=40)

    subject = Subject.objects.first()
    if not subject:
        subject = Subject.objects.create(name_kh="ភាសាខ្មែរ", name_en="Khmer", code="KHM")

    term = ExamTerm.objects.filter(academic_year=active_year).first()
    if not term:
        term = ExamTerm.objects.create(
            name="សម័យប្រឡងតេស្ត Mobile",
            academic_year=active_year,
            term_type='MONTHLY',
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timezone.timedelta(days=7),
        )

    # Student User
    student_user, _ = User.objects.get_or_create(
        username="student_mobile_test",
        defaults={
            'email': "stu_mobile@school.edu.kh",
            'first_name': "តេស្ត",
            'last_name': "សិស្សម៉ូបាល",
            'role': User.Role.STUDENT,
        }
    )
    student_user.set_password("admin123")
    student_user.save()

    student_obj, _ = Student.objects.get_or_create(
        user=student_user,
        defaults={
            'student_id': "STU-MOB-001",
            'khmer_name': "សិស្សម៉ូបាល តេស្ត",
            'latin_name': "Student Mobile Test",
            'gender': "M",
            'date_of_birth': timezone.now().date() - timezone.timedelta(days=5000),
            'classroom': classroom,
            'academic_year': active_year,
            'status': "ACTIVE",
        }
    )
    student_obj.classroom = classroom
    student_obj.save()

    # Teacher User
    teacher_user, _ = User.objects.get_or_create(
        username="teacher_mobile_test",
        defaults={
            'email': "tch_mobile@school.edu.kh",
            'first_name': "វណ្ណា",
            'last_name': "គ្រូ",
            'role': User.Role.TEACHER,
        }
    )
    teacher_user.set_password("admin123")
    teacher_user.save()

    teacher_obj, _ = Teacher.objects.get_or_create(
        user=teacher_user,
        defaults={
            'teacher_id': "TCH-MOB-001",
            'khmer_name': "គ្រូ វណ្ណា ម៉ូបាល",
            'gender': "M",
        }
    )

    print(f"  ✓ Student: {student_obj.khmer_name} (Class: {classroom.name})")
    print(f"  ✓ Teacher: {teacher_obj.khmer_name}")
    print(f"  ✓ Subject: {subject.name_kh}")

    # 2. Create Online Exam with Questions
    print("\n[Step 2] Creating Online Exam with 3 MCQs...")
    exam = OnlineExam.objects.create(
        title="វិញ្ញាសាតេស្តភាសាខ្មែរតាមទូរស័ព្ទ (Mobile Exam)",
        description="សូមជ្រើសរើសចម្លើយត្រឹមត្រូវតែមួយគត់។",
        exam_term=term,
        subject=subject,
        teacher=teacher_obj,
        created_by=teacher_user,
        grade_level=8,
        duration_minutes=20,
        total_score=Decimal('100.00'),
        pass_score=Decimal('50.00'),
        max_attempts=2,
        is_published=True,
        status=OnlineExam.ExamStatus.PUBLISHED,
        access_code="1234",
    )
    exam.target_classrooms.add(classroom)

    # Q1: 50 points
    q1 = OnlineExamQuestion.objects.create(
        exam=exam,
        question_text="តើពាក្យ «កុសល» មានន័យដូចម្តេច?",
        points=Decimal('50.00'),
        order=1,
        explanation="កុសល មានន័យថា អំពើល្អ អំពើបុណ្យ។"
    )
    opt1_1 = OnlineExamOption.objects.create(question=q1, option_text="អំពើល្អ ឬបុណ្យ", is_correct=True, order=1)
    opt1_2 = OnlineExamOption.objects.create(question=q1, option_text="អំពើអាក្រក់ ឬបាប", is_correct=False, order=2)
    opt1_3 = OnlineExamOption.objects.create(question=q1, option_text="សេចក្តីទុក្ខ", is_correct=False, order=3)

    # Q2: 50 points
    q2 = OnlineExamQuestion.objects.create(
        exam=exam,
        question_text="តើព្យញ្ជនៈខ្មែរមានចំនួនប៉ុន្មានតួ?",
        points=Decimal('50.00'),
        order=2,
        explanation="ព្យញ្ជនៈខ្មែរមានចំនួន ៣៣ តួ ចែកជាពួក អ និងពួក អ៊។"
    )
    opt2_1 = OnlineExamOption.objects.create(question=q2, option_text="៣១ តួ", is_correct=False, order=1)
    opt2_2 = OnlineExamOption.objects.create(question=q2, option_text="៣៣ តួ", is_correct=True, order=2)
    opt2_3 = OnlineExamOption.objects.create(question=q2, option_text="៣៥ តួ", is_correct=False, order=3)

    print(f"  ✓ Created Exam ID={exam.id}, Title='{exam.title}', PIN='{exam.access_code}'")
    print(f"  ✓ Total Questions: {exam.questions.count()}, Total Points: {q1.points + q2.points}")

    # 3. Authenticate Student & Get JWT Token
    print("\n[Step 3] Testing Student Login via Mobile API...")
    login_res = client.post('/api/v1/auth/login/', {
        'username': 'student_mobile_test',
        'password': 'admin123'
    }, format='json')
    assert login_res.status_code == 200, f"Login failed: {login_res.data}"
    token = login_res.data['tokens']['access']
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    print(f"  ✓ Login Successful! Bearer Token acquired: {token[:20]}...")

    # 4. Test MobileOnlineExamListView
    print("\n[Step 4] Testing GET /api/v1/online-exams/ (List for Student)...")
    list_res = client.get('/api/v1/online-exams/')
    assert list_res.status_code == 200, f"List failed: {list_res.data}"
    data = list_res.data
    assert data['status'] == 'success'
    assert len(data['exams']) >= 1
    target_exam = next((e for e in data['exams'] if e['id'] == exam.id), None)
    assert target_exam is not None, "Created exam not found in student's list!"
    assert target_exam['can_take'] is True
    assert target_exam['requires_access_code'] is True
    assert target_exam['duration_minutes'] == 20
    assert target_exam['questions_count'] == 2
    print(f"  ✓ Exam found in student list: {target_exam['title']}")
    print(f"  ✓ Can Take: {target_exam['can_take']}, Requires PIN: {target_exam['requires_access_code']}")

    # 5. Test Start Exam with Invalid PIN
    print("\n[Step 5] Testing Start Exam with Invalid PIN...")
    bad_pin_res = client.post(f'/api/v1/online-exams/{exam.id}/take/', {'access_code': '9999'}, format='json')
    assert bad_pin_res.status_code == 403, "Should fail with invalid PIN!"
    print(f"  ✓ Correctly rejected with 403: {bad_pin_res.data.get('message')}")

    # 6. Test Start Exam with Valid PIN & Fetch Questions
    print("\n[Step 6] Testing Start Exam with Correct PIN & Fetching Questions...")
    start_res = client.post(f'/api/v1/online-exams/{exam.id}/take/', {'access_code': '1234'}, format='json')
    assert start_res.status_code == 200, f"Start failed: {start_res.data}"
    start_data = start_res.data
    assert start_data['status'] == 'success'
    sub_id = start_data['submission_id']
    questions = start_data['questions']
    assert len(questions) == 2
    assert start_data['remaining_seconds'] > 0

    # CRITICAL SECURITY CHECK: is_correct must NOT be in options!
    for q in questions:
        for opt in q['options']:
            assert 'is_correct' not in opt, f"SECURITY LEAK: 'is_correct' found in option {opt}!"
    print(f"  ✓ Exam Session Started: Submission ID = {sub_id}")
    print(f"  ✓ Remaining Seconds: {start_data['remaining_seconds']}s")
    print(f"  ✓ Security Verified: 'is_correct' is strictly hidden from API payload.")

    # 7. Test Submit Answers (Answer Q1 correctly, Q2 incorrectly -> 50%)
    print("\n[Step 7] Testing POST /api/v1/online-exams/<id>/submit/...")
    submit_payload = {
        'submission_id': sub_id,
        'time_spent_seconds': 145,
        'answers': {
            str(q1.id): opt1_1.id,  # Correct (50 pts)
            str(q2.id): opt2_1.id,  # Incorrect (0 pts)
        }
    }
    submit_res = client.post(f'/api/v1/online-exams/{exam.id}/submit/', submit_payload, format='json')
    assert submit_res.status_code == 200, f"Submit failed: {submit_res.data}"
    res_data = submit_res.data
    assert res_data['status'] == 'success'
    assert res_data['score_obtained'] == 50.0
    assert res_data['total_possible_score'] == 100.0
    assert res_data['percentage'] == 50.0
    assert res_data['letter_grade'] == 'E'
    assert res_data['is_passed'] is True
    assert res_data['time_spent_seconds'] == 145
    print(f"  ✓ Score Calculated Instantly: {res_data['score_obtained']}/{res_data['total_possible_score']} ({res_data['percentage']}%)")
    print(f"  ✓ Letter Grade: {res_data['letter_grade']}, Mention: {res_data['mention_khmer']}")
    print(f"  ✓ Passed: {res_data['is_passed']}, Time: {res_data['formatted_time_spent']}")

    # 8. Verify Automatic Sync to Official Grade Matrix
    print("\n[Step 8] Verifying Automatic Sync to Official Grade Matrix...")
    official_grade = Grade.objects.filter(student=student_obj, exam_term=term, subject=subject).first()
    assert official_grade is not None, "Grade record was not synced!"
    assert official_grade.score == Decimal('50.00')
    assert "Mobile" in official_grade.remarks
    print(f"  ✓ Official Grade Record Found: Score={official_grade.score}, Remarks='{official_grade.remarks}'")

    # 9. Test Detailed Result View with Question Review
    print("\n[Step 9] Testing GET /api/v1/online-exams/submissions/<sub_id>/result/...")
    result_res = client.get(f'/api/v1/online-exams/submissions/{sub_id}/result/')
    assert result_res.status_code == 200, f"Result view failed: {result_res.data}"
    sub_detail = result_res.data['submission']
    assert sub_detail['score_obtained'] == 50.0
    reviews = sub_detail['questions_review']
    assert len(reviews) == 2

    # Q1 was correct
    rev1 = next(r for r in reviews if r['question_id'] == q1.id)
    assert rev1['is_correct'] is True
    assert rev1['points_awarded'] == 50.0
    assert "កុសល" in rev1['explanation']

    # Q2 was incorrect
    rev2 = next(r for r in reviews if r['question_id'] == q2.id)
    assert rev2['is_correct'] is False
    assert rev2['points_awarded'] == 0.0
    assert "៣៣ តួ" in rev2['explanation']
    print(f"  ✓ Question 1 Review: Correct = {rev1['is_correct']}, Explanation = '{rev1['explanation']}'")
    print(f"  ✓ Question 2 Review: Correct = {rev2['is_correct']}, Explanation = '{rev2['explanation']}'")

    # 10. Clean up test data
    print("\n[Step 10] Cleaning up temporary test exam...")
    exam.delete()
    print("  ✓ Cleanup complete.")

    print("\n" + "=" * 65)
    print("🎉 ALL MOBILE ONLINE EXAM BACKEND API TESTS PASSED 100%!")
    print("=" * 65)

if __name__ == '__main__':
    run_tests()
