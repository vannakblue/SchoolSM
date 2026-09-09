import os
import sys

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import django
from datetime import date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import RequestFactory, Client
from django.contrib.auth import get_user_model
from apps.academics.models import AcademicYear, Classroom, GradeLevel
from apps.students.models import Student
from apps.students.views import (
    api_set_student_repeater_status,
    api_batch_set_student_repeater_status,
    api_classroom_repeater_list,
    api_student_age_grade_drilldown,
    _calculate_age_grade_matrix,
    _get_student_age_roster_data,
    export_student_age_grade_excel,
)

User = get_user_model()


def run_tests():
    print("======================================================================")
    print("   TEST SUITE: ADMIN REPEATER MANAGEMENT & MoEYS AGE-GRADE MATRIX   ")
    print("======================================================================")

    # 1. Setup Test Fixtures
    print("\n[1] Setting up Users, Classrooms, and Test Students...")
    admin_user, _ = User.objects.get_or_create(username='admin_test_repeater', defaults={'email': 'admin_rep@test.com', 'role': 'ADMIN'})
    admin_user.role = 'ADMIN'
    admin_user.save()

    teacher_user, _ = User.objects.get_or_create(username='teacher_test_repeater', defaults={'email': 'teacher_rep@test.com', 'role': 'TEACHER'})
    teacher_user.role = 'TEACHER'
    teacher_user.save()

    ay, _ = AcademicYear.objects.get_or_create(
        name='2025-2026',
        defaults={'start_date': date(2025, 10, 1), 'end_date': date(2026, 8, 31), 'is_current': True}
    )

    cls7a = Classroom.objects.filter(academic_year=ay, grade_level=7).first()
    if not cls7a:
        cls7a = Classroom.objects.create(
            academic_year=ay,
            name='7A-Test',
            code='7A-TEST',
            grade_level=7,
            track='GENERAL'
        )

    # Clean existing test students
    Student.objects.filter(student_id__in=['REP-001', 'REP-002', 'REP-003']).delete()

    s1 = Student.objects.create(
        student_id='REP-001',
        khmer_name='ចាន់ សុខា',
        latin_name='Chan Sokha',
        gender='M',
        date_of_birth=date(2012, 5, 15), # 14 years old
        classroom=cls7a,
        academic_year=ay,
        status='ACTIVE',
        is_repeating_grade=False
    )

    s2 = Student.objects.create(
        student_id='REP-002',
        khmer_name='មាស ធីតា',
        latin_name='Meas Thida',
        gender='F',
        date_of_birth=date(2012, 3, 20), # 14 years old female
        classroom=cls7a,
        academic_year=ay,
        status='ACTIVE',
        is_repeating_grade=False
    )

    s3 = Student.objects.create(
        student_id='REP-003',
        khmer_name='កែវ វិបុល',
        latin_name='Keo Vibul',
        gender='M',
        date_of_birth=date(2013, 8, 10), # 13 years old
        classroom=cls7a,
        academic_year=ay,
        status='ACTIVE',
        is_repeating_grade=False
    )
    print("    Created 3 test students: REP-001 (M, 14), REP-002 (F, 14), REP-003 (M, 13)")

    client = Client()

    # 2. Permission Check: Teacher Forbidden (403 for AJAX, 302 redirect otherwise)
    print("\n[2] Testing RBAC: Non-admin (Teacher) access forbidden...")
    client.force_login(teacher_user)
    resp_teacher_ajax = client.post(f'/students/api/set-repeater-status/{s1.id}/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
    assert resp_teacher_ajax.status_code == 403, f"Expected 403 for AJAX, got {resp_teacher_ajax.status_code}"
    resp_teacher_page = client.post(f'/students/api/set-repeater-status/{s1.id}/')
    assert resp_teacher_page.status_code == 302, f"Expected 302 redirect for non-AJAX, got {resp_teacher_page.status_code}"
    print("    PASSED: Non-admin received 403 for AJAX and 302 redirect for non-AJAX.")

    # 3. 1-Click Toggle: Set to Repeater
    print("\n[3] Testing Admin 1-Click Toggle (False -> True)...")
    client.force_login(admin_user)
    resp_toggle = client.post(f'/students/api/set-repeater-status/{s1.id}/')
    assert resp_toggle.status_code == 200, f"Expected 200, got {resp_toggle.status_code}"
    
    data_toggle = resp_toggle.json()
    assert data_toggle['status'] == 'success'
    assert data_toggle['is_repeater'] is True
    assert 'សិស្សត្រួតថ្នាក់' in data_toggle['admission_type']

    s1.refresh_from_db()
    assert s1.is_repeating_grade is True
    assert s1.last_promotion_status == 'RETAINED'
    print("    PASSED: s1 designated as repeater (is_repeating_grade=True, status=RETAINED).")

    # 4. 1-Click Toggle: Revert to New Student
    print("\n[4] Testing Admin 1-Click Toggle (True -> False)...")
    resp_toggle2 = client.post(f'/students/api/set-repeater-status/{s1.id}/')
    assert resp_toggle2.status_code == 200
    data_toggle2 = resp_toggle2.json()
    assert data_toggle2['is_repeater'] is False
    assert 'សិស្សថ្មី' in data_toggle2['admission_type']

    s1.refresh_from_db()
    assert s1.is_repeating_grade is False
    assert s1.last_promotion_status == 'NORMAL'
    print("    PASSED: s1 reverted back to new student (is_repeating_grade=False).")

    # 5. Batch Repeater Assignment API
    print("\n[5] Testing Admin Batch Assignment API...")
    resp_batch = client.post(
        '/students/api/batch-set-repeater-status/',
        data={'student_ids[]': [str(s1.id), str(s2.id)], 'is_repeating_grade': 'true', 'reason': 'សាកល្បង batch'}
    )
    assert resp_batch.status_code == 200
    data_batch = resp_batch.json()
    assert data_batch['updated_count'] == 2
    assert data_batch['is_repeater'] is True

    s1.refresh_from_db()
    s2.refresh_from_db()
    s3.refresh_from_db()
    assert s1.is_repeating_grade is True
    assert s2.is_repeating_grade is True
    assert s3.is_repeating_grade is False
    print("    PASSED: Batch assignment set s1 & s2 as repeaters, s3 remained new.")

    # 6. Classroom Repeater List API
    print("\n[6] Testing Classroom Repeater List API...")
    resp_list = client.get(f'/students/api/classroom-repeater-list/?classroom_id={cls7a.id}&academic_year_id={ay.id}')
    assert resp_list.status_code == 200
    data_list = resp_list.json()
    assert data_list['status'] == 'success'
    assert data_list['total_repeaters'] >= 2
    assert data_list['total_females_repeater'] >= 1
    student_ids_in_list = [item['id'] for item in data_list['students']]
    assert s1.id in student_ids_in_list
    assert s2.id in student_ids_in_list
    print(f"    PASSED: Classroom list returned {data_list['count']} students with {data_list['total_repeaters']} repeaters.")

    # 7. Age-Grade Statistics Matrix Calculations
    print("\n[7] Testing Age-Grade Statistics Matrix Calculations...")
    matrix_data = _calculate_age_grade_matrix(academic_year=ay, calc_method='exact')
    raw_counts = matrix_data['raw_counts']
    
    # Check age 13 row (both s1 and s2 are age 13 at ref date 31/10/2025 in grade 7)
    g7_13 = raw_counts['g7'][13]
    g7_rep_tot = g7_13['rep_total']
    g7_rep_fem = g7_13['rep_female']
    print(f"    Matrix Age 13 Grade 7 repeaters: total={g7_rep_tot}, female={g7_rep_fem}")
    assert g7_rep_tot >= 2, f"Expected at least 2 repeaters in Age 13 Grade 7, got {g7_rep_tot}"
    assert g7_rep_fem >= 1, f"Expected at least 1 female repeater in Age 13 Grade 7, got {g7_rep_fem}"
    assert matrix_data['total_repeaters_count'] >= 2, f"Expected total_repeaters >= 2, got {matrix_data['total_repeaters_count']}"
    print("    PASSED: Matrix accurately tallies designated repeaters.")

    # 8. Interactive Drilldown API
    print("\n[8] Testing Age-Grade Drilldown Filter by REPEATER...")
    resp_drill_rep = client.get(f'/students/api/age-grade-drilldown/?year_id={ay.id}&cat=g7&age=13&col_type=rep_total&calc_method=exact')
    assert resp_drill_rep.status_code == 200
    data_drill_rep = resp_drill_rep.json()
    rep_ids = [st['id'] for st in data_drill_rep['students']]
    assert s1.id in rep_ids
    assert s2.id in rep_ids
    assert s3.id not in rep_ids
    print(f"    PASSED: Drilldown for rep_total returned s1 & s2, correctly excluding s3.")

    # 9. Custom Age Roster Filtering & Remarks
    print("\n[9] Testing Customizable Age Roster Repeater Integration...")
    req_roster_rep = RequestFactory().get(f'/students/reports/age-roster/?academic_year={ay.id}&grade_level=7&repeater=REPEATER&calc_method=exact&mode=all')
    roster_rep_data = _get_student_age_roster_data(req_roster_rep)
    roster_students = roster_rep_data['students']
    r_ids = [st['id'] for st in roster_students]
    assert s1.id in r_ids
    assert s2.id in r_ids
    assert s3.id not in r_ids
    for st in roster_students:
        if st['id'] in [s1.id, s2.id]:
            assert st['is_repeater'] is True
            assert st['remarks'] == 'ត្រួតថ្នាក់'
    print("    PASSED: Custom Age Roster correctly filtered repeaters with remarks='ត្រួតថ្នាក់'.")

    # 10. Excel Export Verification
    print("\n[10] Testing Excel Export with Designated Repeaters...")
    resp_excel = client.get(f'/students/statistics/age-grade/export-excel/?academic_year_id={ay.id}&calc_method=exact')
    assert resp_excel.status_code == 200
    assert resp_excel['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    print(f"    PASSED: Excel export generated successfully ({len(resp_excel.content)} bytes).")

    # Cleanup test data
    Student.objects.filter(student_id__in=['REP-001', 'REP-002', 'REP-003']).delete()
    print("\n======================================================================")
    print("   ALL 10 VERIFICATION TESTS PASSED SUCCESSFULLY!                    ")
    print("======================================================================")


if __name__ == '__main__':
    run_tests()
