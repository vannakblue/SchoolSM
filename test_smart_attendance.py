import os
import sys
import django
from datetime import datetime, date

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.academics.models import AcademicYear, Classroom, Subject, Timetable
from apps.teachers.models import Teacher
from apps.students.models import Student
from apps.attendance.models import StudentAttendance

def test_smart_attendance():
    print("==========================================================================")
    print("TEST: SMART TIMETABLE AUTO-DETECTION & ABSENCE-FOCUSED ATTENDANCE")
    print("==========================================================================")

    client = Client()

    # 1. Setup Academic Year
    ay, _ = AcademicYear.objects.get_or_create(
        name="2026-2027",
        defaults={'start_date': '2026-09-01', 'end_date': '2027-07-15', 'is_current': True}
    )
    AcademicYear.objects.filter(id=ay.id).update(is_current=True)
    AcademicYear.objects.exclude(id=ay.id).update(is_current=False)


    # 2. Setup Teacher & User
    user, _ = User.objects.get_or_create(
        username="teacher_att_test",
        defaults={'role': 'TEACHER', 'first_name': 'សំ', 'last_name': 'សុក'}
    )
    user.role = 'TEACHER'
    user.save()

    teacher, _ = Teacher.objects.get_or_create(
        teacher_id="TCH-ATT-01",
        defaults={'khmer_name': 'លោកគ្រូ សំ សុក', 'status': 'ACTIVE', 'max_weekly_hours': 18}
    )
    teacher.user = user
    teacher.save()
    client.force_login(user)


    # 3. Setup Classroom & Students
    cls_7a = Classroom.objects.filter(code='7A', academic_year=ay).first()
    if not cls_7a:
        cls_7a = Classroom.objects.create(code='7A', name='ថ្នាក់ទី ៧A', grade_level=7, academic_year=ay)

    students = Student.objects.filter(classroom=cls_7a, academic_year=ay)
    if students.count() < 5:
        # Create 5 test students
        for i in range(1, 6):
            Student.objects.create(
                student_id=f"2607ATT{i:03d}",
                khmer_name=f"សិស្ស តេស្ត {i}",
                latin_name=f"Student Test {i}",
                gender='M' if i % 2 == 0 else 'F',
                date_of_birth=date(2013, 1, 1),
                classroom=cls_7a,
                academic_year=ay,
                status='ACTIVE'
            )
        students = Student.objects.filter(classroom=cls_7a, academic_year=ay)

    st1 = students[0]
    st2 = students[1]
    st3 = students[2]
    total_students_count = students.count()

    # 4. Setup Timetable Slot for Teacher Today (active at current time)
    sub_math, _ = Subject.objects.get_or_create(code='M', defaults={'name_kh': 'គណិតវិទ្យា', 'name_en': 'Math', 'category': 'SCIENCE'})
    now_dt = datetime.now()
    today_dow = now_dt.date().isoweekday()
    if today_dow > 6:
        today_dow = 1 # Monday if Sunday

    cur_h = now_dt.hour
    cur_m = now_dt.minute
    st_time_str = f"{cur_h:02d}:00"
    end_time_str = f"{(cur_h + 1) % 24:02d}:00" if cur_h < 23 else "23:59"

    Timetable.objects.filter(teacher=teacher).delete()
    tt_slot = Timetable.objects.create(
        classroom=cls_7a,
        subject=sub_math,
        teacher=teacher,
        day_of_week=today_dow,
        period_number=3,
        start_time=st_time_str,
        end_time=end_time_str
    )



    # 5. Test GET /attendance/ -> Verify Timetable Auto-Detection
    res_get = client.get('/attendance/')
    assert res_get.status_code == 200
    html = res_get.content.decode('utf-8')

    assert 'ចាក់សោតាមកាលវិភាគ' in html or 'Timetable Auto-Locked' in html
    assert cls_7a.name in html
    assert 'ម៉ោងទី 3' in html or 'ម៉ោងទី ៣' in html
    print(f"✅ PASSED: Timetable Auto-Detection successfully locked to {cls_7a.name}, Period 3 ({sub_math.name_kh}) for {teacher.khmer_name}.")

    # 6. Test POST Attendance with Absence-First logic
    # Clean previous attendance records for this date/session
    test_date_str = datetime.now().strftime('%Y-%m-%d')
    StudentAttendance.objects.filter(classroom=cls_7a, date=test_date_str, session='MORNING').delete()

    # Submit: ONLY st1 (ABSENT) and st2 (PERMISSION with note) are ticked. st3 and remaining 33 students are UNTICKED (Present).
    post_data = {
        'classroom': str(cls_7a.id),
        'date': test_date_str,
        'session': 'MORNING',
        'period': '3',
        'subject': str(sub_math.id),
        f'is_absent_{st1.id}': '1',
        f'status_{st1.id}': 'ABSENT',
        f'notes_{st1.id}': 'គ្មានដំណឹង',
        f'is_absent_{st2.id}': '1',
        f'status_{st2.id}': 'PERMISSION',
        f'notes_{st2.id}': 'ឈឺផ្តាសាយ សុំច្បាប់ ១ ថ្ងៃ',
        # Notice st3, st4, etc. do NOT have is_absent submitted!
    }

    res_post = client.post('/attendance/', data=post_data, follow=True)
    assert res_post.status_code == 200

    # 7. Check Database: ONLY 2 rows must exist in StudentAttendance!
    saved_records = StudentAttendance.objects.filter(classroom=cls_7a, date=test_date_str, session='MORNING')
    print(f"✅ PASSED: Total classroom students = {total_students_count}. Total rows saved in DB = {saved_records.count()} (Lean & Fast!).")
    assert saved_records.count() == 2, f"Expected 2 records in DB, got {saved_records.count()}"

    rec_st1 = saved_records.filter(student=st1).first()
    assert rec_st1 is not None and rec_st1.status == 'ABSENT' and rec_st1.period_number == 3
    rec_st2 = saved_records.filter(student=st2).first()
    assert rec_st2 is not None and rec_st2.status == 'PERMISSION' and 'ឈឺផ្តាសាយ' in rec_st2.notes

    print(f"✅ PASSED: Student 1 ({st1.khmer_name}) saved as ABSENT (Unexcused).")
    print(f"✅ PASSED: Student 2 ({st2.khmer_name}) saved as PERMISSION (Excused with note: '{rec_st2.notes}').")

    # 8. Test Dynamic Un-ticking (Correction)
    # Teacher realizes Student 1 actually came late / was present, so they un-tick Student 1 and save again.
    post_data_update = {
        'classroom': str(cls_7a.id),
        'date': test_date_str,
        'session': 'MORNING',
        'period': '3',
        'subject': str(sub_math.id),
        # st1 is UNCHECKED!
        f'is_absent_{st2.id}': '1',
        f'status_{st2.id}': 'PERMISSION',
        f'notes_{st2.id}': 'សុំច្បាប់',
    }
    res_post_update = client.post('/attendance/', data=post_data_update, follow=True)
    assert res_post_update.status_code == 200

    updated_records = StudentAttendance.objects.filter(classroom=cls_7a, date=test_date_str, session='MORNING')
    assert updated_records.count() == 1, f"Expected 1 record, got {updated_records.count()}"
    assert updated_records.filter(student=st1).count() == 0, "Expected st1 record to be deleted from absent list!"
    print(f"✅ PASSED: Unticking Student 1 deleted their absence record from DB (Now exactly 1 absent student in DB).")

    # 9. Test Attendance Report
    res_report = client.get(f'/attendance/report/?classroom={cls_7a.id}')
    assert res_report.status_code == 200
    print("✅ PASSED: Monthly Attendance Report loaded successfully.")


    # Cleanup test slot and records
    Timetable.objects.filter(id=tt_slot.id).delete()
    StudentAttendance.objects.filter(classroom=cls_7a, date=test_date_str, session='MORNING').delete()

    print("==========================================================================")
    print("🎉 ALL SMART TIMETABLE ATTENDANCE TESTS PASSED 100%!")
    print("==========================================================================")

if __name__ == '__main__':
    test_smart_attendance()
