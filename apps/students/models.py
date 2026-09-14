from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from datetime import datetime

class StudentCategory(models.Model):
    name = models.CharField(max_length=150, unique=True, verbose_name="ឈ្មោះប្រភេទសិស្ស / Category Name")
    code = models.CharField(max_length=50, unique=True, blank=True, verbose_name="កូដសម្គាល់ / Code")
    description = models.TextField(blank=True, null=True, verbose_name="ការពិពណ៌នា / Description")
    is_active = models.BooleanField(default=True, verbose_name="សកម្ម / Active")
    display_order = models.PositiveIntegerField(default=1, verbose_name="លំដាប់លំដោយ / Display Order")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_order', 'id']
        verbose_name = "ប្រភេទសិស្ស / Student Category"
        verbose_name_plural = "ប្រភេទសិស្សទាំងអស់ / Student Categories"

    def save(self, *args, **kwargs):
        if not self.code:
            import re
            cleaned = re.sub(r'[^a-zA-Z0-9]', '_', self.name.strip().upper())
            self.code = cleaned[:30] or f"CAT_{StudentCategory.objects.count() + 1}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ScholarshipType(models.Model):
    name = models.CharField(max_length=150, unique=True, verbose_name="ឈ្មោះកម្រៃ/អាហារូបករណ៍ / Name (Khmer)")
    code = models.CharField(max_length=50, unique=True, verbose_name="កូដសម្គាល់ / Code (e.g. FULL_PAY, SCHOLARSHIP_50)")
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, verbose_name="ភាគរយបញ្ចុះតម្លៃ (%) / Discount (%)")
    description = models.TextField(blank=True, null=True, verbose_name="ការពិពណ៌នា / Description")
    is_active = models.BooleanField(default=True, verbose_name="សកម្ម / Active")
    order = models.PositiveIntegerField(default=1, verbose_name="លំដាប់លំដោយ / Display Order")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    _cached_map = None

    class Meta:
        ordering = ['order', 'id']
        verbose_name = "ប្រភេទកម្រៃ & អាហារូបករណ៍ / Scholarship & Fee Type"
        verbose_name_plural = "ប្រភេទកម្រៃ & អាហារូបករណ៍ទាំងអស់ / Scholarship & Fee Types"

    @classmethod
    def get_cached_map(cls):
        if cls._cached_map is None:
            try:
                cls._cached_map = {s.code: s for s in cls.objects.all()}
            except Exception:
                cls._cached_map = {}
        return cls._cached_map

    @classmethod
    def invalidate_cache(cls):
        cls._cached_map = None

    def save(self, *args, **kwargs):
        ScholarshipType.invalidate_cache()
        if not self.code:
            import re
            cleaned = re.sub(r'[^a-zA-Z0-9]', '_', self.name.strip().upper())
            self.code = cleaned[:30] or f"SCH_{ScholarshipType.objects.count() + 1}"
        super().save(*args, **kwargs)
        ScholarshipType.invalidate_cache()

    def delete(self, *args, **kwargs):
        ScholarshipType.invalidate_cache()
        super().delete(*args, **kwargs)
        ScholarshipType.invalidate_cache()

    def __str__(self):
        discount_text = f" ({self.discount_percentage:.0f}%)" if self.discount_percentage > 0 else ""
        return f"{self.name}{discount_text}"


class StudentStatusConfig(models.Model):
    """
    Dynamic Academic Status Configuration (e.g. Active, Suspended, Dropped, Transferred, Graduated, Medical Leave...)
    Allows Admin to create, edit, delete, color-code, and control behavior for student statuses.
    """
    class CategoryType(models.TextChoices):
        ACTIVE_STUDY = 'ACTIVE_STUDY', 'កំពុងសិក្សា (Active - រាប់ក្នុងបញ្ជីវត្តមាន និងប្រឡង)'
        SUSPENDED = 'SUSPENDED', 'ផ្អាកការសិក្សា (Suspended - ផ្អាកទារប្រាក់ខែ និងដកពីប្រឡង)'
        LEFT_SCHOOL = 'LEFT_SCHOOL', 'ឈប់រៀន / ផ្ទេរចេញ (Left / Transferred Out)'
        COMPLETED = 'COMPLETED', 'បញ្ចប់ការសិក្សា (Graduated / Completed)'

    class ColorScheme(models.TextChoices):
        SUCCESS = 'success', '🟢 បៃតង (Green)'
        WARNING = 'warning', '🟡 លឿង (Yellow)'
        DANGER = 'danger', '🔴 ក្រហម (Red)'
        INFO = 'info', '🔵 ខៀវស្រាល (Cyan)'
        PRIMARY = 'primary', '🟣 ខៀវចាស់ (Blue)'
        SECONDARY = 'secondary', '⚪ ប្រផេះ (Gray)'
        DARK = 'dark', '⚫ ខ្មៅ (Dark)'

    name = models.CharField(max_length=150, unique=True, verbose_name="ឈ្មោះស្ថានភាព (ខ្មែរ) / Name (Khmer)")
    name_en = models.CharField(max_length=150, blank=True, null=True, verbose_name="ឈ្មោះជាអង់គ្លេស / Name (English)")
    code = models.CharField(max_length=50, unique=True, verbose_name="កូដសម្គាល់ / Code (e.g. ACTIVE, SUSPENDED)")
    badge_color = models.CharField(max_length=30, choices=ColorScheme.choices, default=ColorScheme.SUCCESS, verbose_name="ពណ៌សម្គាល់ (Badge Color)")
    category_type = models.CharField(max_length=30, choices=CategoryType.choices, default=CategoryType.ACTIVE_STUDY, verbose_name="ប្រភេទឥរិយាបថ (Behavior Category)")
    description = models.TextField(blank=True, null=True, verbose_name="ការពិពណ៌នា / Description")
    is_system_default = models.BooleanField(default=False, verbose_name="ស្ថានភាពគោលរបស់ប្រព័ន្ធ / System Default")
    is_active = models.BooleanField(default=True, verbose_name="សកម្ម / Active")
    order = models.PositiveIntegerField(default=1, verbose_name="លំដាប់លំដោយ / Display Order")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    _cached_map = None

    class Meta:
        ordering = ['order', 'id']
        verbose_name = "ការកំណត់ស្ថានភាពសិក្សា / Student Status Config"
        verbose_name_plural = "ការកំណត់ស្ថានភាពសិក្សាទាំងអស់ / Student Status Configs"

    @classmethod
    def get_cached_map(cls):
        if cls._cached_map is None:
            try:
                cls._cached_map = {s.code: s for s in cls.objects.all()}
            except Exception:
                cls._cached_map = {}
        return cls._cached_map

    @classmethod
    def invalidate_cache(cls):
        cls._cached_map = None

    def save(self, *args, **kwargs):
        StudentStatusConfig.invalidate_cache()
        if not self.code:
            import re
            cleaned = re.sub(r'[^a-zA-Z0-9]', '_', self.name.strip().upper())
            self.code = cleaned[:30] or f"STATUS_{StudentStatusConfig.objects.count() + 1}"
        super().save(*args, **kwargs)
        StudentStatusConfig.invalidate_cache()

    def delete(self, *args, **kwargs):
        StudentStatusConfig.invalidate_cache()
        super().delete(*args, **kwargs)
        StudentStatusConfig.invalidate_cache()

    def __str__(self):
        return f"{self.name} ({self.code})"

    @classmethod
    def ensure_default_statuses(cls):
        """Initializes the standard 5 MoEYS statuses if they don't exist"""
        defaults = [
            {'code': 'ACTIVE', 'name': 'កំពុងរៀន', 'name_en': 'Active', 'badge_color': 'success', 'category_type': 'ACTIVE_STUDY', 'order': 1, 'is_system_default': True, 'description': 'សិស្សកំពុងរៀនជាប្រក្រតី រាប់ក្នុងវត្តមាន និងការប្រឡង'},
            {'code': 'SUSPENDED', 'name': 'ផ្អាកការសិក្សា', 'name_en': 'Suspended', 'badge_color': 'warning', 'category_type': 'SUSPENDED', 'order': 2, 'is_system_default': True, 'description': 'សិស្សផ្អាកការសិក្សាបណ្តោះអាសន្ន ផ្អាកទារប្រាក់កម្រៃ'},
            {'code': 'DROPPED', 'name': 'បោះបង់ / ឈប់រៀន', 'name_en': 'Dropped Out', 'badge_color': 'danger', 'category_type': 'LEFT_SCHOOL', 'order': 3, 'is_system_default': True, 'description': 'សិស្សឈប់រៀន ឬបោះបង់ការសិក្សា'},
            {'code': 'TRANSFERRED', 'name': 'ផ្ទេរការសិក្សា', 'name_en': 'Transferred', 'badge_color': 'info', 'category_type': 'LEFT_SCHOOL', 'order': 4, 'is_system_default': True, 'description': 'សិស្សផ្ទេរទៅសាលារៀនផ្សេង'},
            {'code': 'GRADUATED', 'name': 'បញ្ចប់ការសិក្សា', 'name_en': 'Graduated', 'badge_color': 'primary', 'category_type': 'COMPLETED', 'order': 5, 'is_system_default': True, 'description': 'សិស្សបានបញ្ចប់ការសិក្សាដោយជោគជ័យ'},
        ]
        try:
            existing_codes = set(cls.objects.values_list('code', flat=True))
            existing_names = set(cls.objects.values_list('name', flat=True))
            for item in defaults:
                if item['code'] not in existing_codes and item['name'] not in existing_names:
                    cls.objects.create(**item)
            cls.invalidate_cache()
        except Exception:
            pass


