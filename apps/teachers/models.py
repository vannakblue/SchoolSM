from django.db import models
from django.conf import settings
from decimal import Decimal

class Teacher(models.Model):
    class Gender(models.TextChoices):
        MALE = 'M', 'ប្រុស / Male'
        FEMALE = 'F', 'ស្រី / Female'

    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'កំពុងបង្រៀន (សកម្ម) / Active'
        ON_LEAVE = 'ON_LEAVE', 'សម្រាកច្បាប់ / On Leave'
        RETIRED = 'RETIRED', 'ចូលនិវត្តន៍ / Retired'
        TRANSFERRED = 'TRANSFERRED', 'ផ្ទេរចេញ / Transferred'
        RESIGNED = 'RESIGNED', 'លាឈប់ / Resigned'
        INACTIVE = 'INACTIVE', 'អសកម្ម / Inactive'

    teacher_id = models.CharField(max_length=50, unique=True, verbose_name="កូដសម្គាល់គ្រូ / Teacher ID")
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='teacher_profile')
    khmer_name = models.CharField(max_length=150, verbose_name="ឈ្មោះខ្មែរ / Khmer Name")
    latin_name = models.CharField(max_length=150, verbose_name="ឈ្មោះឡាតាំង / Latin Name")
    gender = models.CharField(max_length=5, choices=Gender.choices, default=Gender.MALE, verbose_name="ភេទ / Gender")
    date_of_birth = models.DateField(null=True, blank=True, verbose_name="ថ្ងៃខែឆ្នាំកំណើត / Date of Birth")
    phone = models.CharField(max_length=30, verbose_name="លេខទូរស័ព្ទ / Phone")
    email = models.EmailField(blank=True, null=True, verbose_name="អ៊ីមែល / Email")
    address = models.TextField(blank=True, null=True, verbose_name="អាសយដ្ឋានបច្ចុប្បន្ន / Current Address")
    qualification = models.CharField(max_length=200, blank=True, null=True, verbose_name="កម្រិតវប្បធម៌ / Qualification")
    specialization = models.CharField(max_length=200, verbose_name="ឯកទេសបង្រៀន / Specialization")
    training_level = models.CharField(max_length=200, blank=True, null=True, verbose_name="កម្រិតបណ្តុះបណ្តាល / Pedagogical Training Level")
    state_hire_date = models.DateField(null=True, blank=True, verbose_name="ថ្ងៃចូលបម្រើការងាររដ្ឋ / State Civil Service Entry Date")
    permanent_date = models.DateField(null=True, blank=True, verbose_name="ថ្ងៃខែឆ្នាំតែងតាំងស៊ប់ / Permanent Confirmation Date")
    primary_subject = models.CharField(max_length=150, blank=True, null=True, verbose_name="មុខវិជ្ជាឯកទេសទី១ / Subject Specialization 1")
    secondary_subject = models.CharField(max_length=150, blank=True, null=True, verbose_name="មុខវិជ្ជាឯកទេសទី២ / Subject Specialization 2")
    current_duty = models.CharField(max_length=150, blank=True, null=True, default="គ្រូបង្រៀន", verbose_name="ភារកិច្ចបច្ចុប្បន្ន / Current Duty")
    prakas_category = models.CharField(max_length=100, blank=True, null=True, verbose_name="ប្រភេទក្របខ័ណ្ឌ / Civil Servant Category")
    prakas_year = models.CharField(max_length=20, blank=True, null=True, verbose_name="ឆ្នាំទទួលប្រកាស / Decree Year")
    prakas_number = models.CharField(max_length=100, blank=True, null=True, verbose_name="ប្រកាសលេខ / Prakas Number")
    base_salary = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('500.00'), verbose_name="ប្រាក់ខែគោល ($) / Base Salary")
    hire_date = models.DateField(null=True, blank=True, verbose_name="កាលបរិច្ឆេទចូលបម្រើការ / Hire Date")
    photo = models.ImageField(upload_to='teachers/photos/', blank=True, null=True, verbose_name="រូបថត / Photo")
    resume = models.FileField(upload_to='teachers/docs/', blank=True, null=True, verbose_name="ឯកសារប្រវត្តិរូប / Resume/CV")
    max_weekly_hours = models.PositiveIntegerField(default=18, verbose_name="ម៉ោងបង្រៀនអតិបរមា/សប្តាហ៍ / Max Weekly Teaching Hours")
    is_fee_collector = models.BooleanField(default=False, verbose_name="អនុញ្ញាតឱ្យប្រមូលថវិកា / Fee Collector Permission")
    collector_token = models.CharField(max_length=64, blank=True, null=True, unique=True, verbose_name="Collector Pass Token")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, verbose_name="ស្ថានភាព / Status")
    last_profile_verified_at = models.DateTimeField(null=True, blank=True, verbose_name="កាលបរិច្ឆេទផ្ទៀងផ្ទាត់ព័ត៌មានចុងក្រោយ / Last Verified At")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['teacher_id']
        verbose_name = "គ្រូបង្រៀន / Teacher"
        verbose_name_plural = "គ្រូបង្រៀនទាំងអស់ / Teachers"

    @property
    def display_name(self):
        return f"{self.khmer_name} ({self.latin_name})"

    def get_or_create_collector_token(self):
        import uuid
        if not self.collector_token:
            self.collector_token = uuid.uuid4().hex
            self.save(update_fields=['collector_token'])
        return self.collector_token

    def __str__(self):
        return f"{self.teacher_id} - {self.khmer_name} ({self.specialization})"


class TeacherAttendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = 'PRESENT', 'វត្តមាន / Present'
        LATE = 'LATE', 'មកយឺត / Late'
        EXCUSED_LEAVE = 'EXCUSED_LEAVE', 'ច្បាប់អនុញ្ញាត / Excused Leave'
        UNEXCUSED_ABSENCE = 'UNEXCUSED_ABSENCE', 'អវត្តមានឥតច្បាប់ / Unexcused Absence'

    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField(verbose_name="កាលបរិច្ឆេទ / Date")
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.PRESENT, verbose_name="ស្ថានភាព / Status")
    check_in_time = models.TimeField(null=True, blank=True, verbose_name="ម៉ោង Check-In")
    check_out_time = models.TimeField(null=True, blank=True, verbose_name="ម៉ោង Check-Out")
    check_in_method = models.CharField(max_length=30, blank=True, null=True, verbose_name="វិធីសាស្ត្រ Check-in")
    is_late = models.BooleanField(default=False, verbose_name="មកយឺត / Late")
    late_minutes = models.PositiveIntegerField(default=0, verbose_name="នាទីដែលមកយឺត / Late Minutes")
    deduction_amount = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'), verbose_name="ចំនួនកាត់ប្រាក់ ($) / Deduction Amount")
    notes = models.TextField(blank=True, null=True, verbose_name="កំណត់ចំណាំ / Notes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', 'teacher']
        unique_together = ('teacher', 'date')
        verbose_name = "វត្តមានគ្រូបង្រៀន / Teacher Attendance"
        verbose_name_plural = "វត្តមានគ្រូបង្រៀន / Teacher Attendances"

    def save(self, *args, **kwargs):
        # Auto-calculate deduction for unexcused absence if base salary exists
        if self.status == self.Status.UNEXCUSED_ABSENCE and self.deduction_amount == 0 and self.teacher.base_salary:
            daily_rate = self.teacher.base_salary / Decimal('26') # 26 working days standard
            self.deduction_amount = round(daily_rate, 2)
        elif self.status in [self.Status.PRESENT, self.Status.EXCUSED_LEAVE]:
            self.deduction_amount = Decimal('0.00')
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.teacher.khmer_name} - {self.date} [{self.get_status_display()}]"


