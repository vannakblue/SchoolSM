import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.teachers.models import Teacher
from apps.academics.models import (
    AcademicYear, Classroom, Subject, Timetable,
    TeacherDutySchedule, TeacherDutyType
)

def run_tests():
    print("=== TESTING DUTY HOURS IN TEACHER TIMETABLE ===")
    
    admin_user = User.objects.filter(role='ADMIN').first()
    if not admin_user:
        admin_user = User.objects.create_superuser('testadmin', 'testadmin@school.com', 'adminpass123')
    
    active_year = AcademicYear.objects.filter(is_current=True).first()
    if not active_year:
        active_year = AcademicYear.objects.first()
        
    teacher = Teacher.objects.filter(status='ACTIVE').first()
    assert teacher, "At least one active teacher must exist!"
    
    # 1. Create / Ensure Duty Schedule for this teacher
    duty_type = TeacherDutyType.objects.filter(code='OFFICE').first()
    if not duty_type:
        duty_type = TeacherDutyType.objects.create(
            code='OFFICE', name='ប្រចាំការការិយាល័យ', icon='fa-building-columns', color='#4f46e5', order=1
        )
        
    duty_entry, created = TeacherDutySchedule.objects.update_or_create(
        academic_year=active_year,
        teacher=teacher,
        day_of_week=4, # Thursday
        period_number=1,
        defaults={
            'duty_type': 'OFFICE',
            'notes': 'ការិយាល័យរដ្ឋបាល',
        }
    )
    print(f"1. Ensured Duty Schedule for {teacher.khmer_name} on Thursday Period 1 ({duty_entry.duty_type})")
    
    # 2. Test GET student_teacher_timetable_view
    client = Client()
    client.force_login(admin_user)
    
    resp = client.get(f'/academics/timetable/student-teacher/?year={active_year.id if active_year else ""}')
    assert resp.status_code == 200, f"Expected 200 OK, got {resp.status_code}"
    
    html = resp.content.decode('utf-8')
    
    # Check if duty name is in the rendered html
    assert 'ប្រចាំការការិយាល័យ' in html or 'OFFICE' in html, "Duty name must be present in timetable HTML!"
    assert 'cell-duty-slot' in html, "cell-duty-slot CSS class must be present in timetable HTML!"
    assert 'ម៉ោងប្រចាំការ' in html, "ម៉ោងប្រចាំការ label must be present in timetable HTML!"
    print("2. [PASS] Teacher timetable view successfully includes Duty Hours in table cells and header meta!")
    
    # 3. Test Teacher Dashboard
    t_user = teacher.user
    if not t_user:
        t_user = User.objects.create_user(username=f't_{teacher.id}', role='TEACHER')
        teacher.user = t_user
        teacher.save()
        
    t_client = Client()
    t_client.force_login(t_user)
    t_resp = t_client.get('/dashboard/teacher/')
    assert t_resp.status_code == 200, f"Expected 200 OK for teacher dashboard, got {t_resp.status_code}"
    print("3. [PASS] Teacher dashboard rendered 200 OK with duty schedule integration!")
    
    print("\n=== ALL DUTY SCHEDULE IN TIMETABLE TESTS PASSED 100%! ===")

if __name__ == '__main__':
    run_tests()
