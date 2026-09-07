import os
import sys

if sys.stdout and sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

import datetime
from django.test import RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from apps.attendance.models import StudentAttendance, AttendanceSubmissionLog
from apps.attendance.views import student_attendance_grid
from apps.academics.models import Classroom, AcademicYear
from apps.students.models import Student

User = get_user_model()

def run_tests():
    print("=== START HOURLY ATTENDANCE RE-SUBMISSION CONFIRMATION TEST ===")
    
    admin_user = User.objects.filter(is_superuser=True).first() or User.objects.first()
    ay = AcademicYear.objects.first()
    classroom = Classroom.objects.filter(academic_year=ay).first() or Classroom.objects.first()
    test_date = datetime.date(2026, 9, 7)
    test_period = 2
    test_session = StudentAttendance.Session.MORNING

    # Ensure student exists
    student = Student.objects.filter(classroom=classroom, status='ACTIVE').first()
    if not student:
        student = Student.objects.create(
            student_id="STU_TEST_ATT_999",
            khmer_name="សិស្សតេស្ត វត្តមាន",
            latin_name="Test Student Att",
            classroom=classroom,
            academic_year=ay,
            gender=Student.Gender.MALE,
            date_of_birth=datetime.date(2010, 1, 1),
            status=Student.Status.ACTIVE
        )

    # Clean prior logs for this slot
    AttendanceSubmissionLog.objects.filter(
        classroom=classroom,
        date=test_date,
        session=test_session,
        period_number=test_period
    ).delete()
    StudentAttendance.objects.filter(
        classroom=classroom,
        date=test_date,
        session=test_session,
        period_number=test_period
    ).delete()

    factory = RequestFactory()

    # Step 1: Initial GET before any submission
    print("\n--- Step 1: Initial State Check (No prior submission) ---")
    req = factory.get(f'/attendance/?classroom={classroom.id}&date={test_date}&session={test_session}&period={test_period}')
    req.user = admin_user
    setattr(req, 'session', {})
    setattr(req, '_messages', FallbackStorage(req))

    resp = student_attendance_grid(req)
    assert resp.status_code == 200
    html = resp.content.decode('utf-8')
    assert "hasAlreadySubmitted = false" in html or "hasAlreadySubmitted = false;" in html
    print("✅ PASS: hasAlreadySubmitted is FALSE before first submission.")

    # Step 2: First Attendance Submission
    print("\n--- Step 2: First Attendance Submission ---")
    post_data = {
        'classroom': str(classroom.id),
        'date': str(test_date),
        'session': test_session,
        'period': str(test_period),
        f'is_absent_{student.id}': '1',
        f'status_{student.id}': StudentAttendance.Status.ABSENT,
        f'notes_{student.id}': 'ឈឺ',
    }
    req_post = factory.post('/attendance/', data=post_data)
    req_post.user = admin_user
    setattr(req_post, 'session', {})
    setattr(req_post, '_messages', FallbackStorage(req_post))

    resp_post = student_attendance_grid(req_post)
    assert resp_post.status_code == 302, f"Expected 302 redirect, got {resp_post.status_code}"

    log = AttendanceSubmissionLog.objects.filter(
        classroom=classroom,
        date=test_date,
        session=test_session,
        period_number=test_period
    ).first()
    assert log is not None
    assert log.submission_count == 1
    print(f"✅ PASS: First submission logged with submission_count = {log.submission_count}.")

    # Step 3: GET after submission (Must flag hasAlreadySubmitted=True and render confirmation modal)
    print("\n--- Step 3: GET after submission (Verification of Confirmation Modal & Warning) ---")
    req_after = factory.get(f'/attendance/?classroom={classroom.id}&date={test_date}&session={test_session}&period={test_period}')
    req_after.user = admin_user
    setattr(req_after, 'session', {})
    setattr(req_after, '_messages', FallbackStorage(req_after))

    resp_after = student_attendance_grid(req_after)
    assert resp_after.status_code == 200
    html_after = resp_after.content.decode('utf-8')
    assert "hasAlreadySubmitted = true" in html_after or "hasAlreadySubmitted = true;" in html_after
    assert "reSubmitConfirmModal" in html_after
    assert "លោកគ្រូ-អ្នកគ្រូបានចុះអវត្តមានសិស្សសម្រាប់ម៉ោងនេះរួចរាល់ម្តងហើយ" in html_after
    assert "តើលោកគ្រូ-អ្នកគ្រូពិតជាចង់ចុះ និងកែប្រែទិន្នន័យម្តងទៀតមែនឬទេ" in html_after
    print("✅ PASS: hasAlreadySubmitted is TRUE. Re-submission confirmation modal and warning banner are rendered!")

    # Step 4: Re-submission (2nd submission)
    print("\n--- Step 4: Re-submission Execution ---")
    req_post2 = factory.post('/attendance/', data=post_data)
    req_post2.user = admin_user
    setattr(req_post2, 'session', {})
    setattr(req_post2, '_messages', FallbackStorage(req_post2))

    resp_post2 = student_attendance_grid(req_post2)
    assert resp_post2.status_code == 302

    log.refresh_from_db()
    assert log.submission_count == 2
    print(f"✅ PASS: Re-submission succeeded! Log updated with submission_count = {log.submission_count}.")

    # Clean up
    AttendanceSubmissionLog.objects.filter(
        classroom=classroom,
        date=test_date,
        session=test_session,
        period_number=test_period
    ).delete()
    StudentAttendance.objects.filter(
        classroom=classroom,
        date=test_date,
        session=test_session,
        period_number=test_period
    ).delete()
    if student.student_id == "STU_TEST_ATT_999":
        student.delete()
    print("✅ Cleaned up test data.")

    print("\n=== ALL ATTENDANCE RE-SUBMISSION TESTS PASSED! ===")

if __name__ == '__main__':
    run_tests()
