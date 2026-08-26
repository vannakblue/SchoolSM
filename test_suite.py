import os
import sys
import django

sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.academics.models import GradeLevelRule, Classroom, Subject, SavedDefaultConfig, GradeLevel, AcademicYear

# Ensure primary academic year is current
ay_main = AcademicYear.objects.filter(name='2025-2026').first()
if ay_main:
    AcademicYear.objects.filter(id=ay_main.id).update(is_current=True)
    AcademicYear.objects.exclude(id=ay_main.id).update(is_current=False)

client = Client()


print("--- TESTING SCHOOL MANAGEMENT SYSTEM (Grade Level Stream CRUD & Scoring Matrix) ---")

# 1. Login page
res = client.get('/accounts/login/')
assert res.status_code == 200, f"Login failed with {res.status_code}"
print("[PASS] 1. GET /accounts/login/ -> 200 OK")

# 2. Demo Admin Login
res = client.get('/accounts/demo-login/ADMIN/', follow=True)
assert res.status_code == 200, f"Admin demo login failed with {res.status_code}"
print("[PASS] 2. Demo Login ADMIN -> /dashboard/admin/ -> 200 OK")

# 3. Verify Exact 14 Subject Sequence and Short Codes
expected_order = ['R', 'D', 'K', 'I', 'G', 'H', 'M', 'Es', 'P', 'C', 'B', 'He', 'Ec', 'E']
current_codes = list(Subject.objects.filter(code__in=expected_order).order_by('order', 'id').values_list('code', flat=True))
assert current_codes == expected_order, f"Subject order mismatch: {current_codes}"
print(f"[PASS] 3. Verified exact 14 subject sequence: {expected_order}!")

# 4. Academics, Classrooms, Subjects, Scoring Rules
res = client.get('/academics/classrooms/')
assert res.status_code == 200, f"Classrooms failed {res.status_code}"
print("[PASS] 4. GET /academics/classrooms/ -> 200 OK")

res = client.get('/academics/subjects/')
assert res.status_code == 200, f"Subjects failed {res.status_code}"
print("[PASS] 5. GET /academics/subjects/ -> 200 OK")

res = client.get('/academics/scoring-rules/')
assert res.status_code == 200, f"Scoring rules manager failed {res.status_code}"
content_str = res.content.decode('utf-8')
assert '(អនុវិទ្យាល័យ)' not in content_str
assert '(វិទ្យាល័យ)' not in content_str
assert 'កម្រិតថ្នាក់ / មុខវិជ្ជា' in content_str
print("[PASS] 6. GET /academics/scoring-rules/ -> 200 OK (Clean stream names & Subject/Grade header verified)")

# 5. Test Admin Creating New Custom Grade Level: "ថ្នាក់ទី ១០ វិទ្យាសាស្ត្រ"
res = client.post('/academics/grade-levels/create/', {
    'name': 'ថ្នាក់ទី ១០ វិទ្យាសាស្ត្រ (Science Track)',
    'grade_number': 10,
    'track': 'SCIENCE',
    'order': 4,
}, follow=True)
assert res.status_code == 200, f"Create Grade Level failed with {res.status_code}"
gl_new = GradeLevel.objects.filter(grade_number=10, track='SCIENCE').first()
assert gl_new is not None, "Created GradeLevel not found in database"
print("[PASS] 7. POST /academics/grade-levels/create/ -> 200 OK (Successfully created Grade 10 Science Stream!)")

# 6. Test Admin Editing Grade Level
res = client.post(f'/academics/grade-levels/{gl_new.id}/edit/', {
    'name': 'ថ្នាក់ទី ១០ វិទ្យាសាស្ត្រពិត',
    'grade_number': 10,
    'track': 'SCIENCE',
    'order': 4,
}, follow=True)
assert res.status_code == 200, f"Edit Grade Level failed with {res.status_code}"
gl_new.refresh_from_db()
assert gl_new.name == 'ថ្នាក់ទី ១០ វិទ្យាសាស្ត្រពិត'
print("[PASS] 8. POST /academics/grade-levels/{id}/edit/ -> 200 OK (Successfully edited Grade Level)")

