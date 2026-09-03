import os
import sys
import django
import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from apps.academics.models import AcademicYear
from apps.examinations.models import StandardizedExam, ExamRoom, ExamCandidate

User = get_user_model()

def test_session_scoped_desk_numbering():
    print("================================================================================")
    print("TEST: SESSION-SCOPED ROOM ALLOCATION & DESK NUMBERING (តាមសម័យប្រឡងនីមួយៗ)")
    print("================================================================================")

    # 1. Setup Admin & Client
    admin_user, _ = User.objects.get_or_create(
        username='admin_session_test',
        defaults={'role': 'ADMIN', 'is_staff': True, 'is_superuser': True}
    )
    admin_user.role = 'ADMIN'
    admin_user.save()

    client = Client()
    client.force_login(admin_user)

    ay, _ = AcademicYear.objects.get_or_create(
        name='2026-2027-SESSION-ISOLATION-TEST',
        defaults={
            'start_date': datetime.date(2026, 9, 1),
            'end_date': datetime.date(2027, 7, 31),
            'is_current': False
        }
    )
    StandardizedExam.objects.filter(academic_year=ay).delete()

    # 2. Create Session 1 (October Exam Session: G7, G8 Morning & G11 Afternoon)
    date_oct = datetime.date(2026, 10, 15)
    s1_g7 = StandardizedExam.objects.create(
        name='សម័យប្រឡងតេស្តស្តង់ដាលើកទី១ ថ្នាក់ទី ៧',
        academic_year=ay,
        grade_level=7,
        session='MORNING',
        exam_date=date_oct,
        candidates_per_room=25
    )
    s1_g8 = StandardizedExam.objects.create(
        name='សម័យប្រឡងតេស្តស្តង់ដាលើកទី១ ថ្នាក់ទី ៨',
        academic_year=ay,
        grade_level=8,
        session='MORNING',
        exam_date=date_oct,
        candidates_per_room=25
    )
    s1_g11 = StandardizedExam.objects.create(
        name='សម័យប្រឡងតេស្តស្តង់ដាលើកទី១ ថ្នាក់ទី ១១',
        academic_year=ay,
        grade_level=11,
        session='AFTERNOON',
        exam_date=date_oct,
        candidates_per_room=25
    )

    # Populate 50 candidates in each exam of Session 1
    for ex in [s1_g7, s1_g8, s1_g11]:
        for i in range(1, 51):
            ExamCandidate.objects.create(
                exam=ex,
                candidate_name_kh=f"បេក្ខជន {ex.grade_level} លេខ {i:02d}",
                gender="M" if i % 2 == 0 else "F",
                origin_class=f"{ex.grade_level}A1" if i <= 25 else f"{ex.grade_level}A2"
            )

    # 3. Create Session 2 (December Exam Session: G7, G8 Morning & G11 Afternoon)
    date_dec = datetime.date(2026, 12, 20)
    s2_g7 = StandardizedExam.objects.create(
        name='សម័យប្រឡងតេស្តស្តង់ដាលើកទី២ ថ្នាក់ទី ៧',
        academic_year=ay,
        grade_level=7,
        session='MORNING',
        exam_date=date_dec,
        candidates_per_room=25
    )
    s2_g8 = StandardizedExam.objects.create(
        name='សម័យប្រឡងតេស្តស្តង់ដាលើកទី២ ថ្នាក់ទី ៨',
        academic_year=ay,
        grade_level=8,
        session='MORNING',
        exam_date=date_dec,
        candidates_per_room=25
    )
    s2_g11 = StandardizedExam.objects.create(
        name='សម័យប្រឡងតេស្តស្តង់ដាលើកទី២ ថ្នាក់ទី ១១',
        academic_year=ay,
        grade_level=11,
        session='AFTERNOON',
        exam_date=date_dec,
        candidates_per_room=25
    )

    # Populate 50 candidates in each exam of Session 2 with Khmer alphabetical names
    names_g7 = ["កែវ ចិន្តា", "កុសល វិបុល", "ខៀវ សារ៉ាត", "គង់ ពិសី", "ឃុត សារឿន"] + [f"សិស្ស ក {i}" for i in range(6, 51)]
    for i, name in enumerate(names_g7, 1):
        ExamCandidate.objects.create(
            exam=s2_g7,
            candidate_name_kh=name,
            gender="M" if i % 2 == 0 else "F",
            origin_class=f"7A1" if i <= 25 else f"7A2",
            student_code=f"STU-7-{i:03d}"
        )

    for ex in [s2_g8, s2_g11]:
        for i in range(1, 51):
            ExamCandidate.objects.create(
                exam=ex,
                candidate_name_kh=f"បេក្ខជន វគ្គ២ {ex.grade_level} លេខ {i:02d}",
                gender="M" if i % 2 == 0 else "F",
                origin_class=f"{ex.grade_level}A1" if i <= 25 else f"{ex.grade_level}A2",
                student_code=f"STU-{ex.grade_level}-{i:03d}"
            )

    print("\n--- 1. Testing Session 1 Batch Room Generation ---")
    s1_key = f"{ay.id}_{str(date_oct)}_សម័យប្រឡងតេស្តស្តង់ដាលើកទី១"
    res1 = client.post('/examinations/standardized/batch-generate-rooms/', {
        'academic_year': str(ay.id),
        'session_key': s1_key,
        'scope': 'ALL_GRADES',
        'numbering_mode': 'CONTINUOUS_IN_SHIFT',
        'candidates_per_room': '25',
        'candidate_order': 'ALPHABETICAL'
    })
    assert res1.status_code == 302

    # Check Session 1 rooms
    assert s1_g7.rooms.count() == 2
    assert s1_g8.rooms.count() == 2
    assert s1_g11.rooms.count() == 2
    # S1 Morning: G7 (Rooms 01-02), G8 (Rooms 03-04)
    s1_g7_rooms = list(s1_g7.rooms.order_by('room_number'))
    s1_g8_rooms = list(s1_g8.rooms.order_by('room_number'))
    assert s1_g7_rooms[0].room_number == 1 and s1_g7_rooms[1].room_number == 2
    assert s1_g8_rooms[0].room_number == 3 and s1_g8_rooms[1].room_number == 4
    # S1 Afternoon: G11 (Rooms 01-02)
    s1_g11_rooms = list(s1_g11.rooms.order_by('room_number'))
    assert s1_g11_rooms[0].room_number == 1 and s1_g11_rooms[1].room_number == 2
    print("✅ Session 1 partitioned correctly: G7 (Rooms 01-02), G8 (Rooms 03-04), G11 (Rooms 01-02)!")

    print("\n--- 2. Testing Session 2 Batch Room Generation (Strict Isolation from Session 1) ---")
    s2_key = f"{ay.id}_{str(date_dec)}_សម័យប្រឡងតេស្តស្តង់ដាលើកទី២"
    res2 = client.post('/examinations/standardized/batch-generate-rooms/', {
        'academic_year': str(ay.id),
        'session_key': s2_key,
        'scope': 'ALL_GRADES',
        'numbering_mode': 'CONTINUOUS_IN_SHIFT',
        'candidates_per_room': '25',
        'candidate_order': 'ALPHABETICAL'
    })
    assert res2.status_code == 302

    # Check Session 2 rooms: MUST START FROM ROOM 01 in Morning and ROOM 01 in Afternoon, NOT CONTINUE FROM SESSION 1!
    s2_g7_rooms = list(s2_g7.rooms.order_by('room_number'))
    s2_g8_rooms = list(s2_g8.rooms.order_by('room_number'))
    s2_g11_rooms = list(s2_g11.rooms.order_by('room_number'))

    assert len(s2_g7_rooms) == 2
    assert s2_g7_rooms[0].room_number == 1 and s2_g7_rooms[1].room_number == 2
    assert len(s2_g8_rooms) == 2
    assert s2_g8_rooms[0].room_number == 3 and s2_g8_rooms[1].room_number == 4
    assert len(s2_g11_rooms) == 2
    assert s2_g11_rooms[0].room_number == 1 and s2_g11_rooms[1].room_number == 2
    print("✅ Session 2 correctly starts at Room 01 (Morning) and Room 01 (Afternoon), 100% isolated from Session 1!")

    print("\n--- 3. Testing Desk Number Assignment (1 to 25 per Room) & Candidate Ordering ---")
    room_01_candidates = list(s2_g7.candidates.filter(room=s2_g7_rooms[0]).order_by('desk_number'))
    assert len(room_01_candidates) == 25
    for idx, cand in enumerate(room_01_candidates, 1):
        assert cand.desk_number == idx, f"Expected desk {idx}, got {cand.desk_number}"
    print(f"✅ Desk numbers 01 to 25 verified in {s2_g7_rooms[0].room_name}!")

    # Check that candidate ordering worked (First candidate is 'កុសល វិបុល' or 'កែវ ចិន្តា')
    assert room_01_candidates[0].candidate_name_kh in ["កុសល វិបុល", "កែវ ចិន្តា"]
    print(f"✅ Candidate alphabetical sorting passed (First desk: {room_01_candidates[0].candidate_name_kh})!")

    print("\n--- 4. Testing Single Grade CONTINUOUS_IN_SHIFT within Session 2 ---")
    # Regenerate S2 G8 alone via single exam endpoint
    res_single = client.post(f'/examinations/standardized/{s2_g8.id}/generate-rooms/', {
        'numbering_mode': 'CONTINUOUS_IN_SHIFT',
        'candidates_per_room': '25',
        'candidate_order': 'ALPHABETICAL'
    })
    assert res_single.status_code == 302
    s2_g8_rooms = list(s2_g8.rooms.order_by('room_number'))
    assert s2_g8_rooms[0].room_number == 3 and s2_g8_rooms[1].room_number == 4
    s2_g8_cands = list(s2_g8.candidates.order_by('roll_number'))
    assert s2_g8_cands[0].roll_number == "051" and s2_g8_cands[49].roll_number == "100"
    print("✅ Single exam CONTINUOUS_IN_SHIFT correctly references prior grades within Session 2 only (Rooms 03-04, Roll 051-100)!")

    # Cleanup test data
    StandardizedExam.objects.filter(academic_year=ay).delete()
    ay.delete()
    print("\n🎉 ALL SESSION-SCOPED ROOM & DESK NUMBERING TESTS PASSED 100%!")

if __name__ == '__main__':
    test_session_scoped_desk_numbering()
