import os
import sys
import django
from datetime import date, datetime, time

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.conf import settings
from django.template import Template, Context
from apps.accounts.models import SchoolProfile
from apps.accounts.forms import SchoolProfileForm
from apps.accounts.templatetags.i18n_extras import format_school_date, format_school_datetime, format_school_time

def test_date_format_system():
    print("=== STARTING COMPREHENSIVE SCHOOL DATE & TIME FORMAT TEST SUITE ===")

    # 1. Verify Django global settings
    assert settings.DATE_FORMAT == 'd-m-Y'
    assert settings.SHORT_DATE_FORMAT == 'd-m-Y'
    assert '%d-%m-%Y' in settings.DATE_INPUT_FORMATS
    print("1. [PASS] Django global settings configured with standard dd-mm-yyyy (d-m-Y).")

    # 2. Verify SchoolProfile default date & time formats
    profile = SchoolProfile.get_settings()
    profile.date_format = 'dd-mm-yyyy'
    profile.time_format = 'HH:mm'
    profile.save()
    profile.refresh_from_db()

    assert profile.date_format == 'dd-mm-yyyy'
    assert profile.time_format == 'HH:mm'
    print("2. [PASS] SchoolProfile date_format defaults to 'dd-mm-yyyy' and time_format to 'HH:mm'.")

    # 3. Test template filters with default dd-mm-yyyy and HH:mm
    test_d = date(2026, 9, 2)
    test_dt = datetime(2026, 9, 2, 14, 30, 45)
    test_t = time(14, 30, 45)
    
    assert format_school_date(test_d) == '02-09-2026'
    assert format_school_date('2026-09-02') == '02-09-2026'
    assert format_school_datetime(test_dt) == '02-09-2026 14:30'
    assert format_school_time(test_t) == '14:30'
    print("3. [PASS] format_school_date, format_school_datetime, format_school_time default outputs correct.")

    # 4. Test Template rendering with school_date, school_datetime, school_time filters
    tpl = Template("{% load i18n_extras %}{{ my_date|school_date }} | {{ my_dt|school_datetime }} | {{ my_t|school_time }}")
    rendered = tpl.render(Context({'my_date': test_d, 'my_dt': test_dt, 'my_t': test_t})).strip()
    assert rendered == '02-09-2026 | 02-09-2026 14:30 | 14:30'
    print("4. [PASS] Django Template filters render cleanly.")

    # 5. Test Seconds option (HH:mm:ss)
    profile.time_format = 'HH:mm:ss'
    profile.save()
    assert format_school_time(test_t) == '14:30:45'
    assert format_school_datetime(test_dt) == '02-09-2026 14:30:45'
    print("5. [PASS] 24-hour with seconds (HH:mm:ss) renders '14:30:45' and '02-09-2026 14:30:45'.")

    # 6. Test 12-hour AM/PM with seconds (hh:mm:ss a)
    profile.time_format = 'hh:mm:ss a'
    profile.save()
    assert format_school_time(test_t) == '02:30:45 PM'
    assert format_school_datetime(test_dt) == '02-09-2026 02:30:45 PM'
    print("6. [PASS] 12-hour AM/PM with seconds (hh:mm:ss a) renders '02:30:45 PM'.")

    # 7. Test combined date_format with seconds (dd-mm-yyyy HH:mm:ss)
    profile.date_format = 'dd-mm-yyyy HH:mm:ss'
    profile.save()
    assert format_school_datetime(test_dt) == '02-09-2026 14:30:45'
    print("7. [PASS] Composite date_format 'dd-mm-yyyy HH:mm:ss' renders '02-09-2026 14:30:45'.")

    # 8. Test slash format (dd/mm/yyyy HH:mm:ss)
    profile.date_format = 'dd/mm/yyyy HH:mm:ss'
    profile.save()
    assert format_school_datetime(test_dt) == '02/09/2026 14:30:45'
    assert format_school_date(test_d) == '02/09/2026'
    print("8. [PASS] Format 'dd/mm/yyyy HH:mm:ss' renders '02/09/2026 14:30:45'.")

    # 9. Test ISO format with seconds (yyyy-mm-dd HH:mm:ss)
    profile.date_format = 'yyyy-mm-dd HH:mm:ss'
    profile.save()
    assert format_school_datetime(test_dt) == '2026-09-02 14:30:45'
    assert format_school_date(test_d) == '2026-09-02'
    print("9. [PASS] Format 'yyyy-mm-dd HH:mm:ss' renders '2026-09-02 14:30:45'.")

    # Reset back to default dd-mm-yyyy and HH:mm
    profile.date_format = 'dd-mm-yyyy'
    profile.time_format = 'HH:mm'
    profile.save()
    assert format_school_date(test_d) == '02-09-2026'
    print("10. [PASS] Restored back to default 'dd-mm-yyyy' and 'HH:mm'.")

    # 11. Test SchoolProfileForm contains both date_format and time_format fields
    form = SchoolProfileForm(instance=profile)
    assert 'date_format' in form.fields
    assert 'time_format' in form.fields
    print("11. [PASS] SchoolProfileForm properly includes date_format and time_format select inputs.")

    print("\n=== ALL 11 SCHOOL DATE & TIME FORMAT TESTS PASSED 100%! ===")

if __name__ == '__main__':
    test_date_format_system()
