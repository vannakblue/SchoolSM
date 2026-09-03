import os, sys, django
if sys.stdout and sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from apps.academics.models import Subject

ed = Subject.objects.filter(code='ED').first()
ag = Subject.objects.filter(code='AG').first()
print("Subject ED:", ed)
print("Subject AG:", ag)

if not ed:
    ed = Subject.objects.create(
        name_kh='អប់រំកាយ និងកីឡា',
        name_en='Physical Education & Sports',
        code='ED',
        category='GENERAL',
        credit=2,
        color_code='#10b981',
        order=15
    )
    print("Created Subject ED:", ed)

if not ag:
    ag = Subject.objects.create(
        name_kh='កសិកម្ម / គេហវិទ្យា',
        name_en='Agriculture / Technology',
        code='AG',
        category='SPECIALIZED',
        credit=2,
        color_code='#8b5cf6',
        order=16
    )
    print("Created Subject AG:", ag)
