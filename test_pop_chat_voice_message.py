import os
import sys
import django

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.accounts.models import User, DirectChatMessage
from apps.teachers.models import Teacher


def test_pop_chat_voice_messaging():
    print("=== STARTING POP CHAT VOICE MESSAGING VERIFICATION ===")

    admin_user, _ = User.objects.get_or_create(
        username='admin_voice_tester',
        defaults={'role': User.Role.ADMIN, 'khmer_name': 'Admin Voice Tester'}
    )
    admin_user.set_password('password123')
    admin_user.save()

    teacher_user, _ = User.objects.get_or_create(
        username='teacher_voice_tester',
        defaults={'role': User.Role.TEACHER, 'khmer_name': 'គ្រូ សំឡេង', 'latin_name': 'Teacher Voice', 'phone': '012555666'}
    )
    teacher_user.set_password('password123')
    teacher_user.save()

    teacher, _ = Teacher.objects.get_or_create(
        teacher_id='T-VOICE-001',
        defaults={
            'user': teacher_user,
            'khmer_name': 'គ្រូ សំឡេង',
            'latin_name': 'Teacher Voice',
            'gender': Teacher.Gender.FEMALE,
            'phone': '012555666',
            'specialization': 'តន្ត្រី',
            'status': Teacher.Status.ACTIVE
        }
    )

    client_teacher = Client()
    client_teacher.force_login(teacher_user)

    client_admin = Client()
    client_admin.force_login(admin_user)

    # 1. Teacher sends a Voice Message
    voice_audio_data = b"RIFF....WAVEfmt ....data...."
    uploaded_voice = SimpleUploadedFile(
        'teacher_voice_req.webm',
        voice_audio_data,
        content_type='audio/webm'
    )

    res_send_voice = client_teacher.post(reverse('api_pop_chat_send'), {
        'voice_file': uploaded_voice,
        'voice_duration': 14,
        'category': 'profile_correction'
    })
    assert res_send_voice.status_code == 200
    data_res = res_send_voice.json()
    assert data_res['status'] == 'success'
    assert 'voice_url' in data_res and data_res['voice_url'] != ''
    assert data_res['voice_duration'] == 14
    print(f"  [PASS] 1. Teacher sent voice audio message ({data_res['voice_duration']}s) -> URL: {data_res['voice_url']}.")

    # 2. Verify voice message stored in DB
    msg_obj = DirectChatMessage.objects.filter(id=data_res['message_id']).first()
    assert msg_obj is not None
    assert msg_obj.voice_file is not None
    assert msg_obj.voice_duration == 14
    print(f"  [PASS] 2. Stored DirectChatMessage record with audio file: {msg_obj.voice_file.name}.")

    # 3. Admin opens teacher's thread and verifies voice message
    res_admin_history = client_admin.get(f"{reverse('api_pop_chat_history')}?target_user_id={teacher_user.id}")
    assert res_admin_history.status_code == 200
    admin_msgs = res_admin_history.json()['messages']
    assert len(admin_msgs) >= 1
    assert admin_msgs[-1]['voice_url'] != ''
    assert admin_msgs[-1]['voice_duration'] == 14
    print("  [PASS] 3. Admin received and verified teacher's voice message in thread.")

    # 4. Admin replies with a Voice Message
    admin_voice_data = b"RIFF....ADMIN_VOICE_REPLY...."
    uploaded_admin_voice = SimpleUploadedFile(
        'admin_voice_reply.webm',
        admin_voice_data,
        content_type='audio/webm'
    )

    res_admin_send = client_admin.post(reverse('api_pop_chat_send'), {
        'voice_file': uploaded_admin_voice,
        'voice_duration': 22,
        'target_user_id': teacher_user.id,
        'category': 'admin_response'
    })
    assert res_admin_send.status_code == 200
    admin_send_data = res_admin_send.json()
    assert admin_send_data['status'] == 'success'
    assert admin_send_data['voice_duration'] == 22
    print(f"  [PASS] 4. Admin sent direct voice message reply ({admin_send_data['voice_duration']}s).")

    # 5. Teacher fetches history and verifies Admin's voice message
    res_teacher_history = client_teacher.get(reverse('api_pop_chat_history'))
    assert res_teacher_history.status_code == 200
    teacher_msgs = res_teacher_history.json()['messages']
    assert len(teacher_msgs) >= 2
    assert teacher_msgs[-1]['is_from_admin'] is True
    assert teacher_msgs[-1]['voice_url'] != ''
    assert teacher_msgs[-1]['voice_duration'] == 22
    print("  [PASS] 5. Teacher received Admin's direct voice reply in Pop Chat.")

    # Clean up test records and uploaded files
    if msg_obj and msg_obj.voice_file:
        try:
            if os.path.exists(msg_obj.voice_file.path):
                os.remove(msg_obj.voice_file.path)
        except Exception:
            pass
    DirectChatMessage.objects.filter(sender__in=[admin_user, teacher_user]).delete()
    DirectChatMessage.objects.filter(recipient__in=[admin_user, teacher_user]).delete()
    teacher.delete()
    teacher_user.delete()
    admin_user.delete()

    print("=== ALL POP CHAT VOICE MESSAGING TESTS PASSED 100% ===")


if __name__ == '__main__':
    test_pop_chat_voice_messaging()
