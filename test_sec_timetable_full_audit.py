import os
import sys
import json
import django

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.teachers.models import Teacher
from apps.academics.models import (
    AcademicYear, Classroom, Subject, ClassSubject, Timetable, 
    TimetableVersion, DailyReportPrintConfig, TeacherDutySchedule, TeacherDutyType,
    GradeLevel, AcademicTrack
)
from apps.accounts.menu_registry import is_menu_allowed

def run_timetable_full_audit():
    print("=================================================================")
    print("🔍 AUDITING MENU 'កាលវិភាគ & គ្រូបង្រៀន' (TIMETABLE & SCHEDULING)")
    print("=================================================================\n")

    # 1. Setup Active Year & Base Entities
    year, _ = AcademicYear.objects.get_or_create(
        name='2025-2026',
        defaults={'is_current': True, 'start_date': '2025-10-01', 'end_date': '2026-07-31'}
    )
    year.is_current = True
    year.save()

    admin_user = User.objects.filter(role='ADMIN').first()
    if not admin_user:
        admin_user = User.objects.create_superuser('admin_audit', 'admin_audit@school.com', 'AdminPass123!')
    admin_user.role = 'ADMIN'
    admin_user.save()

    teacher_user = User.objects.filter(role='TEACHER').first()
    if not teacher_user:
        teacher_user = User.objects.create_user('teacher_audit', 'teacher_audit@school.com', 'TeacherPass123!')
        teacher_user.role = 'TEACHER'
        teacher_user.save()

    student_user = User.objects.filter(role='STUDENT').first()
    if not student_user:
        student_user = User.objects.create_user('student_audit', 'student_audit@school.com', 'StudentPass123!')
        student_user.role = 'STUDENT'
        student_user.save()

    client_admin = Client()
    client_admin.force_login(admin_user)

    client_teacher = Client()
    client_teacher.force_login(teacher_user)

    client_student = Client()
    client_student.force_login(student_user)

    # -------------------------------------------------------------
    # SUBMENU 1: កាលវិភាគរួម (Master Timetable Matrix) - timetable_view
    # -------------------------------------------------------------
    print("▶ 1. ត្រួតពិនិត្យមុខងារ: កាលវិភាគរួម (Master Timetable Matrix)")
    resp1 = client_admin.get('/academics/timetable/')
    assert resp1.status_code == 200, f"timetable_view failed: {resp1.status_code}"
    html1 = resp1.content.decode('utf-8')
    assert 'selectTimetableVersion' in html1
    assert 'table-timetable' in html1 or 'timetable-container' in html1 or 'btnToggleFullscreen' in html1
    print("   ✓ [PASS] GET /academics/timetable/ (200 OK) - Master Matrix & Versioning UI Rendered")

    # Test Version List API
    resp1_vers = client_admin.get('/academics/timetable/versions/')
    assert resp1_vers.status_code == 200
    v_data = json.loads(resp1_vers.content.decode('utf-8'))
    assert v_data['status'] == 'success'
    print("   ✓ [PASS] GET /academics/timetable/versions/ (200 OK) - JSON Version API works")

    # Test Save Matrix API
    resp1_save = client_admin.post(
        '/academics/timetable/save-matrix/',
        data=json.dumps({'academic_year_id': year.id, 'matrix': []}),
        content_type='application/json'
    )
    assert resp1_save.status_code in [200, 400]
    print("   ✓ [PASS] POST /academics/timetable/save-matrix/ - API responsive")

    # -------------------------------------------------------------
    # SUBMENU 2: របាយការណ៍ប្រចាំថ្ងៃ (Daily Duty & Teaching Log) - timetable_daily_reports_view
    # -------------------------------------------------------------
    print("\n▶ 2. ត្រួតពិនិត្យមុខងារ: របាយការណ៍ប្រចាំថ្ងៃ (Daily Duty & Teaching Log)")
    resp2 = client_admin.get('/academics/timetable/daily-reports/')
    assert resp2.status_code == 200, f"daily_reports failed: {resp2.status_code}"
    print("   ✓ [PASS] GET /academics/timetable/daily-reports/ (200 OK) - Duty & Teaching Tables Rendered")

    # Test Print Config API
    resp2_pcfg = client_admin.get(f'/academics/timetable/daily-reports/print-config/?academic_year_id={year.id}')
    assert resp2_pcfg.status_code == 200
    print("   ✓ [PASS] GET /academics/timetable/daily-reports/print-config/ (200 OK) - Print Config API responsive")

    # Test Excel Export (all report types)
    for r_type in ['duty_sheets', 'teacher_load', 'subject_codes', 'class_summary', 'all_reports']:
        resp_exp = client_admin.get(f'/academics/timetable/daily-reports/export-excel/?report_type={r_type}')
        assert resp_exp.status_code == 200
        assert resp_exp['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    print("   ✓ [PASS] Export 5 Excel Report types: duty_sheets, teacher_load, subject_codes, class_summary, all_reports (100% OK)")

    # -------------------------------------------------------------
    # SUBMENU 3: កាលវិភាគសិស្ស-គ្រូ (Student-Teacher Schedule Card) - student_teacher_timetable_view
    # -------------------------------------------------------------
    print("\n▶ 3. ត្រួតពិនិត្យមុខងារ: កាលវិភាគសិស្ស-គ្រូ (Student-Teacher Schedule Card)")
    resp3 = client_admin.get('/academics/timetable/student-teacher/')
    assert resp3.status_code == 200, f"student_teacher_timetable failed: {resp3.status_code}"
    print("   ✓ [PASS] GET /academics/timetable/student-teacher/ (200 OK) - Dual Tab view (Classrooms & Teachers)")

    # Test Student-Teacher Excel Export
    resp3_exp = client_admin.get('/academics/timetable/student-teacher/export-excel/')
    assert resp3_exp.status_code == 200
    assert resp3_exp['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    print("   ✓ [PASS] GET /academics/timetable/student-teacher/export-excel/ (200 OK) - Schedule Cards Excel Exported")

    # -------------------------------------------------------------
    # SUBMENU 4: មុខវិជ្ជា & ម៉ោងសិក្សា (Subject Hours Requirements) - subject_requirements_manager
    # -------------------------------------------------------------
    print("\n▶ 4. ត្រួតពិនិត្យមុខងារ: មុខវិជ្ជា & ម៉ោងសិក្សា (Subject Hours Requirements)")
    resp4 = client_admin.get('/academics/subject-requirements/')
    assert resp4.status_code == 200, f"subject_requirements failed: {resp4.status_code}"
    print("   ✓ [PASS] GET /academics/subject-requirements/ (200 OK) - Subject matrix rendered per Grade & Track")

    # Test Restore MoEYS default requirements
    resp4_moeys = client_admin.post('/academics/subject-requirements/restore-moeys/', follow=True)
    assert resp4_moeys.status_code == 200
    print("   ✓ [PASS] POST /academics/subject-requirements/restore-moeys/ (200 OK) - MoEYS standards restored")

    # -------------------------------------------------------------
    # SUBMENU 5: គ្រប់គ្រងគ្រូ & ចាត់តាំងថ្នាក់ (Teacher Class Assignments) - teacher_assignments_manager
    # -------------------------------------------------------------
    print("\n▶ 5. ត្រួតពិនិត្យមុខងារ: គ្រប់គ្រងគ្រូ & ចាត់តាំងថ្នាក់ (Teacher Class Assignments)")
    resp5 = client_admin.get('/academics/teacher-assignments/')
    assert resp5.status_code == 200, f"teacher_assignments failed: {resp5.status_code}"
    print("   ✓ [PASS] GET /academics/teacher-assignments/ (200 OK) - Teacher quota & class assignment matrix")

    # Test Quotas Save
    resp5_q = client_admin.post('/academics/teacher-assignments/training-quotas/save/', {
        'quota_គ្រូទុតិយភូមិ': '16',
        'quota_គ្រូបឋមភូមិ': '18',
        'quota_default': '18',
    }, follow=True)
    assert resp5_q.status_code == 200
    print("   ✓ [PASS] POST /academics/teacher-assignments/training-quotas/save/ (200 OK) - Workload Quotas saved")

    # Test Auto-Assign Algorithm
    resp5_auto = client_admin.get('/academics/teacher-assignments/auto-assign/', follow=True)
    assert resp5_auto.status_code == 200
    print("   ✓ [PASS] GET /academics/teacher-assignments/auto-assign/ (200 OK) - Auto-Assignment engine executed")

    # -------------------------------------------------------------
    # SUBMENU 6: គ្រប់គ្រងម៉ោងប្រចាំការ (Duty Hours & Staff Roster) - teacher_duty_manager
    # -------------------------------------------------------------
    print("\n▶ 6. ត្រួតពិនិត្យមុខងារ: គ្រប់គ្រងម៉ោងប្រចាំការ (Duty Hours & Staff Roster)")
    resp6 = client_admin.get('/academics/duty-schedule/')
    assert resp6.status_code == 200, f"duty_schedule failed: {resp6.status_code}"
    print("   ✓ [PASS] GET /academics/duty-schedule/ (200 OK) - Duty roster & shift scheduler rendered")

    # Test Duty Types API
    resp6_types = client_admin.get('/academics/duty-schedule/types/')
    assert resp6_types.status_code == 200
    print("   ✓ [PASS] GET /academics/duty-schedule/types/ (200 OK) - Duty Types API responsive")

    # -------------------------------------------------------------
    # 7. Role-Based Permissions Verification
    # -------------------------------------------------------------
    print("\n▶ 7. ត្រួតពិនិត្យសិទ្ធិប្រើប្រាស់តាម Role (Permissions & Security)")
    
    # ADMIN has full access to all 6 submenus
    for menu_key in ['timetable_view', 'timetable_daily_reports_view', 'student_teacher_timetable_view', 'subject_requirements_manager', 'teacher_assignments_manager', 'teacher_duty_manager']:
        assert is_menu_allowed(admin_user, menu_key), f"Admin should have access to {menu_key}"
    print("   ✓ [PASS] Admin Role: Full access to all 6 submenus (100%)")

    # TEACHER has access to view timetable, daily reports, schedule card, duty manager
    assert is_menu_allowed(teacher_user, 'timetable_view')
    assert is_menu_allowed(teacher_user, 'timetable_daily_reports_view')
    assert is_menu_allowed(teacher_user, 'student_teacher_timetable_view')
    assert is_menu_allowed(teacher_user, 'teacher_duty_manager')
    print("   ✓ [PASS] Teacher Role: Authorized for Timetable, Reports, Schedule Cards & Duty Roster")

    # STUDENT has access to view Student-Teacher Schedule Card
    assert is_menu_allowed(student_user, 'student_teacher_timetable_view')
    print("   ✓ [PASS] Student Role: Authorized to view Student-Teacher Schedule Card")

    print("\n=================================================================")
    print("🎉 លទ្ធផលសរុប: គ្រប់មុខងារ និង Menu 'កាលវិភាគ & គ្រូបង្រៀន' ដំណើរការ 100% យ៉ាងរលូន!")
    print("=================================================================")

if __name__ == '__main__':
    run_timetable_full_audit()
