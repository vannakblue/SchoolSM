from django.db import models
from django.conf import settings
from decimal import Decimal

class Book(models.Model):
    isbn = models.CharField(max_length=50, blank=True, null=True, verbose_name="លេខកូដ ISBN / Book Code")
    title = models.CharField(max_length=200, verbose_name="ចំណងជើងសៀវភៅ / Book Title")
    author = models.CharField(max_length=150, blank=True, null=True, verbose_name="អ្នកនិពន្ធ / Author")
    category = models.CharField(max_length=100, default="General", verbose_name="ប្រភេទសៀវភៅ / Category")
    quantity = models.IntegerField(default=1, verbose_name="ចំនួនសរុប / Total Quantity")
    available_quantity = models.IntegerField(default=1, verbose_name="ចំនួននៅសល់ / Available Quantity")
    shelf_location = models.CharField(max_length=100, blank=True, null=True, verbose_name="ទីតាំងធ្នើសៀវភៅ / Shelf Location")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['title']
        verbose_name = "សៀវភៅបណ្ណាល័យ / Library Book"
        verbose_name_plural = "សៀវភៅបណ្ណាល័យទាំងអស់ / Library Books"

    def __str__(self):
        return f"{self.title} (នៅសល់: {self.available_quantity}/{self.quantity})"


class BookBorrowing(models.Model):
    class Status(models.TextChoices):
        BORROWED = 'BORROWED', 'កំពុងខ្ចី / Borrowed'
        RETURNED = 'RETURNED', 'សងរួចរាល់ / Returned'
        OVERDUE = 'OVERDUE', 'ហួសកំណត់ / Overdue'

    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='borrowings', verbose_name="សៀវភៅ / Book")
    student = models.ForeignKey('students.Student', on_delete=models.SET_NULL, null=True, blank=True, related_name='borrowed_books', verbose_name="សិស្សខ្ចី / Student")
    teacher = models.ForeignKey('teachers.Teacher', on_delete=models.SET_NULL, null=True, blank=True, related_name='borrowed_books', verbose_name="គ្រូខ្ចី / Teacher")
    borrow_date = models.DateField(auto_now_add=True, verbose_name="ថ្ងៃខ្ចី / Borrow Date")
    due_date = models.DateField(verbose_name="ថ្ងៃត្រូវសង / Due Date")
    return_date = models.DateField(blank=True, null=True, verbose_name="ថ្ងៃបានសង / Return Date")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.BORROWED, verbose_name="ស្ថានភាព / Status")
    notes = models.TextField(blank=True, null=True, verbose_name="កំណត់ចំណាំ / Notes")

    class Meta:
        ordering = ['-borrow_date']
        verbose_name = "ការខ្ចី-សងសៀវភៅ / Book Borrowing"
        verbose_name_plural = "ការខ្ចី-សងសៀវភៅទាំងអស់ / Book Borrowings"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            if self.book.available_quantity > 0:
                self.book.available_quantity -= 1
                self.book.save()
        elif self.status == self.Status.RETURNED and self.return_date:
            if self.book.available_quantity < self.book.quantity:
                self.book.available_quantity += 1
                self.book.save()

    def __str__(self):
        borrower = self.student.khmer_name if self.student else (self.teacher.khmer_name if self.teacher else "Unknown")
        return f"{self.book.title} -> {borrower} [{self.get_status_display()}]"


class InventoryItem(models.Model):
    class Category(models.TextChoices):
        UNIFORM = 'UNIFORM', 'ឯកសណ្ឋានសាលា / Uniform'
        TEXTBOOK = 'TEXTBOOK', 'សៀវភៅពុម្ព / Textbooks'
        STATIONERY = 'STATIONERY', 'សម្ភារៈសិក្សា / Stationery'
        EQUIPMENT = 'EQUIPMENT', 'ឧបករណ៍ & សម្ភារៈបង្រៀន / Equipment'
        OTHER = 'OTHER', 'ផ្សេងៗ / Other'

    item_code = models.CharField(max_length=50, unique=True, verbose_name="កូដសម្ភារៈ / Item Code")
    name = models.CharField(max_length=150, verbose_name="ឈ្មោះសម្ភារៈ / Item Name")
    category = models.CharField(max_length=30, choices=Category.choices, default=Category.UNIFORM, verbose_name="ប្រភេទ / Category")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="តម្លៃឯកតា ($) / Unit Price")
    stock_quantity = models.IntegerField(default=0, verbose_name="ចំនួនក្នុងស្តុក / Stock Quantity")
    min_alert_level = models.IntegerField(default=10, verbose_name="កម្រិតផ្តល់ដំណឹងជិតអស់ / Min Alert Level")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['category', 'name']
        verbose_name = "ស្តុកសម្ភារៈ / Inventory Item"
        verbose_name_plural = "ស្តុកសម្ភារៈទាំងអស់ / Inventory Items"

    @property
    def is_low_stock(self):
        return self.stock_quantity <= self.min_alert_level

    def __str__(self):
        return f"{self.name} ({self.stock_quantity} remaining)"


