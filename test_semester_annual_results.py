import os
import sys
import datetime
from decimal import Decimal
import django

sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.academics.models import AcademicYear, Classroom, Subject, GradeLevelRule
from apps.students.models import Student
from apps.examinations.models import ExamTerm, Grade, StudentTransferGrade
from apps.examinations.services import AcademicResultService

print("=== TESTING SEMESTER & ANNUAL RESULTS WITH TRANSFER GRADES ===")

# 1. Setup Academic Year and Classroom
year, _ = AcademicYear.objects.get_or_create(
    name="2026-2027 (Results Test)",
    defaults={'start_date': datetime.date(2026, 1, 1), 'end_date': datetime.date(2026, 12, 31), 'is_current': True}
)

classroom, _ = Classroom.objects.get_or_create(
    code="11A_SEM_TEST",
    academic_year=year,
    defaults={'name': "ថ្នាក់ទី១១A (Sem Test)", 'grade_level': 11, 'track': 'GENERAL'}
)

sub_khmer, _ = Subject.objects.get_or_create(code="KH_TEST", defaults={'name_kh': "ភាសាខ្មែរ", 'name_en': "Khmer"})
sub_math, _ = Subject.objects.get_or_create(code="MATH_TEST", defaults={'name_kh': "គណិតវិទ្យា", 'name_en': "Mathematics"})

GradeLevelRule.objects.update_or_create(
    grade_level=11, track='GENERAL', subject=sub_khmer,
    defaults={'max_score': Decimal('100.00')}
)
GradeLevelRule.objects.update_or_create(
    grade_level=11, track='GENERAL', subject=sub_math,
    defaults={'max_score': Decimal('100.00')}
)

# 2. Setup Exam Terms for Semester 1 and Semester 2
# Semester 1: 2 Monthly terms + 1 Semester 1 Final Exam
term_m1, _ = ExamTerm.objects.get_or_create(
    name="ប្រឡងប្រចាំខែមករា (M1)",
    academic_year=year,
    defaults={
        'semester': 1,
        'term_type': ExamTerm.TermType.MONTHLY,
        'is_counted_in_semester': True,
        'start_date': datetime.date(2026, 1, 20),
        'end_date': datetime.date(2026, 1, 25),
    }
)
term_m2, _ = ExamTerm.objects.get_or_create(
    name="ប្រឡងប្រចាំខែកុម្ភៈ (M2)",
    academic_year=year,
    defaults={
        'semester': 1,
        'term_type': ExamTerm.TermType.MONTHLY,
        'is_counted_in_semester': True,
        'start_date': datetime.date(2026, 2, 20),
        'end_date': datetime.date(2026, 2, 25),
    }
)
term_sem1_final, _ = ExamTerm.objects.get_or_create(
    name="ប្រឡងឆមាសទី១ (S1 Final)",
    academic_year=year,
    defaults={
        'semester': 1,
        'term_type': ExamTerm.TermType.SEMESTER_1,
        'is_counted_in_semester': True,
        'start_date': datetime.date(2026, 3, 20),
        'end_date': datetime.date(2026, 3, 25),
    }
)

# Semester 2: 1 Monthly term + 1 Semester 2 Final Exam
term_m3, _ = ExamTerm.objects.get_or_create(
    name="ប្រឡងប្រចាំខែមេសា (M3)",
    academic_year=year,
    defaults={
        'semester': 2,
        'term_type': ExamTerm.TermType.MONTHLY,
        'is_counted_in_semester': True,
        'start_date': datetime.date(2026, 4, 20),
        'end_date': datetime.date(2026, 4, 25),
    }
)
term_sem2_final, _ = ExamTerm.objects.get_or_create(
    name="ប្រឡងឆមាសទី២ (S2 Final)",
    academic_year=year,
    defaults={
        'semester': 2,
        'term_type': ExamTerm.TermType.SEMESTER_2,
        'is_counted_in_semester': True,
        'start_date': datetime.date(2026, 6, 20),
        'end_date': datetime.date(2026, 6, 25),
    }
)

