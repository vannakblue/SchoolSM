import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.academics.models import ClassSubject, Classroom, AcademicYear, Timetable

def run_test():
    print("=" * 60)
    print("TESTING TEACHER ASSIGNMENTS IMPORT VIEW AND DATABASE PERSISTENCE")
    print("=" * 60)

    # 1. Get or create Admin user
    admin_user = User.objects.filter(role='ADMIN').first()
    if not admin_user:
        admin_user = User.objects.create_superuser('testadmin', 'testadmin@schoolsm.local', 'Admin1234!')
    print(f"Using Admin user: {admin_user.username} (ID: {admin_user.id})")

    client = Client()
    client.force_login(admin_user)

    # 2. Test GET on teacher_assignments_manager
    response = client.get('/academics/teacher-assignments/')
    print(f"GET /academics/teacher-assignments/ status: {response.status_code}")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    content = response.content.decode('utf-8')
    assert 'ចាត់តាំងគ្រូបង្រៀនតាមថ្នាក់ និងមុខវិជ្ជា' in content
    assert 'importDutyModal' in content
    assert 'នាំចូលបំណែងចែកភារកិច្ច (Excel)' in content
    print(" -> Page rendered successfully with Import Duty modal & button!")

    # 3. Test POST on teacher_assignments_import_excel with file upload
    with open('បំណែងចែកគ្រូ2027.xlsx', 'rb') as f:
        post_response = client.post('/academics/teacher-assignments/import-excel/', {'excel_file': f}, follow=True)
    print(f"POST /academics/teacher-assignments/import-excel/ status: {post_response.status_code}")
    assert post_response.status_code == 200
    post_content = post_response.content.decode('utf-8')
    assert 'នាំចូលបំណែងចែកភារកិច្ចគ្រូជោគជ័យ' in post_content
    print(" -> POST import view processed successfully with success message!")

    # 4. Check database counts
    ay = AcademicYear.objects.filter(is_current=True).first()
    cs_assigned = ClassSubject.objects.filter(classroom__academic_year=ay, teacher__isnull=False).count()
    distinct_teachers = ClassSubject.objects.filter(classroom__academic_year=ay, teacher__isnull=False).values('teacher').distinct().count()
    print(f"Database verification for Academic Year {ay.name}:")
    print(f"  ClassSubject count with assigned teacher: {cs_assigned}")
    print(f"  Distinct Teachers assigned: {distinct_teachers}")
    assert distinct_teachers >= 104, f"Expected at least 104 teachers, got {distinct_teachers}"

    print("\nALL VERIFICATIONS PASSED SUCCESSFULLY!")

if __name__ == '__main__':
    run_test()
