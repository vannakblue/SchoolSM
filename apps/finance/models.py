from django.db import models
from django.conf import settings
from decimal import Decimal
from datetime import datetime

class FeeCategory(models.Model):
    name = models.CharField(max_length=150, verbose_name="ឈ្មោះកម្រៃសិក្សា / Fee Title")
    default_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('250.00'), verbose_name="តម្លៃលំនាំដើម ($) / Default Amount")
    description = models.TextField(blank=True, null=True, verbose_name="ការពិពណ៌នា / Description")

    class Meta:
        verbose_name = "ប្រភេទកម្រៃសិក្សា / Fee Category"
        verbose_name_plural = "ប្រភេទកម្រៃសិក្សាទាំងអស់ / Fee Categories"

    def __str__(self):
        return f"{self.name} (${self.default_amount})"


class Invoice(models.Model):
    class Status(models.TextChoices):
        PAID = 'PAID', 'បង់រួចរាល់ / Paid'
        PARTIAL = 'PARTIAL', 'បង់បានខ្លះ / Partially Paid'
        UNPAID = 'UNPAID', 'មិនទាន់បង់ / Unpaid'
        OVERDUE = 'OVERDUE', 'ហួសកាលកំណត់ / Overdue'

    invoice_no = models.CharField(max_length=50, unique=True, blank=True, verbose_name="លេខវិក្កយបត្រ / Invoice No")
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='invoices', verbose_name="សិស្ស / Student")
    fee_category = models.ForeignKey(FeeCategory, on_delete=models.CASCADE, verbose_name="ប្រភេទកម្រៃ / Fee Category")
    academic_year = models.ForeignKey('academics.AcademicYear', on_delete=models.CASCADE, verbose_name="ឆ្នាំសិក្សា / Academic Year")
    original_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="តម្លៃដើម ($) / Original Amount")
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), verbose_name="បញ្ចុះតម្លៃ (%) / Discount/Scholarship %")
    final_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="តម្លៃត្រូវទូទាត់ ($) / Final Payable Amount")
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="ចំនួនបានបង់ ($) / Paid Amount")
    due_date = models.DateField(verbose_name="កាលបរិច្ឆេទទូទាត់ចុងក្រោយ / Due Date")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UNPAID, verbose_name="ស្ថានភាពទូទាត់ / Payment Status")
    notes = models.TextField(blank=True, null=True, verbose_name="កំណត់ចំណាំ / Notes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "វិក្កយបត្រ / Invoice"
        verbose_name_plural = "វិក្កយបត្រទាំងអស់ / Invoices"

    @property
    def remaining_balance(self):
        return max(Decimal('0.00'), self.final_amount - self.paid_amount)

    def update_status(self):
        if self.paid_amount >= self.final_amount and self.final_amount > 0:
            self.status = self.Status.PAID
        elif self.paid_amount > 0:
            self.status = self.Status.PARTIAL
        elif datetime.now().date() > self.due_date and self.paid_amount == 0:
            self.status = self.Status.OVERDUE
        else:
            self.status = self.Status.UNPAID

    def save(self, *args, **kwargs):
        if not self.invoice_no:
            year = datetime.now().year
            last_inv = Invoice.objects.filter(invoice_no__startswith=f"INV-{year}-").order_by('-id').first()
            if last_inv and last_inv.invoice_no:
                try:
                    last_num = int(last_inv.invoice_no.split('-')[-1])
                    new_num = last_num + 1
                except ValueError:
                    new_num = Invoice.objects.count() + 1
            else:
                new_num = Invoice.objects.count() + 1
            self.invoice_no = f"INV-{year}-{new_num:04d}"

        # Auto calculate final amount if not set
        if not self.final_amount:
            discount = (self.original_amount * (self.discount_percent / Decimal('100.0')))
            self.final_amount = max(Decimal('0.00'), self.original_amount - discount)

        self.update_status()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.invoice_no} - {self.student.khmer_name} (${self.final_amount}) [{self.get_status_display()}]"


