import os
import sys
import random
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.academics.models import AcademicYear, Classroom
from apps.students.models import Student, StudentCategory

if sys.stdout and sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Authentic Khmer Family Names (នាមត្រកូល)

KHMER_FAMILY_NAMES = [
    ('សុខ', 'Sok'), ('ចាន់', 'Chan'), ('កែវ', 'Keo'), ('ម៉ៅ', 'Mao'),
    ('សេង', 'Seng'), ('លី', 'Ly'), ('ហេង', 'Heng'), ('ជា', 'Chea'),
    ('អ៊ុក', 'Ouk'), ('ឌិត', 'Dith'), ('គង់', 'Kong'), ('យិន', 'Yin'),
    ('វ៉ាន់', 'Van'), ('អ៊ុំ', 'Oum'), ('ព្រំ', 'Prom'), ('ឃួន', 'Khuon'),
    ('ទេព', 'Tep'), ('ឈឹម', 'Chhim'), ('ញ៉ែម', 'Nhem'), ('ឡុង', 'Long'),
    ('រស់', 'Ros'), ('ទៀង', 'Tieng'), ('មាស', 'Meas'), ('ពេជ្រ', 'Pich'),
    ('អេង', 'Eng'), ('ស៊ិន', 'Sin'), ('ស៊ូ', 'Sou'), ('អ៊ុច', 'Ouch'),
    ('ប៉ែន', 'Pen'), ('នួន', 'Nuon'), ('សោម', 'Som'), ('ឈាង', 'Chheang')
]

# Authentic Male Given Names (ឈ្មោះប្រុស)
MALE_GIVEN_NAMES = [
    ('ដារ៉ា', 'Dara'), ('វិបុល', 'Vibol'), ('រិទ្ធី', 'Rithy'), ('ពិសិដ្ឋ', 'Piseth'),
    ('ចិន្តា', 'Chenda'), ('វណ្ណៈ', 'Vannak'), ('រតនា', 'Rattana'), ('បញ្ញា', 'Panha'),
    ('ឧត្តម', 'Oudom'), ('សម្បត្តិ', 'Sambath'), ('វិសាល', 'Visal'), ('មុន្នី', 'Mony'),
    ('ភិរុណ', 'Phirun'), ('វឌ្ឍនៈ', 'Vaddhana'), ('ថាវរៈ', 'Thavarak'), ('ចំរើន', 'Chamroeun'),
    ('សុភ័ក្ត្រ', 'Sopheak'), ('ណារិទ្ធ', 'Narith'), ('មករា', 'Makara'), ('វុទ្ធី', 'Vuthy'),
    ('សីហា', 'Seyha'), ('សារ៉ាត់', 'Sarath'), ('ធារ៉ា', 'Theara'), ('រស្មី', 'Reaksmey'),
    ('គឹមសាន', 'Kimsan'), ('កុសល', 'Kosol'), ('សេរី', 'Serey'), ('សុវណ្ណ', 'Sovann'),
    ('សុខា', 'Sokha'), ('ពន្លឺ', 'Ponleu'), ('តារា', 'Tara'), ('ចាន់ថន', 'Chanthon'),
    ('សំបូរ', 'Sambor'), ('សុជាតា', 'Socheata'), ('វិទូ', 'Vithou')
]

# Authentic Female Given Names (ឈ្មោះស្រី)
FEMALE_GIVEN_NAMES = [
    ('ស្រីនាង', 'Sreineang'), ('ចរិយា', 'Chariya'), ('សុភាព', 'Sopheap'), ('ទេវី', 'Devy'),
    ('គន្ធា', 'Kunthea'), ('ធីតា', 'Thida'), ('ពិសី', 'Pisey'), ('រស្មី', 'Reaksmey'),
    ('ស្រីមុំ', 'Sreymom'), ('ម៉ាលី', 'Maly'), ('ផល្លា', 'Phalla'), ('សុធារី', 'Sotheary'),
    ('រចនា', 'Rachana'), ('កល្យាណ', 'Kalyan'), ('នារី', 'Neary'), ('ស្រីពៅ', 'Sreypov'),
    ('មុនីរ័ត្ន', 'Muniroth'), ('វណ្ណារី', 'Vannary'), ('ស្រីលក្ខណ៍', 'Sreyleak'), ('ភារម្យ', 'Phearom'),
    ('បុប្ផា', 'Bopha'), ('វត្តី', 'Vatey'), ('សោភា', 'Sophea'), ('ចរណៃ', 'Chornai'),
    ('សោភ័ណ', 'Sophorn'), ('កេសរ', 'Kesor'), ('ចរិយា', 'Chariya'), ('សុភាវី', 'Sopheavy'),
    ('មាលា', 'Mealea'), ('ចន្ទ្រា', 'Chanthrea'), ('សុជាតា', 'Socheata'), ('ស្រីនិច', 'Sreynich'),
    ('កលិកា', 'Kolika'), ('លីដា', 'Lyda'), ('មុនីកា', 'Monika')
]

