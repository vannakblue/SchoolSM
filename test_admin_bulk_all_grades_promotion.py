import os
import sys
import json
from datetime import date
import django

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.academics.models import AcademicYear, Classroom
from apps.students.models import Student, StudentPromotionRecord

def run_tests():
    print("=== STARTING ADMIN BULK ALL-GRADES PROMOTION & TRANSFER TEST SUITE ===")

    # 1. Setup Admin Account
    admin_user, _ = User.objects.get_or_create(
        username='test_admin_bulk_prom',
        defaults={'role': 'ADMIN', 'is_staff': True, 'is_superuser': True}
    )
    admin_user.set_password('Admin@123456')
    admin_user.role = 'ADMIN'
    admin_user.is_superuser = True
    admin_user.save()

    client = Client()
    client.force_login(admin_user)

    # Initial cleanup to ensure clean slate
    Student.objects.filter(student_id__startswith='STU-BULK-').delete()
    AcademicYear.objects.filter(name__in=['2025-2026-BULK-SRC', '2026-2027-BULK-TGT']).delete()

    print("1. [PASS] Setup test environment & admin login.")

    # 2. Setup Academic Years
    year_src = AcademicYear.objects.create(
        name='2025-2026-BULK-SRC',
        start_date=date(2025, 9, 1),
        end_date=date(2026, 7, 31),
        is_current=False
    )
    year_tgt = AcademicYear.objects.create(
        name='2026-2027-BULK-TGT',
        start_date=date(2026, 9, 1),
        end_date=date(2027, 7, 31),
        is_current=True
    )

    # 3. Create Classrooms across Grades 7 through 12 in Source Year
    classrooms_src = {}
    total_students_created = 0

    for grade in range(7, 13):
        cls_name = f"{grade}A"
        c = Classroom.objects.create(
            name=cls_name,
            code=cls_name,
            academic_year=year_src,
            grade_level=grade,
            capacity=45
        )
        classrooms_src[grade] = c

        # Create 2 active students per classroom
        for s_idx in range(1, 3):
            total_students_created += 1
            Student.objects.create(
                student_id=f'STU-BULK-G{grade}-00{s_idx}',
                khmer_name=f'សិស្ស ថ្នាក់ទី{grade} លេខ{s_idx}',
                latin_name=f'Student Grade{grade} No{s_idx}',
                gender='M' if s_idx == 1 else 'F',
                date_of_birth=date(2010, 1, 1),
                classroom=c,
                academic_year=year_src,
                status='ACTIVE'
            )

    print(f"2. [PASS] Created {len(classrooms_src)} classrooms and {total_students_created} active students across Grades 7-12.")

    # 4. Test Matrix Preview API
    resp_matrix = client.get(f'/academics/promotion/api/all-grades-matrix/?source_year_id={year_src.id}&target_year_id={year_tgt.id}')
    assert resp_matrix.status_code == 200
    data_matrix = resp_matrix.json()
    assert data_matrix['status'] == 'success'
    assert data_matrix['total_students'] == 12
    assert data_matrix['total_classes'] == 6
    assert len(data_matrix['grade_groups']) == 6

    # Verify Grade 7 suggestion -> PROMOTE to 8A
    g7_data = next(g for g in data_matrix['grade_groups'] if g['grade_level'] == 7)
    assert g7_data['classes'][0]['suggested_action'] == 'PROMOTE'
    assert g7_data['classes'][0]['suggested_target_grade'] == 8
    assert g7_data['classes'][0]['suggested_target_name'] == '8A'

    # Verify Grade 12 suggestion -> GRADUATE
    g12_data = next(g for g in data_matrix['grade_groups'] if g['grade_level'] == 12)
    assert g12_data['classes'][0]['suggested_action'] == 'GRADUATE'
    print("3. [PASS] Matrix Preview API correctly analyzed all 6 grade levels and produced accurate suggestions.")

    # 5. Test Classroom Students API
    class_7a = classrooms_src[7]
    resp_students = client.get(f'/academics/promotion/api/classroom-students/{class_7a.id}/')
    assert resp_students.status_code == 200
    data_students = resp_students.json()
    assert data_students['status'] == 'success'
    assert data_students['students_count'] == 2
    print("4. [PASS] Classroom Students API returned active students for individual exception handling.")

    # 6. Test Auto-Promote All Grades Execution (+1 Grade Level with 1 Student Repeating Exception)
    # Target:
    # 7A -> 8A (1 promoted to 8A, 1 exception retained in 7A)
    # 8A -> 9A (2 promoted)
    # 9A -> 10A (2 promoted)
    # 10A -> 11A (2 promoted)
    # 11A -> 12A (2 promoted)
    # 12A -> GRADUATED (2 graduated)

    retained_student = Student.objects.get(student_id='STU-BULK-G7-002')

    mappings_payload = []
    for g_lvl, sc in classrooms_src.items():
        if g_lvl == 12:
            mappings_payload.append({
                'source_class_id': sc.id,
                'action': 'GRADUATE',
                'auto_create_target': False,
                'student_exceptions': {}
            })
        elif g_lvl == 7:
            mappings_payload.append({
                'source_class_id': sc.id,
                'action': 'PROMOTE',
                'auto_create_target': True,
                'target_class_name': '8A',
                'target_grade_level': 8,
                'student_exceptions': {
                    str(retained_student.id): {
                        'action': 'RETAIN',
                        'reason': 'FAILED_YEAR',
                        'notes': 'ត្រួតថ្នាក់ទី ៧ ដដែល'
                    }
                }
            })
        else:
            mappings_payload.append({
                'source_class_id': sc.id,
                'action': 'PROMOTE',
                'auto_create_target': True,
                'target_class_name': f"{g_lvl + 1}A",
                'target_grade_level': g_lvl + 1,
                'student_exceptions': {}
            })

    resp_exec = client.post(
        '/academics/promotion/api/all-grades-execute/',
        data=json.dumps({
            'source_year_id': year_src.id,
            'target_year_id': year_tgt.id,
            'mappings': mappings_payload,
            'note': 'ផ្ទេរសិស្សគ្រប់កម្រិតថ្នាក់ទូទាំងសាលា'
        }),
        content_type='application/json'
    )
    assert resp_exec.status_code == 200
    data_exec = resp_exec.json()
    assert data_exec['status'] == 'success'
    assert data_exec['total_moved'] == 12
    assert data_exec['promoted_count'] == 9
    assert data_exec['retained_count'] == 1
    assert data_exec['graduated_count'] == 2
    print("5. [PASS] All-grades bulk promotion executed successfully in database.")

    # 7. Verify Database State Post-Promotion
    # Check Promoted Student (Grade 7 No 1 -> Grade 8A in target year)
    s_promoted = Student.objects.get(student_id='STU-BULK-G7-001')
    assert s_promoted.academic_year == year_tgt
    assert s_promoted.classroom.name == '8A'
    assert s_promoted.classroom.academic_year == year_tgt
    assert s_promoted.classroom.grade_level == 8
    assert s_promoted.status == 'ACTIVE'
    assert s_promoted.is_repeating_grade is False
    assert s_promoted.last_promotion_status == 'ឡើងថ្នាក់'

    # Check Retained Student (Grade 7 No 2 -> Retained)
    retained_student.refresh_from_db()
    assert retained_student.academic_year == year_tgt
    assert retained_student.status == 'ACTIVE'
    assert retained_student.is_repeating_grade is True
    assert retained_student.last_promotion_status == 'ត្រួតថ្នាក់'

    # Check Graduated Students (Grade 12 -> GRADUATED)
    s_grad = Student.objects.get(student_id='STU-BULK-G12-001')
    assert s_grad.status == 'GRADUATED'
    assert s_grad.last_promotion_status == 'បញ្ចប់ការសិក្សា'

    # Check Promotion Audit Records
    audit_count = StudentPromotionRecord.objects.filter(student__student_id__startswith='STU-BULK-').count()
    assert audit_count == 12
    print("6. [PASS] Database verification confirmed accurate classroom rollovers, retention flags, and 12 audit records.")

    # Cleanup
    Student.objects.filter(student_id__startswith='STU-BULK-').delete()
    Classroom.objects.filter(academic_year__in=[year_src, year_tgt]).delete()
    year_src.delete()
    year_tgt.delete()
    admin_user.delete()

    print("\n=== ALL 6 ADMIN BULK ALL-GRADES PROMOTION TESTS PASSED 100%! ===")

if __name__ == '__main__':
    run_tests()
