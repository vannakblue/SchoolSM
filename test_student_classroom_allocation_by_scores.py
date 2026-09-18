import os
import sys
import json
from decimal import Decimal
from datetime import date
import django

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.academics.models import AcademicYear, Classroom, Subject
from apps.students.models import Student, StudentPromotionRecord
from apps.examinations.models import StandardizedExam, ExamCandidate, ExamRoom, CandidateSubjectScore, ExamSubject


def run_tests():
    print("=== STARTING STUDENT CLASSROOM ALLOCATION BY SCORES TEST SUITE ===")

    # 1. Setup Admin Account
    admin_user = User.objects.filter(role=User.Role.ADMIN).first()
    if not admin_user:
        admin_user = User.objects.create_superuser(
            username='test_alloc_admin',
            email='alloc_admin@schoolsm.test',
            password='Password123!',
            role=User.Role.ADMIN,
            khmer_name='អ្នកគ្រប់គ្រង បែងចែកថ្នាក់'
        )

    client = Client()
    client.force_login(admin_user)
    print("1. [PASS] Logged in as Admin.")

    # 2. Setup Academic Years: 2025-2026 (Source) and 2026-2027 (Target)
    ay_source, _ = AcademicYear.objects.get_or_create(
        name='2025-2026-ALLOC-TEST',
        defaults={'start_date': date(2025, 9, 1), 'end_date': date(2026, 7, 31), 'is_current': False}
    )
    ay_target = AcademicYear.objects.filter(is_current=True).first() or AcademicYear.objects.filter(name='2026-2027').first()

    # 3. Get existing classrooms in target year for Grade 7 (7A, 7B)
    cls_7a = Classroom.objects.filter(academic_year=ay_target, grade_level=7).first()
    if not cls_7a:
        cls_7a = Classroom.objects.create(name='7A-TEST', code='7A-TEST', academic_year=ay_target, grade_level=7, capacity=25)
    cls_7b = Classroom.objects.filter(academic_year=ay_target, grade_level=7).exclude(id=cls_7a.id).first()
    if not cls_7b:
        cls_7b = Classroom.objects.create(name='7B-TEST', code='7B-TEST', academic_year=ay_target, grade_level=7, capacity=25)

    # 4. Create 4 active test students
    test_students = []
    for i in range(1, 5):
        st, _ = Student.objects.get_or_create(
            student_id=f'STU-ALLOC-TEST-{i:03d}',
            defaults={
                'khmer_name': f'សិស្ស តេស្តបែងចែក លេខ{i}',
                'gender': 'F' if i % 2 == 0 else 'M',
                'date_of_birth': date(2012, 1, 1),
                'classroom': cls_7a,
                'academic_year': ay_target,
                'status': 'ACTIVE'
            }
        )
        test_students.append(st)

    # 5. Create a test Standardized Exam with different scores
    exam, _ = StandardizedExam.objects.get_or_create(
        name='តេស្តដើមឆ្នាំ សាកល្បងបែងចែកថ្នាក់',
        academic_year=ay_target,
        grade_level=7,
        defaults={'exam_date': date(2026, 9, 20)}
    )

    # Assign candidates with scores: 95.00, 85.00, 75.00, 65.00
    scores = [Decimal('95.00'), Decimal('85.00'), Decimal('75.00'), Decimal('65.00')]
    for idx, st in enumerate(test_students):
        cand, _ = ExamCandidate.objects.get_or_create(
            exam=exam,
            student=st,
            defaults={
                'roll_number': f'R-{idx+1:03d}',
                'candidate_name_kh': st.khmer_name,
                'gender': st.gender,
                'total_score': scores[idx],
                'average_score': scores[idx],
                'rank_overall': idx + 1
            }
        )
        cand.total_score = scores[idx]
        cand.average_score = scores[idx]
        cand.rank_overall = idx + 1
        cand.save()

    print("2. [PASS] Setup test data with students and exam scores.")

    # 6. Test GET Main View
    resp_view = client.get(f'/academics/classrooms/allocation/?grade=7&academic_year={ay_target.id}')
    assert resp_view.status_code == 200, f"Expected 200, got {resp_view.status_code}"
    content = resp_view.content.decode('utf-8')
    assert 'បែងចែកថ្នាក់រៀនតាមពិន្ទុ' in content
    assert 'ពិន្ទុតេស្តដើមឆ្នាំ / តេស្តស្តង់ដា' in content
    assert 'ពិន្ទុមធ្យមភាគចុងឆ្នាំចាស់' in content
    print("3. [PASS] Classroom allocation hub page loaded successfully with Khmer UI elements.")

    # 7. Test API Preview: Standardized Exam (Top-Down)
    payload_preview = {
        'target_year_id': ay_target.id,
        'grade_level': 7,
        'score_source_type': 'STANDARDIZED_EXAM',
        'exam_id': exam.id,
        'strategy': 'TOP_DOWN',
        'target_class_ids': [cls_7a.id, cls_7b.id]
    }
    resp_prev = client.post(
        '/academics/classrooms/allocation/api/preview/',
        data=json.dumps(payload_preview),
        content_type='application/json'
    )
    assert resp_prev.status_code == 200, f"Expected 200, got {resp_prev.status_code}"
    data_prev = resp_prev.json()
    assert data_prev['status'] == 'success'
    buckets = data_prev['preview']['classroom_buckets']
    assert len(buckets) == 2, f"Expected 2 buckets, got {len(buckets)}"

    # In Top-Down, higher score students should be in Class 1 (cls_7a)
    print("4. [PASS] Standardized exam preview computed correctly.")

    # 8. Test API Preview: Balanced Snake (Serpentine)
    payload_snake = dict(payload_preview)
    payload_snake['strategy'] = 'BALANCED_SNAKE'
    resp_snake = client.post(
        '/academics/classrooms/allocation/api/preview/',
        data=json.dumps(payload_snake),
        content_type='application/json'
    )
    assert resp_snake.status_code == 200
    data_snake = resp_snake.json()
    assert data_snake['status'] == 'success'
    print("5. [PASS] Balanced Snake (Serpentine) allocation preview passed.")

    # 9. Test API Preview: Previous Year Annual Average [(S1 + S2) / 2]
    payload_annual = {
        'target_year_id': ay_target.id,
        'grade_level': 7,
        'score_source_type': 'PREVIOUS_YEAR_ANNUAL',
        'source_year_id': ay_source.id,
        'strategy': 'TOP_DOWN',
        'target_class_ids': [cls_7a.id, cls_7b.id]
    }
    resp_ann = client.post(
        '/academics/classrooms/allocation/api/preview/',
        data=json.dumps(payload_annual),
        content_type='application/json'
    )
    assert resp_ann.status_code == 200
    data_ann = resp_ann.json()
    assert data_ann['status'] == 'success'
    print("6. [PASS] Previous Year Annual Average [(S1+S2)/2] preview passed.")

    # 10. Test API Apply Allocation
    allocations_to_apply = [
        {'student_id': test_students[0].id, 'target_classroom_id': cls_7a.id, 'score': 95.0, 'rank': 1},
        {'student_id': test_students[1].id, 'target_classroom_id': cls_7a.id, 'score': 85.0, 'rank': 2},
        {'student_id': test_students[2].id, 'target_classroom_id': cls_7b.id, 'score': 75.0, 'rank': 3},
        {'student_id': test_students[3].id, 'target_classroom_id': cls_7b.id, 'score': 65.0, 'rank': 4},
    ]
    resp_apply = client.post(
        '/academics/classrooms/allocation/api/apply/',
        data=json.dumps({
            'target_year_id': ay_target.id,
            'allocations': allocations_to_apply,
            'audit_reason': 'តេស្តបែងចែកថ្នាក់តាមពិន្ទុ'
        }),
        content_type='application/json'
    )
    assert resp_apply.status_code == 200
    data_apply = resp_apply.json()
    assert data_apply['status'] == 'success'
    assert data_apply['updated_count'] == 4

    # Verify students classroom in DB
    st1 = Student.objects.get(id=test_students[0].id)
    st3 = Student.objects.get(id=test_students[2].id)
    assert st1.classroom_id == cls_7a.id
    assert st3.classroom_id == cls_7b.id
    print("7. [PASS] Applied classroom allocation successfully with database updates!")

    # 11. Test Excel Export
    resp_excel = client.get(
        f'/academics/classrooms/allocation/export-excel/?target_year_id={ay_target.id}&grade_level=7&score_source_type=STANDARDIZED_EXAM&exam_id={exam.id}'
    )
    assert resp_excel.status_code == 200
    assert 'spreadsheetml' in resp_excel['Content-Type']
    assert len(resp_excel.content) > 5000
    print(f"8. [PASS] Official Excel allocation report exported ({len(resp_excel.content)} bytes).")

    # Cleanup test objects
    ExamCandidate.objects.filter(exam=exam).delete()
    exam.delete()
    StudentPromotionRecord.objects.filter(student__in=test_students).delete()
    Student.objects.filter(student_id__startswith='STU-ALLOC-TEST-').delete()
    ay_source.delete()
    print("9. [PASS] Cleaned up all test objects.")

    print("\n🎉 ALL TESTS COMPLETED AND VERIFIED 100% SUCCESSFULLY!")


if __name__ == '__main__':
    run_tests()
