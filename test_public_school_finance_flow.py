import os
import django
from decimal import Decimal
from datetime import date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from apps.teachers.models import Teacher
from apps.academics.models import AcademicYear
from apps.finance.models import (
    SchoolRevenue, TeacherOvertimeConfig, TeacherOvertimeRecord, Expense
)

User = get_user_model()

def run_tests():
    print("Running Public School Finance Flow Tests...")

    # 1. Setup Admin User & Academic Year
    admin_user, _ = User.objects.get_or_create(
        username='admin_finance_tester',
        defaults={'email': 'admin_fin@school.edu', 'role': 'ADMIN', 'is_staff': True, 'is_superuser': True}
    )
    admin_user.set_password('AdminPass123!')
    admin_user.save()

    active_year, _ = AcademicYear.objects.get_or_create(
        name='2026-2027',
        defaults={'start_date': date(2026, 10, 1), 'end_date': date(2027, 8, 31), 'is_current': True}
    )

    # 2. Test School Revenue Sources
    print("\n[Step 1] Testing School Revenue Sources...")
    rev1 = SchoolRevenue.objects.create(
        title="ថវិកាកម្មវិធីរដ្ឋ (PB) ឆមាសទី១",
        source_type=SchoolRevenue.RevenueSource.STATE_BUDGET,
        amount_khr=Decimal('10000000.00'),  # 10 Million KHR
        amount_usd=Decimal('0.00'),
        date=date(2026, 10, 5),
        receipt_reference="MOEYS-PB-2026-001",
        academic_year=active_year,
        recorded_by=admin_user
    )
    assert rev1.amount_khr == Decimal('10000000.00'), "Revenue KHR mismatch"
    assert rev1.total_usd_equivalent > 0, "USD equivalent calculation failed"

    rev2 = SchoolRevenue.objects.create(
        title="វិភាគទានសហគមន៍ & សមាគមអាណាព្យាបាល",
        source_type=SchoolRevenue.RevenueSource.PARENT_CONTRIBUTION,
        amount_khr=Decimal('0.00'),
        amount_usd=Decimal('800.00'),  # $800 USD
        date=date(2026, 10, 10),
        academic_year=active_year,
        recorded_by=admin_user
    )
    assert rev2.amount_usd == Decimal('800.00'), "Revenue USD mismatch"
    assert rev2.total_khr_equivalent == Decimal('3280000.00'), "KHR equivalent calculation failed"
    print(f"  ✓ Created Revenue 1: {rev1}")
    print(f"  ✓ Created Revenue 2: {rev2}")

    # 3. Test Teacher Overtime Config
    print("\n[Step 2] Testing Teacher Overtime Configuration...")
    config = TeacherOvertimeConfig.get_config()
    config.rate_per_hour_khr = Decimal('12000.00')  # 12,000 KHR / hour
    config.rate_per_hour_usd = Decimal('3.00')      # $3.00 / hour
    config.standard_hours_monthly = Decimal('64.00')
    config.save()
    assert config.rate_per_hour_khr == Decimal('12000.00')
    print(f"  ✓ Configured Overtime Rate: {config.rate_per_hour_khr:,.0f}៛ / ${config.rate_per_hour_usd} per hour")

    # 4. Test Teacher Overtime Record & Calculation
    print("\n[Step 3] Testing Teacher Overtime Record & Calculation...")
    teacher, _ = Teacher.objects.get_or_create(
        teacher_id="TCH-FIN-001",
        defaults={
            'khmer_name': "សេង សុជាតិ",
            'latin_name': "Seng Socheat",
            'gender': "M",
            'phone': "012334455",
            'status': "ACTIVE",
            'specialization': "គណិតវិទ្យា"
        }
    )

    ot_record, _ = TeacherOvertimeRecord.objects.update_or_create(
        teacher=teacher,
        month=10,
        year=2026,
        defaults={
            'academic_year': active_year,
            'standard_hours': Decimal('64.00'),
            'actual_hours': Decimal('76.00'),  # 12 hours overtime!
            'rate_per_hour_khr': config.rate_per_hour_khr,
            'rate_per_hour_usd': config.rate_per_hour_usd,
            'status': TeacherOvertimeRecord.Status.PENDING,
            'recorded_by': admin_user
        }
    )
    assert ot_record.overtime_hours == Decimal('12.00'), f"Expected 12.00 overtime hours, got {ot_record.overtime_hours}"
    assert ot_record.total_allowance_khr == Decimal('144000.00'), f"Expected 144,000 KHR, got {ot_record.total_allowance_khr}"
    assert ot_record.total_allowance_usd == Decimal('36.00'), f"Expected $36.00, got {ot_record.total_allowance_usd}"
    print(f"  ✓ Calculated Overtime Record: {ot_record}")

    # 5. Test Paying Teacher Overtime & Auto Expense Entry
    print("\n[Step 4] Testing Teacher Overtime Payment & Auto Expense Entry...")
    client = Client()
    client.force_login(admin_user)

    pay_resp = client.post(f"/finance/teacher-overtime/{ot_record.id}/mark-paid/")
    assert pay_resp.status_code == 302, f"Expected redirect after mark paid, got {pay_resp.status_code}"
    ot_record.refresh_from_db()
    assert ot_record.status == TeacherOvertimeRecord.Status.PAID, "Record should be marked as PAID"

    # Verify that an Expense entry was created
    auto_exp = Expense.objects.filter(
        category=Expense.Category.TEACHER_OVERTIME,
        title__contains=teacher.khmer_name
    ).first()
    assert auto_exp is not None, "Auto Expense for teacher overtime was not created!"
    assert auto_exp.amount_khr == Decimal('144000.00'), "Auto expense amount KHR mismatch"
    print(f"  ✓ Successfully verified auto-created expense: {auto_exp}")

    # 6. Test General School Expense
    print("\n[Step 5] Testing General School Expense...")
    gen_exp = Expense.objects.create(
        title="ទិញដីស ហ្វឺត និងក្រដាស A4 ឆមាសទី១",
        category=Expense.Category.SUPPLIES,
        amount_khr=Decimal('200000.00'),
        amount=Decimal('0.00'),
        date=date(2026, 10, 15),
        recorded_by=admin_user
    )
    assert gen_exp.amount_khr == Decimal('200000.00')
    print(f"  ✓ Created general expense: {gen_exp}")

    # 7. Test Automated Student Collections (Monthly Utility & Student Invoices)
    print("\n[Step 6] Testing Automated Student Utilities & Invoice Payments Integration...")
    from apps.students.models import Student
    from apps.finance.models import FeeCategory, Invoice, PaymentTransaction, StudentMonthlyPayment

    test_student, _ = Student.objects.get_or_create(
        student_id='STU-FIN-AUTO-01',
        defaults={
            'khmer_name': 'សុខ ចាន់ដារ៉ា',
            'latin_name': 'Sok Chandara',
            'gender': 'M',
            'date_of_birth': date(2010, 5, 12),
            'status': 'ACTIVE'
        }
    )

    # A) Student pays monthly utilities: 25,000 ៛
    s_payment, _ = StudentMonthlyPayment.objects.update_or_create(
        student=test_student,
        academic_year=active_year,
        month=10,
        defaults={
            'expected_amount': Decimal('25000.00'),
            'paid_amount': Decimal('25000.00'),
            'status': StudentMonthlyPayment.Status.PAID,
            'collected_by': admin_user
        }
    )
    print(f"  ✓ Recorded Student Monthly Utility Payment: {s_payment.paid_amount:,.0f} ៛")

    # B) Student pays invoice: $50.00
    fee_cat, _ = FeeCategory.objects.get_or_create(
        name="ថ្លៃឯកសណ្ឋាន & សៀវភៅតាមដាន",
        defaults={'default_amount': Decimal('50.00')}
    )
    test_inv, _ = Invoice.objects.get_or_create(
        student=test_student,
        fee_category=fee_cat,
        academic_year=active_year,
        defaults={
            'original_amount': Decimal('50.00'),
            'final_amount': Decimal('50.00'),
            'due_date': date(2026, 11, 1),
            'status': Invoice.Status.PAID
        }
    )
    inv_pay, _ = PaymentTransaction.objects.get_or_create(
        invoice=test_inv,
        amount=Decimal('50.00'),
        defaults={'payment_method': PaymentTransaction.PaymentMethod.KHQR_BAKONG, 'received_by': admin_user}
    )
    print(f"  ✓ Recorded Student Invoice Payment: ${inv_pay.amount}")

    # 8. Test Financial Balance & Cash Flow Reconciliation
    print("\n[Step 7] Testing Financial Balance & Dashboard (Auto-Reconciliation)...")
    dashboard_resp = client.get(f"/finance/financial-balance/?year={active_year.id}")
    assert dashboard_resp.status_code == 200, f"Dashboard returned {dashboard_resp.status_code}"
    content = dashboard_resp.content.decode('utf-8')
    assert "សមតុល្យចំណូល-ចំណាយសាលារៀន" in content, "Dashboard title missing in response"
    assert "ថវិកាកម្មវិធីរដ្ឋ" in content, "MoEYS PB revenue category missing in dashboard"
    assert "ប្រាក់ឧបត្ថម្ភគ្រូបង្រៀនលើសម៉ោង" in content, "Teacher overtime category missing in dashboard"
    assert "ថ្លៃទឹក-ភ្លើងបន្ទប់រៀនប្រចាំខែ" in content, "Auto student utility missing in dashboard sources"
    assert "វិក្កយបត្រសិស្ស" in content, "Auto student invoice missing in dashboard sources"
    print("  [OK] Financial Balance dashboard successfully loads and auto-includes student utilities and invoices!")

    # 9. Test Revenue and Overtime List pages
    rev_resp = client.get(f"/finance/revenues/?year={active_year.id}")
    assert rev_resp.status_code == 200, "Revenues page failed to load"
    rev_content = rev_resp.content.decode('utf-8')
    assert "ប្រព័ន្ធគិតបញ្ចូលចំណូលពីសិស្សដោយស្វ័យប្រវត្តិ" in rev_content, "Live student collections banner missing in revenue list"

    ot_resp = client.get("/finance/teacher-overtime/?month=10&year=2026")
    assert ot_resp.status_code == 200, "Teacher overtime page failed to load"

    exp_resp = client.get("/finance/expenses/")
    assert exp_resp.status_code == 200, "Expenses page failed to load"

    print("\nALL TESTS PASSED SUCCESSFULLY! The Public School Finance System is fully functional with automated student collections.")

if __name__ == '__main__':
    run_tests()

