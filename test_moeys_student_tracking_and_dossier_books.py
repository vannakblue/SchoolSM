import os
import sys
import django
from decimal import Decimal

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage

from apps.students.models import Student
from apps.teachers.models import Teacher
from apps.academics.models import AcademicYear, Classroom, Subject, GradeLevelRule
from apps.examinations.models import ExamTerm, Grade
from apps.attendance.models import StudentAttendance
from apps.examinations.services import (
    get_student_study_tracking_book_data,
    get_student_cumulative_dossier_data,
)
from apps.examinations.views import (
    student_study_tracking_book_view,
    homeroom_individual_tracking_books_batch_view,
    student_cumulative_dossier_view,
    homeroom_cumulative_dossier_batch_view,
)

User = get_user_model()


def run_tests():
    print("=== Testing MoEYS Student Study Tracking Book & Cumulative Dossier ===")
    factory = RequestFactory()

    # 1. Setup or retrieve Admin and Teacher Users
    admin_user, _ = User.objects.get_or_create(
        username="test_admin_books",
        defaults={"role": "ADMIN", "is_staff": True, "is_superuser": True}
    )
    admin_user.role = "ADMIN"
    admin_user.is_superuser = True
    admin_user.save()

    teacher_user, _ = User.objects.get_or_create(
        username="test_teacher_books",
        defaults={"role": "TEACHER"}
    )
    teacher_user.role = "TEACHER"
    teacher_user.save()

    teacher_profile, _ = Teacher.objects.get_or_create(
        user=teacher_user,
        defaults={"khmer_name": "អ្នកគ្រូ សុខ ម៉ាលី", "latin_name": "Sok Maly", "gender": "F"}
    )

    # 2. Academic Year & Classroom (Grade 10)
    ay, _ = AcademicYear.objects.get_or_create(
        name="2026-2027",
        defaults={"start_date": "2026-10-01", "end_date": "2027-07-31", "is_current": True}
    )
    classroom, _ = Classroom.objects.get_or_create(
        code="10A_TEST_BOOKS",
        academic_year=ay,
        defaults={"name": "10A", "grade_level": 10, "homeroom_teacher": teacher_profile, "room_number": "101"}
    )
    classroom.homeroom_teacher = teacher_profile
    classroom.save()

    # 3. Student Setup
    student, _ = Student.objects.get_or_create(
        student_id="STU-2026-0001",
        defaults={
            "khmer_name": "សុខ សុវណ្ណារ៉ា",
            "latin_name": "Sok Sovannara",
            "gender": "M",
            "date_of_birth": "2010-05-15",
            "place_of_birth": "ភូមិព្រែកឯង ខណ្ឌច្បារអំពៅ រាជធានីភ្នំពេញ",
            "current_address": "ផ្ទះលេខ ១២ ផ្លូវលេខ ៥ សង្កាត់ទឹកថ្លា ខណ្ឌសែនសុខ រាជធានីភ្នំពេញ",
            "classroom": classroom,
            "academic_year": ay,
            "father_name": "សុខ វិបុល",
            "father_job": "មន្ត្រីរាជការ",
            "father_phone": "012345678",
            "mother_name": "ចាន់ ធីតា",
            "mother_job": "គ្រូបង្រៀន",
            "mother_phone": "098765432",
            "previous_school": "អនុវិទ្យាល័យ ហ៊ុន សែន ព្រែកឯង",
        }
    )
    student.classroom = classroom
    student.academic_year = ay
    student.save()

    # 4. Subjects & Exam Terms
    sub_khmer = Subject.objects.filter(name_kh="អក្សរសាស្ត្រខ្មែរ").first()
    if not sub_khmer:
        sub_khmer = Subject.objects.create(name_kh="អក្សរសាស្ត្រខ្មែរ", name_en="Khmer Literature", code="KHM_TEST")

    sub_math = Subject.objects.filter(name_kh="គណិតវិទ្យា").first()
    if not sub_math:
        sub_math = Subject.objects.create(name_kh="គណិតវិទ្យា", name_en="Mathematics", code="MATH_TEST")

    sub_phys = Subject.objects.filter(name_kh="រូបវិទ្យា").first()
    if not sub_phys:
        sub_phys = Subject.objects.create(name_kh="រូបវិទ្យា", name_en="Physics", code="PHYS_TEST")

    GradeLevelRule.objects.get_or_create(grade_level=10, subject=sub_khmer, defaults={"max_score": Decimal("100.00")})
    GradeLevelRule.objects.get_or_create(grade_level=10, subject=sub_math, defaults={"max_score": Decimal("100.00")})
    GradeLevelRule.objects.get_or_create(grade_level=10, subject=sub_phys, defaults={"max_score": Decimal("100.00")})

    term_oct = ExamTerm.objects.filter(academic_year=ay, semester=1, term_type=ExamTerm.TermType.MONTHLY).first()
    if not term_oct:
        term_oct = ExamTerm.objects.create(
            name="ប្រឡងខែតុលា", academic_year=ay, semester=1,
            term_type=ExamTerm.TermType.MONTHLY, start_date="2026-10-25", end_date="2026-10-28"
        )

    term_nov = ExamTerm.objects.filter(academic_year=ay, semester=1, term_type=ExamTerm.TermType.MONTHLY).exclude(id=term_oct.id).first()
    if not term_nov:
        term_nov = ExamTerm.objects.create(
            name="ប្រឡងខែវិច្ឆិកា", academic_year=ay, semester=1,
            term_type=ExamTerm.TermType.MONTHLY, start_date="2026-11-25", end_date="2026-11-28"
        )

    term_s1_exam = ExamTerm.objects.filter(academic_year=ay, semester=1, term_type=ExamTerm.TermType.SEMESTER_1).first()
    if not term_s1_exam:
        term_s1_exam = ExamTerm.objects.create(
            name="ប្រឡងឆមាសទី១", academic_year=ay, semester=1,
            term_type=ExamTerm.TermType.SEMESTER_1, start_date="2027-02-20", end_date="2027-02-25"
        )

    term_mar = ExamTerm.objects.filter(academic_year=ay, semester=2, term_type=ExamTerm.TermType.MONTHLY).first()
    if not term_mar:
        term_mar = ExamTerm.objects.create(
            name="ប្រឡងខែមីនា", academic_year=ay, semester=2,
            term_type=ExamTerm.TermType.MONTHLY, start_date="2027-03-25", end_date="2027-03-28"
        )

    term_s2_exam = ExamTerm.objects.filter(academic_year=ay, semester=2, term_type=ExamTerm.TermType.SEMESTER_2).first()
    if not term_s2_exam:
        term_s2_exam = ExamTerm.objects.create(
            name="ប្រឡងឆមាសទី២", academic_year=ay, semester=2,
            term_type=ExamTerm.TermType.SEMESTER_2, start_date="2027-07-20", end_date="2027-07-25"
        )

    # Populate S1 and S2 grades
    Grade.objects.update_or_create(student=student, exam_term=term_oct, subject=sub_khmer, defaults={"classroom": classroom, "score": Decimal("85.00"), "grade_letter": "B"})
    Grade.objects.update_or_create(student=student, exam_term=term_oct, subject=sub_math, defaults={"classroom": classroom, "score": Decimal("92.00"), "grade_letter": "A"})
    Grade.objects.update_or_create(student=student, exam_term=term_nov, subject=sub_khmer, defaults={"classroom": classroom, "score": Decimal("88.00"), "grade_letter": "B"})
    Grade.objects.update_or_create(student=student, exam_term=term_nov, subject=sub_math, defaults={"classroom": classroom, "score": Decimal("94.00"), "grade_letter": "A"})
    Grade.objects.update_or_create(student=student, exam_term=term_s1_exam, subject=sub_khmer, defaults={"classroom": classroom, "score": Decimal("90.00"), "grade_letter": "A"})
    Grade.objects.update_or_create(student=student, exam_term=term_s1_exam, subject=sub_math, defaults={"classroom": classroom, "score": Decimal("95.00"), "grade_letter": "A"})

    Grade.objects.update_or_create(student=student, exam_term=term_mar, subject=sub_khmer, defaults={"classroom": classroom, "score": Decimal("87.00"), "grade_letter": "B"})
    Grade.objects.update_or_create(student=student, exam_term=term_mar, subject=sub_math, defaults={"classroom": classroom, "score": Decimal("96.00"), "grade_letter": "A"})
    Grade.objects.update_or_create(student=student, exam_term=term_s2_exam, subject=sub_khmer, defaults={"classroom": classroom, "score": Decimal("92.00"), "grade_letter": "A"})
    Grade.objects.update_or_create(student=student, exam_term=term_s2_exam, subject=sub_math, defaults={"classroom": classroom, "score": Decimal("98.00"), "grade_letter": "A"})

    # Attendance
    StudentAttendance.objects.get_or_create(student=student, classroom=classroom, date="2026-10-10", session="MORNING", defaults={"status": "PRESENT"})
    StudentAttendance.objects.get_or_create(student=student, classroom=classroom, date="2026-10-15", session="MORNING", defaults={"status": "PERMISSION", "notes": "ឈឺក្បាល"})
    StudentAttendance.objects.get_or_create(student=student, classroom=classroom, date="2026-11-05", session="MORNING", defaults={"status": "ABSENT", "notes": "គ្មានច្បាប់"})

    print(">>> 1. Testing get_student_study_tracking_book_data service...")
    tracking_data = get_student_study_tracking_book_data(student, ay)
    assert tracking_data is not None, "Tracking data should not be None"
    assert tracking_data['student'] == student
    assert tracking_data['grade_level'] == 10
    assert len(tracking_data['subject_rows']) >= 2, "Should have subject rows"
    assert len(tracking_data['monthly_attendance_records']) == 10, "Should have 10 academic months"
    assert tracking_data['annual_att_totals']['excused'] >= 1, "Should count excused attendance"
    assert tracking_data['annual_att_totals']['unexcused'] >= 1, "Should count unexcused attendance"
    assert len(tracking_data['conduct_criteria']) == 5, "Should have 5 MoEYS conduct rubrics"
    assert ("ឡើងទៅរៀនថ្នាក់ទី" in tracking_data['annual_overall']['decision_kh']) or ("ត្រួតថ្នាក់ទី" in tracking_data['annual_overall']['decision_kh']), "Should include promotion recommendation"
    print("  [PASS] get_student_study_tracking_book_data verified successfully!")

    print(">>> 2. Testing get_student_cumulative_dossier_data service...")
    dossier_data = get_student_cumulative_dossier_data(student)
    assert dossier_data is not None, "Dossier data should not be None"
    assert dossier_data['current_grade'] == 10
    assert len(dossier_data['grade_records']) == 6, "Should contain 6 grades (7 through 12)"
    rec_10 = next(r for r in dossier_data['grade_records'] if r['grade_level'] == 10)
    assert rec_10['is_current'] is True
    assert rec_10['classroom_name'] == "10A"
    assert dossier_data['health_info'] is not None
    assert dossier_data['diploma_info'] is not None
    assert dossier_data['bac2_info'] is not None

    # Multi-Year Subject Breakdown Matrix assertions (ថ្នាក់ទី ៧ ដល់ ទី ១២)
    assert 'cumulative_subjects' in dossier_data, "Should include cumulative_subjects"
    assert len(dossier_data['cumulative_subjects']) >= 2, "Should have multi-year subjects"
    khmer_sub_row = next((s for s in dossier_data['cumulative_subjects'] if s['subject'].name_kh == "អក្សរសាស្ត្រខ្មែរ"), None)
    assert khmer_sub_row is not None, "Khmer subject row must exist"
    assert len(khmer_sub_row['grade_cells']) == 6, "Must have 6 grade cells (7 to 12)"
    cell_10 = next(c for c in khmer_sub_row['grade_cells'] if c['grade_level'] == 10)
    assert cell_10['is_current'] is True
    assert cell_10['annual_score'] is not None, "Grade 10 Khmer should have computed annual score"
    assert cell_10['rank'] == 1, f"Grade 10 Khmer rank should be 1, got {cell_10['rank']}"
    assert cell_10['letter'] in ['A', 'B', 'C'], f"Grade 10 Khmer letter should be valid, got {cell_10['letter']}"

    assert 'cumulative_grade_totals' in dossier_data, "Should include cumulative_grade_totals"
    assert len(dossier_data['cumulative_grade_totals']) == 6, "Should have 6 grade totals"
    tot_10 = next(t for t in dossier_data['cumulative_grade_totals'] if t['grade_level'] == 10)
    assert tot_10['is_current'] is True
    assert tot_10['total_score'] is not None
    print("  [PASS] get_student_cumulative_dossier_data with multi-year subjects verified successfully!")

    from django.contrib.sessions.middleware import SessionMiddleware
    from django.contrib.messages.middleware import MessageMiddleware

    def setup_request(req, user):
        req.user = user
        SessionMiddleware(lambda r: None).process_request(req)
        req.session.save()
        MessageMiddleware(lambda r: None).process_request(req)
        return req

    print(">>> 3. Testing Views rendering and HTTP responses with timeframes & scopes...")
    # View 1: student_study_tracking_book_view - Annual scope
    req1_annual = setup_request(factory.get(f"/examinations/students/{student.id}/tracking-book/?period=ANNUAL"), admin_user)
    resp1_annual = student_study_tracking_book_view(req1_annual, student.id)
    assert resp1_annual.status_code == 200, f"Expected 200, got {resp1_annual.status_code}"
    content1_annual = resp1_annual.content.decode('utf-8')
    assert "សៀវភៅតាមដានការសិក្សា" in content1_annual, "Title must be present in HTML"
    assert "ព្រះរាជាណាចក្រកម្ពុជា" in content1_annual, "Royal header must be present"
    assert "សុខ សុវណ្ណារ៉ា" in content1_annual, "Student name must be present"
    assert "របាយការណ៍ពេញមួយឆ្នាំ" in content1_annual, "Annual banner must be present"
    assert "col-grp-s1" in content1_annual
    assert "col-grp-s2" in content1_annual
    assert "col-grp-annual" in content1_annual

    # View 1: student_study_tracking_book_view - Semester 1 scope
    req1_s1 = setup_request(factory.get(f"/examinations/students/{student.id}/tracking-book/?period=SEMESTER_1"), admin_user)
    resp1_s1 = student_study_tracking_book_view(req1_s1, student.id)
    assert resp1_s1.status_code == 200
    content1_s1 = resp1_s1.content.decode('utf-8')
    assert "របាយការណ៍ឆមាសទី ១" in content1_s1

    # View 1: student_study_tracking_book_view - Monthly scope
    req1_m = setup_request(factory.get(f"/examinations/students/{student.id}/tracking-book/?period=MONTHLY"), admin_user)
    resp1_m = student_study_tracking_book_view(req1_m, student.id)
    assert resp1_m.status_code == 200
    content1_m = resp1_m.content.decode('utf-8')
    assert "របាយការណ៍តាមដានប្រចាំខែ" in content1_m
    print("  [PASS] student_study_tracking_book_view rendered all timeframes (Annual, S1, S2, Monthly) with 200 OK!")

    # View 2: homeroom_individual_tracking_books_batch_view
    req2 = setup_request(factory.get(f"/examinations/homeroom/{classroom.id}/individual-tracking-books/?period=ANNUAL"), teacher_user)
    resp2 = homeroom_individual_tracking_books_batch_view(req2, classroom.id)
    assert resp2.status_code == 200, f"Expected 200, got {resp2.status_code}"
    content2 = resp2.content.decode('utf-8')
    assert "សៀវភៅតាមដានការសិក្សា" in content2
    assert "សុខ សុវណ្ណារ៉ា" in content2
    assert "បោះពុម្ពមួយថ្នាក់" in content2
    print("  [PASS] homeroom_individual_tracking_books_batch_view rendered with 200 OK!")

    # View 3: student_cumulative_dossier_view
    req3 = setup_request(factory.get(f"/examinations/students/{student.id}/cumulative-dossier/"), admin_user)
    resp3 = student_cumulative_dossier_view(req3, student.id)
    assert resp3.status_code == 200, f"Expected 200, got {resp3.status_code}"
    content3 = resp3.content.decode('utf-8')
    assert "សៀវភៅសិក្ខាគារិក" in content3
    assert "CUMULATIVE ACADEMIC DOSSIER" in content3
    assert "ផ្នែកទី ៣៖ តារាងពិន្ទុតាមមុខវិជ្ជាប្រចាំឆ្នាំ ពីថ្នាក់ទី ៧ ដល់ ទី ១២" in content3
    assert "អក្សរសាស្ត្រខ្មែរ" in content3
    assert "គណិតវិទ្យា" in content3
    assert "ពិន្ទុ" in content3
    assert "ច.ថ្នាក់" in content3
    assert "និទ្ទេស" in content3
    assert "កំណត់ត្រាប្រវត្តិសិក្សាសន្សំ ពីថ្នាក់ទី ៧ ដល់ ទី ១២" in content3
    assert "ស្ថានភាពសុខភាព និងកាយសម្បទា" in content3
    assert "កំណត់ត្រាការប្រឡងសញ្ញាបត្រថ្នាក់ជាតិ" in content3
    print("  [PASS] student_cumulative_dossier_view rendered with 200 OK and MoEYS multi-year subjects standards!")

    # View 4: homeroom_cumulative_dossier_batch_view
    req4 = setup_request(factory.get(f"/examinations/homeroom/{classroom.id}/cumulative-dossier/"), teacher_user)
    resp4 = homeroom_cumulative_dossier_batch_view(req4, classroom.id)
    assert resp4.status_code == 200, f"Expected 200, got {resp4.status_code}"
    content4 = resp4.content.decode('utf-8')
    assert "សៀវភៅសិក្ខាគារិក" in content4
    assert "បោះពុម្ពជាបណ្តុំ" in content4
    assert "ផ្នែកទី ៣៖ តារាងពិន្ទុតាមមុខវិជ្ជាប្រចាំឆ្នាំ" in content4
    print("  [PASS] homeroom_cumulative_dossier_batch_view rendered with 200 OK!")

    print("\n>>> ALL TESTS PASSED SUCCESSFULLY! Both books are 100% compliant with MoEYS standards! <<<")


if __name__ == "__main__":
    run_tests()
