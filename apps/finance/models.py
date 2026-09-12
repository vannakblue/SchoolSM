from django.db import models
from django.conf import settings
from decimal import Decimal
from datetime import datetime

class FeeCategory(models.Model):
    class CategoryType(models.TextChoices):
        ENROLLMENT = 'ENROLLMENT', 'ថ្លៃចុះឈ្មោះចូលរៀនដើមឆ្នាំ / Early Year Enrollment'
        CONTRIBUTION = 'CONTRIBUTION', 'វិភាគទានសាលារៀន / School Contribution'
        TUITION = 'TUITION', 'កម្រៃសិក្សា / Tuition Fee'
        UTILITIES = 'UTILITIES', 'ថ្លៃទឹក-ភ្លើង / Utilities Billing'
        UNIFORM = 'UNIFORM', 'ថ្លៃឯកសណ្ឋាន / Uniform'
        BOOKS = 'BOOKS', 'ថ្លៃសៀវភៅ & សម្ភារៈ / Books & Supplies'
        OTHER = 'OTHER', 'កម្រៃផ្សេងៗ / Other'

    name = models.CharField(max_length=150, verbose_name="ឈ្មោះកម្រៃសិក្សា / Fee Title")
    category_type = models.CharField(
        max_length=30,
        choices=CategoryType.choices,
        default=CategoryType.OTHER,
        verbose_name="ប្រភេទមុខចំណាយ / Category Type"
    )
    default_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('25.00'), verbose_name="តម្លៃលំនាំដើម ($) / Default Amount")
    description = models.TextField(blank=True, null=True, verbose_name="អត្ថន័យចំណាយ / Description & Purpose")
    applicable_grade_note = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="កម្រិតថ្នាក់ដែលត្រូវអនុវត្ត / Applicable Grade Note",
        help_text="ឧទាហរណ៍៖ សម្រាប់តែថ្នាក់ទី ៧ ឬសិស្សចុះឈ្មោះថ្មី"
    )
    is_active = models.BooleanField(default=True, verbose_name="សកម្ម / Active")
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        ordering = ['-is_active', 'name']
        verbose_name = "ប្រភេទកម្រៃសិក្សា / Fee Category"
        verbose_name_plural = "ប្រភេទកម្រៃសិក្សាទាំងអស់ / Fee Categories"

    @property
    def invoice_count(self):
        return self.invoices.count() if hasattr(self, 'invoices') else self.invoice_set.count()

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
    fee_category = models.ForeignKey(FeeCategory, on_delete=models.CASCADE, related_name='invoices', verbose_name="ប្រភេទកម្រៃ / Fee Category")
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
        elif self.due_date:
            due = self.due_date
            if isinstance(due, str):
                from datetime import date
                try:
                    due = date.fromisoformat(due)
                except Exception:
                    due = None
            if due and datetime.now().date() > due and self.paid_amount == 0:
                self.status = self.Status.OVERDUE
            else:
                self.status = self.Status.UNPAID
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

    def get_clarified_purpose(self):
        """
        Returns a human-readable, unambiguous explanation of what this fee covers,
        incorporating the exact purpose/description and target grade defined by Admin.
        """
        cat = self.fee_category
        cat_name = cat.name if cat else ''
        cat_type = getattr(cat, 'category_type', '') or ''
        cat_desc = (cat.description or '').strip() if cat else ''
        grade_note = (cat.applicable_grade_note or '').strip() if cat else ''
        notes = (self.notes or '').strip()
        class_name = self.student.classroom.name if self.student and self.student.classroom else ''
        
        target_class_desc = f" (សម្រាប់ថ្នាក់ {class_name})" if class_name else ""
        if grade_note and not target_class_desc:
            target_class_desc = f" ({grade_note})"

        # Check by category type or keyword
        if cat_type == FeeCategory.CategoryType.ENROLLMENT or any(k in cat_name for k in ['ចុះឈ្មោះ', 'ដើមឆ្នាំ', 'Enrollment', 'Registration', 'Admission']):
            prefix = cat_name if cat_name else "ថ្លៃចុះឈ្មោះចូលរៀនដើមឆ្នាំ"
            desc_text = f"៖ {cat_desc}" if cat_desc else "៖ សេវាចុះឈ្មោះ សៀវភៅតាមដាន និងកាតសិស្ស"
            return f"{prefix}{target_class_desc}{desc_text}"
        elif cat_type == FeeCategory.CategoryType.CONTRIBUTION or any(k in cat_name for k in ['វិភាគទាន', 'សប្បុរសធម៌', 'មូលនិធិ', 'Contribution', 'Donation']):
            prefix = cat_name if cat_name else "វិភាគទានសាលារៀន"
            desc_text = f"៖ {cat_desc}" if cat_desc else "៖ មូលនិធិអភិវឌ្ឍន៍សាលារៀន និងបរិស្ថានសិក្សា"
            return f"{prefix}{target_class_desc}{desc_text}"
        elif cat_type == FeeCategory.CategoryType.UTILITIES or any(k in cat_name for k in ['ទឹក', 'ភ្លើង', 'Utility', 'Utilities']):
            prefix = cat_name if cat_name else "ថ្លៃសេវាទឹកស្អាត និងអគ្គិសនីប្រចាំខែ"
            desc_text = f" ({cat_desc})" if cat_desc else " (Utilities Billing)"
            return f"{prefix}{desc_text}"
        elif cat_type == FeeCategory.CategoryType.UNIFORM or any(k in cat_name for k in ['ឯកសណ្ឋាន', 'Uniform']):
            prefix = cat_name if cat_name else "ថ្លៃឯកសណ្ឋានសិស្សផ្លូវការ"
            desc_text = f" ({cat_desc})" if cat_desc else " និងស្លាកឈ្មោះ"
            return f"{prefix}{desc_text}"
        elif cat_type == FeeCategory.CategoryType.BOOKS or any(k in cat_name for k in ['សៀវភៅ', 'Book']):
            prefix = cat_name if cat_name else "ថ្លៃសៀវភៅសិក្សាគោល"
            desc_text = f" ({cat_desc})" if cat_desc else " និងឯកសារជំនួយស្មារតី"
            return f"{prefix}{desc_text}"
        elif cat_desc:
            return f"{cat_name}{target_class_desc}៖ {cat_desc}"
        elif notes:
            return f"{cat_name}{target_class_desc} ({notes})"
        return f"{cat_name}{target_class_desc} (កម្រៃសិក្សាផ្លូវការ)"

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
        UTILITIES = 'UTILITIES', 'ថ្លៃទឹក ភ្លើង អ៊ីនធឺណិតសាលា / School Utilities'
        SUPPLIES = 'SUPPLIES', 'សម្ភារៈការិយាល័យ & បង្រៀន (ដីស ហ្វឺត ក្រដាស) / Supplies'
        RENT = 'RENT', 'ថ្លៃជួលទីតាំង & អាគារ / Building Rent'
        MAINTENANCE = 'MAINTENANCE', 'ការជួសជុល & ថែទាំអគារ/បន្ទប់ទឹក / Repairs & Maintenance'
        EVENTS = 'EVENTS', 'កម្មវិធី & កីឡាសាលា / School Events & Sports'
        TEACHER_OVERTIME = 'TEACHER_OVERTIME', 'ប្រាក់ឧបត្ថម្ភគ្រូបង្រៀនលើសម៉ោង / Teacher Overtime Allowance'
        SANITATION_ENV = 'SANITATION_ENV', 'អនាម័យ បរិស្ថាន & សួនច្បារ / Sanitation & Environment'
        SALARY = 'SALARY', 'ប្រាក់ខែ & ប្រាក់រង្វាន់ / Salaries & Bonuses'
        OTHER = 'OTHER', 'ចំណាយផ្សេងៗ / Other Expenses'

    title = models.CharField(max_length=200, verbose_name="ចំណងជើងចំណាយ / Expense Title")
    category = models.CharField(max_length=30, choices=Category.choices, default=Category.UTILITIES, verbose_name="ប្រភេទចំណាយ / Category")
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="ចំនួនទឹកប្រាក់ ($) / Amount (USD)")
    amount_khr = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), verbose_name="ចំនួនទឹកប្រាក់ (រៀល ៛) / Amount (KHR)")
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
        return f"[{self.get_category_display()}] {self.title}: ${self.amount} / {self.amount_khr:,.0f}៛"

    @property
    def total_usd_equivalent(self):
        return round(self.amount + (self.amount_khr / Decimal('4100.00')), 2)

    @property
    def total_khr_equivalent(self):
        return round(self.amount_khr + (self.amount * Decimal('4100.00')), 0)


