from django.db import models
from django.conf import settings

class StudentAttendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = 'PRESENT', 'វត្តមាន / Present'
        ABSENT = 'ABSENT', 'អវត្តមានឥតច្បាប់ / Absent (Unexcused)'
        PERMISSION = 'PERMISSION', 'អវត្តមានមានច្បាប់ / Excused Permission'
        LATE = 'LATE', 'មកយឺត / Late'

    class Session(models.TextChoices):
        MORNING = 'MORNING', 'ពេលព្រឹក / Morning'
        AFTERNOON = 'AFTERNOON', 'ពេលរសៀល / Afternoon'

    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='attendances', verbose_name="សិស្ស / Student")
    classroom = models.ForeignKey('academics.Classroom', on_delete=models.CASCADE, related_name='student_attendances', verbose_name="ថ្នាក់រៀន / Classroom")
    date = models.DateField(verbose_name="កាលបរិច្ឆេទ / Date")
    session = models.CharField(max_length=20, choices=Session.choices, default=Session.MORNING, verbose_name="វេនសិក្សា / Session")

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PRESENT, verbose_name="ស្ថានភាពវត្តមាន / Status")
    period_number = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="ម៉ោងទី / Period Number")
    subject = models.ForeignKey('academics.Subject', on_delete=models.SET_NULL, null=True, blank=True, related_name='student_attendances', verbose_name="មុខវិជ្ជា / Subject")

    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="អ្នកស្រង់វត្តមាន / Recorded By")
    notes = models.CharField(max_length=255, blank=True, null=True, verbose_name="មូលហេតុ / កំណត់ចំណាំ")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', 'student']
        unique_together = ('student', 'date', 'session', 'period_number')
        verbose_name = "វត្តមានសិស្ស / Student Attendance"
        verbose_name_plural = "វត្តមានសិស្សទាំងអស់ / Student Attendances"


    def __str__(self):
        return f"{self.student.khmer_name} - {self.date} [{self.get_status_display()}]"


class AttendanceSubmissionLog(models.Model):
    classroom = models.ForeignKey('academics.Classroom', on_delete=models.CASCADE, related_name='attendance_logs', verbose_name="ថ្នាក់រៀន / Classroom")
    date = models.DateField(verbose_name="កាលបរិច្ឆេទ / Date")
    session = models.CharField(max_length=20, choices=StudentAttendance.Session.choices, verbose_name="វេនសិក្សា / Session")
    period_number = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="ម៉ោងទី / Period Number")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="អ្នកស្រង់វត្តមាន / Recorded By")
    submission_count = models.PositiveIntegerField(default=1, verbose_name="ចំនួនដងដែលបានបញ្ជូន / Submission Count")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', 'classroom', 'period_number']
        unique_together = ('classroom', 'date', 'session', 'period_number')
        verbose_name = "កំណត់ត្រាការបញ្ជូនវត្តមាន / Attendance Submission Log"
        verbose_name_plural = "កំណត់ត្រាការបញ្ជូនវត្តមានទាំងអស់ / Attendance Submission Logs"

    def __str__(self):
        return f"{self.classroom.name} - {self.date} [P{self.period_number}] (Submissions: {self.submission_count})"


def get_default_dispatch_schedule():
    return {
        "1": "17:00",
        "2": "17:00",
        "3": "17:00",
        "4": "17:00",
        "5": "17:00",
        "6": "11:30",
        "7": None,
    }


def get_default_period_grace_minutes():
    return {
        "1": 30,
        "2": 30,
        "3": 30,
        "4": 30,
        "5": 30,
        "6": 30,
        "7": 30,
        "8": 30,
    }


def get_default_period_dispatch_times():
    return {
        "1": "07:35",
        "2": "08:30",
        "3": "09:25",
        "4": "10:20",
        "5": "13:35",
        "6": "14:30",
        "7": "15:25",
        "8": "16:20",
    }


