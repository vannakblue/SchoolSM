from django import template
from apps.accounts.translation_service import t, get_current_language

register = template.Library()

@register.filter(name='t')
def translate_filter(key, lang=None):
    """
    Template filter: {{ 'all_students'|t:current_language }}
    """
    return t(str(key), lang=lang or 'km')

@register.simple_tag(takes_context=True)
def lang_switch(context, kh_text, en_text):
    """
    Simple tag to cleanly output Khmer or English text based on active language:
    {% lang_switch "បញ្ជីសិស្សទាំងអស់" "All Students" %}
    """
    current_lang = context.get('current_language', 'km')
    if current_lang == 'en':
        return en_text
    return kh_text

@register.simple_tag(takes_context=True)
def trans_key(context, key, default=None):
    """
    Simple tag to translate dictionary key:
    {% trans_key 'enroll_student' %}
    """
    current_lang = context.get('current_language', 'km')
    return t(key, lang=current_lang, default=default)


@register.filter(name='school_date')
def format_school_date(val, custom_fmt=None):
    """
    Formats a date/datetime or date string according to the SchoolProfile's date_format (defaults to dd-mm-yyyy).
    Usage: {{ student.date_of_birth|school_date }}
    """
    if not val:
        return ''
    
    from datetime import date, datetime
    
    if isinstance(val, str):
        val = val.strip()
        if not val:
            return ''
        try:
            if len(val) == 10 and '-' in val:
                val = datetime.strptime(val, '%Y-%m-%d').date()
            elif len(val) == 10 and '/' in val:
                val = datetime.strptime(val, '%d/%m/%Y').date()
            elif 'T' in val:
                val = datetime.fromisoformat(val)
        except Exception:
            return val

    if custom_fmt:
        fmt_str = custom_fmt
    else:
        try:
            from apps.accounts.models import SchoolProfile
            profile = SchoolProfile.get_settings()
            df = profile.date_format or 'dd-mm-yyyy'
        except Exception:
            df = 'dd-mm-yyyy'

        if df == 'dd/mm/yyyy':
            fmt_str = '%d/%m/%Y'
        elif df == 'yyyy-mm-dd':
            fmt_str = '%Y-%m-%d'
        elif df == 'dd.mm.yyyy':
            fmt_str = '%d.%m.%Y'
        else:
            fmt_str = '%d-%m-%Y'

    try:
        return val.strftime(fmt_str)
    except Exception:
        return str(val)


@register.filter(name='school_datetime')
def format_school_datetime(val, custom_fmt=None):
    """
    Formats a datetime according to SchoolProfile's date_format + HH:MM:SS.
    Usage: {{ log.created_at|school_datetime }}
    """
    if not val:
        return ''
        
    from datetime import datetime
    
    if isinstance(val, str):
        val = val.strip()
        if not val:
            return ''
        try:
            if 'T' in val:
                val = datetime.fromisoformat(val)
        except Exception:
            return val

    if custom_fmt:
        fmt_str = custom_fmt
    else:
        try:
            from apps.accounts.models import SchoolProfile
            profile = SchoolProfile.get_settings()
            df = profile.date_format or 'dd-mm-yyyy'
        except Exception:
            df = 'dd-mm-yyyy'

        if df == 'dd/mm/yyyy':
            fmt_str = '%d/%m/%Y %H:%M'
        elif df == 'yyyy-mm-dd':
            fmt_str = '%Y-%m-%d %H:%M'
        elif df == 'dd.mm.yyyy':
            fmt_str = '%d.%m.%Y %H:%M'
        else:
            fmt_str = '%d-%m-%Y %H:%M'

    try:
        return val.strftime(fmt_str)
    except Exception:
        return str(val)


KHMER_DAYS = {
    0: 'ចន្ទ',
    1: 'អង្គារ',
    2: 'ពុធ',
    3: 'ព្រហស្បតិ៍',
    4: 'សុក្រ',
    5: 'សៅរ៍',
    6: 'អាទិត្យ',
}

KHMER_MONTHS = {
    1: 'មករា',
    2: 'កុម្ភៈ',
    3: 'មីនា',
    4: 'មេសា',
    5: 'ឧសភា',
    6: 'មិថុនា',
    7: 'កក្កដា',
    8: 'សីហា',
    9: 'កញ្ញា',
    10: 'តុលា',
    11: 'វិច្ឆិកា',
    12: 'ធ្នូ',
}

KHMER_DIGITS = {
    '0': '០', '1': '១', '2': '២', '3': '៣', '4': '៤',
    '5': '៥', '6': '៦', '7': '៧', '8': '៨', '9': '៩'
}

@register.filter(name='to_khmer_number')
def to_khmer_number_filter(val):
    if val is None or val == '':
        return ''
    return ''.join(KHMER_DIGITS.get(ch, ch) for ch in str(val))


@register.filter(name='khmer_full_date')
def khmer_full_date_filter(val, use_khmer_digits=True):
    """
    Converts a date object/string to Cambodian formal date format:
    e.g. ថ្ងៃ ពុធ ទី ២ ខែ កញ្ញា ឆ្នាំ ២០២៦
    """
    if not val:
        return ''
    from datetime import date, datetime
    if isinstance(val, str):
        try:
            val = datetime.strptime(val[:10], '%Y-%m-%d').date()
        except Exception:
            return val
    elif isinstance(val, datetime):
        val = val.date()

    if not isinstance(val, date):
        return str(val)

    day_name = KHMER_DAYS.get(val.weekday(), '')
    month_name = KHMER_MONTHS.get(val.month, '')
    
    if use_khmer_digits:
        day_num = to_khmer_number_filter(val.day)
        year_num = to_khmer_number_filter(val.year)
    else:
        day_num = f"{val.day}"
        year_num = f"{val.year}"

    return f"ថ្ងៃ {day_name} ទី {day_num} ខែ {month_name} ឆ្នាំ {year_num}"