class SchoolRevenue(models.Model):
    class RevenueSource(models.TextChoices):
        STATE_BUDGET = 'STATE_BUDGET', 'ថវិកាកម្មវិធីរដ្ឋ (MoEYS Program Budget / PB)'
        PARENT_CONTRIBUTION = 'PARENT_CONTRIBUTION', 'វិភាគទានសហគមន៍/អាណាព្យាបាល (Community & Parent Support)'
        UTILITY_COLLECTION = 'UTILITY_COLLECTION', 'ថ្លៃទឹកភ្លើងបន្ទប់រៀនប្រចាំខែ (Classroom Utilities)'
        CANTEEN_RENT = 'CANTEEN_RENT', 'ថ្លៃឈ្នួលអាហារដ្ឋាន/តូបលក់ដូរ (Canteen / Booth Rent)'
        SCHOOL_SERVICES = 'SCHOOL_SERVICES', 'ចំណូលសេវាកម្ម (ឯកសណ្ឋាន កាតសិស្ស សៀវភៅតាមដាន)'
        DONATION = 'DONATION', 'អំណោយ/សប្បុរសជន/អតីតសិស្ស (Donations & Grants)'
        OTHER = 'OTHER', 'ចំណូលផ្សេងៗ / Other Revenue'

    title = models.CharField(max_length=200, verbose_name="ចំណងជើងចំណូល / Revenue Title")
    source_type = models.CharField(max_length=40, choices=RevenueSource.choices, default=RevenueSource.STATE_BUDGET, verbose_name="ប្រភពចំណូល / Source")
    amount_khr = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), verbose_name="ចំនួនទឹកប្រាក់ (រៀល ៛) / Amount (KHR)")
    amount_usd = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="ចំនួនទឹកប្រាក់ (ដុល្លារ $) / Amount (USD)")
    date = models.DateField(verbose_name="កាលបរិច្ឆេទទទួល / Date Received")
    receipt_reference = models.CharField(max_length=100, blank=True, null=True, verbose_name="លេខបង្កាន់ដៃ/លិខិតយោង / Voucher Ref")
    receipt_file = models.FileField(upload_to='revenue/vouchers/', blank=True, null=True, verbose_name="ឯកសារភ្ជាប់ / Receipt File")
    academic_year = models.ForeignKey('academics.AcademicYear', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="ឆ្នាំសិក្សា / Academic Year")
    notes = models.TextField(blank=True, null=True, verbose_name="កំណត់ចំណាំ / Notes")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="អ្នកកត់ត្រា / Recorded By")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-id']
        verbose_name = "ចំណូលសាលា / School Revenue"
        verbose_name_plural = "ចំណូលសាលាទាំងអស់ / School Revenues"

    def __str__(self):
        return f"[{self.get_source_type_display()}] {self.title}: {self.amount_khr:,.0f}៛ / ${self.amount_usd:,.2f}"

    @property
    def total_usd_equivalent(self):
        return round(self.amount_usd + (self.amount_khr / Decimal('4100.00')), 2)

    @property
    def total_khr_equivalent(self):
        return round(self.amount_khr + (self.amount_usd * Decimal('4100.00')), 0)


