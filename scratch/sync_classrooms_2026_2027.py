import os, sys, django
if sys.stdout and sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from apps.academics.models import AcademicYear, Classroom

CLASSROOM_DEFS = [
    # Grade 7 (GENERAL)
    {'code': '7A', 'name': 'ថ្នាក់ទី ៧A', 'grade_level': 7, 'track': 'GENERAL'},
    {'code': '7B', 'name': 'ថ្នាក់ទី ៧B', 'grade_level': 7, 'track': 'GENERAL'},
    {'code': '7C', 'name': 'ថ្នាក់ទី ៧C', 'grade_level': 7, 'track': 'GENERAL'},
    {'code': '7D', 'name': 'ថ្នាក់ទី ៧D', 'grade_level': 7, 'track': 'GENERAL'},
    {'code': '7E', 'name': 'ថ្នាក់ទី ៧E', 'grade_level': 7, 'track': 'GENERAL'},

    # Grade 8 (GENERAL)
    {'code': '8A', 'name': 'ថ្នាក់ទី ៨A', 'grade_level': 8, 'track': 'GENERAL'},
    {'code': '8B', 'name': 'ថ្នាក់ទី ៨B', 'grade_level': 8, 'track': 'GENERAL'},
    {'code': '8C', 'name': 'ថ្នាក់ទី ៨C', 'grade_level': 8, 'track': 'GENERAL'},
    {'code': '8D', 'name': 'ថ្នាក់ទី ៨D', 'grade_level': 8, 'track': 'GENERAL'},

    # Grade 9 (GENERAL)
    {'code': '9A', 'name': 'ថ្នាក់ទី ៩A', 'grade_level': 9, 'track': 'GENERAL'},
    {'code': '9B', 'name': 'ថ្នាក់ទី ៩B', 'grade_level': 9, 'track': 'GENERAL'},
    {'code': '9C', 'name': 'ថ្នាក់ទី ៩C', 'grade_level': 9, 'track': 'GENERAL'},
    {'code': '9D', 'name': 'ថ្នាក់ទី ៩D', 'grade_level': 9, 'track': 'GENERAL'},

    # Grade 10 (GENERAL)
    {'code': '10A', 'name': 'ថ្នាក់ទី ១០A', 'grade_level': 10, 'track': 'GENERAL'},
    {'code': '10B', 'name': 'ថ្នាក់ទី ១០B', 'grade_level': 10, 'track': 'GENERAL'},
    {'code': '10C', 'name': 'ថ្នាក់ទី ១០C', 'grade_level': 10, 'track': 'GENERAL'},
    {'code': '10D', 'name': 'ថ្នាក់ទី ១០D', 'grade_level': 10, 'track': 'GENERAL'},
    {'code': '10E', 'name': 'ថ្នាក់ទី ១០E', 'grade_level': 10, 'track': 'GENERAL'},
    {'code': '10F', 'name': 'ថ្នាក់ទី ១០F', 'grade_level': 10, 'track': 'GENERAL'},
    {'code': '10G', 'name': 'ថ្នាក់ទី ១០G', 'grade_level': 10, 'track': 'GENERAL'},
    {'code': '10H', 'name': 'ថ្នាក់ទី ១០H', 'grade_level': 10, 'track': 'GENERAL'},
    {'code': '10I', 'name': 'ថ្នាក់ទី ១០I', 'grade_level': 10, 'track': 'GENERAL'},

    # Grade 11 (SCIENCE & SOCIAL)
    {'code': '11A', 'name': 'ថ្នាក់ទី ១១A', 'grade_level': 11, 'track': 'SCIENCE'},
    {'code': '11B', 'name': 'ថ្នាក់ទី ១១B', 'grade_level': 11, 'track': 'SCIENCE'},
    {'code': '11C', 'name': 'ថ្នាក់ទី ១១C', 'grade_level': 11, 'track': 'SCIENCE'},
    {'code': '11D', 'name': 'ថ្នាក់ទី ១១D', 'grade_level': 11, 'track': 'SCIENCE'},
    {'code': '11E', 'name': 'ថ្នាក់ទី ១១E', 'grade_level': 11, 'track': 'SCIENCE'},
    {'code': '11F', 'name': 'ថ្នាក់ទី ១១F', 'grade_level': 11, 'track': 'SOCIAL'},
    {'code': '11G', 'name': 'ថ្នាក់ទី ១១G', 'grade_level': 11, 'track': 'SOCIAL'},
    {'code': '11H', 'name': 'ថ្នាក់ទី ១១H', 'grade_level': 11, 'track': 'SOCIAL'},
    {'code': '11I', 'name': 'ថ្នាក់ទី ១១I', 'grade_level': 11, 'track': 'SOCIAL'},

    # Grade 12 (SCIENCE & SOCIAL)
    {'code': '12A', 'name': 'ថ្នាក់ទី ១២A', 'grade_level': 12, 'track': 'SCIENCE'},
    {'code': '12B', 'name': 'ថ្នាក់ទី ១២B', 'grade_level': 12, 'track': 'SCIENCE'},
    {'code': '12C', 'name': 'ថ្នាក់ទី ១២C', 'grade_level': 12, 'track': 'SCIENCE'},
    {'code': '12D', 'name': 'ថ្នាក់ទី ១២D', 'grade_level': 12, 'track': 'SCIENCE'},
    {'code': '12E', 'name': 'ថ្នាក់ទី ១២E', 'grade_level': 12, 'track': 'SCIENCE'},
    {'code': '12F', 'name': 'ថ្នាក់ទី ១២F', 'grade_level': 12, 'track': 'SOCIAL'},
    {'code': '12G', 'name': 'ថ្នាក់ទី ១២G', 'grade_level': 12, 'track': 'SOCIAL'},
    {'code': '12H', 'name': 'ថ្នាក់ទី ១២H', 'grade_level': 12, 'track': 'SOCIAL'},
    {'code': '12I', 'name': 'ថ្នាក់ទី ១២I', 'grade_level': 12, 'track': 'SOCIAL'},
]

