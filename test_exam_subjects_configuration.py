import os
import sys
import django
from decimal import Decimal

if sys.stdout and sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from apps.academics.models import AcademicYear, Classroom, Subject, GradeLevelRule
from apps.students.models import Student
from apps.examinations.models import (
    ExamTerm, Grade, ExamTermSubjectSetting, StandardizedExam, ExamSubject, ExamRoom, ExamCandidate
)
from apps.examinations.services import get_effective_term_subjects, AcademicResultService


def test_exam_subjects_configuration():
    print("\n--- Starting Test: Exam Subjects Selection & Non-Tested Subjects Exclusions ---")

    import datetime

    # 1. Setup Academic Year, Exam Term, and Subjects
    ay, _ = AcademicYear.objects.get_or_create(
        name="2025-2026 Test",
        defaults={"is_current": True, "start_date": datetime.date(2025, 10, 1), "end_date": datetime.date(2026, 7, 31)}
    )
    term, _ = ExamTerm.objects.get_or_create(
        academic_year=ay,
        name="ប្រឡងខែតុលា Test",
        defaults={"term_type": "MONTHLY", "start_date": datetime.date(2025, 10, 20), "end_date": datetime.date(2025, 10, 25)}
    )

    # Ensure MoEYS core subjects exist
    khmer, _ = Subject.objects.get_or_create(code="KHM_T", defaults={"name_kh": "ភាសាខ្មែរ", "order": 1})
    math, _ = Subject.objects.get_or_create(code="MAT_T", defaults={"name_kh": "គណិតវិទ្យា", "order": 2})
    life_skills, _ = Subject.objects.get_or_create(code="LS_T", defaults={"name_kh": "បំណិនជីវិត", "order": 3})
    physics, _ = Subject.objects.get_or_create(code="PHY_T", defaults={"name_kh": "រូបវិទ្យា", "order": 4})

    # Grade Level Rules for Grade 11
    r1, _ = GradeLevelRule.objects.get_or_create(grade_level=11, track="GENERAL", subject=khmer, defaults={"max_score": Decimal("100.00")})
    r2, _ = GradeLevelRule.objects.get_or_create(grade_level=11, track="GENERAL", subject=math, defaults={"max_score": Decimal("100.00")})
    r3, _ = GradeLevelRule.objects.get_or_create(grade_level=11, track="GENERAL", subject=life_skills, defaults={"max_score": Decimal("50.00")})

    # Create Classroom 11A and 11B
    c11a, _ = Classroom.objects.get_or_create(
        academic_year=ay,
        code="11A_TEST",
        defaults={"name": "11A Test", "grade_level": 11, "track": "GENERAL"}
    )
    c11b, _ = Classroom.objects.get_or_create(
        academic_year=ay,
        code="11B_TEST",
        defaults={"name": "11B Test", "grade_level": 11, "track": "GENERAL"}
    )

    # Clean previous test settings
    ExamTermSubjectSetting.objects.filter(academic_year=ay).delete()

    # ----------------------------------------------------
    # Case 1: Default behavior - all subjects tested
    # ----------------------------------------------------
    rules_11a_all = get_effective_term_subjects(exam_term=term, classroom=c11a, include_non_tested=False)
    assert len(rules_11a_all) >= 3, f"Expected at least 3 subjects for 11A, got {len(rules_11a_all)}"
    max_11a_all = sum(r.max_score for r in rules_11a_all)
    print(f"✓ Case 1 passed: Default behavior - {len(rules_11a_all)} tested subjects, total max = {max_11a_all}")

    # ----------------------------------------------------
    # Case 2: Classroom-specific exclusion
    # User requirement: "11A មានមុខវិជ្ជា បំណិនជីវិត, តែថ្នាក់ទី 11B មិនមានទេ។"
    # Admin excludes "បំណិនជីវិត" specifically for 11B in this ExamTerm
    # ----------------------------------------------------
    setting_11b, _ = ExamTermSubjectSetting.objects.update_or_create(
        academic_year=ay,
        exam_term=term,
        classroom=c11b,
        subject=life_skills,
        defaults={"is_tested": False, "notes": "ថ្នាក់ 11B មិនប្រឡងបំណិនជីវិត"}
    )

    rules_11a = get_effective_term_subjects(exam_term=term, classroom=c11a, include_non_tested=False)
    rules_11b = get_effective_term_subjects(exam_term=term, classroom=c11b, include_non_tested=False)

    subj_ids_11a = {r.subject_id for r in rules_11a}
    subj_ids_11b = {r.subject_id for r in rules_11b}

    assert life_skills.id in subj_ids_11a, "11A must include Life Skills!"
    assert life_skills.id not in subj_ids_11b, "11B must NOT include Life Skills!"

    total_max_11a = sum(r.max_score for r in rules_11a)
    total_max_11b = sum(r.max_score for r in rules_11b)
    assert total_max_11a > total_max_11b, f"11A max ({total_max_11a}) must be greater than 11B max ({total_max_11b})"
    assert total_max_11a - total_max_11b == Decimal("50.00"), "Difference must be 50.00 for Life Skills"
    print(f"✓ Case 2 passed: 11A includes Life Skills (max {total_max_11a}), 11B excludes Life Skills (max {total_max_11b})")

    # ----------------------------------------------------
    # Case 3: Calculation of student percentage with non-tested subjects
    # A student in 11B who scored 80 in Khmer and 80 in Math should have:
    # total = 160 / 200 = 80.0%, NOT 160 / 250 = 64.0%
    # ----------------------------------------------------
    s_test, _ = Student.objects.get_or_create(
        student_id="ST_TEST_01",
        defaults={
            "khmer_name": "សិស្ស តេស្ត",
            "gender": "M",
            "classroom": c11b,
            "academic_year": ay,
            "date_of_birth": datetime.date(2008, 1, 1)
        }
    )
    s_test.classroom = c11b
    s_test.save()

    # Clear old grades
    Grade.objects.filter(student=s_test, exam_term=term).delete()
    Grade.objects.create(student=s_test, exam_term=term, classroom=c11b, subject=khmer, score=Decimal("80.00"), max_score=Decimal("100.00"), grade_letter="B")
    Grade.objects.create(student=s_test, exam_term=term, classroom=c11b, subject=math, score=Decimal("80.00"), max_score=Decimal("100.00"), grade_letter="B")

    # Test AcademicResultService
    rules_with_non_tested = get_effective_term_subjects(exam_term=term, classroom=c11b, include_non_tested=True)
    res = AcademicResultService.compute_student_term_score(student=s_test, term=term, subject_rules=rules_with_non_tested)

    print(f"Student 11B: Total Score={res['total_score']}, Total Max={res['total_max']}, Percentage={res['percentage']}%")
    assert res["total_score"] == Decimal("160.00"), f"Expected 160.00, got {res['total_score']}"
    assert res["total_max"] == total_max_11b, f"Expected {total_max_11b} (excluding 50 for Life Skills), got {res['total_max']}"
    assert res["total_max"] == total_max_11a - Decimal("50.00"), "Life Skills must be deducted from total max"
    print("✓ Case 3 passed: Student is NOT penalized for non-tested subjects! Percentage is accurately 80.00%")

    # ----------------------------------------------------
    # Case 4: Standardized Exam 7-Subject Presets (Grade 12 Science vs Social)
    # ----------------------------------------------------
    # Ensure Grade 12 subjects exist
    chem, _ = Subject.objects.get_or_create(code="CHM_T", defaults={"name_kh": "គីមីវិទ្យា", "order": 5})
    bio, _ = Subject.objects.get_or_create(code="BIO_T", defaults={"name_kh": "ជីវវិទ្យា", "order": 6})
    hist, _ = Subject.objects.get_or_create(code="HIS_T", defaults={"name_kh": "ប្រវត្តិវិទ្យា", "order": 7})
    geog, _ = Subject.objects.get_or_create(code="GEO_T", defaults={"name_kh": "ភូមិវិទ្យា", "order": 8})
    moral, _ = Subject.objects.get_or_create(code="MOR_T", defaults={"name_kh": "សីលធម៌-ពលរដ្ឋ", "order": 9})
    earth, _ = Subject.objects.get_or_create(code="EAR_T", defaults={"name_kh": "ផែនដីវិទ្យា", "order": 10})
    eng, _ = Subject.objects.get_or_create(code="ENG_T", defaults={"name_kh": "ភាសាអង់គ្លេស", "name_en": "English", "order": 11})

    std_exam, _ = StandardizedExam.objects.get_or_create(
        academic_year=ay,
        name="តេស្តសាកល្បង បាក់ឌុប Grade 12 Mock Test",
        defaults={"grade_level": 12, "track": "ALL", "exam_date": "2025-11-15"}
    )

    # Test applying Science 7 preset
    from django.test import RequestFactory
    from apps.examinations.views import api_apply_standardized_exam_preset
    from apps.accounts.models import User

    admin_user = User.objects.filter(role="ADMIN").first()
    if not admin_user:
        admin_user, _ = User.objects.get_or_create(username="admin_test", defaults={"role": "ADMIN", "is_staff": True, "is_superuser": True})

    rf = RequestFactory()

    # Apply Science Preset
    req_sci = rf.post(f"/examinations/standardized/{std_exam.id}/subjects/apply-preset/", data={"preset": "SCIENCE_7"}, content_type="application/json")
    req_sci.user = admin_user
    resp_sci = api_apply_standardized_exam_preset(req_sci, std_exam.id)
    assert resp_sci.status_code == 200, f"Expected 200, got {resp_sci.status_code}"

    std_exam.refresh_from_db()
    sci_subjects = list(std_exam.exam_subjects.select_related("subject").order_by("order"))
    assert len(sci_subjects) == 7, f"Expected 7 subjects for Science preset, got {len(sci_subjects)}"
    sci_names = [s.subject.name_kh for s in sci_subjects]
    print(f"Science 7 Subjects: {sci_names}")
    assert any("គណិត" in n for n in sci_names), "Math must be in Science 7"
    assert any("រូប" in n for n in sci_names), "Physics must be in Science 7"
    assert any("គីមី" in n for n in sci_names), "Chemistry must be in Science 7"
    assert any("ជីវ" in n for n in sci_names), "Biology must be in Science 7"

    # Math in Science has max 125, coef 2.5
    math_es = next(s for s in sci_subjects if "គណិត" in s.subject.name_kh)
    assert math_es.max_score == Decimal("125.00"), f"Expected Math max 125, got {math_es.max_score}"
    assert math_es.coefficient == Decimal("2.50"), f"Expected Math coef 2.5, got {math_es.coefficient}"
    print(f"✓ Case 4 passed: Science 7 Preset configured successfully with Math (max 125, coef 2.5)!")

    # Apply Social Preset
    req_soc = rf.post(f"/examinations/standardized/{std_exam.id}/subjects/apply-preset/", data={"preset": "SOCIAL_7"}, content_type="application/json")
    req_soc.user = admin_user
    resp_soc = api_apply_standardized_exam_preset(req_soc, std_exam.id)
    assert resp_soc.status_code == 200, f"Expected 200, got {resp_soc.status_code}"

    std_exam.refresh_from_db()
    soc_subjects = list(std_exam.exam_subjects.select_related("subject").order_by("order"))
    assert len(soc_subjects) == 7, f"Expected 7 subjects for Social preset, got {len(soc_subjects)}"
    soc_names = [s.subject.name_kh for s in soc_subjects]
    print(f"Social 7 Subjects: {soc_names}")
    # Khmer in Social has max 125, coef 2.5
    khmer_es = next(s for s in soc_subjects if "ខ្មែរ" in s.subject.name_kh)
    assert khmer_es.max_score == Decimal("125.00"), f"Expected Khmer max 125 in Social, got {khmer_es.max_score}"
    assert khmer_es.coefficient == Decimal("2.50"), f"Expected Khmer coef 2.5 in Social, got {khmer_es.coefficient}"
    print(f"✓ Case 5 passed: Social 7 Preset configured successfully with Khmer (max 125, coef 2.5)!")

    print("\n🎉 ALL TESTS PASSED SUCCESSFULLY!")

if __name__ == '__main__':
    test_exam_subjects_configuration()
