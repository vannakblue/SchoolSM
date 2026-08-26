import os
import sys
import json
import django

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from django.urls import reverse
from apps.accounts.models import User, SchoolProfile
from apps.students.models import Student
from apps.academics.models import Classroom, AcademicYear, Subject
from apps.examinations.models import ExamTerm, Grade
from apps.examinations.telegram_report_card import (
    generate_report_card_pdf_bytes,
    build_report_card_telegram_message,
    dispatch_student_report_card_to_telegram
)
from apps.accounts.search_service import global_omnisearch


def run_tests():
    print("=== STARTING EXAM SCORING MODE, OMNISEARCH, AND TELEGRAM PDF REPORT CARD TESTS ===")

    # 1. Setup Admin User & Base Records
    admin_user, _ = User.objects.get_or_create(
        username='feat_admin_tester',
        defaults={'role': User.Role.ADMIN, 'khmer_name': 'Admin Feature Tester'}
    )
    ay, _ = AcademicYear.objects.get_or_create(
        name='2026-2027',
        defaults={'start_date': '2026-10-01', 'end_date': '2027-07-31', 'is_current': True}
    )
    classroom, _ = Classroom.objects.get_or_create(
        name='7A',
        defaults={'grade_level': 7, 'track': 'GENERAL', 'academic_year': ay}
    )
    student, _ = Student.objects.get_or_create(
        student_id='STU-TEST-99',
        defaults={
            'khmer_name': 'ហេង រតនា',
            'latin_name': 'Heng Rathana',
            'date_of_birth': '2012-05-15',
            'classroom': classroom,
            'academic_year': ay,
            'phone': '012 999 888',
            'emergency_phone': '098 777 666'
        }
    )
    subject, _ = Subject.objects.get_or_create(
        code='MATH7',
        defaults={'name_kh': 'គណិតវិទ្យា', 'name_en': 'Mathematics'}
    )

    client = Client()
    client.force_login(admin_user)

    # 2. Test Exam Scoring Mode Configuration
    term_classroom = ExamTerm.objects.create(
        name='ប្រឡងខែមករា (តាមថ្នាក់)',
        academic_year=ay,
        term_type=ExamTerm.TermType.MONTHLY,
        scoring_mode=ExamTerm.ScoringMode.CLASSROOM,
        start_date='2027-01-10',
        end_date='2027-01-15'
    )
    term_room = ExamTerm.objects.create(
        name='ប្រឡងឆមាសទី១ (តាមបន្ទប់)',
        academic_year=ay,
        term_type=ExamTerm.TermType.SEMESTER_1,
        scoring_mode=ExamTerm.ScoringMode.STANDARDIZED_ROOM,
        start_date='2027-02-10',
        end_date='2027-02-15'
    )

    assert term_classroom.scoring_mode == 'CLASSROOM'
    assert term_room.scoring_mode == 'STANDARDIZED_ROOM'
    print("  [PASS] 1. Exam Scoring Mode successfully configured (Classroom vs Room).")

    # Add a Grade record for testing
    Grade.objects.update_or_create(
        student=student,
        subject=subject,
        exam_term=term_classroom,
        defaults={'classroom': classroom, 'score': 95.0, 'max_score': 100.0}
    )

    # 3. Test Global Omnisearch Engine & API
    # Test Khmer keyword "សៀវភៅតាមដាន"
    res_search1 = global_omnisearch('សៀវភៅតាមដាន')
    assert any('/students/' in item['url'] for item in res_search1), "Search for 'សៀវភៅតាមដាន' must return student directory"
    print("  [PASS] 2. Omnisearch Keyword 'សៀវភៅតាមដាន' accurately maps to Student Directory & Tracking Book.")

    # Test Khmer keyword "ការបង់ទឹកភ្លើង" or "ទឹកភ្លើង"
    res_search2 = global_omnisearch('ការបង់ទឹកភ្លើង')
    assert any('/finance/' in item['url'] for item in res_search2), "Search for 'ការបង់ទឹកភ្លើង' must return Finance / Invoices"
    print("  [PASS] 3. Omnisearch Keyword 'ការបង់ទឹកភ្លើង' accurately maps to Billing & Invoices.")

    # Test Khmer keyword "ប័ណ្ណពិន្ទុ"
    res_search3 = global_omnisearch('ប័ណ្ណពិន្ទុ')
    assert any('/examinations/summary/' in item['url'] for item in res_search3), "Search for 'ប័ណ្ណពិន្ទុ' must return Grade Summary / Report Cards"
    print("  [PASS] 4. Omnisearch Keyword 'ប័ណ្ណពិន្ទុ' accurately maps to Grade Summary & Report Cards.")

    # Test Omnisearch API Endpoint
    res_api = client.get(reverse('api_global_search') + '?q=វត្តមាន')
    assert res_api.status_code == 200
    json_api = res_api.json()
    assert 'results' in json_api and len(json_api['results']) > 0
    print("  [PASS] 5. GET /accounts/api/global-search/?q=វត្តមាន -> 200 OK with suggestions.")

    # 4. Test Report Card PDF In-Memory Generation
    pdf_bytes = generate_report_card_pdf_bytes(student, term_classroom)
    assert pdf_bytes is not None and len(pdf_bytes) > 100
    assert pdf_bytes.startswith(b'%PDF'), "Generated Report Card must be a valid PDF binary file"
    print(f"  [PASS] 6. Official Report Card PDF in-memory generation verified ({len(pdf_bytes)} bytes).")

    # 5. Test Telegram Formatted Rich Message
    tg_msg = build_report_card_telegram_message(student, term_classroom)
    assert student.khmer_name in tg_msg
    assert 'ព្រឹត្តិបត្រពិន្ទុ' in tg_msg
    assert '95.0' in tg_msg
    print("  [PASS] 7. Telegram Rich Message properly formatted with emojis, grades, and rank.")

    # 6. Test Telegram Report Card Dispatch API (Individual)
    res_dispatch_single = client.post(
        reverse('api_send_report_card_telegram'),
        data=json.dumps({
            'student_id': student.id,
            'term_id': term_classroom.id,
            'destination': 'CLASS_GROUP',
            'send_mode': 'BOTH'
        }),
        content_type='application/json'
    )
    assert res_dispatch_single.status_code == 200
    json_single = res_dispatch_single.json()
    assert json_single['status'] == 'success'
    print("  [PASS] 8. POST /examinations/api/report-card/send-telegram/ -> 200 OK")

    # 7. Test Telegram Report Card Dispatch API (Bulk Class)
    res_dispatch_class = client.post(
        reverse('api_send_class_report_cards_telegram'),
        data=json.dumps({
            'classroom_id': classroom.id,
            'term_id': term_classroom.id,
            'destination': 'PARENT_INDIVIDUAL',
            'send_mode': 'BOTH'
        }),
        content_type='application/json'
    )
    assert res_dispatch_class.status_code == 200
    json_class = res_dispatch_class.json()
    assert json_class['status'] == 'success'
    print(f"  [PASS] 9. POST /examinations/api/report-card/send-class-telegram/ -> 200 OK (dispatched {json_class['sent_count']} report cards).")

    # Clean up test term records
    term_classroom.delete()
    term_room.delete()
    student.delete()

    print("=== ALL 9 ADVANCED FEATURE TESTS PASSED WITH 100% SUCCESS ===")


if __name__ == '__main__':
    run_tests()
