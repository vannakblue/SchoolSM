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
from django.utils import timezone
from apps.accounts.models import User
from apps.academics.models import AcademicYear, Classroom, Subject
from apps.students.models import Student
from apps.examinations.models import (
    StandardizedExam, ExamRoom, ExamSubject, ExamCandidate, CandidateSubjectScore,
    ExamRoomSubjectCode
)

def test_blind_scoring_and_grading_window():
    print("🚀 Starting Automated Test for Blind Exam Scoring, Review Mode & Admin Grading Controls...")

    # 1. Setup Users (Admin & Regular Teacher)
    admin_user = User.objects.filter(is_superuser=True).first()
    if not admin_user:
        admin_user = User.objects.create_superuser('admin_ctrl_test', 'admin_ctrl@test.com', 'adminpass123')

    teacher_user, _ = User.objects.get_or_create(
        username='teacher_blind_scorer',
        defaults={'role': 'TEACHER', 'email': 'teacher_blind@test.com', 'is_staff': False, 'is_superuser': False}
    )
    teacher_user.set_password('teacherpass123')
    teacher_user.role = 'TEACHER'
    teacher_user.save()

    # 2. Setup Academic Year & Classroom
    ay, _ = AcademicYear.objects.get_or_create(
        name='2025-2026',
        defaults={'start_date': '2025-09-01', 'end_date': '2026-07-15', 'is_current': True}
    )

    cls_12b, _ = Classroom.objects.get_or_create(
        code='12B1',
        academic_year=ay,
        defaults={'name': 'ថ្នាក់ទី១២B1', 'grade_level': 12, 'track': 'ALL'}
    )

    # Create 25 test students
    Student.objects.filter(student_id__startswith='TEST_CTRL_').delete()
    students = []
    for i in range(1, 26):
        s = Student.objects.create(
            student_id=f"TEST_CTRL_{i:03d}",
            khmer_name=f"សិស្ស កែវ {i:02d}",
            latin_name=f"Student Keo {i:02d}",
            gender='F' if i % 2 == 0 else 'M',
            date_of_birth=datetime.date(2008, 5, (i % 25) + 1),
            classroom=cls_12b,
            academic_year=ay,
            status='ACTIVE'
        )
        students.append(s)

    # 3. Create Standardized Exam
    StandardizedExam.objects.filter(name='សម័យប្រឡងតេស្តស្តង់ដាត្រួតពិនិត្យ Grade 12').delete()
    exam = StandardizedExam.objects.create(
        name='សម័យប្រឡងតេស្តស្តង់ដាត្រួតពិនិត្យ Grade 12',
        academic_year=ay,
        grade_level=12,
        track='ALL',
        session='MORNING',
        exam_date=datetime.date.today(),
        candidates_per_room=25,
        is_published=True,
        is_grading_locked=False
    )

    sub_phys, _ = Subject.objects.get_or_create(code='PHYS_TEST', defaults={'name_kh': 'រូបវិទ្យា', 'name_en': 'Physics', 'credit': 2})
    es_phys = ExamSubject.objects.create(exam=exam, subject=sub_phys, max_score=Decimal('100.00'), coefficient=Decimal('2.00'), order=1)

    admin_client = Client()
    admin_client.force_login(admin_user)

    teacher_client = Client()
    teacher_client.force_login(teacher_user)

    # Pull & generate rooms
    admin_client.post(f'/examinations/standardized/{exam.id}/pull-candidates/')
    admin_client.post(f'/examinations/standardized/{exam.id}/generate-rooms/')

    exam.generate_all_secret_codes()
    room_1 = exam.rooms.first()
    assert room_1.candidates.count() == 25

    code_obj = ExamRoomSubjectCode.objects.filter(exam_room=room_1, exam_subject=es_phys).first()
    assert code_obj is not None
    secret_code = code_obj.secret_code
    print(f"✅ 1. Setup complete: Room 01 with 25 candidates. Envelope secret code: «{secret_code}»")

    # 4. Test Teacher Flow: Step 1 & 2 - Get Subjects API
    res_subjects = teacher_client.get(f'/examinations/standardized/api/get-subjects/{exam.id}/')
    assert res_subjects.status_code == 200
    s_data = res_subjects.json()
    assert s_data['status'] == 'success'
    assert s_data['is_grading_open'] is True
    assert len(s_data['subjects']) == 1
    # Verify envelope listing is present for teacher but physical room names are masked
    assert len(s_data['subjects'][0]['secret_codes']) >= 1
    for envelope in s_data['subjects'][0]['secret_codes']:
        assert 'កញ្ចប់កូដ #' in envelope['room_name'] or envelope['room_name'].startswith('កញ្ចប់កូដ')
    print(f"✅ 2. Step 1 & 2 Get-Subjects API verified. Envelope list returned with physical room names masked.")

    # 5. Test Step 3: Teacher Validates Secret Code
    res_validate = teacher_client.post(
        '/examinations/standardized/api/validate-secret-code/',
        data=json.dumps({'exam_id': exam.id, 'subject_id': es_phys.id, 'secret_code': secret_code}),
        content_type='application/json'
    )
    assert res_validate.status_code == 200
    v_data = res_validate.json()
    assert v_data['status'] == 'success'
    assert v_data['candidate_count'] == 25
    assert len(v_data['desks']) == 25
    # Strict anonymity check
    for d in v_data['desks']:
        assert 'student_id' not in d
        assert 'candidate_name_kh' not in d
        assert 'desk_number' in d
    print(f"✅ 3. Step 3 Validate Secret Code verified: 25 anonymous desk slots returned (01 to 25).")

    # 6. Test Step 4: Teacher Enters Scores (Desk 01 to 25)
    scores_to_send = []
    # 6. Test Step 4: Teacher Enters Scores (Desk 01 to 25) with numeric score and 0 for absent (No letter A needed!)
    scores_to_send = []
    for d in range(1, 26):
        if d == 1:
            scores_to_send.append({'desk_number': d, 'score': '95.0', 'is_absent': False})
        elif d == 2:
            scores_to_send.append({'desk_number': d, 'score': '0', 'is_absent': False})  # Entered as 0
        elif d == 3:
            scores_to_send.append({'desk_number': d, 'score': '0.0', 'is_absent': False}) # Entered as 0.0
        else:
            scores_to_send.append({'desk_number': d, 'score': '80.0', 'is_absent': False})

    res_save = teacher_client.post(
        '/examinations/standardized/api/save-blind-scores/',
        data=json.dumps({'exam_id': exam.id, 'subject_id': es_phys.id, 'secret_code': secret_code, 'scores': scores_to_send}),
        content_type='application/json'
    )
    assert res_save.status_code == 200
    save_res = res_save.json()
    assert save_res['status'] == 'success'
    assert save_res['summary']['absent_count'] == 2
    assert save_res['summary']['max_score'] == 95.0
    print(f"✅ 4. Step 4 Score entry with numeric scores and 0 (for absent) saved successfully by Teacher. Summary: Max={save_res['summary']['max_score']}, 0-Scores/Absents={save_res['summary']['absent_count']}.")

    # 7. Test Review Entered Scores (ត្រួតពិនិត្យពិន្ទុដែលបានបញ្ចូល)
    res_review = teacher_client.post(
        '/examinations/standardized/api/validate-secret-code/',
        data=json.dumps({'exam_id': exam.id, 'subject_id': es_phys.id, 'secret_code': secret_code}),
        content_type='application/json'
    )
    assert res_review.status_code == 200
    r_data = res_review.json()
    assert r_data['is_already_graded'] is True
    # Desk 1 score = 95, Desk 2 and 3 score = 0.0
    desk_1 = next(d for d in r_data['desks'] if d['desk_number'] == 1)
    desk_2 = next(d for d in r_data['desks'] if d['desk_number'] == 2)
    desk_3 = next(d for d in r_data['desks'] if d['desk_number'] == 3)
    assert desk_1['score'] == 95.0
    assert desk_2['score'] == 0.0 or desk_2['is_absent'] is True
    assert desk_3['score'] == 0.0 or desk_3['is_absent'] is True
    print("✅ 5. Review entered scores mode verified: Numeric 0 scores and absentee markers retrieved accurately.")

    # 8. Test Admin Grading Window: 1-Click Instant Lock Toggle API
    res_lock = admin_client.post(
        f'/examinations/standardized/{exam.id}/toggle-grading-lock/',
        data=json.dumps({'is_locked': True, 'apply_to_session': True}),
        content_type='application/json'
    )
    assert res_lock.status_code == 200
    lock_data = res_lock.json()
    assert lock_data['status'] == 'success'
    assert lock_data['is_grading_locked'] is True
    assert lock_data['is_grading_open'] is False
    print("✅ 6. Admin 1-Click Instant Lock Toggle executed. Exam is now LOCKED.")

    # 9. Verify Teacher is BLOCKED from saving scores when exam is locked
    res_teacher_blocked = teacher_client.post(
        '/examinations/standardized/api/save-blind-scores/',
        data=json.dumps({'exam_id': exam.id, 'subject_id': es_phys.id, 'secret_code': secret_code, 'scores': scores_to_send}),
        content_type='application/json'
    )
    assert res_teacher_blocked.status_code == 200
    blocked_data = res_teacher_blocked.json()
    assert blocked_data['status'] == 'error'
    assert 'មិនអាចរក្សាទុកបានទេ' in blocked_data['message']
    print(f"✅ 7. Verified Teacher is blocked when locked: «{blocked_data['message']}».")

    # 10. Verify Teacher CAN still validate to inspect/review scores
    res_teacher_inspect = teacher_client.post(
        '/examinations/standardized/api/validate-secret-code/',
        data=json.dumps({'exam_id': exam.id, 'subject_id': es_phys.id, 'secret_code': secret_code}),
        content_type='application/json'
    )
    assert res_teacher_inspect.status_code == 200
    inspect_data = res_teacher_inspect.json()
    assert inspect_data['status'] == 'success'
    assert inspect_data['is_grading_open'] is False
    print("✅ 8. Verified Teacher CAN still inspect & review entered scores in Read-Only mode while locked.")

    # 11. Test Admin Grading Window: Schedule Datetime Window API
    now = timezone.now()
    future_start = (now + datetime.timedelta(days=1)).isoformat()
    future_end = (now + datetime.timedelta(days=5)).isoformat()

    res_window = admin_client.post(
        f'/examinations/standardized/{exam.id}/set-grading-window/',
        data=json.dumps({
            'grading_start_datetime': future_start,
            'grading_end_datetime': future_end,
            'is_grading_locked': False,
            'apply_to_session': True
        }),
        content_type='application/json'
    )
    assert res_window.status_code == 200
    win_data = res_window.json()
    assert win_data['status'] == 'success'
    assert win_data['status_code'] == 'NOT_STARTED'
    print(f"✅ 9. Admin scheduled future grading window ({win_data['status_code']}). Message: «{win_data['grading_status_msg']}».")

    # 12. Test Admin 1-Click Instant Unlock API
    res_unlock = admin_client.post(
        f'/examinations/standardized/{exam.id}/set-grading-window/',
        data=json.dumps({
            'grading_start_datetime': None,
            'grading_end_datetime': None,
            'is_grading_locked': False,
            'apply_to_session': True
        }),
        content_type='application/json'
    )
    assert res_unlock.status_code == 200
    unl_data = res_unlock.json()
    assert unl_data['is_grading_open'] is True
    print("✅ 10. Admin reopened grading window instantly (is_grading_open=True).")

    # 13. Test Mobile API Endpoints
    # Validate endpoint
    res_mob_val = teacher_client.post(
        '/api/v1/grades/blind-scoring/validate-code/',
        data=json.dumps({'exam_id': exam.id, 'subject_id': es_phys.id, 'secret_code': secret_code}),
        content_type='application/json'
    )
    assert res_mob_val.status_code == 200
    mob_val_data = res_mob_val.json()
    assert mob_val_data['status'] == 'success'
    assert mob_val_data['summary']['entered_count'] == 25
    assert mob_val_data['summary']['absent_count'] == 2
    assert len(mob_val_data['desks']) == 25
    print(f"✅ 11. Mobile Validate API verified: 25 desks with summary (Entered={mob_val_data['summary']['entered_count']}, Absent={mob_val_data['summary']['absent_count']}).")

    # Mobile Save endpoint
    res_mob_save = teacher_client.post(
        '/api/v1/grades/blind-scoring/save-scores/',
        data=json.dumps({
            'exam_id': exam.id,
            'subject_id': es_phys.id,
            'secret_code': secret_code,
            'scores': [{'desk_number': 1, 'score': '99.0', 'is_absent': False}]
        }),
        content_type='application/json'
    )
    assert res_mob_save.status_code == 200
    mob_save_data = res_mob_save.json()
    assert mob_save_data['status'] == 'success'
    print(f"✅ 12. Mobile Save API verified: {mob_save_data['message']}")

    # Cleanup
    exam.delete()
    print("\n🎉 ALL TESTS COMPLETED WITH 100% SUCCESS!")

if __name__ == '__main__':
    test_blind_scoring_and_grading_window()
