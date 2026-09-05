from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'ADMIN', 'Super Admin / អ្នកគ្រប់គ្រងប្រព័ន្ធ'
        ACCOUNTANT = 'ACCOUNTANT', 'Accountant / គណនេយ្យករ'
        TEACHER = 'TEACHER', 'Teacher / គ្រូបង្រៀន'
        STUDENT = 'STUDENT', 'Student/Parent / សិស្ស-អាណាព្យាបាល'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.ADMIN,
        verbose_name="តួនាទី / Role"
    )
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="លេខទូរស័ព្ទ / Phone")
    khmer_name = models.CharField(max_length=150, blank=True, null=True, verbose_name="ឈ្មោះខ្មែរ / Khmer Name")
    latin_name = models.CharField(max_length=150, blank=True, null=True, verbose_name="ឈ្មោះឡាតាំង / Latin Name")
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True, verbose_name="រូបថត / Avatar")
    language_preference = models.CharField(
        max_length=10,
        choices=[('km', 'ភាសាខ្មែរ (Khmer)'), ('en', 'English')],
        default='km',
        verbose_name="ជម្រើសភាសា / Language Preference"
    )

    @property
    def display_name(self):
        if self.khmer_name and self.latin_name:
            return f"{self.khmer_name} ({self.latin_name})"
        elif self.khmer_name:
            return self.khmer_name
        elif self.latin_name:
            return self.latin_name
        return self.get_full_name() or self.username

    @property
    def is_superadmin(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    @property
    def is_accountant(self):
        return self.role == self.Role.ACCOUNTANT or self.is_superadmin

    @property
    def is_teacher(self):
        return self.role == self.Role.TEACHER

    @property
    def is_student(self):
        return self.role == self.Role.STUDENT

    def __str__(self):
        return f"{self.username} [{self.get_role_display()}]"


class TelegramConfig(models.Model):
    class Frequency(models.TextChoices):
        DAILY = 'DAILY', 'រៀងរាល់ថ្ងៃ (Daily)'
        WEEKLY = 'WEEKLY', 'រៀងរាល់សប្តាហ៍ (Weekly)'
        MONTHLY = 'MONTHLY', 'រៀងរាល់ខែ (Monthly)'

    bot_token = models.CharField(max_length=255, blank=True, null=True, verbose_name="Telegram Bot Token")
    chat_id = models.CharField(max_length=100, blank=True, null=True, verbose_name="Default Channel / Chat ID")
    is_active = models.BooleanField(default=True, verbose_name="បើកដំណើរការ / Is Active")
    notify_on_absence = models.BooleanField(default=True, verbose_name="ជូនដំណឹងអវត្តមាន / Absence Alert")
    notify_on_exam = models.BooleanField(default=True, verbose_name="ជូនដំណឹងពិន្ទុ / Exam Results Alert")
    notify_on_fee = models.BooleanField(default=True, verbose_name="ជូនដំណឹងបង់ប្រាក់ / Fee Due Alert")

    # Automated Database Backup Schedule (Admin Configurable directly from Web Browser)
    auto_backup_enabled = models.BooleanField(default=True, verbose_name="បើកដំណើរការ Auto Backup ស្វ័យប្រវត្តិតាមម៉ោង")
    backup_frequency = models.CharField(
        max_length=20,
        choices=Frequency.choices,
        default=Frequency.DAILY,
        verbose_name="ប្រេកង់ Backup"
    )
    backup_time = models.TimeField(default='00:00', verbose_name="ម៉ោងដែលត្រូវ Backup (Time of Day)")
    backup_day_of_week = models.PositiveSmallIntegerField(
        default=6,
        choices=[(0, 'ចន្ទ / Mon'), (1, 'អង្គារ / Tue'), (2, 'ពុធ / Wed'), (3, 'ព្រហស្បតិ៍ / Thu'), (4, 'សុក្រ / Fri'), (5, 'សៅរ៍ / Sat'), (6, 'អាទិត្យ / Sun')],
        verbose_name="ថ្ងៃក្នុងសប្តាហ៍សម្រាប់ Weekly Backup"
    )
    backup_format = models.CharField(
        max_length=20,
        choices=[('json', 'Full JSON Dump (.json)'), ('sqlite3', 'Live SQLite Snapshot (.sqlite3)')],
        default='json',
        verbose_name="ទម្រង់ឯកសារ Backup"
    )
    backup_chat_id = models.CharField(max_length=100, blank=True, null=True, verbose_name="Telegram Chat ID ជាក់លាក់សម្រាប់ Backup")
    last_backup_at = models.DateTimeField(null=True, blank=True, verbose_name="កាលបរិច្ឆេទ Backup ស្វ័យប្រវត្តិចុងក្រោយ")

    class Meta:
        verbose_name = "ការកំណត់ Telegram / Telegram Config"
        verbose_name_plural = "ការកំណត់ Telegram / Telegram Configs"

    @classmethod
    def get_config(cls):
        config = cls.objects.first()
        if not config:
            config = cls.objects.create()
        return config

    def __str__(self):
        return f"Telegram Bot Config ({'Active' if self.is_active else 'Disabled'}) - Auto-Backup: {'ON' if self.auto_backup_enabled else 'OFF'}"


class NotificationLog(models.Model):
    class Channel(models.TextChoices):
        TELEGRAM = 'TELEGRAM', 'Telegram Bot'
        SYSTEM = 'SYSTEM', 'System Alert'
        SMS = 'SMS', 'SMS Gateway'

    class Status(models.TextChoices):
        SENT = 'SENT', 'ផ្ញើរួច / Sent'
        SIMULATED = 'SIMULATED', 'គំរូសាកល្បង / Simulated'
        FAILED = 'FAILED', 'បរាជ័យ / Failed'

    title = models.CharField(max_length=255, verbose_name="ចំណងជើង / Title")
    message = models.TextField(verbose_name="ខ្លឹមសារសារ / Message")
    recipient_type = models.CharField(max_length=50, default="Parent", verbose_name="អ្នកទទួល / Recipient Type")
    recipient_name = models.CharField(max_length=150, verbose_name="ឈ្មោះអ្នកទទួល / Recipient Name")
    recipient_phone = models.CharField(max_length=30, blank=True, null=True, verbose_name="លេខទូរស័ព្ទ / Phone")
    channel = models.CharField(max_length=20, choices=Channel.choices, default=Channel.TELEGRAM)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SIMULATED)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="កាលបរិច្ឆេទ / Date")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "កំណត់ត្រាការជូនដំណឹង / Notification Log"
        verbose_name_plural = "កំណត់ត្រាការជូនដំណឹង / Notification Logs"

    def __str__(self):
        return f"[{self.channel}] {self.title} -> {self.recipient_name}"


