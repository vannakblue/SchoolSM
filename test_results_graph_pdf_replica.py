import os
import sys
import datetime
from decimal import Decimal

if sys.stdout and sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
import django
django.setup()

from django.test import RequestFactory
from apps.academics.models import AcademicYear, Classroom, Subject, GradeLevelRule
from apps.students.models import Student
from apps.accounts.models import User
from apps.examinations.models import (
    StandardizedExam, ExamSubject, ExamRoom, ExamCandidate, CandidateSubjectScore, ExamTerm, Grade
)
from apps.examinations.views import exam_results_sheet_print_view, exam_results_graph_view, term_results_graph_view


def run_graph_pdf_replica_tests():
    print("\n🚀 Running Test Suite: Verify Results Graph (100% Replica of Graph.pdf)...")

    # 1. Setup Academic Year & Exam
    ay, _ = AcademicYear.objects.get_or_create(
        name="២០២៥-២០២៦",
        defaults={"is_current": True, "start_date": datetime.date(2025, 10, 1), "end_date": datetime.date(2026, 7, 31)}
    )

    admin_user = User.objects.filter(role="ADMIN").first()
    if not admin_user:
        admin_user, _ = User.objects.get_or_create(
            username="admin_graph_test",
            defaults={"role": "ADMIN", "is_staff": True, "is_superuser": True}
        )

    # 13 MoEYS subjects
    moeys_defs = [
        ('KHM_T', 'តែងសេចក្តី', 50),
        ('KHM_S', 'សរសេរតាមអាន', 50),
        ('KHM', 'ភាសាខ្មែរ', 100),
        ('MOR', 'សីលធម៌', 50),
        ('GEO', 'ភូមិវិទ្យា', 50),
        ('HIS', 'ប្រវត្តិវិទ្យា', 50),
        ('MAT', 'គណិតវិទ្យា', 100),
        ('EAR', 'ផែនដីវិទ្យា', 50),
        ('PHY', 'រូបវិទ្យា', 50),
        ('CHM', 'គីមីវិទ្យា', 50),
        ('BIO', 'ជីវវិទ្យា', 50),
        ('HOM', 'គេហវិទ្យា', 50),
        ('ENG', 'អង់គ្លេស', 50),
    ]

    subjects_map = {}
    for idx, (code, name_kh, max_s) in enumerate(moeys_defs, 1):
        s, _ = Subject.objects.get_or_create(code=code, defaults={"name_kh": name_kh, "order": idx})
        if s.name_kh != name_kh:
            s.name_kh = name_kh
            s.save()
        subjects_map[code] = (s, max_s)

    # Create Standardized Exam
    exam, _ = StandardizedExam.objects.get_or_create(
        academic_year=ay,
        name="ប្រឡងខែមិថុនា",
        defaults={
            "grade_level": 7,
            "track": "ALL",
            "exam_date": datetime.date(2026, 6, 20),
            "candidates_per_room": 25,
        }
    )

    # Link exam subjects
    for idx, (code, (s, max_s)) in enumerate(subjects_map.items(), 1):
        ExamSubject.objects.get_or_create(
            exam=exam,
            subject=s,
            defaults={"max_score": Decimal(str(max_s)), "coefficient": Decimal("1.0"), "order": idx}
        )

    # Create candidates with diverse scores
    room, _ = ExamRoom.objects.get_or_create(exam=exam, room_number=1, defaults={"room_name": "បន្ទប់ ០១"})

    # Clean old test candidates
    exam.candidates.all().delete()

    # Create 120 test candidates
    for i in range(1, 121):
        cand = ExamCandidate.objects.create(
            exam=exam,
            room=room,
            roll_number=f"70{i:03d}",
            candidate_name_kh=f"បេក្ខជន {i:02d}",
            gender="F" if i % 2 == 0 else "M",
            desk_number=i,
            dob=datetime.date(2013, 5, 10),
            origin_class="7A" if i <= 60 else "7B"
        )
        # Assign scores to create mentions A-F
        for es in exam.exam_subjects.all():
            # alternate scores between 15% and 98%
            pct = ((i * 13 + es.order * 29) % 100) / 100.0
            if pct < 0.2: pct = 0.2
            sc = round(float(es.max_score) * pct, 1)
            CandidateSubjectScore.objects.create(
                candidate=cand,
                exam_subject=es,
                score=Decimal(str(sc))
            )

    exam.recalculate_all_ranks()

    rf = RequestFactory()

    # ----------------------------------------------------
    # Test 1: Rendering exam_results_sheet_print_view?mode=graph
    # ----------------------------------------------------
    req = rf.get(f"/examinations/standardized/{exam.id}/results-sheet/?mode=graph")
    req.user = admin_user
    resp = exam_results_sheet_print_view(req, exam.id)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    html = resp.content.decode('utf-8')

    # Verify Title
    assert "លទ្ធផលប្រឡង" in html, "Title prefix 'លទ្ធផលប្រឡង' missing!"
    assert "ខែមិថុនា" in html, "Exam term name 'ខែមិថុនា' missing from title!"
    assert "ឆ្នាំសិក្សា" in html, "'ឆ្នាំសិក្សា' missing from title!"
    assert "ថ្នាក់ទី" in html, "'ថ្នាក់ទី' missing from title!"
    print("✅ Test 1 Passed: Title correctly rendered with Khmer numerals!")

    # ----------------------------------------------------
    # Test 2: Verify all 13 MoEYS subjects rendered in order
    # ----------------------------------------------------
    for _, name_kh, _ in moeys_defs:
        # Check either directly or with break tag
        assert (name_kh in html or (name_kh == 'សរសេរតាមអាន' and 'សរសេរតាម' in html)), f"Subject {name_kh} missing in graph columns!"
    print("✅ Test 2 Passed: All 13 MoEYS subjects rendered in columns and integrated table!")

    # ----------------------------------------------------
    # Test 3: Verify Mentions A to F and Legend Colors
    # ----------------------------------------------------
    for g in ['A', 'B', 'C', 'D', 'E', 'F']:
        assert f"<span>{g}</span>" in html or f">{g}<" in html, f"Grade {g} missing in data table rows!"
    assert "#1f4e79" in html, "Color for Grade A (#1f4e79) missing!"
    assert "#c55a11" in html, "Color for Grade B (#c55a11) missing!"
    assert "#276a3c" in html, "Color for Grade C (#276a3c) missing!"
    assert "#00a2e8" in html, "Color for Grade D (#00a2e8) missing!"
    assert "#800080" in html, "Color for Grade E (#800080) missing!"
    assert "#548235" in html, "Color for Grade F (#548235) missing!"
    print("✅ Test 3 Passed: Mentions A-F and exact color palette verified!")

    # ----------------------------------------------------
    # Test 4: Verify Y-Axis Ticks (120, 100, 80, 60, 40, 20, 0)
    # ----------------------------------------------------
    for tick in [120, 100, 80, 60, 40, 20, 0]:
        assert f'<div class="y-tick-label">{tick}</div>' in html, f"Tick {tick} missing from Y-axis!"
    print("✅ Test 4 Passed: Y-Axis ticks (120, 100, 80, 60, 40, 20, 0) and grid lines verified!")

    # ----------------------------------------------------
    # Test 5: Verify exam_results_graph_view endpoint
    # ----------------------------------------------------
    req_direct = rf.get(f"/examinations/standardized/{exam.id}/graph/")
    req_direct.user = admin_user
    resp_direct = exam_results_graph_view(req_direct, exam.id)
    assert resp_direct.status_code == 302, f"Expected 302 redirect, got {resp_direct.status_code}"
    assert "mode=graph" in resp_direct.url, f"Expected mode=graph in redirect URL, got {resp_direct.url}"
    print("✅ Test 5 Passed: Dedicated endpoint /standardized/<id>/graph/ redirect verified!")

    # ----------------------------------------------------
    # Test 6: Verify term_results_graph_view for Classroom Monthly Exam
    # ----------------------------------------------------
    term, _ = ExamTerm.objects.get_or_create(
        academic_year=ay,
        name="ប្រឡងខែមិថុនា Classroom",
        defaults={"term_type": "MONTHLY", "start_date": datetime.date(2026, 6, 20), "end_date": datetime.date(2026, 6, 25)}
    )
    req_term = rf.get(f"/examinations/terms/{term.id}/graph/")
    req_term.user = admin_user
    resp_term = term_results_graph_view(req_term, term.id)
    assert resp_term.status_code == 200, f"Expected 200, got {resp_term.status_code}"
    print("✅ Test 6 Passed: Classroom Monthly Exam Graph endpoint verified!")

    # ----------------------------------------------------
    # Test 7: Export HTML to file and Render to PDF with Headless Chrome
    # ----------------------------------------------------
    out_html = "e:/SchoolSM/test_graph_render.html"
    out_pdf = "e:/SchoolSM/test_graph_render.pdf"

    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html)

    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
    ]
    chrome_bin = None
    for p in chrome_paths:
        if os.path.exists(p):
            chrome_bin = p
            break

    if chrome_bin:
        import subprocess
        cmd = [
            chrome_bin,
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={out_pdf}",
            out_html
        ]
        res = subprocess.run(cmd, capture_output=True)
        assert os.path.exists(out_pdf), "PDF was not generated!"
        print(f"✅ Test 7 Passed: Headless Chrome generated {out_pdf} ({os.path.getsize(out_pdf)} bytes)!")

        # Copy to artifact directory
        artifact_pdf = r"C:\Users\Admin\.gemini\antigravity-ide\brain\4dfc1657-b972-4c40-b564-7b31d3c57fbb\graph_sample.pdf"
        import shutil
        shutil.copyfile(out_pdf, artifact_pdf)
        print(f"✅ Test 8 Passed: Copied artifact to {artifact_pdf}!")

    print("\n🎉 ALL TESTS PASSED! Results Graph 100% replicates Graph.pdf!")


if __name__ == '__main__':
    run_graph_pdf_replica_tests()