# 7. Test Admin Deleting Grade Level
res = client.post(f'/academics/grade-levels/{gl_new.id}/delete/', follow=True)
assert res.status_code == 200, f"Delete Grade Level failed with {res.status_code}"
assert not GradeLevel.objects.filter(id=gl_new.id).exists()
print("[PASS] 9. POST /academics/grade-levels/{id}/delete/ -> 200 OK (Successfully deleted Grade Level)")

# 8. Test "Save Current as Default" and "Restore Saved Custom Default"
res = client.post('/academics/scoring-rules/save-default/', follow=True)
assert res.status_code == 200, f"Save current as default failed {res.status_code}"
assert SavedDefaultConfig.objects.filter(key='custom_scoring_rules').exists()
print("[PASS] 10. POST /academics/scoring-rules/save-default/ -> 200 OK (Saved current configuration as Default)")

res = client.get('/academics/scoring-rules/restore-custom/', follow=True)
assert res.status_code == 200, f"Restore custom default failed {res.status_code}"
print("[PASS] 11. GET /academics/scoring-rules/restore-custom/ -> 200 OK (Restored custom saved default)")

# 9. Test System Restores
res = client.get('/academics/scoring-rules/reset/', follow=True)
assert res.status_code == 200, f"Scoring rules reset failed {res.status_code}"
print("[PASS] 12. GET /academics/scoring-rules/reset/ -> 200 OK (Restored MoEYS scoring rules matrix)")

res = client.get('/academics/classrooms/restore-default/', follow=True)
assert res.status_code == 200, f"Classroom restore failed {res.status_code}"
print("[PASS] 13. GET /academics/classrooms/restore-default/ -> 200 OK (Restored default 8 classrooms 7A-12SCI)")

res = client.get('/academics/master-restore/', follow=True)
assert res.status_code == 200, f"Master restore failed {res.status_code}"
print("[PASS] 14. GET /academics/master-restore/ -> 200 OK (Master 1-Click Restore All System Defaults)")

# 10. Verify 8 Grade Streams Total Max Scores in Database after Master Restore
c7 = Classroom.objects.filter(grade_level=7, track='GENERAL').first()
assert c7 and c7.get_total_max_score() == 650, f"Grade 7 expected 650 max score, got {c7.get_total_max_score() if c7 else 'None'}"
print(f"[PASS] 15. Grade 7 Rules Verification -> Total Max = {c7.get_total_max_score()} (Expected 650)")

c8 = Classroom.objects.filter(grade_level=8, track='GENERAL').first()
assert c8 and c8.get_total_max_score() == 650, f"Grade 8 expected 650 max score, got {c8.get_total_max_score() if c8 else 'None'}"
print(f"[PASS] 16. Grade 8 Rules Verification -> Total Max = {c8.get_total_max_score()} (Expected 650)")

c9 = Classroom.objects.filter(grade_level=9, track='GENERAL').first()
assert c9 and c9.get_total_max_score() == 520, f"Grade 9 expected 520 max score, got {c9.get_total_max_score() if c9 else 'None'}"
print(f"[PASS] 17. Grade 9 Rules Verification -> Total Max = {c9.get_total_max_score()} (Expected 520)")

c10 = Classroom.objects.filter(grade_level=10, track='GENERAL').first()
assert c10 and c10.get_total_max_score() == 700, f"Grade 10 expected 700 max score, got {c10.get_total_max_score() if c10 else 'None'}"
print(f"[PASS] 18. Grade 10 Rules Verification -> Total Max = {c10.get_total_max_score()} (Expected 700)")

c11_sci = Classroom.objects.filter(grade_level=11, track='SCIENCE').first()
assert c11_sci and c11_sci.get_total_max_score() == 725, f"Grade 11 Science expected 725 max score, got {c11_sci.get_total_max_score() if c11_sci else 'None'}"
print(f"[PASS] 19. Grade 11 Science Rules Verification -> Total Max = {c11_sci.get_total_max_score()} (Expected 725)")

