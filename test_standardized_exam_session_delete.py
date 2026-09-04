import os
import sys
import django
from datetime import date

sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.examinations.models import StandardizedExam, ExamCandidate, ExamRoom
from apps.academics.models import AcademicYear
from apps.academics.utils import get_active_academic_year

def run_tests():
    print("=" * 80)
    print("TEST: 1-CLICK DELETE ENTIRE EXAM SESSION (លុបសម័យប្រឡងទាំងមូល)")
    print("=" * 80)

    admin_user = User.objects.filter(role='ADMIN').first()
    assert admin_user is not None, "Admin user must exist"

    teacher_user = User.objects.filter(role='TEACHER').first()

    active_year = get_active_academic_year()
    if not active_year:
        active_year = AcademicYear.objects.first()

    test_exam_date = date(2026, 9, 20)
    session_title = "សម័យប្រឡងតេស្តរួមគ្នាប្រចាំខែ (Batch Test)"

    # Clean up any leftover test exams
    StandardizedExam.objects.filter(name__icontains="Batch Test").delete()

    # Create 3 grade level exams under the same session
    e7 = StandardizedExam.objects.create(
        academic_year=active_year,
        grade_level=7,
        name=f"{session_title} ថ្នាក់ទី ៧",
        exam_date=test_exam_date,
        session='MORNING',
        candidates_per_room=25
    )
    e8 = StandardizedExam.objects.create(
        academic_year=active_year,
        grade_level=8,
        name=f"{session_title} ថ្នាក់ទី ៨",
        exam_date=test_exam_date,
        session='MORNING',
        candidates_per_room=25
    )
    e9 = StandardizedExam.objects.create(
        academic_year=active_year,
        grade_level=9,
        name=f"{session_title} ថ្នាក់ទី ៩",
        exam_date=test_exam_date,
        session='MORNING',
        candidates_per_room=25
    )
    
    # Add a room to e7
    r1 = ExamRoom.objects.create(exam=e7, room_number=1, room_name="បន្ទប់ ០១")

    exam_ids = f"{e7.id},{e8.id},{e9.id}"
    print(f"✅ Created 3 test standardized exams: IDs=[{exam_ids}] with room ID={r1.id}")

    client = Client()

    # 1. Test UI Rendering for Admin
    client.force_login(admin_user)
    res_list = client.get('/examinations/standardized/')
    assert res_list.status_code == 200, f"Expected 200, got {res_list.status_code}"
    html = res_list.content.decode('utf-8')
    assert 'openDeleteSessionModal' in html, "openDeleteSessionModal JS trigger must be in HTML"
    assert 'deleteSessionModal' in html, "deleteSessionModal modal element must be in HTML"
    assert 'លុបសម័យប្រឡង' in html, "Delete button text must be in HTML"
    assert 'standardized_exam_session_delete' in html or '/examinations/standardized/session/delete/' in html, "Delete session URL must be in modal action"
    print("✅ Verified UI rendering: Delete button and Confirmation modal are present in standardized_exam_list")

    # 2. Test Non-Admin cannot delete
    if teacher_user:
        teacher_client = Client()
        teacher_client.force_login(teacher_user)
        res_teacher = teacher_client.post('/examinations/standardized/session/delete/', {
            'exam_ids': exam_ids,
            'session_title': session_title
        })
        # Should be redirected or 403
        assert res_teacher.status_code in [302, 403], f"Expected 302 or 403 for non-admin, got {res_teacher.status_code}"
        assert StandardizedExam.objects.filter(id__in=[e7.id, e8.id, e9.id]).count() == 3, "Exams must not be deleted by non-admin"
        print("✅ Verified security: Non-admin users cannot execute session delete")

    # 3. Test Admin executes 1-click delete
    res_delete = client.post('/examinations/standardized/session/delete/', {
        'exam_ids': exam_ids,
        'session_title': session_title
    }, follow=True)
    assert res_delete.status_code == 200, f"Expected 200 following redirect, got {res_delete.status_code}"

    # Verify all 3 exams are deleted
    remaining = StandardizedExam.objects.filter(id__in=[e7.id, e8.id, e9.id]).count()
    assert remaining == 0, f"Expected 0 remaining exams, found {remaining}"
    
    # Verify related room is deleted (cascade)
    room_remaining = ExamRoom.objects.filter(id=r1.id).count()
    assert room_remaining == 0, f"Expected 0 remaining rooms, found {room_remaining}"
    print("✅ Verified deletion: All 3 grade level exams and child rooms were cleanly deleted in 1 click")

    print("\n" + "=" * 80)
    print("ALL TESTS PASSED SUCCESSFULLY! 🎉")
    print("=" * 80)

if __name__ == '__main__':
    run_tests()