class TeacherLeaveRequest(models.Model):
    class Category(models.TextChoices):
        EMERGENCY = 'EMERGENCY', 'ការសុំច្បាប់ភ្លាមៗ (បន្ទាន់ / Emergency Leave)'
        PLANNED = 'PLANNED', 'ការសុំច្បាប់ទុកជាមុន (គ្រោងទុក / Planned Advance Leave)'

    class LeaveType(models.TextChoices):
        SICK = 'SICK', 'ច្បាប់ឈឺ / Sick Leave'
        PERSONAL = 'PERSONAL', 'ធុរៈផ្ទាល់ខ្លួន / Personal Leave'
        MISSION = 'MISSION', 'បេសកកម្មការងារ / Official Mission'
        MATERNITY = 'MATERNITY', 'លំហែមាតុភាព / Maternity Leave'
        OTHER = 'OTHER', 'ផ្សេងៗ / Other'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'រង់ចាំពិនិត្យ / Pending'
        APPROVED = 'APPROVED', 'បានអនុម័ត / Approved'
        REJECTED = 'REJECTED', 'បានបដិសេធ / Rejected'
        CANCELLED = 'CANCELLED', 'បានបោះបង់ / Cancelled'

    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.PLANNED,
        verbose_name="ប្រភេទនៃការដាក់ពាក្យសុំច្បាប់"
    )
    leave_code = models.CharField(max_length=50, blank=True, null=True, verbose_name="លេខកូដលិខិតសុំច្បាប់")
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='leave_requests', verbose_name="គ្រូបង្រៀន / Teacher")
    applied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='applied_teacher_leaves',
        verbose_name="អ្នកដាក់ពាក្យ / Submitted By"
    )
    proxy_note = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="កំណត់សម្គាល់ការដាក់ពាក្យជំនួស (Proxy Note)"
    )
    substitute_teacher = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='substitute_leave_requests',
        verbose_name="គ្រូបង្រៀនជំនួស (បើមាន) / Substitute Teacher"
    )
    leave_type = models.CharField(max_length=20, choices=LeaveType.choices, default=LeaveType.PERSONAL, verbose_name="ប្រភេទច្បាប់ / Leave Type")
    start_date = models.DateField(verbose_name="ថ្ងៃចាប់ផ្តើម / Start Date")
    end_date = models.DateField(verbose_name="ថ្ងៃបញ្ចប់ / End Date")
    reason = models.TextField(verbose_name="មូលហេតុសុំច្បាប់ / Reason")
    attachment = models.FileField(upload_to='teachers/leaves/', blank=True, null=True, verbose_name="ឯកសារភ្ជាប់ (បើមាន) / Attachment")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, verbose_name="ស្ថានភាព / Status")
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_teacher_leaves',
        verbose_name="អ្នកអនុម័ត / Approved By"
    )
    rejection_reason = models.TextField(blank=True, null=True, verbose_name="មូលហេតុបដិសេធ / Rejection Reason")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "ពាក្យសុំច្បាប់គ្រូបង្រៀន / Teacher Leave Request"
        verbose_name_plural = "ពាក្យសុំច្បាប់គ្រូបង្រៀនទាំងអស់ / Teacher Leave Requests"

    @property
    def is_proxy_application(self):
        if not self.applied_by:
            return False
        if hasattr(self.teacher, 'user') and self.teacher.user:
            return self.applied_by_id != self.teacher.user_id
        return True

    @property
    def total_days(self):
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return 1

    def __str__(self):
        return f"{self.teacher.khmer_name} - {self.get_leave_type_display()} ({self.start_date} ~ {self.end_date}) [{self.get_status_display()}]"



