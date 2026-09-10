import os
import sys
import django

sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import RequestFactory
from django.urls import reverse
from apps.students.models import Student
from apps.students.views import student_id_card, batch_student_id_cards
from apps.accounts.models import User

def test_student_card_replica():
    print("=== Testing Student ID Card Replica ===")

    # 1. URL tests
    url_single = reverse('student_id_card', args=[1])
    url_batch = reverse('batch_student_id_cards')
    print(f"  [OK] Single card URL: {url_single}")
    print(f"  [OK] Batch cards URL: {url_batch}")

    # 2. Get or create test student
    student = Student.objects.first()
    if not student:
        print("  [SKIP] No student found in database.")
        return

    print(f"  Testing with student ID {student.id}: {student.khmer_name}")

    factory = RequestFactory()
    admin_user = User.objects.filter(is_superuser=True).first() or User.objects.first()

    # 3. Test 4_grid mode
    req_grid = factory.get(f"{url_single}?mode=4_grid")
    req_grid.user = admin_user
    resp_grid = student_id_card(req_grid, pk=student.pk)
    assert resp_grid.status_code == 200, f"Expected 200, got {resp_grid.status_code}"
    content_grid = resp_grid.content.decode('utf-8')

    required_keywords = [
        "ព្រះរាជាណាចក្រកម្ពុជា",
        "ជាតិ  សាសនា  ព្រះមហាក្សត្រ",
        "មន្ទីរអប់រំ យុវជន និងកីឡា",
        "ប័ណ្ណសម្គាល់ខ្លួនសិស្ស",
        "គោត្តនាម នាម:",
        "ថ្ងៃខែឆ្នាំកំណើត:",
        "ទីកន្លែងកំណើត:",
        "ឪពុកឈ្មោះ:",
        "ម្តាយឈ្មោះ:",
        "ជាសិស្សរៀនថ្នាក់ទី:",
        "នាយក",
        "moeys-id-card",
        "a4-sheet",
        "Tacteing",
        "card-tacteing-display",
        "card-lunar-display",
        "card-solar-display",
        "ថ្ងៃចន្ទ ២កើត ខែជេស្ឋ ឆ្នាំម្សាញ់ សំរឹទ្ធិស័ក ព.ស. ២៥៧០",
        "កណ្ដាល ថ្ងៃទី ១៨ ខែ ឧសភា ឆ្នាំ ២០២៦",
    ]

    for kw in required_keywords:
        assert kw in content_grid, f"Missing keyword: '{kw}'"
        print(f"  [OK] Keyword present: '{kw}'")

    # Verify 'Department of Examination Affairs' is completely deleted per Image 5
    assert "Department of Examination Affairs" not in content_grid, "'Department of Examination Affairs' should be deleted"
    print("  [OK] 'Department of Examination Affairs' was deleted successfully.")

    # Verify Watermark elements & controls
    watermark_checks = [
        "btnWatermarkMoeys",
        "inputWatermarkFile",
        "rangeWatermarkOpacity",
        "rangeWatermarkSize",
        "labelWatermarkSize",
        "btnWatermarkSizeInc",
        "btnWatermarkSizeDec",
        "moeys-watermark-svg",
        "user-custom-watermark-img",
    ]
    for w_elem in watermark_checks:
        assert w_elem in content_grid, f"Missing watermark element: '{w_elem}'"
        print(f"  [OK] Watermark element present: '{w_elem}'")

    # Verify font switcher and "អត្តលេខ:" label
    font_id_checks = [
        "អត្តលេខ:",
        "card-id-label-display",
        "selectCardFont",
        "Khmer OS Siemreap",
        "inputIdLabel",
        "Khmer OS Muol Light",
        "KhmerOSmuollight.ttf",
        "--card-var-font",
        "selectVarFont",
        "btnDateFontDec",
        "btnDateFontInc",
        "labelDateFontSize",
        "--date-font-size",
        "--date-font-family",
        "selectDateFont",
    ]
    for check_item in font_id_checks:
        assert check_item in content_grid, f"Missing font/ID item: '{check_item}'"
        print(f"  [OK] Font/ID label check present: '{check_item}'")

    # 4. Test batch cards view
    req_batch = factory.get(url_batch)
    req_batch.user = admin_user
    resp_batch = batch_student_id_cards(req_batch)
    assert resp_batch.status_code == 200, f"Expected 200, got {resp_batch.status_code}"
    print("  [OK] Batch cards view returned 200 OK.")

    # 5. Verify no duplicate "ថ្នាក់ ថ្នាក់ទី"
    assert "ថ្នាក់ ថ្នាក់ទី" not in content_grid, "Found duplicate 'ថ្នាក់ ថ្នាក់ទី' in single card grid!"
    assert "ថ្នាក់ ថ្នាក់ទី" not in resp_batch.content.decode('utf-8'), "Found duplicate 'ថ្នាក់ ថ្នាក់ទី' in batch cards!"
    print("  [OK] Verified NO duplicate 'ថ្នាក់ ថ្នាក់ទី' in single or batch card views.")

    print("\n[ALL STUDENT ID CARD REPLICA TESTS PASSED SUCCESSFULLY!]")

if __name__ == '__main__':
    test_student_card_replica()