# 3. Create Students:
# Student A: Regular student attending all terms
s_reg, _ = Student.objects.get_or_create(
    student_id="STU_REG_01",
    defaults={
        'khmer_name': "សេង វណ្ណា (Regular)",
        'latin_name': "SENG VANNA",
        'gender': 'M',
        'date_of_birth': datetime.date(2008, 1, 1),
        'classroom': classroom,
        'academic_year': year,
        'status': Student.Status.ACTIVE
    }
)

# Student B: Late-enrolled student (joined in M2, missed M1)
s_late, _ = Student.objects.get_or_create(
    student_id="STU_LATE_02",
    defaults={
        'khmer_name': "កែវ ចិន្តា (Late Enrolled)",
        'latin_name': "KEO CHINDA",
        'gender': 'F',
        'date_of_birth': datetime.date(2008, 3, 10),
        'classroom': classroom,
        'academic_year': year,
        'status': Student.Status.ACTIVE
    }
)

# Student C: Transferred student (joined after Semester 1)
s_transfer, _ = Student.objects.get_or_create(
    student_id="STU_TRANS_03",
    defaults={
        'khmer_name': "យិន សុភ័ក្រ (Transfer In)",
        'latin_name': "YIN SOPHAK",
        'gender': 'M',
        'date_of_birth': datetime.date(2008, 5, 12),
        'classroom': classroom,
        'academic_year': year,
        'status': Student.Status.ACTIVE
    }
)

# 4. Insert Grades:
# Regular Student A:
# M1: Khmer=80, Math=80 -> 160/200 = 80.0%
Grade.objects.update_or_create(student=s_reg, subject=sub_khmer, exam_term=term_m1, classroom=classroom, defaults={'score': Decimal('80.00'), 'max_score': Decimal('100.00')})
Grade.objects.update_or_create(student=s_reg, subject=sub_math, exam_term=term_m1, classroom=classroom, defaults={'score': Decimal('80.00'), 'max_score': Decimal('100.00')})
# M2: Khmer=90, Math=90 -> 180/200 = 90.0%
Grade.objects.update_or_create(student=s_reg, subject=sub_khmer, exam_term=term_m2, classroom=classroom, defaults={'score': Decimal('90.00'), 'max_score': Decimal('100.00')})
Grade.objects.update_or_create(student=s_reg, subject=sub_math, exam_term=term_m2, classroom=classroom, defaults={'score': Decimal('90.00'), 'max_score': Decimal('100.00')})
# Monthly Average for Student A = (80 + 90) / 2 = 85.0%
# Semester 1 Exam: Khmer=95, Math=95 -> 190/200 = 95.0%
Grade.objects.update_or_create(student=s_reg, subject=sub_khmer, exam_term=term_sem1_final, classroom=classroom, defaults={'score': Decimal('95.00'), 'max_score': Decimal('100.00')})
Grade.objects.update_or_create(student=s_reg, subject=sub_math, exam_term=term_sem1_final, classroom=classroom, defaults={'score': Decimal('95.00'), 'max_score': Decimal('100.00')})
# Semester 1 Final for Student A = (85 + 95) / 2 = 90.0%

# Semester 2 for Student A:
# M3: 80.0%, S2 Final: 80.0% -> Semester 2 Final = 80.0%
Grade.objects.update_or_create(student=s_reg, subject=sub_khmer, exam_term=term_m3, classroom=classroom, defaults={'score': Decimal('80.00'), 'max_score': Decimal('100.00')})
Grade.objects.update_or_create(student=s_reg, subject=sub_math, exam_term=term_m3, classroom=classroom, defaults={'score': Decimal('80.00'), 'max_score': Decimal('100.00')})
Grade.objects.update_or_create(student=s_reg, subject=sub_khmer, exam_term=term_sem2_final, classroom=classroom, defaults={'score': Decimal('80.00'), 'max_score': Decimal('100.00')})
Grade.objects.update_or_create(student=s_reg, subject=sub_math, exam_term=term_sem2_final, classroom=classroom, defaults={'score': Decimal('80.00'), 'max_score': Decimal('100.00')})
# Annual Average for Student A = (90.0 + 80.0) / 2 = 85.0%

