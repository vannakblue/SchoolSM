import os
import sys
import django
from datetime import datetime, date, time
from decimal import Decimal

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.academics.models import AcademicYear, Classroom, Subject, Timetable
from apps.teachers.models import Teacher
from apps.attendance.models import StudentAttendance

def test_teacher_no_schedule_modal_scenarios():
    print("==========================================================================")
    print("TEST: TEACHER NO-SCHEDULE MODAL NOTIFICATIONS (1 ម៉ោង, 1 ពេល, 1 ថ្ងៃ)")
    print("==========================================================================")

    # 1. Setup Academic Year & Classroom
    ay, _ = AcademicYear.objects.get_or_create(
        name="2025-2026",
        defaults={'start_date': '2025-09-01', 'end_date': '2026-07-15', 'is_current': True}
    )
    AcademicYear.objects.filter(id=ay.id).update(is_current=True)
    AcademicYear.objects.exclude(id=ay.id).update(is_current=False)

    cls_11a, _ = Classroom.objects.get_or_create(
        code='11A-MODAL-TEST',
        defaults={'name': 'ថ្នាក់ទី ១១A', 'grade_level': 11, 'academic_year': ay}
    )
    cls_11a.academic_year = ay
    cls_11a.save()

    sub_math, _ = Subject.objects.get_or_create(
        code='M-MODAL',
        defaults={'name_kh': 'គណិតវិទ្យា', 'name_en': 'Math', 'category': 'SCIENCE'}
    )


    # Create Teacher 1 (Has class only on Monday morning Period 1)
    u_teacher1, _ = User.objects.get_or_create(
        username='teacher_modal_test1',
        defaults={'role': User.Role.TEACHER, 'khmer_name': 'លោកគ្រូ សុខ', 'latin_name': 'SOK'}
    )
    t1, _ = Teacher.objects.get_or_create(
        teacher_id='T-MODAL-01',
        defaults={'user': u_teacher1, 'khmer_name': 'លោកគ្រូ សុខ', 'latin_name': 'SOK', 'status': 'ACTIVE', 'phone': '012111111'}
    )
    if t1.user != u_teacher1:
        t1.user = u_teacher1
        t1.save()

    # Create Teacher 2 (Has NO classes at all on Monday)
    u_teacher2, _ = User.objects.get_or_create(
        username='teacher_modal_test2',
        defaults={'role': User.Role.TEACHER, 'khmer_name': 'អ្នកគ្រូ ចិន្តា', 'latin_name': 'CHINDA'}
    )
    t2, _ = Teacher.objects.get_or_create(
        teacher_id='T-MODAL-02',
        defaults={'user': u_teacher2, 'khmer_name': 'អ្នកគ្រូ ចិន្តា', 'latin_name': 'CHINDA', 'status': 'ACTIVE', 'phone': '012222222'}
    )
    if t2.user != u_teacher2:
        t2.user = u_teacher2
        t2.save()

    # Fixed Monday (e.g. 2026-08-17, isoweekday=1)
    test_monday = date(2026, 8, 17)
    assert test_monday.isoweekday() == 1

    # Cleanup
    Timetable.objects.filter(classroom=cls_11a).delete()

    # Timetable for T1 on Monday: Period 1 (07:00-08:00) only
    Timetable.objects.create(
        classroom=cls_11a,
        subject=sub_math,
        teacher=t1,
        day_of_week=1,
        period_number=1,
        start_time=time(7, 0),
        end_time=time(8, 0)
    )

    client = Client()

    # -------------------------------------------------------------------------
    # SCENARIO 1: Teacher 2 has NO classes for the ENTIRE DAY (1 ថ្ងៃ)
    # -------------------------------------------------------------------------
    print("\n--- SCENARIO 1: Teacher has NO classes the entire day (1 ថ្ងៃ) ---")
    client.force_login(u_teacher2)
    res_t2 = client.get(f'/attendance/?date={test_monday.strftime("%Y-%m-%d")}')
    assert res_t2.status_code == 200
    html_t2 = res_t2.content.decode('utf-8')
    assert 'teacherScheduleModal' in html_t2
    assert 'ពុំមានម៉ោងបង្រៀនក្នុងថ្ងៃនេះទេ' in html_t2
    assert 'គ្មានកាលវិភាគពេញមួយថ្ងៃ' in html_t2
    print("✅ Scenario 1 Passed: Modal correctly alerted 'គ្មានកាលវិភាគពេញមួយថ្ងៃ'.")

    # -------------------------------------------------------------------------
    # SCENARIO 2: Teacher 1 visits during AFTERNOON session (No classes this session - 1 ពេល)
    # -------------------------------------------------------------------------
    print("\n--- SCENARIO 2: Teacher has NO classes in this session (1 ពេល) ---")
    client.force_login(u_teacher1)
    res_t1_session = client.get(f'/attendance/?date={test_monday.strftime("%Y-%m-%d")}&session=AFTERNOON&period=5')
    assert res_t1_session.status_code == 200
    html_t1_session = res_t1_session.content.decode('utf-8')
    print("Has teacherScheduleModal:", 'teacherScheduleModal' in html_t1_session)
    if 'teacherScheduleModal' in html_t1_session:
        idx = html_t1_session.find('teacherScheduleModal')
        print("Modal snippet:", html_t1_session[idx:idx+500])
    assert 'teacherScheduleModal' in html_t1_session
    print("✅ Scenario 2 Passed.")



    # -------------------------------------------------------------------------
    # SCENARIO 3: Teacher 1 visits in Morning but at Period 3 (No class this period - 1 ម៉ោង)
    # -------------------------------------------------------------------------
    print("\n--- SCENARIO 3: Teacher has NO class at this specific period (1 ម៉ោង) ---")
    res_t1_period = client.get(f'/attendance/?date={test_monday.strftime("%Y-%m-%d")}&session=MORNING&period=3')
    assert res_t1_period.status_code == 200
    html_t1_period = res_t1_period.content.decode('utf-8')
    print("Scenario 3 Modal present:", 'teacherScheduleModal' in html_t1_period)
    if 'teacherScheduleModal' in html_t1_period:
        idx = html_t1_period.find('teacherScheduleModal')
        print("Scenario 3 Modal snippet:", html_t1_period[idx:idx+600])
    assert 'teacherScheduleModal' in html_t1_period
    assert 'ម៉ោងទី 3' in html_t1_period
    print("✅ Scenario 3 Passed: Modal correctly alerted for period 3.")


    print("\n--- SCENARIO 4: Teacher has an active class slot (Period 1) ---")
    res_t1_active = client.get(f'/attendance/?classroom={cls_11a.id}&period=1&date={test_monday.strftime("%Y-%m-%d")}')
    assert res_t1_active.status_code == 200
    html_t1_active = res_t1_active.content.decode('utf-8')
    print("Scenario 4 HTML snippet:", html_t1_active[:600])
    assert 'timetable-locked-card' in html_t1_active
    assert 'teacherScheduleModal' not in html_t1_active
    print("✅ Scenario 4 Passed: Direct access to active locked slot without modal warning.")




    # Cleanup
    Timetable.objects.filter(classroom=cls_11a).delete()
    cls_11a.delete()
    sub_math.delete()
    t1.delete()
    t2.delete()
    u_teacher1.delete()
    u_teacher2.delete()

    print("\n==========================================================================")
    print("🎉 ALL TEACHER NO-SCHEDULE MODAL TESTS PASSED 100%!")
    print("==========================================================================")

if __name__ == '__main__':
    test_teacher_no_schedule_modal_scenarios()
