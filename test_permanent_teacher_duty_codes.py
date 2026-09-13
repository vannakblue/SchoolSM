import os
import sys
import django

sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.teachers.models import Teacher
from apps.academics.models import ClassSubject, Classroom, AcademicYear, Timetable, SavedDefaultConfig
from apps.academics.utils import get_teacher_subject_duty_code_map

def run_verification():
    print("=" * 70)
    print("VERIFICATION: TEACHER SUBJECT DUTY CODES PERMANENT DATABASE PERSISTENCE")
    print("=" * 70)

    # 1. Check all 104 teachers in DB
    teachers_with_code = Teacher.objects.filter(subject_code__isnull=False)
    count = teachers_with_code.count()
    print(f"Teachers with subject_code in DB: {count} / 104")
    assert count >= 104, f"Expected at least 104 teachers, found {count}"

    # Sample check
    sample_expected = {
        'កាន ដាវី': 'M1',
        'សា ប៊ុនថន': 'M2',
        'ផាត់ ស្រ៊ុន': 'M11',
        'ផល ឌីណា': 'P1',
        'ដុក ណាសួន': 'C1',
        'សំ ពិសី': 'B1',
        'វ៉ាន់ ម៉ាលីស': 'ES1',
        'សុន វាសនា': 'H1',
        'ទឹម ប៊ុនធន': 'I9G1',
        'ប៊ុន សម្បត្តិ': 'EC1',
        'យ៉េន ចាន់នី': 'HE1',
        'ពឺន ពិដោរ': 'I1',
        'ឃុត បូរាមី': 'K2',
        'ចាន់  ធី': 'E1',
        'ឆេង សុជាតា': 'ED1',
        'ជុំ សុផន': 'AG1',
    }
    for name, expected_code in sample_expected.items():
        t = Teacher.objects.filter(khmer_name=name).first()
        if not t:
            # check normalized
            t = [x for x in Teacher.objects.all() if x.khmer_name.replace(' ', '') == name.replace(' ', '')][0]
        print(f"  [CHECK] {t.khmer_name} (ID: {t.id}) -> code: {t.subject_code} (Expected: {expected_code})")
        assert t.subject_code.upper() == expected_code.upper(), f"Mismatch for {name}: got {t.subject_code}, expected {expected_code}"

    # 2. Check ClassSubject records have teacher_code
    cs_with_code = ClassSubject.objects.filter(teacher_code__isnull=False).count()
    print(f"\nClassSubject records with teacher_code in DB: {cs_with_code}")
    assert cs_with_code >= 500

    # 3. Check get_teacher_subject_duty_code_map helper
    ay = AcademicYear.objects.filter(is_current=True).first()
    code_map, direct_map = get_teacher_subject_duty_code_map(academic_year=ay)
    print(f"get_teacher_subject_duty_code_map entries: code_map={len(code_map)}, direct_map={len(direct_map)}")
    assert len(code_map) > 0
    assert len(direct_map) >= 104

    # 4. Web Views HTTP 200 & Render Verification
    admin_user = User.objects.filter(role='ADMIN').first()
    client = Client()
    client.force_login(admin_user)

    # A. Submenu Teacher Assignments
    res1 = client.get('/academics/teacher-assignments/')
    print(f"GET /academics/teacher-assignments/ -> HTTP {res1.status_code}")
    assert res1.status_code == 200
    content1 = res1.content.decode('utf-8')
    assert 'M1' in content1
    assert 'ចាត់តាំងគ្រូបង្រៀនតាមថ្នាក់ និងមុខវិជ្ជា' in content1
    print(" -> Submenu 'ចាត់តាំងគ្រូបង្រៀនតាមថ្នាក់ និងមុខវិជ្ជា' renders teacher codes properly!")

    # B. Timetable View
    res2 = client.get('/academics/timetable/')
    print(f"GET /academics/timetable/ -> HTTP {res2.status_code}")
    assert res2.status_code == 200
    content2 = res2.content.decode('utf-8')
    assert 'M1' in content2 or 'P1' in content2
    print(" -> Timetable view renders teacher codes properly!")

    # C. Student Teacher Timetable Print View
    res3 = client.get('/academics/timetable/student-teacher/')
    print(f"GET /academics/timetable/student-teacher/ -> HTTP {res3.status_code}")
    assert res3.status_code == 200

    # D. Teacher List & Teacher Detail View
    t_sample = Teacher.objects.filter(subject_code='M1').first()
    res4 = client.get(f'/teachers/{t_sample.id}/')
    print(f"GET /teachers/{t_sample.id}/ -> HTTP {res4.status_code}")
    assert res4.status_code == 200
    content4 = res4.content.decode('utf-8')
    assert 'M1' in content4
    assert 'កូដមុខវិជ្ជាបង្រៀន' in content4
    print(f" -> Teacher detail for {t_sample.khmer_name} displays subject code {t_sample.subject_code}!")

    print("\n" + "=" * 70)
    print("ALL TESTS AND VERIFICATIONS COMPLETED SUCCESSFULLY (100% PASS)!")
    print("=" * 70)

if __name__ == '__main__':
    run_verification()
