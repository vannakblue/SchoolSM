import os
import sys
import django
import datetime
from decimal import Decimal
import json

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import RequestFactory, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware

def setup_request(req, user):
    middleware = SessionMiddleware(lambda r: None)
    middleware.process_request(req)
    req.session.save()
    setattr(req, '_messages', FallbackStorage(req))
    req.user = user
    return req

from apps.accounts.models import User
from apps.academics.models import AcademicYear, Classroom, Subject, GradeLevelRule
from apps.students.models import Student
from apps.examinations.models import (
    ExamTerm, Grade, StandardizedExam, ExamRoom, ExamSubject,
    ExamCandidate, CandidateSubjectScore, ExamStudentExclusion
)
from apps.examinations.views import (
    exam_pull_candidates, grade_entry_matrix, grade_summary_view,
    exam_room_postings_view, exam_subject_attendance_view,
    api_toggle_candidate_disciplinary_hold, api_batch_toggle_disciplinary_hold,
    exam_exclusions_manage, api_toggle_exam_exclusion
)

print("🚀 Starting Automated Test for Exam Student Restrictions, Monthly Exclusions & Disciplinary Hold...")

# 1. Setup Academic Year, Classroom, and Users
year, _ = AcademicYear.objects.get_or_create(
    name="2026-2027 (Test Restrict)",
    defaults={
        'start_date': datetime.date(2026, 1, 1),
        'end_date': datetime.date(2026, 12, 31),
        'is_current': True
    }
)

classroom, _ = Classroom.objects.get_or_create(
    code="12A_RESTRICT_TEST",
    academic_year=year,
    defaults={
        'name': "ថ្នាក់ទី១២A (Test)",
        'grade_level': 12,
        'track': 'SCIENCE'
    }
)

subj_math, _ = Subject.objects.get_or_create(
    code="MATH_RESTRICT_TEST",
    defaults={'name_kh': "គណិតវិទ្យា", 'name_en': "Mathematics", 'credit': 2}
)
GradeLevelRule.objects.get_or_create(
    grade_level=12,
    track='SCIENCE',
    subject=subj_math,
    defaults={'max_score': Decimal('100.00')}
)

admin_user, _ = User.objects.get_or_create(
    username="admin_test_restrict",
    defaults={'role': User.Role.ADMIN, 'is_superuser': True, 'khmer_name': "Admin Test"}
)
teacher_user, _ = User.objects.get_or_create(
    username="teacher_test_restrict",
    defaults={'role': User.Role.TEACHER, 'khmer_name': "Teacher Test"}
)
teacher_profile = getattr(teacher_user, 'teacher_profile', None)
if not teacher_profile:
    from apps.teachers.models import Teacher
    teacher_profile = Teacher.objects.create(
        user=teacher_user,
        teacher_id="T_RESTRICT_01",
        khmer_name="លោកគ្រូ តេស្តវិន័យ",
        gender='M',
        phone="012999888",
        status='ACTIVE'
    )
from apps.academics.models import ClassSubject
ClassSubject.objects.get_or_create(
    classroom=classroom,
    subject=subj_math,
    defaults={'teacher': teacher_profile, 'weekly_hours': 4}
)

# 2. Setup Students with different statuses
# Student 1: Active (Regular)
s1_active, _ = Student.objects.get_or_create(
    student_id="STU_ACT_01",
    defaults={
        'khmer_name': "សុខ ចាន់ថន (Active)",
        'latin_name': "SOK CHANTHORN",
        'gender': 'M',
        'date_of_birth': datetime.date(2008, 5, 10),
        'classroom': classroom,
        'academic_year': year,
        'status': Student.Status.ACTIVE
    }
)

# Student 2: Dropped Out
s2_dropped, _ = Student.objects.get_or_create(
    student_id="STU_DROP_02",
    defaults={
        'khmer_name': "មាស វិច្ឆិកា (Dropped)",
        'latin_name': "MEAS VICHEKA",
        'gender': 'F',
        'date_of_birth': datetime.date(2008, 6, 12),
        'classroom': classroom,
        'academic_year': year,
        'status': Student.Status.DROPPED
    }
)

# Student 3: Suspended
s3_suspended, _ = Student.objects.get_or_create(
    student_id="STU_SUSP_03",
    defaults={
        'khmer_name': "គង់ សុភ័ក្ត្រ (Suspended)",
        'latin_name': "KONG SOPHEAK",
        'gender': 'M',
        'date_of_birth': datetime.date(2008, 7, 15),
        'classroom': classroom,
        'academic_year': year,
        'status': Student.Status.SUSPENDED
    }
)