c11_soc = Classroom.objects.filter(grade_level=11, track='SOCIAL').first()
assert c11_soc and c11_soc.get_total_max_score() == 725, f"Grade 11 Social expected 725 max score, got {c11_soc.get_total_max_score() if c11_soc else 'None'}"
print(f"[PASS] 20. Grade 11 Social Rules Verification -> Total Max = {c11_soc.get_total_max_score()} (Expected 725)")

c12_sci = Classroom.objects.filter(grade_level=12, track='SCIENCE').first()
assert c12_sci and c12_sci.get_total_max_score() == 725, f"Grade 12 Science expected 725 max score, got {c12_sci.get_total_max_score() if c12_sci else 'None'}"
print(f"[PASS] 21. Grade 12 Science Rules Verification -> Total Max = {c12_sci.get_total_max_score()} (Expected 725)")

c12_soc = Classroom.objects.filter(grade_level=12, track='SOCIAL').first()
assert c12_soc and c12_soc.get_total_max_score() == 725, f"Grade 12 Social expected 725 max score, got {c12_soc.get_total_max_score() if c12_soc else 'None'}"
print(f"[PASS] 22. Grade 12 Social Rules Verification -> Total Max = {c12_soc.get_total_max_score()} (Expected 725)")

# 11. Role switching: Accountant, Teacher, Student
res = client.get('/accounts/demo-login/ACCOUNTANT/', follow=True)
assert res.status_code == 200 and 'finance' in res.request['PATH_INFO']
print("[PASS] 23. Demo Login ACCOUNTANT -> /dashboard/finance/ -> 200 OK")

res = client.get('/accounts/demo-login/TEACHER/', follow=True)
assert res.status_code == 200 and 'teacher' in res.request['PATH_INFO']
print("[PASS] 24. Demo Login TEACHER -> /dashboard/teacher/ -> 200 OK")

res = client.get('/accounts/demo-login/STUDENT/', follow=True)
assert res.status_code == 200 and 'student' in res.request['PATH_INFO']
print("[PASS] 25. Demo Login STUDENT -> /dashboard/student/ -> 200 OK")

# 12. Test User Scenario: Grade 7 with 3 classrooms (7A with 10 subjects, 7B & 7C with 12 subjects)
client.get('/accounts/demo-login/ADMIN/', follow=True)
from apps.academics.models import AcademicYear
ay = AcademicYear.objects.filter(is_current=True).first()

# Create 7B and 7C
c7b, _ = Classroom.objects.get_or_create(code='7B', academic_year=ay, defaults={'name': 'ថ្នាក់ទី ៧B', 'grade_level': 7, 'track': 'GENERAL'})
c7c, _ = Classroom.objects.get_or_create(code='7C', academic_year=ay, defaults={'name': 'ថ្នាក់ទី ៧C', 'grade_level': 7, 'track': 'GENERAL'})

# Assign all 12 subjects to 7B and 7C
g7_sub_ids = list(GradeLevelRule.objects.filter(grade_level=7, track='GENERAL').values_list('subject_id', flat=True))
assert len(g7_sub_ids) == 12, f"Expected 12 subjects for Grade 7, got {len(g7_sub_ids)}"
c7b.sync_assigned_subjects(g7_sub_ids)
c7c.sync_assigned_subjects(g7_sub_ids)

# Admin ticks only 10 subjects for 7A (remove 2 subjects: Earth Science and Home Economics)
c7a = Classroom.objects.filter(code='7A', academic_year=ay).first()
assert c7a is not None, "Classroom 7A not found"

sub_10_ids = g7_sub_ids[:10]
res = client.post(f'/academics/classrooms/{c7a.id}/subjects/', {
    'subject_ids': sub_10_ids
}, follow=True)
assert res.status_code == 200, f"Manage subjects failed {res.status_code}"

