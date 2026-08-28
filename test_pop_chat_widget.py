import os
import sys
import json
import django

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from django.urls import reverse
from apps.accounts.models import User, NotificationLog
from apps.teachers.models import Teacher


def test_pop_chat_widget_system():
    print("=== STARTING ON-SCREEN POP CHAT WIDGET VERIFICATION ===")

    # 1. Setup Test Teacher User
    teacher_user, _ = User.objects.get_or_create(
        username='teacher_popchat_user',
        defaults={
            'role': User.Role.TEACHER,
            'khmer_name': 'អ៊ុក សុផល',
            'latin_name': 'Ouk Sophal',
            'phone': '011223344',
            'email': 'sophal.ouk@school.edu.kh'
        }
    )
    teacher_user.set_password('password123')
    teacher_user.save()

    teacher, _ = Teacher.objects.get_or_create(
        teacher_id='T-POP-007',
        defaults={
            'user': teacher_user,
            'khmer_name': 'អ៊ុក សុផល',
            'latin_name': 'Ouk Sophal',
            'gender': Teacher.Gender.MALE,
            'phone': '011223344',
            'email': 'sophal.ouk@school.edu.kh',
            'specialization': 'ព័ត៌មានវិទ្យា',
            'date_of_birth': '1987-03-20',
            'status': Teacher.Status.ACTIVE
        }
    )
    if teacher.user != teacher_user:
        teacher.user = teacher_user
        teacher.save()

    client = Client()

    # 2. Test Anonymous User Rejected
    res_anon = client.post(reverse('api_pop_chat_send'), {'message': 'Hello'}, content_type='application/json')
    assert res_anon.status_code == 302, "Anonymous user should be redirected to login"
    print("  [PASS] 1. Anonymous access safely blocked (Redirect to login).")

    # 3. Test Teacher Sends Request via Pop Chat
    client.force_login(teacher_user)
    initial_log_count = NotificationLog.objects.count()

    req_payload = {
        'message': 'ខ្ញុំចង់ស្នើសុំកែប្រែថ្ងៃខែឆ្នាំកំណើតទៅជា 20-03-1987 (DOB Correction)',
        'category': 'profile_correction'
    }
    res_send = client.post(
        reverse('api_pop_chat_send'),
        data=json.dumps(req_payload),
        content_type='application/json'
    )
    assert res_send.status_code == 200, f"Expected 200, got {res_send.status_code}"
    data = res_send.json()
    assert data['status'] == 'success'
    assert 'Admin' in data['reply']
    print("  [PASS] 2. Pop Chat POST sent successfully and returned instant confirmation response.")

    # 4. Verify Telegram Alert & NotificationLog Created
    assert NotificationLog.objects.count() > initial_log_count
    latest_log = NotificationLog.objects.order_by('-created_at').first()
    assert latest_log is not None
    assert 'Pop Chat' in latest_log.title or 'Pop Chat' in latest_log.message
    assert 'T-POP-007' in latest_log.message
    assert '20-03-1987' in latest_log.message
    assert 'អ៊ុក សុផល' in latest_log.message
    print(f"  [PASS] 3. Telegram notification alert & log verified: «{latest_log.title}».")

    # 5. Test Pop Chat History API
    res_history = client.get(reverse('api_pop_chat_history'))
    assert res_history.status_code == 200
    hist_data = res_history.json()
    assert hist_data['status'] == 'success'
    assert len(hist_data['history']) > 0
    print(f"  [PASS] 4. Pop Chat history retrieved {len(hist_data['history'])} logs for teacher.")

    # 6. Test Pop Chat Widget Rendered in Base HTML
    res_page = client.get('/dashboard/teacher/')
    assert res_page.status_code == 200
    content = res_page.content.decode('utf-8')
    assert 'id="popChatWidget"' in content, "popChatWidget root container should be present"
    assert 'id="popChatTriggerBtn"' in content, "popChatTriggerBtn button should be present"
    assert 'id="popChatWindow"' in content, "popChatWindow should be present"
    assert 'ជំនួយការ & ស្នើសុំ Admin' in content
    print("  [PASS] 5. Floating Pop Chat widget rendered cleanly in base layout across the screen.")

    # Clean up test records
    teacher.delete()
    teacher_user.delete()

    print("=== ALL ON-SCREEN POP CHAT TESTS PASSED 100% ===")


if __name__ == '__main__':
    test_pop_chat_widget_system()