PROVINCES = [
    'រាជធានីភ្នំពេញ', 'ខេត្តកណ្តាល', 'ខេត្តកំពង់ចាម', 'ខេត្តតាកែវ',
    'ខេត្តកំពត', 'ខេត្តបាត់ដំបង', 'ខេត្តសៀមរាប', 'ខេត្តព្រៃវែង',
    'ខេត្តស្វាយរៀង', 'ខេត្តកំពង់ធំ', 'ខេត្តកំពង់ឆ្នាំង', 'ខេត្តពោធិ៍សាត់'
]

OCCUPATIONS = [
    'កសិករ', 'អាជីវករ', 'មន្ត្រីរាជការ', 'គ្រូបង្រៀន', 'វិស្វករ',
    'វេជ្ជបណ្ឌិត', 'បុគ្គលិកក្រុមហ៊ុន', 'ជាងសំណង់', 'អ្នកលក់ដូរ', 'មេផ្ទះ'
]

PHONE_PREFIXES = ['012', '098', '088', '010', '017', '077', '085', '096', '069', '093']

def generate_phone():
    prefix = random.choice(PHONE_PREFIXES)
    suffix = f"{random.randint(100000, 999999)}"
    return f"{prefix} {suffix[:3]} {suffix[3:]}"

class Command(BaseCommand):
    help = 'Generate 30 to 50 demo/temporary students per classroom for all active classrooms.'

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=35, help='Number of students per classroom (default: 35)')
        parser.add_argument('--year', type=str, default=None, help='Academic Year name (e.g. 2026-2027)')
        parser.add_argument('--clear-existing', action='store_true', help='Clear existing students before seeding')

    def handle(self, *args, **options):
        target_count = options['count']
        year_filter = options['year']
        clear_existing = options['clear_existing']

        self.stdout.write(self.style.NOTICE(f"=== SEEDING DEMO STUDENTS ({target_count} per class) ==="))

        # 1. Setup Student Categories
        cat_normal, _ = StudentCategory.objects.get_or_create(code="NORMAL", defaults={'name': 'សិស្សទូទៅ (Normal)', 'display_order': 1})
        cat_poor, _ = StudentCategory.objects.get_or_create(code="POOR", defaults={'name': 'សិស្សក្រីក្រ (Poor)', 'display_order': 2})
        cat_scholarship, _ = StudentCategory.objects.get_or_create(code="SCHOLARSHIP", defaults={'name': 'អាហារូបករណ៍ (Scholarship)', 'display_order': 3})
        cat_teacher, _ = StudentCategory.objects.get_or_create(code="TEACHER_CHILD", defaults={'name': "កូនគ្រូបង្រៀន (Teacher's Child)", 'display_order': 4})
        cat_free, _ = StudentCategory.objects.get_or_create(code="FREE", defaults={'name': 'ឥតគិតថ្លៃ (Free 100%)', 'display_order': 5})

        category_pool = [cat_normal] * 70 + [cat_poor] * 15 + [cat_scholarship] * 8 + [cat_teacher] * 5 + [cat_free] * 2

        # 2. Resolve Academic Years
        if year_filter:
            academic_years = AcademicYear.objects.filter(name=year_filter)
        else:
            academic_years = AcademicYear.objects.filter(name__in=['2026-2027', '2025-2026'])
            if not academic_years.exists():
                academic_years = AcademicYear.objects.all()

        total_created = 0

        with transaction.atomic():
            if clear_existing:
                Student.objects.filter(academic_year__in=academic_years).delete()
                self.stdout.write(self.style.WARNING("Cleared existing students in selected academic years."))

            for ay in academic_years:
                classrooms = Classroom.objects.filter(academic_year=ay).order_by('grade_level', 'code')
                self.stdout.write(self.style.NOTICE(f"\n--- Processing Academic Year: {ay.name} ({classrooms.count()} Classrooms) ---"))

                year_short = ay.name[:4] if len(ay.name) >= 4 else "2026"
                year_prefix = str(int(year_short) % 100).zfill(2)

                for cls in classrooms:
                    existing_count = Student.objects.filter(classroom=cls, academic_year=ay).count()
                    needed = max(0, target_count - existing_count)

                    if needed <= 0:
                        self.stdout.write(f"  [OK] {cls.name} ({cls.code}): Already has {existing_count} students.")
                        continue

                    # Determine birth year base based on grade level
                    # Grade 7: ~12-13y (2014-2013), Grade 12: ~17-18y (2009-2008)
                    base_birth_year = int(year_short) - (cls.grade_level + 6)
                    grade_str = str(cls.grade_level).zfill(2)

                    students_to_create = []

                    existing_ids = set(Student.objects.values_list('student_id', flat=True))

                    for i in range(1, needed + 1):
                        seq_num = existing_count + i
                        student_id = f"{year_prefix}{cls.id:02d}{str(seq_num).zfill(3)}"

                        # Unique ID check
                        while student_id in existing_ids or Student.objects.filter(student_id=student_id).exists():
                            seq_num += 1
                            student_id = f"{year_prefix}{cls.id:02d}{str(seq_num).zfill(3)}"

                        existing_ids.add(student_id)


                        # Random gender (50/50)
                        is_female = (i % 2 == 0)
                        gender = Student.Gender.FEMALE if is_female else Student.Gender.MALE

                        # Name generation
                        fam_kh, fam_en = random.choice(KHMER_FAMILY_NAMES)
                        if is_female:
                            given_kh, given_en = random.choice(FEMALE_GIVEN_NAMES)
                        else:
                            given_kh, given_en = random.choice(MALE_GIVEN_NAMES)

                        khmer_name = f"{fam_kh} {given_kh}"
                        latin_name = f"{fam_en.upper()} {given_en.upper()}"

                        # Birthdate
                        b_year = base_birth_year + random.choice([-1, 0, 1])
                        b_month = random.randint(1, 12)
                        b_day = random.randint(1, 28)
                        dob = date(b_year, b_month, b_day)

                        # Parents
                        father_fam, father_fam_en = random.choice(KHMER_FAMILY_NAMES)
                        father_given, father_given_en = random.choice(MALE_GIVEN_NAMES)
                        mother_fam, mother_fam_en = random.choice(KHMER_FAMILY_NAMES)
                        mother_given, mother_given_en = random.choice(FEMALE_GIVEN_NAMES)

                        father_name = f"{father_fam} {father_given}"
                        mother_name = f"{mother_fam} {mother_given}"

                        father_phone = generate_phone()
                        mother_phone = generate_phone()
                        prov = random.choice(PROVINCES)

                        cat = random.choice(category_pool)
                        fee_type = Student.ScholarshipType.FULL_PAY
                        if cat.code == 'POOR':
                            fee_type = Student.ScholarshipType.SCHOLARSHIP_50
                        elif cat.code in ['FREE', 'SCHOLARSHIP']:
                            fee_type = Student.ScholarshipType.SCHOLARSHIP_100

                        st = Student(
                            student_id=student_id,
                            khmer_name=khmer_name,
                            latin_name=latin_name,
                            gender=gender,
                            date_of_birth=dob,
                            place_of_birth=prov,
                            current_address=f"ភូមិ១ ឃុំកណ្តួត ស្រុកកណ្តាលស្ទឹង {prov}",
                            phone=generate_phone() if random.random() > 0.4 else None,
                            classroom=cls,
                            academic_year=ay,
                            status=Student.Status.ACTIVE,
                            scholarship_type=fee_type,
                            category=cat,
                            father_name=father_name,
                            father_phone=father_phone,
                            father_job=random.choice(OCCUPATIONS),
                            mother_name=mother_name,
                            mother_phone=mother_phone,
                            mother_job=random.choice(OCCUPATIONS),
                            emergency_phone=father_phone,
                            telegram_chat_id=str(random.randint(100000000, 999999999)) if random.random() > 0.5 else None,
                        )
                        students_to_create.append(st)

                    Student.objects.bulk_create(students_to_create)
                    total_created += len(students_to_create)
                    self.stdout.write(self.style.SUCCESS(f"  [+] {cls.name} ({cls.code}): Created {len(students_to_create)} students (Total now: {existing_count + len(students_to_create)})."))

        self.stdout.write(self.style.SUCCESS(f"\n🎉 Successfully created {total_created} demo students across all classrooms!"))
