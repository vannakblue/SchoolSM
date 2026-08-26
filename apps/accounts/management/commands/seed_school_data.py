from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal
from datetime import datetime, date, time, timedelta

from apps.accounts.models import User, TelegramConfig, NotificationLog
from apps.academics.models import AcademicYear, Classroom, Subject, ClassSubject, Timetable, GradeLevelRule
from apps.teachers.models import Teacher, TeacherAttendance
from apps.students.models import Student
from apps.attendance.models import StudentAttendance
from apps.examinations.models import ExamTerm, Grade
from apps.finance.models import FeeCategory, Invoice, PaymentTransaction, Expense, Payroll
from apps.extras.models import Book, BookBorrowing, InventoryItem, InventoryTransaction, Announcement

class Command(BaseCommand):
    help = "Seeds database with comprehensive realistic dummy data matching exact MoEYS curriculum, official subject short codes, and scoring rules"

    def handle(self, *args, **options):
        self.stdout.write("Starting database seeding for SchoolSM (Exact MoEYS 14-Subject Short Codes & 8-Stream Rules)...")

        with transaction.atomic():
            # 1. Telegram Config
            t_config, _ = TelegramConfig.objects.get_or_create(
                id=1,
                defaults={
                    'bot_token': '123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ',
                    'chat_id': '-100123456789',
                    'is_active': True,
                    'notify_on_absence': True,
                    'notify_on_exam': True,
                    'notify_on_fee': True
                }
            )

            # 2. Users for all 4 Roles
            admin_user, _ = User.objects.get_or_create(
                username='admin',
                defaults={
                    'role': User.Role.ADMIN,
                    'is_staff': True,
                    'is_superuser': True,
                    'khmer_name': 'បណ្ឌិត សុខ វិបុល',
                    'latin_name': 'Dr. SOK VIBOL',
                    'phone': '012 345 678',
                    'email': 'admin@school.edu.kh'
                }
            )
            admin_user.set_password('admin123')
            admin_user.save()

            accountant_user, _ = User.objects.get_or_create(
                username='accountant',
                defaults={
                    'role': User.Role.ACCOUNTANT,
                    'khmer_name': 'អ្នកស្រី គង់ សុភា',
                    'latin_name': 'KONG SOPHEA',
                    'phone': '012 888 777',
                    'email': 'finance@school.edu.kh'
                }
            )
            accountant_user.set_password('password123')
            accountant_user.save()

            # 3. Academic Years
            ay_current, _ = AcademicYear.objects.get_or_create(
                name='2025-2026',
                defaults={
                    'start_date': date(2025, 9, 1),
                    'end_date': date(2026, 7, 15),
                    'is_current': True
                }
            )

            # 4. Exact 14 MoEYS Subjects with official short codes (R, D, K, I, G, H, M, Es, P, C, B, He, Ec, E)
            subjects_data = [
                ('តែងសេចក្តី', 'Composition / Essay', 'R', 2, '#4f46e5'),
                ('សរសេរតាមអាន', 'Dictation', 'D', 2, '#6366f1'),
                ('ភាសាខ្មែរ', 'Khmer Language', 'K', 4, '#0ea5e9'),
                ('សីលធម៌', 'Civics & Moral / Ethics', 'I', 2, '#06b6d4'),
                ('ភូមិវិទ្យា', 'Geography', 'G', 2, '#d97706'),
                ('ប្រវត្តិវិទ្យា', 'History', 'H', 2, '#f59e0b'),
                ('គណិតវិទ្យា', 'Mathematics', 'M', 4, '#dc2626'),
                ('ផែនដីវិទ្យា', 'Earth Science', 'Es', 2, '#84cc16'),
                ('រូបវិទ្យា', 'Physics', 'P', 3, '#8b5cf6'),
                ('គីមីវិទ្យា', 'Chemistry', 'C', 3, '#10b981'),
                ('ជីវវិទ្យា', 'Biology', 'B', 3, '#14b8a6'),
                ('គេហវិទ្យា', 'Home Economics', 'He', 2, '#ec4899'),
                ('សេដ្ឋកិច្ច', 'Economics', 'Ec', 2, '#f97316'),
                ('អង់គ្លេស', 'English Language', 'E', 3, '#3b82f6'),
            ]
            subjects = {}
            for name_kh, name_en, code, credit, color in subjects_data:
                sub = Subject.objects.filter(code=code).first() or Subject.objects.filter(name_kh=name_kh).first()
                if sub:
                    sub.name_kh = name_kh
                    sub.name_en = name_en
                    sub.code = code
                    sub.credit = credit
                    sub.color_code = color
                    sub.save()
                else:
                    sub = Subject.objects.create(
                        name_kh=name_kh,
                        name_en=name_en,
                        code=code,
                        credit=credit,
                        color_code=color
                    )
                subjects[name_kh] = sub

            # 5. Exact MoEYS Scoring Rules Matrix per Stream
            moeys_rules_map = {
                (7, 'GENERAL'): {
                    'តែងសេចក្តី': 60, 'សរសេរតាមអាន': 40, 'សីលធម៌': 50, 'ភូមិវិទ្យា': 50, 'ប្រវត្តិវិទ្យា': 50,
                    'គណិតវិទ្យា': 100, 'ផែនដីវិទ្យា': 50, 'រូបវិទ្យា': 50, 'គីមីវិទ្យា': 50, 'ជីវវិទ្យា': 50,
                    'គេហវិទ្យា': 50, 'អង់គ្លេស': 50
                },
                (8, 'GENERAL'): {
                    'តែងសេចក្តី': 60, 'សរសេរតាមអាន': 40, 'សីលធម៌': 50, 'ភូមិវិទ្យា': 50, 'ប្រវត្តិវិទ្យា': 50,
                    'គណិតវិទ្យា': 100, 'ផែនដីវិទ្យា': 50, 'រូបវិទ្យា': 50, 'គីមីវិទ្យា': 50, 'ជីវវិទ្យា': 50,
                    'គេហវិទ្យា': 50, 'អង់គ្លេស': 50
                },
                (9, 'GENERAL'): {
                    'តែងសេចក្តី': 60, 'សរសេរតាមអាន': 40, 'សីលធម៌': 35, 'ភូមិវិទ្យា': 32, 'ប្រវត្តិវិទ្យា': 33,
                    'គណិតវិទ្យា': 100, 'ផែនដីវិទ្យា': 25, 'រូបវិទ្យា': 35, 'គីមីវិទ្យា': 25, 'ជីវវិទ្យា': 35,
                    'គេហវិទ្យា': 50, 'អង់គ្លេស': 50
                },
                (10, 'GENERAL'): {
                    'ភាសាខ្មែរ': 150, 'សីលធម៌': 38, 'ភូមិវិទ្យា': 38, 'ប្រវត្តិវិទ្យា': 37,
                    'គណិតវិទ្យា': 150, 'ផែនដីវិទ្យា': 25, 'រូបវិទ្យា': 50, 'គីមីវិទ្យា': 37,
                    'ជីវវិទ្យា': 38, 'គេហវិទ្យា': 37, 'អង់គ្លេស': 100
                },
                (11, 'SOCIAL'): {
                    'ភាសាខ្មែរ': 125, 'សីលធម៌': 75, 'ភូមិវិទ្យា': 75, 'ប្រវត្តិវិទ្យា': 75,
                    'គណិតវិទ្យា': 75, 'ផែនដីវិទ្យា': 50, 'រូបវិទ្យា': 50, 'គីមីវិទ្យា': 50,
                    'ជីវវិទ្យា': 50, 'សេដ្ឋកិច្ច': 50, 'អង់គ្លេស': 50
                },
                (11, 'SCIENCE'): {
                    'ភាសាខ្មែរ': 75, 'សីលធម៌': 50, 'ភូមិវិទ្យា': 50, 'ប្រវត្តិវិទ្យា': 50,
                    'គណិតវិទ្យា': 125, 'ផែនដីវិទ្យា': 50, 'រូបវិទ្យា': 75, 'គីមីវិទ្យា': 75,
                    'ជីវវិទ្យា': 75, 'សេដ្ឋកិច្ច': 50, 'អង់គ្លេស': 50
                },
                (12, 'SOCIAL'): {
                    'ភាសាខ្មែរ': 125, 'សីលធម៌': 75, 'ភូមិវិទ្យា': 75, 'ប្រវត្តិវិទ្យា': 75,
                    'គណិតវិទ្យា': 75, 'ផែនដីវិទ្យា': 50, 'រូបវិទ្យា': 50, 'គីមីវិទ្យា': 50,
                    'ជីវវិទ្យា': 50, 'សេដ្ឋកិច្ច': 50, 'អង់គ្លេស': 50
                },
                (12, 'SCIENCE'): {
                    'ភាសាខ្មែរ': 75, 'សីលធម៌': 50, 'ភូមិវិទ្យា': 50, 'ប្រវត្តិវិទ្យា': 50,
                    'គណិតវិទ្យា': 125, 'ផែនដីវិទ្យា': 50, 'រូបវិទ្យា': 75, 'គីមីវិទ្យា': 75,
                    'ជីវវិទ្យា': 75, 'សេដ្ឋកិច្ច': 50, 'អង់គ្លេស': 50
                },
            }

            GradeLevelRule.objects.all().delete()
            for (g, track), sub_map in moeys_rules_map.items():
                order_num = 1
                for sub_name, max_sc in sub_map.items():
                    sub = subjects.get(sub_name)
                    if sub:
                        GradeLevelRule.objects.create(
                            grade_level=g,
                            track=track,
                            subject=sub,
                            max_score=Decimal(str(max_sc)),
                            order=order_num
                        )
                        order_num += 1

            # 6. Teachers
            teachers_info = [
                ('TCH-001', 'teacher1', 'លី វណ្ណារ៉ា', 'LY VANNARA', 'M', 'គណិតវិទ្យា & រូបវិទ្យា', 'បរិញ្ញាបត្រគរុកោសល្យ', Decimal('650.00'), '012 111 222'),
                ('TCH-002', 'teacher2', 'ចាន់ សុភាព', 'CHAN SOPHEAP', 'F', 'ភាសាខ្មែរ & តែងសេចក្តី', 'បរិញ្ញាបត្រអក្សរសាស្ត្រ', Decimal('600.00'), '012 222 333'),
                ('TCH-003', 'teacher3', 'កែវ វិបុល', 'KEO VIBOL', 'M', 'គីមីវិទ្យា & ជីវវិទ្យា', 'អនុបណ្ឌិតគីមីវិទ្យា', Decimal('620.00'), '012 333 444'),
                ('TCH-004', 'teacher4', 'ស៊ិន ស្រីនាង', 'SIN SREINEANG', 'F', 'អង់គ្លេស & គេហវិទ្យា', 'បរិញ្ញាបត្រភាសាអង់គ្លេស (TEFL)', Decimal('580.00'), '012 444 555'),
                ('TCH-005', 'teacher5', 'សេង ពិសិដ្ឋ', 'SENG PISETH', 'M', 'ប្រវត្តិវិទ្យា, ភូមិវិទ្យា & សីលធម៌', 'បរិញ្ញាបត្រប្រវត្តិវិទ្យា', Decimal('550.00'), '012 555 666'),
                ('TCH-006', 'teacher6', 'ម៉ែន សុផាត', 'MEN SOPHAT', 'M', 'ផែនដីវិទ្យា & សេដ្ឋកិច្ច', 'បរិញ្ញាបត្រវិទ្យាសាស្ត្រសេដ្ឋកិច្ច', Decimal('600.00'), '012 666 777'),
            ]
            teachers = {}
            for tid, uname, kh_name, en_name, gender, spec, qual, salary, phone in teachers_info:
                u, _ = User.objects.get_or_create(
                    username=uname,
                    defaults={'role': User.Role.TEACHER, 'khmer_name': kh_name, 'latin_name': en_name, 'phone': phone}
                )
                u.set_password('password123')
                u.save()

                tch, _ = Teacher.objects.get_or_create(
                    teacher_id=tid,
                    defaults={
                        'user': u,
                        'khmer_name': kh_name,
                        'latin_name': en_name,
                        'gender': gender,
                        'specialization': spec,
                        'qualification': qual,
                        'base_salary': salary,
                        'phone': phone,
                        'hire_date': date(2023, 10, 1),
                        'status': Teacher.Status.ACTIVE
                    }
                )
                teachers[tid] = tch

            # 7. Classrooms for all 8 streams
            classrooms_data = [
                ('7A', 'ថ្នាក់ទី ៧A', 7, Classroom.Track.GENERAL, 'បន្ទប់ 001', teachers['TCH-005']),
                ('8A', 'ថ្នាក់ទី ៨A', 8, Classroom.Track.GENERAL, 'បន្ទប់ 002', teachers['TCH-006']),
                ('9A', 'ថ្នាក់ទី ៩A', 9, Classroom.Track.GENERAL, 'បន្ទប់ 003', teachers['TCH-002']),
                ('10A', 'ថ្នាក់ទី ១០A', 10, Classroom.Track.GENERAL, 'បន្ទប់ 101', teachers['TCH-001']),
                ('11-SOC', 'ថ្នាក់ទី ១១ វិទ្យាសាស្ត្រសង្គម', 11, Classroom.Track.SOCIAL, 'បន្ទប់ 201', teachers['TCH-005']),
                ('11-SCI', 'ថ្នាក់ទី ១១ វិទ្យាសាស្ត្រ', 11, Classroom.Track.SCIENCE, 'បន្ទប់ 202', teachers['TCH-003']),
                ('12-SOC', 'ថ្នាក់ទី ១២ វិទ្យាសាស្ត្រសង្គម', 12, Classroom.Track.SOCIAL, 'បន្ទប់ 301', teachers['TCH-002']),
                ('12-SCI', 'ថ្នាក់ទី ១២ វិទ្យាសាស្ត្រ', 12, Classroom.Track.SCIENCE, 'បន្ទប់ 302', teachers['TCH-004']),
            ]
            classrooms = {}
            for code, name, grade, track, room, homeroom in classrooms_data:
                cls, _ = Classroom.objects.get_or_create(
                    code=code,
                    academic_year=ay_current,
                    defaults={'name': name, 'grade_level': grade, 'track': track, 'room_number': room, 'capacity': 40, 'homeroom_teacher': homeroom}
                )
                cls.name = name
                cls.grade_level = grade
                cls.track = track
                cls.save()
                classrooms[code] = cls

            c_10a = classrooms['10A']

            # 8. Students Data across classrooms
            students_list = [
                ('STU-2026-0001', 'student1', 'សុខ ចិន្តា', 'SOK CHINDA', 'F', date(2009, 5, 12), '012 900 101', 'សុខ វិជ្ជា', '012 900 100', 'វិស្វករ', 'ឈួន ម៉ាលី', '098 100 200', 'គ្រូបង្រៀន', c_10a, Student.ScholarshipType.FULL_PAY),
                ('STU-2026-0002', 'student2', 'ឡុង វិសាល', 'LONG VISAL', 'M', date(2009, 3, 20), '012 900 102', 'ឡុង សុធា', '012 900 200', 'អាជីវករ', 'ទូច ស្រីពៅ', '098 200 300', 'មេផ្ទះ', c_10a, Student.ScholarshipType.SCHOLARSHIP_50),
                ('STU-2026-0003', 'student3', 'ជា ស្រីម៉ៅ', 'CHEA SREYMAO', 'F', date(2009, 8, 15), '012 900 103', 'ជា រតនៈ', '012 900 300', 'មន្ត្រីរាជការ', 'នួន ចន្ធូ', '098 300 400', 'អាជីវករ', c_10a, Student.ScholarshipType.FULL_PAY),
                ('STU-2026-0004', 'student4', 'ហេង រតនា', 'HENG RATTANA', 'M', date(2009, 11, 2), '012 900 104', 'ហេង គឹមសាន', '012 900 400', 'វេជ្ជបណ្ឌិត', 'អ៊ុច គឹមហុង', '098 400 500', 'គិលានុបដ្ឋាយិកា', c_10a, Student.ScholarshipType.SCHOLARSHIP_100),
                ('STU-2026-0005', 'student5', 'គឹម ស្រីលីន', 'KIM SREYLIN', 'F', date(2009, 7, 24), '012 900 105', 'គឹម សម្បត្តិ', '012 900 500', 'អ្នកបើកបរ', 'សេង សុខុម', '098 500 600', 'លក់ដូរ', c_10a, Student.ScholarshipType.INSTALLMENT),
                ('STU-2026-0006', 'student6', 'មាស សុវណ្ណ', 'MEAS SOVANN', 'M', date(2012, 12, 5), '012 900 109', 'មាស សារ៉ាត់', '012 900 900', 'កសិករ', 'ស៊ុន ធីតា', '098 900 001', 'កសិករ', classrooms['7A'], Student.ScholarshipType.SCHOLARSHIP_50),
                ('STU-2026-0007', 'student7', 'ចេង ម៉ូនីកា', 'CHENG MONIKA', 'F', date(2011, 6, 14), '012 900 110', 'ចេង វ៉ាន់នី', '012 900 910', 'សាស្ត្រាចារ្យ', 'ហួត ចរិយា', '098 900 002', 'ឱសថការី', classrooms['8A'], Student.ScholarshipType.FULL_PAY),
                ('STU-2026-0008', 'student8', 'ថៃ វិចិត្រ', 'THAI VICHEKA', 'M', date(2010, 1, 10), '012 900 111', 'ថៃ គង់', '012 900 911', 'អ្នកនិពន្ធ', 'លឹម គឹមសួរ', '098 900 003', 'មេផ្ទះ', classrooms['9A'], Student.ScholarshipType.FULL_PAY),
                ('STU-2026-0009', 'student9', 'រឿន សុធី', 'ROEUN SOTHY', 'M', date(2008, 10, 22), '012 900 112', 'រឿន ថា', '012 900 912', 'អាជីវករ', 'អេង ស្រីលក្ខណ៍', '098 900 004', 'លក់ដូរ', classrooms['11-SCI'], Student.ScholarshipType.FULL_PAY),
                ('STU-2026-0010', 'student10', 'កែវ មុនីរ័ត្ន', 'KEO MONIROTH', 'F', date(2008, 4, 18), '012 900 113', 'កែវ សុខឿន', '012 900 913', 'មន្ត្រីរាជការ', 'ស្រីមុំ', '098 900 005', 'មេផ្ទះ', classrooms['11-SOC'], Student.ScholarshipType.FULL_PAY),
                ('STU-2026-0011', 'student11', 'យិន ច័ន្ទរិទ្ធ', 'YIN CHANRITH', 'M', date(2007, 3, 11), '012 900 114', 'យិន សំអាត', '012 900 914', 'វិស្វករ', 'សុភា', '098 900 006', 'គ្រូ', classrooms['12-SCI'], Student.ScholarshipType.SCHOLARSHIP_100),
                ('STU-2026-0012', 'student12', 'សួស ចរិយា', 'SUOS CHORIYA', 'F', date(2007, 9, 29), '012 900 115', 'សួស ផល', '012 900 915', 'អាជីវករ', 'ធីតា', '098 900 007', 'លក់ដូរ', classrooms['12-SOC'], Student.ScholarshipType.FULL_PAY),
            ]

            students_objs = []
            for sid, uname, kh_name, en_name, gender, dob, phone, f_name, f_phone, f_job, m_name, m_phone, m_job, cls, sch in students_list:
                stu_u, _ = User.objects.get_or_create(
                    username=uname,
                    defaults={'role': User.Role.STUDENT, 'khmer_name': kh_name, 'latin_name': en_name, 'phone': phone}
                )
                stu_u.set_password('password123')
                stu_u.save()

                stu, _ = Student.objects.get_or_create(
                    student_id=sid,
                    defaults={
                        'user': stu_u,
                        'khmer_name': kh_name,
                        'latin_name': en_name,
                        'gender': gender,
                        'date_of_birth': dob,
                        'phone': phone,
                        'father_name': f_name,
                        'father_phone': f_phone,
                        'father_job': f_job,
                        'mother_name': m_name,
                        'mother_phone': m_phone,
                        'mother_job': m_job,
                        'classroom': cls,
                        'academic_year': ay_current,
                        'scholarship_type': sch,
                        'status': Student.Status.ACTIVE,
                        'telegram_chat_id': '-100123456789'
                    }
                )
                stu.classroom = cls
                stu.save()
                students_objs.append(stu)

            # 9. Attendance
            today = date.today()
            for i in range(5):
                att_date = today - timedelta(days=i)
                if att_date.weekday() < 6:
                    for stu in students_objs:
                        status = StudentAttendance.Status.PRESENT
                        if stu.student_id == 'STU-2026-0005' and i in [1, 2, 3]:
                            status = StudentAttendance.Status.ABSENT
                        StudentAttendance.objects.update_or_create(
                            student=stu,
                            date=att_date,
                            session=StudentAttendance.Session.FULL_DAY,
                            defaults={'classroom': stu.classroom, 'status': status, 'recorded_by': admin_user}
                        )

            # 10. Exam Term & Sample Grades matching exact max score rules
            term_sem1, _ = ExamTerm.objects.get_or_create(
                name='ប្រឡងឆមាសទី១ ឆ្នាំ២០២៥-២០២៦',
                academic_year=ay_current,
                defaults={
                    'term_type': ExamTerm.TermType.SEMESTER_1,
                    'start_date': date(2026, 1, 20),
                    'end_date': date(2026, 1, 25),
                    'is_published': True
                }
            )

            # Grade 10A sample scores (Max scores: ភាសាខ្មែរ:150, សីលធម៌:38, ភូមិ:38, ប្រវត្តិ:37, គណិត:150, ផែនដី:25, រូប:50, គីមី:37, ជីវ:38, គេហ:37, អង់គ្លេស:100 = 700)
            g10_scores = {
                'STU-2026-0001': {'ភាសាខ្មែរ': 142, 'សីលធម៌': 36, 'ភូមិវិទ្យា': 35, 'ប្រវត្តិវិទ្យា': 35, 'គណិតវិទ្យា': 145, 'ផែនដីវិទ្យា': 24, 'រូបវិទ្យា': 48, 'គីមីវិទ្យា': 35, 'ជីវវិទ្យា': 36, 'គេហវិទ្យា': 35, 'អង់គ្លេស': 95},
                'STU-2026-0002': {'ភាសាខ្មែរ': 125, 'សីលធម៌': 32, 'ភូមិវិទ្យា': 30, 'ប្រវត្តិវិទ្យា': 31, 'គណិតវិទ្យា': 130, 'ផែនដីវិទ្យា': 20, 'រូបវិទ្យា': 40, 'គីមីវិទ្យា': 30, 'ជីវវិទ្យា': 32, 'គេហវិទ្យា': 30, 'អង់គ្លេស': 85},
                'STU-2026-0003': {'ភាសាខ្មែរ': 110, 'សីលធម៌': 28, 'ភូមិវិទ្យា': 28, 'ប្រវត្តិវិទ្យា': 26, 'គណិតវិទ្យា': 115, 'ផែនដីវិទ្យា': 18, 'រូបវិទ្យា': 36, 'គីមីវិទ្យា': 27, 'ជីវវិទ្យា': 28, 'គេហវិទ្យា': 28, 'អង់គ្លេស': 75},
                'STU-2026-0004': {'ភាសាខ្មែរ': 146, 'សីលធម៌': 37, 'ភូមិវិទ្យា': 37, 'ប្រវត្តិវិទ្យា': 36, 'គណិតវិទ្យា': 148, 'ផែនដីវិទ្យា': 25, 'រូបវិទ្យា': 49, 'គីមីវិទ្យា': 36, 'ជីវវិទ្យា': 37, 'គេហវិទ្យា': 36, 'អង់គ្លេស': 98},
                'STU-2026-0005': {'ភាសាខ្មែរ': 70, 'សីលធម៌': 18, 'ភូមិវិទ្យា': 18, 'ប្រវត្តិវិទ្យា': 18, 'គណិតវិទ្យា': 65, 'ផែនដីវិទ្យា': 12, 'រូបវិទ្យា': 24, 'គីមីវិទ្យា': 18, 'ជីវវិទ្យា': 18, 'គេហវិទ្យា': 18, 'អង់គ្លេស': 45},
            }

            for sid, sub_scores in g10_scores.items():
                stu = Student.objects.filter(student_id=sid).first()
                if stu:
                    rules = stu.classroom.get_subject_rules()
                    rule_map = {r.subject.name_kh: r.max_score for r in rules}
                    for sub_name, score_val in sub_scores.items():
                        sub = subjects.get(sub_name)
                        max_sc = rule_map.get(sub_name, Decimal('100.00'))
                        if sub:
                            Grade.objects.update_or_create(
                                student=stu,
                                subject=sub,
                                exam_term=term_sem1,
                                classroom=stu.classroom,
                                defaults={
                                    'score': Decimal(str(score_val)),
                                    'max_score': max_sc
                                }
                            )

            # 11. Announcements
            Announcement.objects.get_or_create(
                title='សេចក្តីជូនដំណឹងស្តីពីការប្រជុំមាតាបិតាសិស្សឆមាសទី១',
                defaults={
                    'category': Announcement.Category.PARENT_MEETING,
                    'target_audience': Announcement.TargetAudience.ALL,
                    'priority': Announcement.Priority.IMPORTANT,
                    'content': 'គណៈគ្រប់គ្រងវិទ្យាល័យអន្តរជាតិ សាលារៀន SM សូមគោរពអញ្ជើញលោក-លោកស្រីជាមាតាបិតា និងអាណាព្យាបាលសិស្សគ្រប់កម្រិតថ្នាក់ (ទី៧ ដល់ ទី១២) ចូលរួមការប្រជុំពិភាក្សាអំពីលទ្ធផលសិក្សា និងការអភិវឌ្ឍសីលធម៌របស់សិស្ស នៅថ្ងៃអាទិត្យ ទី១ ខែមីនា ឆ្នាំ២០២៦ វេលាម៉ោង ៨:០០ ព្រឹក នៅសាលប្រជុំធំ។',
                    'created_by': admin_user,
                    'is_published': True
                }
            )

            # 12. Fee Invoices
            fee_tuition, _ = FeeCategory.objects.get_or_create(
                name='ថ្លៃសិក្សាឆមាសទី១ (Semester 1 Tuition)',
                defaults={'default_amount': Decimal('300.00'), 'description': 'ថ្លៃសិក្សាឆមាសទី១'}
            )
            inv1, _ = Invoice.objects.get_or_create(
                invoice_no='INV-2026-0001',
                defaults={
                    'student': students_objs[0],
                    'fee_category': fee_tuition,
                    'academic_year': ay_current,
                    'original_amount': Decimal('300.00'),
                    'discount_percent': Decimal('0.00'),
                    'final_amount': Decimal('300.00'),
                    'paid_amount': Decimal('300.00'),
                    'due_date': today + timedelta(days=10),
                    'status': Invoice.Status.PAID,
                }
            )
            PaymentTransaction.objects.get_or_create(
                invoice=inv1,
                amount=Decimal('300.00'),
                defaults={
                    'payment_method': PaymentTransaction.PaymentMethod.KHQR_BAKONG,
                    'receipt_number': 'REC-2026-0001',
                    'received_by': accountant_user,
                    'transaction_reference': 'BAKONG-TX-888999'
                }
            )

            # 13. Payroll
            for tid, tch in teachers.items():
                p, _ = Payroll.objects.get_or_create(
                    teacher=tch,
                    month=today.month,
                    year=today.year,
                    defaults={'base_salary': tch.base_salary, 'bonus_allowance': Decimal('20.00')}
                )
                p.calculate()
                p.save()

        self.stdout.write(self.style.SUCCESS("[OK] Successfully seeded 14 subjects with exact short codes, 8 grade streams, and exact MoEYS scoring rules!"))