class InventoryTransaction(models.Model):
    class Type(models.TextChoices):
        STOCK_IN = 'STOCK_IN', 'នាំចូលស្តុក / Stock In'
        SALE_OUT = 'SALE_OUT', 'លក់/ចែកជូនសិស្ស / Sale Out'
        ADJUSTMENT = 'ADJUSTMENT', 'កែសម្រួលស្តុក / Stock Adjustment'

    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='transactions', verbose_name="សម្ភារៈ / Item")
    transaction_type = models.CharField(max_length=20, choices=Type.choices, default=Type.SALE_OUT, verbose_name="ប្រភេទប្រតិបត្តិការ / Type")
    quantity = models.IntegerField(verbose_name="ចំនួន / Quantity")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="តម្លៃឯកតា ($) / Unit Price")
    student = models.ForeignKey('students.Student', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="សិស្សទិញ / Student")
    date = models.DateTimeField(auto_now_add=True, verbose_name="កាលបរិច្ឆេទ / Date")
    notes = models.TextField(blank=True, null=True, verbose_name="កំណត់ចំណាំ / Notes")

    class Meta:
        ordering = ['-date']
        verbose_name = "ប្រតិបត្តិការស្តុក / Inventory Transaction"
        verbose_name_plural = "ប្រតិបត្តិការស្តុកទាំងអស់ / Inventory Transactions"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            if self.transaction_type == self.Type.STOCK_IN:
                self.item.stock_quantity += self.quantity
            elif self.transaction_type == self.Type.SALE_OUT:
                self.item.stock_quantity = max(0, self.item.stock_quantity - self.quantity)
            self.item.save()

    def __str__(self):
        return f"{self.get_transaction_type_display()}: {self.quantity} x {self.item.name}"


class Announcement(models.Model):
    class Category(models.TextChoices):
        GENERAL = 'GENERAL', 'ដំណឹងទូទៅ / General Notice'
        PARENT_MEETING = 'PARENT_MEETING', 'ការប្រជុំមាតាបិតា / Parent Meeting'
        HOLIDAY = 'HOLIDAY', 'ថ្ងៃឈប់សម្រាកបុណ្យ / Holiday Notice'
        EXAM_SCHEDULE = 'EXAM_SCHEDULE', 'កាលវិភាគប្រឡង / Exam Schedule'
        EVENT = 'EVENT', 'ព្រឹត្តិការណ៍ & កម្មវិធីសាលា / School Event'

    class TargetAudience(models.TextChoices):
        ALL = 'ALL', 'ទាំងអស់គ្នា (All Users)'
        TEACHERS = 'TEACHERS', 'គ្រូបង្រៀន (Teachers Only)'
        STUDENTS_PARENTS = 'STUDENTS_PARENTS', 'សិស្ស & មាតាបិតា (Students & Parents)'
        PARENTS_ONLY = 'PARENTS_ONLY', 'មាតាបិតាសិស្ស (Parents Only)'

    class Priority(models.TextChoices):
        NORMAL = 'NORMAL', 'ធម្មតា (Normal)'
        IMPORTANT = 'IMPORTANT', 'សំខាន់ (Important)'
        URGENT = 'URGENT', 'បន្ទាន់ (Urgent)'

    title = models.CharField(max_length=255, verbose_name="ចំណងជើងសេចក្តីជូនដំណឹង / Announcement Title")
    category = models.CharField(max_length=30, choices=Category.choices, default=Category.GENERAL, verbose_name="ប្រភេទ / Category")
    target_audience = models.CharField(max_length=30, choices=TargetAudience.choices, default=TargetAudience.ALL, verbose_name="ក្រុមគោលដៅ / Target Audience")
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.NORMAL, verbose_name="កម្រិតអាទិភាព / Priority")
    content = models.TextField(verbose_name="ខ្លឹមសារលម្អិត / Content")
    attachment = models.FileField(upload_to='announcements/docs/', blank=True, null=True, verbose_name="ឯកសារភ្ជាប់ / Attachment")
    is_published = models.BooleanField(default=True, verbose_name="ផ្សាយជាសាធារណៈ / Is Published")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="អ្នកបង្កើត / Created By")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="កាលបរិច្ឆេទផ្សាយ / Date")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "សេចក្តីជូនដំណឹង / Announcement"
        verbose_name_plural = "សេចក្តីជូនដំណឹងទាំងអស់ / Announcements"

    def __str__(self):
        return f"[{self.get_category_display()}] {self.title}"