class TeacherBiometricProfile(models.Model):
    """
    Stores biometric identifiers, face embeddings, device binding UUID, and card PINs for a teacher.
    """
    teacher = models.OneToOneField(Teacher, on_delete=models.CASCADE, related_name='biometric_profile', verbose_name="គ្រូបង្រៀន / Teacher")
    device_uuid = models.CharField(max_length=120, blank=True, null=True, verbose_name="កូដឧបករណ៍ដែលបានភ្ជាប់ (Device Binding UUID)")
    device_name = models.CharField(max_length=150, blank=True, null=True, verbose_name="ឈ្មោះឧបករណ៍ / Device Model")
    face_photo = models.ImageField(upload_to='teachers/faces/', blank=True, null=True, verbose_name="រូបថតគំរូផ្ទៃមុខ / Enrolled Face Photo")
    face_descriptor = models.JSONField(blank=True, null=True, verbose_name="Face Embedding Descriptors Vector")
    card_rfid = models.CharField(max_length=50, blank=True, null=True, verbose_name="លេខកាត RFID / NFC / QR Pass Token")
    zk_pin = models.CharField(max_length=50, blank=True, null=True, verbose_name="លេខកូដសម្គាល់លើម៉ាស៊ីន (Biometric PIN / ID)")
    fingerprint_template = models.TextField(blank=True, null=True, verbose_name="Fingerprint Template (Base64)")
    is_enrolled_face = models.BooleanField(default=False, verbose_name="បានចុះឈ្មោះស្កេនមុខ / Enrolled Face")
    is_enrolled_fingerprint = models.BooleanField(default=False, verbose_name="បានចុះឈ្មោះក្រយៅដៃ / Enrolled Fingerprint")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "ទិន្នន័យ Biometric គ្រូ / Teacher Biometric Profile"
        verbose_name_plural = "ទិន្នន័យ Biometric គ្រូទាំងអស់ / Teacher Biometric Profiles"

    def __str__(self):
        return f"Biometric Profile: {self.teacher.khmer_name} (Face: {'YES' if self.is_enrolled_face else 'NO'}, Device: {self.device_uuid or 'NONE'})"


class TeacherPunchLog(models.Model):
    """
    Individual Check-in / Check-out punch logs recorded from any input method:
    (Dynamic QR Code, Webcam Face AI, Biometric Machine ZKTeco/Hikvision, USB Reader, Flash Drive Import).
    """
    class Method(models.TextChoices):
        QR_SCAN = 'QR_SCAN', 'Dynamic QR Code (ទូរស័ព្ទ / Mobile QR)'
        FACE_AI = 'FACE_AI', 'Webcam Face AI Recognition'
        BIOMETRIC_DEVICE = 'BIOMETRIC_DEVICE', 'ម៉ាស៊ីន Biometric (ZKTeco/Hikvision)'
        USB_FINGERPRINT = 'USB_FINGERPRINT', 'ឧបករណ៍ USB Fingerprint Reader'
        USB_FILE_IMPORT = 'USB_FILE_IMPORT', 'Import ពី USB Flash Drive'
        TIMETABLE_SYNC = 'TIMETABLE_SYNC', 'ស្រង់វត្តមានសិស្សតាមកាលវិភាគ'
        MANUAL_ADMIN = 'MANUAL_ADMIN', 'រដ្ឋបាលចុះដោយដៃ'

    class PunchType(models.TextChoices):
        CHECK_IN = 'CHECK_IN', 'ចូល / Check In'
        CHECK_OUT = 'CHECK_OUT', 'ចេញ / Check Out'
        AUTO = 'AUTO', 'ស្វ័យប្រវត្តិ / Auto Punch'

    class StatusResult(models.TextChoices):
        ON_TIME = 'ON_TIME', 'ទាន់ពេល / On Time'
        LATE = 'LATE', 'មកយឺត / Late'
        EARLY_LEAVE = 'EARLY_LEAVE', 'ចេញមុន / Left Early'
        NORMAL = 'NORMAL', 'ធម្មតា / Normal'

    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='punch_logs', verbose_name="គ្រូបង្រៀន / Teacher")
    punch_time = models.DateTimeField(verbose_name="ពេលវេលាស្កេន / Punch Timestamp")
    date = models.DateField(verbose_name="កាលបរិច្ឆេទ / Date")
    punch_type = models.CharField(max_length=20, choices=PunchType.choices, default=PunchType.CHECK_IN, verbose_name="ប្រភេទស្កេន / Punch Type")
    method = models.CharField(max_length=30, choices=Method.choices, default=Method.QR_SCAN, verbose_name="វិធីសាស្ត្រ / Method")
    status_result = models.CharField(max_length=30, choices=StatusResult.choices, default=StatusResult.ON_TIME, verbose_name="ស្ថានភាព / Status")
    gps_lat = models.FloatField(blank=True, null=True, verbose_name="រយៈទទឹង GPS (Latitude)")
    gps_lng = models.FloatField(blank=True, null=True, verbose_name="រយៈបណ្តោយ GPS (Longitude)")
    is_within_geofence = models.BooleanField(default=True, verbose_name="ក្នុងបរិវេណសាលា (Within Geofence)")
    device_uuid = models.CharField(max_length=120, blank=True, null=True, verbose_name="កូដឧបករណ៍ / Device UUID")
    ip_address = models.CharField(max_length=50, blank=True, null=True, verbose_name="IP Address")
    snapshot_photo = models.ImageField(upload_to='teachers/punch_snapshots/', blank=True, null=True, verbose_name="រូបថត Selfie Snapshot")
    notes = models.CharField(max_length=255, blank=True, null=True, verbose_name="កំណត់ចំណាំ / Notes")
    raw_payload = models.JSONField(blank=True, null=True, verbose_name="Raw Data Payload")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-punch_time', '-id']
        verbose_name = "កំណត់ត្រាស្កេនវត្តមានគ្រូ / Teacher Punch Log"
        verbose_name_plural = "កំណត់ត្រាស្កេនវត្តមានគ្រូទាំងអស់ / Teacher Punch Logs"

    def __str__(self):
        return f"{self.teacher.khmer_name} - {self.punch_time.strftime('%Y-%m-%d %H:%M:%S')} [{self.get_method_display()}] ({self.get_status_result_display()})"


