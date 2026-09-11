/**
 * Khmer Lunar Calendar Engine (Client-Side JavaScript)
 * ប្រតិទិនចន្ទគតិខ្មែរ (Chhankitek)
 * 
 * Provides real-time automatic conversion from Solar/Gregorian date to Khmer Lunar date.
 * Matches official MoEYS standard:
 * e.g. "ថ្ងៃព្រហស្បតិ៍ ១៣រោច ខែស្រាពណ៍ ឆ្នាំមមី អដ្ឋស័ក ព.ស. ២៥៧០"
 */

(function (window) {
    'use strict';

    const KHMER_DIGITS = {
        '0': '០', '1': '១', '2': '២', '3': '៣', '4': '៤',
        '5': '៥', '6': '៦', '7': '៧', '8': '៨', '9': '៩'
    };

    const KHMER_WEEKDAYS = ['ចន្ទ', 'អង្គារ', 'ពុធ', 'ព្រហស្បតិ៍', 'សុក្រ', 'សៅរ៍', 'អាទិត្យ'];

    const KHMER_ZODIAC = [
        'ជូត', 'ឆ្លូវ', 'ខាល', 'ថោះ', 'រោង', 'ម្សាញ់',
        'មមី', 'មមែ', 'វក', 'រកា', 'ច', 'កុរ'
    ];

    const KHMER_STEMS = [
        'សំរឹទ្ធិស័ក', 'ឯកស័ក', 'ទោស័ក', 'ត្រីស័ក', 'ចត្វាស័ក',
        'បញ្ចស័ក', 'ឆស័ក', 'សប្តស័ក', 'អដ្ឋស័ក', 'នព្វស័ក'
    ];

    const KHMER_MONTHS_NORMAL = [
        'មិគសិរ', 'បុស្ស', 'មាឃ', 'ផល្គុន', 'ចេត្រ', 'ពិសាខ',
        'ជេស្ឋ', 'អាសាឍ', 'ស្រាពណ៍', 'ភទ្របទ', 'អស្សុជ', 'កត្តិក'
    ];

    const KHMER_MONTHS_LEAP = [
        'មិគសិរ', 'បុស្ស', 'មាឃ', 'ផល្គុន', 'ចេត្រ', 'ពិសាខ',
        'ជេស្ឋ', 'បឋមាសាឍ', 'ទុតិយាសាឍ', 'ស្រាពណ៍', 'ភទ្របទ', 'អស្សុជ', 'កត្តិក'
    ];

    const KHMER_SOLAR_MONTHS = {
        'មករា': 1, 'កុម្ភៈ': 2, 'មីនា': 3, 'មេសា': 4,
        'ឧសភា': 5, 'មិថុនា': 6, 'កក្កដា': 7, 'សីហា': 8,
        'កញ្ញា': 9, 'តុលា': 10, 'វិច្ឆិកា': 11, 'ធ្នូ': 12
    };

    function toKhmerDigits(num) {
        if (num === null || num === undefined) return '';
        return String(num).split('').map(ch => KHMER_DIGITS[ch] || ch).join('');
    }

    function parseKhmerDigits(str) {
        if (!str) return '';
        const REVERSE_DIGITS = {
            '០': '0', '១': '1', '២': '2', '៣': '3', '៤': '4',
            '៥': '5', '៦': '6', '៧': '7', '៨': '8', '៩': '9'
        };
        return String(str).split('').map(ch => REVERSE_DIGITS[ch] !== undefined ? REVERSE_DIGITS[ch] : ch).join('');
    }

    function aharakoune(y) {
        return (y * 292207 + 373) % 800;
    }

    function harakoune(y) {
        return Math.floor((y * 292207 + 373) / 800) + 1;
    }

    function avomane(y) {
        return (11 * harakoune(y) + 650) % 692;
    }

    function regularLeap(y) {
        return (800 - aharakoune(y)) <= 207;
    }

    function bodethey(y) {
        const ha = harakoune(y);
        return (ha + Math.floor((11 * ha + 650) / 692)) % 30;
    }

    function jaisLeap(y) {
        const b0 = bodethey(y);
        const b1 = bodethey(y + 1);
        return b0 > 24 || b0 < 6 || (b0 === 24 && b1 === 6) || (b0 === 25 && b1 === 5);
    }

    function isProtetinLeap(y) {
        const av0 = avomane(y);
        const av1 = avomane(y + 1);
        const norm = regularLeap(y);
        let val = norm && av0 < 127;
        if (!norm) {
            if (av0 === 137 && av1 === 0) val = false;
            else if (av0 < 138) val = true;
        }
        if (!val) {
            val = isProtetinLeap(y - 1) && jaisLeap(y - 1);
        }
        return val;
    }

    function greatLeap(y) {
        let val = isProtetinLeap(y);
        if (jaisLeap(y) && val) val = false;
        return val;
    }

    function daysInYear(y) {
        if (jaisLeap(y)) return 384;
        if (greatLeap(y)) return 355;
        return 354;
    }

    function monthsOfYear(y) {
        const ath = jaisLeap(y);
        const great = greatLeap(y);
        const items = [];
        for (let i = 0; i < 12 + (ath ? 1 : 0); i++) {
            let j = i;
            if (ath && j >= 8) j -= 1;
            items.push(29 + (j % 2 !== 0 ? 1 : 0) + (j === 6 && great ? 1 : 0));
        }
        return items;
    }

    function parseDate(input) {
        if (!input) return new Date();
        if (input instanceof Date && !isNaN(input)) return input;

        const str = String(input).trim();

        // 1. Check standard ISO format: YYYY-MM-DD
        const isoMatch = str.match(/^(\d{4})[/-](\d{1,2})[/-](\d{1,2})/);
        if (isoMatch) {
            return new Date(parseInt(isoMatch[1], 10), parseInt(isoMatch[2], 10) - 1, parseInt(isoMatch[3], 10));
        }

        // 2. Check DD/MM/YYYY or DD-MM-YYYY
        const dmyMatch = str.match(/^(\d{1,2})[/-](\d{1,2})[/-](\d{4})/);
        if (dmyMatch) {
            return new Date(parseInt(dmyMatch[3], 10), parseInt(dmyMatch[2], 10) - 1, parseInt(dmyMatch[1], 10));
        }

        // 3. Check Khmer solar string: e.g. "ថ្ងៃទី ១៨ ខែ ឧសភា ឆ្នាំ ២០២៦" or "ទី០៦ ខែតុលា ឆ្នាំ២០២៦"
        const latinDigitsStr = parseKhmerDigits(str);
        const khMatch = latinDigitsStr.match(/(\d{1,2})\s*ខែ\s*([^\s]+)\s*ឆ្នាំ\s*(\d{4})/);
        if (khMatch) {
            const day = parseInt(khMatch[1], 10);
            const rawMonth = khMatch[2].trim();
            const year = parseInt(khMatch[3], 10);
            let month = 1;
            for (const [mName, mIdx] of Object.entries(KHMER_SOLAR_MONTHS)) {
                if (rawMonth.includes(mName)) {
                    month = mIdx;
                    break;
                }
            }
            return new Date(year, month - 1, day);
        }

        const fallback = new Date(str);
        return isNaN(fallback.getTime()) ? new Date() : fallback;
    }

    function calculateLunarDetails(input) {
        const d = parseDate(input);
        const ce = d.getFullYear();

        // Epoch: 1970-11-29 UTC (286596e5 ms)
        const targetMidnight = new Date(Date.UTC(ce, d.getMonth(), d.getDate(), 0, 0, 0));
        const epoch = new Date(Date.UTC(1970, 10, 29, 0, 0, 0));
        const diffDays = Math.round((targetMidnight - epoch) / 86400000);

        let count = 0;
        let x = 1970 - 638 + 1;
        let yTarget = ce - 638;
        if (x > yTarget) {
            const tmp = x; x = yTarget; yTarget = tmp;
        }
        for (let curX = x; curX < yTarget; curX++) {
            count += daysInYear(curX);
        }

        let y = ce - 638;
        let day = Math.abs(Math.abs(diffDays) - count) + 1;
        const be = ce + 543 + (day > 162 ? 1 : 0);
        const length = daysInYear(y);
        if (day > length) {
            day -= length;
            y += 1;
        }

        const lengthOfYear = monthsOfYear(y);
        let m = 0;
        for (const monthLen of lengthOfYear) {
            if (day <= monthLen) break;
            day -= monthLen;
            m += 1;
        }

        const monthNames = lengthOfYear.length === 13 ? KHMER_MONTHS_LEAP : KHMER_MONTHS_NORMAL;
        const monthName = m < monthNames.length ? monthNames[m] : monthNames[monthNames.length - 1];

        // Civic animal year & stem changes at Khmer New Year (~April 14)
        const isAfterNewYear = (d.getMonth() + 1 > 4) || (d.getMonth() + 1 === 4 && d.getDate() >= 14);
        const civicYear = isAfterNewYear ? ce : ce - 1;

        const zodiac = KHMER_ZODIAC[((civicYear + 8) % 12 + 12) % 12];
        const sak = KHMER_STEMS[((civicYear + 2) % 10 + 10) % 10];

        // Weekday (0=Monday in JS weekday mapping)
        const jsDay = d.getDay(); // 0=Sunday, 1=Monday...
        const khDayIdx = (jsDay + 6) % 7;
        const dayOfWeek = KHMER_WEEKDAYS[khDayIdx];

        const moonNum = ((day - 1) % 15) + 1;
        const moonPhase = day <= 15 ? 'កើត' : 'រោច';
        const moonDayKh = toKhmerDigits(moonNum);
        const lunarDayStr = `${moonDayKh}${moonPhase}`;
        const beKh = toKhmerDigits(be);

        const fullString = `ថ្ងៃ${dayOfWeek} ${lunarDayStr} ខែ${monthName} ឆ្នាំ${zodiac} ${sak} ព.ស. ${beKh}`;
        const compactString = `ថ្ងៃ${dayOfWeek} ${lunarDayStr} ខែ${monthName} ឆ្នាំ${zodiac} ${sak} ព.ស.${beKh}`;

        const ZODIAC_EMOJIS = {
            'ជូត': '🐀', 'ឆ្លូវ': '🐂', 'ខាល': '🐅', 'ថោះ': '🐇',
            'រោង': '🐉', 'ម្សាញ់': '🐍', 'មមី': '🐎', 'មមែ': '🐐',
            'វក': '🐒', 'រកា': '🐓', 'ច': '🐕', 'កុរ': '🐖'
        };

        const KHMER_MONTH_NAMES_SOLAR = [
            'មករា', 'កុម្ភៈ', 'មីនា', 'មេសា', 'ឧសភា', 'មិថុនា',
            'កក្កដា', 'សីហា', 'កញ្ញា', 'តុលា', 'វិច្ឆិកា', 'ធ្នូ'
        ];

        const monthLen = lengthOfYear[m] || 30;
        let isHolyDay = false;
        let holyDayLabel = '';

        if (moonPhase === 'កើត') {
            if (moonNum === 8) {
                isHolyDay = true;
                holyDayLabel = 'ថ្ងៃសីល (៨កើត)';
            } else if (moonNum === 15) {
                isHolyDay = true;
                holyDayLabel = 'ថ្ងៃសីល ពេញបូណ៌មី (១៥កើត)';
            }
        } else {
            if (moonNum === 8) {
                isHolyDay = true;
                holyDayLabel = 'ថ្ងៃសីល (៨រោច)';
            } else if ((monthLen === 30 && moonNum === 15) || (monthLen === 29 && moonNum === 14) || (moonNum >= monthLen - 15)) {
                isHolyDay = true;
                holyDayLabel = `ថ្ងៃសីល ដាច់ខែ (${moonDayKh}រោច)`;
            }
        }

        let moonIcon = '🌕';
        if (moonPhase === 'កើត') {
            if (moonNum === 15) moonIcon = '🌕';
            else if (moonNum >= 10) moonIcon = '🌔';
            else if (moonNum >= 6) moonIcon = '🌓';
            else if (moonNum >= 2) moonIcon = '🌒';
            else moonIcon = '🌑';
        } else {
            if ((monthLen === 30 && moonNum === 15) || (monthLen === 29 && moonNum === 14)) moonIcon = '🌑';
            else if (moonNum >= 10) moonIcon = '🌘';
            else if (moonNum >= 6) moonIcon = '🌗';
            else if (moonNum >= 2) moonIcon = '🌖';
            else moonIcon = '🌕';
        }

        let yearTypeLabel = 'ឆ្នាំប្រក្រតី (Normal Year)';
        if (lengthOfYear.length === 13) {
            yearTypeLabel = 'ឆ្នាំអធិកមាស (Leap Month)';
        } else if (greatLeap(y)) {
            yearTypeLabel = 'ឆ្នាំអធិកវារ (Leap Day)';
        }

        const solarDayKh = toKhmerDigits(d.getDate());
        const solarMonthKh = KHMER_MONTH_NAMES_SOLAR[d.getMonth()] || '';
        const solarYearKh = toKhmerDigits(ce);
        const solarFullKh = `ថ្ងៃ${dayOfWeek} ទី${solarDayKh} ខែ${solarMonthKh} ឆ្នាំ${solarYearKh}`;
        const dualDateString = `${solarFullKh} (ត្រូវនឹង${fullString})`;
        const officialHeaderString = `រាជធានីភ្នំពេញ, ${fullString}`;

        return {
            solarDate: `${ce}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`,
            solarDay: d.getDate(),
            solarMonth: d.getMonth() + 1,
            solarYear: ce,
            solarDayKh,
            solarMonthKh,
            solarYearKh,
            solarFullKh,
            dayOfWeek: `ថ្ងៃ${dayOfWeek}`,
            dowShort: dayOfWeek,
            moonNum,
            moonNumKh: moonDayKh,
            moonPhase,
            lunarDay: lunarDayStr,
            lunarMonth: monthName,
            monthLen,
            zodiacYear: zodiac,
            zodiacFull: `ឆ្នាំ${zodiac}`,
            zodiacEmoji: ZODIAC_EMOJIS[zodiac] || '✨',
            stem: sak,
            buddhistEra: be,
            buddhistEraKh: beKh,
            isHolyDay,
            holyDayLabel,
            moonIcon,
            yearTypeLabel,
            fullString,
            compactString,
            dualDateString,
            officialHeaderString,
            isLeapMonthYear: lengthOfYear.length === 13
        };
    }

    function getLunarDate(input, withSpace = true) {
        try {
            const details = calculateLunarDetails(input);
            return withSpace ? details.fullString : details.compactString;
        } catch (e) {
            return 'ថ្ងៃចន្ទ ២កើត ខែជេស្ឋ ឆ្នាំម្សាញ់ សំរឹទ្ធិស័ក ព.ស. ២៥៧០';
        }
    }

    /**
     * Binds real-time automatic conversion between a solar date element (input, select, or text)
     * and one or more lunar display elements.
     */
    function bindAutoConversion(solarSelector, lunarSelector, options = {}) {
        const solarEl = typeof solarSelector === 'string' ? document.querySelector(solarSelector) : solarSelector;
        if (!solarEl) return;

        const updateFn = function () {
            let val = solarEl.value !== undefined ? solarEl.value : (solarEl.textContent || '');
            if (!val) return;
            const lunarStr = getLunarDate(val, options.withSpace !== false);

            if (typeof lunarSelector === 'string') {
                document.querySelectorAll(lunarSelector).forEach(target => {
                    if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') {
                        target.value = lunarStr;
                        target.dispatchEvent(new Event('input', { bubbles: true }));
                    } else {
                        target.textContent = lunarStr;
                    }
                });
            } else if (lunarSelector && typeof lunarSelector === 'object') {
                if (lunarSelector.tagName === 'INPUT' || lunarSelector.tagName === 'TEXTAREA') {
                    lunarSelector.value = lunarStr;
                    lunarSelector.dispatchEvent(new Event('input', { bubbles: true }));
                } else {
                    lunarSelector.textContent = lunarStr;
                }
            }

            if (typeof options.onUpdate === 'function') {
                options.onUpdate(lunarStr, val);
            }
        };

        ['input', 'change'].forEach(evt => solarEl.addEventListener(evt, updateFn));
    }

    // Expose KhmerLunar global object
    window.KhmerLunar = {
        getLunarDate,
        getLunarDetails: calculateLunarDetails,
        parseDate,
        toKhmerDigits,
        bindAutoConversion
    };

})(typeof window !== 'undefined' ? window : this);