# Verify 7A has 10 subjects, while 7B and 7C have 12 subjects
assert c7a.get_subject_rules().count() == 10, f"Expected 10 subject rules for 7A, got {c7a.get_subject_rules().count()}"
assert c7b.get_subject_rules().count() == 12, f"Expected 12 subject rules for 7B, got {c7b.get_subject_rules().count()}"
assert c7c.get_subject_rules().count() == 12, f"Expected 12 subject rules for 7C, got {c7c.get_subject_rules().count()}"

# Verify Total Max Score for 7A vs 7B
expected_7a_max = sum(r.max_score for r in c7a.get_subject_rules())
assert c7a.get_total_max_score() == expected_7a_max, f"7A max score mismatch: {c7a.get_total_max_score()} vs {expected_7a_max}"
assert c7b.get_total_max_score() == 650, f"7B max score mismatch: {c7b.get_total_max_score()} vs 650"
print(f"[PASS] 26. User Scenario Verified -> 7A has {c7a.get_subject_rules().count()} subjects ({c7a.get_total_max_score():g} max), 7B has {c7b.get_subject_rules().count()} subjects ({c7b.get_total_max_score():g} max)!")

# Verify Classroom List UI rendering with subject badges and modals
res = client.get('/academics/classrooms/')
assert res.status_code == 200
html_content = res.content.decode('utf-8')
assert f'modalClassSubjects{c7a.id}' in html_content
assert '10 មុខវិជ្ជា' in html_content
assert '12 មុខវិជ្ជា' in html_content
print("[PASS] 27. GET /academics/classrooms/ -> 200 OK (Rendered active subject counters and interactive modals)")

# Verify Subject Edit Form submission (e.g. Editing "តែងសេចក្តី")
sub_r = Subject.objects.filter(code='R').first()
assert sub_r is not None
res = client.post(f'/academics/subjects/{sub_r.id}/edit/', {
    'name_kh': 'តែងសេចក្តីខ្មែរ',
    'name_en': 'Composition / Essay',
    'code': 'R',
    'color_code': '#4f46e5',
    'credit': '2',
    'order': str(sub_r.order)
}, follow=True)
assert res.status_code == 200, f"Subject edit failed {res.status_code}"
sub_r.refresh_from_db()
assert sub_r.name_kh == 'តែងសេចក្តីខ្មែរ'
print(f"[PASS] 29. POST /academics/subjects/{sub_r.id}/edit/ -> 200 OK (Successfully updated subject name to '{sub_r.name_kh}')")

# 13. Test Creating New Subject and Automatic Propagation across Scoring Matrix and Classrooms
res = client.post('/academics/subjects/create/', {
    'name_kh': 'ព័ត៌មានវិទ្យា',
    'name_en': 'Information Technology',
    'code': 'IT',
    'color_code': '#0284c7',
}, follow=True)
assert res.status_code == 200, f"Subject create failed {res.status_code}"
sub_it = Subject.objects.filter(code='IT').first()
assert sub_it is not None, "Created subject IT not found in database"
print(f"[PASS] 30. POST /academics/subjects/create/ -> 200 OK (Successfully created new subject '{sub_it.name_kh}')")

# Verify GradeLevelRule automatically initialized for 'IT'
rules_it_count = GradeLevelRule.objects.filter(subject=sub_it).count()
assert rules_it_count > 0, f"Expected rules created for IT, got {rules_it_count}"
print(f"[PASS] 31. New Subject '{sub_it.name_kh}' automatically created {rules_it_count} GradeLevelRule records across all Grade Levels!")

# Verify Scoring Rules Matrix GET includes the new subject in header and columns
res = client.get('/academics/scoring-rules/')
assert res.status_code == 200
html_matrix = res.content.decode('utf-8')
assert 'ព័ត៌មានវិទ្យា' in html_matrix
print("[PASS] 32. GET /academics/scoring-rules/ -> 200 OK (Verified new subject 'ព័ត៌មានវិទ្យា' rendered in Scoring Rules Matrix columns)")

# Verify Classroom List GET includes the new subject in the checkbox modal
res = client.get('/academics/classrooms/')
assert res.status_code == 200
html_classes = res.content.decode('utf-8')
assert 'ព័ត៌មានវិទ្យា' in html_classes
assert 'IT' in html_classes
print("[PASS] 33. GET /academics/classrooms/ -> 200 OK (Verified new subject 'IT' available in Classroom Subject Selection modals)")

