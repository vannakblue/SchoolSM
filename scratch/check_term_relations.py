import os
import sys
sys.path.insert(0, 'e:/SchoolSM')
sys.stdout.reconfigure(encoding='utf-8')
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from apps.examinations.models import ExamTerm

term = ExamTerm.objects.first()
for rel in term._meta.related_objects:
    rel_model = rel.related_model
    accessor = rel.get_accessor_name()
    print(f"Related model: {rel_model.__name__} (accessor: '{accessor}')")