# Late Student B:
# Joined in M2: Khmer=70, Math=70 -> 140/200 = 70.0% (Only 1 month attended in S1)
Grade.objects.update_or_create(student=s_late, subject=sub_khmer, exam_term=term_m2, classroom=classroom, defaults={'score': Decimal('70.00'), 'max_score': Decimal('100.00')})
Grade.objects.update_or_create(student=s_late, subject=sub_math, exam_term=term_m2, classroom=classroom, defaults={'score': Decimal('70.00'), 'max_score': Decimal('100.00')})
# Semester 1 Exam for Student B: Khmer=70, Math=70 -> 70.0%
Grade.objects.update_or_create(student=s_late, subject=sub_khmer, exam_term=term_sem1_final, classroom=classroom, defaults={'score': Decimal('70.00'), 'max_score': Decimal('100.00')})
Grade.objects.update_or_create(student=s_late, subject=sub_math, exam_term=term_sem1_final, classroom=classroom, defaults={'score': Decimal('70.00'), 'max_score': Decimal('100.00')})
# S1 Final for B = (70.0 + 70.0) / 2 = 70.0%

# Transfer Student C in Semester 2:
# S2 M3: 84.0%, S2 Final: 86.0% -> S2 Final = (84 + 86) / 2 = 85.0%
Grade.objects.update_or_create(student=s_transfer, subject=sub_khmer, exam_term=term_m3, classroom=classroom, defaults={'score': Decimal('84.00'), 'max_score': Decimal('100.00')})
Grade.objects.update_or_create(student=s_transfer, subject=sub_math, exam_term=term_m3, classroom=classroom, defaults={'score': Decimal('84.00'), 'max_score': Decimal('100.00')})
Grade.objects.update_or_create(student=s_transfer, subject=sub_khmer, exam_term=term_sem2_final, classroom=classroom, defaults={'score': Decimal('86.00'), 'max_score': Decimal('100.00')})
Grade.objects.update_or_create(student=s_transfer, subject=sub_math, exam_term=term_sem2_final, classroom=classroom, defaults={'score': Decimal('86.00'), 'max_score': Decimal('100.00')})

# 5. Test AcademicResultService Computation
s1_results = AcademicResultService.compute_semester_results(classroom, year, semester=1)
s1_map = {r['student'].id: r for r in s1_results['students_data']}

# Check Regular Student A
r_a = s1_map[s_reg.id]
assert r_a['monthly_average'] == Decimal('85.00')
assert r_a['semester_exam_score'] == Decimal('95.00')
assert r_a['semester_final_average'] == Decimal('90.00')
assert r_a['letter_grade'] == 'A'
assert r_a['rank'] == 1
print("[PASS] 1. Regular Student Semester 1: (Monthly 85 + Exam 95)/2 = 90.00% (Grade A, Rank 1) Verified!")

# Check Late Enrolled Student B
r_b = s1_map[s_late.id]
assert r_b['attended_months_count'] == 1
assert r_b['monthly_average'] == Decimal('70.00')
assert r_b['semester_final_average'] == Decimal('70.00')
assert r_b['letter_grade'] == 'C'
print("[PASS] 2. Late Enrolled Student pro-rated over actual attended months: 70.00% Verified!")

# 6. Test Transfer Grade Input (Admin inputs prior school Semester 1 score for Student C)
admin_user, _ = User.objects.get_or_create(username="admin_res_tester", defaults={'role': User.Role.ADMIN, 'is_superuser': True})
client = Client()
client.force_login(admin_user)

res_transfer = client.post('/examinations/api/transfer-grade/save/', {
    'student_id': s_transfer.id,
    'semester': 1,
    'prior_school_name': "វិទ្យាល័យ ព្រះស៊ីសុវត្ថិ",
    'monthly_average': '75.00',
    'semester_exam_score': '85.00',
    'semester_final_average': '80.00',
    'remarks': "ផ្ទេរចូលកាលពីដើមខែមេសា"
}, follow=True)
assert res_transfer.status_code == 200

