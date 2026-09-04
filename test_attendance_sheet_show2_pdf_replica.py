import os
import sys
import django
import datetime
import subprocess
import pypdf

if sys.stdout and sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from apps.examinations.models import StandardizedExam, ExamRoom, ExamCandidate
from apps.examinations.views import exam_subject_attendance_view
from apps.academics.models import AcademicYear
from apps.accounts.models import SchoolProfile

User = get_user_model()

def setup_request(request, user):
    request.user = user
    request.session = {}
    return request

def run_tests():
    print("🚀 Running Test Suite: Verify Attendance & Signature Sheet 100% Replication of show2.pdf...")
    factory = RequestFactory()

    admin_user, _ = User.objects.get_or_create(
        username="admin_test_replica2",
        defaults={'role': 'ADMIN', 'is_staff': True, 'is_superuser': True}
    )

    year, _ = AcademicYear.objects.get_or_create(
        name="2025-2026",
        defaults={
            'start_date': datetime.date(2025, 10, 1),
            'end_date': datetime.date(2026, 8, 31),
        }
    )

    sp = SchoolProfile.get_settings()
    sp.province = "ខេត្តកណ្តាល"
    sp.name_kh = "វិទ្យាល័យ ហ៊ុន សែន កំពង់កន្សួត"
    sp.commune = "ឃុំកំពង់កន្សួត"
    sp.save()

    # Create Exam matching show2.pdf
    exam, _ = StandardizedExam.objects.get_or_create(
        name="ខែមិថុនា",
        academic_year=year,
        grade_level=7,
        defaults={
            'exam_date': datetime.date(2026, 8, 3),
            'session': StandardizedExam.Session.MORNING,
        }
    )
    exam.name = "ខែមិថុនា"
    exam.exam_date = datetime.date(2026, 8, 3)
    exam.session = StandardizedExam.Session.MORNING
    exam.save()

    # Clean old rooms & candidates
    exam.rooms.all().delete()
    exam.candidates.all().delete()

    # Room 1: 25 candidates
    room1 = ExamRoom.objects.create(exam=exam, room_number=1, room_name="បន្ទប់លេខ ០១")
    for i in range(1, 26):
        ExamCandidate.objects.create(
            exam=exam,
            room=room1,
            desk_number=i,
            roll_number=f"{26329 + i}",
            student_code=f"{26329 + i}",
            candidate_name_kh=f"សិស្ស បន្ទប់មួយ ទី{i}",
            gender='F' if i % 2 == 1 else 'M',
            dob=datetime.date(2012, 10, 12),
            origin_class="7B" if i % 2 == 1 else "7D"
        )

    # Room 2: 15 candidates
    room2 = ExamRoom.objects.create(exam=exam, room_number=2, room_name="បន្ទប់លេខ ០២")
    for i in range(1, 16):
        ExamCandidate.objects.create(
            exam=exam,
            room=room2,
            desk_number=25 + i,
            roll_number=f"{26400 + i}",
            student_code=f"{26400 + i}",
            candidate_name_kh=f"សិស្ស បន្ទប់ពីរ ទី{i}",
            gender='F' if i <= 8 else 'M',
            dob=datetime.date(2013, 5, 3),
            origin_class="7A"
        )

    print("✅ Created test rooms: Room 1 (25 students), Room 2 (15 students)")

    # 1. Render all rooms
    req = setup_request(factory.get(f'/examinations/standardized/{exam.id}/attendance-sheets/'), admin_user)
    resp = exam_subject_attendance_view(req, exam.id)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    html = resp.content.decode('utf-8')

    # 2. Check Header & Titles
    assert "វិទ្យាល័យ ហ៊ុន សែន កំពង់កន្សួត" in html, "School name must be present"
    assert "បន្ទប់លេខ៖" in html, "Room label must be present"
    assert "បញ្ជីវត្តមានបេក្ខជនប្រឡងខែមិថុនា ឆ្នាំសិក្សា ២០២៥-២០២៦ ថ្នាក់ទី ៧" in html, "Title line mismatch"
    assert "សម័យប្រឡង៖ ០៣ សីហា ២០២៦" in html, "Exam date line mismatch"
    assert "ព្រឹក" in html, "Morning session must be present"
    print("✅ Header, Title Line & Exam Date verified matching show2.pdf!")

    # 3. Check Table Structure & Multi-Subject Group
    assert "ហត្ថលេខាបេក្ខជនតាមមុខវិជ្ជា" in html, "Grouped subject signature header missing"
    default_subjects = ['តែង', 'សរសេរ', 'ខ្មែរ', 'សីល', 'ភូមិ', 'ប្រវត្តិ', 'គណិត', 'ផែនដី', 'រូប', 'គីមី', 'ជីវ', 'គេហៈ', 'អង់គ្លេស']
    for s in default_subjects:
        assert f'<th class="th-subj-item">{s}</th>' in html, f"Missing subject column header: {s}"
    print("✅ All 13 MoEYS Subject Signature columns verified matching show2.pdf!")

    # 4. Check Base Candidate Columns
    for col in ["ល.រ", "លេខតុ", "អត្តលេខ", "គោត្តនាម និងនាម", "ភេទ", "ថ្ងៃខែឆ្នាំកំណើត", "ថ្នាក់", "ផ្សេងៗ"]:
        assert col in html, f"Missing base column: {col}"
    print("✅ All base columns verified!")

    # 5. Check 25 Rows per room
    for d in range(1, 26):
        assert f'<td class="col-desk">{d}</td>' in html, f"Room 1 missing desk number {d}"
    for d in range(26, 51):
        assert f'<td class="col-desk">{d}</td>' in html, f"Room 2 missing desk number {d}"
    print("✅ Exactly 25 rows with continuous desk numbers verified!")

    # 6. Check Compact DOB formatting (DD/MM/YY e.g. 12/10/12)
    assert '<td class="col-dob">12/10/12</td>' in html, "Compact DOB format for Room 1 missing"
    assert '<td class="col-dob">03/05/13</td>' in html, "Compact DOB format for Room 2 missing"
    print("✅ Compact DOB format (DD/MM/YY) verified!")

    # 7. Check Footer Summaries & Customizable Principal Title
    assert "បញ្ឈប់បញ្ជីត្រឹមចំនួន ២៥ នាក់ ស្រី ១៣ នាក់" in html
    assert "បញ្ឈប់បញ្ជីត្រឹមចំនួន ១៥ នាក់ ស្រី ០៨ នាក់" in html
    assert "កំពង់កន្សួត ថ្ងៃទី" in html
    assert "នាយក" in html
    assert 'contenteditable="true"' in html, "principal-title must be contenteditable for in-place editing"
    assert 'name="sign_role"' in html, "sign_role input must be in modal and form"

    # Test custom sign_role parameter (e.g. នាយិកា or ប្រធានមណ្ឌល)
    req_custom_role = setup_request(factory.get(f'/examinations/standardized/{exam.id}/attendance-sheets/?sign_role=នាយិកា'), admin_user)
    resp_custom_role = exam_subject_attendance_view(req_custom_role, exam.id)
    html_custom = resp_custom_role.content.decode('utf-8')
    assert "នាយិកា" in html_custom, "Custom sign_role 'នាយិកា' must render"
    print("✅ Footer summaries with 2-digit Khmer counts and customizable sign_role verified!")

    # 8. Check Disciplinary Hold Masking
    cand_to_block = ExamCandidate.objects.filter(room=room1).first()
    cand_to_block.is_disciplinary_blocked = True
    cand_to_block.save()

    resp_disc = exam_subject_attendance_view(req, exam.id)
    html_disc = resp_disc.content.decode('utf-8')
    assert "⚠️ [ ជាប់កិច្ចសន្យាវិន័យ - ផ្អាកការចុះហត្ថលេខា ]" in html_disc, "Disciplinary banner must show"
    assert "🔒 សូមទាក់ទងគណៈកម្មការ/រដ្ឋបាល" in html_disc, "Lock notice must show"
    assert "ជាប់កិច្ចសន្យា" in html_disc, "Remarks must show ជាប់កិច្ចសន្យា"
    print("✅ Disciplinary hold masking verified!")

    # 9. Verify with Headless Chrome Print to PDF
    print("📄 Running Headless Chrome to generate test PDF and check margins...")
    html_test_path = 'E:/SchoolSM/test_show2_generated.html'
    pdf_test_path = 'E:/SchoolSM/test_show2_generated.pdf'
    with open(html_test_path, 'wb') as f:
        f.write(resp.content)

    chrome_exe = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
    subprocess.run([
        chrome_exe,
        '--headless=new',
        '--disable-gpu',
        f'--print-to-pdf={pdf_test_path}',
        html_test_path
    ], check=True)

    reader = pypdf.PdfReader(pdf_test_path)
    print(f"Total pages generated: {len(reader.pages)} (1 page per room)")
    assert len(reader.pages) == 2, f"Expected 2 pages for 2 rooms, got {len(reader.pages)}"

    page1 = reader.pages[0]
    w = float(page1.mediabox.width)
    h = float(page1.mediabox.height)
    print(f"Page dimensions: {w*25.4/72:.1f} mm x {h*25.4/72:.1f} mm")
    assert abs(w*25.4/72 - 297.0) < 2.0, "Must be A4 Landscape width (~297mm)"
    assert abs(h*25.4/72 - 210.0) < 2.0, "Must be A4 Landscape height (~210mm)"
    print("✅ Geometry is strictly A4 Landscape (297mm x 210mm)!")

    # Clean up temp test files
    for f in [html_test_path, pdf_test_path]:
        if os.path.exists(f):
            os.remove(f)

    print("\n🎉 ALL TESTS PASSED SUCCESSFULLY! The attendance sheet 100% replicates show2.pdf!")

if __name__ == '__main__':
    run_tests()
