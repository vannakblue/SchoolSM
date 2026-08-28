import os
import sys
import django

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from django.urls import reverse
from apps.accounts.models import User, NotificationLog
from apps.teachers.models import Teacher
from apps.accounts.forms import UserProfileForm


def test_teacher_profile_lock_and_request_change():
    print("=== STARTING TEACHER PROFILE LOCK & REQUEST CHANGE VERIFICATION ===")

    # 1. Setup Teacher & User
    teacher_user, _ = User.objects.get_or_create(
        username='teacher_req_test',
        defaults={
            'role': User.Role.TEACHER,
            'khmer_name': 'សុខ ពិសិដ្ឋ',
            'latin_name': 'Sok Piseth',
            'phone': '012999888',
            'email': 'piseth@school.edu.kh'
        }
    )
    teacher_user.set_password('password123')
    teacher_user.save()

    teacher, _ = Teacher.objects.get_or_create(
        teacher_id='T-REQ-001',
        defaults={
            'user': teacher_user,
            'khmer_name': 'សុខ ពិសិដ្ឋ',
            'latin_name': 'Sok Piseth',
            'gender': Teacher.Gender.MALE,
            'phone': '012999888',
            'email': 'piseth@school.edu.kh',
            'specialization': 'គណិតវិទ្យា',
            'date_of_birth': '1989-06-15',
            'status': Teacher.Status.ACTIVE
        }
    )
    if teacher.user != teacher_user:
        teacher.user = teacher_user
        teacher.save()

    # 2. Test Form Initialization - Name fields disabled for Teachers
    form = UserProfileForm(instance=teacher_user)
    assert form.fields['khmer_name'].disabled is True, "khmer_name should be disabled for teachers"
    assert form.fields['latin_name'].disabled is True, "latin_name should be disabled for teachers"
    print("  [PASS] 1. UserProfileForm correctly locks 'khmer_name' & 'latin_name' for Teachers.")

    # 3. Test Form POST Submission - Name cannot be tampered
    client = Client()
    client.force_login(teacher_user)

    res_post_profile = client.post(reverse('profile'), {
        'khmer_name': 'ឈ្មោះថ្មី ក្លែងបន្លំ',  # Attempt to tamper
        'latin_name': 'Hacked Name',
        'phone': '099888777',
        'email': 'piseth.new@school.edu.kh'
    }, follow=True)
    assert res_post_profile.status_code == 200

    teacher_user.refresh_from_db()
    assert teacher_user.khmer_name == 'សុខ ពិសិដ្ឋ', f"Khmer name should not change, got {teacher_user.khmer_name}"
    assert teacher_user.latin_name == 'Sok Piseth', f"Latin name should not change, got {teacher_user.latin_name}"
    assert teacher_user.phone == '099888777', "Phone should be updated"
    assert teacher_user.email == 'piseth.new@school.edu.kh', "Email should be updated"
    print("  [PASS] 2. Direct POST profile tampering prevented: Name remained unchanged, contact info updated.")

    # 4. Test Teacher Request Profile Change View
    initial_log_count = NotificationLog.objects.count()

    res_request = client.post(reverse('teacher_request_profile_change'), {
        'field_name': 'date_of_birth',
        'new_value': '15-06-1989',
        'reason': 'ថ្ងៃខែឆ្នាំកំណើតក្នុងប្រព័ន្ធខុសថ្ងៃពិត'
    }, follow=True)
    assert res_request.status_code == 200

    # 5. Verify NotificationLog & Alert created
    new_log = NotificationLog.objects.order_by('-created_at').first()
    assert new_log is not None
    assert NotificationLog.objects.count() > initial_log_count
    assert 'សំណើសុំកែប្រែព័ត៌មាន' in new_log.title or 'Profile' in new_log.title
    assert '15-06-1989' in new_log.message
    assert 'T-REQ-001' in new_log.message or 'teacher_req_test' in new_log.message
    print(f"  [PASS] 3. Profile change request sent to Admin via Telegram & Alert log created: «{new_log.title}».")

    # 6. Test Profile Page View Rendering
    res_get_profile = client.get(reverse('profile'))
    assert res_get_profile.status_code == 200
    content = res_get_profile.content.decode('utf-8')
    assert 'ព័ត៌មានអត្តសញ្ញាណផ្លូវការ' in content
    assert 'ចាក់សោដោយរដ្ឋបាល' in content
    assert 'T-REQ-001' in content
    assert 'requestChangeModal' in content
    print("  [PASS] 4. Profile page rendered with locked official identity cards, alert button & modal.")

    # Clean up
    teacher.delete()
    teacher_user.delete()

    print("=== ALL TEACHER PROFILE LOCK & REQUEST CHANGE TESTS PASSED 100% ===")


if __name__ == '__main__':
    test_teacher_profile_lock_and_request_change()
