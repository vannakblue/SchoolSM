from django.db import migrations
from django.db.models import Count


def delete_classrooms_under_10_students(apps, schema_editor):
    """
    Deletes all classrooms with fewer than 10 students.
    Safely re-links any students to official real classrooms so no student is deleted or lost.
    """
    Classroom = apps.get_model('academics', 'Classroom')
    Student = apps.get_model('students', 'Student')

    # 1. Map real classrooms (>= 10 students)
    real_classrooms = {}
    for cls in Classroom.objects.annotate(stu_count=Count('students')).filter(stu_count__gte=10):
        code_key = (cls.code or '').upper().strip()
        if code_key:
            real_classrooms[code_key] = cls

    # 2. Identify small classrooms (< 10 students)
    small_classrooms = list(Classroom.objects.annotate(stu_count=Count('students')).filter(stu_count__lt=10))

    # 3. Safely re-link any students in small classrooms before deletion
    for sc in small_classrooms:
        students = list(Student.objects.filter(classroom=sc))
        if students:
            raw_code = (sc.code or '').upper().split('-')[0].split('_')[0].strip()
            target_cls = real_classrooms.get(raw_code)
            if not target_cls and '8B' in (sc.name or ''):
                target_cls = real_classrooms.get('8B')
            if not target_cls and '7A' in (sc.name or ''):
                target_cls = real_classrooms.get('7A')
            if not target_cls and '10A' in (sc.name or ''):
                target_cls = real_classrooms.get('10A')

            if target_cls:
                Student.objects.filter(classroom=sc).update(classroom=target_cls)
            else:
                Student.objects.filter(classroom=sc).update(classroom=None)

    # 4. Safely delete all classrooms with < 10 students
    small_ids = [sc.id for sc in small_classrooms]
    if small_ids:
        Classroom.objects.filter(id__in=small_ids).delete()


def reverse_func(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0026_enforce_academic_years_and_admin_defaults'),
    ]

    operations = [
        migrations.RunPython(delete_classrooms_under_10_students, reverse_func),
    ]
