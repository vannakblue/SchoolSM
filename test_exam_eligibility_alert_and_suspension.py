import os
import sys
import datetime
import django

sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.academics.models import AcademicYear, Classroom
from apps.students.models import Student
from apps.attendance.models import StudentAttendance
from apps.examinations.models import ExamStudentExclusion
from apps.examinations.services import get_exam_at_risk_students, get_exam_at_risk_student_list

print("=== STARTING EXAM ELIGIBILITY & SUSPENSION POLICY VERIFICATION ===")

# 1. Setup Academic Year and Classroom
year, _ = AcademicYear.objects.get_or_create(
    name="2026-2027 (Policy Test Year)",
    defaults={'start_date': datetime.date(2026, 1, 1), 'end_date': datetime.date(2026, 12, 31), 'is_current': True}
)

classroom, _ = Classroom.objects.get_or_create(
    code="11A_POLICY_TEST",
    academic_year=year,
    defaults={'name': "ថ្នាក់ទី១១A (Policy Test)", 'grade_level': 11, 'track': 'SCIENCE'}
)

# 2. Setup Users
admin_user, _ = User.objects.get_or_create(
    username="admin_policy_test",
    defaults={'role': User.Role.ADMIN, 'is_superuser': True, 'khmer_name': "Admin Policy Tester"}
)
teacher_user, _ = User.objects.get_or_create(
    username="teacher_policy_test",
    defaults={'role': User.Role.TEACHER, 'is_superuser': False, 'khmer_name': "Teacher Policy Tester"}
)

# Clean up previous test students
Student.objects.filter(student_id__in=["STU_POL_01", "STU_POL_02", "STU_POL_03"]).delete()

# 3. Create Sample Students
# Student 1: Normal attendance (Eligible)
s1 = Student.objects.create(
    student_id="STU_POL_01",
    khmer_name="សុខ ចរិយា",
    latin_name="SOK CHORIYA",
    gender='F',
    date_of_birth=datetime.date(2009, 3, 10),
    classroom=classroom,
    academic_year=year,
    status=Student.Status.ACTIVE,
    is_exam_suspended=False
)

# Student 2: High unexcused absences (At Risk: 8 sessions = 4 days unexcused absent)
s2 = Student.objects.create(
    student_id="STU_POL_02",
    khmer_name="ខៀវ វិចិត្រ",
    latin_name="KHIEV VICHTRA",
    gender='M',
    date_of_birth=datetime.date(2009, 5, 15),
    classroom=classroom,
    academic_year=year,
    status=Student.Status.ACTIVE,
    is_exam_suspended=False
)

# Student 3: Already suspended by Admin manually
s3 = Student.objects.create(
    student_id="STU_POL_03",
    khmer_name="មាស រតនា",
    latin_name="MEAS RATANA",
    gender='M',
    date_of_birth=datetime.date(2009, 7, 22),
    classroom=classroom,
    academic_year=year,
    status=Student.Status.ACTIVE,
    is_exam_suspended=True,
    exam_suspension_reason='DISCIPLINARY',
    exam_suspension_notes='ជាប់កិច្ចសន្យាវិន័យលើកទី២'
)

# Create 8 unexcused absence records for s2 across 8 distinct dates/sessions (8 sessions = 4 days)
for i in range(1, 9):
    StudentAttendance.objects.create(
        student=s2,
        classroom=classroom,
        date=datetime.date(2026, 2, i),
        session=StudentAttendance.Session.MORNING,
        status=StudentAttendance.Status.ABSENT,
        recorded_by=teacher_user
    )

# Create only 2 absence records for s1 (1 day absent -> not at risk)
for i in range(1, 3):
    StudentAttendance.objects.create(
        student=s1,
        classroom=classroom,
        date=datetime.date(2026, 2, i),
        session=StudentAttendance.Session.MORNING,
        status=StudentAttendance.Status.ABSENT,
        recorded_by=teacher_user
    )

# -------------------------------------------------------------
# Test 1: Calculation and Alert Verification
# -------------------------------------------------------------
at_risk_map = get_exam_at_risk_students(academic_year=year, threshold_sessions=8)
assert s2.id in at_risk_map, "Student 2 must be flagged in at_risk_map"
assert s1.id not in at_risk_map, "Student 1 must NOT be in at_risk_map"
assert at_risk_map[s2.id]['absent_sessions'] == 8
assert at_risk_map[s2.id]['absent_days'] == 4.0

at_risk_list = get_exam_at_risk_student_list(academic_year=year, threshold_sessions=8)
assert any(st.id == s2.id for st in at_risk_list)
print("[PASS] Test 1: get_exam_at_risk_students and list correctly identify students with >= 8 sessions unexcused absence.")

