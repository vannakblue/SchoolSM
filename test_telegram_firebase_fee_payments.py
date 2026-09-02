import os
import sys
import json
import django
from decimal import Decimal

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client, RequestFactory
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.academics.models import AcademicYear, Classroom, GradeLevel
from apps.students.models import Student, StudentCategory
from apps.finance.models import (
    MonthlyFeeConfig,
    MonthlyFeeRate,
    StudentMonthlyPayment,
    StudentMonthlyCategory,
    FeeCategory,
    Invoice,
    SchoolPaymentMethod,
    PaymentSlipSubmission,
    FirestorePaymentAuditLog
)
from apps.accounts.models import TelegramConfig
from apps.finance.telegram_bot import (
    handle_telegram_fees_message,
    handle_telegram_photo_message,
    process_telegram_fee_callback
)
from apps.finance.firebase_service import (
    get_firestore_db,
    log_fee_inquiry_to_firestore,
    log_qr_dispatch_to_firestore,
    log_payment_slip_to_firestore,
    log_payment_transaction_to_firestore,
    sync_all_local_payments_to_firestore,
    export_firestore_payment_logs
)
from apps.finance.views import (
    payment_logs_dashboard,
    export_payment_logs_excel,
    export_payment_logs_json,
    api_sync_firestore
)

User = get_user_model()