class PaymentTransaction(models.Model):
    class PaymentMethod(models.TextChoices):
        CASH = 'CASH', 'សាច់ប្រាក់សុទ្ធ / Cash'
        KHQR_BAKONG = 'KHQR_BAKONG', 'KHQR (Bakong / គ្រប់ធនាគារ)'
        ABA_BANK = 'ABA_BANK', 'ABA Bank Pay'
        BANK_TRANSFER = 'BANK_TRANSFER', 'ផ្ទេរប្រាក់ធនាគារ / Bank Transfer'

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments', verbose_name="វិក្កយបត្រ / Invoice")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="ចំនួនទឹកប្រាក់បង់ ($) / Amount Paid")
    payment_method = models.CharField(max_length=30, choices=PaymentMethod.choices, default=PaymentMethod.KHQR_BAKONG, verbose_name="វិធីសាស្ត្រទូទាត់ / Payment Method")
    transaction_reference = models.CharField(max_length=100, blank=True, null=True, verbose_name="លេខកូដប្រតិបត្តិការ / Ref No")
    receipt_number = models.CharField(max_length=50, unique=True, blank=True, verbose_name="លេខបង្កាន់ដៃ / Receipt No")
    payment_date = models.DateTimeField(auto_now_add=True, verbose_name="កាលបរិច្ឆេទទូទាត់ / Payment Date")
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="អ្នកទទួលប្រាក់ / Cashier/Accountant")
    notes = models.TextField(blank=True, null=True, verbose_name="កំណត់ចំណាំ / Notes")

    class Meta:
        ordering = ['-payment_date']
        verbose_name = "ប្រតិបត្តិការបង់ប្រាក់ / Payment Transaction"
        verbose_name_plural = "ប្រតិបត្តិការបង់ប្រាក់ទាំងអស់ / Payment Transactions"

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            year = datetime.now().year
            last_rec = PaymentTransaction.objects.filter(receipt_number__startswith=f"REC-{year}-").order_by('-id').first()
            if last_rec and last_rec.receipt_number:
                try:
                    last_num = int(last_rec.receipt_number.split('-')[-1])
                    new_num = last_num + 1
                except ValueError:
                    new_num = PaymentTransaction.objects.count() + 1
            else:
                new_num = PaymentTransaction.objects.count() + 1
            self.receipt_number = f"REC-{year}-{new_num:04d}"
        
        super().save(*args, **kwargs)
        # Update invoice paid amount
        total_paid = sum(p.amount for p in self.invoice.payments.all())
        self.invoice.paid_amount = total_paid
        self.invoice.update_status()
        self.invoice.save()

    def __str__(self):
        return f"{self.receipt_number} - ${self.amount} for {self.invoice.invoice_no}"


class Expense(models.Model):
    class Category(models.TextChoices):
        UTILITIES = 'UTILITIES', 'ថ្លៃទឹក ភ្លើង អ៊ីនធឺណិត / Utilities'
        SUPPLIES = 'SUPPLIES', 'សម្ភារៈការិយាល័យ & បង្រៀន / Supplies'
        RENT = 'RENT', 'ថ្លៃជួលទីតាំង & អាគារ / Building Rent'
        MAINTENANCE = 'MAINTENANCE', 'ការជួសជុល & ថែទាំ / Repairs & Maintenance'
        EVENTS = 'EVENTS', 'កម្មវិធី & កីឡាសាលា / School Events & Sports'
        SALARY = 'SALARY', 'ប្រាក់ខែ & ប្រាក់រង្វាន់ / Salaries & Bonuses'
        OTHER = 'OTHER', 'ចំណាយផ្សេងៗ / Other Expenses'

    title = models.CharField(max_length=200, verbose_name="ចំណងជើងចំណាយ / Expense Title")
    category = models.CharField(max_length=30, choices=Category.choices, default=Category.UTILITIES, verbose_name="ប្រភេទចំណាយ / Category")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="ចំនួនទឹកប្រាក់ ($) / Amount")
    date = models.DateField(verbose_name="កាលបរិច្ឆេទចំណាយ / Expense Date")
    voucher_file = models.FileField(upload_to='expenses/vouchers/', blank=True, null=True, verbose_name="បង្កាន់ដៃ/វិក្កយបត្រចំណាយ / Voucher/Receipt")
    notes = models.TextField(blank=True, null=True, verbose_name="កំណត់ចំណាំ / Notes")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="អ្នកកត់ត្រា / Recorded By")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']
        verbose_name = "ចំណាយ / Expense"
        verbose_name_plural = "ចំណាយទាំងអស់ / Expenses"

    def __str__(self):
        return f"[{self.get_category_display()}] {self.title}: ${self.amount}"


