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
from apps.accounts.models import User, DirectChatMessage, NotificationLog
from apps.teachers.models import Teacher


def test_two_way_teacher_admin_chat():
    print("=== STARTING TWO-WAY TEACHER-ADMIN DIRECT CHAT VERIFICATION ===")

    # 1. Setup Admin User
    admin_user, _ = User.objects.get_or_create(
        username='admin_chat_tester',
        defaults={'role': User.Role.ADMIN, 'khmer_name': 'Admin Tester'}
    )
    admin_user.set_password('password123')
    admin_user.save()

    # 2. Setup Teacher A & Teacher B
    teacher_a_user, _ = User.objects.get_or_create(
        username='teacher_a_chat',
        defaults={'role': User.Role.TEACHER, 'khmer_name': 'គ្រូ វ៉ាន់នី', 'latin_name': 'Vanny', 'phone': '012111222'}
    )
    teacher_a_user.set_password('password123')
    teacher_a_user.save()

    teacher_a, _ = Teacher.objects.get_or_create(
        teacher_id='T-CHAT-001',
        defaults={
            'user': teacher_a_user,
            'khmer_name': 'គ្រូ វ៉ាន់នី',
            'latin_name': 'Vanny',
            'gender': Teacher.Gender.FEMALE,
            'phone': '012111222',
            'specialization': 'ភាសាខ្មែរ',
            'status': Teacher.Status.ACTIVE
        }
    )

    teacher_b_user, _ = User.objects.get_or_create(
        username='teacher_b_chat',
        defaults={'role': User.Role.TEACHER, 'khmer_name': 'គ្រូ បូរ៉ា', 'latin_name': 'Bora', 'phone': '096333444'}
    )
    teacher_b_user.set_password('password123')
    teacher_b_user.save()

    teacher_b, _ = Teacher.objects.get_or_create(
        teacher_id='T-CHAT-002',
        defaults={
            'user': teacher_b_user,
            'khmer_name': 'គ្រូ បូរ៉ា',
            'latin_name': 'Bora',
            'gender': Teacher.Gender.MALE,
            'phone': '096333444',
            'specialization': 'គណិតវិទ្យា',
            'status': Teacher.Status.ACTIVE
        }
    )

    client_teacher_a = Client()
    client_teacher_a.force_login(teacher_a_user)

    client_teacher_b = Client()
    client_teacher_b.force_login(teacher_b_user)

    client_admin = Client()
    client_admin.force_login(admin_user)

    # 3. Teacher A sends a profile correction request to Admin
    req_a = {
        'message': 'សូម Admin ជួយកែប្រែថ្ងៃខែឆ្នាំកំណើតរបស់ខ្ញុំទៅជា 12-05-1990',
        'category': 'profile_correction'
    }
    res_a_send = client_teacher_a.post(
        reverse('api_pop_chat_send'),
        data=json.dumps(req_a),
        content_type='application/json'
    )
    assert res_a_send.status_code == 200
    data_a = res_a_send.json()
    assert data_a['status'] == 'success'
    print("  [PASS] 1. Teacher A successfully sent request to Admin.")

    # 4. Admin checks conversation threads list
    res_threads = client_admin.get(reverse('api_pop_chat_threads'))
    assert res_threads.status_code == 200
    threads_data = res_threads.json()
    assert threads_data['status'] == 'success'
    assert len(threads_data['threads']) >= 1

    thread_a = next((t for t in threads_data['threads'] if t['user_id'] == teacher_a_user.id), None)
    assert thread_a is not None, "Teacher A should appear in Admin inbox threads"
    assert thread_a['unread_count'] >= 1, "Teacher A thread should have unread count"
    assert '12-05-1990' in thread_a['last_message']
    print(f"  [PASS] 2. Admin inbox lists Teacher A with unread count ({thread_a['unread_count']}) and message preview.")

    # 5. Admin opens Teacher A's 1-on-1 thread
    res_history_admin = client_admin.get(f"{reverse('api_pop_chat_history')}?target_user_id={teacher_a_user.id}")
    assert res_history_admin.status_code == 200
    hist_a = res_history_admin.json()
    assert len(hist_a['messages']) >= 1
    assert '12-05-1990' in hist_a['messages'][-1]['message']
    print("  [PASS] 3. Admin opened Teacher A's thread and verified incoming request.")

    # 6. Admin replies directly to Teacher A
    reply_payload = {
        'message': 'ខ្ញុំបានកែប្រែថ្ងៃខែឆ្នាំកំណើតជូនលោកគ្រូ/អ្នកគ្រូរួចរាល់ហើយ!',
        'target_user_id': teacher_a_user.id,
        'category': 'admin_response'
    }
    res_admin_reply = client_admin.post(
        reverse('api_pop_chat_send'),
        data=json.dumps(reply_payload),
        content_type='application/json'
    )
    assert res_admin_reply.status_code == 200
    print("  [PASS] 4. Admin sent direct 1-on-1 reply to Teacher A.")

    # 7. Teacher A checks their Pop Chat history
    res_teacher_a_history = client_teacher_a.get(reverse('api_pop_chat_history'))
    assert res_teacher_a_history.status_code == 200
    msgs_for_a = res_teacher_a_history.json()['messages']
    assert len(msgs_for_a) >= 2
    assert any('បានកែប្រែ' in m['message'] for m in msgs_for_a), "Teacher A should see Admin's direct reply"
    print("  [PASS] 5. Teacher A received Admin's direct reply in their personal Pop Chat thread.")

    # 8. Teacher B checks their Pop Chat history -> Should NOT see Teacher A's conversation
    res_teacher_b_history = client_teacher_b.get(reverse('api_pop_chat_history'))
    assert res_teacher_b_history.status_code == 200
    msgs_for_b = res_teacher_b_history.json()['messages']
    assert not any('12-05-1990' in m['message'] for m in msgs_for_b), "Teacher B must not see Teacher A's messages"
    print("  [PASS] 6. Teacher B thread privacy verified (Zero data leak between teachers).")

    # Clean up test records
    DirectChatMessage.objects.filter(sender__in=[admin_user, teacher_a_user, teacher_b_user]).delete()
    DirectChatMessage.objects.filter(recipient__in=[admin_user, teacher_a_user, teacher_b_user]).delete()
    teacher_a.delete()
    teacher_a_user.delete()
    teacher_b.delete()
    teacher_b_user.delete()
    admin_user.delete()

    print("=== ALL TWO-WAY TEACHER-ADMIN CHAT TESTS PASSED 100% ===")


if __name__ == '__main__':
    test_two_way_teacher_admin_chat()