def run_tests():
    print("==================================================================")
    print("🚀 STARTING EXTENDED TEST SUITE: TELEGRAM BOT & FIRESTORE PAYMENTS")
    print("==================================================================")

    # 1. Setup Academic Year & Classroom
    year, _ = AcademicYear.objects.get_or_create(
        name="2025-2026 Payment Test",
        defaults={'start_date': timezone.now().date(), 'end_date': timezone.now().date(), 'is_current': True}
    )
    AcademicYear.objects.filter(id=year.id).update(is_current=True)
    AcademicYear.objects.exclude(id=year.id).update(is_current=False)

    grade, _ = GradeLevel.objects.get_or_create(grade_number=8, defaults={'name': 'ថ្នាក់ទី ៨', 'order': 2})
    classroom, _ = Classroom.objects.get_or_create(
        name="8A-PayTest",
        defaults={'code': '8A-PAY', 'grade_level': 8, 'academic_year': year, 'capacity': 40}
    )
    classroom.academic_year = year
    classroom.save()

    # 2. Setup Student & Categories
    cat_normal, _ = StudentCategory.objects.get_or_create(name="ទូទៅ (Normal Pay)", defaults={'code': 'NORMAL_PAY'})
    student, _ = Student.objects.get_or_create(
        student_id="2624099",
        defaults={
            'khmer_name': 'សុខ ចិន្តា',
            'latin_name': 'Sok Chenda',
            'gender': Student.Gender.FEMALE,
            'date_of_birth': timezone.now().date(),
            'classroom': classroom,
            'academic_year': year,
            'category': cat_normal,
            'fee_start_month': 10,
            'fee_end_month': 8,
            'telegram_chat_id': '987654321'
        }
    )
    student.classroom = classroom
    student.academic_year = year
    student.save()

    # 3. Setup Early-Year Invoice (ថវិកាដើមឆ្នាំ)
    fee_cat, _ = FeeCategory.objects.get_or_create(name="ថវិកាដើមឆ្នាំ & ឯកសណ្ឋាន", defaults={'default_amount': Decimal('50.00')})
    invoice, _ = Invoice.objects.get_or_create(
        student=student,
        fee_category=fee_cat,
        academic_year=year,
        defaults={
            'original_amount': Decimal('50.00'),
            'final_amount': Decimal('50.00'),
            'paid_amount': Decimal('0.00'),
            'due_date': timezone.now().date(),
            'status': Invoice.Status.UNPAID
        }
    )

    # 4. Setup Monthly Fee Config (ថ្លៃទឹកភ្លើង)
    config = MonthlyFeeConfig.get_or_create_for_year(year)
    config.start_month = 10
    config.end_month = 8
    config.ticked_months = [10, 11, 12, 1]
    config.save()

    for m in [10, 11, 12, 1]:
        MonthlyFeeRate.objects.update_or_create(
            config=config,
            category=cat_normal,
            month=m,
            defaults={'amount': Decimal('20000.00')}
        )

    # 5. Setup Bank Payment Method (ABA & Bakong)
    bank_method, _ = SchoolPaymentMethod.objects.update_or_create(
        bank_name="ABA Bank",
        account_number="000 888 999",
        defaults={
            'account_name': "SCHOOL MANAGEMENT TEST",
            'currency': "KHR",
            'is_active': True,
            'is_default': True,
            'instructions': "ស្កេនដើម្បីបង់ប្រាក់"
        }
    )

    # 6. Setup Telegram Config
    tconfig, _ = TelegramConfig.objects.get_or_create(
        id=1,
        defaults={'bot_token': '123456:TEST_BOT_TOKEN', 'chat_id': '-10099887766', 'is_active': True}
    )
    tconfig.is_active = True
    tconfig.bot_token = '123456:TEST_BOT_TOKEN'
    tconfig.chat_id = '-10099887766'
    tconfig.save()

    print("✅ Initial Test Data setup completed.")

    # =========================================================================
    # TEST CASE 1: Student ID Inquiry via Telegram Bot Message
    # =========================================================================
    print("\n--- TEST CASE 1: Student ID Fee Inquiry ---")
    initial_log_count = FirestorePaymentAuditLog.objects.count()

    # Simulate parent typing raw student ID "2624099"
    msg_student_id = {
        'chat': {'id': 987654321},
        'from': {'first_name': 'Dara', 'username': 'dara_parent', 'id': 987654321},
        'text': '2624099'
    }
    handle_telegram_fees_message(msg_student_id)

    new_logs = FirestorePaymentAuditLog.objects.filter(
        student=student,
        event_type=FirestorePaymentAuditLog.EventType.INQUIRY
    )
    assert new_logs.exists(), "FirestorePaymentAuditLog inquiry entry should be created!"
    latest_inquiry = new_logs.latest('created_at')
    print(f"✅ Telegram Fee Inquiry logged successfully: {latest_inquiry.student_name} -> Total Due: {latest_inquiry.amount:,.0f} {latest_inquiry.currency}")

    # =========================================================================
    # TEST CASE 2: QR Code Callback Dispatch
    # =========================================================================
    print("\n--- TEST CASE 2: Bank QR Code Callback Dispatch ---")
    qr_res = process_telegram_fee_callback(
        callback_data=f"feeqr:{student.id}",
        user_disp="Dara (@dara_parent)",
        chat_id=987654321,
        message_id=101
    )
    assert qr_res['success'] is True, "QR callback should succeed!"
    qr_logs = FirestorePaymentAuditLog.objects.filter(
        student=student,
        event_type=FirestorePaymentAuditLog.EventType.QR_DISPATCH
    )
    assert qr_logs.exists(), "QR dispatch log should be recorded!"
    print(f"✅ QR Code dispatch processed: {qr_res['message']}")

    # =========================================================================
    # TEST CASE 3: Payment Slip Submission & Admin Approval Flow
    # =========================================================================
    print("\n--- TEST CASE 3: Parent Slip Submission & Admin Approval ---")
    photo_msg = {
        'chat': {'id': 987654321},
        'from': {'first_name': 'Dara', 'username': 'dara_parent', 'id': 987654321},
        'photo': [{'file_id': 'TEST_PHOTO_FILE_ID_123', 'file_size': 1024}],
        'caption': 'បង់ថ្លៃទឹកភ្លើង 2624099'
    }
    handle_telegram_photo_message(photo_msg)

    slip = PaymentSlipSubmission.objects.filter(student=student).first()
    assert slip is not None, "PaymentSlipSubmission should be created!"
    assert slip.status == PaymentSlipSubmission.Status.PENDING, "Initial status should be PENDING"
    print(f"✅ Slip submission created: #{slip.id} for student {slip.student.khmer_name}")

    # Admin Approves the slip via Telegram callback
    admin_user, _ = User.objects.get_or_create(username='admin_reviewer', defaults={'role': 'ADMIN', 'is_superuser': True})
    approve_res = process_telegram_fee_callback(
        callback_data=f"feereceipt:approve:{slip.id}",
        user_disp="Admin Manager (@admin_manager)",
        chat_id=987654321,
        message_id=202
    )
    assert approve_res['success'] is True, "Approval callback should succeed!"

    slip.refresh_from_db()
    assert slip.status == PaymentSlipSubmission.Status.APPROVED, "Slip status should be APPROVED!"
    
    # Check that monthly payments were updated to PAID
    payments = StudentMonthlyPayment.objects.filter(student=student, academic_year=year, month__in=[10, 11, 12, 1])
    for p in payments:
        assert p.status == StudentMonthlyPayment.Status.PAID, f"Payment for month {p.month} should be PAID!"
    print(f"✅ Slip approved and {payments.count()} monthly payments marked as PAID!")

    # =========================================================================
    # TEST CASE 4: Google Firebase Firestore Client & Sync
    # =========================================================================
    print("\n--- TEST CASE 4: Google Firebase Firestore Sync Service ---")
    db = get_firestore_db()
    print(f"Firestore Client Connection Status: {'CONNECTED' if db else 'OFFLINE (Local Mode)'}")

    sync_res = sync_all_local_payments_to_firestore()
    print(f"Sync Results: {sync_res}")
    assert sync_res['success'] is True, "Sync to Firestore should execute successfully!"

    cloud_records = export_firestore_payment_logs(limit=10)
    print(f"Exported {len(cloud_records)} payment logs from Firestore/Audit mirror.")
    assert len(cloud_records) > 0, "Should have exported payment records!"

    # =========================================================================
    # TEST CASE 5: Admin Live Dashboard & Any-Time Backup Suite
    # =========================================================================
    print("\n--- TEST CASE 5: Admin Live Dashboard & Any-Time Backup ---")
    factory = RequestFactory()
    
    # Dashboard view test
    req_dash = factory.get('/finance/payment-logs/')
    req_dash.user = admin_user
    resp_dash = payment_logs_dashboard(req_dash)
    assert resp_dash.status_code == 200, f"Dashboard should return 200 OK, got {resp_dash.status_code}"
    print("✅ Payment logs dashboard view returned HTTP 200 OK.")

    # Excel Backup export test
    req_excel = factory.get('/finance/payment-logs/export-excel/')
    req_excel.user = admin_user
    resp_excel = export_payment_logs_excel(req_excel)
    assert resp_excel.status_code == 200, f"Excel export should return 200 OK, got {resp_excel.status_code}"
    assert 'spreadsheetml' in resp_excel['Content-Type'], "Should return Excel content type"
    assert len(resp_excel.content) > 1000, "Excel output should have content!"
    print(f"✅ Excel Backup generated successfully ({len(resp_excel.content):,} bytes).")

    # JSON Snapshot export test
    req_json = factory.get('/finance/payment-logs/export-json/')
    req_json.user = admin_user
    resp_json = export_payment_logs_json(req_json)
    assert resp_json.status_code == 200, f"JSON export should return 200 OK, got {resp_json.status_code}"
    parsed_json = json.loads(resp_json.content.decode('utf-8'))
    assert 'monthly_payments' in parsed_json, "JSON should contain monthly_payments"
    assert 'invoices' in parsed_json, "JSON should contain invoices"
    print(f"✅ JSON Snapshot generated successfully ({len(parsed_json['monthly_payments'])} monthly payments, {len(parsed_json['firestore_logs'])} firestore logs).")

    print("\n==================================================================")
    print("🎉 ALL TEST CASES PASSED SUCCESSFULLY!")
    print("==================================================================")


if __name__ == '__main__':
    run_tests()
