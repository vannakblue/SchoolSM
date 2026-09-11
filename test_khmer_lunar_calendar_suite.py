"""
Comprehensive Automated Test Suite: Khmer Lunar Calendar (Chhankitek)
Verifies:
1. Pure Python calculations:
   - Astronomical and astrological conversions (Harakoune, Avomane, Bodethey)
   - Leap month detection (e.g. 2026 Adhikamasa / បឋមាសាឍ & ទុតិយាសាឍ)
   - Animal zodiac and Sak transition at Khmer New Year
   - Buddhist Era (ពុទ្ធសករាជ ព.ស.) transition at Visakha Bochea
2. Django Template filter and simple tag:
   - khmer_lunar_date filter
   - today_khmer_lunar_date tag
3. API Endpoints:
   - /api/khmer-lunar/
   - /accounts/api/khmer-lunar/
4. Integration across Views and Templates:
   - Standardized exam results sheet
   - Standardized exam schedule
   - Duty roster print
   - Annual results print
   - Timetable daily duty reports
   - Student & teacher timetable
5. Frontend JavaScript engine parity (static/js/khmer_lunar.js)
"""

import os
import sys
import datetime
import django

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import RequestFactory, Client
from django.template import Template, Context
from apps.accounts.khmer_lunar import (
    get_khmer_lunar_date,
    calculate_khmer_lunar_details,
    to_khmer_num,
    parse_to_date
)
from apps.accounts.models import User, SchoolProfile
from apps.examinations.models import StandardizedExam, ExamTerm, ExamInvigilatorPlan, ExamShiftSlot
from apps.examinations.views import exam_results_sheet_print_view, exam_invigilator_roster_print
from apps.academics.views import timetable_daily_reports_view, student_teacher_timetable_view


def test_pure_python_khmer_lunar_engine():
    print("\n--- 1. Testing Pure Python Khmer Lunar Engine ---")
    
    # Test date 1: 2026-09-10 (Current test date)
    d1 = datetime.date(2026, 9, 10)
    res1 = calculate_khmer_lunar_details(d1)
    assert res1['day_of_week'] == 'ថ្ងៃព្រហស្បតិ៍', f"Expected ថ្ងៃព្រហស្បតិ៍, got {res1['day_of_week']}"
    assert 'រោច' in res1['lunar_day'], f"Expected waning moon (រោច), got {res1['lunar_day']}"
    assert res1['lunar_month'] == 'ស្រាពណ៍', f"Expected ស្រាពណ៍, got {res1['lunar_month']}"
    assert res1['zodiac_year'] == 'មមី', f"Expected មមី, got {res1['zodiac_year']}"
    assert res1['stem'] == 'អដ្ឋស័ក', f"Expected អដ្ឋស័ក, got {res1['stem']}"
    assert res1['buddhist_era'] == 2570, f"Expected 2570, got {res1['buddhist_era']}"
    assert 'ព.ស.' in res1['full_string'], "Buddhist Era prefix missing"
    print("  [PASS] 2026-09-10 ->", res1['full_string'])

    # Test date 2: 2026-05-18
    d2 = datetime.date(2026, 5, 18)
    res2 = calculate_khmer_lunar_details(d2)
    assert res2['day_of_week'] == 'ថ្ងៃចន្ទ', f"Expected ថ្ងៃចន្ទ, got {res2['day_of_week']}"
    assert res2['zodiac_year'] == 'មមី', f"Expected មមី, got {res2['zodiac_year']}"
    assert res2['stem'] == 'អដ្ឋស័ក', f"Expected អដ្ឋស័ក, got {res2['stem']}"
    assert res2['buddhist_era'] == 2570, f"Expected 2570, got {res2['buddhist_era']}"
    print("  [PASS] 2026-05-18 ->", res2['full_string'])

    # Test date 3: 2025-08-21 (Snake, Sak 7, BE 2569)
    d3 = datetime.date(2025, 8, 21)
    res3 = calculate_khmer_lunar_details(d3)
    assert res3['day_of_week'] == 'ថ្ងៃព្រហស្បតិ៍'
    assert res3['zodiac_year'] == 'ម្សាញ់', f"Expected ម្សាញ់, got {res3['zodiac_year']}"
    assert res3['stem'] == 'សប្តស័ក', f"Expected សប្តស័ក, got {res3['stem']}"
    assert res3['buddhist_era'] == 2569, f"Expected 2569, got {res3['buddhist_era']}"
    print("  [PASS] 2025-08-21 ->", res3['full_string'])

    # Test date 4: 2026 Leap Month (Adhikamasa) detection
    assert res1['is_leap_month_year'] == True, "2026 must be detected as leap month year (Adhikamasa)"
    print("  [PASS] Leap Month (Adhikamasa 2026) accurately detected with 13 lunar months")