print("--- SYNCING 40 CLASSROOMS FROM DATA.XLSX INTO ACADEMIC YEAR 2026-2027 ---")

# 1. Set main AcademicYear '2026-2027' as active/current
main_year, _ = AcademicYear.objects.get_or_create(
    name='2026-2027',
    defaults={
        'start_date': '2026-09-01',
        'end_date': '2027-07-15',
        'is_current': True
    }
)
main_year.is_current = True
main_year.save()

# Also handle Risk Test Year if present
risk_year = AcademicYear.objects.filter(name='2026-2027 Risk Test Year').first()

target_years = [main_year]
if risk_year:
    target_years.append(risk_year)

for yr in target_years:
    print(f"\nProcessing Year: '{yr.name}' (ID: {yr.id})...")
    created_count = 0
    updated_count = 0
    
    for cdef in CLASSROOM_DEFS:
        # Search by code or clean code
        c_obj = Classroom.objects.filter(academic_year=yr, code=cdef['code']).first()
        if not c_obj:
            # Try finding with prefix like ថ្នាក់ទី 7A or name
            c_obj = Classroom.objects.filter(academic_year=yr, name=cdef['name']).first()
        
        if c_obj:
            c_obj.name = cdef['name']
            c_obj.code = cdef['code']
            c_obj.grade_level = cdef['grade_level']
            c_obj.track = cdef['track']
            c_obj.save()
            updated_count += 1
        else:
            Classroom.objects.create(
                academic_year=yr,
                code=cdef['code'],
                name=cdef['name'],
                grade_level=cdef['grade_level'],
                track=cdef['track'],
                capacity=45
            )
            created_count += 1

    total_now = Classroom.objects.filter(academic_year=yr).count()
    print(f"✅ Year '{yr.name}': Created {created_count}, Updated {updated_count}. Total classrooms now = {total_now}")

# Verify 40 classrooms in main_year
all_codes = list(Classroom.objects.filter(academic_year=main_year).order_by('grade_level', 'code').values_list('code', flat=True))
print("\n=== FINAL CLASSROOM CODES IN 2026-2027 ===")
print(", ".join(all_codes))
print(f"Total count: {len(all_codes)}")
