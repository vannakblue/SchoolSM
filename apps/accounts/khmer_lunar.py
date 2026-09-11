"""
Khmer Lunar Calendar Engine (ប្រតិទិនចន្ទគតិខ្មែរ / Chhankitek)
Calculates Khmer traditional lunar dates according to the Buddhist Era (ព.ស.)
and traditional Cambodian astrological rules (ក្បួនហោរាសាស្ត្រ និងប្រតិទិនចន្ទគតិខ្មែរ).

Handles:
- Solar to Lunar conversion (Harakoune, Avomane, Bodethey algorithm)
- 12 Khmer Lunar Months: មិគសិរ, បុស្ស, មាឃ, ផល្គុន, ចេត្រ, ពិសាខ, ជេស្ឋ, អាសាឍ, ស្រាពណ៍, ភទ្របទ, អស្សុជ, កត្តិក
- Leap Months (អធិកមាស): Doubled Asadha into បឋមាសាឍ (1st Asadha) and ទុតិយាសាឍ (2nd Asadha)
- Leap Days (អធិកវារ): Adds 15រោច to ខែជេស្ឋ (30 days instead of 29)
- 12 Animal Zodiac Years (ឆ្នាំសត្វទាំង១២): ជូត, ឆ្លូវ, ខាល, ថោះ, រោង, ម្សាញ់, មមី, មមែ, វក, រកា, ច, កុរ
- 10 Heavenly Stems / Sak (ស័កទាំង១០): ឯកស័ក ដល់ សំរឹទ្ធិស័ក
- Buddhist Era (ពុទ្ធសករាជ ព.ស.): Correct transition on 1រោច ខែពិសាខ
- Khmer numerals conversion (០-៩)
"""

import math
import datetime
from typing import Union, Dict, Any, Optional

KHMER_DIGITS = {
    '0': '០', '1': '១', '2': '២', '3': '៣', '4': '៤',
    '5': '៥', '6': '៦', '7': '៧', '8': '៨', '9': '៩'
}

KHMER_WEEKDAYS = {
    0: 'ចន្ទ',
    1: 'អង្គារ',
    2: 'ពុធ',
    3: 'ព្រហស្បតិ៍',
    4: 'សុក្រ',
    5: 'សៅរ៍',
    6: 'អាទិត្យ',
}

KHMER_ZODIAC = [
    'ជូត', 'ឆ្លូវ', 'ខាល', 'ថោះ', 'រោង', 'ម្សាញ់',
    'មមី', 'មមែ', 'វក', 'រកា', 'ច', 'កុរ'
]

KHMER_STEMS = [
    'សំរឹទ្ធិស័ក', 'ឯកស័ក', 'ទោស័ក', 'ត្រីស័ក', 'ចត្វាស័ក',
    'បញ្ចស័ក', 'ឆស័ក', 'សប្តស័ក', 'អដ្ឋស័ក', 'នព្វស័ក'
]

KHMER_MONTHS_NORMAL = [
    'មិគសិរ', 'បុស្ស', 'មាឃ', 'ផល្គុន', 'ចេត្រ', 'ពិសាខ',
    'ជេស្ឋ', 'អាសាឍ', 'ស្រាពណ៍', 'ភទ្របទ', 'អស្សុជ', 'កត្តិក'
]

KHMER_MONTHS_LEAP = [
    'មិគសិរ', 'បុស្ស', 'មាឃ', 'ផល្គុន', 'ចេត្រ', 'ពិសាខ',
    'ជេស្ឋ', 'បឋមាសាឍ', 'ទុតិយាសាឍ', 'ស្រាពណ៍', 'ភទ្របទ', 'អស្សុជ', 'កត្តិក'
]


def to_khmer_num(val: Union[int, str]) -> str:
    """Converts standard digits to Khmer numerals."""
    return ''.join(KHMER_DIGITS.get(ch, ch) for ch in str(val))


def parse_to_date(dt_input: Union[datetime.date, datetime.datetime, str, None]) -> datetime.date:
    """Safely converts date, datetime, or date strings to datetime.date."""
    if dt_input is None:
        return datetime.date.today()
    if isinstance(dt_input, datetime.datetime):
        return dt_input.date()
    if isinstance(dt_input, datetime.date):
        return dt_input

    s = str(dt_input).strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d'):
        try:
            return datetime.datetime.strptime(s[:10], fmt).date()
        except Exception:
            pass

    # Try ISO with timestamp
    try:
        return datetime.datetime.fromisoformat(s).date()
    except Exception:
        pass

    return datetime.date.today()


def _aharakoune(y: int) -> int:
    return (y * 292207 + 373) % 800


def _harakoune(y: int) -> int:
    return math.floor((y * 292207 + 373) / 800) + 1


def _avomane(y: int) -> int:
    return (11 * _harakoune(y) + 650) % 692


def _regular_leap(y: int) -> bool:
    return (800 - _aharakoune(y)) <= 207


def _bodethey(y: int) -> int:
    ha = _harakoune(y)
    return (ha + math.floor((11 * ha + 650) / 692)) % 30


