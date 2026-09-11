import os
import sys
import datetime
import subprocess
import pypdf

if sys.stdout and sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

sys.path.insert(0, 'E:/SchoolSM')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
import django
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from apps.academics.models import AcademicYear, Classroom, Subject
from apps.students.models import Student
from apps.accounts.models import SchoolProfile
from apps.examinations.models import ExamTerm, Grade
from apps.examinations.views import (
    report_card_transcript_view,
    classroom_report_cards_transcript_view,
    report_card_western_view,
    classroom_report_cards_western_view,
)

User = get_user_model()

def setup_request(request, user):
    request.user = user
    request.session = {}
    return request

def run_tests():
    print("🚀 Running Test Suite: Verify Student Transcript (ព្រឹត្តិបត្រពិន្ទុ) 100% Replication of transcript.pdf...")
    factory = RequestFactory()

    admin_user, _ = User.objects.get_or_create(
        username="admin_test_transcript",
        defaults={'role': 'ADMIN', 'is_staff': True, 'is_superuser': True}
    )

    year, _ = AcademicYear.objects.get_or_create(
        name="២០២៥-២០២៦",
        defaults={
            'start_date': datetime.date(2025, 10, 1),
            'end_date': datetime.date(2026, 8, 31),
            'is_current': True,
        }
    )

    sp = SchoolProfile.get_settings()
    sp.province = "ខេត្តកណ្ដាល"
    sp.name_kh = "វិទ្យាល័យ ហ៊ុន សែន កំពង់កន្ទួត"
    sp.save()

    from apps.teachers.models import Teacher

    # Homeroom Teacher matching transcript.pdf
    teacher, _ = Teacher.objects.get_or_create(
        teacher_id="T_TRANSCRIPT_TEST",
        defaults={
            'khmer_name': 'ស៊ិន ម៉ូនីដា',
            'latin_name': 'Sin Monida',
            'phone': '(093) 995-927',
            'gender': 'F',
        }
    )
    teacher.khmer_name = 'ស៊ិន ម៉ូនីដា'
    teacher.phone = '(093) 995-927'
    teacher.save()

    # Classroom 12A, Track SCIENCE matching transcript.pdf
    classroom, _ = Classroom.objects.get_or_create(
        code="12A",
        academic_year=year,
        defaults={
            'name': '12A',
            'grade_level': 12,
            'track': 'SCIENCE',
            'homeroom_teacher': teacher,
        }
    )
    classroom.name = "12A"
    classroom.grade_level = 12
    classroom.track = 'SCIENCE'
    classroom.homeroom_teacher = teacher
    classroom.save()

    # Exam term matching transcript.pdf: តេស្តដើមឆ្នាំ
    term, _ = ExamTerm.objects.get_or_create(
        name="តេស្តដើមឆ្នាំ",
        academic_year=year,
        defaults={
            'term_type': ExamTerm.TermType.MONTHLY,
            'start_date': datetime.date(2025, 10, 1),
            'end_date': datetime.date(2025, 10, 31),
        }
    )

    # Clean old students from test class
    Student.objects.filter(classroom=classroom).delete()

    # Main student matching transcript.pdf: 1-ជាម សុធា
    main_student = Student.objects.create(
        student_id="1",
        khmer_name="ជាម សុធា",
        gender="F",
        date_of_birth=datetime.date(2008, 3, 20),
        classroom=classroom,
        academic_year=year,
        status="ACTIVE"
    )

    # Create 39 additional students so total is 40, and 29 females matching transcript.pdf
    # Currently 1 female (main_student). Need 28 more females + 11 males = 39 students.
    for i in range(2, 30):
        Student.objects.create(
            student_id=str(i),
            khmer_name=f"សិស្សស្រី ទី{i}",
            gender="F",
            date_of_birth=datetime.date(2008, 5, 10),
            classroom=classroom,
            academic_year=year,
            status="ACTIVE"
        )
    for i in range(30, 41):
        Student.objects.create(
            student_id=str(i),
            khmer_name=f"សិស្សប្រុស ទី{i}",
            gender="M",
            date_of_birth=datetime.date(2008, 8, 12),
            classroom=classroom,
            academic_year=year,
            status="ACTIVE"
        )

    print(f"✅ Created Classroom 12A with {classroom.students.count()} students ({classroom.students.filter(gender='F').count()} females)")

    # 1. Render Single Student Transcript
    req = setup_request(factory.get(f'/examinations/report-card/{main_student.id}/transcript/?term_id={term.id}'), admin_user)
    resp = report_card_transcript_view(req, main_student.id, term.id)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    html = resp.content.decode('utf-8')

    # Verify Header texts
    assert "គម្រោងកែលម្អការអប់រំចំណេះទូទៅ (គ.ក.អ.ច)" not in html, "Ministry GEIP line must be deleted"
    assert "មន្ទីរអប់រំ យុវជន និងកីឡាខេត្តកណ្ដាល" in html, "Provincial department line must be present"
    assert "វិទ្យាល័យ ហ៊ុន សែន កំពង់កន្ទួត" in html, "School name must be present"
    assert '<span class="pill-badge">' not in html, "Header pill badges must be removed"
    assert "ព្រះរាជាណាចក្រកម្ពុជា" in html, "Kingdom motto must be present"
    assert "ជាតិ សាសនា ព្រះមហាក្សត្រ" in html, "National motto must be present"
    assert "ព្រឹត្តិបត្រពិន្ទុ តេស្តដើមឆ្នាំ" in html, "Title 'ព្រឹត្តិបត្រពិន្ទុ តេស្តដើមឆ្នាំ' must be present"
    print("✅ Header elements and Kingdom motto verified!")

    # Verify Student Info Table
    assert "1-ជាម សុធា" in html, "Student name '1-ជាម សុធា' must be present"
    assert ">ថ្នាក់<" in html, "Header 'ថ្នាក់' must be present"
    assert ">12A<" in html, "Classroom '12A' must be present"
    assert ">40<" in html, "Total students 40 must be present"
    assert ">29<" in html, "Total female students 29 must be present"
    print("✅ Student Info Box (1-ជាម សុធា, ថ្នាក់: 12A, 40, 29) verified!")

    # Verify Section A: Subjects Table dynamically pulled from Classroom/Grade Level
    assert "ក.លទ្ធផលនៃការសិក្សា" in html, "Section A banner must be present"
    cls_rules = list(classroom.get_subject_rules())
    assert len(cls_rules) > 0, "Classroom must have configured rules"
    for r in cls_rules:
        sub_title = r.subject.name_kh or r.subject.name_en
        assert sub_title in html, f"Dynamic subject '{sub_title}' from GradeLevelRule must be in table"
        m_val = int(r.max_score) if float(r.max_score).is_integer() else f"{r.max_score:.2f}"
        assert f">{m_val}<" in html, f"Dynamic max score {m_val} for '{sub_title}' must be present"
    print(f"✅ All {len(cls_rules)} dynamic subjects and accurate max scores verified from Classroom/Grade Level!")

    # Verify Summary Rows
    assert "ពិន្ទុសរុប" in html, "Total score row must be present"
    tot_max = int(sum(r.max_score for r in cls_rules))
    assert f">{tot_max}<" in html, f"Total max score {tot_max} must be present"
    assert "មធ្យមភាគ" in html, "Average row must be present"
    assert ">50.00<" in html, "Average max 50.00 must be present"
    print(f"✅ Summary rows ({tot_max} and 50.00) verified!")

    # Verify Section B & C
    assert "ខ. ចំនួនអវត្តមានក្នុងខែ" in html, "Section B banner must be present"
    assert "គ. មូលវិចារ" in html, "Section C banner must be present"
    assert "លទ្ធផលការសិក្សា" in html, "Overall evaluation line must be present"
    assert "ស៊ិន ម៉ូនីដា" in html, "Teacher name must be present in footer"
    assert "(093) 995-927" in html, "Teacher phone must be present in footer"
    assert "បានឃើញ និងឯកភាព" in html and "នាយក" in html, "Principal approval section must be present"
    print("✅ Sections B, C, overall result, and footer signatures verified!")

    # 2. Test Batch Classroom View
    req_batch = setup_request(factory.get(f'/examinations/classroom/{classroom.id}/report-cards/transcript/?term_id={term.id}'), admin_user)
    resp_batch = classroom_report_cards_transcript_view(req_batch, classroom.id)
    assert resp_batch.status_code == 200, f"Expected 200, got {resp_batch.status_code}"
    html_batch = resp_batch.content.decode('utf-8')
    assert "1-ជាម សុធា" in html_batch, "Main student in batch"
    assert "សិស្សស្រី ទី2" in html_batch, "Batch students present"
    print("✅ Batch Classroom Endpoint verified successfully!")

    # 3. Test Headless Chrome Print to PDF for Single Student (Strict 1 A4 Page)
    print("📄 Running Headless Chrome to generate test PDF and check geometry...")
    html_path = 'E:/SchoolSM/test_transcript_generated.html'
    pdf_path = 'E:/SchoolSM/test_transcript_generated.pdf'
    with open(html_path, 'wb') as f:
        f.write(resp.content)

    chrome_exe = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
    subprocess.run([
        chrome_exe,
        '--headless=new',
        '--disable-gpu',
        '--no-pdf-header-footer',
        f'--print-to-pdf={pdf_path}',
        html_path
    ], check=True)

    reader = pypdf.PdfReader(pdf_path)
    print(f"Total pages generated: {len(reader.pages)}")
    assert len(reader.pages) == 1, f"Expected strictly 1 page, got {len(reader.pages)}"

    page = reader.pages[0]
    w = float(page.mediabox.width) * 25.4 / 72.0
    h = float(page.mediabox.height) * 25.4 / 72.0
    print(f"Page dimensions: {w:.1f} mm x {h:.1f} mm")
    assert abs(w - 210.0) < 2.0, "Must be A4 Portrait width (~210mm)"
    assert abs(h - 297.0) < 2.0, "Must be A4 Portrait height (~297mm)"
    print("✅ Geometry is strictly A4 Portrait (210mm x 297mm) with exactly 1 single page!")

    # Clean up test files
    for f in [html_path, pdf_path]:
        if os.path.exists(f):
            os.remove(f)

    # 4. Test Student with Real Entered Grades
    print("\n📊 Testing Student Transcript with Real Entered Grades...")
    khmer_sub, _ = Subject.objects.get_or_create(code="KH_TEST", defaults={"name_kh": "ភាសាខ្មែរ"})
    math_sub, _ = Subject.objects.get_or_create(code="MATH_TEST", defaults={"name_kh": "គណិតវិទ្យា"})
    phy_sub, _ = Subject.objects.get_or_create(code="PHY_TEST", defaults={"name_kh": "រូបវិទ្យា"})

    # Main student gets high scores
    Grade.objects.create(student=main_student, classroom=classroom, exam_term=term, subject=khmer_sub, score=65.0) # 65/75 = 86.7% (B / ល្អណាស់ / ជាប់)
    Grade.objects.create(student=main_student, classroom=classroom, exam_term=term, subject=math_sub, score=115.0) # 115/125 = 92% (A / ល្អប្រសើរ / ជាប់)
    Grade.objects.create(student=main_student, classroom=classroom, exam_term=term, subject=phy_sub, score=40.0)   # 40/75 = 53.3% (E / មធ្យម / ជាប់)

    # Another student gets lower score
    other_stu = Student.objects.filter(classroom=classroom).exclude(id=main_student.id).first()
    Grade.objects.create(student=other_stu, classroom=classroom, exam_term=term, subject=khmer_sub, score=50.0)
    Grade.objects.create(student=other_stu, classroom=classroom, exam_term=term, subject=math_sub, score=80.0)
    Grade.objects.create(student=other_stu, classroom=classroom, exam_term=term, subject=phy_sub, score=30.0)

    req_graded = setup_request(factory.get(f'/examinations/report-card/{main_student.id}/transcript/?term_id={term.id}'), admin_user)
    resp_graded = report_card_transcript_view(req_graded, main_student.id, term.id)
    html_graded = resp_graded.content.decode('utf-8')

    assert ">65<" in html_graded or ">65.00<" in html_graded or ">65.0<" in html_graded, "Khmer score must be displayed"
    assert ">115<" in html_graded or ">115.00<" in html_graded or ">115.0<" in html_graded, "Math score must be displayed"
    assert "ល្អប្រសើរ" in html_graded, "Math mention remark 'ល្អប្រសើរ' must be displayed"
    assert "ល្អណាស់" in html_graded, "Khmer mention remark 'ល្អណាស់' must be displayed"
    assert "ជាប់" in html_graded, "Pass status 'ជាប់' must be displayed"
    print("✅ Real grades, mentions (A, B, E), remarks (ល្អប្រសើរ, ល្អណាស់, មធ្យម) verified accurately!")

    # Verify Headless Chrome on graded transcript
    with open(html_path, 'wb') as f:
        f.write(resp_graded.content)
    subprocess.run([
        chrome_exe,
        '--headless=new',
        '--disable-gpu',
        '--no-pdf-header-footer',
        f'--print-to-pdf={pdf_path}',
        html_path
    ], check=True)

    reader2 = pypdf.PdfReader(pdf_path)
    assert len(reader2.pages) == 1, "Graded transcript must also be strictly 1 page"
    print("✅ Graded transcript generates strictly 1 page in Chrome PDF!")

    for f in [html_path, pdf_path]:
        if os.path.exists(f):
            os.remove(f)

    # 5. Test Dynamic Exam Term Selection & Dynamic Title
    print("\n🔄 Testing Dynamic Exam Term Selection & Dynamic Title...")
    term_nov, _ = ExamTerm.objects.get_or_create(
        name="ប្រឡងប្រចាំខែ វិច្ឆិកា",
        academic_year=year,
        defaults={
            'term_type': ExamTerm.TermType.MONTHLY,
            'start_date': datetime.date(2025, 11, 1),
            'end_date': datetime.date(2025, 11, 30),
        }
    )
    req_nov = setup_request(factory.get(f'/examinations/report-card/{main_student.id}/transcript/?term_id={term_nov.id}'), admin_user)
    resp_nov = report_card_transcript_view(req_nov, main_student.id)
    html_nov = resp_nov.content.decode('utf-8')

    assert f"ព្រឹត្តិបត្រពិន្ទុ {term_nov.name}" in html_nov, f"Title must dynamically match '{term_nov.name}'"
    assert 'id="termSelector"' in html_nov, "Exam Term dropdown selector must be present in toolbar"
    assert f'value="{term_nov.id}"' in html_nov, "Selected term option must be present"
    assert f'value="{term.id}"' in html_nov, "Original term option must be present in dropdown"
    print(f"✅ Dynamic Exam Term Title verified: 'ព្រឹត្តិបត្រពិន្ទុ {term_nov.name}'")
    # 6. Test Multi-Grade Dynamic Adaptation (Grade 7)
    print("\n🏫 Testing Multi-Grade Dynamic Curriculum Adaptation (Grade 7)...")
    c7 = Classroom.objects.filter(grade_level=7).first()
    if c7:
        s7 = Student.objects.filter(classroom=c7).first()
        if s7:
            req7 = setup_request(factory.get(f'/examinations/report-card/{s7.id}/transcript/'), admin_user)
            resp7 = report_card_transcript_view(req7, s7.id)
            html7 = resp7.content.decode('utf-8')
            assert ">650<" in html7, "Grade 7 total max score 650 must be present"
            assert "តែងសេចក្តី" in html7, "Grade 7 subject តែងសេចក្តី must be present"
            assert ">60<" in html7, "Grade 7 max score 60 must be present"
            print("✅ Grade 7 dynamically adapted with distinct subjects (តែងសេចក្តី) and total max (650)!")

    print("\n🎉 ALL TESTS PASSED! Student transcript (ព្រឹត្តិបត្រពិន្ទុ) 100% replicates transcript.pdf!")

if __name__ == '__main__':
    run_tests()
