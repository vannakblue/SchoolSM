import os, sys, django
if sys.stdout and sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from apps.academics.models import AcademicYear, Classroom
from apps.students.models import Student

main_year = AcademicYear.objects.filter(id=3).first()

# Move students from TMP_261_9A (which are Grade 10 students promoted from 9A) to classroom 10E
tmp_class = Classroom.objects.filter(academic_year=main_year, code='TMP_261_9A').first()
target_10e = Classroom.objects.filter(academic_year=main_year, code='10E').first()

if tmp_class and target_10e:
    Student.objects.filter(classroom=tmp_class).update(classroom=target_10e)
    tmp_class.delete()
    print(f"Moved students from TMP_261_9A to 10E and deleted temp classroom.")

# Also let's check Risk Test Year (ID: 89) and copy the exact same 40 classrooms if needed or leave it clean
risk_year = AcademicYear.objects.filter(id=89).first()
if risk_year:
    # Remove any extra
    for c in list(risk_year.classrooms.all()):
        if c.code not in [
            '7A','7B','7C','7D','7E',
            '8A','8B','8C','8D',
            '9A','9B','9C','9D',
            '10A','10B','10C','10D','10E','10F','10G','10H','10I',
            '11A','11B','11C','11D','11E','11F','11G','11H','11I',
            '12A','12B','12C','12D','12E','12F','12G','12H','12I'
        ]:
            c.delete()

# Verify exact 40 classrooms in 2026-2027
final_classes = list(Classroom.objects.filter(academic_year=main_year).order_by('grade_level', 'code'))
print(f"\n========================================================")
print(f"FINAL CLASSROOM COUNT IN 2026-2027: {len(final_classes)} classrooms")
print(f"========================================================")
for c in final_classes:
    st_count = Student.objects.filter(classroom=c).count()
    print(f"- Grade {c.grade_level:2d} | Code: {c.code:5s} | Name: {c.name:20s} | Track: {c.track:8s} | Students: {st_count:3d}")