class DirectChatMessage(models.Model):
    class Category(models.TextChoices):
        PROFILE_CORRECTION = 'profile_correction', 'ស្នើសុំកែប្រែព័ត៌មានអត្តសញ្ញាណ'
        GENERAL_INQUIRY = 'general_inquiry', 'សាកសួររដ្ឋបាល/ប្រាក់ខែ'
        TECHNICAL_HELP = 'technical_help', 'បញ្ហាបច្ចេកទេស'
        ADMIN_RESPONSE = 'admin_response', 'សារឆ្លើយតបពីរដ្ឋបាល'
        OTHER = 'other', 'សារទូទៅ'

    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_chat_messages', verbose_name="អ្នកផ្ញើ / Sender")
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='received_chat_messages', verbose_name="អ្នកទទួល / Recipient")
    message = models.TextField(verbose_name="ខ្លឹមសារសារ / Message Content", blank=True, default='')
    voice_file = models.FileField(upload_to='chat_voice/', blank=True, null=True, verbose_name="ឯកសារសំឡេង / Voice File")
    voice_duration = models.IntegerField(default=0, verbose_name="រយៈពេលសំឡេង (វិនាទី) / Duration (seconds)")
    category = models.CharField(max_length=50, choices=Category.choices, default=Category.PROFILE_CORRECTION, verbose_name="ប្រភេទសារ / Category")
    is_from_admin = models.BooleanField(default=False, verbose_name="ផ្ញើដោយ Admin / From Admin")
    is_read = models.BooleanField(default=False, verbose_name="បានអាន / Is Read")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="កាលបរិច្ឆេទ / Created At")

    class Meta:
        ordering = ['created_at']
        verbose_name = "សារជជែកផ្ទាល់ / Direct Chat Message"
        verbose_name_plural = "សារជជែកផ្ទាល់ / Direct Chat Messages"

    def __str__(self):
        return f"{self.sender.display_name} -> {self.recipient.display_name if self.recipient else 'Admin'}: {self.message[:30]}"