# Student 4: Active but Excluded for Month 5 / Exam Term
s4_excluded, _ = Student.objects.get_or_create(
    student_id="STU_EXC_04",
    defaults={
        'khmer_name': "ហេង សុជាតា (Excluded)",
        'latin_name': "HENG SOCHEATAR",
        'gender': 'F',
        'date_of_birth': datetime.date(2008, 8, 20),
        'classroom': classroom,
        'academic_year': year,
        'status': Student.Status.ACTIVE
    }
)

# Student 5: Active candidate for Disciplinary Hold Test
s5_discipline, _ = Student.objects.get_or_create(
    student_id="STU_DISC_05",
    defaults={
        'khmer_name': "កែវ ពិសី (Discipline)",
        'latin_name': "KEO PISEY",
        'gender': 'F',
        'date_of_birth': datetime.date(2008, 9, 25),
        'classroom': classroom,
        'academic_year': year,
        'status': Student.Status.ACTIVE
    }
)

# 3. Create Standardized Exam and Exam Term
std_exam, _ = StandardizedExam.objects.get_or_create(
    name="ការប្រឡងតេស្តស្តង់ដា ថ្នាក់ទី១២ (Restrictions Test)",
    academic_year=year,
    defaults={
        'grade_level': 12,
        'track': 'SCIENCE',
        'exam_date': datetime.date(2026, 5, 20),
        'candidates_per_room': 25
    }
)

exam_subj, _ = ExamSubject.objects.get_or_create(
    exam=std_exam,
    subject=subj_math,
    defaults={'max_score': Decimal('50.00'), 'coefficient': Decimal('2.0')}
)

# Create an exclusion for Student 4 (s4_excluded) for std_exam
ExamStudentExclusion.objects.get_or_create(
    student=s4_excluded,
    academic_year=year,
    standardized_exam=std_exam,
    defaults={
        'reason': ExamStudentExclusion.Reason.DROPPED,
        'notes': "សិស្សឈប់រៀនបណ្តោះអាសន្ន",
        'is_active': True,
        'excluded_by': admin_user
    }
)

# 4. TEST REQUIREMENT 1 & 2: Auto-Pull candidates enforces ONLY Active and Non-Excluded students
std_exam.candidates.all().delete()
factory = RequestFactory()
pull_request = setup_request(factory.post(f'/examinations/standardized/{std_exam.id}/pull-candidates/'), admin_user)
exam_pull_candidates(pull_request, std_exam.id)

pulled_student_ids = list(std_exam.candidates.values_list('student_id', flat=True))
print(f"Candidate IDs pulled: {pulled_student_ids}")

assert s1_active.id in pulled_student_ids, "❌ Error: Active student s1_active should be pulled!"
assert s5_discipline.id in pulled_student_ids, "❌ Error: Active student s5_discipline should be pulled!"
assert s2_dropped.id not in pulled_student_ids, "❌ Error: Dropped student s2_dropped MUST NOT be pulled!"
assert s3_suspended.id not in pulled_student_ids, "❌ Error: Suspended student s3_suspended MUST NOT be pulled!"
assert s4_excluded.id not in pulled_student_ids, "❌ Error: Excluded student s4_excluded MUST NOT be pulled!"
print("✅ Requirement 1 & 2 Passed: ONLY Active and Non-Excluded students are pulled into exams!")

# 5. TEST REQUIREMENT 4: Disciplinary Hold / Blocking on Posting & Signature Lists
# Setup a room for std_exam
room_01, _ = ExamRoom.objects.get_or_create(
    exam=std_exam,
    room_number=1,
    defaults={'room_name': "បន្ទប់លេខ ០១", 'building': "អគារ A"}
)

cand_disc = std_exam.candidates.get(student=s5_discipline)
cand_disc.room = room_01
cand_disc.desk_number = 1
cand_disc.roll_number = "001"
cand_disc.save()

cand_active = std_exam.candidates.get(student=s1_active)
cand_active.room = room_01
cand_active.desk_number = 2
cand_active.roll_number = "002"
cand_active.save()

# 5a. Toggle Disciplinary Hold ON (Tick)
toggle_req = setup_request(factory.post(
    '/examinations/api/candidate/toggle-disciplinary-hold/',
    data=json.dumps({'candidate_id': cand_disc.id, 'reason': "បញ្ហាវិន័យមិនទាន់ធ្វើកិច្ចសន្យា"}),
    content_type='application/json'
), admin_user)
resp = api_toggle_candidate_disciplinary_hold(toggle_req)
resp_data = json.loads(resp.content)
assert resp_data['status'] == 'success'
assert resp_data['is_disciplinary_blocked'] == True
cand_disc.refresh_from_db()
assert cand_disc.is_disciplinary_blocked == True
print(f"✅ Ticked disciplinary hold on «{cand_disc.candidate_name_kh}» (is_disciplinary_blocked=True)")