# -------------------------------------------------------------
# Test 2: Crucial Policy Principle - System NEVER auto-suspends!
# -------------------------------------------------------------
s2.refresh_from_db()
assert s2.is_exam_suspended is False, "CRITICAL: System must NOT auto-suspend student! is_exam_suspended must remain False until Admin toggles it."
assert s2.is_disqualified_from_exams is False
print("[PASS] Test 2: Policy confirmed - System only alerts; is_exam_suspended remains False!")

# -------------------------------------------------------------
# Test 3: Admin Web UI Views & Alerts Check
# -------------------------------------------------------------
client = Client()
client.force_login(admin_user)

# A. Student List view has alert banner & at-risk badge
res_students = client.get(f'/students/?classroom={classroom.id}')
assert res_students.status_code == 200
html_students = res_students.content.decode('utf-8')
assert 'ការគណនាសិទ្ធិប្រឡង' in html_students
assert 'Exam Eligibility Alert' in html_students
assert 'ប្រឈម' in html_students
print("[PASS] Test 3A: Student List renders Exam Eligibility Alert Banner and At-Risk Badge.")

# B. Filter ?exam_status=at_risk isolates at-risk students
res_filter = client.get(f'/students/?classroom={classroom.id}&exam_status=at_risk')
assert res_filter.status_code == 200
html_filter = res_filter.content.decode('utf-8')
assert s2.khmer_name in html_filter
assert s1.khmer_name not in html_filter
assert s3.khmer_name not in html_filter
print("[PASS] Test 3B: Filter ?exam_status=at_risk isolates at-risk student accurately.")

# C. Exam Exclusions Manage page shows At-Risk warning section
res_exclusions = client.get('/examinations/exclusions/')
assert res_exclusions.status_code == 200
html_exclusions = res_exclusions.content.decode('utf-8')
assert 'ប្រឈមដកសិទ្ធិ' in html_exclusions
assert s2.khmer_name in html_exclusions
assert 'openDirectExcludeModal' in html_exclusions
print("[PASS] Test 3C: Exam Exclusions Manage view displays At-Risk Alert Table.")

# D. Attendance At-Risk view shows Exam Status column and Toggle button
res_att_risk = client.get(f'/attendance/at-risk/?classroom={classroom.id}&unit=TIMES&min_absences=2')
assert res_att_risk.status_code == 200
html_att_risk = res_att_risk.content.decode('utf-8')
assert 'សិទ្ធិប្រឡង' in html_att_risk
assert 'attendanceExamModal' in html_att_risk
assert 'openAttendanceExamModal' in html_att_risk
print("[PASS] Test 3D: At-Risk Attendance view renders Exam Status column and direct toggle modal.")

# -------------------------------------------------------------
# Test 4: Manual Admin Toggle (ON and OFF)
# -------------------------------------------------------------
# Admin toggles s2 to suspended
res_toggle_on = client.post(f'/students/{s2.id}/exam-status/', {
    'is_exam_suspended': 'true',
    'exam_suspension_reason': 'UNEXCUSED_ABSENCE',
    'exam_suspension_notes': 'អវត្តមានឥតច្បាប់ ៤ ថ្ងៃ',
    'next': '/attendance/at-risk/'
}, follow=True)
assert res_toggle_on.status_code == 200
s2.refresh_from_db()
assert s2.is_exam_suspended is True
assert s2.is_disqualified_from_exams is True
assert s2.exam_suspension_reason == 'UNEXCUSED_ABSENCE'
print("[PASS] Test 4A: Admin successfully toggles Exam Suspension to ON.")

# Admin toggles s2 back to eligible (OFF)
res_toggle_off = client.post(f'/students/{s2.id}/exam-status/', {
    'is_exam_suspended': 'false',
    'next': '/attendance/at-risk/'
}, follow=True)
assert res_toggle_off.status_code == 200
s2.refresh_from_db()
assert s2.is_exam_suspended is False
assert s2.is_disqualified_from_exams is False
print("[PASS] Test 4B: Admin successfully toggles Exam Suspension back to OFF (Eligible).")

# -------------------------------------------------------------
# Test 5: Teacher/Unauthorized Role cannot toggle Exam Suspension
# -------------------------------------------------------------
client_teacher = Client()
client_teacher.force_login(teacher_user)
res_teacher = client_teacher.post(f'/students/{s2.id}/exam-status/', {
    'is_exam_suspended': 'true'
})
# Must be blocked (403 forbidden or redirect)
assert res_teacher.status_code in [403, 302]
s2.refresh_from_db()
assert s2.is_exam_suspended is False, "Teacher cannot toggle exam suspension!"
print("[PASS] Test 5: Non-Admin roles are blocked from toggling Exam Suspension.")

# Cleanup
StudentAttendance.objects.filter(student__in=[s1, s2, s3]).delete()
Student.objects.filter(student_id__in=["STU_POL_01", "STU_POL_02", "STU_POL_03"]).delete()

print("\n=== ALL EXAM ELIGIBILITY & SUSPENSION POLICY TESTS PASSED 100%! ===")
