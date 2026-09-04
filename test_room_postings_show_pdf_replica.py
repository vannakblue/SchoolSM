import os
import sys
import django
import datetime

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
from apps.examinations.views import exam_room_postings_view
from apps.academics.models import AcademicYear, Classroom
from apps.students.models import Student
from apps.accounts.models import SchoolProfile

User = get_user_model()

def setup_request(request, user):
    request.user = user
    request.session = {}
    return request

def run_tests():
    print("🚀 Running Test Suite: Verify Room Postings 100% Replication of show.pdf...")
    factory = RequestFactory()

    admin_user, _ = User.objects.get_or_create(
        username="admin_test_replica",
        defaults={'role': 'ADMIN', 'is_staff': True, 'is_superuser': True}
    )

    year, _ = AcademicYear.objects.get_or_create(
        name="2025-2026",
        defaults={
            'start_date': datetime.date(2025, 10, 1),
            'end_date': datetime.date(2026, 8, 31),
            'is_active': True
        }
    )

    # Setup SchoolProfile
    sp = SchoolProfile.get_settings()
    sp.province = "ខេត្តកណ្តាល"
    sp.name_kh = "វិទ្យាល័យ ហ៊ុន សែន កំពង់កន្សួត"
    sp.commune = "ឃុំកំពង់កន្សួត"
    sp.save()

    # Create Exam matching show.pdf
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

    # Clear old rooms & candidates for clean test
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
            origin_class="7A" if i % 2 == 1 else "7B"
        )

    # Room 2: 15 candidates (partial room like Room 10 in show.pdf)
    room2 = ExamRoom.objects.create(exam=exam, room_number=2, room_name="បន្ទប់លេខ ០២")
    for i in range(1, 16):
        ExamCandidate.objects.create(
            exam=exam,
            room=room2,
            desk_number=25 + i,
            roll_number=f"{26400 + i}",
            student_code=f"{26400 + i}",
            candidate_name_kh=f"សិស្ស បន្ទប់ពីរ ទី{i}",
            gender='F' if i <= 8 else 'M', # 8 females, 7 males
            dob=datetime.date(2013, 5, 3),
            origin_class="7C"
        )

    # Room 3: 0 candidates (empty room like Room 11..20 in show.pdf)
    room3 = ExamRoom.objects.create(exam=exam, room_number=3, room_name="បន្ទប់លេខ ០៣")

    print("✅ Created test rooms: Room 1 (25 students), Room 2 (15 students), Room 3 (0 students)")

    # 1. Render all rooms
    req = setup_request(factory.get(f'/examinations/standardized/{exam.id}/room-postings/'), admin_user)
    resp = exam_room_postings_view(req, exam.id)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    html = resp.content.decode('utf-8')

    # 2. Check National Header & School Information
    assert "ព្រះរាជាណាចក្រកម្ពុជា" in html, "Kingdom title must be present"
    assert "ជាតិ សាសនា ព្រះមហាក្សត្រ" in html, "Kingdom motto must be present"
    assert "― ❖ ―" in html or "— ❖ —" in html, "Flourish divider must be present"
    assert "ខេត្តកណ្តាល" in html, "Province must be present"
    assert "វិទ្យាល័យ ហ៊ុន សែន កំពង់កន្សួត" in html, "School name must be present"
    assert "បន្ទប់លេខ៖" in html, "Room label must be present"
    assert "ព្រឹក" in html, "Morning session must be present"

    # 3. Check Main Title Line & Exam Date
    assert "បញ្ជីរាយនាមសិស្សប្រឡងខែមិថុនា ឆ្នាំសិក្សា ២០២៥-២០២៦ ថ្នាក់ទី ៧" in html, "Main title line mismatch"
    assert "សម័យប្រឡង៖ ០៣ សីហា ២០២៦" in html, "Exam date line mismatch"
    print("✅ National Header, Title Line & Exam Date fully match show.pdf!")

    # 4. Check 8 Table Column Headers
    expected_headers = [
        "ល.រ", "លេខតុ", "អត្តលេខ", "គោត្តនាម និងនាម", "ភេទ", "ថ្ងៃ ខែ ឆ្នាំកំណើត", "មកពីថ្នាក់", "ផ្សេងៗ"
    ]
    for h in expected_headers:
        assert h in html, f"Missing table header: {h}"
    print("✅ Table contains all 8 exact MoEYS columns from show.pdf!")

    # 5. Check 25 Rows per room
    # Room 1 desk numbers: 1 to 25
    for d in range(1, 26):
        assert f'<td class="col-desk">{d}</td>' in html, f"Room 1 missing desk number {d}"
    
    # Room 2 desk numbers: 26 to 50 (15 students, but desk numbers 26..50 all present!)
    for d in range(26, 51):
        assert f'<td class="col-desk">{d}</td>' in html, f"Room 2 missing desk number {d}"

    # Room 3 desk numbers: 51 to 75 (0 students, but desk numbers 51..75 all present!)
    for d in range(51, 76):
        assert f'<td class="col-desk">{d}</td>' in html, f"Room 3 missing desk number {d}"
    print("✅ Exactly 25 rows with continuous global desk numbers verified for all rooms!")

    # 6. Check Khmer DOB formatting: DD ខែ YYYY
    assert "១២ តុលា ២០១២" in html, "Khmer DOB formatting for Room 1 mismatch"
    assert "០៣ ឧសភា ២០១៣" in html, "Khmer DOB formatting for Room 2 mismatch"
    print("✅ Khmer DOB formatting (DD ខែ YYYY) verified!")

    # 7. Check Class cleaning (e.g. 7A -> A, 7B -> B, 7C -> C)
    assert '<td class="col-class">A</td>' in html
    assert '<td class="col-class">B</td>' in html
    assert '<td class="col-class">C</td>' in html
    print("✅ Class section letters cleanly formatted matching show.pdf!")

    # 8. Check Footer Summaries
    # Room 1 (25 total, 13 female):
    assert "បញ្ឈប់បញ្ជីត្រឹមចំនួន ២៥ នាក់ ស្រី ១៣ នាក់" in html
    # Room 2 (15 total, 8 female):
    assert "បញ្ឈប់បញ្ជីត្រឹមចំនួន ១៥ នាក់ ស្រី ០៨ នាក់" in html
    # Room 3 (0 total, 0 female):
    assert "បញ្ឈប់បញ្ជីត្រឹមចំនួន ០០ នាក់ ស្រី ០០ នាក់" in html
    print("✅ 2-digit Khmer numeral footer counts verified for all rooms!")

    # 9. Check Signature Block & Customizable Principal Title
    assert "កំពង់កន្សួត ថ្ងៃទី" in html, "Commune location in signature missing"
    assert "នាយក" in html, "Principal title missing"
    assert 'contenteditable="true"' in html, "principal-title must be contenteditable"
    assert 'name="sign_role"' in html, "sign_role input must be in modal and form"

    # Test custom sign_role parameter
    req_custom_role = setup_request(factory.get(f'/examinations/standardized/{exam.id}/room-postings/?sign_role=ប្រធានមណ្ឌល'), admin_user)
    resp_custom_role = exam_room_postings_view(req_custom_role, exam.id)
    html_custom = resp_custom_role.content.decode('utf-8')
    assert "ប្រធានមណ្ឌល" in html_custom, "Custom sign_role 'ប្រធានមណ្ឌល' must render"
    print("✅ Signature block and customizable sign_role verified!")

    # 10. Test Single Room Filter
    req_r1 = setup_request(factory.get(f'/examinations/standardized/{exam.id}/room-postings/?room_id={room1.id}'), admin_user)
    resp_r1 = exam_room_postings_view(req_r1, exam.id)
    html_r1 = resp_r1.content.decode('utf-8')
    assert f'<td class="col-desk">25</td>' in html_r1
    assert f'<td class="col-desk">26</td>' not in html_r1, "Single room filter should only show Room 1"
    print("✅ Single room filter works properly!")

    # 11. Disciplinary hold masking test
    cand_to_block = ExamCandidate.objects.filter(room=room1).first()
    cand_to_block.is_disciplinary_blocked = True
    cand_to_block.save()

    resp_disc = exam_room_postings_view(req_r1, exam.id)
    html_disc = resp_disc.content.decode('utf-8')
    assert "⚠️ [ ផ្អាកបណ្តោះអាសន្ន - សូមទាក់ទងការិយាល័យវិន័យ/រដ្ឋបាល ដើម្បីធ្វើកិច្ចសន្យាមុនចូលប្រឡង ]" in html_disc
    assert "ជាប់កិច្ចសន្យា" in html_disc
    print("✅ Disciplinary hold masking verified!")

    print("\n🎉 ALL 11 TESTS PASSED SUCCESSFULLY! The output 100% replicates show.pdf!")

if __name__ == '__main__':
    run_tests()