class TeacherOvertimeConfig(models.Model):
    rate_per_hour_khr = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('10000.00'), verbose_name="អត្រាក្នុងមួយម៉ោង (រៀល ៛/h) / Rate (KHR)")
    rate_per_hour_usd = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('2.50'), verbose_name="អត្រាក្នុងមួយម៉ោង (ដុល្លារ $/h) / Rate (USD)")
    standard_hours_weekly = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('16.00'), verbose_name="ម៉ោងកាតព្វកិច្ចរដ្ឋក្នុងមួយសប្តាហ៍ / Standard Weekly Hours")
    standard_hours_monthly = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('64.00'), verbose_name="ម៉ោងកាតព្វកិច្ចរដ្ឋក្នុងមួយខែ / Standard Monthly Hours")
    notes = models.TextField(blank=True, null=True, default="អត្រាប្រាក់ឧបត្ថម្ភបង្រៀនលើសម៉ោងកំណត់សម្រាប់គ្រូបង្រៀនសាលារដ្ឋ", verbose_name="កំណត់ចំណាំ / Policy Notes")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "ការកំណត់អត្រាលើសម៉ោង / Overtime Rate Config"
        verbose_name_plural = "ការកំណត់អត្រាលើសម៉ោង / Overtime Rate Configs"

    @classmethod
    def get_config(cls):
        config = cls.objects.first()
        if not config:
            config = cls.objects.create()
        return config


