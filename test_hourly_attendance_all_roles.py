import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.academics.models import Classroom, AcademicYear, Subject
from apps.students.models import Student
from apps.attendance.models import StudentAttendance, AttendanceSubmissionLog
from datetime import date
from rest_framework_simplejwt.tokens import RefreshToken


def run_tests():
    print("=== Testing Hourly Attendance Across Web & Mobile for Admin, Teacher, Accountant ===")
    
    # Setup test users
    admin_user, _ = User.objects.get_or_create(
        username='test_admin_att',
        defaults={'role': User.Role.ADMIN, 'first_name': 'Test', 'last_name': 'Admin'}
    )
    admin_user.set_password('pass123')
    admin_user.role = User.Role.ADMIN
    admin_user.save()

    accountant_user, _ = User.objects.get_or_create(
        username='test_accountant_att',
        defaults={'role': User.Role.ACCOUNTANT, 'first_name': 'Test', 'last_name': 'Accountant'}
    )
    accountant_user.set_password('pass123')
    accountant_user.role = User.Role.ACCOUNTANT
    accountant_user.save()

    teacher_user, _ = User.objects.get_or_create(
        username='test_teacher_att',
        defaults={'role': User.Role.TEACHER, 'first_name': 'Test', 'last_name': 'Teacher'}
    )
    teacher_user.set_password('pass123')
    teacher_user.role = User.Role.TEACHER
    teacher_user.save()

    student_user, _ = User.objects.get_or_create(
        username='test_student_att',
        defaults={'role': User.Role.STUDENT, 'first_name': 'Test', 'last_name': 'Student'}
    )
    student_user.set_password('pass123')
    student_user.role = User.Role.STUDENT
    student_user.save()

    # Get or create active year & classroom
    year = AcademicYear.objects.first()
    classroom = Classroom.objects.first()
    if not classroom:
        classroom = Classroom.objects.create(name='Class 10A', code='10A', grade_level=10, academic_year=year)

    # Get or create a test student in the classroom
    student = Student.objects.filter(classroom=classroom).first()
    if not student:
        student = Student.objects.create(
            classroom=classroom,
            student_id='STU-TEST-999',
            khmer_name='សុខ តេស្ត',
            latin_name='Sok Test',
            gender='M',
            status='ACTIVE'
        )

    today = date.today()
    client = Client()

    # --- 1. WEB PORTAL TESTS ---
    print("\n--- Testing Web Portal: student_attendance_grid ---")
    
    # 1.1 Admin access
    client.force_login(admin_user)
    resp_admin = client.get(f'/attendance/?classroom={classroom.id}&period=1')
    assert resp_admin.status_code == 200, f"Admin web access failed: {resp_admin.status_code}"
    print("  [PASS] Admin web portal access: HTTP 200")

    # 1.2 Accountant access
    client.force_login(accountant_user)
    resp_acc = client.get(f'/attendance/?classroom={classroom.id}&period=1')
    assert resp_acc.status_code == 200, f"Accountant web access failed: {resp_acc.status_code}"
    print("  [PASS] Accountant web portal access: HTTP 200")

    # 1.3 Teacher access
    client.force_login(teacher_user)
    resp_teacher = client.get(f'/attendance/?classroom={classroom.id}&period=1')
    assert resp_teacher.status_code == 200, f"Teacher web access failed: {resp_teacher.status_code}"
    print("  [PASS] Teacher web portal access: HTTP 200")

    # 1.4 Student access (Must be blocked)
    client.force_login(student_user)
    resp_stu = client.get(f'/attendance/?classroom={classroom.id}&period=1')
    assert resp_stu.status_code in [403, 302], f"Student should be blocked from web portal: {resp_stu.status_code}"
    print("  [PASS] Student unauthorized web access blocked")

    # 1.5 Accountant POST saving attendance on Web Portal
    client.force_login(accountant_user)
    post_data = {
        'classroom': classroom.id,
        'date': today.strftime('%Y-%m-%d'),
        'period': '2',
        'session': 'MORNING',
        f'is_absent_{student.id}': '1',
        f'status_{student.id}': 'ABSENT',
        f'notes_{student.id}': 'អវត្តមានដោយសារឈឺ (Accountant Web Test)',
    }
    resp_post = client.post('/attendance/', post_data, follow=True)
    assert resp_post.status_code == 200, f"Accountant POST web attendance failed: {resp_post.status_code}"
    att_rec = StudentAttendance.objects.filter(student=student, date=today, period_number=2, status='ABSENT').first()
    assert att_rec is not None, "Web attendance record not found in DB!"
    assert att_rec.recorded_by == accountant_user, "recorded_by should be accountant!"
    print("  [PASS] Accountant Web attendance saving & enforcement verified in DB!")

    # --- 2. MOBILE API TESTS ---
    print("\n--- Testing Mobile API: Hourly Attendance Endpoints ---")
    
    # 2.1 Meta API for Admin, Accountant, Teacher
    for u, role_name in [(admin_user, "Admin"), (accountant_user, "Accountant"), (teacher_user, "Teacher")]:
        token = str(RefreshToken.for_user(u).access_token)
        resp = client.get('/api/v1/attendance/hourly/meta/', HTTP_AUTHORIZATION=f'Bearer {token}')
        assert resp.status_code == 200, f"{role_name} meta API failed: {resp.status_code}"
        data = resp.json()
        assert data['status'] == 'success'
        assert len(data['periods']) == 8
        assert len(data['classrooms']) > 0
        print(f"  [PASS] Mobile API meta endpoint for {role_name}: OK (8 periods, {len(data['classrooms'])} classrooms)")

    # 2.2 Roster API
    acc_token = str(RefreshToken.for_user(accountant_user).access_token)
    roster_resp = client.get(
        f'/api/v1/attendance/hourly/roster/?classroom_id={classroom.id}&period_number=2&date={today.strftime("%Y-%m-%d")}',
        HTTP_AUTHORIZATION=f'Bearer {acc_token}'
    )
    assert roster_resp.status_code == 200, f"Roster API failed: {roster_resp.status_code}"
    r_data = roster_resp.json()
    assert r_data['status'] == 'success'
    assert len(r_data['students']) > 0
    stu_entry = next((s for s in r_data['students'] if s['id'] == student.id), None)
    assert stu_entry is not None
    assert stu_entry['status'] == 'ABSENT'
    print(f"  [PASS] Mobile API roster endpoint returned {len(r_data['students'])} students with accurate saved status")

    # 2.3 Save API (Marking Permission via Mobile API)
    save_payload = {
        'classroom_id': classroom.id,
        'date': today.strftime('%Y-%m-%d'),
        'period_number': 3,
        'session': 'MORNING',
        'notify_parents': False,
        'attendances': [
            {
                'student_id': student.id,
                'status': 'PERMISSION',
                'notes': 'សុំច្បាប់មើលថែម្តាយឈឺ'
            }
        ]
    }
    save_resp = client.post(
        '/api/v1/attendance/hourly/save/',
        save_payload,
        content_type='application/json',
        HTTP_AUTHORIZATION=f'Bearer {acc_token}'
    )
    assert save_resp.status_code == 200, f"Save API failed: {save_resp.status_code}"
    s_data = save_resp.json()
    assert s_data['status'] == 'success'
    assert s_data['summary']['permission_count'] == 1

    perm_rec = StudentAttendance.objects.filter(student=student, date=today, period_number=3, status='PERMISSION').first()
    assert perm_rec is not None, "Permission attendance record not found in DB!"
    assert perm_rec.notes == 'សុំច្បាប់មើលថែម្តាយឈឺ'
    assert perm_rec.recorded_by == accountant_user
    print("  [PASS] Mobile API save endpoint recorded PERMISSION with custom note successfully!")

    # 2.4 Mark PRESENT (deletes absence record)
    save_present_payload = {
        'classroom_id': classroom.id,
        'date': today.strftime('%Y-%m-%d'),
        'period_number': 3,
        'session': 'MORNING',
        'attendances': [
            {
                'student_id': student.id,
                'status': 'PRESENT',
                'notes': ''
            }
        ]
    }
    save_resp2 = client.post(
        '/api/v1/attendance/hourly/save/',
        save_present_payload,
        content_type='application/json',
        HTTP_AUTHORIZATION=f'Bearer {acc_token}'
    )
    assert save_resp2.status_code == 200
    perm_rec_after = StudentAttendance.objects.filter(student=student, date=today, period_number=3).first()
    assert perm_rec_after is None, "Student record should be cleaned up when marked PRESENT!"
    print("  [PASS] Mobile API save endpoint cleanly removed absence record when marked PRESENT!")

    # 2.5 Unauthorized student check on Mobile API
    stu_token = str(RefreshToken.for_user(student_user).access_token)
    stu_save_resp = client.post(
        '/api/v1/attendance/hourly/save/',
        save_payload,
        content_type='application/json',
        HTTP_AUTHORIZATION=f'Bearer {stu_token}'
    )
    assert stu_save_resp.status_code == 403, f"Student should be 403 Forbidden: {stu_save_resp.status_code}"
    print("  [PASS] Mobile API properly blocked student role (HTTP 403 Forbidden)")

    print("\n========================================================")
    print("ALL TESTS PASSED SUCCESSFULLY (100% Verification Complete)!")
    print("========================================================")

if __name__ == '__main__':
    run_tests()
