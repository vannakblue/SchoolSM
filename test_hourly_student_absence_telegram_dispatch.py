import os
import sys
import django
from datetime import date, datetime, timedelta, time

sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User, TelegramConfig, NotificationLog

from apps.attendance.models import StudentAttendance, AttendanceSetting
from apps.academics.models import Classroom, Subject, AcademicYear
from apps.academics.utils import get_active_academic_year
from apps.students.models import Student
from apps.teachers.models import Teacher
from apps.attendance.telegram_utils import (
    send_classroom_attendance_telegram,
    send_hourly_period_absence_dispatch
)

def run_tests():
    print("=" * 85)
    print("TEST: HOURLY STUDENT ABSENCE TELEGRAM DISPATCH (ALPHABETICAL & GRADE 7-12 HIERARCHY)")
    print("=" * 85)

    today = date.today()
    active_year = get_active_academic_year()

    # 1. Setup Telegram Config & Settings
    config = TelegramConfig.objects.first()
    if not config:
        config = TelegramConfig.objects.create(
            bot_token='123456789:ABCdefGHIjklMNOpqrSTUvwxYZ',
            chat_id='-100999888777',
            is_active=False
        )
    else:
        config.is_active = False
        config.save()

    att_settings = AttendanceSetting.get_settings()
    att_settings.hourly_dispatch_enabled = True
    att_settings.dispatch_to_guardians = True
    att_settings.dispatch_to_homeroom = True
    att_settings.dispatch_to_management = True
    att_settings.management_chat_id = '-100111222333, -100444555666'
    att_settings.custom_dispatch_groups = '-100777888999'
    att_settings.period_dispatch_times = {
        "1": "07:35", "2": "08:30", "3": "09:25", "4": "10:20",
        "5": "13:35", "6": "14:30", "7": "15:25", "8": "16:20"
    }
    att_settings.save()

    # 2. Setup Classrooms across Grade Levels (7 to 12)
    t_teacher = Teacher.objects.filter(status='ACTIVE').first()
    if not t_teacher.user:
        u = User.objects.create_user(username='t_hourly_test', password='password123', role='TEACHER')
        t_teacher.user = u
        t_teacher.save()
    t_teacher.user.telegram_chat_id = '-100333444555'
    t_teacher.user.save()

    cls7a, _ = Classroom.objects.get_or_create(code='7A_TEST', academic_year=active_year, defaults={'name': 'ថ្នាក់ទី 7A', 'grade_level': 7, 'homeroom_teacher': t_teacher, 'telegram_chat_id': '-100701010101'})
    cls8b, _ = Classroom.objects.get_or_create(code='8B_TEST', academic_year=active_year, defaults={'name': 'ថ្នាក់ទី 8B', 'grade_level': 8, 'homeroom_teacher': t_teacher, 'telegram_chat_id': '-100802020202'})
    cls12a, _ = Classroom.objects.get_or_create(code='12A_TEST', academic_year=active_year, defaults={'name': 'ថ្នាក់ទី 12A', 'grade_level': 12, 'homeroom_teacher': t_teacher, 'telegram_chat_id': '-100120120120'})

    # 3. Create/Update Students with names covering Khmer Alphabet
    subject = Subject.objects.first()

    # In 7A: create students with names starting with គ, ច, ស, ហ
    s1, _ = Student.objects.get_or_create(student_id='STU_TEST_01', defaults={'date_of_birth': date(2010, 1, 1), 'gender': 'M'})
    s1.khmer_name = 'សុខ វិបុល'
    s1.classroom = cls7a
    s1.status = 'ACTIVE'
    s1.telegram_chat_id = '-100555111'
    s1.save()

    s2, _ = Student.objects.get_or_create(student_id='STU_TEST_02', defaults={'date_of_birth': date(2010, 1, 1), 'gender': 'F'})
    s2.khmer_name = 'កែវ សុខា'
    s2.classroom = cls7a
    s2.status = 'ACTIVE'
    s2.telegram_chat_id = '-100555222'
    s2.save()

    s3, _ = Student.objects.get_or_create(student_id='STU_TEST_03', defaults={'date_of_birth': date(2010, 1, 1), 'gender': 'M'})
    s3.khmer_name = 'ចាន់ ដារ៉ា'
    s3.classroom = cls7a
    s3.status = 'ACTIVE'
    s3.telegram_chat_id = '-100555333'
    s3.save()

    s4, _ = Student.objects.get_or_create(student_id='STU_TEST_04', defaults={'date_of_birth': date(2010, 1, 1), 'gender': 'M'})
    s4.khmer_name = 'ហ៊ាន ពិសិដ្ឋ'
    s4.classroom = cls7a
    s4.status = 'ACTIVE'
    s4.telegram_chat_id = '-100555444'
    s4.save()

    # In 8B: create student
    s5, _ = Student.objects.get_or_create(student_id='STU_TEST_05', defaults={'date_of_birth': date(2010, 1, 1), 'gender': 'F'})
    s5.khmer_name = 'នាង សុភា'
    s5.classroom = cls8b
    s5.status = 'ACTIVE'
    s5.telegram_chat_id = '-100555555'
    s5.save()

    # In 12A: create student
    s6, _ = Student.objects.get_or_create(student_id='STU_TEST_06', defaults={'date_of_birth': date(2010, 1, 1), 'gender': 'F'})
    s6.khmer_name = 'ឡុង ចិន្តា'
    s6.classroom = cls12a
    s6.status = 'ACTIVE'
    s6.telegram_chat_id = '-100555666'
    s6.save()



    # 4. Record Student Attendance for Period 1
    StudentAttendance.objects.filter(date=today, period_number=1).delete()
    
    # 7A records:
    StudentAttendance.objects.create(student=s1, classroom=cls7a, date=today, session='MORNING', period_number=1, status=StudentAttendance.Status.ABSENT, subject=subject, notes='ឈឺពោះ', recorded_by=t_teacher.user)
    StudentAttendance.objects.create(student=s2, classroom=cls7a, date=today, session='MORNING', period_number=1, status=StudentAttendance.Status.ABSENT, subject=subject, notes='គ្មានមូលហេតុ', recorded_by=t_teacher.user)
    StudentAttendance.objects.create(student=s3, classroom=cls7a, date=today, session='MORNING', period_number=1, status=StudentAttendance.Status.PERMISSION, subject=subject, notes='សុំច្បាប់ការងារផ្ទះ', recorded_by=t_teacher.user)
    StudentAttendance.objects.create(student=s4, classroom=cls7a, date=today, session='MORNING', period_number=1, status=StudentAttendance.Status.LATE, subject=subject, notes='យឺត ១៥ នាទី', recorded_by=t_teacher.user)

    # 8B record:
    StudentAttendance.objects.create(student=s5, classroom=cls8b, date=today, session='MORNING', period_number=1, status=StudentAttendance.Status.ABSENT, subject=subject, notes='ខកម៉ោង', recorded_by=t_teacher.user)

    # 12A record:
    StudentAttendance.objects.create(student=s6, classroom=cls12a, date=today, session='MORNING', period_number=1, status=StudentAttendance.Status.PERMISSION, subject=subject, notes='ប្រឡងបាក់ឌុបត្រៀម', recorded_by=t_teacher.user)

    # ---------------------------------------------------------
    # TEST 1: Alphabetical Sorting in Classroom Absence Report
    # ---------------------------------------------------------
    print("\n--- TEST 1: Alphabetical Sorting of Absent Students in Classroom Report ---")
    NotificationLog.objects.all().delete()
    res_class = send_classroom_attendance_telegram(cls7a, today, session='MORNING', period_number=1, custom_chat_id='-100701010101', sender_user=t_teacher.user)
    assert res_class['success'] is True

    class_log = NotificationLog.objects.filter(recipient_phone__isnull=True).order_by('-created_at').first()
    assert class_log is not None
    msg_body = class_log.message
    print("Classroom Report Snippet:")
    print("-" * 40)
    print(msg_body)
    print("-" * 40)

    # Verify that in absent list, 'កែវ សុខា' comes before 'សុខ វិបុល' (Alphabetical)
    pos_kaev = msg_body.find('កែវ សុខា')
    pos_sokh = msg_body.find('សុខ វិបុល')
    assert pos_kaev != -1 and pos_sokh != -1
    assert pos_kaev < pos_sokh, "កែវ សុខា (starts with ក) must appear before សុខ វិបុល (starts with ស)"
    print("✅ Verified: Student names are sorted strictly alphabetically by Khmer name.")

    # ---------------------------------------------------------
    # TEST 2: Hourly Absence Dispatch to Guardians, Homeroom & Management
    # ---------------------------------------------------------
    print("\n--- TEST 2: Hourly Absence Auto-Dispatch to All 3 Destinations ---")
    NotificationLog.objects.all().delete()
    dispatch_res = send_hourly_period_absence_dispatch(today, period_number=1, session='MORNING', sender_user=t_teacher.user, force=True)
    assert dispatch_res['success'] is True
    assert dispatch_res['guardian_sent_count'] >= 6
    assert dispatch_res['homeroom_sent_count'] >= 3
    assert dispatch_res['management_sent_count'] >= 3 # management_chat_ids + custom_dispatch_groups
    print(f"✅ Dispatch summary: {dispatch_res['message']}")

    # Verify Direct Guardian Notification
    parent_logs = list(NotificationLog.objects.filter(recipient_type="Parent"))
    print(f"Parent logs count: {len(parent_logs)}")
    for pl in parent_logs:
        print(f"Parent Log: Recipient={pl.recipient_name}, Title={pl.title}, Message Snippet={pl.message[:60]}")
    assert len(parent_logs) > 0
    first_parent = parent_logs[0]
    assert 'ថ្នាក់រៀន' in first_parent.message
    print("✅ Verified: Direct Guardian received personalized alert.")


    # ---------------------------------------------------------
    # TEST 3: Schoolwide Hierarchy Ordering from Grade 7 to 12
    # ---------------------------------------------------------
    print("\n--- TEST 3: Master Absence Summary Ordered by Grade 7 to 12 Hierarchy ---")
    mgmt_log = NotificationLog.objects.filter(recipient_type="Management Group").first()
    assert mgmt_log is not None
    mgmt_msg = mgmt_log.message
    print("Master Management Hierarchy Report:")
    print("-" * 40)
    print(mgmt_msg)
    print("-" * 40)


    # Check hierarchy order: Grade 7 appears before Grade 8, and Grade 8 appears before Grade 12
    pos_7a = mgmt_msg.find('ថ្នាក់ទី 7A')
    pos_8b = mgmt_msg.find('ថ្នាក់ទី 8B')
    pos_12a = mgmt_msg.find('ថ្នាក់ទី 12A')

    assert pos_7a != -1 and pos_8b != -1 and pos_12a != -1
    assert pos_7a < pos_8b < pos_12a, "Classrooms must be strictly ordered from Grade 7 to Grade 12 (7A -> 8B -> 12A)"
    print("✅ Verified: Master Management report orders classrooms strictly from Grade 7 to 12.")

    # ---------------------------------------------------------
    # TEST 4: Admin Hub UI & Instant Test Dispatch (dispatch_hourly_now)
    # ---------------------------------------------------------
    print("\n--- TEST 4: Admin Hub POST action='dispatch_hourly_now' ---")
    admin_user = User.objects.filter(role='ADMIN').first()
    client_admin = Client()
    client_admin.force_login(admin_user)

    res_post = client_admin.post('/attendance/admin-hub/', {
        'action': 'dispatch_hourly_now',
        'target_date': today.strftime('%Y-%m-%d'),
        'period_number': '1'
    }, follow=True)
    assert res_post.status_code == 200
    print("✅ Verified: Admin Hub instant hourly dispatch endpoint executed with 200 OK.")

    print("\n" + "=" * 85)
    print("🎉 ALL HOURLY STUDENT ABSENCE TELEGRAM DISPATCH TESTS PASSED 100%!")
    print("=" * 85)

if __name__ == '__main__':
    run_tests()