class SchoolProfile(models.Model):
    """
    Singleton School Profile model holding official school identity, logo, MoEYS administrative info,
    geographic location (village, commune, district, province), contact information, and principal details.
    """
    name_kh = models.CharField(
        max_length=200,
        default="វិទ្យាល័យអន្តរជាតិ សាលារៀន SM",
        verbose_name="ឈ្មោះសាលា (ខ្មែរ) / School Name (Khmer)"
    )
    name_en = models.CharField(
        max_length=200,
        default="SchoolSM International High School",
        verbose_name="ឈ្មោះសាលា (ឡាតាំង/អង់គ្លេស) / School Name (English)"
    )
    short_name = models.CharField(
        max_length=100,
        default="សាលារៀន SM",
        verbose_name="ឈ្មោះកាត់សាលា / Short Name"
    )
    school_code = models.CharField(
        max_length=50,
        default="080101",
        verbose_name="លេខកូដសាលា / EMIS School Code"
    )
    school_type = models.CharField(
        max_length=100,
        default="វិទ្យាល័យ / General High School",
        verbose_name="កម្រិត/ប្រភេទសាលា / School Level & Type"
    )
    motto = models.CharField(
        max_length=255,
        default="ចំណេះដឹង វិន័យ សីលធម៌ គុណធម៌",
        blank=True,
        verbose_name="បាវចនាសាលា / School Motto"
    )
    
    # Media: Logo, Seal, Signature
    logo = models.ImageField(
        upload_to='school/',
        blank=True,
        null=True,
        verbose_name="រូបសញ្ញាសាលា (Logo) / School Logo"
    )
    seal = models.ImageField(
        upload_to='school/',
        blank=True,
        null=True,
        verbose_name="ត្រាសាលាផ្លូវការ / Official Stamp & Seal"
    )
    principal_signature = models.ImageField(
        upload_to='school/',
        blank=True,
        null=True,
        verbose_name="ហត្ថលេខានាយកសាលា / Principal Signature"
    )

    class InstitutionType(models.TextChoices):
        PUBLIC = 'PUBLIC', 'សាលារដ្ឋ / Public School'
        PRIVATE = 'PRIVATE', 'សាលាឯកជន / Private School'
        INTERNATIONAL = 'INTERNATIONAL', 'សាលាអន្តរជាតិ / International School'
        NGO = 'NGO', 'អង្គការមិនមែនរដ្ឋាភិបាល / NGO School'

    institution_type = models.CharField(
        max_length=30,
        choices=InstitutionType.choices,
        default=InstitutionType.PUBLIC,
        blank=True,
        verbose_name="ប្រភេទគ្រឹះស្ថាន / Institution Type"
    )
    education_levels = models.CharField(
        max_length=255,
        default="មត្តេយ្យ, បឋមសិក្សា, អនុវិទ្យាល័យ, វិទ្យាល័យ",
        blank=True,
        verbose_name="កម្រិតសិក្សា / Education Levels"
    )
    date_format = models.CharField(
        max_length=50,
        default="dd-mm-yyyy",
        choices=[
            ('dd-mm-yyyy', 'dd-mm-yyyy (ឧ. 02-09-2026) - លំនាំដើម'),
            ('dd/mm/yyyy', 'dd/mm/yyyy (ឧ. 02/09/2026)'),
            ('yyyy-mm-dd', 'yyyy-mm-dd (ឧ. 2026-09-02)'),
            ('dd.mm.yyyy', 'dd.mm.yyyy (ឧ. 02.09.2026)'),
            ('dd-mm-yyyy HH:mm', 'dd-mm-yyyy HH:mm (ឧ. 02-09-2026 14:30)'),
            ('dd-mm-yyyy HH:mm:ss', 'dd-mm-yyyy HH:mm:ss (ឧ. 02-09-2026 14:30:45)'),
            ('dd/mm/yyyy HH:mm', 'dd/mm/yyyy HH:mm (ឧ. 02/09/2026 14:30)'),
            ('dd/mm/yyyy HH:mm:ss', 'dd/mm/yyyy HH:mm:ss (ឧ. 02/09/2026 14:30:45)'),
            ('yyyy-mm-dd HH:mm', 'yyyy-mm-dd HH:mm (ឧ. 2026-09-02 14:30)'),
            ('yyyy-mm-dd HH:mm:ss', 'yyyy-mm-dd HH:mm:ss (ឧ. 2026-09-02 14:30:45)'),
            ('dd.mm.yyyy HH:mm', 'dd.mm.yyyy HH:mm (ឧ. 02.09.2026 14:30)'),
            ('dd.mm.yyyy HH:mm:ss', 'dd.mm.yyyy HH:mm:ss (ឧ. 02.09.2026 14:30:45)'),
            ('dd-mm-yyyy hh:mm a', 'dd-mm-yyyy hh:mm A (ឧ. 02-09-2026 02:30 PM)'),
            ('dd-mm-yyyy hh:mm:ss a', 'dd-mm-yyyy hh:mm:ss A (ឧ. 02-09-2026 02:30:45 PM)'),
            ('dd/mm/yyyy hh:mm:ss a', 'dd/mm/yyyy hh:mm:ss A (ឧ. 02/09/2026 02:30:45 PM)'),
        ],
        blank=True,
        verbose_name="ទម្រង់កាលបរិច្ឆេទ / Date Format"
    )
    time_format = models.CharField(
        max_length=30,
        default="HH:mm",
        choices=[
            ('HH:mm', 'HH:mm (ឧ. 14:30 - 24 ម៉ោង គ្មានវិនាទី) - លំនាំដើម'),
            ('HH:mm:ss', 'HH:mm:ss (ឧ. 14:30:45 - 24 ម៉ោង មានវិនាទី)'),
            ('hh:mm a', 'hh:mm A (ឧ. 02:30 PM - 12 ម៉ោង គ្មានវិនាទី)'),
            ('hh:mm:ss a', 'hh:mm:ss A (ឧ. 02:30:45 PM - 12 ម៉ោង មានវិនាទី)'),
        ],
        blank=True,
        verbose_name="ទម្រង់ម៉ោង / Time Format"
    )

    # Student ID Configuration & Generation Pattern
    class StudentIdPattern(models.TextChoices):
        YEAR_END_4D = 'YEAR_END_4D', 'ឆ្នាំបញ្ចប់ + លេខ ៤ ខ្ទង់ (ឧ. 270001) - ស្តង់ដារជាតិ MoEYS'
        YEAR_END_5D = 'YEAR_END_5D', 'ឆ្នាំបញ្ចប់ + លេខ ៥ ខ្ទង់ (ឧ. 2700001)'
        PREFIX_YEAR_4D = 'PREFIX_YEAR_4D', 'Prefix + ឆ្នាំបញ្ចប់ + លេខ ៤ ខ្ទង់ (ឧ. STU-27-0001)'
        PREFIX_YEAR_5D = 'PREFIX_YEAR_5D', 'Prefix + ឆ្នាំបញ្ចប់ + លេខ ៥ ខ្ទង់ (ឧ. STU-27-00001)'
        GRADE_YEAR_4D = 'GRADE_YEAR_4D', 'កម្រិតថ្នាក់ + ឆ្នាំបញ្ចប់ + លេខ ៤ ខ្ទង់ (ឧ. 7-27-0001)'
        CUSTOM_PATTERN = 'CUSTOM_PATTERN', 'ទម្រង់ផ្ទាល់ខ្លួន (Custom Template) ឧ. {PREFIX}-{YEAR2}-{SEQ}'

    student_id_pattern = models.CharField(
        max_length=50,
        choices=StudentIdPattern.choices,
        default=StudentIdPattern.YEAR_END_4D,
        verbose_name="ទម្រង់អត្តលេខសិស្ស / Student ID Pattern"
    )
    student_id_prefix = models.CharField(
        max_length=20,
        default="STU",
        blank=True,
        verbose_name="អក្សរកាត់អត្តលេខ (Prefix)"
    )
    student_id_custom_template = models.CharField(
        max_length=100,
        default="{PREFIX}-{YEAR2}-{SEQ}",
        blank=True,
        verbose_name="រូបមន្តអត្តលេខផ្ទាល់ខ្លួន (Custom Template)"
    )
    student_id_digits = models.PositiveSmallIntegerField(
        default=4,
        choices=[
            (4, '៤ ខ្ទង់ (ឧ. 0001)'),
            (5, '៥ ខ្ទង់ (ឧ. 00001)'),
            (6, '៦ ខ្ទង់ (ឧ. 000001)'),
        ],
        verbose_name="ចំនួនខ្ទង់លេខរៀងរត់ / Sequence Digits"
    )
    student_id_include_grade = models.BooleanField(
        default=False,
        verbose_name="បញ្ចូលលេខកម្រិតថ្នាក់ក្នុងអត្តលេខ / Include Grade Level in ID"
    )

    # MoEYS Administrative & Hierarchy
    ministry_name = models.CharField(
        max_length=200,
        default="ក្រសួងអប់រំ យុវជន និងកីឡា",
        verbose_name="ក្រសួងសាមី / Ministry Name"
    )
    poe_name = models.CharField(
        max_length=200,
        default="មន្ទីរអប់រំ យុវជន និងកីឡា រាជធានីភ្នំពេញ",
        verbose_name="មន្ទីរអប់រំ / Provincial/Municipal Dept of Education (PoE)"
    )
    doe_name = models.CharField(
        max_length=200,
        default="ការិយាល័យអប់រំ យុវជន និងកីឡា ខណ្ឌដូនពេញ",
        blank=True,
        verbose_name="ការិយាល័យអប់រំ / District Office of Education (DoE)"
    )

    # Geographic Location & GPS / Google Maps
    province = models.CharField(
        max_length=100,
        default="រាជធានីភ្នំពេញ",
        verbose_name="រាជធានី/ខេត្ត / Province/City"
    )
    district = models.CharField(
        max_length=100,
        default="ខណ្ឌដូនពេញ",
        verbose_name="ក្រុង/ស្រុក/ខណ្ឌ / District/Khan"
    )
    commune = models.CharField(
        max_length=100,
        default="សង្កាត់វត្តភ្នំ",
        verbose_name="ឃុំ/សង្កាត់ / Commune/Sangkat"
    )
    village = models.CharField(
        max_length=100,
        default="ភូមិ១",
        blank=True,
        verbose_name="ភូមិ / Village"
    )
    street_address = models.CharField(
        max_length=255,
        default="មហាវិថីព្រះនរោត្តម សង្កាត់វត្តភ្នំ",
        blank=True,
        verbose_name="អាសយដ្ឋានលម្អិត / Street Address"
    )
    latitude = models.FloatField(
        default=11.5564,
        blank=True,
        null=True,
        verbose_name="រយៈទទឹង GPS (Latitude)"
    )
    longitude = models.FloatField(
        default=104.9282,
        blank=True,
        null=True,
        verbose_name="រយៈបណ្តោយ GPS (Longitude)"
    )
    google_maps_url = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Link ផែនទី Google Maps"
    )
    gps_radius_meters = models.PositiveIntegerField(
        default=100,
        blank=True,
        null=True,
        verbose_name="រង្វង់សុពលភាព GPS (Geofencing Radius - Meters)"
    )

    # Leadership & Contact
    principal_name = models.CharField(
        max_length=150,
        default="លោកបណ្ឌិត សុខ ចាន់ថន",
        verbose_name="ឈ្មោះនាយក/នាយិកាសាលា / Principal Name"
    )
    phone = models.CharField(
        max_length=100,
        default="023 888 999 / 012 345 678",
        verbose_name="លេខទូរស័ព្ទ / Phone Number"
    )
    email = models.EmailField(
        default="info@schoolsm.edu.kh",
        blank=True,
        verbose_name="អ៊ីមែល / Email Address"
    )
    website = models.CharField(
        max_length=200,
        default="https://schoolsm.edu.kh",
        blank=True,
        verbose_name="គេហទំព័រ / Website"
    )
    facebook_page = models.CharField(
        max_length=200,
        default="https://facebook.com/schoolsm",
        blank=True,
        verbose_name="ទំព័រហ្វេសប៊ុក / Facebook Page"
    )
    telegram_channel = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Telegram Channel / Group សាលា"
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="កែប្រែចុងក្រោយ / Updated At")

    class Meta:
        verbose_name = "ព័ត៌មានសាលារៀន / School Profile"
        verbose_name_plural = "ព័ត៌មានសាលារៀន / School Profile"

    @classmethod
    def get_settings(cls):
        profile = cls.objects.first()
        if not profile:
            profile = cls.objects.create()
        return profile

    @property
    def logo_url(self):
        if self.logo:
            try:
                return self.logo.url
            except Exception:
                return None
        return None

    @property
    def google_maps_direct_url(self):
        if self.google_maps_url and self.google_maps_url.startswith('http') and 'schoolsm_sample' not in self.google_maps_url:
            return self.google_maps_url
        if self.latitude and self.longitude:
            return f"https://www.google.com/maps?q={self.latitude},{self.longitude}"
        return "https://www.google.com/maps?q=11.5564,104.9282"

    @property
    def full_address(self):
        parts = []
        if self.street_address:
            parts.append(self.street_address)
        if self.village and self.village not in self.street_address:
            parts.append(f"{self.village}")
        if self.commune and self.commune not in self.street_address:
            parts.append(f"{self.commune}")
        if self.district and self.district not in self.street_address:
            parts.append(f"{self.district}")
        if self.province and self.province not in self.street_address:
            parts.append(f"{self.province}")
        return ", ".join(parts) if parts else (self.province or "កម្ពុជា")

    @property
    def logo_url(self):
        if self.logo and hasattr(self.logo, 'url'):
            return self.logo.url
        return None

    @property
    def seal_url(self):
        if self.seal and hasattr(self.seal, 'url'):
            return self.seal.url
        return None

    @property
    def signature_url(self):
        if self.principal_signature and hasattr(self.principal_signature, 'url'):
            return self.principal_signature.url
        return None

    def __str__(self):
        return f"{self.name_kh} ({self.school_code})"


