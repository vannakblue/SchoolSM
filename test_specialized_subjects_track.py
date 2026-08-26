import os
import sys
import django

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from django.urls import reverse
from apps.accounts.models import User
from apps.academics.models import AcademicTrack, GradeLevel, Classroom, AcademicYear, Subject, GradeLevelRule


def test_specialized_subjects_per_track():
    print("=== STARTING SPECIALIZED SUBJECTS PER TRACK (ICT, LAW, ELECTRICITY) TEST ===")

    admin_user, _ = User.objects.get_or_create(
        username='admin_spec_tester',
        defaults={'role': User.Role.ADMIN, 'khmer_name': 'Admin Spec Tester'}
    )
    ay, _ = AcademicYear.objects.get_or_create(
        name='2026-2027',
        defaults={'start_date': '2026-10-01', 'end_date': '2027-07-31', 'is_current': True}
    )

    client = Client()
    client.force_login(admin_user)

    # 1. Create Technical Academic Track
    track_code = 'TECH_SPEC'
    track, _ = AcademicTrack.objects.update_or_create(
        code=track_code,
        defaults={'name_kh': 'ថ្នាក់បច្ចេកទេស & IT', 'name_en': 'Technical & ICT Track', 'order': 10}
    )
    print(f"  [PASS] 1. Configured Academic Track: «{track.name_kh}» (Code: {track.code}).")

    # 2. Admin Creates Specialized Subjects: ICT, Law (ច្បាប់), Electricity (អគ្គិសនី)
    sub_ict, _ = Subject.objects.update_or_create(
        code='SPEC_ICT',
        defaults={'name_kh': 'ព័ត៌មានវិទ្យា & ICT', 'name_en': 'Information & Comm Technology', 'category': 'TECH', 'credit': 3}
    )
    sub_law, _ = Subject.objects.update_or_create(
        code='SPEC_LAW',
        defaults={'name_kh': 'ច្បាប់ទូទៅ & ពាណិជ្ជកម្ម', 'name_en': 'General & Commercial Law', 'category': 'SPECIALIZED', 'credit': 2}
    )
    sub_elec, _ = Subject.objects.update_or_create(
        code='SPEC_ELEC',
        defaults={'name_kh': 'អគ្គិសនី & ថាមពល', 'name_en': 'Electricity & Power Systems', 'category': 'TECH', 'credit': 3}
    )
    sub_math, _ = Subject.objects.get_or_create(code='MATH', defaults={'name_kh': 'គណិតវិទ្យា', 'name_en': 'Mathematics'})

    print(f"  [PASS] 2. Admin created specialized subjects: «{sub_ict.name_kh}», «{sub_law.name_kh}», «{sub_elec.name_kh}».")

    # 3. Create Grade 10 Technical GradeLevel
    gl, _ = GradeLevel.objects.update_or_create(
        grade_number=10,
        track=track_code,
        defaults={'name': 'ថ្នាក់ទី ១០ បច្ចេកទេស', 'order': 10}
    )
    print(f"  [PASS] 3. Created Grade Level: «{gl.name}».")

    # 4. Admin configures specialized scoring rules for Grade 10 Technical Track:
    # - ICT: 100 max score
    # - Law (ច្បាប់): 75 max score
    # - Electricity (អគ្គិសនី): 100 max score
    # - Math: 100 max score
    # (Total Max Score = 375 pts)
    GradeLevelRule.objects.update_or_create(grade_level=10, track=track_code, subject=sub_ict, defaults={'max_score': 100.0, 'weekly_hours': 4})
    GradeLevelRule.objects.update_or_create(grade_level=10, track=track_code, subject=sub_law, defaults={'max_score': 75.0, 'weekly_hours': 2})
    GradeLevelRule.objects.update_or_create(grade_level=10, track=track_code, subject=sub_elec, defaults={'max_score': 100.0, 'weekly_hours': 4})
    GradeLevelRule.objects.update_or_create(grade_level=10, track=track_code, subject=sub_math, defaults={'max_score': 100.0, 'weekly_hours': 4})

    print("  [PASS] 4. Admin configured specific scoring rules for Grade 10 Tech (ICT=100, Law=75, Elec=100, Math=100).")

    # 5. Verify Classroom for Grade 10 Tech automatically gets only these specialized subjects
    classroom = Classroom.objects.create(
        name='10-TECH-01',
        code='10T01',
        grade_level=10,
        track=track_code,
        academic_year=ay
    )

    class_subjects = list(classroom.get_assigned_subjects())
    class_sub_codes = [s.code for s in class_subjects]
    assert 'SPEC_ICT' in class_sub_codes
    assert 'SPEC_LAW' in class_sub_codes
    assert 'SPEC_ELEC' in class_sub_codes
    assert 'MATH' in class_sub_codes
    print(f"  [PASS] 5. Classroom «{classroom.name}» automatically assigned {len(class_subjects)} specialized subjects: {', '.join(s.name_kh for s in class_subjects)}.")

    # 6. Verify Total Max Score for this Technical Classroom = 375.0
    tot_max = classroom.get_total_max_score()
    assert tot_max == 375.0
    print(f"  [PASS] 6. Verified Classroom total max score is exactly {tot_max:.0f} pts (100+75+100+100).")

    # Clean up
    classroom.delete()
    gl.delete()
    GradeLevelRule.objects.filter(grade_level=10, track=track_code).delete()
    track.delete()
    sub_ict.delete()
    sub_law.delete()
    sub_elec.delete()

    print("=== ALL SPECIALIZED SUBJECTS PER TRACK TESTS PASSED 100% ===")


if __name__ == '__main__':
    test_specialized_subjects_per_track()
