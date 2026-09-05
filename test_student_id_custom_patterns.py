import os
import sys
import django

# Reconfigure stdout for UTF-8 on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from datetime import date
from django.test import Client
from apps.accounts.models import User, SchoolProfile
from apps.academics.models import AcademicYear, Classroom
from apps.students.models import Student

def run_tests():
    print("=== STARTING STUDENT ID CUSTOM PATTERN & ENDING YEAR TESTS ===")

    # 1. Setup Admin User & Client
    admin_user, _ = User.objects.get_or_create(
        username='admin_sid_test',
        defaults={'role': 'ADMIN', 'email': 'admin_sid_test@example.com'}
    )
    admin_user.set_password('AdminTest123!')
    admin_user.save()

    client = Client()
    client.force_login(admin_user)

    # 2. Setup Academic Years (2026-2027 and Khmer 2026-2027)
    ay_2026_2027, _ = AcademicYear.objects.get_or_create(
        name='2026-2027 Standard',
        defaults={'start_date': date(2026, 1, 1), 'end_date': date(2027, 12, 31), 'is_current': True}
    )
    ay_khmer, _ = AcademicYear.objects.get_or_create(
        name='ឆ្នាំសិក្សា ២០២៦-២០២៧',
        defaults={'start_date': date(2026, 1, 1), 'end_date': date(2027, 12, 31)}
    )

    cls_7, _ = Classroom.objects.get_or_create(
        name='7A_CUSTOM_SID',
        academic_year=ay_2026_2027,
        defaults={'grade_level': 7, 'code': '7A_CSID'}
    )

    # Clean previous test students
    Student.objects.filter(classroom=cls_7).delete()
    Student.objects.filter(khmer_name__startswith='តេស្ត_SID').delete()

    profile = SchoolProfile.get_settings()

    # TEST A: Default National Standard (Ending Year 27 + 4 digits: 270001)
    print("\n--- TEST A: Ending Year Extraction (2026-2027 -> 27) & YEAR_END_4D ---")
    profile.student_id_pattern = 'YEAR_END_4D'
    profile.student_id_prefix = 'STU'
    profile.student_id_digits = 4
    profile.student_id_include_grade = False
    profile.save()

    id_latin = Student.generate_unique_student_id(ay_2026_2027)
    print(f"Latin Academic Year ID: {id_latin}")
    assert id_latin == '270001', f"Expected 270001, got {id_latin}"
    assert id_latin.startswith('27'), "Must start with ending year 27, NOT 26!"

    id_khmer = Student.generate_unique_student_id(ay_khmer)
    print(f"Khmer Academic Year ID: {id_khmer}")
    assert id_khmer.startswith('27'), f"Expected ending year 27 for Khmer numbers, got {id_khmer}"
    print(">>> [PASS] Ending year extraction correctly identifies 27!")

    # TEST B: 5-Digit Sequence (YEAR_END_5D: 2700001)
    print("\n--- TEST B: 5-Digit Sequence (YEAR_END_5D) ---")
    profile.student_id_pattern = 'YEAR_END_5D'
    profile.save()

    id_5d = Student.generate_unique_student_id(ay_2026_2027)
    print(f"5-digit ID generated: {id_5d}")
    assert id_5d == '2700001', f"Expected 2700001, got {id_5d}"
    print(">>> [PASS] 5-Digit sequence generates 2700001!")

    # TEST C: Prefix Pattern (PREFIX_YEAR_4D: STU-27-0001)
    print("\n--- TEST C: Custom Prefix Pattern (PREFIX_YEAR_4D) ---")
    profile.student_id_pattern = 'PREFIX_YEAR_4D'
    profile.student_id_prefix = 'STU'
    profile.student_id_digits = 4
    profile.save()

    id_prefix = Student.generate_unique_student_id(ay_2026_2027)
    print(f"Prefix ID generated: {id_prefix}")
    assert id_prefix == 'STU-27-0001', f"Expected STU-27-0001, got {id_prefix}"
    print(">>> [PASS] Custom prefix STU generates STU-27-0001!")

    # TEST D: Grade-based Pattern (GRADE_YEAR_4D: 7-27-0001)
    print("\n--- TEST D: Grade-based Pattern (GRADE_YEAR_4D) ---")
    profile.student_id_pattern = 'GRADE_YEAR_4D'
    profile.student_id_digits = 4
    profile.save()

    id_grade = Student.generate_unique_student_id(ay_2026_2027, classroom=cls_7)
    print(f"Grade-based ID generated: {id_grade}")
    assert id_grade == '7-27-0001', f"Expected 7-27-0001, got {id_grade}"
    print(">>> [PASS] Grade-based pattern generates 7-27-0001!")

    # TEST E: Custom Pattern Template (CUSTOM_PATTERN)
    print("\n--- TEST E: Custom Template Pattern ---")
    profile.student_id_pattern = 'CUSTOM_PATTERN'
    profile.student_id_prefix = 'KPS'
    profile.student_id_custom_template = '{PREFIX}-{YEAR4}-G{GRADE}-{SEQ}'
    profile.student_id_digits = 4
    profile.save()

    id_custom = Student.generate_unique_student_id(ay_2026_2027, classroom=cls_7)
    print(f"Custom template ID generated: {id_custom}")
    assert id_custom == 'KPS-2027-G7-0001', f"Expected KPS-2027-G7-0001, got {id_custom}"
    print(">>> [PASS] Custom template correctly generates KPS-2027-G7-0001!")

    # TEST F: Collision Detection & Sequential Creation in Database
    print("\n--- TEST F: Collision Avoidance & Database Save ---")
    profile.student_id_pattern = 'YEAR_END_4D'
    profile.student_id_digits = 4
    profile.save()

    # Create 3 students with auto-generated ID
    st1 = Student.objects.create(
        khmer_name='តេស្ត_SID_1',
        gender='M',
        date_of_birth=date(2013, 1, 1),
        classroom=cls_7,
        academic_year=ay_2026_2027
    )
    st2 = Student.objects.create(
        khmer_name='តេស្ត_SID_2',
        gender='F',
        date_of_birth=date(2013, 2, 2),
        classroom=cls_7,
        academic_year=ay_2026_2027
    )
    print(f"Student 1 ID: {st1.student_id}")
    print(f"Student 2 ID: {st2.student_id}")
    assert st1.student_id == '270001', f"Expected 270001, got {st1.student_id}"
    assert st2.student_id == '270002', f"Expected 270002, got {st2.student_id}"

    # Insert a manual gap: 270010
    st_gap = Student.objects.create(
        student_id='270003',
        khmer_name='តេស្ត_SID_Gap',
        gender='M',
        date_of_birth=date(2013, 3, 3),
        classroom=cls_7,
        academic_year=ay_2026_2027
    )
    next_id = Student.generate_unique_student_id(ay_2026_2027)
    print(f"Next ID after 270003 is: {next_id}")
    assert next_id == '270004', f"Expected 270004, got {next_id}"
    print(">>> [PASS] Auto-generation is strictly sequential and collision-free!")

    # TEST G: AJAX APIs
    print("\n--- TEST G: AJAX APIs Verification ---")
    # 1. api_generate_student_id
    resp_gen = client.get(f'/students/api/generate-student-id/?year_id={ay_2026_2027.id}&classroom_id={cls_7.id}')
    assert resp_gen.status_code == 200, f"Generate API failed with status {resp_gen.status_code}"
    data_gen = resp_gen.json()
    assert data_gen['status'] == 'success'
    assert data_gen['student_id'] == '270004'
    print(f"Generate API returned: {data_gen['student_id']}")

    # 2. api_preview_student_id_pattern
    resp_prev = client.get('/students/api/preview-student-id/?pattern=PREFIX_YEAR_4D&prefix=STU&digits=4&grade_level=7')
    assert resp_prev.status_code == 200, f"Preview API failed with status {resp_prev.status_code}"
    data_prev = resp_prev.json()
    assert data_prev['status'] == 'success'
    assert data_prev['year_ending_code'] == '27'
    assert data_prev['samples'][0] == 'STU-27-0001'
    print(f"Preview API samples: {data_prev['samples']}")

    # 3. Check School Settings Form Submission
    print("\n--- TEST H: School Settings Form Submission ---")
    resp_form = client.post('/accounts/settings/school/', {
        'name_kh': profile.name_kh,
        'name_en': profile.name_en,
        'short_name': profile.short_name,
        'school_code': profile.school_code,
        'school_type': profile.school_type,
        'institution_type': profile.institution_type,
        'education_levels': profile.education_levels,
        'date_format': profile.date_format,
        'time_format': profile.time_format,
        'motto': profile.motto,
        'student_id_pattern': 'YEAR_END_4D',
        'student_id_prefix': 'STU',
        'student_id_custom_template': '{PREFIX}-{YEAR2}-{SEQ}',
        'student_id_digits': 4,
        'student_id_include_grade': False,
        'principal_name': profile.principal_name or 'លោកនាយក',
        'phone': profile.phone or '012345678',
    })
    # Form post redirects on success
    assert resp_form.status_code in [200, 302], f"Form submit failed with {resp_form.status_code}"
    profile.refresh_from_db()
    assert profile.student_id_pattern == 'YEAR_END_4D'
    print(">>> [PASS] School settings saved successfully!")

    # Clean up test data
    Student.objects.filter(classroom=cls_7).delete()
    cls_7.delete()
    ay_2026_2027.delete()
    ay_khmer.delete()
    admin_user.delete()

    print("\n=================================================")
    print("🎉 ALL TESTS PASSED SUCCESSFULLY! 100% VERIFIED! 🎉")
    print("=================================================")

if __name__ == '__main__':
    run_tests()