class Payroll(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'រង់ចាំបើក / Pending'
        PAID = 'PAID', 'បើករួចរាល់ / Paid'

    teacher = models.ForeignKey('teachers.Teacher', on_delete=models.CASCADE, related_name='payrolls', verbose_name="គ្រូបង្រៀន/បុគ្គលិក / Teacher/Staff")
    month = models.IntegerField(verbose_name="ប្រចាំខែ (1-12) / Month")
    year = models.IntegerField(verbose_name="ប្រចាំឆ្នាំ / Year")
    base_salary = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="ប្រាក់ខែគោល ($) / Base Salary")
    bonus_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="ប្រាក់បន្ថែម ($) / Bonus/Allowance")
    unexcused_days = models.IntegerField(default=0, verbose_name="ចំនួនថ្ងៃអវត្តមានឥតច្បាប់ / Unexcused Absences")
    absence_deduction = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="កាត់ប្រាក់អវត្តមាន ($) / Absence Deductions")
    net_salary = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="ប្រាក់ខែសុទ្ធត្រូវបើក ($) / Net Salary")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, verbose_name="ស្ថានភាព / Status")
    payment_date = models.DateField(blank=True, null=True, verbose_name="ថ្ងៃបើកប្រាក់ / Payment Date")
    notes = models.TextField(blank=True, null=True, verbose_name="កំណត់ចំណាំ / Notes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-year', '-month', 'teacher']
        unique_together = ('teacher', 'month', 'year')
        verbose_name = "ប្រាក់ខែបុគ្គលិក / Payroll Record"
        verbose_name_plural = "ប្រាក់ខែបុគ្គលិកទាំងអស់ / Payroll Records"

    def calculate(self):
        # Auto calculate deduction from teacher's unexcused absences for the month
        from apps.teachers.models import TeacherAttendance
        unexcused = TeacherAttendance.objects.filter(
            teacher=self.teacher,
            date__year=self.year,
            date__month=self.month,
            status=TeacherAttendance.Status.UNEXCUSED_ABSENCE
        )
        self.unexcused_days = unexcused.count()
        daily_rate = self.base_salary / Decimal('26')
        self.absence_deduction = round(daily_rate * self.unexcused_days, 2)
        self.net_salary = max(Decimal('0.00'), self.base_salary + self.bonus_allowance - self.absence_deduction)

    def save(self, *args, **kwargs):
        if not self.net_salary:
            self.calculate()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.teacher.khmer_name} - {self.month:02d}/{self.year} (${self.net_salary}) [{self.get_status_display()}]"


# ==========================================================
# Monthly Utility & School Fee Management Models (បញ្ជីទឹកភ្លើងប្រចាំខែ)
# ==========================================================

class MonthlyFeeConfig(models.Model):
    academic_year = models.OneToOneField('academics.AcademicYear', on_delete=models.CASCADE, related_name='monthly_fee_config', verbose_name="ឆ្នាំសិក្សា / Academic Year")
    title = models.CharField(max_length=200, default="ថ្លៃទឹកភ្លើង និងសេវាសិក្សាប្រចាំខែ", verbose_name="ចំណងជើងកម្រៃ / Fee Title")
    start_month = models.PositiveSmallIntegerField(default=10, verbose_name="ខែចាប់ផ្តើម (1-12) / Start Month")
    end_month = models.PositiveSmallIntegerField(default=8, verbose_name="ខែបញ្ចប់ (1-12) / End Month")
    ticked_months = models.JSONField(default=list, blank=True, verbose_name="ខែដែលបាន Tick ត្រូវបង់ / Ticked Due Months")
    currency_symbol = models.CharField(max_length=10, default="៛", verbose_name="រូបិយប័ណ្ណ / Currency Symbol")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "ការកំណត់ថ្លៃទឹកភ្លើងប្រចាំខែ / Monthly Fee Config"
        verbose_name_plural = "ការកំណត់ថ្លៃទឹកភ្លើងប្រចាំខែ / Monthly Fee Configs"

    @classmethod
    def get_or_create_for_year(cls, academic_year=None):
        if not academic_year:
            from apps.academics.models import AcademicYear
            academic_year = AcademicYear.objects.filter(is_current=True).first() or AcademicYear.objects.order_by('-id').first()
        if not academic_year:
            return None
        config, _ = cls.objects.get_or_create(
            academic_year=academic_year,
            defaults={
                'start_month': 10,
                'end_month': 8,
                'ticked_months': [10, 11, 12, 1],
                'currency_symbol': '៛'
            }
        )
        return config

    def get_month_sequence(self):
        """Returns the ordered list of months for the academic year (e.g. [10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8])"""
        months = []
        m = self.start_month
        while True:
            months.append(m)
            if m == self.end_month:
                break
            m = 1 if m == 12 else m + 1
            if len(months) >= 12:
                break
        return months

    def get_scoped_month_numbers(self):
        """Returns list of active/ticked month numbers configured by Admin"""
        return self.ticked_months or []


class MonthlyFeeRate(models.Model):
    config = models.ForeignKey(MonthlyFeeConfig, on_delete=models.CASCADE, related_name='rates', verbose_name="ការកំណត់ / Config")
    category = models.ForeignKey('students.StudentCategory', on_delete=models.CASCADE, related_name='monthly_rates', verbose_name="ប្រភេទសិស្ស / Category")
    month = models.PositiveSmallIntegerField(verbose_name="ខែ (1-12) / Month")
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('20000.00'), verbose_name="ចំនួនទឹកប្រាក់ / Amount")

    class Meta:
        unique_together = ('config', 'category', 'month')
        ordering = ['category__display_order', 'month']
        verbose_name = "តម្លៃប្រចាំខែតាមប្រភេទសិស្ស / Monthly Fee Rate"
        verbose_name_plural = "តម្លៃប្រចាំខែតាមប្រភេទសិស្សទាំងអស់ / Monthly Fee Rates"

    def __str__(self):
        return f"{self.category.name} - ខែ {self.month}: {self.amount:,.0f} {self.config.currency_symbol}"