class Student(models.Model):
    class Gender(models.TextChoices):
        MALE = 'M', 'ប្រុស / Male'
        FEMALE = 'F', 'ស្រី / Female'

    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'កំពុងសិក្សា / Active'
        SUSPENDED = 'SUSPENDED', 'ផ្អាកការសិក្សា / Suspended'
        DROPPED = 'DROPPED', 'បោះបង់ការសិក្សា / Dropped'
        TRANSFERRED = 'TRANSFERRED', 'ផ្ទេរការសិក្សា / Transferred'
        GRADUATED = 'GRADUATED', 'បញ្ចប់ការសិក្សា / Graduated'

    class ScholarshipType(models.TextChoices):
        FULL_PAY = 'FULL_PAY', 'បង់ពេញ ១០០% / Full Pay (100%)'
        SCHOLARSHIP_50 = 'SCHOLARSHIP_50', 'អាហារូបករណ៍ ៥០% / Scholarship (50%)'
        SCHOLARSHIP_100 = 'SCHOLARSHIP_100', 'អាហារូបករណ៍ ១០០% (ឥតគិតថ្លៃ) / Free (100%)'
        INSTALLMENT = 'INSTALLMENT', 'បង់រំលស់ប្រចាំខែ / Monthly Installment'

    class ExamExclusionReason(models.TextChoices):
        DISCIPLINARY = 'DISCIPLINARY', 'បញ្ហាវិន័យ / ជាប់កិច្ចសន្យា / Disciplinary'
        SUSPENDED = 'SUSPENDED', 'ផ្អាកការសិក្សា / Suspended'
        DROPPED = 'DROPPED', 'ឈប់រៀន / Dropped Out'
        UNEXCUSED_ABSENCE = 'UNEXCUSED_ABSENCE', 'អវត្តមានច្រើនឥតច្បាប់ / Unexcused Absence'
        FEE_OVERDUE = 'FEE_OVERDUE', 'ជំពាក់ប្រាក់កម្រៃ / Fee Overdue'
        HEALTH = 'HEALTH', 'បញ្ហាសុខភាព / សម្រាកព្យាបាល / Health Issue'
        OTHER = 'OTHER', 'ផ្សេងៗ / Other'

    MONTH_CHOICES = [
        (1, 'ខែ ១ - មករា (January)'),
        (2, 'ខែ ២ - កុម្ភៈ (February)'),
        (3, 'ខែ ៣ - មីនា (March)'),
        (4, 'ខែ ៤ - មេសា (April)'),
        (5, 'ខែ ៥ - ឧសភា (May)'),
        (6, 'ខែ ៦ - មិថុនា (June)'),
        (7, 'ខែ ៧ - កក្កដា (July)'),
        (8, 'ខែ ៨ - សីហា (August)'),
        (9, 'ខែ ៩ - កញ្ញា (September)'),
        (10, 'ខែ ១០ - តុលា (October)'),
        (11, 'ខែ ១១ - វិច្ឆិកា (November)'),
        (12, 'ខែ ១២ - ធ្នូ (December)'),
    ]

    student_id = models.CharField(max_length=50, unique=True, blank=True, verbose_name="កូដសម្គាល់សិស្ស / Student ID")
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='student_profile')
    khmer_name = models.CharField(max_length=150, verbose_name="ឈ្មោះខ្មែរ / Khmer Name")
    latin_name = models.CharField(max_length=150, verbose_name="ឈ្មោះឡាតាំង / Latin Name")
    gender = models.CharField(max_length=5, choices=Gender.choices, default=Gender.MALE, verbose_name="ភេទ / Gender")
    date_of_birth = models.DateField(verbose_name="ថ្ងៃខែឆ្នាំកំណើត / Date of Birth")
    place_of_birth = models.CharField(max_length=255, blank=True, null=True, verbose_name="ទីកន្លែងកំណើត / Place of Birth")
    current_address = models.TextField(blank=True, null=True, verbose_name="អាសយដ្ឋានបច្ចុប្បន្ន / Current Address")
    phone = models.CharField(max_length=30, blank=True, null=True, verbose_name="លេខទូរស័ព្ទសិស្ស / Student Phone")
    previous_school = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="ឆ្នាំសិក្សាចាស់មកពីសាលា / Previous School & Academic Year",
        help_text="សាលារៀន និងឆ្នាំសិក្សាចាស់ដែលសិស្សបានរៀនពីមុន (ឧ. បឋមសិក្សា ហ៊ុន សែន ២០២៤-២០២៥)"
    )
    photo = models.ImageField(upload_to='students/photos/', blank=True, null=True, verbose_name="រូបថតសិស្ស (៤x៦) / Student Photo")
    photo_drive_url = models.URLField(max_length=500, blank=True, null=True, verbose_name="រូបថតលើ Google Drive (URL) / Google Drive Photo URL")
    birth_certificate = models.FileField(upload_to='students/docs/', blank=True, null=True, verbose_name="សំបុត្រកំណើត / Birth Certificate")
    
    # Academic association
    classroom = models.ForeignKey('academics.Classroom', on_delete=models.SET_NULL, null=True, blank=True, related_name='students', verbose_name="ថ្នាក់រៀន / Classroom")
    academic_year = models.ForeignKey('academics.AcademicYear', on_delete=models.SET_NULL, null=True, blank=True, related_name='enrolled_students', verbose_name="ឆ្នាំសិក្សា / Academic Year")
    enrollment_date = models.DateField(auto_now_add=True, verbose_name="ថ្ងៃចុះឈ្មោះ / Enrollment Date")
    fee_start_month = models.PositiveSmallIntegerField(blank=True, null=True, choices=MONTH_CHOICES, verbose_name="ខែចាប់ផ្តើមបង់ប្រាក់ / Fee Start Month", help_text="ខែដែលសិស្សត្រូវចាប់ផ្តើមបង់ប្រាក់ (ទុកទទេដើម្បីគិតចាប់ពីដើមឆ្នាំសិក្សា)")
    fee_end_month = models.PositiveSmallIntegerField(blank=True, null=True, choices=MONTH_CHOICES, verbose_name="ខែបញ្ចប់/ផ្អាកការបង់ប្រាក់ / Fee End Month", help_text="ខែចុងក្រោយដែលសិស្សត្រូវបង់ប្រាក់ (សម្រាប់សិស្សឈប់រៀន ឬផ្អាកការសិក្សា ទុកទទេដើម្បីបង់ដល់ចប់ឆ្នាំ)")
    status = models.CharField(max_length=50, choices=Status.choices, default=Status.ACTIVE, verbose_name="ស្ថានភាព / Status")
    scholarship_type = models.CharField(max_length=50, default='FULL_PAY', verbose_name="ប្រភេទកម្រៃសិក្សា / Fee Type")
    category = models.ForeignKey(StudentCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='students', verbose_name="ប្រភេទសិស្ស / Student Category")
    enrollment_data = models.JSONField(default=dict, blank=True, verbose_name="ទិន្នន័យបន្ថែមតាមកម្រិតថ្នាក់ / Grade Specific Data")

    # Exam Suspension & Exclusion Fields (Configurable directly from Student List)
    is_exam_suspended = models.BooleanField(
        default=False,
        verbose_name="ដកចេញពីការប្រឡង / Disqualified from Exam",
        help_text="កំណត់ដកសិទ្ធិមិនឱ្យសិស្សចូលរួមការប្រឡង"
    )
    exam_suspension_reason = models.CharField(
        max_length=50,
        choices=ExamExclusionReason.choices,
        default=ExamExclusionReason.DISCIPLINARY,
        blank=True,
        null=True,
        verbose_name="មូលហេតុដកសិទ្ធិប្រឡង / Exam Exclusion Reason"
    )
    exam_suspension_notes = models.TextField(
        blank=True,
        null=True,
        verbose_name="កំណត់សម្គាល់ដកសិទ្ធិប្រឡង / Exam Suspension Notes"
    )

    # Promotion & Grade Retention Tracking (ឡើងថ្នាក់ & ត្រួតថ្នាក់)
    is_repeating_grade = models.BooleanField(
        default=False,
        verbose_name="ជាសិស្សត្រួតថ្នាក់ / Is Repeating Grade",
        help_text="សិស្សដែលរៀនត្រួតថ្នាក់ក្នុងកម្រិតថ្នាក់ដដែល"
    )
    last_promotion_status = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="ស្ថានភាពឡើង/ត្រួតថ្នាក់ចុងក្រោយ / Last Promotion Status"
    )
    last_promotion_reason = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="មូលហេតុឡើង/ត្រួតថ្នាក់ចុងក្រោយ / Last Promotion Reason"
    )

    # Parent & Guardian Info
    father_name = models.CharField(max_length=150, blank=True, null=True, verbose_name="ឈ្មោះឪពុក / Father Name")
    father_phone = models.CharField(max_length=30, blank=True, null=True, verbose_name="លេខទូរស័ព្ទឪពុក / Father Phone")
    father_job = models.CharField(max_length=150, blank=True, null=True, verbose_name="មុខរបរឪពុក / Father Occupation")
    mother_name = models.CharField(max_length=150, blank=True, null=True, verbose_name="ឈ្មោះម្តាយ / Mother Name")
    mother_phone = models.CharField(max_length=30, blank=True, null=True, verbose_name="លេខទូរស័ព្ទម្តាយ / Mother Phone")
    mother_job = models.CharField(max_length=150, blank=True, null=True, verbose_name="មុខរបរម្តាយ / Mother Occupation")
    guardian_name = models.CharField(max_length=150, blank=True, null=True, verbose_name="ឈ្មោះអាណាព្យាបាលជំនួស / Guardian Name")
    emergency_phone = models.CharField(max_length=30, blank=True, null=True, verbose_name="លេខទាក់ទងបន្ទាន់ / Emergency Phone")
    telegram_chat_id = models.CharField(max_length=50, blank=True, null=True, verbose_name="Telegram Chat ID អាណាព្យាបាល")

    # Student Verification & Beginning-of-Year Confirmation Tracking
    is_verified = models.BooleanField(
        default=False,
        verbose_name="បានផ្ទៀងផ្ទាត់ព័ត៌មាន / Is Verified"
    )
    last_verified_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="កាលបរិច្ឆេទផ្ទៀងផ្ទាត់ចុងក្រោយ / Last Verified At"
    )
    last_verified_by_role = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        verbose_name="តួនាទីអ្នកផ្ទៀងផ្ទាត់ចុងក្រោយ / Last Verified By Role"
    )
    last_verified_by_name = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        verbose_name="ឈ្មោះអ្នកផ្ទៀងផ្ទាត់ចុងក្រោយ / Last Verified By Name"
    )
    verification_round = models.PositiveIntegerField(
        default=0,
        verbose_name="ជុំផ្ទៀងផ្ទាត់ / Verification Round"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['classroom__grade_level', 'classroom__code', 'student_id']
        verbose_name = "សិស្ស / Student"
        verbose_name_plural = "សិស្សទាំងអស់ / Students"

    @property
    def display_name(self):
        return f"{self.khmer_name} ({self.latin_name})"

    @property
    def scholarship_name(self):
        """Returns dynamic scholarship name if available, fallback to choice label or raw string"""
        try:
            st = ScholarshipType.get_cached_map().get(self.scholarship_type)
            if st:
                return st.name
        except Exception:
            pass
        try:
            return dict(Student.ScholarshipType.choices).get(self.scholarship_type, self.scholarship_type)
        except Exception:
            return self.scholarship_type

    @property
    def scholarship_discount_percentage(self):
        """Returns discount percentage as a decimal/float"""
        try:
            st = ScholarshipType.get_cached_map().get(self.scholarship_type)
            if st:
                return float(st.discount_percentage)
        except Exception:
            pass
        if self.scholarship_type == 'SCHOLARSHIP_50':
            return 50.0
        elif self.scholarship_type == 'SCHOLARSHIP_100':
            return 100.0
        return 0.0

    def get_scholarship_type_display(self):
        return self.scholarship_name

    @property
    def status_config(self):
        """Returns the dynamic StudentStatusConfig object for this student's status"""
        try:
            return StudentStatusConfig.get_cached_map().get(self.status)
        except Exception:
            return None

    @property
    def status_display_name(self):
        """Returns dynamic status name if available, fallback to choice label"""
        cfg = self.status_config
        if cfg:
            return cfg.name
        try:
            return dict(Student.Status.choices).get(self.status, self.status)
        except Exception:
            return self.status

    @property
    def status_badge_color(self):
        """Returns badge color: success, warning, danger, info, primary, secondary"""
        cfg = self.status_config
        if cfg:
            return cfg.badge_color
        color_map = {
            'ACTIVE': 'success',
            'SUSPENDED': 'warning',
            'DROPPED': 'danger',
            'TRANSFERRED': 'info',
            'GRADUATED': 'primary',
        }
        return color_map.get(self.status, 'secondary')

    def get_status_display(self):
        return self.status_display_name

    @property
    def photo_url(self):
        """Returns Google Drive photo URL if available, otherwise local uploaded photo URL."""
        if self.photo_drive_url:
            return self.photo_drive_url
        if self.photo:
            try:
                return self.photo.url
            except Exception:
                pass
        return None

    @property
    def is_disqualified_from_exams(self):
        """Returns True if student is suspended, dropped, transferred, or specifically disqualified from exams"""
        if self.status in [self.Status.SUSPENDED, self.Status.DROPPED, self.Status.TRANSFERRED]:
            return True
        if self.is_exam_suspended:
            return True
        try:
            if self.exam_exclusions.filter(is_active=True).exists():
                return True
        except Exception:
            pass
        return False

    @property
    def effective_exam_exclusion_reason(self):
        """Returns human-readable reason for exam exclusion"""
        if self.is_exam_suspended:
            try:
                return dict(self.ExamExclusionReason.choices).get(self.exam_suspension_reason, self.exam_suspension_reason or 'បញ្ហាវិន័យ')
            except Exception:
                return self.exam_suspension_reason or 'បញ្ហាវិន័យ'
        if self.status != self.Status.ACTIVE:
            return self.get_status_display()
        try:
            active_exc = self.exam_exclusions.filter(is_active=True).first()
            if active_exc:
                return active_exc.get_reason_display()
        except Exception:
            pass
        return ''

    def get_exam_suspension_reason_display(self):
        return self.effective_exam_exclusion_reason

    @classmethod
    def generate_unique_student_id(cls, academic_year=None, exclude_pk=None, custom_prefix=None, grade_level=None, classroom=None):
        """
        Generates a guaranteed collision-free, strictly unique student ID.
        By default, extracts the ending academic year (e.g., '2026-2027' -> '27').
        Applies school-configured pattern from SchoolProfile:
        - YEAR_END_4D: {year2}{seq:04d} e.g. 270001
        - YEAR_END_5D: {year2}{seq:05d} e.g. 2700001
        - PREFIX_YEAR_4D: {prefix}-{year2}-{seq:04d} e.g. STU-27-0001
        - PREFIX_YEAR_5D: {prefix}-{year2}-{seq:05d} e.g. STU-27-00001
        - GRADE_YEAR_4D: {grade}-{year2}-{seq:04d} e.g. 7-27-0001
        - CUSTOM_PATTERN: Custom template e.g. {PREFIX}-{YEAR2}-{SEQ}
        """
        import re
        from datetime import datetime

        # 1. Resolve academic year if not passed
        if not academic_year and classroom and hasattr(classroom, 'academic_year'):
            academic_year = classroom.academic_year
        if not academic_year:
            from apps.academics.models import AcademicYear
            academic_year = AcademicYear.objects.filter(is_current=True).first()

        # 2. Extract ending year (and start year)
        # Academic year name format examples: '2026-2027', '២០២៦-២០២៧', '2026 - 2027', '2026'
        khmer_to_latin = str.maketrans('០១២៣៤៥៦៧៨៩', '0123456789')
        end_year_val = None
        start_year_val = None

        if academic_year:
            name_str = getattr(academic_year, 'name', '') or ''
            converted_name = name_str.translate(khmer_to_latin)
            year_matches = re.findall(r'\b(20\d\d|19\d\d|\d{4})\b', converted_name)
            if len(year_matches) >= 2:
                start_year_val = int(year_matches[0])
                end_year_val = int(year_matches[-1])
            elif len(year_matches) == 1:
                end_year_val = int(year_matches[0])
                start_year_val = end_year_val

            # If end_date provides more information
            if not end_year_val and getattr(academic_year, 'end_date', None):
                end_year_val = academic_year.end_date.year
            if not start_year_val and getattr(academic_year, 'start_date', None):
                start_year_val = academic_year.start_date.year

        if not end_year_val:
            end_year_val = datetime.now().year
        if not start_year_val:
            start_year_val = end_year_val

        year2 = f"{end_year_val % 100:02d}"
        start_year2 = f"{start_year_val % 100:02d}"
        year4 = f"{end_year_val:04d}"
        start_year4 = f"{start_year_val:04d}"

        # 3. Resolve grade level
        grade_str = ""
        if grade_level is not None:
            grade_str = str(grade_level).strip()
        elif classroom and getattr(classroom, 'grade_level', None):
            grade_str = str(classroom.grade_level).strip()

        # 4. Fetch School Profile Settings
        from apps.accounts.models import SchoolProfile
        try:
            profile = SchoolProfile.get_settings()
        except Exception:
            profile = None

        pattern_choice = getattr(profile, 'student_id_pattern', 'YEAR_END_4D') if profile else 'YEAR_END_4D'
        cfg_prefix = (getattr(profile, 'student_id_prefix', '') or 'STU').strip() if profile else 'STU'
        cfg_digits = getattr(profile, 'student_id_digits', 4) or 4
        cfg_template = (getattr(profile, 'student_id_custom_template', '') or '{PREFIX}-{YEAR2}-{SEQ}').strip() if profile else '{PREFIX}-{YEAR2}-{SEQ}'
        include_grade = getattr(profile, 'student_id_include_grade', False) if profile else False

        # If custom_prefix is explicitly provided by caller, prioritize it
        if custom_prefix is not None and str(custom_prefix).strip() != '':
            id_prefix = str(custom_prefix).strip()
            id_suffix = ""
            digits = 4
        else:
            # Build prefix and suffix around the sequence number
            if pattern_choice == 'YEAR_END_5D':
                digits = 5
                if include_grade and grade_str:
                    id_prefix = f"{grade_str}-{year2}-"
                else:
                    id_prefix = f"{year2}"
                id_suffix = ""
            elif pattern_choice == 'PREFIX_YEAR_4D':
                digits = 4
                if include_grade and grade_str:
                    id_prefix = f"{cfg_prefix}-{grade_str}-{year2}-"
                else:
                    id_prefix = f"{cfg_prefix}-{year2}-"
                id_suffix = ""
            elif pattern_choice == 'PREFIX_YEAR_5D':
                digits = 5
                if include_grade and grade_str:
                    id_prefix = f"{cfg_prefix}-{grade_str}-{year2}-"
                else:
                    id_prefix = f"{cfg_prefix}-{year2}-"
                id_suffix = ""
            elif pattern_choice == 'GRADE_YEAR_4D':
                digits = cfg_digits or 4
                id_prefix = f"{grade_str}-{year2}-" if grade_str else f"{year2}-"
                id_suffix = ""
            elif pattern_choice == 'CUSTOM_PATTERN':
                digits = cfg_digits or 4
                raw_template = cfg_template
                if '{SEQ}' in raw_template:
                    parts = raw_template.split('{SEQ}', 1)
                    raw_prefix = parts[0]
                    raw_suffix = parts[1]
                else:
                    raw_prefix = raw_template + "-"
                    raw_suffix = ""

                # Token replacements
                token_map = {
                    '{PREFIX}': cfg_prefix,
                    '{YEAR2}': year2,
                    '{START_YEAR2}': start_year2,
                    '{YEAR4}': year4,
                    '{START_YEAR4}': start_year4,
                    '{GRADE}': grade_str or '',
                }
                for tok, val in token_map.items():
                    raw_prefix = raw_prefix.replace(tok, val)
                    raw_suffix = raw_suffix.replace(tok, val)

                id_prefix = raw_prefix
                id_suffix = raw_suffix
            else:  # Default YEAR_END_4D
                digits = cfg_digits or 4
                if include_grade and grade_str:
                    id_prefix = f"{grade_str}-{year2}-"
                else:
                    id_prefix = f"{year2}"
                id_suffix = ""

        # 5. Scan database for existing IDs with id_prefix to find max sequence
        escaped_prefix = re.escape(id_prefix)
        escaped_suffix = re.escape(id_suffix)
        seq_pattern = re.compile(rf'^{escaped_prefix}(\d+){escaped_suffix}$')

        candidates = cls.objects.filter(student_id__startswith=id_prefix).values_list('student_id', flat=True)
        max_num = 0
        for sid in candidates:
            m = seq_pattern.match(sid)
            if m:
                try:
                    num = int(m.group(1))
                    if num > max_num:
                        max_num = num
                except (ValueError, TypeError):
                    continue

        new_num = max_num + 1
        candidate_id = f"{id_prefix}{new_num:0{digits}d}{id_suffix}"

        # 6. Collision detection loop to guarantee 100% uniqueness
        qs = cls.objects.filter(student_id__iexact=candidate_id)
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)

        while qs.exists():
            new_num += 1
            candidate_id = f"{id_prefix}{new_num:0{digits}d}{id_suffix}"
            qs = cls.objects.filter(student_id__iexact=candidate_id)
            if exclude_pk:
                qs = qs.exclude(pk=exclude_pk)

        return candidate_id

    @property
    def clean_latin_name(self):
        """Returns clean Latin name without any leftover Khmer characters"""
        import re
        from .khmer_romanizer import romanize_khmer_name
        if not self.latin_name or re.search(r'[\u1780-\u17FF]', str(self.latin_name)):
            return romanize_khmer_name(self.khmer_name)
        return self.latin_name

    def clean(self):
        super().clean()
        if self.student_id:
            self.student_id = str(self.student_id).strip()
            qs = Student.objects.filter(student_id__iexact=self.student_id)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                existing = qs.first()
                class_info = f" ({existing.classroom.name})" if existing.classroom else ""
                raise ValidationError({
                    'student_id': f"អត្តលេខសិស្ស '{self.student_id}' ត្រូវបានប្រើប្រាស់រួចហើយដោយសិស្ស {existing.khmer_name}{class_info}! សូមបញ្ចូលអត្តលេខផ្សេង ឬទុកទទេដើម្បីឱ្យប្រព័ន្ធបង្កើតស្វ័យប្រវត្តិ។"
                })

    def save(self, *args, **kwargs):
        # Auto-generate or format student ID
        if not self.student_id or str(self.student_id).strip() == '':
            target_year = self.academic_year or (self.classroom.academic_year if self.classroom else None)
            grade_lvl = self.classroom.grade_level if self.classroom else None
            self.student_id = Student.generate_unique_student_id(
                academic_year=target_year,
                exclude_pk=self.pk,
                grade_level=grade_lvl,
                classroom=self.classroom
            )
        else:
            self.student_id = str(self.student_id).strip()
            # Double check collision on save
            qs = Student.objects.filter(student_id__iexact=self.student_id)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                existing = qs.first()
                class_info = f" ({existing.classroom.name})" if existing.classroom else ""
                raise ValidationError({
                    'student_id': f"អត្តលេខសិស្ស '{self.student_id}' ត្រូវបានប្រើប្រាស់រួចហើយដោយសិស្ស {existing.khmer_name}{class_info}!"
                })

        # Auto-clean and romanize Latin name if missing or corrupted
        import re
        from .khmer_romanizer import romanize_khmer_name
        if not self.latin_name or re.search(r'[\u1780-\u17FF]', str(self.latin_name)):
            self.latin_name = romanize_khmer_name(self.khmer_name)

        super().save(*args, **kwargs)

    def __str__(self):
        class_name = self.classroom.name if self.classroom else "គ្មានថ្នាក់"
        return f"{self.student_id} - {self.khmer_name} [{class_name}]"


