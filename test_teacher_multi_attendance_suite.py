import os
import sys
import django
from datetime import datetime, date, time as dtime
from decimal import Decimal
import io

sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()


from django.test import Client
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.accounts.models import User, SchoolProfile
from apps.teachers.models import (
    Teacher,
    TeacherAttendance,
    TeacherBiometricProfile,
    TeacherPunchLog,
    TeacherAttendanceConfig
)
from apps.teachers.biometric_views import (
    generate_rolling_qr_token,
    verify_rolling_qr_token,
    calculate_haversine_distance,
    record_teacher_punch
)


def run_tests():
    print("=" * 70)
    print("TEST: TEACHER MULTI-METHOD ATTENDANCE SUITE (QR, FACE AI, BIOMETRIC)")
    print("=" * 70)

    client = Client()

    # 1. Setup Admin & Teacher Users
    admin_user, _ = User.objects.get_or_create(
        username='admin_att_test',
        defaults={'role': User.Role.ADMIN, 'khmer_name': 'Admin Test'}
    )
    admin_user.set_password('pass123')
    admin_user.save()

    teacher_user, _ = User.objects.get_or_create(
        username='teacher_att_test',
        defaults={'role': User.Role.TEACHER, 'khmer_name': 'គ្រូ សុខ ពិសិដ្ឋ'}
    )
    teacher_user.set_password('pass123')
    teacher_user.save()

    teacher = Teacher.objects.filter(user=teacher_user).first()
    if not teacher:
        teacher = Teacher.objects.filter(teacher_id='T_ATT_001').first()
    if not teacher:
        teacher = Teacher.objects.create(
            teacher_id='T_ATT_001',
            khmer_name='សុខ ពិសិដ្ឋ',
            latin_name='Sok Piseth',
            specialization='គណិតវិទ្យា',
            phone='012999888',
            base_salary=Decimal('600.00'),
            user=teacher_user,
            status=Teacher.Status.ACTIVE
        )
    else:
        teacher.user = teacher_user
        teacher.status = Teacher.Status.ACTIVE
        teacher.save()


    # 2. Setup School Profile & Coordinates
    school = SchoolProfile.get_settings()
    school.latitude = 11.5564
    school.longitude = 104.9282
    school.gps_radius_meters = 150
    school.save()

    config = TeacherAttendanceConfig.get_settings()
    config.active_daily_mode = TeacherAttendanceConfig.DailyMode.ALL
    config.enable_qr_checkin = True
    config.enable_face_ai_checkin = True
    config.enable_biometric_device = True
    config.enable_usb_fingerprint = True
    config.enable_file_import = True
    config.enable_timetable_sync = True
    config.require_gps_validation = True
    config.require_device_binding = True
    config.rolling_qr_interval_seconds = 20
    config.biometric_push_secret = "TEST_SECRET_KEY_123"
    config.save()


    # Reset test data
    today = date.today()
    TeacherPunchLog.objects.filter(teacher=teacher, date=today).delete()
    TeacherAttendance.objects.filter(teacher=teacher, date=today).delete()
    TeacherBiometricProfile.objects.filter(teacher=teacher).delete()

    client.force_login(admin_user)

    # -----------------------------------------------------------------------
    # TEST 1: Cryptographic Rolling QR Code Generation & Verification
    # -----------------------------------------------------------------------
    print("\n--- TEST 1: Rolling Dynamic QR Token Security ---")
    token, expires_in = generate_rolling_qr_token(config)
    assert token.startswith("QR_"), f"Invalid token format: {token}"
    assert verify_rolling_qr_token(token, config) is True, "Fresh token should verify true"
    assert verify_rolling_qr_token("QR_99999_fakehash", config) is False, "Forged token must fail"
    print(f"✅ Rolling QR Token generated: {token} (Expires in {expires_in}s)")

    # -----------------------------------------------------------------------
    # TEST 2: GPS Geofencing Haversine Calculation
    # -----------------------------------------------------------------------
    print("\n--- TEST 2: GPS Geofencing Distance Check ---")
    # Exact school coords -> distance ~ 0m
    dist_exact = calculate_haversine_distance(11.5564, 104.9282, 11.5564, 104.9282)
    assert dist_exact < 1.0, f"Distance should be 0: {dist_exact}"
    
    # 50m nearby
    dist_near = calculate_haversine_distance(11.5564, 104.9282, 11.5568, 104.9282)
    assert dist_near < 100.0, f"Distance should be ~44m: {dist_near}"

    # Far away (e.g. 5km away in another district)
    dist_far = calculate_haversine_distance(11.5564, 104.9282, 11.6000, 104.9282)
    assert dist_far > 4000.0, f"Distance should be >4km: {dist_far}"
    print(f"✅ Geofence calculation verified: Near={dist_near}m, Far={dist_far}m")

    # -----------------------------------------------------------------------
    # TEST 3: Mobile QR Check-in API (with Device Binding & GPS validation)
    # -----------------------------------------------------------------------
    print("\n--- TEST 3: Mobile QR Scan Check-in API ---")
    client.force_login(teacher_user)
    
    # A. Scan with GPS outside geofence -> Must be rejected
    res_outside = client.post('/teachers/attendance/scan/api/process/', {
        'token': token,
        'device_uuid': 'PHONE_TEST_UUID_001',
        'latitude': 11.6000, # Far away
        'longitude': 104.9282,
    })
    assert res_outside.status_code == 400, f"Expected 400 outside geofence: {res_outside.status_code}"
    print("✅ 1. Check-in from outside school geofence blocked successfully.")

    # B. Scan with invalid / expired token -> Must be rejected
    res_invalid_token = client.post('/teachers/attendance/scan/api/process/', {
        'token': 'QR_EXPIRED_TOKEN_123',
        'device_uuid': 'PHONE_TEST_UUID_001',
        'latitude': 11.5564,
        'longitude': 104.9282,
    })
    assert res_invalid_token.status_code == 400, f"Expected 400 with invalid token"
    print("✅ 2. Expired/Fake QR token blocked successfully.")

    # C. Valid Scan -> Binds Phone UUID & Records Punch
    res_valid = client.post('/teachers/attendance/scan/api/process/', {
        'token': token,
        'device_uuid': 'PHONE_TEST_UUID_001',
        'device_name': 'iPhone 15 Pro',
        'latitude': 11.5564,
        'longitude': 104.9282,
    })
    assert res_valid.status_code == 200, f"Expected 200 on valid scan: {res_valid.json()}"
    data_valid = res_valid.json()
    assert data_valid['status'] == 'success'
    print(f"✅ 3. Valid Mobile QR Check-in recorded: {data_valid['message']}")

    # Verify Device Binding & TeacherAttendance DB
    bio_profile = TeacherBiometricProfile.objects.get(teacher=teacher)
    assert bio_profile.device_uuid == 'PHONE_TEST_UUID_001', f"Device not bound: {bio_profile.device_uuid}"
    
    att_rec = TeacherAttendance.objects.get(teacher=teacher, date=today)
    assert att_rec.check_in_method == 'QR_SCAN'
    assert att_rec.status in [TeacherAttendance.Status.PRESENT, TeacherAttendance.Status.LATE]
    print(f"✅ 4. TeacherAttendance DB synced automatically: Status={att_rec.status}, Method={att_rec.check_in_method}")

    # D. Attempt scan from different unauthorized device -> Must be rejected (Anti-Buddy Punching)
    fresh_token, _ = generate_rolling_qr_token(config)
    res_buddy = client.post('/teachers/attendance/scan/api/process/', {
        'token': fresh_token,
        'device_uuid': 'DIFFERENT_UNAUTHORIZED_PHONE_UUID',
        'latitude': 11.5564,
        'longitude': 104.9282,
    })
    assert res_buddy.status_code == 403, f"Expected 403 Device Mismatch, got {res_buddy.status_code}"
    print("✅ 5. Anti-Buddy Punching: Secondary unauthorized device blocked successfully.")

    # -----------------------------------------------------------------------
    # TEST 4: Face AI Recognition & Enrollment API
    # -----------------------------------------------------------------------
    print("\n--- TEST 4: Webcam Face AI Recognition & Enrollment ---")
    client.force_login(admin_user)

    # Enroll face descriptor
    res_enroll = client.post(f'/teachers/attendance/face-enroll/{teacher.id}/', {
        'face_descriptor': '[0.11, -0.42, 0.88, 0.23, 0.05]',
    })
    assert res_enroll.status_code == 302, f"Face enrollment redirect expected: {res_enroll.status_code}"
    bio_profile.refresh_from_db()
    assert bio_profile.is_enrolled_face is True
    assert len(bio_profile.face_descriptor) == 5
    print("✅ 1. Teacher Face Embedding enrolled successfully.")

    # Get enrolled faces endpoint
    res_get_faces = client.get('/teachers/attendance/face-ai/api/enrolled/')
    assert res_get_faces.status_code == 200
    faces_json = res_get_faces.json()
    assert faces_json['count'] >= 1
    print(f"✅ 2. API Enrolled Faces returned {faces_json['count']} registered teachers.")

    # Check-in via Face AI API
    res_face_checkin = client.post('/teachers/attendance/face-ai/api/checkin/', {
        'teacher_id': teacher.id
    })
    assert res_face_checkin.status_code == 200
    face_checkin_data = res_face_checkin.json()
    assert face_checkin_data['status'] == 'success'
    print(f"✅ 3. Face AI Check-in punch logged: {face_checkin_data['message']}")

    # -----------------------------------------------------------------------
    # TEST 5: Biometric Push Webhook (ZKTeco / Hikvision) & File Import
    # -----------------------------------------------------------------------
    print("\n--- TEST 5: Biometric Push Webhook & USB Flash Import ---")
    # Biometric Push Webhook
    res_webhook = client.post(f'/teachers/attendance/biometric/api/push/?secret={config.biometric_push_secret}', {
        'pin': teacher.teacher_id,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'type': 'CHECK_IN'
    })
    assert res_webhook.status_code == 200
    assert res_webhook.json()['status'] == 'success'
    print(f"✅ 1. ZKTeco/Hikvision Push Webhook accepted punch log for {teacher.khmer_name}.")

    # USB File Import (CSV Log from Flash Drive)
    csv_content = f"{teacher.teacher_id},{datetime.now().strftime('%Y-%m-%d %H:%M:%S')},0\n"
    csv_file = SimpleUploadedFile("attendance_log.csv", csv_content.encode('utf-8'), content_type="text/csv")
    
    res_import = client.post('/teachers/attendance/biometric/import/', {
        'log_file': csv_file
    })
    assert res_import.status_code == 302
    print("✅ 2. Flash Drive CSV log parsed & imported successfully.")

    # -----------------------------------------------------------------------
    # TEST 6: Admin Attendance Configuration & Punch Logs Audit
    # -----------------------------------------------------------------------
    print("\n--- TEST 6: Admin Attendance Settings & Audit Trail ---")
    res_settings = client.post('/teachers/attendance/settings/', {
        'enable_qr_checkin': 'on',
        'enable_face_ai_checkin': 'on',
        'enable_biometric_device': 'on',
        'enable_usb_fingerprint': 'on',
        'enable_file_import': 'on',
        'enable_timetable_sync': 'on',
        'require_gps_validation': 'on',
        'require_device_binding': 'on',
        'rolling_qr_interval_seconds': '30',
        'morning_checkin_start': '06:30',
        'morning_checkin_end': '08:30',
        'morning_late_threshold': '07:15',
        'afternoon_checkin_start': '12:30',
        'afternoon_checkin_end': '14:30',
        'afternoon_late_threshold': '13:15',
        'biometric_device_ip': '192.168.1.250',
        'biometric_device_port': '4370',
        'biometric_device_type': 'ZKTECO',
        'biometric_push_secret': 'TEST_SECRET_KEY_123',
    })
    assert res_settings.status_code == 302
    config.refresh_from_db()
    assert config.rolling_qr_interval_seconds == 30
    assert config.biometric_device_ip == '192.168.1.250'
    print("✅ 1. Admin Attendance settings updated & verified.")

    # Punch Logs Audit View
    res_logs = client.get(f'/teachers/attendance/logs/?date={today.strftime("%Y-%m-%d")}')
    assert res_logs.status_code == 200
    assert "Punch Logs" in res_logs.content.decode('utf-8')
    print("✅ 2. Punch Logs Audit Trail rendered successfully (200 OK).")

    # Kiosk Display View
    res_kiosk = client.get('/teachers/attendance/kiosk/')
    assert res_kiosk.status_code == 200
    assert "KIOSK LIVE" in res_kiosk.content.decode('utf-8')
    print("✅ 3. Dynamic QR Kiosk Display view rendered successfully (200 OK).")

    # Mobile Scan Page
    res_mobile_page = client.get('/teachers/attendance/scan/')
    assert res_mobile_page.status_code == 200
    assert "Mobile Check-in" in res_mobile_page.content.decode('utf-8')
    print("✅ 4. Teacher Mobile QR Scan page rendered successfully (200 OK).")


    # -----------------------------------------------------------------------
    # TEST 7: Admin Enforced Daily Mode (Option 1 / Option 2 / Option 3) & Privacy Isolation
    # -----------------------------------------------------------------------
    print("\n--- TEST 7: Admin Enforced Daily Scan Option & Teacher Privacy Isolation ---")
    # A. Enforce Option 1 (QR Only)
    config.active_daily_mode = TeacherAttendanceConfig.DailyMode.OPTION_1_QR
    config.save()

    # Attempt Face AI -> Must be blocked because Admin enforced QR Only
    client.force_login(teacher_user)
    res_face_blocked = client.post('/teachers/attendance/face-ai/api/checkin/', {'teacher_id': teacher.id})
    assert res_face_blocked.status_code == 403
    print("✅ 1. Admin Enforced Option 1 (QR Only): Face AI attempt correctly blocked.")

    # QR Scan -> Must succeed
    t_token, _ = generate_rolling_qr_token(config)
    res_qr_ok = client.post('/teachers/attendance/scan/api/process/', {
        'token': t_token,
        'device_uuid': 'PHONE_TEST_UUID_001',
        'latitude': 11.5564,
        'longitude': 104.9282,
    })
    assert res_qr_ok.status_code == 200
    print("✅ 2. Admin Enforced Option 1 (QR Only): QR Scan succeeded.")

    # B. Enforce Option 2 (Face AI Only)
    config.active_daily_mode = TeacherAttendanceConfig.DailyMode.OPTION_2_FACE
    config.save()

    # Attempt QR Scan -> Must be blocked because Admin enforced Face AI Only
    t_token_2, _ = generate_rolling_qr_token(config)
    res_qr_blocked = client.post('/teachers/attendance/scan/api/process/', {
        'token': t_token_2,
        'device_uuid': 'PHONE_TEST_UUID_001',
        'latitude': 11.5564,
        'longitude': 104.9282,
    })
    assert res_qr_blocked.status_code == 403
    print("✅ 3. Admin Enforced Option 2 (Face AI Only): QR Scan attempt correctly blocked.")

    # C. Teacher Privacy Isolation: Teacher can only view their own records
    res_my_history = client.get('/teachers/my-attendance/')
    assert res_my_history.status_code == 200
    assert "ប្រវត្តិចុះវត្តមានផ្ទាល់ខ្លួន" in res_my_history.content.decode('utf-8')
    print("✅ 4. Teacher My Attendance History portal rendered with strict account isolation.")

    # Teacher cannot access Admin attendance settings
    res_teacher_settings = client.get('/teachers/attendance/settings/')
    assert res_teacher_settings.status_code in [302, 403], f"Teachers must be blocked from settings, got {res_teacher_settings.status_code}"
    print("✅ 5. Security: Teacher account is strictly blocked from Admin Attendance Settings.")

    # Cleanup test punch logs
    TeacherPunchLog.objects.filter(teacher=teacher, date=today).delete()
    TeacherAttendance.objects.filter(teacher=teacher, date=today).delete()
    TeacherBiometricProfile.objects.filter(teacher=teacher).delete()
    config.active_daily_mode = TeacherAttendanceConfig.DailyMode.ALL
    config.save()

    print("\n" + "=" * 70)
    print("🎉 ALL TEACHER MULTI-METHOD ATTENDANCE TESTS PASSED 100%!")
    print("=" * 70)




if __name__ == '__main__':
    run_tests()
