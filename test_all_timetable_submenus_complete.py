import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.conf import settings
from django.test import Client
from apps.accounts.models import User
from apps.teachers.models import Teacher
from apps.academics.models import AcademicYear, Classroom, Subject, ClassSubject

def run_test():
    print("=== TESTING ALL TIMETABLE & TEACHER ASSIGNMENT SUBMENUS & ACTIONS ===")
    settings.DEBUG = False

    admin_user = User.objects.filter(role='ADMIN').first()
    if not admin_user:
        admin_user = User.objects.create_superuser('admin_test_full', 'admin_full@school.com', 'adminpass123')

    client = Client()
    client.force_login(admin_user)

    teacher = Teacher.objects.filter(status='ACTIVE').first()
    active_year = AcademicYear.objects.filter(is_current=True).first() or AcademicYear.objects.first()

    # 1. Master Timetable
    resp = client.get('/academics/timetable/')
    assert resp.status_code == 200, f"Master Timetable failed: {resp.status_code}"
    print("1. [PASS] Master Timetable (GET /academics/timetable/) -> 200 OK")

    # 2. Daily Duty Reports
    resp = client.get('/academics/timetable/daily-reports/')
    assert resp.status_code == 200, f"Daily Duty Reports failed: {resp.status_code}"
    print("2. [PASS] Daily Duty Reports (GET /academics/timetable/daily-reports/) -> 200 OK")

    # 3. Student-Teacher Timetables
    resp = client.get('/academics/timetable/student-teacher/')
    assert resp.status_code == 200, f"Student-Teacher Timetable failed: {resp.status_code}"
    print("3. [PASS] Student-Teacher Timetable (GET /academics/timetable/student-teacher/) -> 200 OK")

    # 4. Subject Requirements Matrix
    resp = client.get('/academics/subject-requirements/')
    assert resp.status_code == 200, f"Subject Requirements Matrix failed: {resp.status_code}"
    print("4. [PASS] Subject Requirements Matrix (GET /academics/subject-requirements/) -> 200 OK")

    # 5. Teacher Assignments Manager (List & Specific Teacher)
    resp = client.get('/academics/teacher-assignments/')
    assert resp.status_code == 200, f"Teacher Assignments Manager failed: {resp.status_code}"
    print("5. [PASS] Teacher Assignments Manager (GET /academics/teacher-assignments/) -> 200 OK")

    if teacher:
        resp = client.get(f'/academics/teacher-assignments/?teacher={teacher.id}')
        assert resp.status_code == 200, f"Teacher Assignments for teacher {teacher.id} failed: {resp.status_code}"
        print(f"6. [PASS] Teacher Assignments for {teacher.khmer_name} (GET /academics/teacher-assignments/?teacher={teacher.id}) -> 200 OK")

    # 6. Save Training Quotas
    resp = client.post('/academics/teacher-assignments/training-quotas/save/', {
        'quota_គ្រូទុតិយភូមិ': '16',
        'quota_គ្រូបឋមភូមិ': '18',
        'quota_default': '18',
    }, follow=True)
    assert resp.status_code == 200, f"Training quotas save failed: {resp.status_code}"
    print("7. [PASS] Training Quotas Save (POST /academics/teacher-assignments/training-quotas/save/) -> 200 OK")

    # 7. Auto-Assign
    resp = client.get('/academics/teacher-assignments/auto-assign/', follow=True)
    assert resp.status_code == 200, f"Auto-assign failed: {resp.status_code}"
    print("8. [PASS] Auto-Assign (GET /academics/teacher-assignments/auto-assign/) -> 200 OK")

    # 8. Reset Single Teacher
    if teacher:
        resp = client.get(f'/academics/teacher-assignments/reset-teacher/{teacher.id}/', follow=True)
        assert resp.status_code == 200, f"Reset teacher failed: {resp.status_code}"
        print(f"9. [PASS] Reset Single Teacher {teacher.khmer_name} -> 200 OK")

    # 9. Reset All Assignments
    resp = client.get('/academics/teacher-assignments/reset-all/', follow=True)
    assert resp.status_code == 200, f"Reset all assignments failed: {resp.status_code}"
    print("10. [PASS] Reset All Assignments -> 200 OK")

    # 10. Duty Schedule Manager
    resp = client.get('/academics/duty-schedule/')
    assert resp.status_code == 200, f"Duty Schedule Manager failed: {resp.status_code}"
    print("11. [PASS] Duty Schedule Manager (GET /academics/duty-schedule/) -> 200 OK")

    print("\n=== ALL 11 TIMETABLE SUBMENU TESTS PASSED 100%! ===")

if __name__ == '__main__':
    run_test()