class StudentPromotionRecord(models.Model):
    """
    Tracks historical promotion and retention decisions for individual students at end-of-year.
    """
    class Action(models.TextChoices):
        PROMOTE = 'PROMOTE', 'ឡើងថ្នាក់ / Promoted to Next Grade'
        RETAIN = 'RETAIN', 'ត្រួតថ្នាក់ / Retained in Same Grade'
        GRADUATE = 'GRADUATE', 'បញ្ចប់ការសិក្សា / Graduated'
        TRANSFER = 'TRANSFER', 'ផ្ទេរចេញ / Transferred Out'
        DROP = 'DROP', 'ឈប់រៀន / Dropped Out'

    class StandardReason(models.TextChoices):
        PASSED_YEAR = 'PASSED_YEAR', 'ជាប់មធ្យមភាគប្រចាំឆ្នាំ (Passed Yearly Average)'
        FAILED_YEAR = 'FAILED_YEAR', 'ធ្លាក់មធ្យមភាគប្រចាំឆ្នាំ (< ៥០.០០) (Failed Yearly Average)'
        EXCESSIVE_ABSENCE = 'EXCESSIVE_ABSENCE', 'អវត្តមានច្រើនហួសកម្រិតកំណត់ (Excessive Absences)'
        VOLUNTARY_RETENTION = 'VOLUNTARY_RETENTION', 'សុំត្រួតថ្នាក់ដោយស្ម័គ្រចិត្ត (Voluntary Grade Retention)'
        DISCIPLINARY_BOARD = 'DISCIPLINARY_BOARD', 'សេចក្តីសម្រេចក្រុមប្រឹក្សាវិន័យ (Disciplinary Board Decision)'
        TEST_SCORE_LOW = 'TEST_SCORE_LOW', 'លទ្ធផលតេស្តសមត្ថភាពមិនគ្រប់ (Low Standardized Test Score)'
        EXCELLENT_DOUBLE_PROMOTION = 'EXCELLENT_DOUBLE_PROMOTION', 'លទ្ធផលសិក្សាឆ្នើម / លោតថ្នាក់ (Double Promotion)'
        OTHER = 'OTHER', 'ផ្សេងៗ (Other Reason)'

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='promotion_records', verbose_name="សិស្ស / Student")
    from_academic_year = models.ForeignKey('academics.AcademicYear', on_delete=models.SET_NULL, null=True, blank=True, related_name='promotions_from', verbose_name="ឆ្នាំសិក្សាដើម / From Year")
    to_academic_year = models.ForeignKey('academics.AcademicYear', on_delete=models.SET_NULL, null=True, blank=True, related_name='promotions_to', verbose_name="ឆ្នាំសិក្សាថ្មី / To Year")
    from_classroom = models.ForeignKey('academics.Classroom', on_delete=models.SET_NULL, null=True, blank=True, related_name='promotions_from_class', verbose_name="ថ្នាក់ដើម / From Class")
    to_classroom = models.ForeignKey('academics.Classroom', on_delete=models.SET_NULL, null=True, blank=True, related_name='promotions_to_class', verbose_name="ថ្នាក់ថ្មី / To Class")
    action = models.CharField(max_length=50, choices=Action.choices, default=Action.PROMOTE, verbose_name="សកម្មភាព / Action")
    standard_reason = models.CharField(max_length=100, choices=StandardReason.choices, default=StandardReason.PASSED_YEAR, verbose_name="មូលហេតុស្តង់ដារ / Standard Reason")
    custom_notes = models.TextField(blank=True, null=True, verbose_name="កំណត់សម្គាល់ & មូលហេតុលម្អិត / Notes & Reason Details")
    processed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_promotions', verbose_name="ចាត់ចែងដោយ / Processed By")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="កាលបរិច្ឆេទ & ម៉ោង / Created At")

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = "កំណត់ត្រាឡើង/ត្រួតថ្នាក់ / Student Promotion Record"
        verbose_name_plural = "កំណត់ត្រាឡើង/ត្រួតថ្នាក់ទាំងអស់ / Student Promotion Records"

    def __str__(self):
        from_c = self.from_classroom.name if self.from_classroom else 'គ្មាន'
        to_c = self.to_classroom.name if self.to_classroom else 'គ្មាន'
        return f"{self.student.khmer_name} - {self.get_action_display()} ({from_c} ➡️ {to_c})"


