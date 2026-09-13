import os
import sys
import django
import json

sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.teachers.models import Teacher, TeacherAttendanceConfig, TeacherPunchLog
from apps.teachers.biometric_views import generate_rolling_qr_token

def run_tests():
    print("=" * 80)
    print("TEST: ADMIN TEACHER ATTENDANCE SCAN CONTROL & DAILY MODE ENFORCEMENT")
    print("=" * 80)

    # 1. Setup Admin User and Teacher User
    admin_user = User.objects.filter(role=User.Role.ADMIN).first()
    if not admin_user:
        admin_user = User.objects.create_superuser(
            username='admin_scan_test',
            password='password123',
            email='admin_scan@schoolsm.kh'
        )

    teacher = Teacher.objects.filter(status=Teacher.Status.ACTIVE).exclude(teacher_id='').first()
    if not teacher:
        teacher = Teacher.objects.filter(status=Teacher.Status.ACTIVE).first()
        if teacher:
            teacher.teacher_id = 'T_SCAN_001'
            teacher.save(update_fields=['teacher_id'])
        else:
            teacher = Teacher.objects.create(
                teacher_id='T_SCAN_001',
                khmer_name='គ្រូ ពិសិដ្ឋ',
                latin_name='Pyseth Teacher',
                gender='M',
                status=Teacher.Status.ACTIVE
            )

    teacher_user = teacher.user
    if not teacher_user:
        teacher_user = User.objects.filter(role=User.Role.TEACHER).first()
        if not teacher_user:
            teacher_user = User.objects.create_user(
                username='teacher_scan_test',
                password='password123',
                role=User.Role.TEACHER
            )
        teacher.user = teacher_user
        teacher.save(update_fields=['user'])

    client = Client()

    # 2. Test GET TeacherAttendanceConfig API
    print("\n[STEP 1] Testing GET /api/v1/attendance/teacher/config/ ...")
    client.force_login(admin_user)
    res = client.get('/api/v1/attendance/teacher/config/')
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.content}"
    data = res.json()
    assert data['status'] == 'success'
    assert 'config' in data
    assert 'daily_mode_choices' in data
    print("  -> Config retrieved successfully:")
    print(f"     enable_qr_checkin: {data['config']['enable_qr_checkin']}")
    print(f"     active_daily_mode: {data['config']['active_daily_mode']}")
    print(f"     choices count: {len(data['daily_mode_choices'])}")

    # 3. Test POST TeacherAttendanceConfig API by Admin (Toggle QR OFF & Set Mode to OPTION_2_FACE)
    print("\n[STEP 2] Testing POST /api/v1/attendance/teacher/config/ to DISABLE QR check-in ...")
    payload = {
        'enable_qr_checkin': False,
        'active_daily_mode': 'OPTION_2_FACE',
        'enable_face_ai_checkin': True,
        'enable_biometric_device': True,
    }
    res = client.post('/api/v1/attendance/teacher/config/', data=json.dumps(payload), content_type='application/json')
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.content}"
    config = TeacherAttendanceConfig.get_settings()
    assert config.enable_qr_checkin is False, "enable_qr_checkin should be False"
    assert config.active_daily_mode == 'OPTION_2_FACE', "active_daily_mode should be OPTION_2_FACE"
    print("  -> Config successfully updated by Admin in DB:")
    print(f"     enable_qr_checkin: {config.enable_qr_checkin}")
    print(f"     active_daily_mode: {config.active_daily_mode}")

    # 4. Test Teacher QR Scan when enable_qr_checkin is FALSE
    print("\n[STEP 3] Testing Teacher QR Scan when Admin disabled QR check-in ...")
    client.force_login(teacher_user)
    # Teacher scanning their own QR code
    scan_res = client.post(
        '/api/v1/attendance/qr-scan/',
        data=json.dumps({'qr_code': teacher.teacher_id, 'scan_type': 'AUTO'}),
        content_type='application/json'
    )
    print(f"  -> Response Status: {scan_res.status_code}")
    print(f"  -> Response Body: {scan_res.json()}")
    assert scan_res.status_code == 403, f"Expected 403 Forbidden, got {scan_res.status_code}"
    res_msg = scan_res.json().get('message', '') or scan_res.json().get('error', '')
    assert "បិទដំណើរការ" in res_msg
    print("  -> PASSED: Teacher scan correctly blocked when QR check-in is disabled by Admin.")

    # 5. Test Teacher QR Scan when QR is enabled BUT active_daily_mode is OPTION_2_FACE (Face AI Only)
    print("\n[STEP 4] Testing Teacher QR Scan when active_daily_mode is OPTION_2_FACE (Face AI Only) ...")
    client.force_login(admin_user)
    payload = {
        'enable_qr_checkin': True,
        'active_daily_mode': 'OPTION_2_FACE',
        'enable_face_ai_checkin': True,
        'enable_biometric_device': True,
    }
    res = client.post('/api/v1/attendance/teacher/config/', data=json.dumps(payload), content_type='application/json')
    assert res.status_code == 200

    client.force_login(teacher_user)
    scan_res = client.post(
        '/api/v1/attendance/qr-scan/',
        data=json.dumps({'qr_code': teacher.teacher_id, 'scan_type': 'AUTO'}),
        content_type='application/json'
    )
    print(f"  -> Response Status: {scan_res.status_code}")
    print(f"  -> Response Body: {scan_res.json()}")
    assert scan_res.status_code == 403, f"Expected 403 Forbidden, got {scan_res.status_code}"
    res_msg = scan_res.json().get('message', '') or scan_res.json().get('error', '')
    assert "Admin បានកំណត់ឱ្យប្រើ" in res_msg
    print("  -> PASSED: Teacher scan correctly blocked when daily method is enforced as Face AI Only.")

    # 6. Test Teacher QR Scan when Admin sets active_daily_mode = OPTION_1_QR (QR Only)
    print("\n[STEP 5] Testing Teacher QR Scan when Admin sets active_daily_mode = OPTION_1_QR ...")
    client.force_login(admin_user)
    payload = {
        'enable_qr_checkin': True,
        'active_daily_mode': 'OPTION_1_QR',
        'enable_face_ai_checkin': False,
        'enable_biometric_device': False,
    }
    res = client.post('/api/v1/attendance/teacher/config/', data=json.dumps(payload), content_type='application/json')
    assert res.status_code == 200

    client.force_login(teacher_user)
    scan_res = client.post(
        '/api/v1/attendance/qr-scan/',
        data=json.dumps({'qr_code': teacher.teacher_id, 'scan_type': 'AUTO'}),
        content_type='application/json'
    )
    print(f"  -> Response Status: {scan_res.status_code}")
    print(f"  -> Response Body: {scan_res.json()}")
    assert scan_res.status_code == 200, f"Expected 200 OK, got {scan_res.status_code}: {scan_res.content}"
    assert scan_res.json().get('type') == 'TEACHER'
    print("  -> PASSED: Teacher scan successfully recorded when OPTION_1_QR is active.")

    # 7. Test Teacher scanning Dynamic Rolling Kiosk QR Token (QR_...)
    print("\n[STEP 6] Testing Teacher scanning Dynamic Rolling Kiosk QR Token ...")
    config = TeacherAttendanceConfig.get_settings()
    rolling_token, _ = generate_rolling_qr_token(config)
    print(f"  -> Generated Rolling Token: {rolling_token}")

    scan_rolling_res = client.post(
        '/api/v1/attendance/qr-scan/',
        data=json.dumps({'qr_code': rolling_token, 'scan_type': 'AUTO'}),
        content_type='application/json'
    )
    print(f"  -> Response Status: {scan_rolling_res.status_code}")
    print(f"  -> Response Body: {scan_rolling_res.json()}")
    assert scan_rolling_res.status_code == 200, f"Expected 200 OK, got {scan_rolling_res.status_code}"
    assert scan_rolling_res.json().get('type') == 'TEACHER'
    print("  -> PASSED: Dynamic Rolling QR token scanned and attendance punch created.")

    # 8. Test Non-Admin cannot modify configuration
    print("\n[STEP 7] Testing security: Non-Admin (Teacher) forbidden from modifying attendance config ...")
    client.force_login(teacher_user)
    hacker_payload = {
        'enable_qr_checkin': False,
        'active_daily_mode': 'OPTION_3_BIOMETRIC',
    }
    forbidden_res = client.post(
        '/api/v1/attendance/teacher/config/',
        data=json.dumps(hacker_payload),
        content_type='application/json'
    )
    print(f"  -> Response Status: {forbidden_res.status_code}")
    assert forbidden_res.status_code == 403, f"Expected 403 Forbidden, got {forbidden_res.status_code}"
    print("  -> PASSED: Non-admin users strictly forbidden from changing attendance configuration.")

    # 9. Reset config to default ALL
    config.enable_qr_checkin = True
    config.enable_face_ai_checkin = True
    config.enable_biometric_device = True
    config.active_daily_mode = TeacherAttendanceConfig.DailyMode.ALL
    config.save()
    print("\n[STEP 8] Reset TeacherAttendanceConfig back to default ALL.")

    print("\n" + "=" * 80)
    print("ALL TESTS PASSED! Admin QR scanning toggle and method selection verified 100%.")
    print("=" * 80)

if __name__ == '__main__':
    run_tests()