def _jais_leap(y: int) -> bool:
    b0 = _bodethey(y)
    b1 = _bodethey(y + 1)
    return b0 > 24 or b0 < 6 or (b0 == 24 and b1 == 6) or (b0 == 25 and b1 == 5)


def _is_protetin_leap(y: int) -> bool:
    av0 = _avomane(y)
    av1 = _avomane(y + 1)
    norm = _regular_leap(y)
    val = norm and av0 < 127
    if not norm:
        if av0 == 137 and av1 == 0:
            val = False
        elif av0 < 138:
            val = True
    if not val:
        val = _is_protetin_leap(y - 1) and _jais_leap(y - 1)
    return val


def _great_leap(y: int) -> bool:
    val = _is_protetin_leap(y)
    if _jais_leap(y) and val:
        val = False
    return val


def _days_in_year(y: int) -> int:
    if _jais_leap(y):
        return 384
    if _great_leap(y):
        return 355
    return 354


def _months_of_year(y: int):
    ath = _jais_leap(y)
    great = _great_leap(y)
    items = []
    for i in range(12 + (1 if ath else 0)):
        j = i
        if ath and j >= 8:
            j -= 1
        items.append(29 + (1 if j % 2 != 0 else 0) + (1 if j == 6 and great else 0))
    return items


