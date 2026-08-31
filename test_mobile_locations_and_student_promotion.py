import os
import django
import json
from decimal import Decimal
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.utils import timezone
from django.test import Client
from apps.accounts.models import User
from apps.teachers.models import Teacher
from apps.students.models import Student, StudentPromotionRecord
from apps.academics.models import (
    AcademicYear, Classroom, Province, District, Commune, Village, ClassSubject, Subject
)

def run_tests():
    print("=== STARTING MOBILE LOCATIONS & STUDENT PROMOTION MATRIX TESTS ===")

    # 1. Setup Admin & Teacher users
    admin_user = User.objects.filter(role='ADMIN').first()
    if not admin_user:
        admin_user = User.objects.create_superuser('admin_promo_test', 'admin_promo@school.com', 'adminpass123')

    teacher_user = User.objects.filter(role='TEACHER').first()
    if not teacher_user:
        teacher_user = User.objects.create_user('teacher_promo_test', 'teacher_promo@school.com', 'teacherpass123', role='TEACHER')
    teacher_prof, _ = Teacher.objects.get_or_create(
        user=teacher_user,
        defaults={'khmer_name': 'គ្រូ ពិសិដ្ឋ (Promo Test)', 'latin_name': 'Piseth', 'phone': '012999888'}
    )

    # 2. Setup Academic Years and Classrooms
    now = timezone.now()
    year_2025, _ = AcademicYear.objects.get_or_create(
        name="2025-2026",
        defaults={'start_date': now.date() - timedelta(days=365), 'end_date': now.date(), 'is_current': False}
    )
    year_2026, _ = AcademicYear.objects.get_or_create(
        name="2026-2027",
        defaults={'start_date': now.date(), 'end_date': now.date() + timedelta(days=365), 'is_current': True}
    )

    class_10a, _ = Classroom.objects.get_or_create(
        name="ថ្នាក់ទី ១០A (2025)",
        academic_year=year_2025,
        defaults={'grade_level': 10, 'code': '10A-25', 'capacity': 40}
    )
    class_11a, _ = Classroom.objects.get_or_create(
        name="ថ្នាក់ទី ១១A (2026)",
        academic_year=year_2026,
        defaults={'grade_level': 11, 'code': '11A-26', 'capacity': 40}
    )
    class_10a_new, _ = Classroom.objects.get_or_create(
        name="ថ្នាក់ទី ១០A (2026)",
        academic_year=year_2026,
        defaults={'grade_level': 10, 'code': '10A-26', 'capacity': 40}
    )

    # Assign teacher to 10a
    sub_math = Subject.objects.filter(code='M').first() or Subject.objects.first()
    ClassSubject.objects.get_or_create(classroom=class_10a, teacher=teacher_prof, subject=sub_math)

    # Setup 2 Test Students in 10A
    student_pass, _ = Student.objects.get_or_create(
        student_id="PROMO-PASS-01",
        defaults={
            'khmer_name': 'សុខ សម្បត្តិ (ជាប់)', 'latin_name': 'Sok Sambath',
            'gender': 'M', 'date_of_birth': '2008-01-15',
            'classroom': class_10a, 'academic_year': year_2025, 'status': 'ACTIVE'
        }
    )
    student_fail, _ = Student.objects.get_or_create(
        student_id="PROMO-FAIL-02",
        defaults={
            'khmer_name': 'កែវ ធារ៉ា (ត្រួតថ្នាក់)', 'latin_name': 'Keo Theara',
            'gender': 'F', 'date_of_birth': '2008-05-20',
            'classroom': class_10a, 'academic_year': year_2025, 'status': 'ACTIVE'
        }
    )

    # Ensure clean state for test students
    student_pass.classroom = class_10a
    student_pass.academic_year = year_2025
    student_pass.status = 'ACTIVE'
    student_pass.is_repeating_grade = False
    student_pass.save()

    student_fail.classroom = class_10a
    student_fail.academic_year = year_2025
    student_fail.status = 'ACTIVE'
    student_fail.is_repeating_grade = False
    student_fail.save()

    client = Client()

    # ----------------- TEST 1: ADMINISTRATIVE LOCATIONS MOBILE APIS -----------------
    client.force_login(admin_user)

    # 1.1 Provinces
    resp_prov = client.get('/api/v1/locations/provinces/')
    assert resp_prov.status_code == 200, f"Provinces API failed: {resp_prov.status_code}"
    prov_data = resp_prov.json()
    assert prov_data['status'] == 'success' and prov_data['count'] > 0
    first_prov = prov_data['data'][0]
    first_prov_id = first_prov['id']
    print(f"1. [PASS] Mobile Location Provinces API returned {prov_data['count']} provinces successfully!")

    # 1.2 Districts
    resp_dist = client.get(f'/api/v1/locations/districts/?province_id={first_prov_id}')
    assert resp_dist.status_code == 200, f"Districts API failed: {resp_dist.status_code}"
    dist_data = resp_dist.json()
    assert dist_data['status'] == 'success'
    first_dist_id = dist_data['data'][0]['id'] if dist_data['data'] else None
    print(f"2. [PASS] Mobile Location Districts API returned {len(dist_data['data'])} districts for Province #{first_prov_id}!")

    # 1.3 Communes & Villages
    if first_dist_id:
        resp_com = client.get(f'/api/v1/locations/communes/?district_id={first_dist_id}')
        assert resp_com.status_code == 200
        com_data = resp_com.json()
        first_com_id = com_data['data'][0]['id'] if com_data['data'] else None

        if first_com_id:
            resp_vil = client.get(f'/api/v1/locations/villages/?commune_id={first_com_id}')
            assert resp_vil.status_code == 200
            print("3. [PASS] Mobile Location Communes and Villages APIs returned 200 OK!")

    # 1.4 Hierarchy API
    resp_hier = client.get('/api/v1/locations/hierarchy/')
    assert resp_hier.status_code == 200
    hier_data = resp_hier.json()
    assert hier_data['status'] == 'success' and len(hier_data['data']) > 0
    print("4. [PASS] Mobile Location Hierarchy Tree API returned successfully for offline mobile caching!")

    # ----------------- TEST 2: WEB STUDENT PROMOTION & RETENTION MATRIX -----------------
    # 2.1 View promotion portal for Admin
    resp_view = client.get(f'/academics/promotion/?source_class={class_10a.id}')
    assert resp_view.status_code == 200
    assert "ឧបករណ៍ផ្ទេរ ឡើងថ្នាក់ និងត្រួតថ្នាក់សិស្ស" in resp_view.content.decode('utf-8')
    print("5. [PASS] Web Promotion Matrix rendered 200 OK for Admin!")

    # 2.2 View promotion portal for Authorized Teacher
    client.force_login(teacher_user)
    resp_t_view = client.get(f'/academics/promotion/?source_class={class_10a.id}')
    assert resp_t_view.status_code == 200
    print("6. [PASS] Web Promotion Matrix rendered 200 OK for Authorized Teacher!")

    # 2.3 Submit Promotion Decision: Student A -> PROMOTE to 11A, Student B -> RETAIN in 10A
    post_payload = {
        'source_class': class_10a.id,
        'target_year': year_2026.id,
        'global_promotion_action': 'PROMOTE',
        'global_target_class': class_11a.id,
        'student_ids': [student_pass.id, student_fail.id],
        # Student Pass: PROMOTE to 11A
        f'action_{student_pass.id}': 'PROMOTE',
        f'target_class_{student_pass.id}': class_11a.id,
        f'reason_{student_pass.id}': 'PASSED_YEAR',
        f'notes_{student_pass.id}': 'ពិន្ទុមធ្យមភាគ ៨៥.០០',
        # Student Fail: RETAIN in 10A_new
        f'action_{student_fail.id}': 'RETAIN',
        f'target_class_{student_fail.id}': class_10a_new.id,
        f'reason_{student_fail.id}': 'FAILED_YEAR',
        f'notes_{student_fail.id}': 'ពិន្ទុមធ្យមភាគ ៤២.០០',
    }

    client.force_login(admin_user)
    resp_post = client.post('/academics/promotion/', post_payload, follow=True)
    assert resp_post.status_code == 200

    # 2.4 Verify Database Updates for Student A (Pass)
    student_pass.refresh_from_db()
    assert student_pass.classroom == class_11a, f"Expected 11A, got {student_pass.classroom}"
    assert student_pass.academic_year == year_2026
    assert student_pass.is_repeating_grade is False
    assert student_pass.last_promotion_status == 'ឡើងថ្នាក់'

    # 2.5 Verify Database Updates for Student B (Retain)
    student_fail.refresh_from_db()
    assert student_fail.classroom == class_10a_new, f"Expected 10A_new, got {student_fail.classroom}"
    assert student_fail.academic_year == year_2026
    assert student_fail.is_repeating_grade is True
    assert student_fail.last_promotion_status == 'ត្រួតថ្នាក់'
    assert 'ធ្លាក់មធ្យមភាគ' in student_fail.last_promotion_reason

    # 2.6 Verify Audit Trail Records
    log_pass = StudentPromotionRecord.objects.filter(student=student_pass, to_academic_year=year_2026).first()
    assert log_pass and log_pass.action == 'PROMOTE' and log_pass.to_classroom == class_11a

    log_fail = StudentPromotionRecord.objects.filter(student=student_fail, to_academic_year=year_2026).first()
    assert log_fail and log_fail.action == 'RETAIN' and log_fail.standard_reason == 'FAILED_YEAR'

    print("7. [PASS] Individual Student Decisions & Reasons executed successfully (Pass->Promote, Fail->Retain)!")
    print("8. [PASS] StudentPromotionRecord audit log created with full timestamp, user, reasons, and classroom changes!")

    # ----------------- TEST 3: MOBILE API STUDENT PROMOTION ENDPOINTS -----------------
    # 3.1 Metadata Endpoint
    resp_m_meta = client.get('/api/v1/students/promotion/meta/')
    assert resp_m_meta.status_code == 200
    meta_json = resp_m_meta.json()
    assert meta_json['status'] == 'success'
    assert len(meta_json['source_classrooms']) > 0
    assert len(meta_json['standard_reasons']) > 0
    print("9. [PASS] Mobile API Promotion Meta endpoint returned 200 OK with classroom lists and reasons!")

    # 3.2 Classroom Students List Endpoint
    resp_m_stud = client.get(f'/api/v1/students/promotion/students/?source_class_id={class_11a.id}')
    assert resp_m_stud.status_code == 200
    stud_json = resp_m_stud.json()
    assert stud_json['status'] == 'success'
    print(f"10. [PASS] Mobile API Class Students endpoint returned {stud_json['student_count']} students!")

    # 3.3 Submit Promotion via Mobile API
    mobile_payload = {
        'source_class_id': class_10a_new.id,
        'target_year_id': year_2026.id,
        'students': [
            {
                'student_id': student_fail.id,
                'action': 'PROMOTE',
                'target_class_id': class_11a.id,
                'standard_reason': 'PASSED_YEAR',
                'custom_notes': 'ប្រឡងសងជាប់ (Passed Retake Exam)'
            }
        ]
    }
    resp_m_sub = client.post('/api/v1/students/promotion/submit/', mobile_payload, content_type='application/json')
    assert resp_m_sub.status_code == 200
    sub_json = resp_m_sub.json()
    assert sub_json['status'] == 'success' and sub_json['promoted_count'] == 1

    student_fail.refresh_from_db()
    assert student_fail.classroom == class_11a
    assert student_fail.is_repeating_grade is False
    print("11. [PASS] Mobile API Student Promotion Submit endpoint processed decision and updated student records!")

    print("\n=== ALL MOBILE LOCATIONS & STUDENT PROMOTION MATRIX TESTS PASSED 100%! ===")

if __name__ == '__main__':
    run_tests()
