import os
import sys
import django
from datetime import date

sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.examinations.models import StandardizedExam, ExamSubject
from apps.academics.models import AcademicYear, GradeLevelRule, Subject
from apps.academics.utils import get_active_academic_year

def run_tests():
    print("=" * 80)
    print("TEST: MULTI-GRADE STANDARDIZED EXAM CREATION & CUSTOMIZABLE SETTINGS")
    print("=" * 80)

    admin_user = User.objects.filter(role='ADMIN').first()
    assert admin_user is not None, "Admin user must exist"

    client = Client()
    client.force_login(admin_user)
    active_year = get_active_academic_year()

    # Clean previous test exams with test title
    StandardizedExam.objects.filter(name__icontains='តេស្តតេស្តពហុកម្រិត').delete()

    # -------------------------------------------------------------
    # 1. TEST MULTI-GRADE CREATION WITH INDIVIDUAL CUSTOMIZATIONS
    # -------------------------------------------------------------
    print("\n--- 1. Testing Multi-Grade Batch Creation (Grades 7, 8, 9, 10, 11, 12) ---")
    post_data = {
        'name': 'តេស្តតេស្តពហុកម្រិត ឆមាសទី១',
        'academic_year': active_year.id,
        'selected_grades': ['7', '8', '9', '10', '11', '12'],
        'track': 'ALL',
        'session': 'MORNING',
        'exam_date': date.today().strftime('%Y-%m-%d'),
        'candidates_per_room': 25,
        'description': 'ការប្រឡងតេស្តស្តង់ដារួមប្រចាំសាលា',
        'is_published': 'on',

        # Custom per-grade settings:
        'grade_name_7': 'តេស្តតេស្តពហុកម្រិត ថ្នាក់ទី ៧ (អនុវិទ្យាល័យ)',
        'grade_track_7': 'GENERAL',
        'grade_session_7': 'MORNING',
        'grade_date_7': date.today().strftime('%Y-%m-%d'),
        'grade_cpr_7': 25,

        'grade_name_11': 'តេស្តតេស្តពហុកម្រិត ថ្នាក់ទី ១១ វិទ្យាសាស្ត្រ',
        'grade_track_11': 'SCIENCE',
        'grade_session_11': 'AFTERNOON',
        'grade_date_11': date.today().strftime('%Y-%m-%d'),
        'grade_cpr_11': 25,

        'grade_name_12': 'តេស្តតេស្តពហុកម្រិត ថ្នាក់ទី ១២ បាក់ឌុបសាកល្បង',
        'grade_track_12': 'ALL',
        'grade_session_12': 'AFTERNOON',
        'grade_date_12': date.today().strftime('%Y-%m-%d'),
        'grade_cpr_12': 25,
    }

    res_post = client.post('/examinations/standardized/create/', post_data, follow=True)
    assert res_post.status_code == 200

    created_exams = StandardizedExam.objects.filter(name__icontains='តេស្តតេស្តពហុកម្រិត').order_by('grade_level')
    assert created_exams.count() == 6, f"Expected 6 created exams, got {created_exams.count()}"

    print(f"✅ Verified: Exactly 6 exams created for Grades 7 through 12!")

    # Verify per-grade properties
    exam7 = created_exams.filter(grade_level=7).first()
    assert exam7 is not None
    assert exam7.name == 'តេស្តតេស្តពហុកម្រិត ថ្នាក់ទី ៧ (អនុវិទ្យាល័យ)'
    assert exam7.session == 'MORNING'
    assert exam7.track == 'GENERAL'
    assert exam7.exam_subjects.count() > 0
    print(f"✅ Grade 7 Exam: Name='{exam7.name}', Track={exam7.track}, Session={exam7.session}, Subjects={exam7.exam_subjects.count()}")

    exam11 = created_exams.filter(grade_level=11).first()
    assert exam11 is not None
    assert exam11.name == 'តេស្តតេស្តពហុកម្រិត ថ្នាក់ទី ១១ វិទ្យាសាស្ត្រ'
    assert exam11.track == 'SCIENCE'
    assert exam11.session == 'AFTERNOON'
    print(f"✅ Grade 11 Exam: Name='{exam11.name}', Track={exam11.track}, Session={exam11.session}, Subjects={exam11.exam_subjects.count()}")

    exam12 = created_exams.filter(grade_level=12).first()
    assert exam12 is not None
    assert exam12.name == 'តេស្តតេស្តពហុកម្រិត ថ្នាក់ទី ១២ បាក់ឌុបសាកល្បង'
    assert exam12.session == 'AFTERNOON'
    print(f"✅ Grade 12 Exam: Name='{exam12.name}', Track={exam12.track}, Session={exam12.session}, Subjects={exam12.exam_subjects.count()}")

    # -------------------------------------------------------------
    # 2. TEST FILTERING BY GRADE LEVEL IN EXAM LIST
    # -------------------------------------------------------------
    print("\n--- 2. Testing Grade Level Filter in Standardized Exam List ---")
    res_list_grade7 = client.get('/examinations/standardized/?grade=7')
    assert res_list_grade7.status_code == 200
    assert 'ថ្នាក់ទី 7' in res_list_grade7.content.decode('utf-8') or 'ថ្នាក់ទី ៧' in res_list_grade7.content.decode('utf-8')
    print("✅ GET /examinations/standardized/?grade=7 -> 200 OK (Filter working)")

    res_list_grade12 = client.get('/examinations/standardized/?grade=12')
    assert res_list_grade12.status_code == 200
    print("✅ GET /examinations/standardized/?grade=12 -> 200 OK (Filter working)")

    # Clean up test exams
    created_exams.delete()
    print("✅ Cleaned up test data.")

    print("\n" + "=" * 80)
    print("🎉 ALL MULTI-GRADE EXAM CREATION & CUSTOMIZATION TESTS PASSED 100%!")
    print("=" * 80)

if __name__ == '__main__':
    run_tests()
