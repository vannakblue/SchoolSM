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
    get_teacher_display_name,
    sort_khmer_teacher_entries,
    format_daily_teacher_absence_report_message,
    get_daily_teacher_absence_data,
    send_daily_teacher_absence_telegram,
    send_daily_summary_telegram,
)
from apps.teachers.models import Teacher


def test_format_matches_user_screenshot():
    print("=== Test 1: Testing exact format matching user screenshot ===")

    # 26 teachers from the user's screenshot
    unrecorded_teachers = [
        'កាន ដាវី', 'ក្រឹង ចន្ធា', 'ឃឹម ស្រស់', 'ចាន់ ធី', 'ចេង បុណ្ណាវុធ',
        'ជៀស ឌីនីន', 'ជុំ សុជន', 'ឈឿន លីឆាយ', 'ដួង ពិសាល', 'ណុំ ស្រីណែត',
        'ទូច សុខម៉េត', 'ថេង លាងឃន', 'ពិន ពិដោរ', 'យ៉ន ណារ៉ា', 'លី ហូត',
        'វិន ភារុន', 'សា ប៊ុនថន', 'សុខា សាមឌី', 'សុន ឌីម៉ង់', 'សឿន សម្បត្តិ',
        'សំ ពិសី', 'ឡេង សេស', 'អ៊ិន ឆាយ', 'អ៊ឹម សំអុល', 'អ៊ុយ វាសនា', 'អេង រតនា'
    ]

    on_leave_teachers = [
        'សុទ្ធ ចរិយា'
    ]

    target_d = date(2026, 7, 22)
    formatted_msg = format_daily_teacher_absence_report_message(
        unrecorded_teachers=unrecorded_teachers,
        on_leave_teachers=on_leave_teachers,
        target_date=target_d
    )

    print("\n--- Output Message ---\n")
    print(formatted_msg)
    print("\n----------------------\n")

    # Assertions matching user screenshot
    assert "⚠️ របាយការណ៍អវត្តមានគ្រូប្រចាំថ្ងៃ" in formatted_msg
    assert "📅 ថ្ងៃទី៖ 22/07/2026" in formatted_msg
    assert "❌ គ្រូមិនបានបញ្ចូលអវត្តមាន៖" in formatted_msg
    assert "ទី១៖ កាន ដាវី" in formatted_msg
    assert "ទី២៖ ក្រឹង ចន្ធា" in formatted_msg
    assert "ទី៣៖ ឃឹម ស្រស់" in formatted_msg
    assert "ទី៤៖ ចាន់ ធី" in formatted_msg
    assert "ទី៥៖ ចេង បុណ្ណាវុធ" in formatted_msg
    assert "ទី២៦៖" in formatted_msg
    assert "🟡 គ្រូមានច្បាប់ឈប់សម្រាក៖" in formatted_msg
    assert "ទី១៖ សុទ្ធ ចរិយា" in formatted_msg

    print("Test 1 Passed: Format exactly matches user screenshot!")


def test_alphabetical_sorting():
    print("\n=== Test 2: Testing Khmer alphabetical sorting from ក to អ ===")

    # Test unsorted teachers
    unsorted_list = [
        'អេង រតនា',
        'កាន ដាវី',
        'សុទ្ធ ចរិយា',
        'ចេង បុណ្ណាវុធ',
        'ខៀវ សុខា',
        'ឡេង សេស',
        'ដួង ពិសាល',
    ]
    sorted_list = sort_khmer_teacher_entries(unsorted_list)
    print("Sorted teachers:", sorted_list)

    # ក must be first, អ must be last
    assert sorted_list[0] == 'កាន ដាវី'
    assert sorted_list[-1] == 'អេង រតនា'
    # Check relative positions: ក < ខ < ច < ដ < ស < ឡ < អ
    k_idx = sorted_list.index('កាន ដាវី')
    kh_idx = sorted_list.index('ខៀវ សុខា')
    ch_idx = sorted_list.index('ចេង បុណ្ណាវុធ')
    d_idx = sorted_list.index('ដួង ពិសាល')
    s_idx = sorted_list.index('សុទ្ធ ចរិយា')
    l_idx = sorted_list.index('ឡេង សេស')
    a_idx = sorted_list.index('អេង រតនា')

    assert k_idx < kh_idx < ch_idx < d_idx < s_idx < l_idx < a_idx
    print("Test 2 Passed: Khmer alphabetical sorting verified!")


def test_database_and_dispatch():
    print("\n=== Test 3: Testing database evaluation & dispatch ===")

    today_d = date.today()
    data = get_daily_teacher_absence_data(target_date=today_d)
    print(f"Evaluated today: {data['total_unrecorded']} unrecorded, {data['total_on_leave']} on leave.")

    # Test standalone dispatch
    res = send_daily_teacher_absence_telegram(
        target_date=today_d,
        custom_chat_id="-100999999999"
    )
    print("Dispatch result:", res)
    assert res.get('success') is True

    # Test daily summary dispatch which includes teacher reports
    summary_res = send_daily_summary_telegram(
        target_date=today_d,
        send_students=True,
        send_teachers=True,
        custom_chat_id="-100999999999"
    )
    print("Summary dispatch result:", summary_res)
    assert summary_res.get('success') is True
    assert summary_res.get('teacher_reports') is not None
    assert summary_res['teacher_reports'].get('success') is True

    print("Test 3 Passed: DB evaluation & dispatch verified!")


if __name__ == '__main__':
    test_format_matches_user_screenshot()
    test_alphabetical_sorting()
    test_database_and_dispatch()
    print("\n🎉 ALL TESTS PASSED 100%! 🎉")
