import os
import sys
import django

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from apps.accounts.models import User
from apps.academics.models import AcademicYear, Classroom
from apps.students.models import Student
from apps.examinations.models import ExamTerm
from apps.finance.models import Invoice

def check_years():
    print("=== CURRENT ACADEMIC YEARS IN DATABASE ===")
    years = list(AcademicYear.objects.all().order_by('id'))
    for y in years:
        students_count = Student.objects.filter(academic_year=y).count()
        classrooms_count = Classroom.objects.filter(academic_year=y).count()
        terms_count = ExamTerm.objects.filter(academic_year=y).count()
        print(f"ID: {y.id}, Name: '{y.name}', is_current: {y.is_current}, Start: {y.start_date}, End: {y.end_date} -> Students: {students_count}, Classrooms: {classrooms_count}, ExamTerms: {terms_count}")

    admin_user = User.objects.filter(username='admin').first()
    if admin_user:
        print(f"\nAdmin user: {admin_user.username}, Role: {admin_user.role}, Password check '123': {admin_user.check_password('123')}, 'admin123': {admin_user.check_password('admin123')}")
    else:
        print("\nNo user with username 'admin'")

if __name__ == '__main__':
    check_years()
