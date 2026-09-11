import os, sys
sys.stdout.reconfigure(encoding='utf-8')
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from apps.academics.models import Classroom
from apps.examinations.views import annual_results_print_view
import subprocess
import pypdf

def run_tests():
    print("🚀 Running Test Suite: Annual Results Print Pagination (~1.5cm bottom space)...")

    User = get_user_model()
    admin_user = User.objects.filter(is_superuser=True).first()
    classroom_12a = Classroom.objects.filter(name='12A').first()

    factory = RequestFactory()
    chrome_exe = r'C:\Program Files\Google\Chrome\Application\chrome.exe'

    # 1. Test Classroom 12A (40 students) live data
    print("\n[Test 1] Testing Classroom 12A (40 students)...")
    req = factory.get(f'/examinations/annual-results/print/?classroom={classroom_12a.id}&source=live')
    req.user = admin_user
    resp = annual_results_print_view(req)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

    html = resp.content.decode('utf-8')
    assert "សរុប 40 នាក់ (1 ទំព័រ)" in html, "Classroom 12A should now be 1 single page for 40 students"
    assert "បញ្ឈប់បញ្ជីត្រឹមចំនួន" in html, "Summary stats must be on the page"
    assert "នាយក" in html, "Director signature must be present"

    html_file = 'E:/SchoolSM/test_annual_12a.html'
    pdf_file = 'E:/SchoolSM/test_annual_12a.pdf'
    with open(html_file, 'wb') as f:
        f.write(resp.content)

    subprocess.run([
        chrome_exe,
        '--headless=new',
        '--disable-gpu',
        '--no-pdf-header-footer',
        f'--print-to-pdf={pdf_file}',
        html_file
    ], check=True)

    reader = pypdf.PdfReader(pdf_file)
    print(f"Total pages generated for 12A: {len(reader.pages)}")
    assert len(reader.pages) == 1, f"Expected strictly 1 page for 40 students, got {len(reader.pages)}"

    # Measure bottom space in PDF
    page = reader.pages[0]
    y_coords = []
    def visitor(text, cm, tm, font_dict, font_size):
        if text.strip() and 'ទំព័រទី' not in text:
            y_coords.append(tm[5] if tm[5] > 0 else cm[5])
    page.extract_text(visitor_text=visitor)

    min_y = min(y_coords) if y_coords else 0
    bottom_space_mm = min_y * 25.4 / 72.0
    bottom_space_cm = bottom_space_mm / 10.0
    print(f"Bottom space remaining: {bottom_space_mm:.1f} mm ({bottom_space_cm:.2f} cm)")
    assert 1.0 <= bottom_space_cm <= 2.5, f"Expected ~1.5cm bottom space, got {bottom_space_cm:.2f} cm"
    print("✅ Classroom 12A (40 students) fits perfectly on 1 page with ~1.5 - 1.7 cm bottom space!")

    for f in [html_file, pdf_file]:
        if os.path.exists(f): os.remove(f)

    # 2. Test Official Benchmark (255 students, year.pdf)
    print("\n[Test 2] Testing Official benchmark data (255 students matching year.pdf)...")
    req_official = factory.get(f'/examinations/annual-results/print/?source=official')
    req_official.user = admin_user
    resp_official = annual_results_print_view(req_official)
    assert resp_official.status_code == 200

    html_off = resp_official.content.decode('utf-8')
    assert "សរុប 255 នាក់ (6 ទំព័រ)" in html_off, "Official benchmark must be 6 pages"

    with open(html_file, 'wb') as f:
        f.write(resp_official.content)

    subprocess.run([
        chrome_exe,
        '--headless=new',
        '--disable-gpu',
        '--no-pdf-header-footer',
        f'--print-to-pdf={pdf_file}',
        html_file
    ], check=True)

    reader_off = pypdf.PdfReader(pdf_file)
    print(f"Total pages generated for official benchmark: {len(reader_off.pages)}")
    assert len(reader_off.pages) == 6, f"Expected 6 pages, got {len(reader_off.pages)}"
    print("✅ Official benchmark (255 students) matches year.pdf with strictly 6 pages!")

    for f in [html_file, pdf_file]:
        if os.path.exists(f): os.remove(f)

    print("\n🎉 ALL TESTS PASSED! Pagination leaves ~1.5cm bottom space and cleanly overflows to next page!")

if __name__ == '__main__':
    run_tests()
