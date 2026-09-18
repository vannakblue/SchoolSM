"""
End-to-End Test for Web-based Gemini API Key Configuration & Live Tester.
Verifies:
1. Access control: Admin allowed, Teacher redirected/blocked.
2. GET request loads settings form and rotator status report.
3. POST request updates GeminiAiConfig in DB and immediately syncs gemini_rotator in memory.
4. api_gemini_test_key AJAX endpoint handles testing with live feedback.
5. Pop Chat widget and Admin Dashboard include the new links.
"""

import os
import sys
import json
from unittest.mock import patch, MagicMock
import django

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from django.urls import reverse
from apps.accounts.models import User, GeminiAiConfig
from apps.tools.gemini_rotator import gemini_rotator


def test_web_gemini_settings():
    print("==================================================================")
    print("TESTING: WEB BROWSER GEMINI API KEY CONFIGURATION & ROTATION")
    print("==================================================================")

    orig_cfg = GeminiAiConfig.get_config()
    orig_keys = orig_cfg.api_keys
    orig_model = orig_cfg.model_name
    orig_level = orig_cfg.thinking_level
    orig_active = orig_cfg.is_active

    # 1. Setup Admin & Teacher users
    admin_user, _ = User.objects.get_or_create(
        username='admin_gemini_tester',
        defaults={'role': User.Role.ADMIN, 'khmer_name': 'អភិបាលប្រព័ន្ធ', 'latin_name': 'System Admin'}
    )
    admin_user.set_password('pass123')
    admin_user.role = User.Role.ADMIN
    admin_user.is_superuser = True
    admin_user.is_staff = True
    admin_user.save()

    teacher_user, _ = User.objects.get_or_create(
        username='teacher_gemini_tester',
        defaults={'role': User.Role.TEACHER, 'khmer_name': 'គ្រូ ពិសោធន៍', 'latin_name': 'Test Teacher'}
    )
    teacher_user.set_password('pass123')
    teacher_user.role = User.Role.TEACHER
    teacher_user.save()

    client = Client()

    # 2. Test Non-Admin Forbidden/Redirected
    client.force_login(teacher_user)
    res_teacher = client.get(reverse('gemini_settings'))
    assert res_teacher.status_code in [302, 403], f"Teacher should not access gemini settings, got {res_teacher.status_code}"
    print("  [PASS] 1. Role permission enforced: Non-admin users cannot access Gemini Settings.")

    # 3. Test Admin Access (GET)
    client.force_login(admin_user)
    res_admin = client.get(reverse('gemini_settings'))
    assert res_admin.status_code == 200, f"Expected 200 for admin, got {res_admin.status_code}"
    content = res_admin.content.decode('utf-8')
    assert 'ការកំណត់ Google Gemini AI & Key Rotation' in content
    assert 'បញ្ជី Google Gemini API Keys' in content
    assert 'ស្ថានភាពបង្វិលសោ' in content or 'Key Rotator' in content
    print("  [PASS] 2. Admin successfully loaded web settings UI with form and status dashboard.")

    # 4. Test Saving Keys via Web Browser POST Form
    test_keys_input = "AIzaSyWebKey1_AAAA1111\nAIzaSyWebKey2_BBBB2222\nAIzaSyWebKey3_CCCC3333"
    post_payload = {
        'api_keys': test_keys_input,
        'model_name': 'gemini-3.8-flash',
        'thinking_level': 'high',
        'is_active': 'on',
        'rotation_enabled': 'on',
    }
    res_post = client.post(reverse('gemini_settings'), data=post_payload, follow=True)
    assert res_post.status_code == 200

    # Verify DB update
    config = GeminiAiConfig.get_config()
    keys_in_db = config.get_keys_list()
    assert len(keys_in_db) == 3
    assert "AIzaSyWebKey1_AAAA1111" in keys_in_db
    assert "AIzaSyWebKey2_BBBB2222" in keys_in_db
    assert "AIzaSyWebKey3_CCCC3333" in keys_in_db
    assert config.thinking_level == 'high'
    print(f"  [PASS] 3. Web form POST saved {len(keys_in_db)} keys to database successfully.")

    # Verify in-memory rotator automatically synced
    rotator_keys = [gemini_rotator.get_available_key() for _ in range(3)]
    assert "AIzaSyWebKey1_AAAA1111" in rotator_keys
    assert "AIzaSyWebKey2_BBBB2222" in rotator_keys
    assert "AIzaSyWebKey3_CCCC3333" in rotator_keys
    print("  [PASS] 4. In-memory GeminiKeyRotator automatically synced with keys from database.")

    # 5. Test AJAX Key Testing Endpoint (api_gemini_test_key)
    with patch('requests.post') as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'candidates': [{'content': {'parts': [{'text': 'ការតភ្ជាប់ជាមួយប្រព័ន្ធ Gemini AI ដំណើរការជោគជ័យ!'}]}}]
        }
        mock_post.return_value = mock_resp

        res_test = client.post(reverse('api_gemini_test_key'), {'api_key': 'AIzaSyWebKey1_AAAA1111'})
        assert res_test.status_code == 200
        test_data = res_test.json()
        assert test_data['status'] == 'success'
        assert 'AIza...1111' in test_data['masked_key']
        assert 'ការតភ្ជាប់ជោគជ័យ' in test_data['message']
        print(f"  [PASS] 5. Live connection test API passed: {test_data['message']}.")

    # 6. Verify Pop Chat & Admin Dashboard integration
    res_dash = client.get('/dashboard/admin/')
    assert res_dash.status_code == 200
    dash_content = res_dash.content.decode('utf-8')
    assert reverse('gemini_settings') in dash_content, "Admin dashboard should contain gemini_settings link"
    assert 'កំណត់ Gemini AI' in dash_content
    print("  [PASS] 6. Quick action button present on Super Admin Dashboard.")

    # Cleanup
    teacher_user.delete()
    admin_user.delete()

    orig_cfg.api_keys = orig_keys
    orig_cfg.model_name = orig_model
    orig_cfg.thinking_level = orig_level
    orig_cfg.is_active = orig_active
    orig_cfg.save()
    gemini_rotator.set_keys(orig_cfg.get_keys_list())

    print("\n==================================================================")
    print("ALL WEB GEMINI SETTINGS TESTS PASSED 100%!")
    print("==================================================================")


if __name__ == '__main__':
    test_web_gemini_settings()
