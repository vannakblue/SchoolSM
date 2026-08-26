import os
import sys
import django
from datetime import date, datetime, timedelta, time

sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.teachers.models import Teacher, TeacherLeaveRequest, TeacherAttendanceConfig
from apps.academics.models import Classroom, Subject, Timetable

def run_tests():
    print("=" * 80)
    print("TEST: ADMIN PROXY LEAVE APPLICATION (ដាក់ពាក្យសុំច្បាប់ជំនួសគ្រូ)")
    print("=" * 80)

    today = date.today()
    admin_user = User.objects.filter(role='ADMIN').first()
    if not admin_user:
        admin_user = User.objects.create_user(username='admin_proxy_test', password='password123', role='ADMIN')

    teacher1 = Teacher.objects.filter(status='ACTIVE').first()
    if not teacher1.user:
        u = User.objects.create_user(username='t_self_test', password='password123', role='TEACHER')
        teacher1.user = u
        teacher1.save()

    # Ensure timetable for today
    classroom = Classroom.objects.first()
    subject = Subject.objects.first()
    if not Timetable.objects.filter(teacher=teacher1, day_of_week=today.isoweekday()).exists():
        Timetable.objects.create(
            classroom=classroom,
            subject=subject,
            teacher=teacher1,
            day_of_week=today.isoweekday(),
            period_number=1,
            start_time=time(7, 0),
            end_time=time(8, 0)
        )

    client_admin = Client()
    client_admin.force_login(admin_user)

    client_teacher = Client()
    client_teacher.force_login(teacher1.user)

    # ---------------------------------------------------------
    # TEST 1: Admin applies for Teacher (Proxy submission)
    # ---------------------------------------------------------
    print("\n--- TEST 1: Admin Submits Leave on Behalf of Teacher ---")
    res_proxy = client_admin.post('/teachers/leave/apply/', {
        'teacher_id': teacher1.id,
        'category': 'EMERGENCY',
        'leave_type': 'SICK',
        'start_date': today.strftime('%Y-%m-%d'),
        'end_date': today.strftime('%Y-%m-%d'),
        'reason': 'គ្រូមានជំងឺគ្រុនឈាមសម្រាកនៅមន្ទីរពេទ្យ មិនអាចដាក់ពាក្យដោយខ្លួនឯងបាន',
        'proxy_note': 'គ្រូបានទូរស័ព្ទមកប្រាប់នាយកសាលាផ្ទាល់នៅម៉ោង 7:15 ព្រឹក',
    }, follow=True)
    assert res_proxy.status_code == 200

    proxy_leave = TeacherLeaveRequest.objects.filter(teacher=teacher1, start_date=today, category='EMERGENCY').order_by('-created_at').first()
    assert proxy_leave is not None
    assert proxy_leave.applied_by == admin_user
    assert proxy_leave.is_proxy_application is True
    assert 'ទូរស័ព្ទមកប្រាប់' in proxy_leave.proxy_note
    print(f"✅ Admin Proxy Leave created: AppliedBy={proxy_leave.applied_by.display_name}, Note={proxy_leave.proxy_note}")

    # ---------------------------------------------------------
    # TEST 2: Verify Leave List shows Proxy Badge
    # ---------------------------------------------------------
    print("\n--- TEST 2: Leave List Table Renders Proxy Badge ---")
    res_list = client_admin.get('/teachers/leave/')
    assert res_list.status_code == 200
    list_content = res_list.content.decode('utf-8')
    assert 'ដាក់ជំនួសដោយ៖' in list_content
    assert admin_user.display_name in list_content
    print("✅ Leave List accurately displays proxy submitter badge.")

    # ---------------------------------------------------------
    # TEST 3: Verify Printable A4 Letter shows Proxy Applicant & Signature Block
    # ---------------------------------------------------------
    print("\n--- TEST 3: Printable A4 Letter Renders Proxy Applicant & Signature ---")
    res_print = client_admin.get(f'/teachers/leave/{proxy_leave.id}/print/')
    assert res_print.status_code == 200
    print_content = res_print.content.decode('utf-8')
    assert 'ដាក់ពាក្យជំនួសដោយ៖' in print_content
    assert 'ហត្ថលេខាអ្នកដាក់ពាក្យជំនួស' in print_content
    assert admin_user.display_name in print_content
    print("✅ Printable Khmer A4 Letter shows proxy applicant details and modified signature block.")

    # ---------------------------------------------------------
    # TEST 4: Teacher Self-Submission is NOT flagged as Proxy
    # ---------------------------------------------------------
    print("\n--- TEST 4: Teacher Self-Submission is Direct (Not Proxy) ---")
    future_date = today + timedelta(days=7)
    res_self = client_teacher.post('/teachers/leave/apply/', {
        'category': 'PLANNED',
        'leave_type': 'PERSONAL',
        'start_date': future_date.strftime('%Y-%m-%d'),
        'end_date': future_date.strftime('%Y-%m-%d'),
        'reason': 'សុំច្បាប់ផ្ទាល់ខ្លួនដោយសាមីខ្លួន',
    }, follow=True)
    assert res_self.status_code == 200
    self_leave = TeacherLeaveRequest.objects.filter(teacher=teacher1, start_date=future_date).first()
    assert self_leave is not None
    assert self_leave.applied_by == teacher1.user
    assert self_leave.is_proxy_application is False
    print("✅ Teacher self-submission correctly recognized as direct application (is_proxy_application=False).")

    print("\n" + "=" * 80)
    print("🎉 ALL ADMIN PROXY LEAVE SUBMISSION TESTS PASSED 100%!")
    print("=" * 80)

if __name__ == '__main__':
    run_tests()
