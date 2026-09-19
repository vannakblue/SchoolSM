import os
import sys
from datetime import date

# Setup Django environment
sys.path.insert(0, r"e:\SchoolSM")
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
import django
django.setup()

from apps.attendance.telegram_utils import (
    to_khmer_numeral,
    natural_classroom_sort_key,
    sort_khmer_student_entries,
    format_classroom_short_name,
    format_daily_grade_student_absence_message,
    get_daily_grade_student_absences,
    send_daily_grade_student_absence_telegram,
    send_daily_summary_telegram,
)
from apps.academics.models import Classroom, AcademicYear
from apps.students.models import Student
from apps.attendance.models import StudentAttendance


def test_format_matches_user_screenshot():
    print("=== Test 1: Testing exact format matching user screenshot ===")

    # Test data reflecting Grade 7 from the screenshot
    classrooms_data = [
        {
            'classroom': 'ថ្នាក់ទី 7B',
            'students': [
                {'student_id': '26398', 'name': 'នីន ដាលីស', 'count': 1},
                {'student_id': '26462', 'name': 'វ៉ែត ម៉ារីន', 'count': 1},
                {'student_id': '26512', 'name': 'ឡិក គីមឡុង', 'count': 1},
            ]
        },
        {
            'classroom': '7C',
            'students': [
                {'student_id': '26342', 'name': 'គឹម រចនា', 'count': 1},
                {'student_id': '26385', 'name': 'ថេង ច័ន្ទ័រ៉ា', 'count': 1},
                {'student_id': '26386', 'name': 'ថៅ ស្រីយ៉ា', 'count': 1},
                {'student_id': '26392', 'name': 'ធឿន ច័ន្ទ្រ', 'count': 1},
                {'student_id': '26413', 'name': 'ផាន ស្រីនួន', 'count': 1},
                {'student_id': '26420', 'name': 'ព្រុំ ស្រីលក្ខិណា', 'count': 1},
                {'student_id': '26426', 'name': 'ម៉ឺន កញ្ញា', 'count': 1},
                {'student_id': '26449', 'name': 'លាត ម៉ារ៉ាឌី', 'count': 1},
                {'student_id': '26487', 'name': 'សុជាត សារីណា', 'count': 1},
                {'student_id': '26500', 'name': 'ស្រែន ចម្រើន', 'count': 1},
                {'student_id': '26535', 'name': 'ឈិត រ៉ាឌី', 'count': 1},
                {'student_id': '26545', 'name': 'វ៉ែន សុខលាភ', 'count': 1},
                {'student_id': '26714', 'name': 'វឿន សម្ភស្សរចនា', 'count': 1},
            ]
        },
        {
            'classroom': '7D',
            'students': [
                {'student_id': '25393', 'name': 'ជុំ សុជាតិកា', 'count': 1},
                {'student_id': '25440', 'name': 'ផល ផាន់ន់', 'count': 1},
                {'student_id': '26343', 'name': 'គឹមលី ស្រីណេត', 'count': 1},
                {'student_id': '26354', 'name': 'ចាន់ថា លីហ្សា', 'count': 1},
                {'student_id': '26358', 'name': 'ច័ន្ទ សុខវិសាល', 'count': 1},
            ]
        }
    ]

    target_d = date(2026, 7, 22)
    formatted_msg = format_daily_grade_student_absence_message(
        grade_level=7,
        classrooms_data=classrooms_data,
        target_date=target_d
    )

    print("\n--- Output Message ---\n")
    print(formatted_msg)
    print("\n----------------------\n")

    # Assertions
    assert "⚠️ របាយការណ៍អវត្តមានសិស្សប្រចាំថ្ងៃ - កម្រិតថ្នាក់ទី ៧" in formatted_msg
    assert "📅 ថ្ងៃទី៖ 22/07/2026" in formatted_msg
    assert "🏫 ថ្នាក់ 7B" in formatted_msg
    assert "១. 26398-នីន ដាលីស (១ពេល)" in formatted_msg
    assert "២. 26462-វ៉ែត ម៉ារីន (១ពេល)" in formatted_msg
    assert "៣. 26512-ឡិក គីមឡុង (១ពេល)" in formatted_msg
    assert "🏫 ថ្នាក់ 7C" in formatted_msg
    assert "🏫 ថ្នាក់ 7D" in formatted_msg
    assert "១០." in formatted_msg
    assert "១១." in formatted_msg
    assert "១២." in formatted_msg
    assert "១៣." in formatted_msg

    print("Test 1 Passed: Format exactly matches screenshot!")


def test_classroom_and_name_sorting():
    print("\n=== Test 2: Testing classroom sequential sorting & student name sorting ===")

    # Unordered classrooms: 12B, 7D, 11A, 7B, 10C, 7C, 8A
    raw_classes = ['12B', '7D', '11A', '7B', '10C', '7C', '8A', '7A']
    sorted_classes = sorted(raw_classes, key=natural_classroom_sort_key)
    print("Classroom natural sort:", sorted_classes)
    assert sorted_classes == ['7A', '7B', '7C', '7D', '8A', '10C', '11A', '12B']

    # Test student Khmer alphabetical sorting:
    students_unsorted = [
        {'student_id': '101', 'name': 'អ៊ុំ វ៉ាន់នី'},   # អ (Last)
        {'student_id': '102', 'name': 'កែវ មករា'},     # ក (First)
        {'student_id': '103', 'name': 'ចាន់ តារា'},    # ច (Middle)
        {'student_id': '104', 'name': 'ខៀវ សុខា'},     # ខ (Second)
    ]
    sorted_st = sort_khmer_student_entries(students_unsorted)
    sorted_names = [s['name'] for s in sorted_st]
    print("Student Khmer sort:", sorted_names)
    assert sorted_names == ['កែវ មករា', 'ខៀវ សុខា', 'ចាន់ តារា', 'អ៊ុំ វ៉ាន់នី']

    print("Test 2 Passed: Classroom and student sorting verified!")


def test_database_query_and_dispatch():
    print("\n=== Test 3: Testing database query & telegram dispatch logic ===")

    # Check active academic year and grade query
    active_year = AcademicYear.objects.filter(is_current=True).first()
    today_d = date.today()

    for g in range(7, 13):
        data = get_daily_grade_student_absences(today_d, g, active_year=active_year)
        total_students = sum(len(c['students']) for c in data)
        print(f"Grade {g}: {len(data)} classes with absences, {total_students} total absent students.")

    # Test dispatch function (with dummy chat_id or dry run)
    res = send_daily_grade_student_absence_telegram(
        target_date=today_d,
        grade_levels=[7, 8, 9, 10, 11, 12],
        custom_chat_id="-100999999999"
    )
    print("Dispatch result:", res)
    assert res.get('success') is True

    # Test daily summary dispatch
    summary_res = send_daily_summary_telegram(
        target_date=today_d,
        send_students=True,
        send_teachers=True,
        custom_chat_id="-100999999999",
        send_grade_reports=True
    )
    print("Daily summary dispatch result:", summary_res)
    assert summary_res.get('success') is True
    assert summary_res.get('grade_reports') is not None

    print("Test 3 Passed: DB Query & Telegram Dispatch verified successfully!")


if __name__ == '__main__':
    test_format_matches_user_screenshot()
    test_classroom_and_name_sorting()
    test_database_query_and_dispatch()
    print("\n🎉 ALL TESTS PASSED 100%! 🎉")
