import os, sys, django
if sys.stdout and sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from apps.academics.models import Subject

print("=== ALL SUBJECTS IN DATABASE ===")
for s in Subject.objects.all().order_by('order', 'id'):
    print(f"ID: {s.id:2d} | Code: '{s.code:10s}' | Name KH: '{s.name_kh:30s}' | Name EN: '{s.name_en:25s}' | Cat: {s.category}")