class TeacherOvertimeRecord(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'រង់ចាំបើក / Pending'
        APPROVED = 'APPROVED', 'បានអនុម័ត / Approved'
        PAID = 'PAID', 'បើករួចរាល់ / Paid'

    teacher = models.ForeignKey('teachers.Teacher', on_delete=models.CASCADE, related_name='overtime_records', verbose_name="គ្រូបង្រៀន / Teacher")
    academic_year = models.ForeignKey('academics.AcademicYear', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="ឆ្នាំសិក្សា / Academic Year")
    month = models.PositiveSmallIntegerField(verbose_name="ប្រចាំខែ (1-12) / Month")
    year = models.PositiveIntegerField(verbose_name="ប្រចាំឆ្នាំ / Year")
    standard_hours = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('64.00'), verbose_name="ម៉ោងកាតព្វកិច្ចរដ្ឋ / Standard Hours")
    actual_hours = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('64.00'), verbose_name="ម៉ោងបង្រៀនជាក់ស្តែង / Actual Taught Hours")
    overtime_hours = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'), verbose_name="ម៉ោងបង្រៀនលើស / Overtime Hours")
    rate_per_hour_khr = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('10000.00'), verbose_name="អត្រា/ម៉ោង (រៀល ៛)")
    rate_per_hour_usd = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('2.50'), verbose_name="អត្រា/ម៉ោង (ដុល្លារ $)")
    total_allowance_khr = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="សរុបប្រាក់ឧបត្ថម្ភ (រៀល ៛)")
    total_allowance_usd = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="សរុបប្រាក់ឧបត្ថម្ភ (ដុល្លារ $)")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, verbose_name="ស្ថានភាព / Status")
    payment_date = models.DateField(blank=True, null=True, verbose_name="ថ្ងៃបើកប្រាក់ / Payment Date")
    voucher_ref = models.CharField(max_length=100, blank=True, null=True, verbose_name="លេខលិខិតទូទាត់ / Voucher Ref")
    notes = models.TextField(blank=True, null=True, verbose_name="កំណត់ចំណាំ / Notes")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="អ្នកកត់ត្រា / Recorded By")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-year', '-month', 'teacher__khmer_name']
        unique_together = ('teacher', 'month', 'year')
        verbose_name = "ប្រាក់ឧបត្ថម្ភលើសម៉ោងគ្រូ / Teacher Overtime Allowance"
        verbose_name_plural = "ប្រាក់ឧបត្ថម្ភលើសម៉ោងគ្រូទាំងអស់ / Teacher Overtime Allowances"

    def calculate(self):
        if self.actual_hours > self.standard_hours:
            self.overtime_hours = self.actual_hours - self.standard_hours
        else:
            self.overtime_hours = Decimal('0.00')

        self.total_allowance_khr = round(self.overtime_hours * self.rate_per_hour_khr, 0)
        self.total_allowance_usd = round(self.overtime_hours * self.rate_per_hour_usd, 2)

    def save(self, *args, **kwargs):
        self.calculate()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.teacher.khmer_name} ({self.month:02d}/{self.year}) : {self.overtime_hours}h លើសម៉ោង = {self.total_allowance_khr:,.0f}៛ / ${self.total_allowance_usd}"


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