# Re-compute Semester 1 and verify Student C now has prior score
s1_results_after = AcademicResultService.compute_semester_results(classroom, year, semester=1)
s1_map_after = {r['student'].id: r for r in s1_results_after['students_data']}
r_c = s1_map_after[s_transfer.id]
assert r_c['is_transfer'] is True
assert r_c['semester_final_average'] == Decimal('80.00')
assert r_c['transfer_school'] == "វិទ្យាល័យ ព្រះស៊ីសុវត្ថិ"
print("[PASS] 3. Transfer-in Student prior school Semester 1 grade (80.00%) successfully recorded and reflected!")

# 7. Test Annual Calculation
annual_res = AcademicResultService.compute_annual_results(classroom, year)
ann_map = {r['student'].id: r for r in annual_res['students_data']}

# Student A: S1=90, S2=80 -> Annual = (90 + 80)/2 = 85.00%
ann_a = ann_map[s_reg.id]
assert ann_a['s1_average'] == Decimal('90.00')
assert ann_a['s2_average'] == Decimal('80.00')
assert ann_a['annual_average'] == Decimal('85.00')
assert ann_a['letter_grade'] == 'B'
assert ann_a['passed'] is True
print("[PASS] 4. Regular Student Annual Average: (S1 90 + S2 80)/2 = 85.00% Verified!")

# Student C (Transfer): S1=80 (from prior school), S2=85 (from current school) -> Annual = (80 + 85)/2 = 82.50%
ann_c = ann_map[s_transfer.id]
assert ann_c['s1_average'] == Decimal('80.00')
assert ann_c['s2_average'] == Decimal('85.00')
assert ann_c['annual_average'] == Decimal('82.50')
assert ann_c['letter_grade'] == 'B'
assert ann_c['passed'] is True
assert 'ព្រះស៊ីសុវត្ថិ' in ann_c['notes']
print("[PASS] 5. Transfer Student Annual Average: (Prior S1 80 + Current S2 85)/2 = 82.50% Verified!")

# 8. Test Web Endpoints & Excel Exports
res_sem_view = client.get(f'/examinations/results/semester/?classroom={classroom.id}&semester=1&year={year.id}')
assert res_sem_view.status_code == 200
html_sem = res_sem_view.content.decode('utf-8')
assert 'លទ្ធផលសិក្សាប្រចាំឆមាស' in html_sem
assert s_reg.khmer_name in html_sem
assert s_transfer.khmer_name in html_sem
assert 'ព្រះស៊ីសុវត្ថិ' in html_sem
print("[PASS] 6. GET /examinations/results/semester/ rendered table, badges, and modals successfully!")

res_ann_view = client.get(f'/examinations/results/annual/?classroom={classroom.id}&year={year.id}')
assert res_ann_view.status_code == 200
html_ann = res_ann_view.content.decode('utf-8')
assert 'លទ្ធផលសិក្សាប្រចាំឆ្នាំ' in html_ann
assert 'ឡើងថ្នាក់' in html_ann
print("[PASS] 7. GET /examinations/results/annual/ rendered annual rankings and promotion status!")

res_excel_sem = client.get(f'/examinations/results/semester/export-excel/?classroom={classroom.id}&semester=1&year={year.id}')
assert res_excel_sem.status_code == 200
assert res_excel_sem['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
print("[PASS] 8. Excel Export for Semester Results downloaded successfully!")

res_excel_ann = client.get(f'/examinations/results/annual/export-excel/?classroom={classroom.id}&year={year.id}')
assert res_excel_ann.status_code == 200
assert res_excel_ann['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
print("[PASS] 9. Excel Export for Annual Results downloaded successfully!")

# Cleanup test records
Student.objects.filter(student_id__in=["STU_REG_01", "STU_LATE_02", "STU_TRANS_03"]).delete()
print("\n=== ALL SEMESTER & ANNUAL RESULTS TESTS PASSED 100%! ===")
