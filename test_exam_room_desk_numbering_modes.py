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
from apps.academics.models import AcademicYear, GradeLevelRule, Subject
from apps.examinations.models import StandardizedExam, ExamRoom, ExamCandidate, ExamSubject

User = get_user_model()

def test_numbering_modes():
    print("================================================================================")
    print("TEST: STANDARDIZED EXAM ROOM & DESK NUMBERING MODES (RESET VS CONTINUOUS SHIFT)")
    print("================================================================================")

    # 1. Setup Admin & Client
    admin_user, _ = User.objects.get_or_create(username='admin_test', defaults={'role': 'ADMIN', 'is_staff': True, 'is_superuser': True})
    admin_user.role = 'ADMIN'
    admin_user.save()

    client = Client()
    client.force_login(admin_user)

    ay, _ = AcademicYear.objects.get_or_create(
        name='2026-2027-TEST-NUMBERING',
        defaults={
            'start_date': datetime.date(2026, 9, 1),
            'end_date': datetime.date(2027, 7, 31),
            'is_current': False
        }
    )
    StandardizedExam.objects.filter(academic_year=ay).delete()

    # 2. Create Morning Exams (Grade 7 & Grade 8) and Afternoon Exams (Grade 11 & Grade 12)
    today = datetime.date(2026, 9, 15)
    exam_g7 = StandardizedExam.objects.create(
        name='តេស្តលេខតុ ថ្នាក់ទី ៧',
        academic_year=ay,
        grade_level=7,
        session='MORNING',
        exam_date=today,
        candidates_per_room=25
    )
    exam_g8 = StandardizedExam.objects.create(
        name='តេស្តលេខតុ ថ្នាក់ទី ៨',
        academic_year=ay,
        grade_level=8,
        session='MORNING',
        exam_date=today,
        candidates_per_room=25
    )
    exam_g11 = StandardizedExam.objects.create(
        name='តេស្តលេខតុ ថ្នាក់ទី ១១',
        academic_year=ay,
        grade_level=11,
        session='AFTERNOON',
        exam_date=today,
        candidates_per_room=25
    )
    exam_g12 = StandardizedExam.objects.create(
        name='តេស្តលេខតុ ថ្នាក់ទី ១២',
        academic_year=ay,
        grade_level=12,
        session='AFTERNOON',
        exam_date=today,
        candidates_per_room=25
    )

    # Add 50 candidates to each exam
    for ex in [exam_g7, exam_g8, exam_g11, exam_g12]:
        for i in range(1, 51):
            ExamCandidate.objects.create(
                exam=ex,
                candidate_name_kh=f"សិស្សទី {i} ថ្នាក់ {ex.grade_level}",
                gender="M" if i % 2 == 0 else "F"
            )

    print("--- 1. Testing RESET_PER_GRADE (រាប់ចាប់ពីលេខ ១ សម្រាប់កម្រិតថ្នាក់នីមួយៗ) ---")
    # Generate rooms for G7 with RESET_PER_GRADE
    res = client.post(f'/examinations/standardized/{exam_g7.id}/generate-rooms/', {'numbering_mode': 'RESET_PER_GRADE'})
    assert res.status_code == 302
    g7_rooms = list(exam_g7.rooms.order_by('room_number'))
    assert len(g7_rooms) == 2
    assert g7_rooms[0].room_number == 1 and g7_rooms[1].room_number == 2
    g7_cands = list(exam_g7.candidates.order_by('roll_number'))
    assert g7_cands[0].roll_number == "001" and g7_cands[0].desk_number == 1
    assert g7_cands[49].roll_number == "050" and g7_cands[49].desk_number == 25
    print("✅ Grade 7 (Morning): Rooms 01-02, Roll 001-050 [RESET_PER_GRADE PASSED]")

    # Generate rooms for G8 with RESET_PER_GRADE
    res = client.post(f'/examinations/standardized/{exam_g8.id}/generate-rooms/', {'numbering_mode': 'RESET_PER_GRADE'})
    assert res.status_code == 302
    g8_rooms = list(exam_g8.rooms.order_by('room_number'))
    assert len(g8_rooms) == 2
    assert g8_rooms[0].room_number == 1 and g8_rooms[1].room_number == 2
    g8_cands = list(exam_g8.candidates.order_by('roll_number'))
    assert g8_cands[0].roll_number == "001" and g8_cands[0].desk_number == 1
    assert g8_cands[49].roll_number == "050" and g8_cands[49].desk_number == 25
    print("✅ Grade 8 (Morning): Rooms 01-02, Roll 001-050 [RESET_PER_GRADE PASSED]")

    print("\n--- 2. Testing CONTINUOUS_IN_SHIFT (រាប់បន្តគ្នាតាមវេនប្រឡង) ---")
    # Regenerate G8 with CONTINUOUS_IN_SHIFT (should continue after G7: Rooms 03-04, Roll 051-100)
    res = client.post(f'/examinations/standardized/{exam_g8.id}/generate-rooms/', {'numbering_mode': 'CONTINUOUS_IN_SHIFT'})
    assert res.status_code == 302
    g8_rooms = list(exam_g8.rooms.order_by('room_number'))
    assert len(g8_rooms) == 2
    assert g8_rooms[0].room_number == 3 and g8_rooms[1].room_number == 4
    g8_cands = list(exam_g8.candidates.order_by('roll_number'))
    assert g8_cands[0].roll_number == "051" and g8_cands[0].desk_number == 1
    assert g8_cands[49].roll_number == "100" and g8_cands[49].desk_number == 25
    print(f"✅ Grade 8 (Morning Shift Continuation): Rooms {g8_rooms[0].room_number:02d}-{g8_rooms[1].room_number:02d}, Roll {g8_cands[0].roll_number}-{g8_cands[49].roll_number} [OK]")

    # Generate G11 (Afternoon shift starting)
    res = client.post(f'/examinations/standardized/{exam_g11.id}/generate-rooms/', {'numbering_mode': 'CONTINUOUS_IN_SHIFT'})
    assert res.status_code == 302
    g11_rooms = list(exam_g11.rooms.order_by('room_number'))
    assert len(g11_rooms) == 2
    assert g11_rooms[0].room_number == 1 and g11_rooms[1].room_number == 2
    g11_cands = list(exam_g11.candidates.order_by('roll_number'))
    assert g11_cands[0].roll_number == "001" and g11_cands[49].roll_number == "050"
    print(f"✅ Grade 11 (Afternoon Shift Start): Rooms {g11_rooms[0].room_number:02d}-{g11_rooms[1].room_number:02d}, Roll {g11_cands[0].roll_number}-{g11_cands[49].roll_number} [OK]")

    # Generate G12 (Afternoon shift continuation)
    res = client.post(f'/examinations/standardized/{exam_g12.id}/generate-rooms/', {'numbering_mode': 'CONTINUOUS_IN_SHIFT'})
    assert res.status_code == 302
    g12_rooms = list(exam_g12.rooms.order_by('room_number'))
    assert len(g12_rooms) == 2
    assert g12_rooms[0].room_number == 3 and g12_rooms[1].room_number == 4
    g12_cands = list(exam_g12.candidates.order_by('roll_number'))
    assert g12_cands[0].roll_number == "051" and g12_cands[49].roll_number == "100"
    print(f"✅ Grade 12 (Afternoon Shift Continuation): Rooms {g12_rooms[0].room_number:02d}-{g12_rooms[1].room_number:02d}, Roll {g12_cands[0].roll_number}-{g12_cands[49].roll_number} [OK]")

    print("\n--- 3. Testing CUSTOM Starting Numbers ---")
    res = client.post(f'/examinations/standardized/{exam_g7.id}/generate-rooms/', {
        'numbering_mode': 'CUSTOM',
        'start_room_number': '10',
        'start_roll_number': '500'
    })
    assert res.status_code == 302
    g7_custom_rooms = list(exam_g7.rooms.order_by('room_number'))
    assert g7_custom_rooms[0].room_number == 10 and g7_custom_rooms[1].room_number == 11
    g7_custom_cands = list(exam_g7.candidates.order_by('roll_number'))
    assert g7_custom_cands[0].roll_number == "500" and g7_custom_cands[49].roll_number == "549"
    print("✅ Custom start: Rooms 10-11, Roll 500-549 [CUSTOM MODE PASSED]")

    print("\n--- 4. Testing BATCH AUTO-GENERATE ROOMS (1-Click for All Exams) ---")
    res = client.post('/examinations/standardized/batch-generate-rooms/', {
        'academic_year': str(ay.id),
        'scope': 'ALL_GRADES',
        'numbering_mode': 'CONTINUOUS_IN_SHIFT',
        'candidates_per_room': '25'
    })
    assert res.status_code == 302

    # Check G7 & G8 (Morning)
    g7_rooms = list(exam_g7.rooms.order_by('room_number'))
    g8_rooms = list(exam_g8.rooms.order_by('room_number'))
    assert g7_rooms[0].room_number == 1 and g7_rooms[1].room_number == 2
    assert g8_rooms[0].room_number == 3 and g8_rooms[1].room_number == 4

    # Check G11 & G12 (Afternoon)
    g11_rooms = list(exam_g11.rooms.order_by('room_number'))
    g12_rooms = list(exam_g12.rooms.order_by('room_number'))
    assert g11_rooms[0].room_number == 1 and g11_rooms[1].room_number == 2
    assert g12_rooms[0].room_number == 3 and g12_rooms[1].room_number == 4

    print("✅ Batch Generation with CONTINUOUS_IN_SHIFT correctly processed all exams across shifts!")

    # Cleanup
    StandardizedExam.objects.filter(name__icontains='តេស្តលេខតុ').delete()
    print("\n🎉 ALL ROOM & DESK NUMBERING MODE TESTS PASSED 100%!")

if __name__ == '__main__':
    test_numbering_modes()
