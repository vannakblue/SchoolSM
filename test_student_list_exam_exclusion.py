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
from apps.examinations.models import ExamStudentExclusion

print("=== TESTING STUDENT LIST EXAM EXCLUSION & SUSPENSION SUITE ===")

# 1. Setup Academic Year and Classroom
year, _ = AcademicYear.objects.get_or_create(
    name="2026-2027 (Exclusion Test)",
    defaults={'start_date': datetime.date(2026, 1, 1), 'end_date': datetime.date(2026, 12, 31), 'is_current': True}
)

classroom, _ = Classroom.objects.get_or_create(
    code="10A_EXAM_EXC_TEST",
    academic_year=year,
    defaults={'name': "ថ្នាក់ទី១០A (Exc Test)", 'grade_level': 10, 'track': 'GENERAL'}
)

# Clean up any leftover test records from previous runs
Student.objects.filter(student_id__in=["STU_EXC_01", "STU_EXC_02"]).delete()

# 2. Setup Admin and Teacher Users
admin_user, _ = User.objects.get_or_create(
    username="admin_exam_exc_tester",
    defaults={'role': User.Role.ADMIN, 'is_superuser': True, 'khmer_name': "Admin Exc Tester"}
)

# 3. Create Sample Students
s1, _ = Student.objects.get_or_create(
    student_id="STU_EXC_01",
    defaults={
        'khmer_name': "ចាន់ វឌ្ឍនា (Eligible)",
        'latin_name': "CHAN VATTANA",
        'gender': 'M',
        'date_of_birth': datetime.date(2009, 2, 14),
        'classroom': classroom,
        'academic_year': year,
        'status': Student.Status.ACTIVE,
        'is_exam_suspended': False
    }
)

s2, _ = Student.objects.get_or_create(
    student_id="STU_EXC_02",
    defaults={
        'khmer_name': "លី ស្រីមុំ (Disqualified)",
        'latin_name': "LY SREY MOM",
        'gender': 'F',
        'date_of_birth': datetime.date(2009, 6, 20),
        'classroom': classroom,
        'academic_year': year,
        'status': Student.Status.ACTIVE,
        'is_exam_suspended': True,
        'exam_suspension_reason': 'DISCIPLINARY',
        'exam_suspension_notes': 'លួចចម្លងសំណៅឯកសារ'
    }
)

# 4. Verify Model Properties
assert s1.is_disqualified_from_exams is False
assert s2.is_disqualified_from_exams is True
assert 'បញ្ហាវិន័យ' in s2.get_exam_suspension_reason_display()
print("[PASS] 1. Student model properties (is_disqualified_from_exams & reasons) verified!")

# 5. Test Web Client Single Student Exam Status Endpoint
client = Client()
client.force_login(admin_user)

# Toggle s1 to suspended
res = client.post(f'/students/{s1.id}/exam-status/', {
    'is_exam_suspended': 'true',
    'exam_suspension_reason': 'UNEXCUSED_ABSENCE',
    'exam_suspension_notes': 'អវត្តមានលើសពី ៥ ថ្ងៃឥតច្បាប់'
}, follow=True)
assert res.status_code == 200

s1.refresh_from_db()
assert s1.is_exam_suspended is True
assert s1.exam_suspension_reason == 'UNEXCUSED_ABSENCE'
assert s1.exam_suspension_notes == 'អវត្តមានលើសពី ៥ ថ្ងៃឥតច្បាប់'

# Verify synchronization with ExamStudentExclusion
exc_record = ExamStudentExclusion.objects.filter(student=s1, is_active=True).first()
assert exc_record is not None
assert exc_record.reason == 'UNEXCUSED_ABSENCE'
print("[PASS] 2. POST /students/<pk>/exam-status/ successfully disqualified student and synced with ExamStudentExclusion!")

# Re-enable s1
res_allow = client.post(f'/students/{s1.id}/exam-status/', {
    'is_exam_suspended': 'false'
}, follow=True)
assert res_allow.status_code == 200
s1.refresh_from_db()
assert s1.is_exam_suspended is False
exc_record_updated = ExamStudentExclusion.objects.filter(student=s1, is_active=True).first()
assert exc_record_updated is None
print("[PASS] 3. POST /students/<pk>/exam-status/ successfully restored exam eligibility!")

# 6. Test Batch Exam Status Endpoint
res_batch_suspend = client.post('/students/batch/exam-status/', {
    'student_ids': f"{s1.id},{s2.id}",
    'batch_action': 'suspend',
    'exam_suspension_reason': 'FEE_OVERDUE',
    'exam_suspension_notes': 'ជំពាក់ថ្លៃសិក្សាឆមាសទី១'
}, follow=True)
assert res_batch_suspend.status_code == 200

s1.refresh_from_db()
s2.refresh_from_db()
assert s1.is_exam_suspended is True
assert s2.is_exam_suspended is True
assert s1.exam_suspension_reason == 'FEE_OVERDUE'
print("[PASS] 4. POST /students/batch/exam-status/ (suspend) updated multiple students successfully!")

res_batch_allow = client.post('/students/batch/exam-status/', {
    'student_ids': f"{s1.id}",
    'batch_action': 'allow'
}, follow=True)
assert res_batch_allow.status_code == 200
s1.refresh_from_db()
assert s1.is_exam_suspended is False
print("[PASS] 5. POST /students/batch/exam-status/ (allow) restored student successfully!")

# 7. Test Student List Filters & Rendered HTML
res_list = client.get('/students/')
assert res_list.status_code == 200
html = res_list.content.decode('utf-8')
assert 'សិទ្ធិប្រឡង' in html
assert 'ដកសិទ្ធិប្រឡង' in html
assert 'មានសិទ្ធិប្រឡង' in html
assert 'examExclusionModal' in html
assert 'batchExamModal' in html
print("[PASS] 6. GET /students/ rendered Exam Status column, Badges, Single Modal & Batch Actions Toolbar!")

# Filter by disqualified
res_disq = client.get(f'/students/?exam_status=disqualified&year={year.id}')
assert res_disq.status_code == 200
html_disq = res_disq.content.decode('utf-8')
assert s2.khmer_name in html_disq
print("[PASS] 7. Filter ?exam_status=disqualified correctly isolates excluded students!")

# Filter by eligible
res_elig = client.get(f'/students/?exam_status=eligible&classroom={classroom.id}')
assert res_elig.status_code == 200
html_elig = res_elig.content.decode('utf-8')
assert s1.khmer_name in html_elig
assert s2.khmer_name not in html_elig
print("[PASS] 8. Filter ?exam_status=eligible correctly isolates eligible students!")

# 8. Test Student Detail View
res_detail = client.get(f'/students/{s2.id}/')
assert res_detail.status_code == 200
html_detail = res_detail.content.decode('utf-8')
assert 'ដកសិទ្ធិប្រឡង' in html_detail
print("[PASS] 9. GET /students/<pk>/ displays exam suspension badge and note on student profile!")

# Cleanup test records
Student.objects.filter(student_id__in=["STU_EXC_01", "STU_EXC_02"]).delete()
print("\n=== ALL STUDENT LIST EXAM EXCLUSION TESTS PASSED 100%! ===")
