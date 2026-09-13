import os
import sys
import django
import subprocess

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from apps.accounts.khmer_lunar import calculate_khmer_lunar_details, get_khmer_lunar_date
from apps.academics.models import Classroom, AcademicYear
from apps.students.models import Student
from apps.examinations.views import classroom_report_cards_western_view, report_card_western_view

User = get_user_model()


def test_js_khmer_lunar_and_date_sync():
    print("\n--- 1. Testing JS KhmerLunar Engine & Date Parser in Node ---")
    node_script = """
    const fs = require('fs');
    const vm = require('vm');
    const window = {};
    const lunarContent = fs.readFileSync('static/js/khmer_lunar.js', 'utf8');
    vm.runInNewContext(lunarContent, { window, console, Math, Date, String, parseInt, isNaN });

    const tests = [
        { input: '2026-09-13', expDay: 13, expMonth: 9, expYear: 2026 },
        { input: '13/09/2026', expDay: 13, expMonth: 9, expYear: 2026 },
        { input: '13-09-2026', expDay: 13, expMonth: 9, expYear: 2026 },
        { input: '១៣/០៩/២០២៦', expDay: 13, expMonth: 9, expYear: 2026 },
        { input: '១៣-០៩-២០២៦', expDay: 13, expMonth: 9, expYear: 2026 },
        { input: 'ថ្ងៃទី១៣ ខែកញ្ញា ឆ្នាំ២០២៦', expDay: 13, expMonth: 9, expYear: 2026 },
        { input: 'វ.ហ.ស.ក.ក ថ្ងៃទី១៣ ខែកញ្ញា ឆ្នាំ២០២៦', expDay: 13, expMonth: 9, expYear: 2026 },
        { input: '13 កញ្ញា 2026', expDay: 13, expMonth: 9, expYear: 2026 },
        { input: '2026-10-15', expDay: 15, expMonth: 10, expYear: 2026 },
        { input: '15/10/2026', expDay: 15, expMonth: 10, expYear: 2026 }
    ];

    tests.forEach((t, i) => {
        const parsed = window.KhmerLunar.parseDate(t.input);
        if (parsed.getFullYear() !== t.expYear || (parsed.getMonth() + 1) !== t.expMonth || parsed.getDate() !== t.expDay) {
            console.error(`FAIL: ${t.input} expected ${t.expYear}-${t.expMonth}-${t.expDay}, got ${parsed.getFullYear()}-${parsed.getMonth()+1}-${parsed.getDate()}`);
            process.exit(1);
        }
    });

    const lDetails = window.KhmerLunar.getLunarDetails('2026-09-13');
    console.log('Lunar Details for 2026-09-13:', lDetails.fullString);
    if (!lDetails.fullString.includes('ភទ្របទ') || !lDetails.fullString.includes('មមី') || !lDetails.fullString.includes('២៥៧០')) {
        console.error('FAIL: Lunar details mismatch:', lDetails);
        process.exit(1);
    }

    const formattedSolar = window.KhmerLunar.formatSolarKhmer('2026-09-13', 'វ.ហ.ស.ក.ក');
    console.log('Formatted Solar:', formattedSolar);
    if (formattedSolar !== 'វ.ហ.ស.ក.ក ថ្ងៃទី១៣ ខែកញ្ញា ឆ្នាំ២០២៦') {
        console.error('FAIL: Formatted solar mismatch:', formattedSolar);
        process.exit(1);
    }

    console.log('All JS Node tests passed successfully!');
    """
    res = subprocess.run(['node', '-e', node_script], capture_output=True, text=True, encoding='utf-8')
    print(res.stdout)
    if res.returncode != 0:
        print(res.stderr)
        raise AssertionError("Node test failed")