class TeacherAttendanceConfig(models.Model):
    """
    Singleton configuration for Teacher Multi-Method Attendance, Policies, Timings & Hardware Integration.
    """
    class DailyMode(models.TextChoices):
        ALL = 'ALL', 'អនុញ្ញាតគ្រប់ជម្រើស (All Methods Allowed)'
        OPTION_1_QR = 'OPTION_1_QR', 'ជម្រើសទី ១: ស្កេន Dynamic QR Code ប៉ុណ្ណោះ (Option 1 - QR Only)'
        OPTION_2_FACE = 'OPTION_2_FACE', 'ជម្រើសទី ២: ស្កេនផ្ទៃមុខ Webcam Face AI ប៉ុណ្ណោះ (Option 2 - Face AI Only)'
        OPTION_3_BIOMETRIC = 'OPTION_3_BIOMETRIC', 'ជម្រើសទី ៣: ម៉ាស៊ីន Biometric ស្កេនមេដៃ/មុខ ប៉ុណ្ណោះ (Option 3 - Hardware Biometric Only)'

    # Admin Choice for Enforced Scan Mode
    active_daily_mode = models.CharField(
        max_length=30,
        choices=DailyMode.choices,
        default=DailyMode.ALL,
        verbose_name="ជម្រើសស្កេនវត្តមានប្រចាំថ្ងៃដែលបានកំណត់ដោយ Admin"
    )

    # Method Toggles
    enable_qr_checkin = models.BooleanField(default=True, verbose_name="បើកដំណើរការស្កេន Dynamic QR Code")
    enable_face_ai_checkin = models.BooleanField(default=True, verbose_name="បើកដំណើរការ Webcam Face Recognition AI")
    enable_biometric_device = models.BooleanField(default=True, verbose_name="បើកដំណើរការម៉ាស៊ីន Biometric (ZKTeco/Hikvision)")
    enable_usb_fingerprint = models.BooleanField(default=True, verbose_name="បើកដំណើរការឧបករណ៍ USB Fingerprint Reader")
    enable_file_import = models.BooleanField(default=True, verbose_name="បើកដំណើរការ Import File ពី USB Flash Drive")
    enable_timetable_sync = models.BooleanField(default=True, verbose_name="បើកដំណើរការ Sync ពីការស្រង់វត្តមានសិស្ស")


    # Security Policies
    require_gps_validation = models.BooleanField(default=True, verbose_name="តម្រូវឱ្យផ្ទៀងផ្ទាត់ទីតាំង GPS")
    require_device_binding = models.BooleanField(default=True, verbose_name="តម្រូវឱ្យចងភ្ជាប់ទូរស័ព្ទ (១ គណនី = ១ ទូរស័ព្ទ)")
    require_selfie_snap = models.BooleanField(default=False, verbose_name="តម្រូវឱ្យថតរូប Selfie បញ្ជាក់ពេលស្កេន")
    rolling_qr_interval_seconds = models.PositiveIntegerField(default=20, verbose_name="រយៈពេលផ្លាស់ប្តូរ Dynamic QR Code (វិនាទី)")

    # Shifts & Working Timings
    morning_checkin_start = models.TimeField(default='06:30', verbose_name="ម៉ោងចាប់ផ្តើម Check-in ពេលព្រឹក")
    morning_checkin_end = models.TimeField(default='08:30', verbose_name="ម៉ោងផុតកំណត់ Check-in ពេលព្រឹក")
    morning_late_threshold = models.TimeField(default='07:15', verbose_name="ម៉ោងចាត់ទុកថាមកយឺតពេលព្រឹក (Late Cutoff)")
    
    afternoon_checkin_start = models.TimeField(default='12:30', verbose_name="ម៉ោងចាប់ផ្តើម Check-in ពេលរសៀល")
    afternoon_checkin_end = models.TimeField(default='14:30', verbose_name="ម៉ោងផុតកំណត់ Check-in ពេលរសៀល")
    afternoon_late_threshold = models.TimeField(default='13:15', verbose_name="ម៉ោងចាត់ទុកថាមកយឺតពេលរសៀល (Late Cutoff)")

    # Emergency Leave Policy (ម៉ោងកំណត់ចុងក្រោយសម្រាប់សុំច្បាប់បន្ទាន់មុន១ថ្ងៃ)
    emergency_leave_cutoff_time = models.TimeField(default='17:00', verbose_name="ម៉ោងកំណត់ចុងក្រោយសម្រាប់សុំច្បាប់បន្ទាន់មុន១ថ្ងៃ")


    # Hardware & Network Integration
    biometric_device_ip = models.CharField(max_length=50, default='192.168.1.201', verbose_name="IP ម៉ាស៊ីន Biometric")
    biometric_device_port = models.PositiveIntegerField(default=4370, verbose_name="Port ម៉ាស៊ីន (ZKTeco=4370, Hik=8000)")
    biometric_device_type = models.CharField(
        max_length=30,
        choices=[
            ('ZKTECO', 'ZKTeco Standalone (UDP/TCP 4370)'),
            ('HIKVISION', 'Hikvision ISAPI Terminal (HTTP 80/8000)'),
            ('GENERIC_PUSH', 'Generic ADMS / Cloud Webhook Push')
        ],
        default='ZKTECO',
        verbose_name="ប្រភេទម៉ាស៊ីន Biometric"
    )
    biometric_push_secret = models.CharField(max_length=64, blank=True, null=True, verbose_name="Secret Token សម្រាប់ Push Webhook")
    notify_telegram_on_punch = models.BooleanField(default=True, verbose_name="ជូនដំណឹង Telegram ពេលគ្រូ Check-in")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "ការកំណត់វត្តមានគ្រូ & ឧបករណ៍ / Teacher Attendance & Biometric Config"
        verbose_name_plural = "ការកំណត់វត្តមានគ្រូ & ឧបករណ៍ / Teacher Attendance & Biometric Config"

    @classmethod
    def get_settings(cls):
        config = cls.objects.first()
        if not config:
            import uuid
            config = cls.objects.create(biometric_push_secret=uuid.uuid4().hex[:16])
        return config

    def __str__(self):
        return f"Attendance Config (QR: {'ON' if self.enable_qr_checkin else 'OFF'}, Face AI: {'ON' if self.enable_face_ai_checkin else 'OFF'}, Biometric: {'ON' if self.enable_biometric_device else 'OFF'})"


