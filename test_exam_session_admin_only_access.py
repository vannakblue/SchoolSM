import os
import sys
import django

if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from apps.examinations.models import StandardizedExam, ExamRoom
from apps.academics.models import AcademicYear
import datetime

User = get_user_model()

def run_admin_only_tests():
    print("=== STARTING EXAM SESSION ADMIN-ONLY ACCESS VERIFICATION ===")

    # 1. Setup Users
    admin_user, _ = User.objects.get_or_create(
        username='test_admin_security',
        defaults={'role': 'ADMIN', 'is_superuser': True}
    )
    admin_user.role = 'ADMIN'
    admin_user.is_superuser = True
    admin_user.save()

    teacher_user, _ = User.objects.get_or_create(
        username='test_teacher_security',
        defaults={'role': 'TEACHER', 'is_superuser': False}
    )
    teacher_user.role = 'TEACHER'
    teacher_user.is_superuser = False
    teacher_user.save()

    student_user, _ = User.objects.get_or_create(
        username='test_student_security',
        defaults={'role': 'STUDENT', 'is_superuser': False}
    )
    student_user.role = 'STUDENT'
    student_user.is_superuser = False
    student_user.save()

    # Ensure at least one test exam exists
    ay = AcademicYear.objects.first()
    exam, _ = StandardizedExam.objects.get_or_create(
        name="សម័យប្រឡងតេស្តសាកល្បងសុវត្ថិភាព",
        defaults={
            'academic_year': ay,
            'exam_date': datetime.date.today(),
            'grade_level': 7
        }
    )
    room, _ = ExamRoom.objects.get_or_create(exam=exam, room_number=1, defaults={'room_name': 'បន្ទប់ ០១'})

    # 2. Test Teacher Sidebar & Access Restrictions
    client_teacher = Client()
    client_teacher.force_login(teacher_user)

    res_dash = client_teacher.get('/', follow=True)
    assert res_dash.status_code == 200
    dash_html = res_dash.content.decode('utf-8')
    assert 'href="/examinations/standardized/"' not in dash_html, "❌ Standardized exam link must NOT appear in Teacher's sidebar!"
    print("1. [PASS] Teacher sidebar does NOT show 'សម័យប្រឡង' (Exam Sessions) link.")

    # 3. Test Teacher Direct URL Access (Must be BLOCKED & redirected)
    endpoints_to_test = [
        f'/examinations/standardized/',
        f'/examinations/standardized/create/',
        f'/examinations/standardized/{exam.id}/manage/',
        f'/examinations/standardized/{exam.id}/edit/',
        f'/examinations/standardized/{exam.id}/room-postings/',
        f'/examinations/standardized/{exam.id}/attendance-sheets/',
        f'/examinations/standardized/{exam.id}/provisional-results/',
        f'/examinations/standardized/{exam.id}/export-candidates/',
        f'/examinations/standardized/{exam.id}/export-provisional-excel/',
        f'/examinations/standardized/{exam.id}/analytics/',
        f'/examinations/standardized/session/analytics/',
    ]

    for url in endpoints_to_test:
        resp = client_teacher.get(url)
        assert resp.status_code == 302, f"❌ Teacher should be redirected (302) from {url}, got {resp.status_code}"
        assert resp.url in ['/dashboard/', '/', '/accounts/login/', '/accounts/redirect/'], f"❌ Unexpected redirect target: {resp.url}"
    print(f"2. [PASS] Teacher blocked from accessing all {len(endpoints_to_test)} exam session URLs directly.")

    # 4. Test Student Direct URL Access (Must be BLOCKED)
    client_student = Client()
    client_student.force_login(student_user)
    resp_student = client_student.get(f'/examinations/standardized/{exam.id}/manage/')
    assert resp_student.status_code == 302, "❌ Student should be blocked from exam manage page"
    print("3. [PASS] Student blocked from exam session dashboard.")

    # 5. Test Admin Access (Must have full access & sidebar visibility)
    client_admin = Client()
    client_admin.force_login(admin_user)

    res_admin_dash = client_admin.get('/', follow=True)
    assert res_admin_dash.status_code == 200
    admin_dash_html = res_admin_dash.content.decode('utf-8')
    assert 'href="/examinations/standardized/"' in admin_dash_html, "❌ Admin sidebar MUST show 'សម័យប្រឡង' link!"
    print("4. [PASS] Admin sidebar prominently includes 'សម័យប្រឡង' (Exam Sessions).")

    res_admin_list = client_admin.get('/examinations/standardized/')
    assert res_admin_list.status_code == 200, "❌ Admin must be able to view exam session list"

    res_admin_manage = client_admin.get(f'/examinations/standardized/{exam.id}/manage/')
    assert res_admin_manage.status_code == 200, "❌ Admin must be able to view exam manage dashboard"
    print("5. [PASS] Admin successfully accesses exam list and exam manage dashboards.")

    # 6. Test Teacher Portal (Teachers CAN still access invigilator shift requests)
    res_invig = client_teacher.get('/examinations/invigilator-request/')
    assert res_invig.status_code == 200, "❌ Teacher must still be able to access teacher invigilator shift portal"
    print("6. [PASS] Teacher self-service shift request portal remains properly accessible.")

    print("\n=== ALL ADMIN-ONLY SECURITY & ACCESS TESTS PASSED 100%! ===")

if __name__ == '__main__':
    run_admin_only_tests()
