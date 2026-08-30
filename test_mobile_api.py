import os
import sys
import django

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.teachers.models import Teacher, TeacherAttendance
from apps.students.models import Student
from apps.attendance.models import StudentAttendance
from apps.mobile_api.models import DeviceFCMToken, MobileNotificationLog

def test_mobile_apis():
    client = Client()

    # 1. Test Login with Admin (password 1627)
    print("Testing Mobile Login API...")
    resp = client.post('/api/v1/auth/login/', {
        'username': 'admin',
        'password': '1627',
        'device_token': 'fcm_test_device_token_abc123',
        'device_type': 'android',
        'device_name': 'Samsung Galaxy S24',
        'app_version': '1.0.0'
    }, content_type='application/json')

    print(f"Login HTTP Status: {resp.status_code}")
    data = resp.json()
    assert resp.status_code == 200, f"Login failed: {data}"
    assert 'tokens' in data, "No tokens in response"
    assert 'access' in data['tokens'], "No access token"
    access_token = data['tokens']['access']
    print(f"✅ Login successful! Access Token: {access_token[:25]}...")
    print(f"User: {data['user']['display_name']} ({data['user']['role_display']})")

    # Verify FCM token saved
    token_obj = DeviceFCMToken.objects.filter(token='fcm_test_device_token_abc123').first()
    assert token_obj is not None, "FCM token was not recorded"
    print(f"✅ FCM Token recorded: {token_obj}")

    headers = {'HTTP_AUTHORIZATION': f'Bearer {access_token}'}

    # 2. Test Profile API
    print("\nTesting Profile API...")
    resp = client.get('/api/v1/profile/', **headers)
    assert resp.status_code == 200
    pdata = resp.json()
    print(f"✅ Profile API OK: {pdata['user']['username']}")

    # 3. Test Dashboard Summary API
    print("\nTesting Dashboard Summary API...")
    resp = client.get('/api/v1/dashboard/', **headers)
    assert resp.status_code == 200
    ddata = resp.json()
    print(f"✅ Dashboard Summary API OK: {ddata['dashboard']}")

    # 4. Test QR Attendance Scan API
    print("\nTesting QR Attendance Scan API...")
    # Find any teacher or student
    teacher = Teacher.objects.first()
    if teacher:
        resp = client.post('/api/v1/attendance/qr-scan/', {
            'qr_code': teacher.teacher_id,
            'scan_type': 'TEACHER'
        }, content_type='application/json', **headers)
        print(f"Teacher QR Scan Response: {resp.json()}")
        assert resp.status_code == 200

    student = Student.objects.first()
    if student:
        resp = client.post('/api/v1/attendance/qr-scan/', {
            'qr_code': student.student_id,
            'scan_type': 'STUDENT'
        }, content_type='application/json', **headers)
        print(f"Student QR Scan Response: {resp.json()}")
        assert resp.status_code == 200

    # 5. Test Timetable API
    print("\nTesting Timetable API...")
    resp = client.get('/api/v1/timetable/', **headers)
    assert resp.status_code == 200
    print(f"✅ Timetable API OK: Count = {len(resp.json().get('timetable', []))}")

    # 6. Test Grades API
    print("\nTesting Grades API...")
    resp = client.get('/api/v1/grades/', **headers)
    assert resp.status_code == 200
    print(f"✅ Grades API OK: Count = {len(resp.json().get('scores', []))}")

    # 7. Test Notifications API
    print("\nTesting Notifications API...")
    # Log a dummy notification
    admin_user = User.objects.filter(username='admin').first()
    MobileNotificationLog.objects.create(
        user=admin_user,
        title="ដំណឹងបន្ទាន់",
        body="សូមអញ្ជើញលោកគ្រូអ្នកគ្រូចូលរួមកិច្ចប្រជុំថ្ងៃស្អែក"
    )
    resp = client.get('/api/v1/notifications/', **headers)
    assert resp.status_code == 200
    ndata = resp.json()
    assert ndata['unread_count'] > 0
    print(f"✅ Notifications API OK: Unread = {ndata['unread_count']}")

    # Mark as read
    resp = client.post('/api/v1/notifications/', **headers)
    assert resp.status_code == 200
    print("✅ Mark notifications read OK")

    print("\n=======================================================")
    print("🎉 ALL MOBILE REST API ENDPOINTS VERIFIED SUCCESSFULLY!")
    print("=======================================================")

if __name__ == '__main__':
    test_mobile_apis()
