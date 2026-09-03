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
from apps.examinations.models import (
    StandardizedExam, ExamTerm, ExamRoom, ExamSubject
)

User = get_user_model()

def run_tests():
    print("=== STARTING EXAM PRESETS & STREAMLINED BATCH ROOM MODAL TEST SUITE ===")

    admin_user, _ = User.objects.get_or_create(
        username='admin_batch_preset_test',
        defaults={'role': 'ADMIN', 'is_staff': True, 'is_superuser': True}
    )
    admin_user.role = 'ADMIN'
    admin_user.save()

    client = Client()
    client.force_login(admin_user)

    from apps.academics.utils import get_active_academic_year
    ay = get_active_academic_year(None) or AcademicYear.objects.filter(is_active=True).first()
    
    # 1. Create Sample ExamTerms (Monthly & Semester 1)
    monthly_term, _ = ExamTerm.objects.get_or_create(
        name='ប្រឡងប្រចាំខែ វិច្ឆិកា',
        academic_year=ay,
        defaults={
            'semester': ExamTerm.Semester.SEMESTER_1,
            'term_type': ExamTerm.TermType.MONTHLY,
            'start_date': datetime.date(2026, 11, 20),
            'end_date': datetime.date(2026, 11, 25)
        }
    )

    semester_term, _ = ExamTerm.objects.get_or_create(
        name='ប្រឡងឆមាសទី១ ផ្លូវការ',
        academic_year=ay,
        defaults={
            'semester': ExamTerm.Semester.SEMESTER_1,
            'term_type': ExamTerm.TermType.SEMESTER_1,
            'start_date': datetime.date(2027, 2, 10),
            'end_date': datetime.date(2027, 2, 15)
        }
    )

    # 2. Test GET exam creation form: check for preset buttons and term options
    create_get_res = client.get('/examinations/standardized/create/')
    assert create_get_res.status_code == 200
    create_html = create_get_res.content.decode('utf-8')
    assert 'selectExamPreset' in create_html
    assert '🎯 តេស្តដើមឆ្នាំ' in create_html
    assert '🎓 ប្រឡងឆមាសទី១' in create_html
    assert '📝 ប្រឡងសាកល្បង' in create_html
    assert 'linked_exam_term_select' in create_html
    assert 'ប្រឡងប្រចាំខែ វិច្ឆិកា' in create_html
    print("1. [PASS] Exam creation form renders all preset categories and linked exam terms.")

    # 3. Test POST exam creation with BASELINE test preset
    StandardizedExam.objects.filter(name__icontains='តេស្តដើមឆ្នាំ ស្វ័យប្រវត្តិ').delete()
    post_res = client.post('/examinations/standardized/create/', {
        'name': 'ការប្រឡងតេស្តដើមឆ្នាំ ស្វ័យប្រវត្តិ',
        'academic_year': ay.id,
        'exam_type': 'BASELINE',
        'selected_grades': ['7', '8'],
        'track': 'ALL',
        'session': 'MORNING',
        'exam_date': '2026-10-05',
        'candidates_per_room': '25'
    })
    assert post_res.status_code in [200, 302]
    
    baseline_exams = StandardizedExam.objects.filter(name__icontains='តេស្តដើមឆ្នាំ ស្វ័យប្រវត្តិ')
    assert baseline_exams.count() == 2
    for be in baseline_exams:
        assert be.exam_type == 'BASELINE'
    print("2. [PASS] Successfully created BASELINE standardized exams across 2 grades.")

    # 4. Test POST exam creation linked to an official MONTHLY ExamTerm
    StandardizedExam.objects.filter(name__icontains='ប្រឡងប្រចាំខែ វិច្ឆិកា ស្តង់ដា').delete()
    post_term_res = client.post('/examinations/standardized/create/', {
        'name': 'ប្រឡងប្រចាំខែ វិច្ឆិកា ស្តង់ដា',
        'academic_year': ay.id,
        'exam_type': 'MONTHLY',
        'exam_term': monthly_term.id,
        'selected_grades': ['12'],
        'track': 'ALL',
        'session': 'MORNING',
        'exam_date': '2026-11-20',
        'candidates_per_room': '25'
    })
    assert post_term_res.status_code in [200, 302]
    monthly_exam = StandardizedExam.objects.filter(name__icontains='ប្រឡងប្រចាំខែ វិច្ឆិកា ស្តង់ដា').first()
    assert monthly_exam is not None
    assert monthly_exam.exam_type == 'MONTHLY'
    assert monthly_exam.exam_term == monthly_term
    print("3. [PASS] Successfully created MONTHLY standardized exam linked to official ExamTerm.")

    # 5. Test GET exam_list: verify streamlined batchGenerateRoomsModal
    list_res = client.get(f'/examinations/standardized/?year={ay.id}')
    assert list_res.status_code == 200
    list_html = list_res.content.decode('utf-8')
    assert 'batch_academic_year_input' in list_html
    assert 'batch_session_key_input' in list_html
    assert 'batch_academic_year_select' not in list_html, "Academic year select should be removed from modal UI"
    assert 'batch_session_select' not in list_html, "Exam session select should be removed from modal UI"
    assert 'openSessionInvigilatorModal' in list_html
    assert 'invigilatorModal_' in list_html
    print("4. [PASS] batchGenerateRoomsModal UI is streamlined and Invigilator Modal is rendered.")

    # 6. Test POST batch rooms partitioning using hidden session_key and academic_year
    # Let's generate rooms for baseline_exams session
    from apps.examinations.views import get_clean_exam_session_title
    clean_title = get_clean_exam_session_title(baseline_exams[0].name)
    session_key = f"{ay.id}_{baseline_exams[0].exam_date}_{clean_title}"

    batch_post_res = client.post('/examinations/standardized/batch-generate-rooms/', {
        'academic_year': ay.id,
        'session_key': session_key,
        'scope': 'ALL_GRADES',
        'numbering_mode': 'CONTINUOUS_IN_SHIFT',
        'candidates_per_room': 25,
        'candidate_order': 'ALPHABETICAL'
    })
    assert batch_post_res.status_code == 302
    print("5. [PASS] batch-generate-rooms completed successfully using hidden session_key.")

    # Clean up
    baseline_exams.delete()
    monthly_exam.delete()
    print("6. [PASS] Cleaned up test data.")

    print("\n=== ALL 6 TESTS PASSED 100%! ===")

if __name__ == '__main__':
    run_tests()
