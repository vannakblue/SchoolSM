"""
Comprehensive Verification Test for Khmer Lunar Date Converter (បម្លែងថ្ងៃខែចន្ទគតិ)
"""

import os
import sys
import json
import django

# Reconfigure stdout for UTF-8 in Windows console
if sys.stdout and sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import RequestFactory
from django.urls import reverse, resolve
from apps.accounts.models import User
from apps.accounts.menu_registry import get_menu_catalog, sync_system_menus_to_db, MenuItem
from apps.accounts.khmer_lunar import calculate_khmer_lunar_details, get_khmer_lunar_date
from apps.tools.views import khmer_lunar_converter_view, api_solar_to_lunar, tools_hub
from apps.tools.ai_service import ToolAiService


def test_khmer_lunar_feature():
    print("==================================================================")
    print("TESTING: KHMER LUNAR CALENDAR CONVERTER (បម្លែងថ្ងៃខែចន្ទគតិ)")
    print("==================================================================")

    rf = RequestFactory()
    admin_user = User.objects.filter(role=User.Role.ADMIN).first() or User.objects.filter(is_superuser=True).first()

    # 1. Test URL resolution
    print("\n[TEST 1] Testing URL Resolution...")
    url_tool = reverse('tool_khmer_lunar_converter')
    url_api = reverse('api_solar_to_lunar')
    assert url_tool == '/tools/khmer-lunar-converter/', f"Unexpected URL: {url_tool}"
    assert url_api == '/tools/api/solar-to-lunar/', f"Unexpected API URL: {url_api}"
    print(f"  -> PASS: URLs verified: {url_tool} and {url_api}")

    # 2. Test Calculation Engine
    print("\n[TEST 2] Testing Khmer Lunar Calculation Accuracy...")
    test_cases = [
        {
            'date': '2024-10-02', # Pchum Ben 2024 (15រោច ខែភទ្របទ ឆ្នាំរោង ឆស័ក ព.ស. ២៥៦៨)
            'expected_lunar_day': '១៥រោច',
            'expected_month': 'ភទ្របទ',
            'expected_zodiac': 'រោង',
            'expected_stem': 'ឆស័ក',
            'expected_holy': True,
        },
        {
            'date': '2024-04-14', # Khmer New Year 2024
            'expected_zodiac': 'រោង',
            'expected_stem': 'ឆស័ក',
        },
        {
            'date': '2026-09-11', # Today's test date
            'expected_weekday': 'ថ្ងៃសុក្រ',
            'expected_holy': True, # 14រោច in 29-day month (សីលដាច់ខែ)
        }
    ]

    for tc in test_cases:
        res = calculate_khmer_lunar_details(tc['date'])
        print(f"  Checking {tc['date']}: {res['full_string']}")
        if 'expected_lunar_day' in tc:
            assert res['lunar_day'] == tc['expected_lunar_day'], f"Expected {tc['expected_lunar_day']}, got {res['lunar_day']}"
        if 'expected_month' in tc:
            assert res['lunar_month'] == tc['expected_month'], f"Expected {tc['expected_month']}, got {res['lunar_month']}"
        if 'expected_zodiac' in tc:
            assert res['zodiac_year'] == tc['expected_zodiac'], f"Expected {tc['expected_zodiac']}, got {res['zodiac_year']}"
        if 'expected_stem' in tc:
            assert res['stem'] == tc['expected_stem'], f"Expected {tc['expected_stem']}, got {res['stem']}"
        if 'expected_holy' in tc:
            assert res['is_holy_day'] == tc['expected_holy'], f"Expected holy={tc['expected_holy']}, got {res['is_holy_day']}"

    print("  -> PASS: All astrological & lunar calculations verified with 100% accuracy!")

    # 3. Test View Rendering
    print("\n[TEST 3] Testing khmer_lunar_converter_view...")
    req = rf.get('/tools/khmer-lunar-converter/')
    req.user = admin_user
    resp = khmer_lunar_converter_view(req)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    body = resp.content.decode('utf-8')
    assert 'បម្លែងថ្ងៃខែសុរិយគតិ ទៅជាចន្ទគតិ' in body, "Page title missing in rendered template"
    assert 'solarDateInput' in body, "solarDateInput missing"
    assert 'lunarFullDisplay' in body, "lunarFullDisplay missing"
    assert 'calendarDaysGrid' in body, "calendarDaysGrid missing"
    print("  -> PASS: khmer_lunar_converter_view rendered with full UI elements (HTTP 200)!")

    # 4. Test API Endpoint
    print("\n[TEST 4] Testing api_solar_to_lunar endpoint...")
    req_api = rf.get('/tools/api/solar-to-lunar/?date=2024-10-02')
    req_api.user = admin_user
    resp_api = api_solar_to_lunar(req_api)
    assert resp_api.status_code == 200, f"Expected 200, got {resp_api.status_code}"
    api_data = json.loads(resp_api.content.decode('utf-8'))
    assert api_data.get('success') is True, "API returned success=False"
    assert api_data['data']['lunar_day'] == '១៥រោច', f"Expected ១៥រោច, got {api_data['data']['lunar_day']}"
    assert api_data['data']['lunar_month'] == 'ភទ្របទ', f"Expected ភទ្របទ, got {api_data['data']['lunar_month']}"
    print(f"  -> PASS: api_solar_to_lunar returned JSON data: {api_data['data']['full_string']}")

    # 5. Test Menu Registry & Database
    print("\n[TEST 5] Testing Menu Registry and DB...")
    sync_system_menus_to_db()
    menu_item = MenuItem.objects.filter(code='tool_khmer_lunar_converter').first()
    assert menu_item is not None, "tool_khmer_lunar_converter not found in database MenuItem"
    assert menu_item.is_active is True, "tool_khmer_lunar_converter is not active"
    assert menu_item.url_name == 'tool_khmer_lunar_converter', f"Wrong url_name: {menu_item.url_name}"
    print(f"  -> PASS: Database MenuItem verified: id={menu_item.id}, name_kh={menu_item.name_kh}, url={menu_item.url_name}")

    # 6. Test Tools Hub Integration
    print("\n[TEST 6] Testing Tools Hub template...")
    req_hub = rf.get('/tools/')
    req_hub.user = admin_user
    resp_hub = tools_hub(req_hub)
    assert resp_hub.status_code == 200
    body_hub = resp_hub.content.decode('utf-8')
    assert 'tool_khmer_lunar_converter' in body_hub or 'khmer-lunar-converter' in body_hub, "tool_khmer_lunar_converter missing in hub"
    print("  -> PASS: Tools Hub contains Khmer Lunar Converter card!")

    # 7. Test AI Assistant integration
    print("\n[TEST 7] Testing ToolAiService fallback with khmer_lunar_converter...")
    res_ai = ToolAiService._get_smart_fallback(
        tool_name='khmer_lunar_converter',
        action='explain',
        content='ថ្ងៃសុក្រ ១៤រោច ខែស្រាពណ៍ ឆ្នាំមមី អដ្ឋស័ក ព.ស. ២៥៧០',
        options={},
        school_name='វិទ្យាល័យ ហ៊ុន សែន'
    )
    assert 'ព័ត៌មានកាលបរិច្ឆេទចន្ទគតិខ្មែរ' in res_ai, f"Fallback unexpected: {res_ai}"
    print(f"  -> PASS: ToolAiService fallback explained lunar date: {res_ai[:100]}...")

    print("\n==================================================================")
    print("🎉 ALL TESTS PASSED SUCCESSFULLY! FEATURE 100% OPERATIONAL!")
    print("==================================================================")


if __name__ == '__main__':
    test_khmer_lunar_feature()
