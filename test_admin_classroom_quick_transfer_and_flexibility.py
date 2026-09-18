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
    print("=== STARTING ADMIN CLASSROOM QUICK TRANSFER & FLEXIBILITY TESTS ===")

    # 1. Admin login
    admin_user = User.objects.filter(role=User.Role.ADMIN).first()
    if not admin_user:
        admin_user = User.objects.create_superuser(
            username='admin_transfer_tester',
            password='Password123!',
            email='admin_tester@example.com',
            role=User.Role.ADMIN,
            khmer_name='អ្នកគ្រប់គ្រង ផ្ទេរថ្នាក់'
        )

    client = Client()
    client.force_login(admin_user)
    print("1. [PASS] Admin logged in successfully.")

    # 2. Get target academic year
    ay_target = AcademicYear.objects.filter(is_current=True).first() or AcademicYear.objects.filter(name='2026-2027').first()
    assert ay_target is not None, "Target academic year 2026-2027 must exist"

    # 3. Create or get test classrooms
    cls_7a, _ = Classroom.objects.get_or_create(
        name='7A-FLEX-TEST',
        code='7A-FLEX-TEST',
        academic_year=ay_target,
        grade_level=7,
        defaults={'capacity': 45}
    )
    cls_7b, _ = Classroom.objects.get_or_create(
        name='7B-FLEX-TEST',
        code='7B-FLEX-TEST',
        academic_year=ay_target,
        grade_level=7,
        defaults={'capacity': 45}
    )

    # 4. Create test student
    student, _ = Student.objects.get_or_create(
        student_id='STU-FLEX-TEST-001',
        defaults={
            'khmer_name': 'សុខ ចាន់ដារ៉ា',
            'latin_name': 'Sok Chandara',
            'gender': 'M',
            'date_of_birth': date(2012, 5, 15),
            'classroom': cls_7a,
            'academic_year': ay_target,
            'status': 'ACTIVE'
        }
    )
    student.classroom = cls_7a
    student.save()
    print("2. [PASS] Test classrooms and student initialized.")

    # 5. Test Classroom Allocation Main Page Rendering
    resp_page = client.get(f'/academics/classrooms/allocation/?grade=7&academic_year={ay_target.id}')
    assert resp_page.status_code == 200, f"Expected 200, got {resp_page.status_code}"
    content = resp_page.content.decode('utf-8')
    assert 'សិទ្ធិអភិបាលពេញលេញជានិច្ច' in content, "Admin rights banner not found in page content"
    assert 'modalClassRosterQuickTransfer' in content, "Quick transfer modal not found in page content"
    assert '/academics/classrooms/allocation/api/current-roster/' in content, "Current roster API url not found in page content"
    assert '/academics/classrooms/allocation/api/quick-transfer/' in content, "Quick transfer API url not found in page content"
    print("3. [PASS] Classroom Allocation page renders with Admin Rights Assurance Banner & Modal.")

    # 6. Test API Current Classroom Roster
    roster_url = f'/academics/classrooms/allocation/api/current-roster/?classroom_id={cls_7a.id}'
    resp_roster = client.get(roster_url)
    assert resp_roster.status_code == 200, f"Expected 200, got {resp_roster.status_code}"
    roster_data = resp_roster.json()
    assert roster_data['status'] == 'success', f"Expected success, got {roster_data}"
    assert any(s['id'] == student.id for s in roster_data['students']), "Student not found in roster"
    assert any(d['id'] == cls_7b.id for d in roster_data['destination_classrooms']), "Destination class 7B not found"
    print(f"4. [PASS] Current roster API returned {roster_data['total_count']} student(s) and valid destination classes.")

    # 7. Test Quick Transfer API
    transfer_url = '/academics/classrooms/allocation/api/quick-transfer/'
    payload = {
        'student_id': student.id,
        'target_classroom_id': cls_7b.id,
        'reason': 'Admin តម្រូវឱ្យប្តូរទៅ 7B ដោយផ្ទាល់'
    }
    resp_trans = client.post(
        transfer_url,
        data=json.dumps(payload),
        content_type='application/json'
    )
    assert resp_trans.status_code == 200, f"Expected 200, got {resp_trans.status_code}"
    trans_data = resp_trans.json()
    assert trans_data['status'] == 'success', f"Expected success, got {trans_data}"

    # Verify student moved to 7B in database
    student.refresh_from_db()
    assert student.classroom_id == cls_7b.id, f"Expected classroom {cls_7b.id}, got {student.classroom_id}"
    assert '7B' in student.last_promotion_status, "Student last_promotion_status not updated"

    # Verify StudentPromotionRecord audit log
    log = StudentPromotionRecord.objects.filter(student=student, to_classroom=cls_7b).order_by('-id').first()
    assert log is not None, "StudentPromotionRecord audit log was not created"
    assert log.from_classroom_id == cls_7a.id, "Audit from_classroom mismatch"
    assert log.to_classroom_id == cls_7b.id, "Audit to_classroom mismatch"
    print("5. [PASS] Student successfully transferred and audited in StudentPromotionRecord.")

    # Clean up test records
    student.delete()
    cls_7a.delete()
    cls_7b.delete()
    print("6. [PASS] Test records cleaned up.")
    print("=== ALL ADMIN CLASSROOM QUICK TRANSFER & FLEXIBILITY TESTS PASSED! ===")

if __name__ == '__main__':
    run_tests()