class StudentMonthlyPayment(models.Model):
    class Status(models.TextChoices):
        PAID = 'PAID', 'បង់គ្រប់ / Paid Full'
        PARTIAL = 'PARTIAL', 'បង់បានខ្លះ / Partial'
        UNPAID = 'UNPAID', 'មិនទាន់បង់ / Unpaid'

    class PaymentMethod(models.TextChoices):
        CASH = 'CASH', 'សាច់ប្រាក់សុទ្ធ / Cash'
        KHQR_BAKONG = 'KHQR_BAKONG', 'KHQR (Bakong)'
        ABA_BANK = 'ABA_BANK', 'ABA Bank Pay'
        BANK_TRANSFER = 'BANK_TRANSFER', 'ផ្ទេរប្រាក់ធនាគារ / Bank Transfer'

    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='monthly_payments', verbose_name="សិស្ស / Student")
    academic_year = models.ForeignKey('academics.AcademicYear', on_delete=models.CASCADE, verbose_name="ឆ្នាំសិក្សា / Academic Year")
    month = models.PositiveSmallIntegerField(verbose_name="ខែ (1-12) / Month")
    expected_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="ចំនួនត្រូវបង់ / Expected Amount")
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="ចំនួនបានបង់ / Paid Amount")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UNPAID, verbose_name="ស្ថានភាព / Status")
    is_on_time = models.BooleanField(default=True, verbose_name="បង់ទាន់ពេល / Paid On Time")
    payment_date = models.DateTimeField(blank=True, null=True, verbose_name="ថ្ងៃបង់ប្រាក់ / Payment Date")
    payment_method = models.CharField(max_length=30, choices=PaymentMethod.choices, default=PaymentMethod.CASH, verbose_name="វិធីសាស្ត្រទូទាត់ / Payment Method")
    receipt_no = models.CharField(max_length=50, blank=True, verbose_name="លេខបង្កាន់ដៃ / Receipt No")
    collected_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="អ្នកប្រមូល / Collector")
    notes = models.TextField(blank=True, null=True, verbose_name="កំណត់ចំណាំ / Notes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('student', 'academic_year', 'month')
        ordering = ['student', 'month']
        verbose_name = "កំណត់ត្រាបង់ប្រាក់ប្រចាំខែ / Student Monthly Payment"
        verbose_name_plural = "កំណត់ត្រាបង់ប្រាក់ប្រចាំខែទាំងអស់ / Student Monthly Payments"

    @property
    def remaining_balance(self):
        return max(Decimal('0.00'), self.expected_amount - self.paid_amount)

    def update_status(self):
        if self.paid_amount >= self.expected_amount and self.expected_amount > 0:
            self.status = self.Status.PAID
        elif self.paid_amount > 0:
            self.status = self.Status.PARTIAL
        else:
            self.status = self.Status.UNPAID

    def save(self, *args, **kwargs):
        self.update_status()
        if not self.receipt_no and self.paid_amount > 0:
            year = datetime.now().year
            self.receipt_no = f"UF-{year}-{self.student.id:03d}-M{self.month:02d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student.khmer_name} - M{self.month} ({self.get_status_display()})"


class StudentMonthlyCategory(models.Model):
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='monthly_category_assignments', verbose_name="សិស្ស / Student")
    academic_year = models.ForeignKey('academics.AcademicYear', on_delete=models.CASCADE, verbose_name="ឆ្នាំសិក្សា / Academic Year")
    month = models.PositiveSmallIntegerField(verbose_name="ខែ (1-12) / Month")
    category = models.ForeignKey('students.StudentCategory', on_delete=models.CASCADE, null=True, blank=True, verbose_name="ប្រភេទសិស្ស / Category")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('student', 'academic_year', 'month')
        ordering = ['student', 'month']
        verbose_name = "ប្រភេទសិស្សតាមខែជាក់ស្តែង / Student Monthly Category"
        verbose_name_plural = "ប្រភេទសិស្សតាមខែជាក់ស្តែងទាំងអស់ / Student Monthly Categories"

    def __str__(self):
        cat_name = self.category.name if self.category else "ទូទៅ (Normal)"
        return f"{self.student.khmer_name} - ខែ {self.month}: {cat_name}"

