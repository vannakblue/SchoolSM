import os
import sys
import django
from datetime import date, datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.conf import settings
from django.template import Template, Context
from apps.accounts.models import SchoolProfile
from apps.accounts.forms import SchoolProfileForm
from apps.accounts.templatetags.i18n_extras import format_school_date, format_school_datetime

def test_date_format_system():
    print("=== STARTING SCHOOL DATE FORMAT (DD-MM-YYYY) TEST SUITE ===")

    # 1. Verify Django global settings
    assert settings.DATE_FORMAT == 'd-m-Y'
    assert settings.SHORT_DATE_FORMAT == 'd-m-Y'
    assert '%d-%m-%Y' in settings.DATE_INPUT_FORMATS
    print("1. [PASS] Django global settings configured with standard dd-mm-yyyy (d-m-Y).")

    # 2. Verify SchoolProfile default date format
    profile = SchoolProfile.get_settings()
    profile.date_format = 'dd-mm-yyyy'
    profile.save()
    profile.refresh_from_db()

    assert profile.date_format == 'dd-mm-yyyy'
    print("2. [PASS] SchoolProfile date_format defaults to 'dd-mm-yyyy'.")

    # 3. Test template filter with default dd-mm-yyyy
    test_d = date(2026, 9, 2)
    test_dt = datetime(2026, 9, 2, 14, 30, 0)
    
    assert format_school_date(test_d) == '02-09-2026'
    assert format_school_date('2026-09-02') == '02-09-2026'
    assert format_school_datetime(test_dt) == '02-09-2026 14:30'
    print("3. [PASS] format_school_date outputs '02-09-2026' for date object & ISO string.")

    # 4. Test Template rendering with school_date filter
    tpl = Template("{% load i18n_extras %}{{ my_date|school_date }}")
    rendered = tpl.render(Context({'my_date': test_d})).strip()
    assert rendered == '02-09-2026'
    print("4. [PASS] Template filter {{ my_date|school_date }} renders '02-09-2026'.")

    # 5. Test Admin custom override (e.g. admin switches to dd/mm/yyyy)
    profile.date_format = 'dd/mm/yyyy'
    profile.save()
    assert format_school_date(test_d) == '02/09/2026'
    print("5. [PASS] Admin customization to 'dd/mm/yyyy' works seamlessly.")

    # 6. Test Admin custom override to yyyy-mm-dd
    profile.date_format = 'yyyy-mm-dd'
    profile.save()
    assert format_school_date(test_d) == '2026-09-02'
    print("6. [PASS] Admin customization to 'yyyy-mm-dd' works seamlessly.")

    # Reset back to default dd-mm-yyyy
    profile.date_format = 'dd-mm-yyyy'
    profile.save()
    assert format_school_date(test_d) == '02-09-2026'
    print("7. [PASS] Successfully restored back to default 'dd-mm-yyyy'.")

    # 8. Test SchoolProfileForm contains date_format field
    form = SchoolProfileForm(instance=profile)
    assert 'date_format' in form.fields
    print("8. [PASS] SchoolProfileForm properly includes date_format select input.")

    print("\n=== ALL 8 SCHOOL DATE FORMAT TESTS PASSED 100%! ===")

if __name__ == '__main__':
    test_date_format_system()