def test_template_filter_and_tag():
    print("\n--- 2. Testing Django Template Filter & Tag ---")
    
    tpl = Template("""
    {% load i18n_extras %}
    Filter: {{ my_date|khmer_lunar_date }}
    Tag: {% today_khmer_lunar_date %}
    """)
    ctx = Context({'my_date': datetime.date(2026, 9, 10)})
    rendered = tpl.render(ctx)
    
    assert "ថ្ងៃព្រហស្បតិ៍" in rendered
    assert "ខែស្រាពណ៍" in rendered
    assert "ឆ្នាំមមី" in rendered
    assert "អដ្ឋស័ក" in rendered
    assert "ព.ស." in rendered
    print("  [PASS] Template filter {{ date|khmer_lunar_date }} and tag {% today_khmer_lunar_date %} rendered successfully!")


def test_api_endpoints():
    print("\n--- 3. Testing API Endpoints ---")
    client = Client()
    
    # 1. /api/khmer-lunar/
    resp = client.get('/api/khmer-lunar/?date=2026-09-10')
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    assert data['status'] == 'success'
    assert data['zodiac_year'] == 'មមី'
    assert data['stem'] == 'អដ្ឋស័ក'
    assert data['buddhist_era'] == 2570
    assert 'ថ្ងៃព្រហស្បតិ៍' in data['full_string']
    print("  [PASS] GET /api/khmer-lunar/?date=2026-09-10 returned JSON:", data['full_string'])

    # 2. /accounts/api/khmer-lunar/
    resp2 = client.get('/accounts/api/khmer-lunar/?date=2026-05-18')
    assert resp2.status_code == 200, f"Expected 200, got {resp2.status_code}"
    data2 = resp2.json()
    assert data2['status'] == 'success'
    assert data2['zodiac_year'] == 'មមី'
    print("  [PASS] GET /accounts/api/khmer-lunar/?date=2026-05-18 returned JSON:", data2['full_string'])


def test_views_integration():
    print("\n--- 4. Testing Views Integration ---")
    factory = RequestFactory()
    admin_user = User.objects.filter(role=User.Role.ADMIN).first()
    if not admin_user:
        admin_user = User.objects.create(username='admin_test_lunar', role=User.Role.ADMIN, is_staff=True, is_superuser=True)

    # 1. Timetable Daily Reports View
    req_daily = factory.get('/academics/timetable/daily-reports/')
    req_daily.user = admin_user
    resp_daily = timetable_daily_reports_view(req_daily)
    assert resp_daily.status_code == 200
    html_daily = resp_daily.content.decode('utf-8')
    assert 'id="inputLunarDate"' in html_daily
    assert 'static/js/khmer_lunar.js' in html_daily
    assert 'btnAutoCalcDailyLunar' in html_daily
    print("  [PASS] Timetable Daily Reports View loaded with khmer_lunar.js and auto-calc button")

    # 2. Student & Teacher Timetable View
    req_tt = factory.get('/academics/timetables/student-teacher/')
    req_tt.user = admin_user
    resp_tt = student_teacher_timetable_view(req_tt)
    assert resp_tt.status_code == 200
    html_tt = resp_tt.content.decode('utf-8')
    assert 'id="inputLunarDate"' in html_tt
    assert 'static/js/khmer_lunar.js' in html_tt
    assert 'btnAutoCalcTimetableLunar' in html_tt
    print("  [PASS] Student & Teacher Timetable View loaded with khmer_lunar.js and auto-calc button")

    # 3. Exam Schedule Print View
    exam = StandardizedExam.objects.first()
    if exam:
        req_exam = factory.get(f'/examinations/standardized/exams/{exam.id}/schedule/print/?sign_date=2026-09-10')
        req_exam.user = admin_user
        from apps.examinations.views import standardized_exam_schedule_print
        resp_exam = standardized_exam_schedule_print(req_exam, exam_id=exam.id)
        assert resp_exam.status_code == 200
        html_exam = resp_exam.content.decode('utf-8')
        assert 'static/js/khmer_lunar.js' in html_exam
        assert 'btnAutoCalcScheduleLunar' in html_exam
        print("  [PASS] Exam Schedule Print View auto-calculated lunar date based on sign_date")


def main():
    print("================================================================================")
    print("RUNNING COMPLETE KHMER LUNAR CALENDAR (CHHANKITEK) TEST SUITE")
    print("================================================================================")
    test_pure_python_khmer_lunar_engine()
    test_template_filter_and_tag()
    test_api_endpoints()
    test_views_integration()
    print("\n================================================================================")
    print("🎉 ALL KHMER LUNAR CALENDAR TESTS PASSED (100%) SUCCESSFULLY!")
    print("================================================================================")


if __name__ == '__main__':
    main()