class AcademicYearStudentArchive(models.Model):
    class ActionType(models.TextChoices):
        SOFT_UNENROLL = 'SOFT_UNENROLL', 'ដកសិស្សចេញពីឆ្នាំ (Soft Unenroll & Clear)'
        PURGE_DELETE = 'PURGE_DELETE', 'លុបសិស្សចេញពីប្រព័ន្ធ (Full Purge & Delete)'

    academic_year = models.ForeignKey('academics.AcademicYear', on_delete=models.CASCADE, related_name='student_archives', verbose_name="ឆ្នាំសិក្សា / Academic Year")
    academic_year_name = models.CharField(max_length=150, verbose_name="ឈ្មោះឆ្នាំសិក្សា / Academic Year Name")
    archived_at = models.DateTimeField(auto_now_add=True, verbose_name="កាលបរិច្ឆេទរក្សាទុក / Archived At")
    archived_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='student_archives_created', verbose_name="រៀបចំដោយ / Archived By")
    action_type = models.CharField(max_length=30, choices=ActionType.choices, default=ActionType.SOFT_UNENROLL, verbose_name="ប្រភេទប្រតិបត្តិការ / Action Type")
    students_count = models.PositiveIntegerField(default=0, verbose_name="ចំនួនសិស្ស / Students Count")
    classrooms_count = models.PositiveIntegerField(default=0, verbose_name="ចំនួនថ្នាក់ / Classrooms Count")
    grades_count = models.PositiveIntegerField(default=0, verbose_name="ចំនួនកំណត់ត្រាពិន្ទុ / Grades Count")
    attendances_count = models.PositiveIntegerField(default=0, verbose_name="ចំនួនកំណត់ត្រាវត្តមាន / Attendances Count")
    fees_count = models.PositiveIntegerField(default=0, verbose_name="ចំនួនវិក្កយបត្រ / Fees Count")
    archive_payload = models.JSONField(default=dict, blank=True, verbose_name="ទិន្នន័យ Snapshot (JSON) / Archive Payload")
    archive_excel = models.FileField(upload_to='archives/students/', blank=True, null=True, verbose_name="ឯកសារ Excel ប័ណ្ណសារ / Archive Excel File")
    confirmation_note = models.TextField(blank=True, null=True, verbose_name="កំណត់សម្គាល់សុវត្ថិភាព / Confirmation Note")

    class Meta:
        ordering = ['-archived_at']
        verbose_name = "ប័ណ្ណសារសិស្សប្រចាំឆ្នាំ / Student Year Archive"
        verbose_name_plural = "ប័ណ្ណសារសិស្សប្រចាំឆ្នាំទាំងអស់ / Student Year Archives"

    def __str__(self):
        return f"ប័ណ្ណសារ {self.academic_year_name} ({self.students_count} នាក់) - {self.archived_at.strftime('%d/%m/%Y %H:%M')}"


