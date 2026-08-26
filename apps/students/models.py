from django.db import models
from django.conf import settings
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

    class Meta:
        ordering = ['order', 'id']
        verbose_name = "ប្រភេទកម្រៃ & អាហារូបករណ៍ / Scholarship & Fee Type"
        verbose_name_plural = "ប្រភេទកម្រៃ & អាហារូបករណ៍ទាំងអស់ / Scholarship & Fee Types"

    def save(self, *args, **kwargs):
        if not self.code:
            import re
            cleaned = re.sub(r'[^a-zA-Z0-9]', '_', self.name.strip().upper())
            self.code = cleaned[:30] or f"SCH_{ScholarshipType.objects.count() + 1}"
        super().save(*args, **kwargs)

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

    class Meta:
        ordering = ['order', 'id']
        verbose_name = "ការកំណត់ស្ថានភាពសិក្សា / Student Status Config"
        verbose_name_plural = "ការកំណត់ស្ថានភាពសិក្សាទាំងអស់ / Student Status Configs"

    def save(self, *args, **kwargs):
        if not self.code:
            import re
            cleaned = re.sub(r'[^a-zA-Z0-9]', '_', self.name.strip().upper())
            self.code = cleaned[:30] or f"STATUS_{StudentStatusConfig.objects.count() + 1}"
        super().save(*args, **kwargs)

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
        for item in defaults:
            cls.objects.get_or_create(code=item['code'], defaults=item)


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
    photo = models.ImageField(upload_to='students/photos/', blank=True, null=True, verbose_name="រូបថតសិស្ស (៤x៦) / Student Photo")
    birth_certificate = models.FileField(upload_to='students/docs/', blank=True, null=True, verbose_name="សំបុត្រកំណើត / Birth Certificate")
    
    # Academic association
    classroom = models.ForeignKey('academics.Classroom', on_delete=models.SET_NULL, null=True, blank=True, related_name='students', verbose_name="ថ្នាក់រៀន / Classroom")
    academic_year = models.ForeignKey('academics.AcademicYear', on_delete=models.SET_NULL, null=True, blank=True, related_name='enrolled_students', verbose_name="ឆ្នាំសិក្សា / Academic Year")
    enrollment_date = models.DateField(auto_now_add=True, verbose_name="ថ្ងៃចុះឈ្មោះ / Enrollment Date")
    fee_start_month = models.PositiveSmallIntegerField(blank=True, null=True, choices=MONTH_CHOICES, verbose_name="ខែចាប់ផ្តើមបង់ប្រាក់ / Fee Start Month", help_text="ខែដែលសិស្សត្រូវចាប់ផ្តើមបង់ប្រាក់ (ទុកទទេដើម្បីគិតចាប់ពីដើមឆ្នាំសិក្សា)")
    fee_end_month = models.PositiveSmallIntegerField(blank=True, null=True, choices=MONTH_CHOICES, verbose_name="ខែបញ្ចប់/ផ្អាកការបង់ប្រាក់ / Fee End Month", help_text="ខែចុងក្រោយដែលសិស្សត្រូវបង់ប្រាក់ (សម្រាប់សិស្សឈប់រៀន ឬផ្អាកការសិក្សា ទុកទទេដើម្បីបង់ដល់ចប់ឆ្នាំ)")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, verbose_name="ស្ថានភាព / Status")
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
        st = ScholarshipType.objects.filter(code=self.scholarship_type).first()
        if st:
            return st.name
        try:
            return dict(Student.ScholarshipType.choices).get(self.scholarship_type, self.scholarship_type)
        except Exception:
            return self.scholarship_type

    @property
    def scholarship_discount_percentage(self):
        """Returns discount percentage as a decimal/float"""
        st = ScholarshipType.objects.filter(code=self.scholarship_type).first()
        if st:
            return float(st.discount_percentage)
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
            return StudentStatusConfig.objects.filter(code=self.status).first()
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

    def save(self, *args, **kwargs):
        if not self.student_id:
            import re
            year_prefix = f"{datetime.now().year % 100:02d}"
            if self.academic_year:
                if self.academic_year.start_date:
                    year_prefix = f"{self.academic_year.start_date.year % 100:02d}"
                elif self.academic_year.name:
                    m = re.search(r'(\d{4})', self.academic_year.name)
                    if m:
                        year_prefix = f"{int(m.group(1)) % 100:02d}"

            candidates = Student.objects.filter(student_id__regex=rf'^{year_prefix}\d{{4}}$').values_list('student_id', flat=True)
            max_num = 0
            for sid in candidates:
                try:
                    num = int(sid[len(year_prefix):])
                    if num > max_num:
                        max_num = num
                except (ValueError, TypeError):
                    continue
            new_num = max_num + 1
            self.student_id = f"{year_prefix}{new_num:04d}"

        super().save(*args, **kwargs)

    def __str__(self):
        class_name = self.classroom.name if self.classroom else "គ្មានថ្នាក់"
        return f"{self.student_id} - {self.khmer_name} [{class_name}]"
