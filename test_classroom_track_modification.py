import os
import sys
import django
from datetime import date

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.academics.models import AcademicYear, Classroom, Subject, GradeLevelRule
from apps.students.models import Student

def run_tests():
    print("=== STARTING CLASSROOM TRACK MODIFICATION TEST SUITE ===")

    # 1. Setup Admin Account
    admin_user, _ = User.objects.get_or_create(
        username='test_admin_track_mod',
        defaults={'role': 'ADMIN', 'is_staff': True, 'is_superuser': True}
    )
    admin_user.set_password('Admin@123456')
    admin_user.role = 'ADMIN'
    admin_user.is_superuser = True
    admin_user.save()

    client = Client()
    client.force_login(admin_user)

    # Initial cleanup
    Classroom.objects.filter(code__startswith='TEST-TRACK-').delete()
    AcademicYear.objects.filter(name='2026-2027-TRACK-TEST').delete()

    print("1. [PASS] Setup test admin user.")

    # 2. Setup Academic Year
    year = AcademicYear.objects.create(
        name='2026-2027-TRACK-TEST',
        start_date=date(2026, 9, 1),
        end_date=date(2027, 7, 31),
        is_current=True
    )

    # 3. Create Classroom in Science Track (ថ្នាក់ទី ១១ វិទ្យាសាស្ត្រ)
    cls_obj = Classroom.objects.create(
        name='11 វិទ្យាសាស្ត្រ A',
        code='TEST-TRACK-11-SCI',
        grade_level=11,
        track='SCIENCE',
        academic_year=year,
        capacity=45
    )

    # Add student
    student = Student.objects.create(
        student_id='STU-TRACK-001',
        khmer_name='សិស្ស វិទ្យាសាស្ត្រ',
        latin_name='Science Student',
        gender='M',
        date_of_birth=date(2009, 1, 1),
        classroom=cls_obj,
        academic_year=year,
        status='ACTIVE'
    )

    print(f"2. [PASS] Created classroom '{cls_obj.name}' with track='{cls_obj.track}' and active student.")

    # 4. Test Track Subjects API for SCIENCE vs SOCIAL
    resp_sci = client.get('/academics/api/track-subjects/?grade_level=11&track=SCIENCE')
    assert resp_sci.status_code == 200
    data_sci = resp_sci.json()
    assert data_sci['success'] is True
    assert data_sci['track'] == 'SCIENCE'

    resp_soc = client.get('/academics/api/track-subjects/?grade_level=11&track=SOCIAL')
    assert resp_soc.status_code == 200
    data_soc = resp_soc.json()
    assert data_soc['success'] is True
    assert data_soc['track'] == 'SOCIAL'
    print("3. [PASS] api_get_track_subjects correctly returned curriculum subjects for SCIENCE and SOCIAL tracks.")

    # 5. Modify Classroom: Change Track from SCIENCE to SOCIAL (វិទ្យាសាស្ត្រ -> វិទ្យាសាស្ត្រសង្គម)
    resp_edit = client.post(
        f'/academics/classrooms/{cls_obj.id}/edit/',
        data={
            'name': '11 វិទ្យាសាស្ត្រសង្គម A',
            'code': 'TEST-TRACK-11-SOC',
            'grade_level': 11,
            'track': 'SOCIAL',
            'academic_year': year.id,
            'capacity': 45,
            'subject_ids': data_soc['subject_ids']
        }
    )
    assert resp_edit.status_code == 302 # Redirects to classroom_list

    # 6. Verify Database State
    cls_obj.refresh_from_db()
    assert cls_obj.track == 'SOCIAL'
    assert cls_obj.name == '11 វិទ្យាសាស្ត្រសង្គម A'
    assert cls_obj.code == 'TEST-TRACK-11-SOC'
    assert cls_obj.get_track_display() == 'ថ្នាក់វិទ្យាសាស្ត្រសង្គម (Social Science Track)'

    # Verify student is still in this classroom
    student.refresh_from_db()
    assert student.classroom_id == cls_obj.id
    assert student.classroom.track == 'SOCIAL'

    # Verify subject rules
    rules = cls_obj.get_subject_rules()
    assert len(rules) > 0
    print("4. [PASS] Classroom successfully updated to track='SOCIAL' (វិទ្យាសាស្ត្រសង្គម) with student and subjects preserved.")

    # 7. Cleanup
    student.delete()
    cls_obj.delete()
    year.delete()
    admin_user.delete()

    print("\n=== ALL 4 CLASSROOM TRACK MODIFICATION TESTS PASSED 100%! ===")

if __name__ == '__main__':
    run_tests()