# 5b. Verify Room Notice Posting View masks the student info
posting_req = setup_request(factory.get(f'/examinations/standardized/{std_exam.id}/room-postings/'), admin_user)
posting_resp = exam_room_postings_view(posting_req, std_exam.id)
posting_html = posting_resp.content.decode('utf-8')

assert "⚠️ [ ផ្អាកបណ្តោះអាសន្ន - សូមទាក់ទងការិយាល័យវិន័យ/រដ្ឋបាល ដើម្បីធ្វើកិច្ចសន្យាមុនចូលប្រឡង ]" in posting_html, "❌ Error: Disciplinary notice must be masked on posting list!"
assert "សុខ ចាន់ថន" in posting_html, "❌ Error: Normal candidate s1_active must be visible on posting list!"
print("✅ Room Notice Posting List: Disciplinary student info is correctly masked/hidden!")

# 5c. Verify Attendance & Signature Sheet masks candidate and blocks signature
att_req = setup_request(factory.get(f'/examinations/standardized/{std_exam.id}/attendance-sheets/'), admin_user)
att_resp = exam_subject_attendance_view(att_req, std_exam.id)
att_html = att_resp.content.decode('utf-8')

assert "⚠️ [ ជាប់កិច្ចសន្យាវិន័យ - ផ្អាកការចុះហត្ថលេខា ]" in att_html, "❌ Error: Signature sheet must display disciplinary block!"
assert "🔒 សូមទាក់ទងគណៈកម្មការ/រដ្ឋបាល" in att_html, "❌ Error: Signature box must be locked for disciplinary student!"
print("✅ Attendance & Signature Sheet: Candidate signature is blocked!")

# 5d. Student visits office, signs contract -> Untick Disciplinary Hold (ដោះ Tick ចេញ)
untoggle_req = setup_request(factory.post(
    '/examinations/api/candidate/toggle-disciplinary-hold/',
    data=json.dumps({'candidate_id': cand_disc.id}),
    content_type='application/json'
), admin_user)
resp_untick = api_toggle_candidate_disciplinary_hold(untoggle_req)
resp_untick_data = json.loads(resp_untick.content)
assert resp_untick_data['status'] == 'success'
assert resp_untick_data['is_disciplinary_blocked'] == False
cand_disc.refresh_from_db()
assert cand_disc.is_disciplinary_blocked == False
print(f"✅ Unticked disciplinary hold on «{cand_disc.candidate_name_kh}» (is_disciplinary_blocked=False)")

# 5e. Verify both sheets now immediately restore full candidate info
posting_resp_restored = exam_room_postings_view(posting_req, std_exam.id)
posting_html_restored = posting_resp_restored.content.decode('utf-8')
assert "កែវ ពិសី" in posting_html_restored, "❌ Error: Candidate name must be restored in posting sheet!"

att_resp_restored = exam_subject_attendance_view(att_req, std_exam.id)
att_html_restored = att_resp_restored.content.decode('utf-8')
assert "កែវ ពិសី" in att_html_restored, "❌ Error: Candidate name must be restored in signature sheet!"
assert "⚠️ [ ជាប់កិច្ចសន្យាវិន័យ - ផ្អាកការចុះហត្ថលេខា ]" not in att_html_restored
print("✅ Restored Candidate: Full name and signature line are completely restored in both lists!")

# 6. TEST REQUIREMENT 3: Monthly Exam Exclusion with 0-score and Admin-only modification
exam_term, _ = ExamTerm.objects.get_or_create(
    name="ប្រឡងប្រចាំខែឧសភា ថ្នាក់ទី១២ (Test)",
    academic_year=year,
    defaults={
        'term_type': ExamTerm.TermType.MONTHLY,
        'start_date': datetime.date(2026, 5, 1),
        'end_date': datetime.date(2026, 5, 5),
    }
)

# Clean up any leftover grade records for clean test run
Grade.objects.filter(student__in=[s1_active, s4_excluded], exam_term=exam_term).delete()

# Exclude Student 4 for this exam term
term_exclusion, _ = ExamStudentExclusion.objects.update_or_create(
    student=s4_excluded,
    academic_year=year,
    exam_term=exam_term,
    defaults={
        'reason': ExamStudentExclusion.Reason.DROPPED,
        'notes': "សិស្សឈប់រៀនខែឧសភា",
        'is_active': True,
        'excluded_by': admin_user
    }
)

