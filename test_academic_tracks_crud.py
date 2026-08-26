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


def test_tracks_and_grade_levels():
    print("=== STARTING ACADEMIC TRACKS & GRADE LEVELS CRUD VERIFICATION ===")

    admin_user, _ = User.objects.get_or_create(
        username='admin_tracks_tester',
        defaults={'role': User.Role.ADMIN, 'khmer_name': 'Admin Track Tester'}
    )
    ay, _ = AcademicYear.objects.get_or_create(
        name='2026-2027',
        defaults={'start_date': '2026-10-01', 'end_date': '2027-07-31', 'is_current': True}
    )

    client = Client()
    client.force_login(admin_user)

    # 1. Test Admin Adding New Academic Track (e.g., TECH - បច្ចេកទេស & IT)
    track_code = 'TECH_TEST'
    AcademicTrack.objects.filter(code=track_code).delete()

    res_create = client.post(
        reverse('academic_track_create'),
        data={
            'code': track_code,
            'name_kh': 'ថ្នាក់បច្ចេកទេស & វិជ្ជាជីវៈ (Technical Track)',
            'name_en': 'Technical & Vocational Track',
            'is_ajax': '1'
        },
        HTTP_X_REQUESTED_WITH='XMLHttpRequest'
    )
    assert res_create.status_code == 200
    created_track = AcademicTrack.objects.filter(code=track_code).first()
    assert created_track is not None
    print(f"  [PASS] 1. Admin added new Academic Track: «{created_track.name_kh}» (Code: {created_track.code}).")

    # 2. Test Admin Editing Academic Track
    res_edit = client.post(
        reverse('academic_track_edit', kwargs={'pk': created_track.pk}),
        data={
            'code': track_code,
            'name_kh': 'ថ្នាក់បច្ចេកទេស វិស្វកម្ម & IT (Engineering & IT Track)',
            'name_en': 'Engineering & IT Track',
            'order': 5
        }
    )
    created_track.refresh_from_db()
    assert created_track.name_kh == 'ថ្នាក់បច្ចេកទេស វិស្វកម្ម & IT (Engineering & IT Track)'
    print(f"  [PASS] 2. Admin edited Academic Track successfully: «{created_track.name_kh}».")

    # 3. Test Admin Creating Grade Level with this Track (e.g., Grade 10 Tech)
    gl, _ = GradeLevel.objects.update_or_create(
        grade_number=10,
        track=track_code,
        defaults={'name': 'ថ្នាក់ទី ១០ បច្ចេកទេស', 'order': 10}
    )
    assert gl.pk is not None
    print(f"  [PASS] 3. Admin created Grade Level for Grade 10 with Track: «{gl.name}».")

    # 4. Test Grade Level Rules for this Track (e.g., Math max 100)
    sub_math, _ = Subject.objects.get_or_create(code='MATH10', defaults={'name_kh': 'គណិតវិទ្យា', 'name_en': 'Math'})
    rule, _ = GradeLevelRule.objects.update_or_create(
        grade_level=10,
        track=track_code,
        subject=sub_math,
        defaults={'max_score': 100.0}
    )
    assert rule.max_score == 100.0
    print(f"  [PASS] 4. Configured Scoring Rule for Grade 10 Tech: Math = {rule.max_score} pts.")

    # 5. Test Classroom creation with this new custom Track
    classroom = Classroom.objects.create(
        name='10-TECH-1',
        code='10T1',
        grade_level=10,
        track=track_code,
        academic_year=ay
    )
    assert classroom.track == track_code
    print(f"  [PASS] 5. Created Classroom «{classroom.name}» using custom Track «{track_code}».")

    # 6. Test Track Delete Safety Validation (Cannot delete if classroom/grade level is using it)
    res_delete_blocked = client.post(reverse('academic_track_delete', kwargs={'pk': created_track.pk}), follow=True)
    assert AcademicTrack.objects.filter(pk=created_track.pk).exists(), "Track should NOT be deleted when active classrooms/grade levels exist"
    print("  [PASS] 6. Safety guard prevented deleting track while active classrooms are linked.")

    # Clean up classroom and grade level, then test deletion
    classroom.delete()
    gl.delete()
    rule.delete()

    res_delete_success = client.post(reverse('academic_track_delete', kwargs={'pk': created_track.pk}), follow=True)
    assert not AcademicTrack.objects.filter(pk=created_track.pk).exists(), "Track should be deleted after references are cleared"
    print("  [PASS] 7. Admin successfully deleted Academic Track after cleaning references.")

    print("=== ALL ACADEMIC TRACKS & GRADE LEVELS CRUD TESTS PASSED 100% ===")


if __name__ == '__main__':
    test_tracks_and_grade_levels()