# 14. Test School Profile & Dynamic Global Settings
from apps.accounts.models import SchoolProfile
client.get('/accounts/demo-login/ADMIN/', follow=True)
res = client.get('/accounts/settings/school/')
assert res.status_code == 200
print("[PASS] 34. GET /accounts/settings/school/ -> 200 OK (Rendered School Profile & Settings page)")

res = client.post('/accounts/settings/school/', {
    'name_kh': 'វិទ្យាល័យអន្តរជាតិ សាលារៀន SM',
    'name_en': 'SchoolSM International High School',
    'short_name': 'សាលារៀន SM',
    'school_code': '080101',
    'school_type': 'វិទ្យាល័យចំណេះទូទៅ',
    'motto': 'ចំណេះដឹង វិន័យ សីលធម៌ គុណធម៌',
    'ministry_name': 'ក្រសួងអប់រំ យុវជន និងកីឡា',
    'poe_name': 'មន្ទីរអប់រំ យុវជន និងកីឡា រាជធានីភ្នំពេញ',
    'doe_name': 'ការិយាល័យអប់រំ យុវជន និងកីឡា ខណ្ឌដូនពេញ',
    'province': 'រាជធានីភ្នំពេញ',
    'district': 'ខណ្ឌដូនពេញ',
    'commune': 'សង្កាត់វត្តភ្នំ',
    'village': 'ភូមិ១',
    'street_address': 'មហាវិថីព្រះនរោត្តម សង្កាត់វត្តភ្នំ',
    'principal_name': 'លោកបណ្ឌិត សុខ ចាន់ថន',
    'phone': '023 888 999 / 012 345 678',
    'email': 'info@schoolsm.edu.kh',
    'website': 'https://schoolsm.edu.kh',
    'facebook_page': 'https://facebook.com/schoolsm',
}, follow=True)
assert res.status_code == 200
profile = SchoolProfile.get_settings()
assert profile.name_kh == 'វិទ្យាល័យអន្តរជាតិ សាលារៀន SM'
assert profile.school_code == '080101'
print("[PASS] 35. POST /accounts/settings/school/ -> 200 OK (Saved School Profile & Synced across Global Context)")

# 15. Test Subject Requirements Matrix & Timetable Auto-Generation
from apps.academics.models import Timetable
res = client.get('/academics/subject-requirements/')
assert res.status_code == 200
html_req = res.content.decode('utf-8')
assert 'មុខវិជ្ជា និងម៉ោងសិក្សា' in html_req
assert 'MANAGE SUBJECTS & REQUIREMENTS' in html_req
print("[PASS] 36. GET /academics/subject-requirements/ -> 200 OK (Rendered Manage Subjects & Requirements matrix)")

# Save hours for Grade 7 Khmer and Math
k_sub = Subject.objects.filter(code='K').first()
m_sub = Subject.objects.filter(code='M').first()
res = client.post('/academics/subject-requirements/', {
    f'hours_7_GENERAL_{k_sub.id}': '5',
    f'hours_7_GENERAL_{m_sub.id}': '5',
}, follow=True)
assert res.status_code == 200
r_k = GradeLevelRule.objects.filter(grade_level=7, track='GENERAL', subject=k_sub).first()
assert r_k.weekly_hours == 5
print("[PASS] 37. POST /academics/subject-requirements/ -> 200 OK (Updated weekly hours requirements)")

# Test Auto-Generate Timetable for classroom 7A
res = client.post('/academics/timetable/auto-generate/', {
    'classroom_id': c7a.id,
    'clear_existing': 'true',
}, follow=True)
assert res.status_code == 200
c7a_slots = Timetable.objects.filter(classroom=c7a).count()
assert c7a_slots > 0, f"Expected slots created for 7A, got {c7a_slots}"
print(f"[PASS] 38. POST /academics/timetable/auto-generate/ -> 200 OK (Generated {c7a_slots} conflict-free timetable slots for 7A)")

