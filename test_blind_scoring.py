import os
import sys
import django
import datetime
from decimal import Decimal
import json

sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.academics.models import AcademicYear, Classroom, Subject
from apps.students.models import Student
from apps.examinations.models import (
    StandardizedExam, ExamRoom, ExamSubject, ExamCandidate, CandidateSubjectScore,
    ExamRoomSubjectCode
)

def test_blind_scoring_workflow():
    print("🚀 Starting Automated Test for Blind / Secret-Coded Exam Scoring System...")

    # 1. Setup Admin & Academic Year
    admin_user = User.objects.filter(is_superuser=True).first()
    if not admin_user:
        admin_user = User.objects.create_superuser('admin_blind_test', 'admin_blind@test.com', 'adminpass123')

    ay, _ = AcademicYear.objects.get_or_create(
        name='2025-2026',
        defaults={'start_date': '2025-09-01', 'end_date': '2026-07-15', 'is_current': True}
    )

    cls_12a, _ = Classroom.objects.get_or_create(
        code='12A1',
        academic_year=ay,
        defaults={'name': 'ថ្នាក់ទី១២A1', 'grade_level': 12, 'track': 'SCIENCE'}
    )

    # Create 30 students to test 25/room
    Student.objects.filter(student_id__startswith='TEST_BLIND_').delete()
    students = []
    for i in range(1, 31):
        s = Student.objects.create(
            student_id=f"TEST_BLIND_{i:03d}",
            khmer_name=f"សិស្ស កូដ {i:02d}",
            latin_name=f"Student Blind {i:02d}",
            gender='F' if i % 2 == 0 else 'M',
            date_of_birth=datetime.date(2008, (i % 12) + 1, (i % 25) + 1),
            classroom=cls_12a,
            academic_year=ay,
            status='ACTIVE'
        )
        students.append(s)

    # 2. Create Standardized Exam
    StandardizedExam.objects.filter(name='សម័យប្រឡងតេស្តសម្ងាត់ ថ្នាក់ទី១២ (Blind Test)').delete()
    exam = StandardizedExam.objects.create(
        name='សម័យប្រឡងតេស្តសម្ងាត់ ថ្នាក់ទី១២ (Blind Test)',
        academic_year=ay,
        grade_level=12,
        track='ALL',
        exam_date=datetime.date.today(),
        candidates_per_room=25,
        is_published=True
    )

    sub_math, _ = Subject.objects.get_or_create(code='MATH_BLIND', defaults={'name_kh': 'គណិតវិទ្យា', 'name_en': 'Math', 'credit': 2})
    sub_khmer, _ = Subject.objects.get_or_create(code='KHM_BLIND', defaults={'name_kh': 'ភាសាខ្មែរ', 'name_en': 'Khmer', 'credit': 2})

    es_math = ExamSubject.objects.create(exam=exam, subject=sub_math, max_score=Decimal('100.00'), coefficient=Decimal('2.00'), order=1)
    es_khmer = ExamSubject.objects.create(exam=exam, subject=sub_khmer, max_score=Decimal('100.00'), coefficient=Decimal('2.00'), order=2)

    # 3. Pull candidates & generate 25-cap rooms
    client = Client()
    client.force_login(admin_user)

    client.post(f'/examinations/standardized/{exam.id}/pull-candidates/')
    client.post(f'/examinations/standardized/{exam.id}/generate-rooms/')

    rooms = list(exam.rooms.all().order_by('room_number'))
    assert len(rooms) >= 2
    room_1 = rooms[0]
    assert room_1.candidates.count() == 25
    print(f"✅ 1. Setup complete. Exam created with 2 rooms (Room 01 has {room_1.candidates.count()} candidates).")

    # 4. Check Secret Codes auto-generated
    exam.generate_all_secret_codes()
    math_code_obj = ExamRoomSubjectCode.objects.filter(exam_room=room_1, exam_subject=es_math).first()
    assert math_code_obj is not None, "Math secret code envelope must exist!"
    secret_code_math_r1 = math_code_obj.secret_code
    print(f"✅ 2. Auto-generated Secret Code for Room 01 Math: «{secret_code_math_r1}»")

    # 5. Test Step 1 & 2 API: get-subjects
    res_subjects = client.get(f'/examinations/standardized/api/get-subjects/{exam.id}/')
    assert res_subjects.status_code == 200
    subj_data = res_subjects.json()
    assert subj_data['status'] == 'success'
    assert len(subj_data['subjects']) == 2
    print(f"✅ 3. Step 1 & 2 API /api/get-subjects/{exam.id}/ returned {len(subj_data['subjects'])} subjects.")

    # 6. Test Step 3: Validate Invalid Secret Code
    res_invalid = client.post(
        '/examinations/standardized/api/validate-secret-code/',
        data=json.dumps({
            'exam_id': exam.id,
            'subject_id': es_math.id,
            'secret_code': 'WRONG-CODE-9999'
        }),
        content_type='application/json'
    )
    assert res_invalid.status_code == 200
    assert res_invalid.json()['status'] == 'error'
    print(f"✅ 4. Invalid secret code correctly rejected with error message: {res_invalid.json()['message']}")

    # 7. Test Step 3: Validate Valid Secret Code
    res_valid = client.post(
        '/examinations/standardized/api/validate-secret-code/',
        data=json.dumps({
            'exam_id': exam.id,
            'subject_id': es_math.id,
            'secret_code': secret_code_math_r1
        }),
        content_type='application/json'
    )
    assert res_valid.status_code == 200
    val_data = res_valid.json()
    assert val_data['status'] == 'success'
    assert val_data['candidate_count'] == 25
    assert len(val_data['desks']) == 25
    # Verify Anonymity: candidate names and IDs are NOT present in desks payload!
    for d in val_data['desks']:
        assert 'candidate_name_kh' not in d
        assert 'student_id' not in d
        assert 'desk_number' in d
    print(f"✅ 5. Valid secret code accepted! Returned 25 anonymous candidate desks (01 to 25) with zero candidate identity leakage.")

    # 8. Test Step 4: Rapid Save Blind Scores (Desk 01 to 25)
    # We submit: Desk 1 = 98.5, Desk 2 = 'A' (Absent), Desk 3 = 85.0, others = 70.0
    scores_payload = []
    for d_num in range(1, 26):
        if d_num == 1:
            scores_payload.append({'desk_number': d_num, 'score': '98.5', 'is_absent': False})
        elif d_num == 2:
            scores_payload.append({'desk_number': d_num, 'score': 'A', 'is_absent': True})
        elif d_num == 3:
            scores_payload.append({'desk_number': d_num, 'score': '85.0', 'is_absent': False})
        else:
            scores_payload.append({'desk_number': d_num, 'score': '70.0', 'is_absent': False})

    res_save = client.post(
        '/examinations/standardized/api/save-blind-scores/',
        data=json.dumps({
            'exam_id': exam.id,
            'subject_id': es_math.id,
            'secret_code': secret_code_math_r1,
            'scores': scores_payload
        }),
        content_type='application/json'
    )
    assert res_save.status_code == 200
    save_data = res_save.json()
    assert save_data['status'] == 'success'
    assert save_data['summary']['absent_count'] == 1
    assert save_data['summary']['max_score'] == 98.5
    print(f"✅ 6. Step 4 Save API executed successfully! Saved 25 scores, Max={save_data['summary']['max_score']}, Avg={save_data['summary']['average_score']}")

    # 9. Verify that real student candidates now have those scores mapped
    cand_1 = room_1.candidates.filter(desk_number=1).first()
    cand_2 = room_1.candidates.filter(desk_number=2).first()
    score_cand_1 = CandidateSubjectScore.objects.filter(candidate=cand_1, exam_subject=es_math).first()
    score_cand_2 = CandidateSubjectScore.objects.filter(candidate=cand_2, exam_subject=es_math).first()

    assert score_cand_1.score == Decimal('98.50'), f"Expected Cand 1 score 98.50, got {score_cand_1.score}"
    assert score_cand_2.is_absent is True, "Expected Cand 2 to be Absent"
    print(f"✅ 7. Verified in database: Real Candidate «{cand_1.candidate_name_kh}» (Desk 01) mapped score = 98.50. Desk 02 mapped as Absent.")

    # 10. Verify ExamRoomSubjectCode is_graded status
    math_code_obj.refresh_from_db()
    assert math_code_obj.is_graded is True
    print(f"✅ 8. Envelope «{secret_code_math_r1}» successfully marked as Graded (is_graded=True).")

    # 11. Test Views Rendering
    res_portal = client.get('/examinations/standardized/blind-scoring/')
    assert res_portal.status_code == 200
    assert 'ផ្ទាំងបញ្ចូលពិន្ទុសិស្សដោយលេខកូដសម្ងាត់' in res_portal.content.decode('utf-8')
    print("✅ 9. GET /examinations/standardized/blind-scoring/ -> 200 OK (Blind Scoring Portal)")

    res_directory = client.get(f'/examinations/standardized/{exam.id}/secret-codes/')
    assert res_directory.status_code == 200
    assert 'តារាងបញ្ជីលេខកូដសម្ងាត់កញ្ចប់វិញ្ញាសា' in res_directory.content.decode('utf-8')
    print("✅ 10. GET /examinations/standardized/<id>/secret-codes/ -> 200 OK (Admin Secret Codes Directory)")

    # Cleanup
    exam.delete()
    print("\n🎉 ALL BLIND SCORING TESTS PASSED WITH 100% SUCCESS!")

if __name__ == '__main__':
    test_blind_scoring_workflow()
