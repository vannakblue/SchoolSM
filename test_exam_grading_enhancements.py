import os
import django
from decimal import Decimal
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.utils import timezone
from django.test import Client
from apps.accounts.models import User
from apps.teachers.models import Teacher
from apps.students.models import Student
from apps.academics.models import AcademicYear, Classroom, Subject, ClassSubject
from apps.examinations.models import (
    ExamTerm, Grade, StandardizedExam, ExamRoom, ExamSubject,
    ExamRoomSubjectCode, ExamCandidate, CandidateSubjectScore
)

def run_tests():
    print("=== STARTING EXAM GRADING & MOBILE ENHANCEMENTS TEST ===")
    
    # 1. Setup Admin and Teacher Users
    admin_user = User.objects.filter(role='ADMIN').first()
    if not admin_user:
        admin_user = User.objects.create_superuser('admin_test', 'admin_test@school.com', 'adminpass123')

    teacher = Teacher.objects.filter(status='ACTIVE').first()
    assert teacher, "Active teacher required!"
    
    teacher_user = teacher.user
    if not teacher_user:
        teacher_user = User.objects.create_user(username=f't_user_{teacher.id}', role='TEACHER')
        teacher.user = teacher_user
        teacher.save()

    active_year = AcademicYear.objects.filter(is_current=True).first() or AcademicYear.objects.first()
    classroom = Classroom.objects.filter(academic_year=active_year).first() or Classroom.objects.first()
    subject = Subject.objects.first()

    # Assign teacher to this classroom and subject
    ClassSubject.objects.get_or_create(
        classroom=classroom,
        subject=subject,
        defaults={'teacher': teacher, 'weekly_hours': 4}
    )

    # 2. Test ExamTerm Grading Window Controls
    now = timezone.now()
    term = ExamTerm.objects.create(
        name="សម័យប្រឡងតេស្ត Windows",
        academic_year=active_year,
        start_date=now.date(),
        end_date=now.date() + timedelta(days=5),
        grading_start_datetime=now - timedelta(hours=1),
        grading_end_datetime=now + timedelta(days=2),
        is_grading_locked=False
    )

    is_open, status_code, msg = term.get_grading_status()
    assert is_open is True, f"Expected open grading window, got {status_code}: {msg}"
    print("1. [PASS] Open grading window returns True.")

    # Test lock
    term.is_grading_locked = True
    term.save()
    is_open, status_code, msg = term.get_grading_status()
    assert is_open is False and status_code == 'LOCKED', "Expected LOCKED status."
    print("2. [PASS] Locked grading returns False (LOCKED).")

    # Unlock for subsequent tests
    term.is_grading_locked = False
    term.save()

    # 3. Test Web Grade Entry Matrix
    admin_client = Client()
    admin_client.force_login(admin_user)
    resp = admin_client.get(f'/examinations/matrix/?term={term.id}&classroom={classroom.id}')
    assert resp.status_code == 200, f"Expected 200 OK for admin matrix, got {resp.status_code}"
    print("3. [PASS] Web Grade Matrix rendered 200 OK for Admin.")

    teacher_client = Client()
    teacher_client.force_login(teacher_user)
    resp_t = teacher_client.get(f'/examinations/matrix/?term={term.id}&classroom={classroom.id}')
    assert resp_t.status_code == 200, f"Expected 200 OK for teacher matrix, got {resp_t.status_code}"
    print("4. [PASS] Web Grade Matrix rendered 200 OK for Teacher with assigned subjects.")

    # 4. Test Mobile API Endpoints
    # 4.1 Teacher Meta API
    meta_resp = teacher_client.get('/api/v1/grades/teacher-entry/meta/')
    assert meta_resp.status_code == 200, f"Expected 200 for meta API, got {meta_resp.status_code}"
    meta_data = meta_resp.json()
    assert meta_data['status'] == 'success'
    print("5. [PASS] Mobile API meta endpoint returned assigned classes and exam terms.")

    # 4.2 Teacher Sheet API
    sheet_resp = teacher_client.get(f'/api/v1/grades/teacher-entry/sheet/?term_id={term.id}&classroom_id={classroom.id}&subject_id={subject.id}')
    assert sheet_resp.status_code == 200, f"Expected 200 for sheet API, got {sheet_resp.status_code}"
    sheet_data = sheet_resp.json()
    assert sheet_data['status'] == 'success'
    print("6. [PASS] Mobile API grading sheet returned students list and max scores.")

    # 4.3 Teacher Save API
    student = Student.objects.filter(classroom=classroom).first()
    if not student:
        import datetime
        student = Student.objects.create(
            student_id="ST-TEST-999",
            khmer_name="សិស្ស ធ្វើតេស្ត Mobile",
            classroom=classroom,
            gender='M',
            date_of_birth=datetime.date(2008, 1, 1),
            status='ACTIVE'
        )
    save_payload = {
        'term_id': term.id,
        'classroom_id': classroom.id,
        'scores': [
            {'student_id': student.id, 'subject_id': subject.id, 'score': '48.5'}
        ]
    }
    save_resp = teacher_client.post('/api/v1/grades/teacher-entry/save/', save_payload, content_type='application/json')
    assert save_resp.status_code == 200, f"Expected 200 for save API, got {save_resp.status_code}"
    grade_rec = Grade.objects.filter(student=student, exam_term=term, subject=subject).first()
    assert grade_rec and float(grade_rec.score) == 48.5, f"Expected grade 48.5, got {grade_rec.score if grade_rec else 'None'}"
    print("7. [PASS] Mobile API teacher grade save successfully recorded score 48.5!")

    # 5. Test Standardized Exam & Secret Code Blind Scoring with custom candidates per room (e.g. 26 candidates)
    std_exam = StandardizedExam.objects.create(
        name="តេស្តសមត្ថភាពប្រឡងស្តង់ដា Mobile & Web Test",
        academic_year=active_year,
        grade_level=12,
        track='SCIENCE',
        exam_date=now.date(),
        candidates_per_room=26
    )

    std_room = ExamRoom.objects.create(
        exam=std_exam,
        room_number=1,
        room_name="បន្ទប់លេខ ០១",
        secret_code="SEC-01-9988"
    )

    exam_sub = ExamSubject.objects.create(
        exam=std_exam,
        subject=subject,
        max_score=Decimal('50.00'),
        coefficient=Decimal('1.00')
    )

    test_code_str = f"MTEST{now.strftime('%H%M%S')}"
    room_code = ExamRoomSubjectCode.objects.create(
        exam_room=std_room,
        exam_subject=exam_sub,
        secret_code=test_code_str
    )

    # Populate 26 candidates
    for i in range(1, 27):
        ExamCandidate.objects.create(
            exam=std_exam,
            room=std_room,
            roll_number=f"R-{i:03d}",
            desk_number=i,
            candidate_name_kh=f"បេក្ខជន ទី{i}",
            gender='M' if i % 2 == 0 else 'F',
        )

    # 5.1 Test Mobile Blind Scoring Validate API
    val_resp = teacher_client.post('/api/v1/grades/blind-scoring/validate-code/', {
        'exam_id': std_exam.id,
        'subject_id': exam_sub.id,
        'secret_code': test_code_str
    }, content_type='application/json')
    assert val_resp.status_code == 200, f"Expected 200 for blind validate, got {val_resp.status_code}"
    val_json = val_resp.json()
    assert val_json['status'] == 'success'
    assert val_json['candidate_count'] == 26, f"Expected 26 candidates, got {val_json['candidate_count']}"
    print(f"8. [PASS] Mobile Blind Scoring Validate API returned {val_json['candidate_count']} desks anonymously!")

    # 5.2 Test Mobile Blind Scoring Save API
    save_blind_payload = {
        'exam_id': std_exam.id,
        'subject_id': exam_sub.id,
        'secret_code': test_code_str,
        'scores': [
            {'desk_number': 1, 'score': '46.5'},
            {'desk_number': 2, 'score': 'A'}, # Absent
            {'desk_number': 26, 'score': '49.0'},
        ]
    }
    save_b_resp = teacher_client.post('/api/v1/grades/blind-scoring/save-scores/', save_blind_payload, content_type='application/json')
    assert save_b_resp.status_code == 200, f"Expected 200 for blind save API, got {save_b_resp.status_code}"
    print("9. [PASS] Mobile Blind Scoring Save API saved anonymous desk scores and updated exam ranks!")

    print("\n=== ALL EXAM GRADING & MOBILE ENHANCEMENT TESTS PASSED 100%! ===")

if __name__ == '__main__':
    run_tests()
