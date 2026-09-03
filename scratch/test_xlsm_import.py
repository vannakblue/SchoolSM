import os, sys, django
if sys.stdout and sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.academics.models import AcademicYear, Classroom
from apps.students.models import Student

admin_user = User.objects.filter(role=User.Role.ADMIN).first()
if not admin_user:
    admin_user = User.objects.create_superuser('admin_test', 'admin@example.com', 'adminpass')
    admin_user.role = User.Role.ADMIN
    admin_user.save()

client = Client()
client.force_login(admin_user)

file_path = r'E:\SchoolSM\2026-2027.xlsm'
ay = AcademicYear.objects.filter(name='2026-2027').first() or AcademicYear.objects.filter(is_current=True).first()

with open(file_path, 'rb') as f:
    response = client.post('/students/import/', {
        'academic_year': str(ay.id),
        'file': f
    })

print("Response Status Code:", response.status_code)
total_students = Student.objects.filter(academic_year=ay, status='ACTIVE').count()
print(f"Total Active Students in '{ay.name}' after test import: {total_students}")
