import os
import django
import io

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from apps.academics.models import Classroom, GradeLevel, AcademicYear
from apps.students.models import Student
import pypdf

User = get_user_model()

def run_tests():
    print("=== STARTING ONLINE TOOLS SUITE VERIFICATION ===")

    user, created = User.objects.get_or_create(
        username='tool_tester_admin',
        defaults={'role': User.Role.ADMIN, 'email': 'admin@test.com'}
    )
    if created:
        user.set_password('testpass123')
        user.save()

    client = Client()
    client.force_login(user)

    # 1. Test All Tool Views URLs
    tool_routes = [
        ('tools_hub', reverse('tools_hub')),
        ('tool_pdf_merge', reverse('tool_pdf_merge')),
        ('tool_pdf_split', reverse('tool_pdf_split')),
        ('tool_pdf_to_word_excel', reverse('tool_pdf_to_word_excel')),
        ('tool_images_to_pdf', reverse('tool_images_to_pdf')),
        ('tool_doc_scanner', reverse('tool_doc_scanner')),
        ('tool_image_editor', reverse('tool_image_editor')),
        ('tool_id_photo_maker', reverse('tool_id_photo_maker')),
        ('tool_image_compressor', reverse('tool_image_compressor')),
        ('tool_qr_generator', reverse('tool_qr_generator')),
        ('tool_qr_scanner', reverse('tool_qr_scanner')),
        ('tool_khmer_number_converter', reverse('tool_khmer_number_converter')),
        ('tool_text_analyzer', reverse('tool_text_analyzer')),
        ('tool_voice_typing', reverse('tool_voice_typing')),
        ('tool_classroom_picker', reverse('tool_classroom_picker')),
        ('tool_calculator_converter', reverse('tool_calculator_converter')),
    ]

    for name, url in tool_routes:
        res = client.get(url)
        assert res.status_code == 200, f"Route {name} ({url}) returned status {res.status_code}"
        print(f"  [PASS] Route {name} -> 200 OK")

    # 2. Test Classroom Students API
    year, _ = AcademicYear.objects.get_or_create(
        name="2025-2026",
        defaults={"start_date": "2025-10-01", "end_date": "2026-07-31", "is_current": True}
    )
    grade, _ = GradeLevel.objects.get_or_create(
        grade_number=7,
        track='GENERAL',
        defaults={'name': 'ថ្នាក់ទី ៧'}
    )
    classroom, _ = Classroom.objects.get_or_create(
        code="7A-TEST",
        academic_year=year,
        defaults={"name": "ថ្នាក់ទី ៧A-TEST", "grade_level": 7, "capacity": 40}
    )
    student, _ = Student.objects.get_or_create(
        student_id="ST-TOOLS-001",
        defaults={
            "khmer_name": "សុក វិបុល",
            "latin_name": "Sok Vibol",
            "gender": Student.Gender.MALE,
            "date_of_birth": "2012-05-10",
            "classroom": classroom,
            "academic_year": year,
        }
    )

    api_url = reverse('api_tool_classroom_students', kwargs={'classroom_id': classroom.id})
    res = client.get(api_url)
    assert res.status_code == 200, f"API {api_url} returned {res.status_code}"
    json_data = res.json()
    assert json_data['success'] is True, "API success should be True"
    assert len(json_data['students']) >= 1, "Should return at least 1 student"
    print(f"  [PASS] API classroom_students returned {len(json_data['students'])} student(s)")

    # 3. Test Backend PDF Merge API
    writer1 = pypdf.PdfWriter()
    writer1.add_blank_page(width=200, height=200)
    pdf1_bytes = io.BytesIO()
    writer1.write(pdf1_bytes)
    pdf1_bytes.seek(0)

    writer2 = pypdf.PdfWriter()
    writer2.add_blank_page(width=200, height=200)
    pdf2_bytes = io.BytesIO()
    writer2.write(pdf2_bytes)
    pdf2_bytes.seek(0)

    pdf1_file = io.BytesIO(pdf1_bytes.getvalue())
    pdf1_file.name = 'test1.pdf'
    pdf2_file = io.BytesIO(pdf2_bytes.getvalue())
    pdf2_file.name = 'test2.pdf'

    merge_res = client.post(reverse('api_tool_pdf_merge'), {'pdf_files': [pdf1_file, pdf2_file]})
    assert merge_res.status_code == 200, f"PDF Merge API returned {merge_res.status_code}"
    assert merge_res['Content-Type'] == 'application/pdf', "Merge response should be application/pdf"
    print("  [PASS] Backend API PDF Merge executed successfully")

    # 4. Test Backend PDF to Word API
    pdf_word_file = io.BytesIO(pdf1_bytes.getvalue())
    pdf_word_file.name = 'sample.pdf'
    docx_res = client.post(reverse('api_tool_pdf_to_docx'), {'pdf_file': pdf_word_file})
    assert docx_res.status_code == 200, f"PDF to Word API returned {docx_res.status_code}"
    print("  [PASS] Backend API PDF to Word executed successfully")

    # 5. Test Backend PDF to Excel API
    pdf_excel_file = io.BytesIO(pdf1_bytes.getvalue())
    pdf_excel_file.name = 'sample.pdf'
    excel_res = client.post(reverse('api_tool_pdf_to_excel'), {'pdf_file': pdf_excel_file})
    assert excel_res.status_code == 200, f"PDF to Excel API returned {excel_res.status_code}"
    print("  [PASS] Backend API PDF to Excel executed successfully")

    # 6. Test Backend Images to PDF API
    from PIL import Image as PILImage
    img_sample = PILImage.new('RGB', (100, 100), color='red')
    img_io = io.BytesIO()
    img_sample.save(img_io, format='JPEG')
    img_io.seek(0)
    img_file = io.BytesIO(img_io.getvalue())
    img_file.name = 'photo.jpg'

    img_pdf_res = client.post(reverse('api_tool_images_to_pdf'), {
        'images': [img_file],
        'orientation': 'portrait',
        'pageSize': 'a4',
        'margin': 'small',
        'docTitle': 'Test_Document'
    })
    assert img_pdf_res.status_code == 200, f"Images to PDF API returned {img_pdf_res.status_code}"
    assert img_pdf_res['Content-Type'] == 'application/pdf', "Response should be application/pdf"
    print("  [PASS] Backend API Images to PDF executed successfully")

    print("\n=== ALL ONLINE TOOLS TESTS PASSED WITH 100% SUCCESS! ===")

if __name__ == '__main__':
    run_tests()
