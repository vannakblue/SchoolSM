import os
import sys
import django
from datetime import date

sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.examinations.models import StandardizedExam, ExamTerm
from apps.academics.models import AcademicYear, Subject
from apps.academics.utils import get_active_academic_year

def run_tests():
    print("=" * 80)
    print("TEST: ADMIN CAPABILITY TO EDIT AND DELETE EXAM SESSIONS")
    print("=" * 80)

    admin_user = User.objects.filter(role='ADMIN').first()
    assert admin_user is not None, "Admin user must exist"

    client = Client()
    client.force_login(admin_user)
    active_year = get_active_academic_year()

    # -------------------------------------------------------------
    # 1. TEST STANDARDIZED EXAM: CREATE -> EDIT -> DELETE
    # -------------------------------------------------------------
    print("\n--- 1. Testing Standardized Exam Edit & Delete ---")
    exam = StandardizedExam.objects.create(
        academic_year=active_year,
        grade_level=12,
        track='ALL',
        name='ការប្រឡងតេស្តស្តង់ដាសាកល្បង',
        exam_date=date.today(),
        session='MORNING',
        candidates_per_room=25
    )
    exam_id = exam.id
    print(f"✅ Created test Standardized Exam: ID={exam_id}, Name={exam.name}")


    # Edit GET
    res_edit_get = client.get(f'/examinations/standardized/{exam_id}/edit/')
    assert res_edit_get.status_code == 200
    print("✅ GET /examinations/standardized/{id}/edit/ -> 200 OK")

    # Edit POST
    res_edit_post = client.post(f'/examinations/standardized/{exam_id}/edit/', {
        'academic_year': active_year.id,
        'grade_level': 12,
        'track': 'SCIENCE',
        'name': 'ការប្រឡងតេស្តស្តង់ដា (បានកែប្រែថ្មី)',
        'exam_date': date.today().strftime('%Y-%m-%d'),
        'session': 'AFTERNOON',
        'candidates_per_room': 25,
        'description': 'ការកែប្រែដោយ Admin',
        'is_published': 'on'
    }, follow=True)
    assert res_edit_post.status_code == 200
    exam.refresh_from_db()
    assert exam.name == 'ការប្រឡងតេស្តស្តង់ដា (បានកែប្រែថ្មី)'
    assert exam.track == 'SCIENCE'
    assert exam.session == 'AFTERNOON'
    print(f"✅ POST Edit verified: New Name={exam.name}, Track={exam.track}, Session={exam.session}")

    # Delete POST
    res_delete = client.post(f'/examinations/standardized/{exam_id}/delete/', follow=True)
    assert res_delete.status_code == 200
    assert not StandardizedExam.objects.filter(id=exam_id).exists()
    print("✅ POST Delete verified: Standardized Exam deleted successfully from DB.")

    # -------------------------------------------------------------
    # 2. TEST EXAM TERM (MONTHLY / SEMESTER): CREATE -> EDIT -> DELETE
    # -------------------------------------------------------------
    print("\n--- 2. Testing Exam Term (Monthly/Semester) Edit & Delete ---")
    term = ExamTerm.objects.create(
        academic_year=active_year,
        semester=1,
        name='ប្រឡងខែកញ្ញា សាកល្បង',
        term_type='MONTHLY',
        scoring_mode='CLASSROOM',
        start_date=date.today(),
        end_date=date.today(),
        is_counted_in_semester=True
    )
    term_id = term.id
    print(f"✅ Created test Exam Term: ID={term_id}, Name={term.name}")

    # Edit GET
    res_term_edit_get = client.get(f'/examinations/terms/{term_id}/edit/')
    assert res_term_edit_get.status_code == 200
    print("✅ GET /examinations/terms/{id}/edit/ -> 200 OK")

    # Edit POST
    res_term_edit_post = client.post(f'/examinations/terms/{term_id}/edit/', {
        'academic_year': active_year.id,
        'semester': 1,
        'name': 'ប្រឡងខែកញ្ញា (បានកែប្រែ)',
        'term_type': 'MONTHLY',
        'scoring_mode': 'CLASSROOM',
        'start_date': date.today().strftime('%Y-%m-%d'),
        'end_date': date.today().strftime('%Y-%m-%d'),
        'is_counted_in_semester': 'on'
    }, follow=True)
    assert res_term_edit_post.status_code == 200
    term.refresh_from_db()
    assert term.name == 'ប្រឡងខែកញ្ញា (បានកែប្រែ)'
    print(f"✅ POST Edit verified: New Term Name={term.name}")

    # Delete POST
    res_term_delete = client.post(f'/examinations/terms/{term_id}/delete/', follow=True)
    assert res_term_delete.status_code == 200
    assert not ExamTerm.objects.filter(id=term_id).exists()
    print("✅ POST Delete verified: Exam Term deleted successfully from DB.")

    print("\n" + "=" * 80)
    print("🎉 ALL EXAM EDIT AND DELETE TESTS PASSED 100%!")
    print("=" * 80)

if __name__ == '__main__':
    run_tests()
