import os
import sys
import django
import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from apps.academics.models import AcademicYear, Classroom, Subject
from apps.students.models import Student
from apps.teachers.models import Teacher
from apps.examinations.models import (
    StandardizedExam, ExamRoom, ExamSubject,
    ExamCandidate, ExamStudentExclusion, ExamRoomSubjectCode
)

User = get_user_model()

def run_tests():
    print("=== STARTING SCORING METHOD, SECRET CODES & EXCLUSIONS TEST SUITE ===")

    # 1. Setup Admin & Teacher users
    admin_user, _ = User.objects.get_or_create(username='admin_scoring_test', defaults={'role': 'ADMIN', 'is_staff': True, 'is_superuser': True})
    admin_user.role = 'ADMIN'
    admin_user.save()

    teacher_user, _ = User.objects.get_or_create(username='teacher_scoring_test', defaults={'role': 'TEACHER'})
    teacher_user.role = 'TEACHER'
    teacher_user.save()

    teacher_prof, _ = Teacher.objects.get_or_create(
        teacher_id='T_SCORE_TEST',
        defaults={'khmer_name': 'ស៊ុំ គ្រូ', 'gender': 'M', 'status': Teacher.Status.ACTIVE}
    )
    teacher_prof.user = teacher_user
    teacher_prof.save()

    ay, _ = AcademicYear.objects.get_or_create(name='2026-2027', defaults={'is_active': True})
    classroom, _ = Classroom.objects.get_or_create(
        academic_year=ay,
        grade_level=12,
        name='12A1',
        defaults={'code': '12A1'}
    )

    # 2. Setup Students (1 normal active, 1 excluded)
    stu_normal, _ = Student.objects.get_or_create(
        student_id='STU_SCORE_01',
        defaults={
            'khmer_name': 'សុខ សំណាង',
            'gender': 'M',
            'date_of_birth': datetime.date(2008, 1, 1),
            'status': 'ACTIVE',
            'classroom': classroom,
            'academic_year': ay
        }
    )
    stu_normal.status = 'ACTIVE'
    stu_normal.classroom = classroom
    stu_normal.academic_year = ay
    stu_normal.save()

    stu_excluded, _ = Student.objects.get_or_create(
        student_id='STU_SCORE_02',
        defaults={
            'khmer_name': 'ជា វិបុល',
            'gender': 'M',
            'date_of_birth': datetime.date(2008, 5, 15),
            'status': 'ACTIVE',
            'classroom': classroom,
            'academic_year': ay
        }
    )
    stu_excluded.status = 'ACTIVE'
    stu_excluded.classroom = classroom
    stu_excluded.academic_year = ay
    stu_excluded.save()

    # Clean old test exams
    StandardizedExam.objects.filter(name__icontains='តេស្តកូដសម្ងាត់ & លើកលែង').delete()

    # 3. Create StandardizedExam with BLIND_SECRET_CODE mode
    exam = StandardizedExam.objects.create(
        name='តេស្តកូដសម្ងាត់ & លើកលែង ថ្នាក់ទី ១២',
        academic_year=ay,
        grade_level=12,
        track='ALL',
        session='MORNING',
        exam_date=datetime.date(2026, 9, 25),
        candidates_per_room=25,
        grading_method=StandardizedExam.GradingMethod.BLIND_SECRET_CODE,
        is_published=True
    )
    subj = Subject.objects.filter(name_kh='គណិតវិទ្យា').first() or Subject.objects.create(name_kh='គណិតវិទ្យា', code='MATH_12')
    ExamSubject.objects.create(exam=exam, subject=subj, max_score=100, coefficient=2, order=1)
    room = ExamRoom.objects.create(exam=exam, room_number=1, room_name="បន្ទប់ 01")

    print(f"1. [PASS] Created StandardizedExam with grading_method='{exam.grading_method}'.")

    # 4. Create an ExamStudentExclusion linked to this standardized_exam
    exclusion = ExamStudentExclusion.objects.create(
        student=stu_excluded,
        academic_year=ay,
        standardized_exam=exam,
        reason=ExamStudentExclusion.Reason.DROPPED,
        notes='សិស្សឈប់រៀនមុនសម័យប្រឡង',
        is_active=True,
        excluded_by=admin_user
    )
    print("2. [PASS] Created ExamStudentExclusion linked directly to standardized_exam.")

    # 5. Test 1-Click Pull Candidates: stu_excluded must NOT be pulled, stu_normal MUST be pulled
    client_admin = Client()
    client_admin.force_login(admin_user)

    pull_res = client_admin.post(f'/examinations/standardized/{exam.id}/pull-candidates/')
    assert pull_res.status_code in [200, 302]

    pulled_candidate_ids = list(exam.candidates.values_list('student_id', flat=True))
    assert stu_normal.id in pulled_candidate_ids, "Active student should be pulled"
    assert stu_excluded.id not in pulled_candidate_ids, "Excluded student MUST NOT be pulled"
    print("3. [PASS] Pull candidates respected exam exclusion: normal student pulled, excluded student omitted.")

    # 6. Test Score Entry Enforcement:
    # A Teacher trying to access room scores entry when BLIND_SECRET_CODE is active must be redirected
    client_teacher = Client()
    client_teacher.force_login(teacher_user)

    teacher_room_res = client_teacher.get(f'/examinations/standardized/{exam.id}/scores-entry/')
    assert teacher_room_res.status_code == 302
    assert '/examinations/standardized/blind-scoring/' in teacher_room_res.url
    print("4. [PASS] Teacher was blocked from direct room scores entry and redirected to blind scoring portal.")

    # Admin CAN access room scores entry
    admin_room_res = client_admin.get(f'/examinations/standardized/{exam.id}/scores-entry/')
    assert admin_room_res.status_code == 200
    print("5. [PASS] Admin successfully accessed direct room scores entry.")

    # 7. Test Admin updating grading_method via API to 'TEACHER_DIRECT'
    update_res = client_admin.post(f'/examinations/standardized/{exam.id}/set-grading-window/', {
        'grading_method': 'TEACHER_DIRECT',
        'is_grading_locked': False
    }, content_type='application/json')
    assert update_res.status_code == 200
    assert update_res.json()['status'] == 'success'
    exam.refresh_from_db()
    assert exam.grading_method == 'TEACHER_DIRECT'
    print("6. [PASS] Successfully updated exam grading_method to 'TEACHER_DIRECT' via API.")

    # Now Teacher CAN access direct room scores entry
    teacher_room_res2 = client_teacher.get(f'/examinations/standardized/{exam.id}/scores-entry/')
    assert teacher_room_res2.status_code == 200
    print("7. [PASS] Teacher can now enter room scores directly under TEACHER_DIRECT mode.")

    # 8. Test Secret Codes Directory & Generation
    codes_dir_res = client_admin.get(f'/examinations/standardized/{exam.id}/secret-codes/')
    assert codes_dir_res.status_code == 200
    assert ExamRoomSubjectCode.objects.filter(exam_room__exam=exam).exists()
    print("8. [PASS] Secret codes directory generated room/subject secret codes successfully.")

    # 9. Test exclusions_manage page with ?standardized_exam={exam.id}
    exc_page_res = client_admin.get(f'/examinations/exclusions/?standardized_exam={exam.id}')
    assert exc_page_res.status_code == 200
    content = exc_page_res.content.decode('utf-8')
    assert 'តេស្តកូដសម្ងាត់' in content
    print("9. [PASS] exclusions_manage page correctly displayed banner and filtered by standardized_exam.")

    # 10. Test standardized_exam_list renders session Secret Codes modal
    list_page_res = client_admin.get(f'/examinations/standardized/?year={ay.id}')
    assert list_page_res.status_code == 200
    list_content = list_page_res.content.decode('utf-8')
    assert 'openSessionSecretCodesModal' in list_content
    assert 'secretCodesModal_' in list_content
    print("10. [PASS] standardized_exam_list renders Secret Codes modal and trigger successfully.")

    # Clean up
    exam.delete()
    stu_normal.delete()
    stu_excluded.delete()
    print("11. [PASS] Cleaned up test data.")

    print("\n=== ALL 11 TESTS PASSED 100%! ===")

if __name__ == '__main__':
    run_tests()