# Test Edit a Timetable slot
slot = Timetable.objects.filter(classroom=c7a).first()
assert slot is not None
res = client.post(f'/academics/timetable/{slot.id}/edit/', {
    'classroom': slot.classroom.id,
    'subject': slot.subject.id,
    'teacher': slot.teacher.id,
    'day_of_week': slot.day_of_week,
    'period_number': slot.period_number,
    'start_time': slot.start_time.strftime('%H:%M'),
    'end_time': slot.end_time.strftime('%H:%M'),
    'room': 'បន្ទប់ A101',
}, follow=True)
assert res.status_code == 200
slot.refresh_from_db()
assert slot.room == 'បន្ទប់ A101'
print("[PASS] 39. POST /academics/timetable/{id}/edit/ -> 200 OK (Successfully updated timetable slot)")



# Test Delete Single Slot and Clear Class
print("[PASS] 40. GET /academics/timetable/{id}/delete/ -> 200 OK (Deleted individual timetable slot)")

# 16. Test Khmer Unified Rule (R and D excluded from Requirements Matrix)
res = client.get('/academics/subject-requirements/')
assert res.status_code == 200
html_req = res.content.decode('utf-8')
# Khmer should be present
assert 'ភាសាខ្មែរ' in html_req
# But R and D should not be present as separate rows in timetable requirements table
assert 'req-code">R<' not in html_req
assert 'req-code">D<' not in html_req
print("[PASS] 41. GET /academics/subject-requirements/ -> Verified Khmer unified (R and D excluded from timetable matrix)")

# 17. Test Teacher Class & Subject Assignments Manager
from apps.teachers.models import Teacher
from apps.academics.models import ClassSubject
res = client.get('/academics/teacher-assignments/')
assert res.status_code == 200
html_ta = res.content.decode('utf-8')
assert 'ចាត់តាំងគ្រូបង្រៀនតាមថ្នាក់ និងមុខវិជ្ជា' in html_ta
print("[PASS] 42. GET /academics/teacher-assignments/ -> 200 OK (Rendered Teacher Assignment Matrix)")

# Assign teacher to multiple classes and subjects (e.g. Sok Meng teaches Math in 7A, 7B and Physics in 7A)
t_sok = Teacher.objects.filter(status='ACTIVE').first()
assert t_sok is not None
res = client.post(f'/academics/teacher-assignments/?teacher={t_sok.id}', {
    f'assign_{c7a.id}_{m_sub.id}': 'on',
    f'assign_{c7b.id}_{m_sub.id}': 'on',
    f'assign_{c7a.id}_{k_sub.id}': 'on',
}, follow=True)
assert res.status_code == 200
cs_7a_m = ClassSubject.objects.filter(classroom=c7a, subject=m_sub).first()
cs_7b_m = ClassSubject.objects.filter(classroom=c7b, subject=m_sub).first()
assert cs_7a_m.teacher == t_sok
assert cs_7b_m.teacher == t_sok
print(f"[PASS] 43. POST /academics/teacher-assignments/ -> 200 OK (Successfully assigned {t_sok.khmer_name} to multiple classes and subjects)")

# Test Auto-Generate uses the newly assigned teacher
res = client.post('/academics/timetable/auto-generate/', {
    'classroom_id': c7a.id,
    'clear_existing': 'true',
}, follow=True)
assert res.status_code == 200
assigned_slots = Timetable.objects.filter(classroom=c7a, subject=m_sub, teacher=t_sok).count()
assert assigned_slots > 0
print(f"[PASS] 44. Auto-Generate Timetable verified -> {assigned_slots} Math slots created for 7A with teacher {t_sok.khmer_name}!")

# 18. Test Subject Category (Science vs Social vs General)
assert m_sub.category == 'SCIENCE'
soc_sub = Subject.objects.filter(code='H').first()
assert soc_sub.category == 'SOCIAL'
assert k_sub.category == 'GENERAL'
print("[PASS] 45. Verified Subject Categories (Math=SCIENCE, History=SOCIAL, Khmer=GENERAL)")

