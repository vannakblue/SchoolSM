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


class GoogleSheetsConfig(models.Model):
    """
    Google Sheets & Google Drive Integration Settings for SchoolSM:
    - Syncs Students (with photos via Google Drive), Attendance, Incomes, Expenses
    - Organizes sheets per Academic Year
    - Admin-only restricted access
    - Backup & Restore support
    """
    is_active = models.BooleanField(default=False, verbose_name="បើកដំណើរការ Google Sheets Sync")
    admin_email = models.CharField(max_length=255, blank=True, null=True, verbose_name="Gmail Admin សម្រាប់ទទួលសិទ្ធិមើលឯកសារ (Admin Only)")
    service_account_json_path = models.CharField(max_length=500, blank=True, default="google_service_account.json", verbose_name="ទីតាំងឯកសារ JSON Credentials (Path)")
    service_account_json_content = models.TextField(blank=True, null=True, verbose_name="ឬបិទភ្ជាប់ខ្លឹមសារ JSON Credentials ដោយផ្ទាល់")
    drive_folder_name = models.CharField(max_length=200, default="SchoolSM_Cloud_Sync", verbose_name="ឈ្មោះ Folder លើ Google Drive")
    drive_folder_id = models.CharField(max_length=200, blank=True, null=True, verbose_name="Google Drive Folder ID")
    sync_students_with_photos = models.BooleanField(default=True, verbose_name="Upload រូបថតសិស្សទៅ Drive & បង្ហាញក្នុង Sheet (=IMAGE)")
    spreadsheets_registry = models.JSONField(default=dict, blank=True, verbose_name="បញ្ជីតំណភ្ជាប់ Google Sheets តាមឆ្នាំសិក្សា")
    last_sync_at = models.DateTimeField(null=True, blank=True, verbose_name="កាលបរិច្ឆេទ Sync ចុងក្រោយ")
    last_sync_status = models.CharField(max_length=50, blank=True, null=True, verbose_name="ស្ថានភាព Sync ចុងក្រោយ")
    last_sync_message = models.TextField(blank=True, null=True, verbose_name="កំណត់ត្រា Sync ចុងក្រោយ")

    class Meta:
        verbose_name = "ការកំណត់ Google Sheets / Google Sheets Config"
        verbose_name_plural = "ការកំណត់ Google Sheets / Google Sheets Configs"

    @classmethod
    def get_config(cls):
        config = cls.objects.first()
        if not config:
            config = cls.objects.create()
        return config

    def get_credentials_dict(self):
        """Returns the service account credentials as a Python dict, or None if not configured."""
        import json
        from pathlib import Path
        from django.conf import settings

        if self.service_account_json_content and self.service_account_json_content.strip():
            try:
                return json.loads(self.service_account_json_content.strip())
            except Exception:
                pass

        # Check environment variables (e.g. Render Environment Variables)
        import os
        for env_var in ['GOOGLE_SERVICE_ACCOUNT_JSON', 'GOOGLE_SHEETS_CREDENTIALS', 'GOOGLE_CREDENTIALS']:
            val = os.environ.get(env_var, '').strip()
            if val:
                try:
                    return json.loads(val)
                except Exception:
                    pass

        candidate_paths = [
            Path(self.service_account_json_path) if self.service_account_json_path else None,
            settings.BASE_DIR / 'google_service_account.json',
            settings.BASE_DIR / 'credentials.json',
            settings.BASE_DIR / 'service_account.json',
        ]
        for p in candidate_paths:
            if p and p.exists() and p.is_file():
                try:
                    with open(p, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception:
                    continue
        return None

    def is_configured(self):
        return bool(self.get_credentials_dict())

    @property
    def client_email(self):
        """Extracts client_email from the configured service account credentials."""
        d = self.get_credentials_dict()
        return d.get('client_email') if d else None

    def __str__(self):
        status = "Configured" if self.is_configured() else "Not Configured"
        return f"Google Sheets Config [{status}] - Admin: {self.admin_email or 'None'}"


class GeminiAiConfig(models.Model):
    """
    Google Gemini AI Agent & Key Rotation Configuration (Admin Configurable directly from Web Browser):
    - Multi-Key storage (comma or newline separated)
    - Primary Model selection
    - Thinking level selection
    - Rotation toggle & test logs
    """
    api_keys = models.TextField(
        blank=True,
        default="",
        verbose_name="បញ្ជី Gemini API Keys (១ Key ក្នុងមួយបន្ទាត់ ឬខណ្ឌដោយក្បៀស)",
        help_text="បញ្ចូល API Key មួយ ឬច្រើន (៣ ទៅ ៥ Keys សម្រាប់ Free Tier)។ ប្រព័ន្ធនឹងធ្វើ Auto Key Rotation ដោយស្វ័យប្រវត្តិ។"
    )
    model_name = models.CharField(
        max_length=100,
        default="gemini-3.5-flash",
        verbose_name="ម៉ូដែល Gemini AI ចម្បង (Primary Model)",
        help_text="ឧទាហរណ៍៖ gemini-3.5-flash, gemini-3.5-flash-lite, gemini-flash-latest"
    )
    thinking_level = models.CharField(
        max_length=20,
        choices=[('low', '⚡ Low (លឿនរហ័ស)'), ('medium', '⚖️ Medium (លំនឹងស្តង់ដារ)'), ('high', '🧠 High (ស៊ីជម្រៅបំផុត)')],
        default='medium',
        verbose_name="កម្រិតគិតពិចារណា (Thinking Level)"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="បើកដំណើរការ Generative AI ក្នុងប្រព័ន្ធ"
    )
    rotation_enabled = models.BooleanField(
        default=True,
        verbose_name="បើកដំណើរការ Multi-Key Rotation (ចែកវេនគ្នាស្មើៗ & Auto Failover)"
    )
    last_tested_at = models.DateTimeField(null=True, blank=True, verbose_name="កាលបរិច្ឆេទតេស្តចុងក្រោយ")
    last_test_status = models.CharField(max_length=50, blank=True, default="", verbose_name="ស្ថានភាពតេស្ត")
    last_test_message = models.TextField(blank=True, default="", verbose_name="លទ្ធផលតេស្ត")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "ការកំណត់ Gemini AI / Gemini AI Config"
        verbose_name_plural = "ការកំណត់ Gemini AI / Gemini AI Configs"

    @classmethod
    def get_config(cls):
        config = cls.objects.first()
        if not config:
            from django.conf import settings
            import os
            initial_keys = (
                getattr(settings, 'GEMINI_API_KEYS', '')
                or getattr(settings, 'GEMINI_API_KEY', '')
                or os.environ.get('GEMINI_API_KEYS', '')
                or os.environ.get('GEMINI_API_KEY', '')
            )
            initial_model = getattr(settings, 'GEMINI_MODEL', '') or os.environ.get('GEMINI_MODEL', 'gemini-3.8-flash')
            initial_level = getattr(settings, 'GEMINI_THINKING_LEVEL', '') or os.environ.get('GEMINI_THINKING_LEVEL', 'medium')
            config = cls.objects.create(
                api_keys=initial_keys or '',
                model_name=initial_model,
                thinking_level=initial_level
            )
        return config

    def get_keys_list(self):
        """Returns clean list of unique API keys from stored text."""
        keys = []
        if self.api_keys:
            raw = self.api_keys.replace('\r', '\n').replace(',', '\n').replace(';', '\n')
            for line in raw.split('\n'):
                line = line.strip()
                if line and line not in keys:
                    keys.append(line)
        return keys

    def __str__(self):
        k_count = len(self.get_keys_list())
        return f"Gemini AI Config ({'Active' if self.is_active else 'Disabled'}) - {k_count} Keys"


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

DEFAULT_REGISTRATION_FIELDS_CONFIG = {
    # ------------------ GENERAL FORM (បែបបទ Admin កំណត់) ------------------
    'general': {
        'sections': {
            'student_info': True,     # ផ្នែកទី១. ព័ត៌មានផ្ទាល់ខ្លួនសិស្ស
            'parent_info': True,      # ផ្នែកទី២. ព័ត៌មានអាណាព្យាបាល
            'academic_fee': True,     # ផ្នែកទី៣. ការសិក្សា & កម្រៃ
            'documents': True,        # ផ្នែកទី៤. ឯកសារ & រូបថត
            'grade_specific': True,   # ផ្នែកទី៥. ព័ត៌មានបន្ថែមតាមកម្រិតថ្នាក់
        },
        'fields': {
            # Section 1: ព័ត៌មានផ្ទាល់ខ្លួនសិស្ស
            'student_id': True,
            'khmer_name': True,       # Always locked/required
            'latin_name': True,
            'gender': True,           # Always locked/required
            'date_of_birth': True,    # Always locked/required
            'phone': True,
            'previous_school': True,
            'place_of_birth': True,
            'current_address': True,
            # Section 2: ព័ត៌មានអាណាព្យាបាល
            'father_name': True,
            'father_phone': True,
            'father_job': True,
            'mother_name': True,
            'mother_phone': True,
            'mother_job': True,
            'guardian_name': True,
            'emergency_phone': True,
            # Section 3: ការសិក្សា & កម្រៃ
            'academic_year': True,
            'classroom': True,
            'scholarship_type': True,
            'fee_start_month': True,
            'telegram_chat_id': True,
            # Section 4: ឯកសារ & រូបថត
            'photo': True,
            'birth_certificate': True,
        }
    },
    # ------------------ MOEYS FORM (បែបបទសម្រង់ព័ត៌មាន ៣៥ ជួរឈរ) ------------------
    'moeys': {
        'sections': {
            'identity': True,         # ផ្នែកទី១. អត្តសញ្ញាណសិស្ស
            'pob_address': True,      # ផ្នែកទី២. ទីកន្លែងកំណើត & អាសយដ្ឋាន
            'parents': True,          # ផ្នែកទី៣. ព័ត៌មានឪពុកម្តាយ & អាណាព្យាបាល
            'academic_origin': True,  # ផ្នែកទី៤. ស្ថានភាពសិក្សា & សាលាចាស់
            'vulnerability': True,    # ផ្នែកទី៥. ស្ថានភាពងាយរងគ្រោះ & ប័ណ្ណសមធម៌
            'fees': True,             # ផ្នែកទី៦. ការសិក្សា & កម្រៃ
        },
        'fields': {
            # Section 1
            'student_id': True,
            'surname': True,
            'given_name': True,
            'latin_name': True,
            'gender': True,
            'date_of_birth': True,
            # Section 2
            'pob': True,
            'current_address': True,
            # Section 3
            'father': True,
            'mother': True,
            'guardian': True,
            # Section 4
            'classroom': True,
            'previous_school': True,
            'repeater': True,
            'scholarship': True,
            # Section 5
            'equity_cards': True,
            'risk_card': True,
            'disability': True,
            # Section 6
            'academic_year': True,
            'fee_start_month': True,
            'telegram_chat_id': True,
        }
    }
}


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
    short_name_en = models.CharField(
        max_length=100,
        default="SchoolSM",
        blank=True,
        null=True,
        verbose_name="ឈ្មោះកាត់សាលា (English) / Short Name (English)"
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
    school_type_en = models.CharField(
        max_length=100,
        default="General High School",
        blank=True,
        null=True,
        verbose_name="កម្រិត/ប្រភេទសាលា (English) / School Level & Type (English)"
    )
    motto = models.CharField(
        max_length=255,
        default="ចំណេះដឹង វិន័យ សីលធម៌ គុណធម៌",
        blank=True,
        verbose_name="បាវចនាសាលា / School Motto"
    )
    motto_en = models.CharField(
        max_length=255,
        default="Knowledge, Discipline, Morality, Virtue",
        blank=True,
        null=True,
        verbose_name="បាវចនាសាលា (English) / School Motto (English)"
    )
    about_school = models.TextField(
        blank=True,
        null=True,
        verbose_name="អំពីសាលារៀន (Khmer) / About School (Khmer)"
    )
    about_school_en = models.TextField(
        blank=True,
        null=True,
        verbose_name="អំពីសាលារៀន (English) / About School (English)"
    )
    principal_name_en = models.CharField(
        max_length=150,
        default="Dr. Sok Chanthorn",
        blank=True,
        null=True,
        verbose_name="ឈ្មោះនាយក/នាយិកា (English) / Principal Name (English)"
    )
    street_address_en = models.CharField(
        max_length=255,
        default="Preah Norodom Blvd, Sangkat Wat Phnom",
        blank=True,
        null=True,
        verbose_name="អាសយដ្ឋាន (English) / Street Address (English)"
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

    # Theme, Colors & Typography Customization
    class DisplayFont(models.TextChoices):
        KANTUMRUY = 'Kantumruy Pro', 'Kantumruy Pro (លំនាំដើម - ទំនើប ទាន់សម័យ)'
        SIEMREAP = 'Khmer OS Siemreap', 'Khmer OS Siemreap (ស្តង់ដាររដ្ឋបាល MoEYS)'
        BATTAMBANG = 'Khmer OS Battambang', 'Khmer OS Battambang (ងាយអាន អក្សរមូលច្បាស់)'
        HANUMAN = 'Hanuman', 'Hanuman (ក្បូរក្បាច់ ស្រទន់ បុរាណ)'
        KOH_SANTEPHEAP = 'Koh Santepheap', 'Koh Santepheap (ទាន់សម័យ ជ្រុងស្អាត)'
        NOTO_SANS = 'Noto Sans Khmer', 'Noto Sans Khmer (Google Standard)'
        NOKORA = 'Nokora', 'Nokora (ស្រាល ស្រស់ស្អាត)'

    class ReportHeaderFont(models.TextChoices):
        MOUL = 'Moul', 'Moul / Khmer OS Muol Light (ក្បាលលិខិត & របាយការណ៍ MoEYS)'
        KANTUMRUY_BOLD = 'Kantumruy Pro', 'Kantumruy Pro Bold (ទំនើប)'
        BATTAMBANG_BOLD = 'Khmer OS Battambang', 'Khmer OS Battambang Bold'
        SIEMREAP_BOLD = 'Khmer OS Siemreap', 'Khmer OS Siemreap Bold'

    display_font = models.CharField(
        max_length=100,
        choices=DisplayFont.choices,
        default=DisplayFont.KANTUMRUY,
        verbose_name="ពុម្ពអក្សរទូទៅក្នុងប្រព័ន្ធ (Display Font)"
    )
    report_header_font = models.CharField(
        max_length=100,
        choices=ReportHeaderFont.choices,
        default=ReportHeaderFont.MOUL,
        verbose_name="ពុម្ពអក្សរចំណងជើង & របាយការណ៍ (Report Header Font)"
    )
    theme_primary_color = models.CharField(
        max_length=20,
        default="#1e40af",
        verbose_name="ពណ៌ចម្បង (Primary Brand Color)"
    )
    header_bg_color = models.CharField(
        max_length=20,
        default="#0f172a",
        verbose_name="ពណ៌ក្បាលទំព័រ Header (Header Background)"
    )
    footer_bg_color = models.CharField(
        max_length=20,
        default="#0b1329",
        verbose_name="ពណ៌បាតទំព័រ Footer (Footer Background)"
    )
    body_bg_color = models.CharField(
        max_length=20,
        default="#f8fafc",
        verbose_name="ពណ៌ផ្ទៃទំព័រ (Page Background)"
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

    # Student Registration Mode Configuration (Admin Enforced Control)
    class RegistrationMode(models.TextChoices):
        ADMIN_CUSTOM = 'ADMIN_CUSTOM', 'ចុះឈ្មោះតាមដែល Admin បានកំណត់ (ទូទៅ / Standard)'
        MOEYS_INDIVIDUAL = 'MOEYS_INDIVIDUAL', 'ចុះឈ្មោះតាមសម្រង់ព័ត៌មានសិស្សម្នាក់ៗ (MoEYS Census 35 Columns)'
        BOTH = 'BOTH', 'តាមការកំណត់របស់ Admin តាមកម្រិតថ្នាក់ (Admin Grade-Level Config)'

    registration_mode = models.CharField(
        max_length=30,
        choices=RegistrationMode.choices,
        default=RegistrationMode.ADMIN_CUSTOM,
        verbose_name="វិធីសាស្ត្រចុះឈ្មោះសិស្ស / Student Registration Mode",
        help_text="កំណត់វិធីចុះឈ្មោះសិស្ស៖ តាមទម្រង់ Admin កំណត់ ឬ តាមសម្រង់ព័ត៌មានសិស្សម្នាក់ៗ ឬ តាមកម្រិតថ្នាក់ (សិស្សមិនអាចជ្រើសរើសនៅលើ Portal ឬ Mobile បានទេ គឺ Admin ជាអ្នកកំណត់)"
    )

    # Customizable Registration Form Sections & Fields Configuration (Ticking Admin Control)
    registration_form_config = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="ការកំណត់ផ្នែក & ប្រអប់ចុះឈ្មោះ / Registration Sections & Fields Config",
        help_text="រក្សាទុកការកំណត់ Ticking លើផ្នែកធំៗ និងចំណុចតូចៗនីមួយៗនៃបែបបទចុះឈ្មោះ"
    )

    # Student Registration Allowance & Period Configuration (Admin Control for Portal & Mobile App)
    is_registration_open = models.BooleanField(
        default=True,
        verbose_name="បើកដំណើរការចុះឈ្មោះសិស្ស / Enable Student Registration",
        help_text="អនុញ្ញាត ឬ ផ្អាក ការចុះឈ្មោះសិស្សថ្មីទាំងនៅលើ Portal និង Mobile App"
    )
    registration_start_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="កាលបរិច្ឆេទចាប់ផ្តើមចុះឈ្មោះ / Registration Start Date & Time",
        help_text="ពេលវេលាចាប់ផ្តើមអនុញ្ញាតឱ្យសិស្សចុះឈ្មោះ (ទុកទទេ ប្រសិនបើបើកភ្លាមៗ)"
    )
    registration_end_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="កាលបរិច្ឆេទផុតកំណត់ចុះឈ្មោះ / Registration End Date & Time",
        help_text="ពេលវេលាបញ្ចប់/ផុតកំណត់ការចុះឈ្មោះ (ទុកទទេ ប្រសិនបើគ្មានកំណត់)"
    )
    registration_closed_message = models.CharField(
        max_length=500,
        blank=True,
        default="ការចុះឈ្មោះសិស្សថ្មីត្រូវបានបិទជាបណ្តោះអាសន្ន ឬផុតកំណត់កាលបរិច្ឆេទកំណត់ដោយរដ្ឋបាលសាលា។ សូមទាក់ទងរដ្ឋបាលសាលាសម្រាប់ព័ត៌មានបន្ថែម។",
        verbose_name="សារជូនដំណឹងពេលបិទការចុះឈ្មោះ / Closed Notice Message"
    )

    def is_student_registration_allowed(self):
        """
        Determines whether student registration is currently permitted by Admin.
        Used by both Web Portal and Mobile App.
        Returns: (allowed: bool, reason: str, status_code: str)
        status_code: 'OPEN', 'CLOSED_MANUAL', 'NOT_STARTED', 'EXPIRED'
        """
        from django.utils import timezone
        if not self.is_registration_open:
            msg = self.registration_closed_message or "ការចុះឈ្មោះសិស្សថ្មីត្រូវបានបិទដោយរដ្ឋបាលសាលា។"
            return False, msg, "CLOSED_MANUAL"

        now = timezone.now()
        if self.registration_start_date and now < self.registration_start_date:
            from django.utils.timezone import localtime
            local_start = localtime(self.registration_start_date)
            start_str = local_start.strftime('%d/%m/%Y វេលាម៉ោង %H:%M')
            msg = f"ការចុះឈ្មោះសិស្សថ្មីមិនទាន់បើកដំណើរការនៅឡើយទេ។ នឹងចាប់ផ្តើមទទួលពាក្យនៅថ្ងៃទី {start_str}។"
            return False, msg, "NOT_STARTED"

        if self.registration_end_date and now > self.registration_end_date:
            from django.utils.timezone import localtime
            local_end = localtime(self.registration_end_date)
            end_str = local_end.strftime('%d/%m/%Y វេលាម៉ោង %H:%M')
            msg = f"ការចុះឈ្មោះសិស្សថ្មីបានផុតកំណត់កាលបរិច្ឆេទទទួលពាក្យហើយ (ផុតកំណត់កាលពីថ្ងៃទី {end_str})។"
            return False, msg, "EXPIRED"

        return True, "ការចុះឈ្មោះកំពុងបើកដំណើរការជាធម្មតា។", "OPEN"

    def get_registration_fields_config(self):
        """
        Returns the merged registration form sections and fields configuration.
        Ensures defaults exist for any missing keys.
        """
        import copy
        config = copy.deepcopy(DEFAULT_REGISTRATION_FIELDS_CONFIG)
        if isinstance(self.registration_form_config, dict) and self.registration_form_config:
            for form_key in ['general', 'moeys']:
                saved_form = self.registration_form_config.get(form_key, {})
                if isinstance(saved_form, dict):
                    saved_sec = saved_form.get('sections', {})
                    if isinstance(saved_sec, dict):
                        for s_key, s_val in saved_sec.items():
                            if s_key in config[form_key]['sections']:
                                config[form_key]['sections'][s_key] = bool(s_val)
                    saved_fld = saved_form.get('fields', {})
                    if isinstance(saved_fld, dict):
                        for f_key, f_val in saved_fld.items():
                            if f_key in config[form_key]['fields']:
                                config[form_key]['fields'][f_key] = bool(f_val)
        # Always enforce basic essentials to prevent invalid states
        config['general']['sections']['student_info'] = True
        config['general']['fields']['khmer_name'] = True
        config['general']['fields']['gender'] = True
        config['general']['fields']['date_of_birth'] = True

        config['moeys']['sections']['identity'] = True
        config['moeys']['fields']['surname'] = True
        config['moeys']['fields']['given_name'] = True
        config['moeys']['fields']['gender'] = True
        config['moeys']['fields']['date_of_birth'] = True
        return config

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
        # If logo is unset, auto-link to default committed school photo if available
        if not profile.logo:
            from pathlib import Path
            from django.conf import settings
            default_media = Path(settings.MEDIA_ROOT) / 'school' / 'photo_2021-02-28_21-07-22_-_Copy.jpg'
            if default_media.exists():
                profile.logo = 'school/photo_2021-02-28_21-07-22_-_Copy.jpg'
                profile.save(update_fields=['logo'])
        return profile

    @property
    def logo_url(self):
        if self.logo and hasattr(self.logo, 'name') and self.logo.name:
            try:
                if hasattr(self.logo, 'storage') and self.logo.storage.exists(self.logo.name):
                    return self.logo.url
            except Exception:
                try:
                    return self.logo.url
                except Exception:
                    pass
        # Permanent fallback to static logo tracked in Git (guaranteed never to be wiped on deploy)
        from django.templatetags.static import static
        return static('img/school_logo.png')

    @property
    def unlocalized_latitude(self):
        if self.latitude is not None:
            return f"{float(self.latitude):.6f}".rstrip('0').rstrip('.')
        return "11.5564"

    @property
    def unlocalized_longitude(self):
        if self.longitude is not None:
            return f"{float(self.longitude):.6f}".rstrip('0').rstrip('.')
        return "104.9282"

    @property
    def google_maps_direct_url(self):
        if self.google_maps_url and self.google_maps_url.startswith('http') and 'schoolsm_sample' not in self.google_maps_url:
            return self.google_maps_url
        if self.latitude is not None and self.longitude is not None:
            return f"https://www.google.com/maps?q={self.unlocalized_latitude},{self.unlocalized_longitude}"
        return "https://www.google.com/maps?q=11.5564,104.9282"

    @property
    def google_maps_embed_url(self):
        """
        Clean, unlocalized Google Maps embed URL for iframes.
        Ensures dots are always used for decimal separation, avoiding L10N comma replacement.
        """
        import re, urllib.parse

        # 1. If admin provided an iframe snippet or embed URL
        if self.google_maps_url:
            url_clean = self.google_maps_url.strip()
            iframe_match = re.search(r'src=["\']([^"\']+)["\']', url_clean)
            if iframe_match:
                return iframe_match.group(1)
            if 'output=embed' in url_clean or 'google.com/maps/embed' in url_clean:
                return url_clean

        # 2. If latitude and longitude exist, use dot decimal coordinates
        if self.latitude is not None and self.longitude is not None:
            lat = self.unlocalized_latitude
            lng = self.unlocalized_longitude
            return f"https://maps.google.com/maps?q={lat},{lng}&hl=km&z=16&output=embed"

        # 3. Fallback to school name
        if self.name_kh:
            q = urllib.parse.quote(f"{self.name_kh} {self.province or ''}".strip())
            return f"https://maps.google.com/maps?q={q}&hl=km&z=15&output=embed"

        return "https://maps.google.com/maps?q=11.5564,104.9282&hl=km&z=16&output=embed"

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
    def seal_url(self):
        if self.seal and hasattr(self.seal, 'url'):
            return self.seal.url
        return None

    @property
    def display_font_css(self):
        font = self.display_font or 'Kantumruy Pro'
        if font == 'Khmer OS Siemreap':
            return "'Khmer OS Siemreap', 'Siemreap', 'Kantumruy Pro', sans-serif"
        elif font == 'Khmer OS Battambang':
            return "'Khmer OS Battambang', 'Battambang', 'Kantumruy Pro', sans-serif"
        elif font == 'Hanuman':
            return "'Hanuman', 'Kantumruy Pro', sans-serif"
        elif font == 'Koh Santepheap':
            return "'Koh Santepheap', 'Kantumruy Pro', sans-serif"
        elif font == 'Noto Sans Khmer':
            return "'Noto Sans Khmer', 'Kantumruy Pro', sans-serif"
        elif font == 'Nokora':
            return "'Nokora', 'Kantumruy Pro', sans-serif"
        return "'Kantumruy Pro', 'Battambang', sans-serif"

    @property
    def report_font_css(self):
        font = self.report_header_font or 'Moul'
        if font == 'Moul':
            return "'Khmer OS Muol Light', 'KhmerOSmuollight', 'Moul', 'Khmer OS Muol', 'Kantumruy Pro', sans-serif"
        elif font == 'Khmer OS Siemreap':
            return "'Khmer OS Siemreap', 'Siemreap', sans-serif"
        elif font == 'Khmer OS Battambang':
            return "'Khmer OS Battambang', 'Battambang', sans-serif"
        return "'Kantumruy Pro', 'Battambang', sans-serif"

    @property
    def district_en(self):
        from apps.tools.ai_translation_service import OFFLINE_DICTIONARY
        if not self.district:
            return "Kandal Stueng"
        return OFFLINE_DICTIONARY.get(self.district, "Kandal Stueng")

    @property
    def province_en(self):
        from apps.tools.ai_translation_service import OFFLINE_DICTIONARY
        if not self.province:
            return "Kandal Province"
        return OFFLINE_DICTIONARY.get(self.province, "Kandal Province")

    def get_name(self, lang='km'):
        import re
        if lang == 'en':
            if self.name_en and not re.search(r'[\u1780-\u17FF]', self.name_en):
                return self.name_en
            return "Hun Sen Kampong Kantuot High School"
        return self.name_kh

    def get_short_name(self, lang='km'):
        import re
        if lang == 'en':
            if self.short_name_en and not re.search(r'[\u1780-\u17FF]', self.short_name_en):
                return self.short_name_en
            if self.name_en and not re.search(r'[\u1780-\u17FF]', self.name_en):
                return self.name_en
            return "Hun Sen Kampong Kantuot HS"
        return self.short_name or self.name_kh

    def get_motto(self, lang='km'):
        import re
        if lang == 'en':
            if self.motto_en and not re.search(r'[\u1780-\u17FF]', self.motto_en):
                return self.motto_en
            return "Knowledge, Discipline, Morality, Virtue"
        return self.motto

    def get_principal_name(self, lang='km'):
        import re
        if lang == 'en':
            if self.principal_name_en and not re.search(r'[\u1780-\u17FF]', self.principal_name_en):
                return self.principal_name_en
            return "Mr. Theng Rithya"
        return self.principal_name or "លោក ថេង រិទ្ធីយ៉ា"

    def get_street_address(self, lang='km'):
        import re
        if lang == 'en':
            if self.street_address_en and not re.search(r'[\u1780-\u17FF]', self.street_address_en):
                return self.street_address_en
            return "Street 105, Svay Ming Village, Barkou, Kandal Stueng, Kandal Province"
        return self.street_address or "ផ្លូវលេខ១០៥ ភូមិស្វាយមីង ឃុំបារគូ ស្រុកកណ្តាលស្ទឹង ខេត្តកណ្តាល"

    def get_school_type(self, lang='km'):
        import re
        if lang == 'en':
            if self.school_type_en and not re.search(r'[\u1780-\u17FF]', self.school_type_en):
                return self.school_type_en
            return "General High School"
        return self.school_type

    def get_about(self, lang='km'):
        import re
        if lang == 'en':
            if self.about_school_en and not re.search(r'[\u1780-\u17FF]', self.about_school_en):
                return self.about_school_en
            return "We educate students with comprehensive knowledge, technology skills, strong discipline, good morality, and a high sense of responsibility."
        return self.about_school

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

