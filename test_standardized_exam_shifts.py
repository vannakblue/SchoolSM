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

def test_standardized_exam_shift_assignments():
    print("=== STARTING STANDARDIZED EXAM MULTI-GRADE SHIFT TEST SUITE ===")

    # 1. Setup Admin User & Client
    admin_user, _ = User.objects.get_or_create(username='admin_test', defaults={'role': 'ADMIN', 'is_staff': True, 'is_superuser': True})
    admin_user.role = 'ADMIN'
    admin_user.set_password('Admin@1234')
    admin_user.save()

    client = Client()
    client.force_login(admin_user)

    # 2. Setup Academic Year
    ay, _ = AcademicYear.objects.get_or_create(name='2026-2027', defaults={'is_active': True})
    ay.is_active = True
    ay.save()

    # Clean up previous test exams if any
    StandardizedExam.objects.filter(name__icontains='តេស្តស្តង់ដារវេន').delete()

    # 3. Simulate POST to standardized_exam_create with Grades 7..10 (MORNING) and 11..12 (AFTERNOON)
    post_data = {
        'name': 'តេស្តស្តង់ដារវេនឆមាសទី១',
        'academic_year': str(ay.id),
        'track': 'ALL',
        'session': 'MORNING',
        'exam_date': '2026-09-15',
        'candidates_per_room': '25',
        'description': 'ការប្រឡងតេស្តស្តង់ដារៀបចំតាមវេនព្រឹក-រសៀល',
        'is_published': 'on',
        'selected_grades': ['7', '8', '9', '10', '11', '12'],
        'grade_session_7': 'MORNING',
        'grade_session_8': 'MORNING',
        'grade_session_9': 'MORNING',
        'grade_session_10': 'MORNING',
        'grade_session_11': 'AFTERNOON',
        'grade_session_12': 'AFTERNOON',
    }

    response = client.post('/examinations/standardized/create/', post_data, follow=True)
    assert response.status_code == 200
    print("1. [PASS] POST /examinations/standardized/create/ multi-grade batch succeeded.")

    # 4. Verify that 6 StandardizedExam records were created with exact shift assignments
    exams = list(StandardizedExam.objects.filter(name__icontains='តេស្តស្តង់ដារវេន').order_by('grade_level'))
    assert len(exams) == 6
    print(f"2. [PASS] Created {len(exams)} StandardizedExam instances across grades 7-12.")

    for ex in exams:
        if ex.grade_level in [7, 8, 9, 10]:
            assert ex.session == 'MORNING', f"Grade {ex.grade_level} expected MORNING, got {ex.session}"
            print(f"   -> Grade {ex.grade_level}: {ex.get_session_display()} [OK - Morning]")
        else:
            assert ex.session == 'AFTERNOON', f"Grade {ex.grade_level} expected AFTERNOON, got {ex.session}"
            print(f"   -> Grade {ex.grade_level}: {ex.get_session_display()} [OK - Afternoon]")

    # 5. Verify ExamSubject session inheritance
    morning_exam = exams[0]  # Grade 7
    afternoon_exam = exams[5] # Grade 12

    assert morning_exam.exam_subjects.exists()
    assert afternoon_exam.exam_subjects.exists()
    assert morning_exam.exam_subjects.first().session == 'MORNING'
    assert afternoon_exam.exam_subjects.first().session == 'AFTERNOON'
    print("3. [PASS] ExamSubject sessions properly inherited from exam shifts.")

    # 6. Test Room Generation and Room Postings Sheet (បញ្ជីបិទផ្សាយតាមបន្ទប់)
    # Create sample room and candidate for testing rendering
    room_m = ExamRoom.objects.create(exam=morning_exam, room_number=1, room_name="បន្ទប់លេខ ០១")
    cand_m = ExamCandidate.objects.create(
        exam=morning_exam,
        room=room_m,
        roll_number="001",
        desk_number=1,
        candidate_name_kh="សុខ ចិន្តា",
        gender="F"
    )

    room_a = ExamRoom.objects.create(exam=afternoon_exam, room_number=1, room_name="បន្ទប់លេខ ០១")
    cand_a = ExamCandidate.objects.create(
        exam=afternoon_exam,
        room=room_a,
        roll_number="001",
        desk_number=1,
        candidate_name_kh="កែវ សម្បត្តិ",
        gender="M"
    )

    # 7. Verify Room Postings view for Morning and Afternoon
    res_m_post = client.get(f'/examinations/standardized/{morning_exam.id}/room-postings/')
    assert res_m_post.status_code == 200
    html_m = res_m_post.content.decode('utf-8')
    assert "វេនពេលព្រឹក" in html_m or "ពេលព្រឹក" in html_m
    assert "សុខ ចិន្តា" in html_m
    print("4. [PASS] Morning room postings view renders Morning shift & candidate correctly.")

    res_a_post = client.get(f'/examinations/standardized/{afternoon_exam.id}/room-postings/')
    assert res_a_post.status_code == 200
    html_a = res_a_post.content.decode('utf-8')
    assert "វេនពេលរសៀល" in html_a or "ពេលរសៀល" in html_a
    assert "កែវ សម្បត្តិ" in html_a
    print("5. [PASS] Afternoon room postings view renders Afternoon shift & candidate correctly.")

    # 8. Verify Attendance Signature Sheet (បញ្ជីវត្តមានចុះហត្ថលេខា)
    res_m_att = client.get(f'/examinations/standardized/{morning_exam.id}/attendance-sheets/')
    assert res_m_att.status_code == 200
    html_att_m = res_m_att.content.decode('utf-8')
    assert "វេនពេលព្រឹក" in html_att_m or "ពេលព្រឹក" in html_att_m
    print("6. [PASS] Morning attendance signature sheet renders Morning shift correctly.")

    res_a_att = client.get(f'/examinations/standardized/{afternoon_exam.id}/attendance-sheets/')
    assert res_a_att.status_code == 200
    html_att_a = res_a_att.content.decode('utf-8')
    assert "វេនពេលរសៀល" in html_att_a or "ពេលរសៀល" in html_att_a
    print("7. [PASS] Afternoon attendance signature sheet renders Afternoon shift correctly.")

    print("\n=== ALL 7 STANDARDIZED EXAM SHIFT TESTS PASSED 100%! ===")

if __name__ == '__main__':
    test_standardized_exam_shift_assignments()