class StudentVerificationCampaign(models.Model):
    """
    Beginning-of-Year or Periodic Student Information Filling & Verification Campaign.
    Configurable by Admin. Allows multiple rounds (ជុំទី១, ជុំទី២...) to verify/cross-check student data.
    """
    title = models.CharField(
        max_length=200,
        verbose_name="ឈ្មោះយុទ្ធនាការ / ជុំផ្ទៀងផ្ទាត់ (Campaign Title)",
        help_text="ឧ. ការបំពេញ និងផ្ទៀងផ្ទាត់ព័ត៌មានសិស្សដើមឆ្នាំ ២០២៦-២០២៧ (ជុំទី១)"
    )
    round_number = models.PositiveIntegerField(
        default=1,
        verbose_name="ជុំទី / Round Number",
        help_text="លេខជុំ (១, ២, ៣...) អនុញ្ញាតឱ្យធ្វើច្រើនដងដើម្បីផ្ទៀងផ្ទាត់ព័ត៌មានសិស្ស"
    )
    academic_year = models.ForeignKey(
        'academics.AcademicYear',
        on_delete=models.CASCADE,
        related_name='verification_campaigns',
        verbose_name="ឆ្នាំសិក្សា / Academic Year"
    )
    start_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="កាលបរិច្ឆេទចាប់ផ្តើម / Start Date & Time"
    )
    end_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="កាលបរិច្ឆេទផុតកំណត់ / End Date & Time"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="បើកដំណើរការ / Active Status"
    )
    require_confirmation_for_existing = models.BooleanField(
        default=True,
        verbose_name="ទាមទារការបញ្ជាក់ពេលកែប្រែសិស្សចាស់ / Require Confirmation for Existing Students",
        help_text="តម្រូវឱ្យសិស្ស អាណាព្យាបាល ឬគ្រូដែលកំពុងបញ្ចូល ធ្វើការបញ្ជាក់ (Confirm) មុនពេលកែប្រែទិន្នន័យ"
    )
    allow_student_self_confirm = models.BooleanField(
        default=True,
        verbose_name="អនុញ្ញាតឱ្យសិស្សបញ្ជាក់ / Allow Student Confirmation"
    )
    allow_parent_confirm = models.BooleanField(
        default=True,
        verbose_name="អនុញ្ញាតឱ្យអាណាព្យាបាលបញ្ជាក់ / Allow Parent Confirmation"
    )
    allow_teacher_confirm = models.BooleanField(
        default=True,
        verbose_name="អនុញ្ញាតឱ្យគ្រូបង្រៀនបញ្ជាក់ / Allow Teacher Confirmation"
    )
    target_grades = models.ManyToManyField(
        'academics.GradeLevel',
        blank=True,
        related_name='verification_campaigns',
        verbose_name="កម្រិតថ្នាក់គោលដៅ / Target Grade Levels",
        help_text="ទុកទទេដើម្បីអនុវត្តចំពោះគ្រប់កម្រិតថ្នាក់ទាំងអស់"
    )
    instructions = models.TextField(
        blank=True,
        null=True,
        verbose_name="សេចក្តីណែនាំ / Instructions",
        help_text="សេចក្តីណែនាំបង្ហាញដល់សិស្ស អាណាព្យាបាល និងគ្រូពេលបំពេញទិន្នន័យ"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_verification_campaigns',
        verbose_name="បង្កើតដោយ / Created By"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-academic_year__start_date', '-round_number', '-created_at']
        verbose_name = "យុទ្ធនាការផ្ទៀងផ្ទាត់ព័ត៌មានសិស្ស / Student Verification Campaign"
        verbose_name_plural = "យុទ្ធនាការផ្ទៀងផ្ទាត់ព័ត៌មានសិស្សទាំងអស់ / Student Verification Campaigns"

    def is_open(self):
        if not self.is_active:
            return False
        from django.utils import timezone
        now = timezone.now()
        if self.start_date and now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False
        return True

    def get_status_display_kh(self):
        if not self.is_active:
            return "បានបិទ (Inactive)"
        from django.utils import timezone
        now = timezone.now()
        if self.start_date and now < self.start_date:
            return "មិនទាន់ដល់ពេល (Upcoming)"
        if self.end_date and now > self.end_date:
            return "ផុតកំណត់ (Expired)"
        return "កំពុងដំណើរការ (Active)"

    def get_total_students_count(self):
        qs = Student.objects.filter(academic_year=self.academic_year)
        target_grades = self.target_grades.all()
        if target_grades.exists():
            grade_nums = target_grades.values_list('grade_number', flat=True)
            qs = qs.filter(classroom__grade_level__in=grade_nums)
        return qs.count()

    def get_verified_students_count(self):
        qs = Student.objects.filter(academic_year=self.academic_year, is_verified=True)
        target_grades = self.target_grades.all()
        if target_grades.exists():
            grade_nums = target_grades.values_list('grade_number', flat=True)
            qs = qs.filter(classroom__grade_level__in=grade_nums)
        return qs.count()

    def get_verification_percentage(self):
        total = self.get_total_students_count()
        if total == 0:
            return 0
        verified = self.get_verified_students_count()
        return round((verified / total) * 100, 1)

    def __str__(self):
        return f"{self.title} [ជុំទី {self.round_number}] ({self.academic_year.name})"


class GradeVerificationFormConfig(models.Model):
    """
    Form Template Configuration per Grade Level.
    Allows Admin to choose which form format/template (បែបបទ) students of each grade level must fill.
    Options:
    - GENERAL: Standard Admin-configured enrollment form (with dynamic GradeEnrollmentOptions)
    - MOEYS_INDIVIDUAL: MoEYS 35-Column Census Individual Extract Form
    - CUSTOM_COMBINED: Combined form containing both General and MoEYS fields
    """
    class FormTemplate(models.TextChoices):
        GENERAL = 'GENERAL', 'បែបបទចុះឈ្មោះទូទៅ (Admin កំណត់) / General Form'
        MOEYS_INDIVIDUAL = 'MOEYS_INDIVIDUAL', 'បែបបទសម្រង់ព័ត៌មានសិស្សម្នាក់ៗ (MoEYS Census 35 Columns)'
        CUSTOM_COMBINED = 'CUSTOM_COMBINED', 'បែបបទរួមបញ្ចូល (General + MoEYS Census)'

    grade_level = models.ForeignKey(
        'academics.GradeLevel',
        on_delete=models.CASCADE,
        related_name='form_configurations',
        verbose_name="កម្រិតថ្នាក់ / Grade Level"
    )
    campaign = models.ForeignKey(
        StudentVerificationCampaign,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='grade_form_configs',
        verbose_name="យុទ្ធនាការ / Campaign (ទុកទទេសម្រាប់ទូទៅ)"
    )
    academic_year = models.ForeignKey(
        'academics.AcademicYear',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="ឆ្នាំសិក្សា / Academic Year"
    )
    form_template = models.CharField(
        max_length=30,
        choices=FormTemplate.choices,
        default=FormTemplate.GENERAL,
        verbose_name="បែបបទតម្រូវឱ្យសិស្សបំពេញ / Required Form Template",
        help_text="ជ្រើសរើសបែបបទដែលត្រូវឱ្យសិស្សកម្រិតថ្នាក់នេះបំពេញ"
    )
    custom_instructions = models.TextField(
        blank=True,
        null=True,
        verbose_name="សេចក្តីណែនាំបន្ថែមសម្រាប់កម្រិតនេះ / Grade Instructions"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="សកម្ម / Active"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['grade_level__order', 'grade_level__grade_number']
        verbose_name = "ការកំណត់បែបបទតាមកម្រិតថ្នាក់ / Grade Form Configuration"
        verbose_name_plural = "ការកំណត់បែបបទតាមកម្រិតថ្នាក់ទាំងអស់ / Grade Form Configurations"

    @classmethod
    def get_template_for_grade(cls, grade_level, academic_year=None, campaign=None):
        """
        Resolves the configured form template for a given grade level.
        Fallback to GENERAL or SchoolProfile registration_mode.
        """
        if not grade_level:
            return cls.FormTemplate.GENERAL

        # 1. Look for campaign specific config
        if campaign:
            cfg = cls.objects.filter(grade_level=grade_level, campaign=campaign, is_active=True).first()
            if cfg:
                return cfg.form_template

        # 2. Look for academic year specific config
        if academic_year:
            cfg = cls.objects.filter(grade_level=grade_level, academic_year=academic_year, campaign__isnull=True, is_active=True).first()
            if cfg:
                return cfg.form_template

        # 3. Look for general grade config
        cfg = cls.objects.filter(grade_level=grade_level, campaign__isnull=True, is_active=True).first()
        if cfg:
            return cfg.form_template

        return cls.FormTemplate.GENERAL

    def __str__(self):
        camp_str = f" [{self.campaign.title}]" if self.campaign else ""
        return f"{self.grade_level.name} ➡️ {self.get_form_template_display()}{camp_str}"


class StudentVerificationLog(models.Model):
    """
    Audit Trail & Confirmation Log for Student Information Entry & Verification.
    Tracks edits by Student, Parent/Guardian, or Teacher, especially when existing student data is confirmed.
    """
    class ConfirmerRole(models.TextChoices):
        STUDENT = 'STUDENT', 'សិស្ស (Student)'
        PARENT = 'PARENT', 'អាណាព្យាបាល / មាតាបិតា (Parent/Guardian)'
        TEACHER = 'TEACHER', 'គ្រូបង្រៀន / គ្រូបន្ទុកថ្នាក់ (Teacher)'
        ADMIN = 'ADMIN', 'រដ្ឋបាលសាលា (School Admin)'

    class Channel(models.TextChoices):
        PORTAL = 'PORTAL', 'គេហទំព័រ / Web Portal'
        MOBILE_APP = 'MOBILE_APP', 'កម្មវិធីទូរស័ព្ទ / Mobile App'

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='verification_logs',
        verbose_name="សិស្ស / Student"
    )
    campaign = models.ForeignKey(
        StudentVerificationCampaign,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verification_logs',
        verbose_name="យុទ្ធនាការ / Verification Campaign"
    )
    academic_year = models.ForeignKey(
        'academics.AcademicYear',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="ឆ្នាំសិក្សា / Academic Year"
    )
    confirmed_by_role = models.CharField(
        max_length=20,
        choices=ConfirmerRole.choices,
        default=ConfirmerRole.STUDENT,
        verbose_name="អ្នកបញ្ជាក់ / Confirmed By Role",
        help_text="តួនាទីអ្នកដែលបានបញ្ជាក់ការកែប្រែទិន្នន័យ (សិស្ស, អាណាព្យាបាល, ឬ គ្រូ)"
    )
    confirmed_by_name = models.CharField(
        max_length=150,
        verbose_name="ឈ្មោះអ្នកបញ្ជាក់ / Confirmer Name"
    )
    confirmed_by_phone = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        verbose_name="លេខទូរស័ព្ទអ្នកបញ្ជាក់ / Confirmer Phone"
    )
    relationship_to_student = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="ទំនាក់ទំនង / មុខងារ (Relationship / Role)",
        help_text="ឧ. ខ្លួនឯង (សិស្ស), ឪពុក, ម្តាយ, អាណាព្យាបាល, គ្រូបន្ទុកថ្នាក់"
    )
    is_existing_student = models.BooleanField(
        default=True,
        verbose_name="ជាសិស្សមានទិន្នន័យស្រាប់ / Is Existing Student"
    )
    confirmation_notes = models.TextField(
        blank=True,
        null=True,
        verbose_name="កំណត់សម្គាល់ការកែប្រែ / Confirmation Notes / Reason"
    )
    channel = models.CharField(
        max_length=20,
        choices=Channel.choices,
        default=Channel.PORTAL,
        verbose_name="មធ្យោបាយបញ្ចូល / Channel (Portal / Mobile App)"
    )
    changes_diff = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="សង្ខេបទិន្នន័យកែប្រែ / Changes Diff (JSON)"
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="អាសយដ្ឋាន IP / IP Address"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='student_verification_confirmations',
        verbose_name="គណនីអ្នកបញ្ចូល / Logged-in User"
    )
    verified_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="កាលបរិច្ឆេទ & ម៉ោង / Verified At"
    )

    class Meta:
        ordering = ['-verified_at', '-id']
        verbose_name = "កំណត់ត្រាបញ្ជាក់ព័ត៌មានសិស្ស / Student Verification Log"
        verbose_name_plural = "កំណត់ត្រាបញ្ជាក់ព័ត៌មានសិស្សទាំងអស់ / Student Verification Logs"

    def __str__(self):
        return f"បញ្ជាក់សិស្ស {self.student.khmer_name} ដោយ {self.get_confirmed_by_role_display()} ({self.confirmed_by_name}) - {self.verified_at.strftime('%d/%m/%Y %H:%M')}"