class TeacherProfileUpdateCampaign(models.Model):
    """
    Allows Admin to configure a Teacher Information Re-Submission / Verification Campaign.
    Admin can TICK specific sections/fields that teachers are required to review or update.
    """
    AVAILABLE_SECTIONS = [
        ('identity', 'អត្តសញ្ញាណ (Teacher ID, ឈ្មោះខ្មែរ, ឈ្មោះឡាតាំង)'),
        ('dob_gender', 'ថ្ងៃខែឆ្នាំកំណើត & ភេទ'),
        ('phone_email', 'លេខទូរស័ព្ទ & អ៊ីមែល'),
        ('address', 'អាសយដ្ឋានបច្ចុប្បន្ន (ភូមិ ឃុំ ស្រុក ខេត្ត)'),
        ('education', 'កម្រិតវប្បធម៌ & ឯកទេសទូទៅ'),
        ('training_subjects', 'កម្រិតបណ្តុះបណ្តាល & មុខវិជ្ជាឯកទេសទី១ ទី២'),
        ('civil_service', 'ព័ត៌មានក្របខ័ណ្ឌរដ្ឋ (ភារកិច្ច, ថ្ងៃចូលរដ្ឋ, ថ្ងៃតាំងស៊ប់, ប្រកាសលេខ...)'),
        ('photo_resume', 'រូបថត & ឯកសារ CV / Resume'),
    ]

    title = models.CharField(max_length=200, default="យុទ្ធនាការផ្ទៀងផ្ទាត់ និងបំពេញព័ត៌មានគ្រូបង្រៀន", verbose_name="ចំណងជើងយុទ្ធនាការ")
    instructions = models.TextField(blank=True, default="សូមលោកគ្រូ-អ្នកគ្រូ មេត្តាពិនិត្យ និងបំពេញព័ត៌មានដែលបានជ្រើសរើសខាងក្រោមឱ្យបានត្រឹមត្រូវ។", verbose_name="សេចក្តីណែនាំដល់គ្រូ")
    is_active = models.BooleanField(default=True, verbose_name="បើកដំណើរការយុទ្ធនាការ / Active")
    allowed_sections = models.JSONField(default=list, blank=True, verbose_name="ផ្នែកព័ត៌មានដែលតម្រូវឱ្យបំពេញ (Tick Selection)")
    target_all = models.BooleanField(default=True, verbose_name="អនុវត្តចំពោះគ្រូទាំងអស់ / Target All Teachers")
    target_teachers = models.ManyToManyField(Teacher, blank=True, related_name='update_campaigns', verbose_name="គ្រូជាក់លាក់")
    deadline = models.DateField(null=True, blank=True, verbose_name="កាលបរិច្ឆេទផុតកំណត់ / Deadline")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "យុទ្ធនាការបំពេញព័ត៌មានគ្រូ / Teacher Profile Update Campaign"
        verbose_name_plural = "យុទ្ធនាការបំពេញព័ត៌មានគ្រូទាំងអស់"

    @classmethod
    def get_current_active(cls, teacher=None):
        import datetime
        campaign = cls.objects.filter(is_active=True).first()
        if not campaign:
            return None
        if campaign.deadline and campaign.deadline < datetime.date.today():
            return None
        if teacher and not campaign.target_all:
            if not campaign.target_teachers.filter(id=teacher.id).exists():
                return None
        return campaign

    def is_section_allowed(self, section_code):
        if not self.allowed_sections:
            return True # If empty, all allowed
        return section_code in self.allowed_sections

    def __str__(self):
        return f"{self.title} ({'Active' if self.is_active else 'Closed'})"