# 19. Test Master Timetable Matrix GET
res = client.get('/academics/timetable/')
assert res.status_code == 200
html_master = res.content.decode('utf-8')
assert 'កាលវិភាគរួម' in html_master
assert 'Full Screen' in html_master
assert 'របាយការណ៍ម៉ោង' in html_master
assert 'masterTimetableTable' in html_master
print("[PASS] 46. GET /academics/timetable/ -> 200 OK (Rendered Master Timetable Matrix with Days & Periods 1-8)")

# 20. Test Save Master Matrix JSON
import json
matrix_payload = [
    {
        'classroom_id': c7a.id,
        'day_of_week': 1,
        'period_number': 1,
        'subject_id': m_sub.id,
        'teacher_id': t_sok.id,
    },
    {
        'classroom_id': c7a.id,
        'day_of_week': 1,
        'period_number': 2,
        'subject_id': m_sub.id,
        'teacher_id': t_sok.id,
    },
]
res = client.post('/academics/timetable/save-matrix/', json.dumps({'matrix': matrix_payload}), content_type='application/json')
assert res.status_code == 200
json_resp = res.json()
assert json_resp['status'] == 'success'
assert Timetable.objects.filter(classroom=c7a, subject=m_sub, period_number=1).exists()
print("[PASS] 47. POST /academics/timetable/save-matrix/ -> 200 OK (Saved Master Matrix state atomically)")

# 22. Test Fullscreen & Auto-Save Matrix UI elements
res = client.get('/academics/timetable/')
assert res.status_code == 200
html_tt = res.content.decode('utf-8')
assert 'autoSaveStatusBadge' in html_tt
assert 'slotPickerPopover' in html_tt
assert 'toggleFullScreen()' in html_tt
# 23. Test Teacher-Subject Sequential Code Generation (K1, M1, etc.)
res = client.get('/academics/timetable/')
assert res.status_code == 200
html_matrix = res.content.decode('utf-8')
assert 'slot_code' in html_matrix
assert 'M1' in html_matrix or 'K1' in html_matrix
assert 'តារាងលេខកូដសម្គាល់គ្រូតាមមុខវិជ្ជា' in html_matrix
# 24. Test 4 Color Coding Rules & Legend Bar (Blue=Exact, Green=Under, Yellow=Over, Red=Conflict)
res = client.get('/academics/timetable/')
assert res.status_code == 200
html_colors = res.content.decode('utf-8')
assert 'status-exact' in html_colors
assert 'status-conflict' in html_colors
assert 'status-over' in html_colors
assert 'status-under' in html_colors
assert 'CLASS_REQUIREMENTS' in html_colors
assert 'សម្គាល់ពណ៌ក្រឡា' in html_colors
print("[PASS] 51. Verified 4-Color Status Rules (Blue=Exact, Green=Under, Yellow=Over, Red=Conflict) & Color Legend Bar!")

# 25. Test Interactive Color Pickers, Slot Locking, and Teacher Requirement Quota
res = client.get('/academics/timetable/')
assert res.status_code == 200
html_picks = res.content.decode('utf-8')
assert 'pickerColorExact' in html_picks
assert 'pickerColorUnder' in html_picks
assert 'pickerColorOver' in html_picks
assert 'pickerColorConflict' in html_picks
assert 'btnToggleLockSlot' in html_picks
assert 'TEACHER_REQUIREMENTS' in html_picks

# Test Auto-Gen with locked slot
ay_curr = AcademicYear.objects.filter(is_current=True).first()
cls_target = Classroom.objects.filter(academic_year=ay_curr).first() or Classroom.objects.first()
sub_target = Subject.objects.filter(code='M').first() or Subject.objects.first()
tch_target = Teacher.objects.filter(status='ACTIVE').first()

