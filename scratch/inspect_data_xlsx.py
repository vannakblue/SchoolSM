import os, sys, django
if sys.stdout and sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from apps.academics.models import AcademicYear, Classroom
from apps.students.models import Student

y = AcademicYear.objects.filter(id=3).first()
print(f"=== CLASSROOM AUDIT IN YEAR '{y.name}' ===")

for c in y.classrooms.order_by('grade_level', 'code'):
    st_count = Student.objects.filter(classroom=c).count()
    print(f"ID: {c.id:3d} | Grade: {c.grade_level:2d} | Track: {c.track:8s} | Code: '{c.code:25s}' | Name: '{c.name:25s}' | Students: {st_count:3d}")
