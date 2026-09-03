import os
import django
import json
import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from apps.academics.models import (
    AcademicYear, Classroom, Subject, ClassSubject, Timetable, TimetableVersion, GradeLevel
)
from apps.teachers.models import Teacher
from apps.students.models import Student
from apps.attendance.models import StudentAttendance

User = get_user_model()

def run_tests():
    print("=" * 70)
    print("TESTING TIMETABLE BACKUP, VERSION RESTORE & ATTENDANCE INTEGRATION")
    print("=" * 70)

    # 1. Setup Admin user and test client
    admin_user = User.objects.filter(is_superuser=True).first()
    if not admin_user:
        admin_user = User.objects.create_superuser('admin_test', 'admin@test.com', 'adminpass123')
    
    client = Client()
    client.force_login(admin_user)

    # 2. Get/create active academic year, grade, classroom, subjects, teachers
    year, _ = AcademicYear.objects.get_or_create(
        name="2025-2026",
        defaults={"is_active": True, "start_date": datetime.date(2025, 10, 1), "end_date": datetime.date(2026, 8, 31)}
    )
    year.is_active = True
    year.save()

    classroom = Classroom.objects.filter(academic_year=year, code="10A").first()
    if not classroom:
        classroom = Classroom.objects.create(
            academic_year=year,
            name="10A",
            code="10A",
            grade_level=10
        )

    subj_math, _ = Subject.objects.get_or_create(code="M", defaults={"name_kh": "គណិតវិទ្យា", "name_en": "Mathematics"})
    subj_khmer, _ = Subject.objects.get_or_create(code="K", defaults={"name_kh": "ភាសាខ្មែរ", "name_en": "Khmer Literature"})

    teacher_1, _ = Teacher.objects.get_or_create(
        teacher_id="TCH001",
        defaults={"khmer_name": "គ្រូ គណិត", "latin_name": "Math Teacher", "status": "ACTIVE", "specialization": "គណិត"}
    )
    teacher_2, _ = Teacher.objects.get_or_create(
        teacher_id="TCH002",
        defaults={"khmer_name": "គ្រូ ខ្មែរ", "latin_name": "Khmer Teacher", "status": "ACTIVE", "specialization": "ខ្មែរ"}
    )

    # Student
    student = Student.objects.filter(status='ACTIVE').first()
    if not student:
        student = Student.objects.create(
            student_id="STU001",
            khmer_name="សិស្ស សាកល្បង",
            latin_name="Test Student",
            gender="M",
            date_of_birth=datetime.date(2008, 1, 1),
            status="ACTIVE"
        )

    # 3. Setup Live Timetable Version 1 (លើកទី១):
    # Monday Period 1: Math (Teacher 1)
    # Monday Period 2: Khmer (Teacher 2)
    Timetable.objects.filter(classroom=classroom).delete()
    t1 = Timetable.objects.create(
        classroom=classroom,
        subject=subj_math,
        teacher=teacher_1,
        day_of_week=1, # Monday
        period_number=1,
        start_time=datetime.time(7, 0),
        end_time=datetime.time(7, 50)
    )
    t2 = Timetable.objects.create(
        classroom=classroom,
        subject=subj_khmer,
        teacher=teacher_2,
        day_of_week=1, # Monday
        period_number=2,
        start_time=datetime.time(7, 50),
        end_time=datetime.time(8, 40)
    )

    # Save Version 1 via API
    resp_v1 = client.post(
        '/academics/timetable/versions/save/',
        data=json.dumps({
            'academic_year_id': year.id,
            'version_number': 1,
            'title': 'លើកទី ១ (ដើមឆ្នាំ)',
            'note': 'កាលវិភាគដើមឆ្នាំ ២០២៥-២០២៦',
            'set_active': True
        }),
        content_type='application/json'
    )
    assert resp_v1.status_code == 200, f"Failed to save Version 1: {resp_v1.content}"
    v1_id = resp_v1.json()['version']['id']
    print(f"✅ 1. Created and backed up Timetable Version 1 (ID={v1_id})")

    # 4. Modify Live Timetable to Version 2 (លើកទី២ - Switched subjects/teachers):
    # Monday Period 1: Khmer (Teacher 2)
    # Monday Period 2: Math (Teacher 1)
    Timetable.objects.filter(classroom=classroom).delete()
    Timetable.objects.create(
        classroom=classroom,
        subject=subj_khmer,
        teacher=teacher_2,
        day_of_week=1,
        period_number=1,
        start_time=datetime.time(7, 0),
        end_time=datetime.time(7, 50)
    )
    Timetable.objects.create(
        classroom=classroom,
        subject=subj_math,
        teacher=teacher_1,
        day_of_week=1,
        period_number=2,
        start_time=datetime.time(7, 50),
        end_time=datetime.time(8, 40)
    )

    # Save Version 2 via API
    resp_v2 = client.post(
        '/academics/timetable/versions/save/',
        data=json.dumps({
            'academic_year_id': year.id,
            'version_number': 2,
            'title': 'លើកទី ២ (ឆមាសទី១ កែសម្រួល)',
            'note': 'កែសម្រួលដូរវេនគ្រូ',
            'set_active': True
        }),
        content_type='application/json'
    )
    assert resp_v2.status_code == 200, f"Failed to save Version 2: {resp_v2.content}"
    v2_id = resp_v2.json()['version']['id']
    print(f"✅ 2. Created and backed up Timetable Version 2 (ID={v2_id})")

    # 5. RESTORE BACK TO VERSION 1 via API
    resp_restore_v1 = client.post(
        f'/academics/timetable/versions/{v1_id}/restore/',
        data=json.dumps({'sync_teachers': True}),
        content_type='application/json'
    )
    assert resp_restore_v1.status_code == 200, f"Failed to restore Version 1: {resp_restore_v1.content}"
    print(f"✅ 3. Restored Timetable Version 1 successfully!")

    # Verify live timetable in DB has Math at Period 1, Khmer at Period 2
    live_p1 = Timetable.objects.filter(classroom=classroom, day_of_week=1, period_number=1).first()
    live_p2 = Timetable.objects.filter(classroom=classroom, day_of_week=1, period_number=2).first()
    assert live_p1.subject == subj_math and live_p1.teacher == teacher_1, "Version 1 P1 should be Math/Teacher 1"
    assert live_p2.subject == subj_khmer and live_p2.teacher == teacher_2, "Version 1 P2 should be Khmer/Teacher 2"
    print(f"   -> Verified live DB: Period 1 = {live_p1.subject.name_kh} ({live_p1.teacher.khmer_name}), Period 2 = {live_p2.subject.name_kh} ({live_p2.teacher.khmer_name})")

    # 6. RESTORE TO VERSION 2 via API
    resp_restore_v2 = client.post(
        f'/academics/timetable/versions/{v2_id}/restore/',
        data=json.dumps({'sync_teachers': True}),
        content_type='application/json'
    )
    assert resp_restore_v2.status_code == 200, f"Failed to restore Version 2: {resp_restore_v2.content}"
    print(f"✅ 4. Restored Timetable Version 2 successfully!")

    # Verify live timetable in DB now has Khmer at Period 1, Math at Period 2
    live_p1_v2 = Timetable.objects.filter(classroom=classroom, day_of_week=1, period_number=1).first()
    live_p2_v2 = Timetable.objects.filter(classroom=classroom, day_of_week=1, period_number=2).first()
    assert live_p1_v2.subject == subj_khmer and live_p1_v2.teacher == teacher_2, "Version 2 P1 should be Khmer/Teacher 2"
    assert live_p2_v2.subject == subj_math and live_p2_v2.teacher == teacher_1, "Version 2 P2 should be Math/Teacher 1"
    print(f"   -> Verified live DB: Period 1 = {live_p1_v2.subject.name_kh} ({live_p1_v2.teacher.khmer_name}), Period 2 = {live_p2_v2.subject.name_kh} ({live_p2_v2.teacher.khmer_name})")

    # 7. TEST ATTENDANCE SYSTEM INTEGRATION
    # Attendance for Monday:
    test_date = datetime.date(2025, 10, 6) # This is a Monday (isoweekday = 1)
    
    # Check student attendance slot query matches Version 2 (Period 1 -> Khmer/Teacher 2)
    tt_slot = Timetable.objects.filter(
        classroom=classroom,
        period_number=1,
        day_of_week=test_date.isoweekday()
    ).first()
    assert tt_slot is not None and tt_slot.subject == subj_khmer and tt_slot.teacher == teacher_2, "Attendance query should match Version 2"

    # Record attendance
    att, created = StudentAttendance.objects.update_or_create(
        student=student,
        date=test_date,
        session=StudentAttendance.Session.MORNING,
        period_number=1,
        defaults={
            'classroom': classroom,
            'status': StudentAttendance.Status.PRESENT,
            'subject': tt_slot.subject,
            'recorded_by': admin_user
        }
    )
    assert att.subject == subj_khmer, "Recorded attendance subject matches active version"
    print(f"✅ 5. Student Attendance seamlessly recorded for active restored Version 2 ({att.subject.name_kh})")

    # 8. TEST DAILY SIGN-IN REPORT VIEW & STUDENT-TEACHER TIMETABLE VIEW
    resp_daily = client.get('/academics/timetable/daily-reports/')
    assert resp_daily.status_code == 200, "Daily report view should render 200 OK"

    resp_st_tt = client.get('/academics/timetable/student-teacher/')
    assert resp_st_tt.status_code == 200, "Student-teacher timetable view should render 200 OK"
    print("✅ 6. Daily Attendance Reports & Student-Teacher Timetable views rendered 200 OK with restored version!")

    print("\n" + "=" * 70)
    print("🎉 ALL TIMETABLE BACKUP, VERSION RESTORE & ATTENDANCE TESTS PASSED 100%!")
    print("=" * 70)

if __name__ == '__main__':
    run_tests()