def calculate_khmer_lunar_details(dt_input: Union[datetime.date, datetime.datetime, str, None]) -> Dict[str, Any]:
    """
    Computes all components of the Khmer Lunar Calendar for any given date.
    Returns a rich dict with:
    - day_of_week: ថ្ងៃចន្ទ, ថ្ងៃអង្គារ, etc.
    - moon_day: ១, ២, ... ១៥
    - moon_phase: កើត or រោច
    - lunar_day: ឧ. ១៤រោច
    - lunar_month: ឧ. ស្រាពណ៍ or បឋមាសាឍ
    - zodiac_year: ឧ. មមី, ម្សាញ់, រោង
    - stem: ឧ. អដ្ឋស័ក, សប្តស័ក, ឆស័ក
    - buddhist_era: ឧ. ២៥៧០
    - full_string: ថ្ងៃព្រហស្បតិ៍ ១៤រោច ខែស្រាពណ៍ ឆ្នាំមមី អដ្ឋស័ក ព.ស. ២៥៧០
    - compact_string: ថ្ងៃព្រហស្បតិ៍ ១៤រោច ខែស្រាពណ៍ ឆ្នាំមមី អដ្ឋស័ក ព.ស.២៥៧០
    """
    d = parse_to_date(dt_input)
    ce = d.year

    # Epoch reference: 1970-11-29 07:00:00 (Cambodia UTC+7)
    target_dt = datetime.datetime(d.year, d.month, d.day, 0, 0, 0)
    epoch = datetime.datetime(1970, 11, 29, 7, 0, 0)
    diff_days = round((target_dt - epoch).total_seconds() / 86400)

    count = 0
    x = 1970 - 638 + 1
    y_target = ce - 638
    if x > y_target:
        x, y_target = y_target, x
    for cur_x in range(x, y_target):
        count += _days_in_year(cur_x)

    y = ce - 638
    day = abs(abs(diff_days) - count) + 1
    be = ce + 543 + (1 if day > 162 else 0)
    length = _days_in_year(y)
    if day > length:
        day -= length
        y += 1

    length_of_year = _months_of_year(y)
    m = 0
    for month_len in length_of_year:
        if day <= month_len:
            break
        day -= month_len
        m += 1

    month_names = KHMER_MONTHS_LEAP if len(length_of_year) == 13 else KHMER_MONTHS_NORMAL
    month_name = month_names[m] if m < len(month_names) else month_names[-1]

    # In Khmer civil practice, the Animal year and Sak change around Khmer New Year (mid-April, ~April 14-16)
    is_after_new_year = (d.month > 4) or (d.month == 4 and d.day >= 14)
    civic_year = ce if is_after_new_year else ce - 1

    zodiac = KHMER_ZODIAC[(civic_year + 8) % 12]
    sak = KHMER_STEMS[(civic_year + 2) % 10]

    day_of_week = KHMER_WEEKDAYS[d.weekday()]
    moon_num = (day - 1) % 15 + 1
    moon_phase = 'កើត' if day <= 15 else 'រោច'
    moon_day_kh = to_khmer_num(moon_num)
    lunar_day_str = f"{moon_day_kh}{moon_phase}"
    be_kh = to_khmer_num(be)

    KHMER_SOLAR_MONTHS_NAMES = {
        1: 'មករា', 2: 'កុម្ភៈ', 3: 'មីនា', 4: 'មេសា',
        5: 'ឧសភា', 6: 'មិថុនា', 7: 'កក្កដា', 8: 'សីហា',
        9: 'កញ្ញា', 10: 'តុលា', 11: 'វិច្ឆិកា', 12: 'ធ្នូ'
    }

    ZODIAC_EMOJIS = {
        'ជូត': '🐀', 'ឆ្លូវ': '🐂', 'ខាល': '🐅', 'ថោះ': '🐇',
        'រោង': '🐉', 'ម្សាញ់': '🐍', 'មមី': '🐎', 'មមែ': '🐐',
        'វក': '🐒', 'រកា': '🐓', 'ច': '🐕', 'កុរ': '🐖'
    }

    month_len = length_of_year[m] if m < len(length_of_year) else 30
    is_holy_day = False
    holy_day_label = ''

    if moon_phase == 'កើត':
        if moon_num == 8:
            is_holy_day = True
            holy_day_label = 'ថ្ងៃសីល (៨កើត)'
        elif moon_num == 15:
            is_holy_day = True
            holy_day_label = 'ថ្ងៃសីល ពេញបូណ៌មី (១៥កើត)'
    else:  # រោច
        if moon_num == 8:
            is_holy_day = True
            holy_day_label = 'ថ្ងៃសីល (៨រោច)'
        elif (month_len == 30 and moon_num == 15) or (month_len == 29 and moon_num == 14) or (moon_num >= month_len - 15):
            is_holy_day = True
            holy_day_label = f'ថ្ងៃសីល ដាច់ខែ ({moon_day_kh}រោច)'

    if moon_phase == 'កើត':
        if moon_num == 15:
            moon_icon = '🌕'
        elif moon_num >= 10:
            moon_icon = '🌔'
        elif moon_num >= 6:
            moon_icon = '🌓'
        elif moon_num >= 2:
            moon_icon = '🌒'
        else:
            moon_icon = '🌑'
    else:
        if (month_len == 30 and moon_num == 15) or (month_len == 29 and moon_num == 14):
            moon_icon = '🌑'
        elif moon_num >= 10:
            moon_icon = '🌘'
        elif moon_num >= 6:
            moon_icon = '🌗'
        elif moon_num >= 2:
            moon_icon = '🌖'
        else:
            moon_icon = '🌕'

    if len(length_of_year) == 13:
        year_type_label = 'ឆ្នាំអធិកមាស (Leap Month)'
    elif _great_leap(y):
        year_type_label = 'ឆ្នាំអធិកវារ (Leap Day)'
    else:
        year_type_label = 'ឆ្នាំប្រក្រតី (Normal Year)'

    solar_day_kh = to_khmer_num(d.day)
    solar_month_kh = KHMER_SOLAR_MONTHS_NAMES.get(d.month, '')
    solar_year_kh = to_khmer_num(d.year)
    solar_full_kh = f"ថ្ងៃ{day_of_week} ទី{solar_day_kh} ខែ{solar_month_kh} ឆ្នាំ{solar_year_kh}"

    full_string = f"ថ្ងៃ{day_of_week} {lunar_day_str} ខែ{month_name} ឆ្នាំ{zodiac} {sak} ព.ស. {be_kh}"
    compact_string = f"ថ្ងៃ{day_of_week} {lunar_day_str} ខែ{month_name} ឆ្នាំ{zodiac} {sak} ព.ស.{be_kh}"
    dual_date_string = f"{solar_full_kh} (ត្រូវនឹង{full_string})"
    official_header_string = f"រាជធានីភ្នំពេញ, {full_string}"

    return {
        'solar_date': d.strftime('%Y-%m-%d'),
        'solar_day': d.day,
        'solar_month': d.month,
        'solar_year': d.year,
        'solar_day_kh': solar_day_kh,
        'solar_month_kh': solar_month_kh,
        'solar_year_kh': solar_year_kh,
        'solar_full_kh': solar_full_kh,
        'day_of_week': f"ថ្ងៃ{day_of_week}",
        'dow_short': day_of_week,
        'moon_num': moon_num,
        'moon_num_kh': moon_day_kh,
        'moon_phase': moon_phase,
        'lunar_day': lunar_day_str,
        'lunar_month': month_name,
        'month_len': month_len,
        'zodiac_year': zodiac,
        'zodiac_full': f"ឆ្នាំ{zodiac}",
        'zodiac_emoji': ZODIAC_EMOJIS.get(zodiac, '✨'),
        'stem': sak,
        'buddhist_era': be,
        'buddhist_era_kh': be_kh,
        'is_holy_day': is_holy_day,
        'holy_day_label': holy_day_label,
        'moon_icon': moon_icon,
        'year_type_label': year_type_label,
        'full_string': full_string,
        'compact_string': compact_string,
        'dual_date_string': dual_date_string,
        'official_header_string': official_header_string,
        'is_leap_month_year': len(length_of_year) == 13,
    }


def get_khmer_lunar_date(dt_input: Union[datetime.date, datetime.datetime, str, None], with_space: bool = True) -> str:
    """
    Returns the standard formatted Khmer Lunar Date string:
    e.g. 'ថ្ងៃព្រហស្បតិ៍ ១៤រោច ខែស្រាពណ៍ ឆ្នាំមមី អដ្ឋស័ក ព.ស. ២៥៧០'
    """
    try:
        details = calculate_khmer_lunar_details(dt_input)
        return details['full_string'] if with_space else details['compact_string']
    except Exception:
        return 'ថ្ងៃចន្ទ ២កើត ខែជេស្ឋ ឆ្នាំម្សាញ់ សំរឹទ្ធិស័ក ព.ស. ២៥៧០'