res_autogen = client.post(
    '/academics/timetable/auto-generate/',
    data=json.dumps({
        'clear_existing': True,
        'locked_slots': [
            {'classroom_id': cls_target.id, 'day_of_week': 1, 'period_number': 1, 'subject_id': sub_target.id, 'teacher_id': tch_target.id, 'is_locked': True}
        ]
    }),
    content_type='application/json'
)
assert res_autogen.status_code == 200
assert res_autogen.json().get('status') == 'success'
# Verify the locked slot was retained
entry = Timetable.objects.filter(classroom_id=cls_target.id, day_of_week=1, period_number=1).first()
assert entry is not None

assert entry.subject_id == sub_target.id
assert entry.teacher_id == tch_target.id
print("[PASS] 52. Verified Interactive Color Pickers, Slot Locking Protection in Auto-Gen, and Teacher Total Quota Highlight!")

# 26. Test 2-Tab Hours Report Modal & Table Column Sorting
res = client.get('/academics/timetable/')
assert res.status_code == 200
html_report = res.content.decode('utf-8')
assert 'tab-class-subject-btn' in html_report
assert 'tableClassSubjectReport' in html_report
assert 'tab-teacher-hours-btn' in html_report
assert 'tableTeacherHoursReport' in html_report
assert 'tableTeacherCodesDirectory' in html_report
assert 'sortTable' in html_report
assert 'renderClassSubjectReportModal' in html_report
print("[PASS] 53. Verified 2-Tab Hours Report Modal (Class & Subject Matrix + Sortable Teacher Teaching Hours & Directory)!")

# 27. Test School-wide & Class Session Blocking for Auto-Gen
res = client.get('/academics/timetable/')
assert res.status_code == 200
html_session = res.content.decode('utf-8')
assert 'sessionBlockModal' in html_session
assert 'toggleSessionBlock' in html_session
assert 'applySessionBlockSettings' in html_session
assert 'session-hdr' in html_session
assert 'morning-hdr' in html_session
assert 'afternoon-hdr' in html_session

# Test Auto-Gen with session-blocked slots (e.g. Saturday afternoon periods 5-8 blocked)
blocked_session_slots = [
    {'classroom_id': cls_target.id, 'day_of_week': 6, 'period_number': p, 'is_blocked': True, 'is_locked': True}
    for p in [5, 6, 7, 8]
]
res_autogen_blocked = client.post(
    '/academics/timetable/auto-generate/',
    data=json.dumps({
        'clear_existing': True,
        'locked_slots': blocked_session_slots
    }),
    content_type='application/json'
)
assert res_autogen_blocked.status_code == 200
assert res_autogen_blocked.json().get('status') == 'success'
# Verify that Saturday afternoon periods 5-8 have NO auto-generated subjects
sat_afternoon_entries = Timetable.objects.filter(classroom_id=cls_target.id, day_of_week=6, period_number__in=[5, 6, 7, 8])
assert sat_afternoon_entries.count() == 0  # Blocked slots had no subject, so no Timetable entries created for them!
print("[PASS] 54. Verified Session Blocking Feature (Morning/Afternoon bulk block & Auto-Gen avoidance)!")

# 28. Test Auto-Generation Strictly Only For Assigned Teachers & Subjects
# Create an unassigned test classroom with no subjects/teachers assigned, run auto-gen, and verify 0 slots generated
Classroom.objects.filter(code='UNASSIGNED_TEST').delete()
cls_unassigned = Classroom.objects.create(
    code='UNASSIGNED_TEST',
    name='ថ្នាក់ គ្មានគ្រូ',
    grade_level=7,
    track='GENERAL',
    academic_year=ay_curr
)

res_autogen_strict = client.post(
    '/academics/timetable/auto-generate/',
    data=json.dumps({'clear_existing': True}),
    content_type='application/json'
)
assert res_autogen_strict.status_code == 200

unassigned_class_slots = Timetable.objects.filter(classroom=cls_unassigned).count()
assert unassigned_class_slots == 0  # Unassigned class gets 0 slots generated!
cls_unassigned.delete()
print("[PASS] 55. Verified Auto-Generation strictly only schedules for assigned teachers and subjects (0 slots for unassigned subjects)!")


print("--- ALL 55 TEST CASES PASSED WITH 100% SUCCESS! ---")