def test_django_templates_and_views():
    print("\n--- 2. Testing Django Views & Report Card Templates ---")
    factory = RequestFactory()

    user = User.objects.filter(is_superuser=True).first()
    if not user:
        user = User.objects.first()

    student = Student.objects.filter(status='ACTIVE').first()
    if not student:
        print("No active student found for view testing, skipping view render check.")
        return

    classroom = student.classroom

    # 1. Test Single Student View with model=tr (MoEYS tr.pdf)
    req = factory.get(f'/examinations/report-card/{student.id}/?model=tr&date=2026-09-13')
    req.user = user
    resp = report_card_western_view(req, student.id)
    html = resp.content.decode('utf-8')

    assert 'toolbarSolarPicker' in html, "toolbarSolarPicker missing in report_card_moeys_tr.html"
    assert 'toolbarSolarInput' in html, "toolbarSolarInput missing in report_card_moeys_tr.html"
    assert 'toolbarLunarDisplay' in html, "toolbarLunarDisplay missing in report_card_moeys_tr.html"
    assert 'btnSetTodayDate' in html, "btnSetTodayDate missing in report_card_moeys_tr.html"
    assert 'btnResetDateDots' in html, "btnResetDateDots missing in report_card_moeys_tr.html"
    assert 'rc-date-buddhist' in html, "rc-date-buddhist missing in report_card_moeys_tr.html"
    assert 'rc-date-solar' in html, "rc-date-solar missing in report_card_moeys_tr.html"
    assert 'គំរូទី១' in html, "គំរូទី១ button missing in report_card_moeys_tr.html"
    assert 'គំរូទី២' in html, "គំរូទី២ button missing in report_card_moeys_tr.html"
    assert 'គំរូទី៣' in html, "គំរូទី៣ button missing in report_card_moeys_tr.html"
    print("  [PASS] report_card_moeys_tr.html correctly loaded with full Solar-to-Lunar date sync suite!")

    # 2. Test Transcript Model (transcript.pdf)
    req_tr = factory.get(f'/examinations/report-card/{student.id}/?model=transcript&date=2026-09-13')
    req_tr.user = user
    resp_tr = report_card_western_view(req_tr, student.id)
    html_tr = resp_tr.content.decode('utf-8')

    assert 'toolbarSolarPicker' in html_tr, "toolbarSolarPicker missing in report_card_transcript.html"
    assert 'rc-date-buddhist' in html_tr, "rc-date-buddhist missing in report_card_transcript.html"
    assert 'rc-date-solar' in html_tr, "rc-date-solar missing in report_card_transcript.html"
    assert 'report_card_date_sync.js' in html_tr, "report_card_date_sync.js missing in report_card_transcript.html"
    print("  [PASS] report_card_transcript.html correctly loaded with full Solar-to-Lunar date sync suite!")

    # 3. Test MoEYS Annual 8-col Model (report_card_moeys_annual.html)
    req_ann = factory.get(f'/examinations/report-card/{student.id}/?model=moeys&date=2026-09-13')
    req_ann.user = user
    resp_ann = report_card_western_view(req_ann, student.id)
    html_ann = resp_ann.content.decode('utf-8')

    assert '<title></title>' in html_ann, "Title must be empty to avoid browser print header"
    assert 'ព្រឹត្តិបត្រពិន្ទុប្រចាំឆ្នាំ (គំរូសាលារដ្ឋ) - ថ្នាក់' not in html_ann, "Old header title must be removed"
    assert 'លោក ផេង រិទ្ធីយ៉ា' not in html_ann, "Principal name 'លោក ផេង រិទ្ធីយ៉ា' must be removed"
    assert 'sig-person-name' not in html_ann.split('sig-box-left')[1].split('sig-box-right')[0], "Principal name block must be removed from left signature box"
    assert '@page' in html_ann and 'size: A4 portrait' in html_ann, "A4 portrait @page rule missing"
    assert 'margin: 0' in html_ann, "@page margin: 0 missing"
    assert 'toolbarSolarPicker' in html_ann, "toolbarSolarPicker missing in report_card_moeys_annual.html"
    assert 'rc-date-buddhist' in html_ann, "rc-date-buddhist missing in report_card_moeys_annual.html"
    from apps.accounts.models import SchoolProfile
    expected_short_name = SchoolProfile.get_settings().short_name
    assert expected_short_name in html, f"Expected {expected_short_name} in report_card_moeys_tr.html"
    assert expected_short_name in html_tr, f"Expected {expected_short_name} in report_card_transcript.html"
    assert expected_short_name in html_ann, f"Expected {expected_short_name} in report_card_moeys_annual.html"
    assert 'school-abbr-txt' in html_tr, "school-abbr-txt missing in report_card_transcript.html"
    assert 'school-abbr-txt' in html_ann, "school-abbr-txt missing in report_card_moeys_annual.html"
    assert 'ធ្វើនៅ' not in html_ann.split('rc-date-solar')[1].split('</div>')[0], "ធ្វើនៅ prefix must be removed from rc-date-solar"
    assert 'report_card_date_sync.js' in html_ann, "report_card_date_sync.js missing in report_card_moeys_annual.html"
    print("  [PASS] report_card_moeys_annual.html correctly loaded and meets all 5 requirements!")

    # 4. Test Batch Classroom Report Cards
    if classroom:
        req_batch = factory.get(f'/examinations/classroom/{classroom.id}/report-cards/?model=tr&date=2026-09-13')
        req_batch.user = user
        resp_batch = classroom_report_cards_western_view(req_batch, classroom.id)
        html_batch = resp_batch.content.decode('utf-8')
        assert 'toolbarSolarPicker' in html_batch, "Batch view toolbar missing solar picker"
        assert 'rc-date-buddhist' in html_batch, "Batch view missing rc-date-buddhist"
        print(f"  [PASS] Batch classroom report cards ({classroom.name}) loaded successfully!")


if __name__ == '__main__':
    test_js_khmer_lunar_and_date_sync()
    test_django_templates_and_views()
    print("\n🎉 ALL TESTS PASSED SUCCESSFULLY! (100%)\n")