class AttendanceSetting(models.Model):
    """
    Singleton configuration for Attendance policies, grace window cutoff,
    Telegram automation, and system maintenance lockouts.
    """
    submission_grace_minutes = models.PositiveIntegerField(
        default=30,
        verbose_name="កំឡុងពេល Deadline អនុញ្ញាតឱ្យចុះវត្តមានទូទៅ (នាទី) / Global Submission Grace Window (Mins)"
    )
    period_grace_minutes = models.JSONField(
        default=get_default_period_grace_minutes,
        verbose_name="កំឡុងពេល Deadline តាមម៉ោងនីមួយៗ (ម៉ោងទី១-៨) / Period Grace Minutes (P1-P8)"
    )
    management_chat_id = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="Telegram Group គណៈគ្រប់គ្រងសាលា (អាចដាក់ច្រើន Chat ID) / Management Telegram Chat IDs"
    )
    is_maintenance_mode = models.BooleanField(
        default=False,
        verbose_name="បិទប្រព័ន្ធជាបណ្តោះអាសន្នសម្រាប់ថែទាំ / Maintenance Mode Lockout"
    )
    maintenance_message = models.TextField(
        default="ប្រព័ន្ធស្រង់វត្តមានកំពុងបិទដំណើរការជាបណ្តោះអាសន្នដើម្បីធ្វើបច្ចុប្បន្នភាព និងថែទាំបច្ចេកទេស។ សូមអភ័យទោសចំពោះការរំខាន!",
        verbose_name="សារជូនដំណឹងពេលបិទថែទាំ / Maintenance Notice"
    )
    auto_daily_dispatch_enabled = models.BooleanField(
        default=True,
        verbose_name="បើកដំណើរការផ្ញើរបាយការណ៍ស្វ័យប្រវត្តិតាម Telegram / Auto Daily Telegram Dispatch"
    )
    daily_dispatch_schedule = models.JSONField(
        default=get_default_dispatch_schedule,
        verbose_name="កាលវិភាគម៉ោងផ្ញើប្រចាំថ្ងៃ (១=ច័ន្ទ ... ៧=អាទិត្យ) / Daily Dispatch Schedule"
    )
    auto_send_student_summary = models.BooleanField(
        default=True,
        verbose_name="ផ្ញើសង្ខេបអវត្តមានសិស្សប្រចាំថ្ងៃ / Auto Send Student Summary"
    )
    auto_send_teacher_summary = models.BooleanField(
        default=True,
        verbose_name="ផ្ញើសង្ខេបវត្តមានគ្រូប្រចាំថ្ងៃ / Auto Send Teacher Summary"
    )

    # Hourly Absence Auto-Dispatch Settings
    hourly_dispatch_enabled = models.BooleanField(
        default=True,
        verbose_name="បើកដំណើរការផ្ញើបញ្ជីអវត្តមានស្វ័យប្រវត្តិតាមម៉ោង / Enable Hourly Auto Dispatch"
    )
    period_dispatch_times = models.JSONField(
        default=get_default_period_dispatch_times,
        verbose_name="ម៉ោងកំណត់ (Deadline) សម្រាប់ផ្ញើអវត្តមានតាមម៉ោងនីមួយៗ (P1-P8) / Period Dispatch Deadlines"
    )
    dispatch_to_guardians = models.BooleanField(
        default=True,
        verbose_name="ផ្ញើទៅអាណាព្យាបាលផ្ទាល់ / Send to Direct Guardians"
    )
    dispatch_to_homeroom = models.BooleanField(
        default=True,
        verbose_name="ផ្ញើទៅគ្រូបន្ទុកថ្នាក់ & Group ថ្នាក់ / Send to Homeroom Teachers & Class Groups"
    )
    dispatch_to_management = models.BooleanField(
        default=True,
        verbose_name="ផ្ញើទៅ Group គណៈគ្រប់គ្រងសាលា / Send to Management Group"
    )
    # Assembly & Pre-Class Attendance Configuration (វត្តមានពេលគោរពទង់ជាតិ & មុនម៉ោងចូលរៀន)
    enable_assembly_attendance = models.BooleanField(
        default=True,
        verbose_name="បើកដំណើរការស្រង់វត្តមានពេលគោរពទង់ជាតិ/មុនម៉ោងចូលរៀន / Enable Assembly Attendance"
    )
    assembly_morning_start = models.TimeField(
        default='06:30',
        verbose_name="ម៉ោងចាប់ផ្តើមស្រង់វត្តមានពេលព្រឹក (ឧ. 06:30)"
    )
    assembly_morning_end = models.TimeField(
        default='06:50',
        verbose_name="ម៉ោងបញ្ចប់ស្រង់វត្តមានពេលព្រឹក (ឧ. 06:50)"
    )
    assembly_afternoon_start = models.TimeField(
        default='12:30',
        verbose_name="ម៉ោងចាប់ផ្តើមស្រង់វត្តមានពេលរសៀល (ឧ. 12:30)"
    )
    assembly_afternoon_end = models.TimeField(
        default='12:50',
        verbose_name="ម៉ោងបញ្ចប់ស្រង់វត្តមានពេលរសៀល (ឧ. 12:50)"
    )
    allow_all_teachers_assembly_recording = models.BooleanField(
        default=True,
        verbose_name="អនុញ្ញាតឱ្យគ្រូបង្រៀនទាំងអស់អាចស្រង់វត្តមានគោរពទង់ជាតិ / Allow All Teachers to record Assembly Attendance"
    )
    allow_monitor_assembly_recording = models.BooleanField(
        default=True,
        verbose_name="អនុញ្ញាតឱ្យប្រធានថ្នាក់/អនុប្រធានថ្នាក់ស្រង់វត្តមានតាមទូរស័ព្ទ / Allow Class Monitors to record via Mobile/Tablet"
    )
    assembly_telegram_alert = models.BooleanField(
        default=True,
        verbose_name="ជូនដំណឹង Telegram ទៅគណៈគ្រប់គ្រងភ្លាមៗក្រោយគោរពទង់ជាតិ / Instant Management Telegram Alert"
    )
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        verbose_name = "ការកំណត់ប្រព័ន្ធវត្តមាន និង Telegram / Attendance & Telegram Setting"
        verbose_name_plural = "ការកំណត់ប្រព័ន្ធវត្តមាន និង Telegram / Attendance & Telegram Settings"

    @classmethod
    def get_settings(cls):
        setting = cls.objects.first()
        if not setting:
            setting = cls.objects.create()
        return setting

    def get_grace_minutes_for_period(self, period_number):
        """
        Returns the grace window (in minutes) for the given period_number (1-8).
        Falls back to submission_grace_minutes or 30.
        """
        if self.period_grace_minutes and isinstance(self.period_grace_minutes, dict):
            val = self.period_grace_minutes.get(str(period_number))
            if val is not None:
                try:
                    return int(val)
                except (ValueError, TypeError):
                    pass
        return self.submission_grace_minutes or 30

    def __str__(self):
        return f"Attendance Settings (Deadline P1-P8: {self.period_grace_minutes}, Maintenance: {'ON' if self.is_maintenance_mode else 'OFF'})"


