import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from apps.students.models import Student
from apps.academics.models import AcademicYear, Classroom
from apps.teachers.models import Teacher

User = get_user_model()

def test_student_id_policy():
    client = APIClient()
    current_year = AcademicYear.objects.filter(is_current=True).first() or AcademicYear.objects.first()
    classroom = Classroom.objects.filter(academic_year=current_year).first()

    # 1. Unauthenticated or non-admin user
    res_meta_anon = client.get('/api/v1/students/enroll/')
    assert res_meta_anon.status_code == 200
    assert res_meta_anon.data.get('can_edit_student_id') is False, "Anonymous/Public should not be allowed to edit student ID"
    print("Check 1 passed: Anonymous can_edit_student_id is False")

    # 2. Teacher user
    teacher_user = User.objects.filter(role=User.Role.TEACHER).first()
    if not teacher_user:
        teacher_user = User.objects.create_user(username='test_teacher_id_policy', password='password', role=User.Role.TEACHER)
    client.force_authenticate(user=teacher_user)
    res_meta_teacher = client.get('/api/v1/students/enroll/')
    assert res_meta_teacher.data.get('can_edit_student_id') is False, "Teacher should not be allowed to edit student ID"
    print("Check 2 passed: Teacher can_edit_student_id is False")

    # 3. Teacher attempts to enroll student with custom manual ID
    expected_next_id = Student.generate_unique_student_id(current_year)
    payload_teacher = {
        'enrollment_mode': 'ADMIN_CUSTOM',
        'student_id': 'FORBIDDEN_MANUAL_ID_999',
        'khmer_name': 'តេស្ត សិស្សស្វ័យប្រវត្តិ',
        'latin_name': 'TEST AUTO ID',
        'gender': 'F',
        'date_of_birth': '2011-06-10',
        'phone': '012111222',
        'classroom_id': classroom.id if classroom else None,
        'academic_year_id': current_year.id if current_year else None,
    }
    res_enroll_teacher = client.post('/api/v1/students/enroll/', payload_teacher, format='json')
    assert res_enroll_teacher.status_code in [200, 201], f"Enrollment failed: {res_enroll_teacher.data}"
    stu_teacher = Student.objects.get(student_id=res_enroll_teacher.data['student']['student_id'])
    assert stu_teacher.student_id != 'FORBIDDEN_MANUAL_ID_999', "Teacher's manual custom ID must NOT be used"
    assert stu_teacher.student_id == expected_next_id, f"Expected sequential ID {expected_next_id}, got {stu_teacher.student_id}"
    print(f"Check 3 passed: Teacher submission resulted in auto-generated sequential ID: {stu_teacher.student_id}")

    # 4. Admin user
    admin_user = User.objects.filter(role=User.Role.ADMIN, is_staff=True).first()
    if not admin_user:
        admin_user = User.objects.create_superuser(username='test_admin_id_policy', password='password', email='admin@test.com')
    client.force_authenticate(user=admin_user)
    res_meta_admin = client.get('/api/v1/students/enroll/')
    assert res_meta_admin.data.get('can_edit_student_id') is True, "Admin should be allowed to edit student ID"
    print("Check 4 passed: Admin can_edit_student_id is True")

    # 5. Clean up
    stu_teacher.delete()
    print("All auto student ID policy tests passed successfully!")

if __name__ == '__main__':
    test_student_id_policy()