# 6a. Teacher attempts to post grades for classroom
matrix_post_teacher = setup_request(factory.post(
    f'/examinations/matrix/?term={exam_term.id}&classroom={classroom.id}',
    data={
        f'score_{s1_active.id}_{subj_math.id}': '85.00',
        f'score_{s4_excluded.id}_{subj_math.id}': '95.00',  # Excluded student! Teacher should not be allowed
    }
), teacher_user)
grade_entry_matrix(matrix_post_teacher)

# Verify s1_active got score 85.00, but s4_excluded grade was not set by teacher
g1 = Grade.objects.filter(student=s1_active, exam_term=exam_term, subject=subj_math).first()
g4_teacher_attempt = Grade.objects.filter(student=s4_excluded, exam_term=exam_term, subject=subj_math).first()
assert g1 is not None and g1.score == Decimal('85.00'), "Active student grade must be saved"
assert g4_teacher_attempt is None, "❌ Error: Regular Teacher MUST NOT be able to submit scores for excluded student!"
print("✅ Teacher Score Restriction Passed: Teacher cannot submit positive scores for excluded student!")

# 6b. Admin overrides score for excluded student
matrix_post_admin = setup_request(factory.post(
    f'/examinations/matrix/?term={exam_term.id}&classroom={classroom.id}',
    data={
        f'score_{s4_excluded.id}_{subj_math.id}': '75.00',  # Admin override!
    }
), admin_user)
grade_entry_matrix(matrix_post_admin)

g4_admin_saved = Grade.objects.filter(student=s4_excluded, exam_term=exam_term, subject=subj_math).first()
assert g4_admin_saved is not None and g4_admin_saved.score == Decimal('75.00'), "❌ Error: Admin MUST be able to override scores!"
print("✅ Admin Override Passed: Admin successfully overridden score for student!")

# 7. TEST STUDENT RE-ENROLLMENT / RETURN (ចូលរៀនវិញ)
# Student was absent/dropped for Month 5, now re-enrolls in Month 6
exam_term_june, _ = ExamTerm.objects.get_or_create(
    name="ប្រឡងប្រចាំខែមិថុនា ថ្នាក់ទី១២ (Test)",
    academic_year=year,
    defaults={
        'term_type': ExamTerm.TermType.MONTHLY,
        'start_date': datetime.date(2026, 6, 1),
        'end_date': datetime.date(2026, 6, 5),
    }
)

# Student s4_excluded returns to ACTIVE status and is not excluded for June
s4_excluded.status = Student.Status.ACTIVE
s4_excluded.save()

# Verify June matrix renders s4_excluded as normal active student
june_get_req = setup_request(factory.get(f'/examinations/matrix/?term={exam_term_june.id}&classroom={classroom.id}'), teacher_user)
june_resp = grade_entry_matrix(june_get_req)
june_html = june_resp.content.decode('utf-8')
assert s4_excluded.khmer_name in june_html, "Student should appear in June matrix"
assert f'name="score_{s4_excluded.id}_{subj_math.id}"' in june_html, "Student input should be editable in June matrix"

# Grade student normally in June by teacher
june_post_teacher = setup_request(factory.post(
    f'/examinations/matrix/?term={exam_term_june.id}&classroom={classroom.id}',
    data={
        f'score_{s4_excluded.id}_{subj_math.id}': '90.00',
    }
), teacher_user)
grade_entry_matrix(june_post_teacher)

g4_june = Grade.objects.filter(student=s4_excluded, exam_term=exam_term_june, subject=subj_math).first()
assert g4_june is not None and g4_june.score == Decimal('90.00'), "Re-enrolled student can be graded normally in new term"
print("✅ Re-enrollment Workflow Passed: Student returning to school can take new monthly exams normally!")

# 8. TEST EXCLUSIONS MANAGEMENT VIEW & AJAX API
exc_manage_req = setup_request(factory.get('/examinations/exclusions/'), admin_user)
exc_manage_resp = exam_exclusions_manage(exc_manage_req)
assert exc_manage_resp.status_code == 200
print("✅ GET /examinations/exclusions/ -> 200 OK")

# Test toggle exclusion API
exc_toggle_api_req = setup_request(factory.post(
    '/examinations/api/exclusion/toggle/',
    data=json.dumps({'exclusion_id': term_exclusion.id}),
    content_type='application/json'
), admin_user)
exc_toggle_resp = api_toggle_exam_exclusion(exc_toggle_api_req)
assert json.loads(exc_toggle_resp.content)['status'] == 'success'
print("✅ AJAX Toggle Exclusion API passed!")

print("\n🎉 ALL TESTS PASSED! Active student restrictions, monthly exclusions (0-score + Admin edit), and disciplinary hold masking are 100% OPERATIONAL & VERIFIED!")

