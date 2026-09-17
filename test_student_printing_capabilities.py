import os
import sys
import django

sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import RequestFactory
from django.urls import reverse
from apps.students.models import Student
from apps.academics.models import Classroom
from apps.students.views import student_id_card, batch_student_id_cards, moeys_individual_student_roster, moeys_individual_student_roster_print
from apps.examinations.views import student_cumulative_dossier_view, homeroom_cumulative_dossier_batch_view
from apps.accounts.models import User
from apps.accounts.menu_registry import MENU_SECTIONS_CATALOG

def test_all_student_printing_options():
    print("=== Testing All Student Printing Capabilities ===")
    factory = RequestFactory()
    admin_user = User.objects.filter(is_superuser=True).first() or User.objects.filter(role='ADMIN').first()
    assert admin_user is not None, "Admin user must exist"

    student = Student.objects.select_related('classroom').first()
    assert student is not None, "At least one student must exist"
    print(f"  [1] Student loaded: {student.khmer_name} (ID: {student.student_id})")

    # 1. Test Single Student ID Card (ប័ណ្ណសម្គាល់ខ្លួនសិស្សម្នាក់ៗ)
    url_single = reverse('student_id_card', args=[student.id])
    req_single = factory.get(url_single)
    req_single.user = admin_user
    resp_single = student_id_card(req_single, pk=student.id)
    assert resp_single.status_code == 200, f"Expected 200, got {resp_single.status_code}"
    content_single = resp_single.content.decode('utf-8')
    assert "ប័ណ្ណសម្គាល់ខ្លួនសិស្ស" in content_single
    assert "filterGradeLevel" in content_single
    assert "filterClassroom" in content_single
    print("  [OK] Single Student ID Card: 200 OK with Grade & Class selectors")

    # 2. Test Batch Student ID Cards by Classroom (បោះពុម្ពជាថ្នាក់)
    if student.classroom:
        url_batch_class = f"{reverse('batch_student_id_cards')}?classroom={student.classroom.id}"
        req_batch_class = factory.get(url_batch_class)
        req_batch_class.user = admin_user
        resp_batch_class = batch_student_id_cards(req_batch_class)
        assert resp_batch_class.status_code == 200
        content_class = resp_batch_class.content.decode('utf-8')
        assert "a4-sheet" in content_class
        print(f"  [OK] Batch ID Cards by Classroom ({student.classroom.name}): 200 OK")

    # 3. Test Batch Student ID Cards by Grade Level (បោះពុម្ពជាកម្រិតថ្នាក់)
    grade = student.classroom.grade_level if student.classroom else 12
    url_batch_grade = f"{reverse('batch_student_id_cards')}?grade_level={grade}"
    req_batch_grade = factory.get(url_batch_grade)
    req_batch_grade.user = admin_user
    resp_batch_grade = batch_student_id_cards(req_batch_grade)
    assert resp_batch_grade.status_code == 200
    content_grade = resp_batch_grade.content.decode('utf-8')
    assert "a4-sheet" in content_grade
    assert "moeys-id-card" in content_grade
    print(f"  [OK] Batch ID Cards by Grade Level (ថ្នាក់ទី {grade}): 200 OK")

    # 4. Test Student Cumulative Academic Dossier (សៀវភៅសិក្ខាគារិក / សំណុំឯកសារព័ត៌មាននិងប្រវត្តិសិស្ស)
    url_dossier = reverse('student_cumulative_dossier_view', args=[student.id])
    req_dossier = factory.get(url_dossier)
    req_dossier.user = admin_user
    resp_dossier = student_cumulative_dossier_view(req_dossier, student_id=student.id)
    assert resp_dossier.status_code == 200
    content_dossier = resp_dossier.content.decode('utf-8')
    assert "សៀវភៅសិក្ខាគារិក" in content_dossier
    assert "CUMULATIVE ACADEMIC DOSSIER" in content_dossier
    print("  [OK] Single Student Cumulative Academic Dossier: 200 OK")

    # 5. Test Homeroom Batch Cumulative Dossier (សៀវភៅសិក្ខាគារិកជាថ្នាក់)
    if student.classroom:
        url_hr_dossier = reverse('homeroom_cumulative_dossier_batch_view', args=[student.classroom.id])
        req_hr_dossier = factory.get(url_hr_dossier)
        req_hr_dossier.user = admin_user
        resp_hr_dossier = homeroom_cumulative_dossier_batch_view(req_hr_dossier, classroom_id=student.classroom.id)
        assert resp_hr_dossier.status_code == 200
        print(f"  [OK] Batch Homeroom Cumulative Dossier for class ({student.classroom.name}): 200 OK")

    # 6. Test MoEYS Individual Student Extract Roster (សម្រង់ព័ត៌មានសិស្សម្នាក់ៗ - 35 ជួរឈរ)
    url_roster = f"{reverse('moeys_individual_student_roster')}?grade_level={grade}"
    req_roster = factory.get(url_roster)
    req_roster.user = admin_user
    resp_roster = moeys_individual_student_roster(req_roster)
    assert resp_roster.status_code == 200
    print("  [OK] MoEYS Individual Student Extract (35 Columns): 200 OK")

    url_roster_print = f"{reverse('moeys_individual_student_roster_print')}?grade_level={grade}"
    req_roster_print = factory.get(url_roster_print)
    req_roster_print.user = admin_user
    resp_roster_print = moeys_individual_student_roster_print(req_roster_print)
    assert resp_roster_print.status_code == 200
    print("  [OK] MoEYS Individual Student Extract Print View: 200 OK")

    # 7. Test Sidebar Menu Registry has batch_student_id_cards
    student_section = next((sec for sec in MENU_SECTIONS_CATALOG if sec.get('key') == 'sec_students'), None)
    assert student_section is not None, "sec_students must exist in sidebar"
    has_id_card_item = any(item.get('url_name') == 'batch_student_id_cards' for item in student_section.get('items', []))
    assert has_id_card_item, "batch_student_id_cards must be registered in sidebar menu"
    print("  [OK] batch_student_id_cards verified in sidebar menu registry")

    print("\n[ALL STUDENT PRINTING VERIFICATION TESTS PASSED SUCCESSFULLY!]")

if __name__ == '__main__':
    test_all_student_printing_options()