class MenuSection(models.Model):
    """
    Dynamic Menu Section stored in database.
    Admin can Add, Edit, Reorder, or Disable any section.
    """
    code = models.CharField(max_length=100, unique=True, verbose_name="កូដផ្នែក / Section Code")
    name_kh = models.CharField(max_length=150, verbose_name="ឈ្មោះខ្មែរ / Name (Khmer)")
    name_en = models.CharField(max_length=150, verbose_name="ឈ្មោះឡាតាំង / Name (English)")
    icon = models.CharField(max_length=100, default='fa-solid fa-folder', verbose_name="រូបតំណាង / Icon Class")
    color = models.CharField(max_length=50, default='secondary', verbose_name="ពណ៌ / Color Class")
    order = models.PositiveIntegerField(default=0, verbose_name="លំដាប់លំដោយ / Sort Order")
    is_active = models.BooleanField(default=True, verbose_name="បើកដំណើរការ / Is Active")
    is_system = models.BooleanField(default=False, verbose_name="ប្រព័ន្ធដើម / Is System")
    default_roles = models.CharField(max_length=255, default='ADMIN,TEACHER,STUDENT,ACCOUNTANT', verbose_name="តួនាទីលំនាំដើម / Default Roles")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = "ផ្នែកម៉ឺនុយ / Menu Section"
        verbose_name_plural = "ផ្នែកម៉ឺនុយ / Menu Sections"

    def __str__(self):
        return f"{self.name_kh} ({self.code})"