# ==========================================================
# School Bank Account & Payment Method Configuration
# ==========================================================

class SchoolPaymentMethod(models.Model):
    class BankType(models.TextChoices):
        ABA = 'ABA', 'ABA Bank (ABA Pay / KHQR)'
        BAKONG = 'BAKONG', 'Bakong KHQR (គ្រប់ធនាគារ)'
        ACLEDA = 'ACLEDA', 'ACLEDA Bank Plc.'
        CANADIA = 'CANADIA', 'Canadia Bank'
        WING = 'WING', 'Wing Bank'
        OTHER = 'OTHER', 'ធនាគារផ្សេងៗ / Other Bank'

    class Currency(models.TextChoices):
        KHR = 'KHR', 'រៀល (KHR ៛)'
        USD = 'USD', 'ដុល្លារ (USD $)'
        BOTH = 'BOTH', 'ទាំងពីរ (KHR / USD)'

    bank_type = models.CharField(max_length=30, choices=BankType.choices, default=BankType.ABA, verbose_name="ប្រភេទធនាគារ / Bank")
    bank_name = models.CharField(max_length=150, default="ABA Bank", verbose_name="ឈ្មោះធនាគារ / Bank Name")
    account_name = models.CharField(max_length=150, verbose_name="ឈ្មោះម្ចាស់គណនី / Account Name")
    account_number = models.CharField(max_length=100, verbose_name="លេខគណនី / Account Number")
    currency = models.CharField(max_length=10, choices=Currency.choices, default=Currency.KHR, verbose_name="រូបិយប័ណ្ណ / Currency")
    qr_image = models.ImageField(upload_to='bank_qr/', blank=True, null=True, verbose_name="រូបភាព QR Code / Bank QR Code Image")
    khqr_payload = models.TextField(blank=True, null=True, verbose_name="ទិន្នន័យ Bakong KHQR String / Payload")
    instructions = models.TextField(
        blank=True,
        null=True,
        default="សូមស្កេន QR Code ខាងលើដើម្បីបង់ប្រាក់។ បន្ទាប់មក សូមដាក់កំណត់សម្គាល់ (Memo) ជា «អត្តលេខសិស្ស» ហើយផ្ញើរូបថតបង្កាន់ដៃ (Receipt) មកទីនេះ។",
        verbose_name="ការណែនាំសម្រាប់ការបង់ប្រាក់ / Payment Instructions"
    )
    is_active = models.BooleanField(default=True, verbose_name="សកម្ម / Active")
    is_default = models.BooleanField(default=False, verbose_name="គណនីលំនាំដើម / Default Account")
    display_order = models.PositiveIntegerField(default=1, verbose_name="លំដាប់លំដោយ / Display Order")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_default', 'display_order', 'id']
        verbose_name = "គណនីធនាគារ & QR Code / School Payment Method"
        verbose_name_plural = "គណនីធនាគារ & QR Code ទាំងអស់ / School Payment Methods"

    def save(self, *args, **kwargs):
        if self.is_default:
            SchoolPaymentMethod.objects.exclude(id=self.id).update(is_default=False)
        super().save(*args, **kwargs)

    @classmethod
    def get_default_or_first(cls):
        return cls.objects.filter(is_active=True, is_default=True).first() or cls.objects.filter(is_active=True).first()

    @classmethod
    def get_active_methods(cls):
        return cls.objects.filter(is_active=True).order_by('-is_default', 'display_order', 'id')

    def get_brand_badge_info(self):
        """Returns styling info, emoji icon, and badge class for bank cards."""
        btype = str(self.bank_type or '').upper()
        bname = str(self.bank_name or '').upper()
        if 'ABA' in btype or 'ABA' in bname:
            return {
                'brand': 'ABA',
                'color': '#003366',
                'btn_icon': '🔴',
                'short_name': 'ABA Pay',
                'card_class': 'aba-card',
                'badge_class': 'bg-primary'
            }
        elif 'BAKONG' in btype or 'BAKONG' in bname:
            return {
                'brand': 'BAKONG',
                'color': '#cc0000',
                'btn_icon': '🔵',
                'short_name': 'Bakong KHQR',
                'card_class': 'bakong-card',
                'badge_class': 'bg-danger'
            }
        elif 'ACLEDA' in btype or 'ACLEDA' in bname:
            return {
                'brand': 'ACLEDA',
                'color': '#0d47a1',
                'btn_icon': '🟢',
                'short_name': 'ACLEDA Bank',
                'card_class': 'acleda-card',
                'badge_class': 'bg-success'
            }
        elif 'CANADIA' in btype or 'CANADIA' in bname:
            return {
                'brand': 'CANADIA',
                'color': '#b71c1c',
                'btn_icon': '🟠',
                'short_name': 'Canadia Bank',
                'card_class': 'canadia-card',
                'badge_class': 'bg-warning text-dark'
            }
        elif 'WING' in btype or 'WING' in bname:
            return {
                'brand': 'WING',
                'color': '#689f38',
                'btn_icon': '🟡',
                'short_name': 'Wing Bank',
                'card_class': 'wing-card',
                'badge_class': 'bg-info text-dark'
            }
        return {
            'brand': 'OTHER',
            'color': '#374151',
            'btn_icon': '🏦',
            'short_name': self.bank_name,
            'card_class': 'other-bank-card',
            'badge_class': 'bg-secondary'
        }

    def __str__(self):
        return f"{self.bank_name} - {self.account_name} ({self.account_number})"


