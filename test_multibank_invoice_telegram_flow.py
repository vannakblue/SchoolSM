import os
import sys
import json
import django
from decimal import Decimal

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
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
    PaymentTransaction,
    SchoolPaymentMethod,
    PaymentSlipSubmission
)
from apps.accounts.models import TelegramConfig
from apps.finance.telegram_bot import (
    handle_telegram_fees_message,
    process_telegram_fee_callback,
    send_combined_student_fee_statement,
    send_payment_confirmation_and_banks,
    send_bank_qr_code,
    execute_and_generate_invoice
)

User = get_user_model()

def run_tests():
    print("==================================================================")
    print("🚀 RUNNING MULTI-BANK PAYMENT & TELEGRAM INVOICE TEST SUITE")
    print("==================================================================")

    # 1. Setup Academic Year & Classroom
    year, _ = AcademicYear.objects.get_or_create(
        name="2026-2027",
        defaults={'start_date': timezone.now().date(), 'end_date': timezone.now().date(), 'is_current': True}
    )
    AcademicYear.objects.filter(id=year.id).update(is_current=True)

    grade7, _ = GradeLevel.objects.get_or_create(grade_number=7, defaults={'name': 'ថ្នាក់ទី ៧', 'order': 1})
    classroom, _ = Classroom.objects.get_or_create(
        name="7A-Test",
        defaults={'code': '7A-TEST', 'grade_level': 7, 'academic_year': year, 'capacity': 40}
    )

    # 2. Setup Student
    cat_normal, _ = StudentCategory.objects.get_or_create(name="ទូទៅ (Normal Pay)", defaults={'code': 'NORMAL_PAY'})
    student, _ = Student.objects.get_or_create(
        student_id="2624088",
        defaults={
            'khmer_name': 'លី ម៉េងហុង',
            'latin_name': 'Ly Menghong',
            'gender': Student.Gender.MALE,
            'date_of_birth': timezone.now().date(),
            'classroom': classroom,
            'academic_year': year,
            'category': cat_normal,
            'fee_start_month': 10,
            'fee_end_month': 8,
            'telegram_chat_id': '555123456'
        }
    )
    student.classroom = classroom
    student.academic_year = year
    student.save()

    # 3. Setup Early-Year Enrollment Invoice
    fee_cat, _ = FeeCategory.objects.get_or_create(
        name="ថ្លៃចុះឈ្មោះចូលរៀនដើមឆ្នាំ",
        defaults={'default_amount': Decimal('25.00'), 'description': 'សេវាចុះឈ្មោះ សៀវភៅតាមដាន និងកាតសិស្ស'}
    )
    invoice, _ = Invoice.objects.get_or_create(
        student=student,
        fee_category=fee_cat,
        academic_year=year,
        defaults={
            'original_amount': Decimal('25.00'),
            'final_amount': Decimal('25.00'),
            'paid_amount': Decimal('0.00'),
            'due_date': timezone.now().date(),
            'status': Invoice.Status.UNPAID,
            'notes': 'ថ្លៃចុះឈ្មោះដើមឆ្នាំសម្រាប់ថ្នាក់ទី៧'
        }
    )
    invoice.payments.all().delete()
    invoice.paid_amount = Decimal('0.00')
    invoice.status = Invoice.Status.UNPAID
    invoice.save()

    # Verify Invoice Clarified Purpose
    purpose = invoice.get_clarified_purpose()
    print(f"✅ Invoice Clarified Purpose: {purpose}")
    assert "ថ្លៃចុះឈ្មោះចូលរៀនដើមឆ្នាំ" in purpose
    assert "7A-Test" in purpose

    # 4. Setup Monthly Fee Config (ថ្លៃទឹកភ្លើង)
    config = MonthlyFeeConfig.get_or_create_for_year(year)
    config.start_month = 10
    config.end_month = 8
    config.ticked_months = [10, 11]
    config.save()

    for m in [10, 11]:
        MonthlyFeeRate.objects.update_or_create(
            config=config,
            category=cat_normal,
            month=m,
            defaults={'amount': Decimal('20000.00')}
        )
        StudentMonthlyPayment.objects.filter(student=student, academic_year=year, month=m).delete()

    # 5. Setup Multi-Bank Payment Methods: ABA, Bakong KHQR, ACLEDA, Canadia
    SchoolPaymentMethod.objects.filter(account_number__in=["ABA-001", "BK-002", "ACL-003", "CAN-004"]).delete()

    aba_bank = SchoolPaymentMethod.objects.create(
        bank_type=SchoolPaymentMethod.BankType.ABA,
        bank_name="ABA Bank",
        account_name="SCHOOL MANAGEMENT (ABA)",
        account_number="ABA-001",
        currency="BOTH",
        is_default=True,
        is_active=True
    )
    bakong_khqr = SchoolPaymentMethod.objects.create(
        bank_type=SchoolPaymentMethod.BankType.BAKONG,
        bank_name="Bakong KHQR",
        account_name="SCHOOL MANAGEMENT (BAKONG)",
        account_number="BK-002",
        khqr_payload="00020101021229300012bakong@abaa...testpayload",
        currency="KHR",
        is_default=False,
        is_active=True
    )
    acleda_bank = SchoolPaymentMethod.objects.create(
        bank_type=SchoolPaymentMethod.BankType.ACLEDA,
        bank_name="ACLEDA Bank Plc.",
        account_name="SCHOOL MANAGEMENT (ACLEDA)",
        account_number="ACL-003",
        currency="KHR",
        is_default=False,
        is_active=True
    )
    canadia_bank = SchoolPaymentMethod.objects.create(
        bank_type=SchoolPaymentMethod.BankType.CANADIA,
        bank_name="Canadia Bank",
        account_name="SCHOOL MANAGEMENT (CANADIA)",
        account_number="CAN-004",
        currency="KHR",
        is_default=False,
        is_active=True
    )

    # 6. Telegram Config
    tconfig, _ = TelegramConfig.objects.get_or_create(
        id=1,
        defaults={'bot_token': '123456:TEST_BOT_TOKEN', 'chat_id': '-10099887766', 'is_active': True}
    )

    print("✅ Initial data setup completed.")

    # -------------------------------------------------------------------------
    # TEST CASE 1: Student ID Inquiry -> Returns Clarified Breakdown
    # -------------------------------------------------------------------------
    print("\n--- TEST CASE 1: Student ID Inquiry in Telegram Bot ---")
    msg_student_id = {
        'chat': {'id': 555123456},
        'from': {'first_name': 'Heng', 'username': 'heng_parent', 'id': 555123456},
        'text': '2624088'
    }
    handle_telegram_fees_message(msg_student_id)
    print("✅ Handled Student ID inquiry successfully.")

    # -------------------------------------------------------------------------
    # TEST CASE 2: Click 'Proceed to Pay' -> Confirmation & Multi-Bank Options
    # -------------------------------------------------------------------------
    print("\n--- TEST CASE 2: Proceed to Pay Callback (feeproc) ---")
    res_proc = process_telegram_fee_callback(
        callback_data=f"feeproc:{student.id}",
        user_disp="Heng Parent",
        chat_id=555123456,
        message_id=200
    )
    assert res_proc['success'] is True, "feeproc should succeed"
    print(f"✅ Proceed to pay confirmation dispatched: {res_proc['message']}")

    # -------------------------------------------------------------------------
    # TEST CASE 3: Select Bank (feebank) -> ACLEDA / Canadia / Bakong QR
    # -------------------------------------------------------------------------
    print("\n--- TEST CASE 3: Bank Choice Callback (feebank) for ACLEDA & Canadia ---")
    res_acleda = process_telegram_fee_callback(
        callback_data=f"feebank:{student.id}:{acleda_bank.id}",
        user_disp="Heng Parent",
        chat_id=555123456,
        message_id=201
    )
    assert res_acleda['success'] is True
    print(f"✅ ACLEDA QR Code dispatch: {res_acleda['message']}")

    res_canadia = process_telegram_fee_callback(
        callback_data=f"feebank:{student.id}:{canadia_bank.id}",
        user_disp="Heng Parent",
        chat_id=555123456,
        message_id=202
    )
    assert res_canadia['success'] is True
    print(f"✅ Canadia Bank QR Code dispatch: {res_canadia['message']}")

    # -------------------------------------------------------------------------
    # TEST CASE 4: Verification & Automated Official Invoice Generation (feeverify)
    # -------------------------------------------------------------------------
    print("\n--- TEST CASE 4: Verification & Official Invoice Generation (feeverify) ---")
    res_verify = process_telegram_fee_callback(
        callback_data=f"feeverify:{student.id}:{aba_bank.id}",
        user_disp="Heng Parent",
        chat_id=555123456,
        message_id=203
    )
    assert res_verify['success'] is True, "feeverify should succeed"
    assert 'invoice_no' in res_verify, "Response must contain invoice_no"
    print(f"✅ Verified & Generated Invoice: {res_verify['invoice_no']}")
    assert "🧾 *វិក្កយបត្រផ្លូវការ / OFFICIAL INVOICE*" in res_verify['updated_text']
    assert "ថ្លៃចុះឈ្មោះចូលរៀនដើមឆ្នាំ" in res_verify['updated_text']
    assert "ថ្លៃទឹក-ភ្លើងប្រចាំខែ" in res_verify['updated_text']

    # Verify DB State
    invoice.refresh_from_db()
    assert invoice.status == Invoice.Status.PAID, "Invoice must be marked PAID"
    assert invoice.paid_amount == Decimal('25.00')

    monthly_10 = StudentMonthlyPayment.objects.get(student=student, academic_year=year, month=10)
    assert monthly_10.status == StudentMonthlyPayment.Status.PAID
    monthly_11 = StudentMonthlyPayment.objects.get(student=student, academic_year=year, month=11)
    assert monthly_11.status == StudentMonthlyPayment.Status.PAID
    print("✅ Database records verified: Invoices & Utilities marked as PAID.")

    # -------------------------------------------------------------------------
    # TEST CASE 5: Admin Bank Method Management API (Toggle Active & Set Default)
    # -------------------------------------------------------------------------
    print("\n--- TEST CASE 5: Admin Bank Settings API ---")
    client = Client()
    admin_user = User.objects.filter(role='ADMIN').first()
    if not admin_user:
        admin_user = User.objects.create_superuser('admin_test_bank', 'admin@test.com', 'pass123')
        admin_user.role = 'ADMIN'
        admin_user.save()
    client.force_login(admin_user)

    # Toggle active
    toggle_resp = client.post('/finance/payment-logs/methods/', {
        'action': 'toggle_active',
        'method_id': canadia_bank.id
    })
    assert toggle_resp.status_code == 302
    canadia_bank.refresh_from_db()
    assert canadia_bank.is_active is False, "Canadia Bank should now be inactive"
    print("✅ Successfully toggled Canadia Bank to Inactive.")

    toggle_resp2 = client.post('/finance/payment-logs/methods/', {
        'action': 'toggle_active',
        'method_id': canadia_bank.id
    })
    assert toggle_resp2.status_code == 302
    canadia_bank.refresh_from_db()
    assert canadia_bank.is_active is True, "Canadia Bank should now be active again"
    print("✅ Successfully toggled Canadia Bank back to Active.")

    # Set Default
    set_def_resp = client.post('/finance/payment-logs/methods/', {
        'action': 'set_default',
        'method_id': bakong_khqr.id
    })
    assert set_def_resp.status_code == 302
    bakong_khqr.refresh_from_db()
    aba_bank.refresh_from_db()
    assert bakong_khqr.is_default is True
    assert aba_bank.is_default is False
    print("✅ Successfully set Bakong KHQR as default bank.")

    print("\n==================================================================")
    print("🎉 ALL MULTI-BANK & INVOICE FLOW TESTS PASSED PERFECTLY!")
    print("==================================================================")

if __name__ == '__main__':
    run_tests()
