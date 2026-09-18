/**
 * SchoolSM - Report Card Automatic Solar-to-Lunar Date Synchronization Engine
 * ប្រព័ន្ធកែតម្រូវកាលបរិច្ឆេទសុរិយគតិ និងបំប្លែងទៅចន្ទគតិស្វ័យប្រវត្តិនៃព្រឹត្តិបត្រពិន្ទុ
 *
 * Supports:
 * - Real-time conversion from Solar (Gregorian) date input/picker to authentic Khmer Lunar date
 * - Immediate sync across all report card sheets in batch (e.g. 60 students per class)
 * - In-place editing on the printable sheet (contenteditable)
 * - Preset "Today" (ថ្ងៃនេះ) and "Blank Dots" (ទុកចន្លោះចុចៗ)
 * - Persistent storage in localStorage
 */

(function () {
    'use strict';

    const STORAGE_KEY_DATE = 'schoolsm_rc_solar_date';
    const STORAGE_KEY_PREFIX = 'schoolsm_rc_school_prefix';

    let debounceTimer = null;
    let currentPrefix = '';

    function getSchoolPrefix() {
        const prefixInput = document.getElementById('toolbarPrefixInput');
        if (prefixInput && prefixInput.value.trim() && !prefixInput.value.trim().includes('...')) {
            return prefixInput.value.trim();
        }
        const firstAbbr = document.querySelector('.school-abbr-txt');
        if (firstAbbr && firstAbbr.textContent.trim() && !firstAbbr.textContent.includes('...')) {
            return firstAbbr.textContent.trim();
        }
        const saved = localStorage.getItem(STORAGE_KEY_PREFIX);
        if (saved) return saved;
        return '';
    }

    function setSchoolPrefix(newPrefix) {
        currentPrefix = newPrefix;
        localStorage.setItem(STORAGE_KEY_PREFIX, newPrefix);
        document.querySelectorAll('.school-abbr-txt, .school-loc-txt').forEach(el => {
            if (newPrefix) {
                el.textContent = newPrefix;
            }
        });
    }

    function flashElement(el) {
        if (!el) return;
        el.classList.add('rc-date-highlight');
        setTimeout(() => {
            el.classList.remove('rc-date-highlight');
        }, 800);
    }

    function applyDateToReportCards(dateInput, isManualReset = false) {
        const lunarDisplay = document.getElementById('toolbarLunarDisplay');
        const solarPicker = document.getElementById('toolbarSolarPicker');
        const solarInput = document.getElementById('toolbarSolarInput');
        const prefix = currentPrefix || getSchoolPrefix();

        // 1. Handle Reset to Dots
        if (isManualReset || !dateInput) {
            localStorage.removeItem(STORAGE_KEY_DATE);

            if (solarPicker) solarPicker.value = '';
            if (solarInput && document.activeElement !== solarInput) solarInput.value = '';
            if (lunarDisplay) {
                lunarDisplay.textContent = 'ទុកចន្លោះចុចៗ (Blank / Dots)';
                lunarDisplay.classList.remove('text-success');
                lunarDisplay.classList.add('text-muted');
            }

            // Restore all sheets to authentic MoEYS blank dotted format
            document.querySelectorAll('.rc-date-buddhist').forEach(el => {
                const defaultBlank = el.getAttribute('data-default-blank') ||
                    'ថ្ងៃ..........................ខែ....................ឆ្នាំ........................ ព.ស. ២៥.......';
                el.textContent = defaultBlank;
                flashElement(el);
            });

            document.querySelectorAll('.rc-date-solar').forEach(el => {
                const template = el.getAttribute('data-template-type') || 'tr';
                const abbrHtml = `<span class="school-abbr-txt" contenteditable="true" title="ចុចដើម្បីកែប្រែអក្សរកាត់">${prefix || 'វ.ហ.ស.ក.ក'}</span>`;
                const locHtml = `<span class="school-loc-txt" contenteditable="true" title="ចុចកែប្រែទីតាំង">${prefix || '.....................'}</span>`;

                if (template === 'tr' || template === 'moeys_annual' || template === 'transcript') {
                    el.innerHTML = `${abbrHtml} ថ្ងៃទី............... ខែ ................... ឆ្នាំ..................`;
                } else {
                    el.innerHTML = `ថ្ងៃទី............... ខែ ................... ឆ្នាំ..................`;
                }
                flashElement(el);
            });

            return;
        }

        // 2. Parse and Calculate Khmer Lunar Details
        if (!window.KhmerLunar) return;

        const d = window.KhmerLunar.parseDate(dateInput);
        if (!d || isNaN(d.getTime())) return;

        const details = window.KhmerLunar.getLunarDetails(d);
        const lunarFull = details.fullString;
        const dayKh = window.KhmerLunar.toKhmerDigits(d.getDate());
        const monthKh = details.solarMonthKh;
        const yearKh = window.KhmerLunar.toKhmerDigits(d.getFullYear());
        const isoDate = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
        const solarKhmerFormatted = `ថ្ងៃទី${dayKh} ខែ${monthKh} ឆ្នាំ${yearKh}`;

        // Save to localStorage
        localStorage.setItem(STORAGE_KEY_DATE, isoDate);

        // Update Toolbar UI
        if (solarPicker && solarPicker.value !== isoDate) {
            solarPicker.value = isoDate;
        }
        if (solarInput && document.activeElement !== solarInput) {
            solarInput.value = solarKhmerFormatted;
        }
        if (lunarDisplay) {
            lunarDisplay.textContent = lunarFull;
            lunarDisplay.classList.remove('text-muted');
            lunarDisplay.classList.add('text-success');
        }

        // Update all report card sheets
        document.querySelectorAll('.rc-date-buddhist').forEach(el => {
            el.textContent = lunarFull;
            flashElement(el);
        });

        document.querySelectorAll('.rc-date-solar').forEach(el => {
            const template = el.getAttribute('data-template-type') || 'tr';
            const curAbbr = prefix || 'វ.ហ.ស.ក.ក';
            const abbrHtml = `<span class="school-abbr-txt" contenteditable="true" title="ចុចដើម្បីកែប្រែអក្សរកាត់">${curAbbr}</span>`;
            const curLoc = prefix || (template === 'transcript' ? '.....................' : '......');
            const locHtml = `<span class="school-loc-txt" contenteditable="true" title="ចុចកែប្រែទីតាំង">${curLoc}</span>`;

            if (template === 'tr' || template === 'moeys_annual' || template === 'transcript') {
                el.innerHTML = `${abbrHtml} ថ្ងៃទី${dayKh} ខែ${monthKh} ឆ្នាំ${yearKh}`;
            } else {
                el.innerHTML = `ថ្ងៃទី${dayKh} ខែ${monthKh} ឆ្នាំ${yearKh}`;
            }
            flashElement(el);
        });
    }

    function initReportCardDateSync() {
        const solarPicker = document.getElementById('toolbarSolarPicker');
        const solarInput = document.getElementById('toolbarSolarInput');
        const prefixInput = document.getElementById('toolbarPrefixInput');
        const btnToday = document.getElementById('btnSetTodayDate');
        const btnResetDots = document.getElementById('btnResetDateDots');

        const serverPrefix = prefixInput && prefixInput.value.trim() && !prefixInput.value.trim().includes('...') ? prefixInput.value.trim() : '';
        if (serverPrefix) {
            currentPrefix = serverPrefix;
            localStorage.setItem(STORAGE_KEY_PREFIX, serverPrefix);
        } else {
            currentPrefix = getSchoolPrefix();
        }
        if (prefixInput && currentPrefix) {
            prefixInput.value = currentPrefix;
        }

        // Store original blank placeholders on sheets
        document.querySelectorAll('.rc-date-buddhist').forEach(el => {
            if (!el.getAttribute('data-default-blank')) {
                el.setAttribute('data-default-blank', el.textContent.trim());
            }
        });

        // 1. Toolbar Solar Picker Event
        if (solarPicker) {
            solarPicker.addEventListener('change', function () {
                if (this.value) {
                    applyDateToReportCards(this.value);
                }
            });
        }

        // 2. Toolbar Solar Text Input Event (Real-time Typing)
        if (solarInput) {
            solarInput.addEventListener('input', function () {
                clearTimeout(debounceTimer);
                const val = this.value.trim();
                debounceTimer = setTimeout(() => {
                    if (val) {
                        applyDateToReportCards(val);
                    }
                }, 400);
            });

            solarInput.addEventListener('blur', function () {
                const val = this.value.trim();
                if (val) {
                    applyDateToReportCards(val);
                }
            });
        }

        // 3. Prefix Input Event
        if (prefixInput) {
            prefixInput.addEventListener('input', function () {
                setSchoolPrefix(this.value.trim());
            });
        }

        // 4. Quick Buttons
        if (btnToday) {
            btnToday.addEventListener('click', function (e) {
                e.preventDefault();
                applyDateToReportCards(new Date());
            });
        }

        if (btnResetDots) {
            btnResetDots.addEventListener('click', function (e) {
                e.preventDefault();
                applyDateToReportCards(null, true);
            });
        }

        // 5. Direct In-Sheet Editing on .rc-date-solar
        document.querySelectorAll('.rc-date-solar').forEach(el => {
            el.addEventListener('input', function () {
                clearTimeout(debounceTimer);
                const text = this.innerText.trim();
                debounceTimer = setTimeout(() => {
                    if (window.KhmerLunar && text) {
                        const parsed = window.KhmerLunar.parseDate(text);
                        if (parsed && !isNaN(parsed.getTime())) {
                            applyDateToReportCards(parsed);
                        }
                    }
                }, 500);
            });

            el.addEventListener('blur', function () {
                const text = this.innerText.trim();
                if (window.KhmerLunar && text) {
                    const parsed = window.KhmerLunar.parseDate(text);
                    if (parsed && !isNaN(parsed.getTime())) {
                        applyDateToReportCards(parsed);
                    }
                }
            });
        });

        // 6. Direct In-Sheet Editing on .rc-date-buddhist (sync across cards)
        document.querySelectorAll('.rc-date-buddhist').forEach(el => {
            el.addEventListener('input', function () {
                const text = this.innerText.trim();
                document.querySelectorAll('.rc-date-buddhist').forEach(other => {
                    if (other !== el) {
                        other.innerText = text;
                    }
                });
                const lunarDisplay = document.getElementById('toolbarLunarDisplay');
                if (lunarDisplay) lunarDisplay.textContent = text;
            });
        });

        // 7. Direct In-Sheet Editing on .school-abbr-txt & .school-loc-txt (sync across cards and toolbar)
        document.querySelectorAll('.school-abbr-txt, .school-loc-txt').forEach(el => {
            el.addEventListener('input', function () {
                const text = this.innerText.trim();
                setSchoolPrefix(text);
            });
        });

        // 8. Check URL Search Params or LocalStorage on Page Load
        const urlParams = new URLSearchParams(window.location.search);
        const paramDate = urlParams.get('date') || urlParams.get('solar_date');
        const savedDate = localStorage.getItem(STORAGE_KEY_DATE);

        if (paramDate) {
            applyDateToReportCards(paramDate);
        } else if (savedDate) {
            applyDateToReportCards(savedDate);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initReportCardDateSync);
    } else {
        initReportCardDateSync();
    }

    window.ReportCardDateSync = {
        applyDate: applyDateToReportCards,
        setPrefix: setSchoolPrefix,
        init: initReportCardDateSync
    };
})();