# ==========================================================
# Parent Payment Slip Submission (បង្កាន់ដៃបង់ប្រាក់តាម Telegram)
# ==========================================================

class PaymentSlipSubmission(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'រង់ចាំផ្ទៀងផ្ទាត់ / Pending Verification'
        APPROVED = 'APPROVED', 'បានយល់ព្រម / Approved'
        REJECTED = 'REJECTED', 'បដិសេធ / Rejected'

    class FeeType(models.TextChoices):
        MONTHLY_UTILITY = 'MONTHLY_UTILITY', 'ថ្លៃទឹកភ្លើងប្រចាំខែ / Monthly Utilities'
        EARLY_YEAR_INVOICE = 'EARLY_YEAR_INVOICE', 'ថវិកាដើមឆ្នាំ/វិក្កយបត្រ / Early Year Invoice'
        ALL_DUE = 'ALL_DUE', 'ទូទាត់ជំពាក់ទាំងអស់ / All Due Fees'
        OTHER = 'OTHER', 'ផ្សេងៗ / Other'

    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='payment_slips', verbose_name="សិស្ស / Student")
    academic_year = models.ForeignKey('academics.AcademicYear', on_delete=models.CASCADE, verbose_name="ឆ្នាំសិក្សា / Academic Year")
    fee_type = models.CharField(max_length=30, choices=FeeType.choices, default=FeeType.MONTHLY_UTILITY, verbose_name="ប្រភេទកម្រៃ / Fee Type")
    target_months = models.JSONField(default=list, blank=True, verbose_name="ខែដែលបានបង់ / Target Months")
    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True, related_name='slip_submissions', verbose_name="វិក្កយបត្រ / Invoice")
    claimed_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="ចំនួនទឹកប្រាក់បង់ ($ / ៛) / Amount")
    currency = models.CharField(max_length=10, default="៛", verbose_name="រូបិយប័ណ្ណ / Currency")
    slip_image = models.ImageField(upload_to='payment_slips/%Y/%m/', blank=True, null=True, verbose_name="រូបថតបង្កាន់ដៃ / Slip Image")
    telegram_file_id = models.CharField(max_length=255, blank=True, null=True, verbose_name="Telegram File ID")
    telegram_user_id = models.CharField(max_length=100, blank=True, null=True, verbose_name="Telegram User ID")
    telegram_username = models.CharField(max_length=150, blank=True, null=True, verbose_name="Telegram Username")
    telegram_chat_id = models.CharField(max_length=100, blank=True, null=True, verbose_name="Telegram Chat ID")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, verbose_name="ស្ថានភាព / Status")
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="អ្នកផ្ទៀងផ្ទាត់ / Reviewed By")
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="កាលបរិច្ឆេទផ្ទៀងផ្ទាត់ / Reviewed At")
    notes = models.TextField(blank=True, null=True, verbose_name="កំណត់ចំណាំ / Notes")
    firestore_doc_id = models.CharField(max_length=100, blank=True, null=True, verbose_name="Firestore Doc ID")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "បង្កាន់ដៃបង់ប្រាក់អាណាព្យាបាល / Payment Slip Submission"
        verbose_name_plural = "បង្កាន់ដៃបង់ប្រាក់អាណាព្យាបាលទាំងអស់ / Payment Slip Submissions"

    def __str__(self):
        return f"Slip #{self.id} - {self.student.khmer_name} ({self.get_status_display()})"


