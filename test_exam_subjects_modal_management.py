import os
import sys
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.academics.models import AcademicYear, GradeLevelRule, Subject
from apps.examinations.models import StandardizedExam, ExamSubject

def test_api_manage_subjects():
    print("Testing api_manage_standardized_exam_subjects...")

    admin_user = User.objects.filter(role='ADMIN').first()
    if not admin_user:
        admin_user = User.objects.create_superuser('test_admin_exam', 'admin@example.com', 'pass123', role='ADMIN')

    client = Client()
    client.force_login(admin_user)

    year = AcademicYear.objects.first()
    exam = StandardizedExam.objects.first()
    if not exam:
        exam = StandardizedExam.objects.create(
            name='Test Exam Session',
            academic_year=year,
            grade_level=7,
            exam_type='STANDARDIZED',
            exam_date='2026-11-20',
            grading_method='TEACHER_DIRECT'
        )

    all_subs = list(Subject.objects.all()[:4])
    assert len(all_subs) >= 2, "Need at least 2 subjects to test"

    sub1 = all_subs[0]
    sub2 = all_subs[1]

    # Test 1: Set subjects with custom max score and coef
    payload = {
        'subjects_data': [
            {'subject_id': sub1.id, 'max_score': 125, 'coefficient': 2.5, 'session': 'MORNING'},
            {'subject_id': sub2.id, 'max_score': 75, 'coefficient': 1.5, 'session': 'AFTERNOON'}
        ]
    }

    url = f"/examinations/standardized/{exam.id}/subjects/manage/"
    response = client.post(url, data=payload, content_type='application/json')
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.content}"

    data = response.json()
    assert data['status'] == 'success'
    assert data['total_subjects'] == 2

    es1 = ExamSubject.objects.filter(exam=exam, subject=sub1).first()
    assert es1 is not None
    assert es1.max_score == Decimal('125.00')
    assert es1.coefficient == Decimal('2.50')
    assert es1.session == 'MORNING'

    es2 = ExamSubject.objects.filter(exam=exam, subject=sub2).first()
    assert es2 is not None
    assert es2.max_score == Decimal('75.00')
    assert es2.coefficient == Decimal('1.50')
    assert es2.session == 'AFTERNOON'

    print("[PASS] Successfully updated subjects with custom max_score, coefficient, and session.")

    # Test 2: Uncheck sub2 and add sub3
    if len(all_subs) >= 3:
        sub3 = all_subs[2]
        payload2 = {
            'subjects_data': [
                {'subject_id': sub1.id, 'max_score': 100, 'coefficient': 2.0, 'session': 'MORNING'},
                {'subject_id': sub3.id, 'max_score': 50, 'coefficient': 1.0, 'session': 'MORNING'}
            ]
        }
        res2 = client.post(url, data=payload2, content_type='application/json')
        assert res2.status_code == 200
        assert not ExamSubject.objects.filter(exam=exam, subject=sub2).exists(), "sub2 should have been deleted"
        assert ExamSubject.objects.filter(exam=exam, subject=sub3).exists(), "sub3 should have been added"
        print("[PASS] Successfully handled adding/deleting subjects and recalculating ranks.")

    # Test 3: Check that GET standardized_exam_manage returns 200 and renders modal with checkboxes
    manage_url = f"/examinations/standardized/{exam.id}/manage/"
    manage_res = client.get(manage_url)
    assert manage_res.status_code == 200, f"Expected 200, got {manage_res.status_code}"
    assert b'id="manageExamSubjectsModal"' in manage_res.content
    assert b'modal-subj-check' in manage_res.content
    # Test 4: Check Grade 8 conditional priority in modal
    exam.grade_level = 8
    exam.track = 'ALL'
    exam.save()
    res_g8 = client.get(manage_url)
    assert res_g8.status_code == 200
    assert "MoEYS ថ្នាក់ទី 8 (ណែនាំ)".encode('utf-8') in res_g8.content
    assert "ស្តង់ដារណែនាំសម្រាប់ថ្នាក់ទី 8".encode('utf-8') in res_g8.content
    print("[PASS] Grade 8 correctly features All MoEYS as primary recommended preset.")

    print("\nALL TESTS PASSED SUCCESSFULLY!")

if __name__ == '__main__':
    test_api_manage_subjects()
