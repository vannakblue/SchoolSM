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


def _get_school_formats():
    try:
        from apps.accounts.models import SchoolProfile
        profile = SchoolProfile.get_settings()
        df = getattr(profile, 'date_format', 'dd-mm-yyyy') or 'dd-mm-yyyy'
        tf = getattr(profile, 'time_format', 'HH:mm') or 'HH:mm'
        return df, tf
    except Exception:
        return 'dd-mm-yyyy', 'HH:mm'


def _map_date_strftime(df):
    if '/' in df:
        return '%d/%m/%Y'
    elif '.' in df:
        return '%d.%m.%Y'
    elif df.startswith('yyyy'):
        return '%Y-%m-%d'
    return '%d-%m-%Y'


def _map_time_strftime(tf):
    if tf == 'HH:mm:ss':
        return '%H:%M:%S'
    elif tf == 'hh:mm:ss a':
        return '%I:%M:%S %p'
    elif tf == 'hh:mm a':
        return '%I:%M %p'
    return '%H:%M'


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
            elif 'T' in val or ' ' in val:
                val = datetime.fromisoformat(val)
        except Exception:
            return val

    if custom_fmt:
        fmt_str = custom_fmt
    else:
        df, _ = _get_school_formats()
        date_fmt = _map_date_strftime(df)
        if isinstance(val, datetime) and any(tok in df for tok in ['HH:mm', 'HH:mm:ss', 'hh:mm']):
            if 'HH:mm:ss' in df or 'hh:mm:ss' in df:
                time_fmt = '%I:%M:%S %p' if 'hh:' in df else '%H:%M:%S'
            elif 'hh:mm' in df:
                time_fmt = '%I:%M %p'
            else:
                time_fmt = '%H:%M'
            fmt_str = f"{date_fmt} {time_fmt}"
        else:
            fmt_str = date_fmt

    try:
        return val.strftime(fmt_str)
    except Exception:
        return str(val)


@register.filter(name='school_time')
def format_school_time(val, custom_fmt=None):
    """
    Formats a time or datetime according to SchoolProfile's time_format (defaults to HH:mm).
    Supports hours, minutes, seconds (HH:mm, HH:mm:ss, hh:mm a, hh:mm:ss a).
    Usage: {{ log.created_at|school_time }}
    """
    if not val:
        return ''
        
    from datetime import datetime, time
    
    if isinstance(val, str):
        val = val.strip()
        if not val:
            return ''
        try:
            if 'T' in val or ' ' in val:
                val = datetime.fromisoformat(val)
            elif len(val) == 8 and ':' in val:
                val = datetime.strptime(val, '%H:%M:%S').time()
            elif len(val) == 5 and ':' in val:
                val = datetime.strptime(val, '%H:%M').time()
        except Exception:
            return val

    if custom_fmt:
        fmt_str = custom_fmt
    else:
        _, tf = _get_school_formats()
        fmt_str = _map_time_strftime(tf)

    try:
        return val.strftime(fmt_str)
    except Exception:
        return str(val)


@register.filter(name='school_datetime')
def format_school_datetime(val, custom_fmt=None):
    """
    Formats a datetime according to SchoolProfile's date_format + time_format (with hours, minutes, seconds).
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
            elif len(val) >= 19 and '-' in val and ' ' in val:
                val = datetime.strptime(val[:19], '%Y-%m-%d %H:%M:%S')
        except Exception:
            return val

    if custom_fmt:
        fmt_str = custom_fmt
    else:
        df, tf = _get_school_formats()
        date_fmt = _map_date_strftime(df)
        if any(tok in df for tok in ['HH:mm', 'HH:mm:ss', 'hh:mm']):
            if 'HH:mm:ss' in df or 'hh:mm:ss' in df:
                time_fmt = '%I:%M:%S %p' if 'hh:' in df else '%H:%M:%S'
            elif 'hh:mm' in df:
                time_fmt = '%I:%M %p'
            else:
                time_fmt = '%H:%M'
        else:
            time_fmt = _map_time_strftime(tf)
        fmt_str = f"{date_fmt} {time_fmt}"

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