# ==========================================================
# Local Firestore Payment Audit Log Mirror
# ==========================================================

class FirestorePaymentAuditLog(models.Model):
    class EventType(models.TextChoices):
        INQUIRY = 'INQUIRY', 'សាកសួរព័ត៌មានកម្រៃ / Student Fee Inquiry'
        QR_DISPATCH = 'QR_DISPATCH', 'បង្ហាញ QR Code / Bank QR Dispatched'
        SLIP_SUBMISSION = 'SLIP_SUBMISSION', 'ផ្ញើបង្កាន់ដៃបង់ប្រាក់ / Slip Submitted'
        PAYMENT_CONFIRMED = 'PAYMENT_CONFIRMED', 'បញ្ជាក់ការបង់ប្រាក់ / Payment Confirmed'
        CLOUD_SYNC = 'CLOUD_SYNC', 'Sync Cloud Firestore / Cloud Sync'

    event_type = models.CharField(max_length=30, choices=EventType.choices, default=EventType.INQUIRY, verbose_name="ប្រភេទព្រឹត្តិការណ៍ / Event Type")
    student = models.ForeignKey('students.Student', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="សិស្ស / Student")
    student_id_str = models.CharField(max_length=50, blank=True, null=True, verbose_name="អត្តលេខសិស្ស / Student ID")
    student_name = models.CharField(max_length=150, blank=True, null=True, verbose_name="ឈ្មោះសិស្ស / Student Name")
    classroom_name = models.CharField(max_length=100, blank=True, null=True, verbose_name="ថ្នាក់ / Classroom")
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="ចំនួនទឹកប្រាក់ / Amount")
    currency = models.CharField(max_length=10, default="៛", verbose_name="រូបិយប័ណ្ណ / Currency")
    fee_category_name = models.CharField(max_length=150, blank=True, null=True, verbose_name="ប្រភេទកម្រៃ / Fee Category")
    channel = models.CharField(max_length=50, default="TELEGRAM_BOT", verbose_name="ប៉ុស្តិ៍ទាក់ទង / Channel")
    telegram_user_info = models.CharField(max_length=200, blank=True, null=True, verbose_name="ព័ត៌មានអ្នកប្រើប្រាស់ Telegram")
    firestore_doc_id = models.CharField(max_length=100, blank=True, null=True, verbose_name="Firestore Doc ID")
    is_synced_to_firestore = models.BooleanField(default=False, verbose_name="បាន Sync ទៅ Firestore / Synced to Firestore")
    payload_data = models.JSONField(default=dict, blank=True, verbose_name="ទិន្នន័យលម្អិត / Payload Data")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="កាលបរិច្ឆេទ / Created At")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "កំណត់ត្រា Firestore Payment Log / Payment Audit Log"
        verbose_name_plural = "កំណត់ត្រា Firestore Payment Logs ទាំងអស់ / Payment Audit Logs"

    def __str__(self):
        return f"[{self.get_event_type_display()}] {self.student_name} - {self.amount:,.0f} {self.currency}"