class MenuItem(models.Model):
    """
    Dynamic Submenu Item stored in database.
    Admin can Add new custom submenus, Edit names/icons/URLs, and Delete items.
    """
    section = models.ForeignKey(MenuSection, on_delete=models.CASCADE, related_name='items', verbose_name="ផ្នែកម៉ឺនុយ / Section")
    code = models.CharField(max_length=100, unique=True, verbose_name="កូដម៉ឺនុយ / Submenu Code")
    name_kh = models.CharField(max_length=150, verbose_name="ឈ្មោះខ្មែរ / Name (Khmer)")
    name_en = models.CharField(max_length=150, verbose_name="ឈ្មោះឡាតាំង / Name (English)")
    icon = models.CharField(max_length=100, default='fa-solid fa-circle-dot', verbose_name="រូបតំណាង / Icon Class")
    url_name = models.CharField(max_length=100, blank=True, null=True, verbose_name="ឈ្មោះ URL (Django URL Name)")
    custom_url = models.CharField(max_length=255, blank=True, null=True, verbose_name="URL ផ្ទាល់ / Custom URL")
    order = models.PositiveIntegerField(default=0, verbose_name="លំដាប់លំដោយ / Sort Order")
    is_active = models.BooleanField(default=True, verbose_name="បើកដំណើរការ / Is Active")
    is_admin_only = models.BooleanField(default=False, verbose_name="សម្រាប់តែ Admin / Admin Only")
    is_system = models.BooleanField(default=False, verbose_name="ប្រព័ន្ធដើម / Is System")
    default_roles = models.CharField(max_length=255, default='ADMIN', verbose_name="តួនាទីលំនាំដើម / Default Roles")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = "ម៉ឺនុយរង / Menu Item"
        verbose_name_plural = "ម៉ឺនុយរង / Menu Items"

    def __str__(self):
        return f"{self.section.name_kh} -> {self.name_kh} ({self.code})"

    @property
    def get_url(self):
        if self.custom_url:
            return self.custom_url
        if self.url_name:
            from django.urls import reverse
            try:
                return reverse(self.url_name)
            except Exception:
                return f"/{self.url_name}/"
        return "#"


class RoleMenuPermission(models.Model):
    """
    Stores custom dynamic menu & submenu visibility and access permissions configured by Admin.
    """
    role = models.CharField(
        max_length=20,
        choices=User.Role.choices,
        verbose_name="តួនាទី / Role"
    )
    menu_key = models.CharField(
        max_length=100,
        verbose_name="កូដម៉ឺនុយ / Menu Key"
    )
    is_allowed = models.BooleanField(
        default=True,
        verbose_name="អនុញ្ញាត / Is Allowed"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "សិទ្ធិម៉ឺនុយតាមតួនាទី / Role Menu Permission"
        verbose_name_plural = "សិទ្ធិម៉ឺនុយតាមតួនាទី / Role Menu Permissions"
        unique_together = ('role', 'menu_key')
        indexes = [
            models.Index(fields=['role', 'menu_key']),
        ]

    def __str__(self):
        status = "Allowed" if self.is_allowed else "Denied"
        return f"{self.role} -> {self.menu_key} ({status})"

