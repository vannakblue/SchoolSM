import os
import sys
import django
from datetime import date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from apps.academics.models import AcademicYear, Classroom
from apps.students.models import Student
from apps.students.forms import StudentEnrollmentForm
from apps.students.views import api_check_duplicate_student

User = get_user_model()
rf = RequestFactory()

def run_tests():
    print("=== TESTING SIMULTANEOUS DUAL-RULE DUPLICATE STUDENT DETECTION ===")

    # 1. Setup Academic Year & Classroom
    year, _ = AcademicYear.objects.get_or_create(
        name='2026-2027',
        defaults={'start_date': date(2026, 9, 1), 'end_date': date(2027, 7, 31), 'is_current': True}
    )
    cls, _ = Classroom.objects.get_or_create(
        name='7A',
        academic_year=year,
        defaults={'grade_level': 7, 'code': '7A'}
    )

    # 2. Clean test baseline
    Student.objects.filter(khmer_name__in=['សុខ ចិន្តា', 'កែវ វិបុល', 'ជា សុផាត']).delete()

    # 3. Create baseline student
    st1 = Student.objects.create(
        student_id='269901',
        khmer_name='សុខ ចិន្តា',
        latin_name='SOK CHINDA',
        gender=Student.Gender.FEMALE,
        date_of_birth=date(2012, 5, 15),
        academic_year=year,
        classroom=cls,
        father_name='សុខ ម៉េង',
        father_phone='012999888'
    )
    print(f"[PASS] 1. Created initial student: {st1.khmer_name} (DOB: {st1.date_of_birth}, Father: {st1.father_name})")

    # 4. Test Form Validation: Attempt duplicate enrollment with matching name & DOB
    form_data = {
        'khmer_name': 'សុខ ចិន្តា',
        'latin_name': 'SOK CHINDA',
        'gender': 'F',
        'date_of_birth': '2012-05-15',
        'classroom': cls.id,
        'academic_year': year.id,
        'status': 'ACTIVE',
        'scholarship_type': 'FULL_PAY',
        'father_name': 'សុខ ម៉េង',
        'father_phone': '012999888'
    }
    form = StudentEnrollmentForm(data=form_data, academic_year=year)
    is_valid = form.is_valid()
    assert not is_valid, "Form should fail due to duplicate detection"
    assert "បានចុះឈ្មោះចូលរៀនរួចហើយ" in str(form.errors)
    print("[PASS] 2. StudentEnrollmentForm successfully blocked duplicate registration with detailed Khmer alert message!")

    # 5. Test Form Validation: Different student with same name but different DOB (Allowed)
    form_data_diff_dob = form_data.copy()
    form_data_diff_dob['date_of_birth'] = '2013-08-20'
    form_diff = StudentEnrollmentForm(data=form_data_diff_dob, academic_year=year)
    assert form_diff.is_valid(), f"Different DOB should be allowed, got errors: {form_diff.errors}"
    print("[PASS] 3. Student with same name but different birth date is allowed without collision!")

    # 6. Test Live AJAX API: api_check_duplicate_student
    req = rf.get('/students/api/check-duplicate/', {
        'khmer_name': 'សុខ ចិន្តា',
        'date_of_birth': '2012-05-15',
        'father_name': 'សុខ ម៉េង',
        'father_phone': '012999888',
        'academic_year_id': year.id
    })
    resp = api_check_duplicate_student(req)
    import json
    data = json.loads(resp.content.decode('utf-8'))
    assert data['is_duplicate'] is True
    assert 'សុខ ចិន្តា' in data['message']
    print(f"[PASS] 4. Live AJAX API detected duplicate: {data['message']}")

    # 7. Test Live AJAX API for new unique student
    req_unique = rf.get('/students/api/check-duplicate/', {
        'khmer_name': 'កែវ វិបុល',
        'date_of_birth': '2012-10-10',
        'academic_year_id': year.id
    })
    resp_unique = api_check_duplicate_student(req_unique)
    data_unique = json.loads(resp_unique.content.decode('utf-8'))
    assert data_unique['is_duplicate'] is False
    print("[PASS] 5. Live AJAX API confirmed unique student available for enrollment!")

    # Cleanup
    st1.delete()
    print("=== ALL DUAL-RULE DUPLICATE STUDENT DETECTION TESTS PASSED 100%! ===")

if __name__ == '__main__':
    run_tests()
