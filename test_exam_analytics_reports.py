import os
import sys
import django
import datetime
from decimal import Decimal

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from apps.academics.models import AcademicYear, Subject, Classroom
from apps.examinations.models import StandardizedExam, ExamSubject, ExamCandidate, CandidateSubjectScore
from apps.examinations.analytics_service import ExamAnalyticsService, get_subject_mention, get_overall_mention
from apps.examinations.views import exam_analytics_view, exam_session_analytics_view

User = get_user_model()

def run_tests():
    print("=== STARTING EXAM ANALYTICS REPORTS SUITE TESTS ===")
    
    # 1. Setup Test Data
    admin_user, _ = User.objects.get_or_create(username='admin_test_analytics', defaults={'role': 'ADMIN', 'is_superuser': True})
    
    year, _ = AcademicYear.objects.get_or_create(
        name="2025-2026-ANALYTICS",
        defaults={"start_date": datetime.date(2025, 10, 1), "end_date": datetime.date(2026, 8, 31)}
    )

    # Clean previous test exams if any
    StandardizedExam.objects.filter(name__contains="ANALYTICS_TEST").delete()

    exam_g7 = StandardizedExam.objects.create(
        name="ប្រឡងឆមាសទី១ (ថ្នាក់ទី ៧) ANALYTICS_TEST",
        academic_year=year,
        grade_level=7,
        exam_date=datetime.date(2026, 3, 15),
    )

    exam_g8 = StandardizedExam.objects.create(
        name="ប្រឡងឆមាសទី១ (ថ្នាក់ទី ៨) ANALYTICS_TEST",
        academic_year=year,
        grade_level=8,
        exam_date=datetime.date(2026, 3, 15),
    )

    # Find or create Subjects safely
    subj_khmer = Subject.objects.filter(name_kh__contains="តែង").first()
    if not subj_khmer:
        subj_khmer = Subject.objects.create(name_kh="តែងសេចក្តី", code="KHM_T", order=1)

    subj_math = Subject.objects.filter(name_kh__contains="គណិត").first()
    if not subj_math:
        subj_math = Subject.objects.create(name_kh="គណិតវិទ្យា", code="MATH", order=2)

    es_g7_k = ExamSubject.objects.create(exam=exam_g7, subject=subj_khmer, max_score=Decimal('100.00'), order=1)
    es_g7_m = ExamSubject.objects.create(exam=exam_g7, subject=subj_math, max_score=Decimal('100.00'), order=2)

    es_g8_k = ExamSubject.objects.create(exam=exam_g8, subject=subj_khmer, max_score=Decimal('100.00'), order=1)
    es_g8_m = ExamSubject.objects.create(exam=exam_g8, subject=subj_math, max_score=Decimal('100.00'), order=2)

    # Create Candidates for Grade 7 (Classes 7A and 7B)
    # Cand 1: 7A Female (Excellent: Khmer 95, Math 92) -> Mention A
    c1 = ExamCandidate.objects.create(
        exam=exam_g7, roll_number="701", candidate_name_kh="សុខា ស្រីនាង", gender="F", origin_class="7A", student_code="S701",
        total_score=Decimal('187.00'), grade_letter='A'
    )
    CandidateSubjectScore.objects.create(candidate=c1, exam_subject=es_g7_k, score=Decimal('95.00'))
    CandidateSubjectScore.objects.create(candidate=c1, exam_subject=es_g7_m, score=Decimal('92.00'))

    # Cand 2: 7A Male (Good: Khmer 82, Math 84) -> Mention B
    c2 = ExamCandidate.objects.create(
        exam=exam_g7, roll_number="702", candidate_name_kh="ចាន់ តារា", gender="M", origin_class="7A", student_code="S702",
        total_score=Decimal('166.00'), grade_letter='B'
    )
    CandidateSubjectScore.objects.create(candidate=c2, exam_subject=es_g7_k, score=Decimal('82.00'))
    CandidateSubjectScore.objects.create(candidate=c2, exam_subject=es_g7_m, score=Decimal('84.00'))

    # Cand 3: 7B Female (Weak / Slow learner: Khmer 45, Math 30) -> Mention F
    c3 = ExamCandidate.objects.create(
        exam=exam_g7, roll_number="703", candidate_name_kh="កែវ ធីតា", gender="F", origin_class="7B", student_code="S703",
        total_score=Decimal('75.00'), grade_letter='F'
    )
    CandidateSubjectScore.objects.create(candidate=c3, exam_subject=es_g7_k, score=Decimal('45.00'))
    CandidateSubjectScore.objects.create(candidate=c3, exam_subject=es_g7_m, score=Decimal('30.00'))

    # Cand 4: Grade 8 (Class 8A Male: Khmer 75, Math 70) -> Mention C
    c4 = ExamCandidate.objects.create(
        exam=exam_g8, roll_number="801", candidate_name_kh="ម៉ៅ វិចិត្រ", gender="M", origin_class="8A", student_code="S801",
        total_score=Decimal('145.00'), grade_letter='C'
    )
    CandidateSubjectScore.objects.create(candidate=c4, exam_subject=es_g8_k, score=Decimal('75.00'))
    CandidateSubjectScore.objects.create(candidate=c4, exam_subject=es_g8_m, score=Decimal('70.00'))

    print("✅ Test data created successfully.")

    # 2. Test Analytics Service - Scope: School Level (Both G7 & G8)
    exams_list = [exam_g7, exam_g8]
    payload_school = ExamAnalyticsService.get_analytics_payload(exams_list, scope='school')

    assert payload_school['total_candidates'] == 4, f"Expected 4 total candidates, got {payload_school['total_candidates']}"
    assert payload_school['female_candidates'] == 2, f"Expected 2 female candidates, got {payload_school['female_candidates']}"
    assert payload_school['male_candidates'] == 2, f"Expected 2 male candidates, got {payload_school['male_candidates']}"
    
    # Overall mentions matrix checks
    tot_row = payload_school['overall_mentions']['total_row']
    assert tot_row['grand_total'] == 4, "Grand total must be 4"
    # A=1 (c1), B=1 (c2), C=1 (c4), D=0, E=0, F=1 (c3) -> sum_abc = 3
    assert tot_row['counts'][0] == 1, f"A count should be 1, got {tot_row['counts'][0]}"
    assert tot_row['counts'][1] == 1, f"B count should be 1, got {tot_row['counts'][1]}"
    assert tot_row['counts'][2] == 1, f"C count should be 1, got {tot_row['counts'][2]}"
    assert tot_row['counts'][5] == 1, f"F count should be 1, got {tot_row['counts'][5]}"
    assert tot_row['sum_abc'] == 3, f"sum_abc should be 3, got {tot_row['sum_abc']}"
    print("✅ Scope 'school' overall mentions verified.")

    # Quality evaluation checks:
    # c1: 187/200 = 93.5% >= 80% (good)
    # c2: 166/200 = 83.0% >= 80% (good)
    # c4: 145/200 = 72.5% in [65, 80) (fairly_good)
    # c3: 75/200 = 37.5% < 50% (weak)
    # Total: good = 2, fairly_good = 1, weak = 1
    q_tot = payload_school['quality_evaluation']['total_row']
    assert q_tot['good'] == 2, f"Good count should be 2, got {q_tot['good']}"
    assert q_tot['fairly_good'] == 1, f"Fairly good count should be 1, got {q_tot['fairly_good']}"
    assert q_tot['weak'] == 1, f"Weak count should be 1, got {q_tot['weak']}"
    assert q_tot['grand_total'] == 4
    print("✅ Scope 'school' quality evaluation verified.")

    # Subject mentions checks
    assert len(payload_school['subject_mentions_single']) == 2
    assert len(payload_school['subject_mentions_detailed']) == 2
    # Check Khmer subject mentions
    kh_single = next(r for r in payload_school['subject_mentions_single'] if r['subject_id'] == subj_khmer.id)
    # Scores: c1=95(A), c2=82(B), c3=45(F), c4=75(C)
    assert kh_single['a'] == 1
    assert kh_single['b'] == 1
    assert kh_single['c'] == 1
    assert kh_single['f'] == 1
    assert kh_single['sum_abc'] == 3
    assert kh_single['total'] == 4
    print("✅ Scope 'school' subject mentions verified.")

    # Subject percentage rows checks
    assert len(payload_school['subject_percentage_rows']) == 2
    # For Khmer: percentages: 95%, 82%, 45%, 75%
    kh_pct = next(r for r in payload_school['subject_percentage_rows'] if r['subject_id'] == subj_khmer.id)
    # >=95% is 1 (c1)
    assert kh_pct['gte_counts'][0] == 1
    # <50% is 1 (c3 with 45%)
    assert kh_pct['lt_50'] == 1
    print("✅ Scope 'school' subject percentage analysis verified.")

    # 3. Test Analytics Service - Scope: Grade Level (Grade 7 only)
    payload_grade = ExamAnalyticsService.get_analytics_payload(exams_list, scope='grade', grade_level=7)
    assert payload_grade['total_candidates'] == 3, f"Expected 3 candidates in G7, got {payload_grade['total_candidates']}"
    assert payload_grade['female_candidates'] == 2
    assert payload_grade['male_candidates'] == 1
    print("✅ Scope 'grade' filtering verified.")

    # 4. Test Analytics Service - Scope: Classroom Level (Class 7A only)
    payload_class = ExamAnalyticsService.get_analytics_payload(exams_list, scope='class', classroom_name='7A')
    assert payload_class['total_candidates'] == 2, f"Expected 2 candidates in 7A, got {payload_class['total_candidates']}"
    assert payload_class['female_candidates'] == 1
    assert payload_class['male_candidates'] == 1
    print("✅ Scope 'class' filtering verified.")

    # 5. Test Django HTTP Views and Template Rendering
    factory = RequestFactory()

    # Test 5.1: exam_analytics_view with exam_id
    req1 = factory.get(f'/examinations/standardized/{exam_g7.id}/analytics/')
    req1.user = admin_user
    resp1 = exam_analytics_view(req1, exam_id=exam_g7.id)
    assert resp1.status_code == 200, f"Expected status 200, got {resp1.status_code}"
    content1 = resp1.content.decode('utf-8')
    assert "របាយការណ៍វិភាគលទ្ធផល" in content1
    assert "សរុបនិទ្ទេសរួម" in content1
    assert "របាយការណ៍វាយតម្លៃគុណភាព" in content1
    assert "សង្ខេបនិទ្ទេសតាមមុខវិជ្ជា" in content1
    assert "វិភាគភាគរយមុខវិជ្ជា (ផ្អែកលើពិន្ទុអតិបរមា)" in content1
    assert "របាយការណ៍សិស្សរៀនយឺត (តាមមុខវិជ្ជា)" in content1
    assert "បង្ហាញពិន្ទុ" in content1
    assert "បង្ហាញនិទ្ទេស" in content1
    print("✅ View exam_analytics_view rendered with 200 and all 4 report components present.")

    # Test 5.2: exam_session_analytics_view with session_key and scope=school
    from apps.examinations.views import get_clean_exam_session_title
    clean_t = get_clean_exam_session_title(exam_g7.name)
    s_key = f"{year.id}_{exam_g7.exam_date}_{clean_t}"
    req2 = factory.get(f'/examinations/standardized/session/analytics/?session_key={s_key}&scope=school')
    req2.user = admin_user
    resp2 = exam_session_analytics_view(req2)
    assert resp2.status_code == 200, f"Expected status 200, got {resp2.status_code}"
    content2 = resp2.content.decode('utf-8')
    assert "កម្រិតសាលា (School Level)" in content2
    print("✅ View exam_session_analytics_view rendered with 200 for session school scope.")

    # Cleanup test records
    StandardizedExam.objects.filter(name__contains="ANALYTICS_TEST").delete()
    year.delete()
    admin_user.delete()
    print("=== ALL TESTS PASSED SUCCESSFULLY! ===")

if __name__ == '__main__':
    run_tests()
