from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.conf import settings
from decimal import Decimal


class AcademicYear(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name="ឆ្នាំសិក្សា / Academic Year Name (e.g. 2025-2026)")
    start_date = models.DateField(verbose_name="ថ្ងៃចាប់ផ្តើម / Start Date")
    end_date = models.DateField(verbose_name="ថ្ងៃបញ្ចប់ / End Date")
    is_current = models.BooleanField(default=True, verbose_name="ឆ្នាំសិក្សាបច្ចុប្បន្ន / Is Current Year")

    class Meta:
        ordering = ['-start_date']
        verbose_name = "ឆ្នាំសិក្សា / Academic Year"
        verbose_name_plural = "ឆ្នាំសិក្សាទាំងអស់ / Academic Years"

    def save(self, *args, **kwargs):
        if self.is_current:
            AcademicYear.objects.filter(is_current=True).exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name}{' (បច្ចុប្បន្ន)' if self.is_current else ''}"


class AcademicTrack(models.Model):
    """
    Academic Track / Program (e.g. GENERAL, SCIENCE, SOCIAL, TECH, BILINGUAL, etc.)
    Admin can create, edit, delete any tracks freely.
    """
    code = models.CharField(max_length=50, unique=True, verbose_name="កូដជំនាញ / Track Code (e.g. GENERAL, SCIENCE, SOCIAL, TECH)")
    name_kh = models.CharField(max_length=150, verbose_name="ឈ្មោះជំនាញ (ខ្មែរ) / Track Name (Khmer)")
    name_en = models.CharField(max_length=150, blank=True, null=True, verbose_name="ឈ្មោះជំនាញ (អង់គ្លេស) / Track Name (English)")
    is_default = models.BooleanField(default=False, verbose_name="ជំនាញស្តង់ដារ MoEYS / Is Standard")
    order = models.IntegerField(default=1, verbose_name="លំដាប់លំដោយ / Sort Order")

    class Meta:
        ordering = ['order', 'id']
        verbose_name = "ជំនាញ/កម្មវិធីសិក្សា / Academic Track"
        verbose_name_plural = "ជំនាញ/កម្មវិធីសិក្សាទាំងអស់ / Academic Tracks"

    @classmethod
    def get_track_choices(cls):
        try:
            tracks = list(cls.objects.all().order_by('order', 'id'))
            if not tracks:
                cls.objects.bulk_create([
                    cls(code='GENERAL', name_kh='កម្មវិធីទូទៅ (ថ្នាក់ទី ៧-១០)', name_en='General Track (Grades 7-10)', is_default=True, order=1),
                    cls(code='SCIENCE', name_kh='ថ្នាក់វិទ្យាសាស្ត្រ (Science Track)', name_en='Science Track', is_default=True, order=2),
                    cls(code='SOCIAL', name_kh='ថ្នាក់វិទ្យាសាស្ត្រសង្គម (Social Science Track)', name_en='Social Science Track', is_default=True, order=3),
                ])
                tracks = list(cls.objects.all().order_by('order', 'id'))
            return [(t.code, t.name_kh) for t in tracks]
        except Exception:
            return [
                ('GENERAL', 'កម្មវិធីទូទៅ (ថ្នាក់ទី ៧-១០)'),
                ('SCIENCE', 'ថ្នាក់វិទ្យាសាស្ត្រ (Science Track)'),
                ('SOCIAL', 'ថ្នាក់វិទ្យាសាស្ត្រសង្គម (Social Science Track)'),
            ]

    def __str__(self):
        return self.name_kh


class GradeLevel(models.Model):
    """
    Dynamic Grade Level entity (e.g., ថ្នាក់ទី ៧, ថ្នាក់ទី ១០ វិទ្យាសាស្ត្រ, ថ្នាក់ទី ១០ វិទ្យាសាស្ត្រសង្គម)
    Admin can create, edit, delete any grade levels freely.
    """
    name = models.CharField(max_length=100, verbose_name="ឈ្មោះកម្រិតថ្នាក់ / Grade Level Name (e.g. ថ្នាក់ទី ១០ វិទ្យាសាស្ត្រ)")
    grade_number = models.IntegerField(verbose_name="កម្រិតថ្នាក់លេខ / Grade Number (e.g. 7, 8, 9, 10, 11, 12)")
    track = models.CharField(max_length=50, default='GENERAL', verbose_name="ជំនាញសិក្សា / Track (GENERAL, SCIENCE, SOCIAL...)")
    order = models.IntegerField(default=1, verbose_name="លំដាប់លំដោយ / Sort Order")

    class Meta:
        ordering = ['order', 'grade_number', 'track', 'id']
        unique_together = ('grade_number', 'track')
        verbose_name = "កម្រិតថ្នាក់ / Grade Level"
        verbose_name_plural = "កម្រិតថ្នាក់ទាំងអស់ / Grade Levels"

    def get_subject_rules(self):
        return GradeLevelRule.objects.filter(
            grade_level=self.grade_number,
            track=self.track
        ).select_related('subject').order_by('subject__order', 'id')

    def get_total_max_score(self):
        rules = self.get_subject_rules()
        return sum(r.max_score for r in rules)

    def __str__(self):
        return self.name


class Classroom(models.Model):
    class Track(models.TextChoices):
        GENERAL = 'GENERAL', 'កម្មវិធីទូទៅ (ថ្នាក់ទី ៧-១០)'
        SCIENCE = 'SCIENCE', 'ថ្នាក់វិទ្យាសាស្ត្រ (Science Track)'
        SOCIAL = 'SOCIAL', 'ថ្នាក់វិទ្យាសាស្ត្រសង្គម (Social Science Track)'

    name = models.CharField(max_length=100, verbose_name="ឈ្មោះថ្នាក់រៀន / Class Name (e.g. ថ្នាក់ទី៧A, ទី១១ វិទ្យាសាស្ត្រ)")
    code = models.CharField(max_length=20, verbose_name="កូដថ្នាក់ / Class Code (e.g. 7A, 11-SCI)")
    grade_level = models.IntegerField(default=10, verbose_name="កម្រិតថ្នាក់ (៧-១២) / Grade Level (7-12)")
    track = models.CharField(max_length=50, choices=Track.choices, default=Track.GENERAL, verbose_name="ជំនាញសិក្សា / Academic Track")
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='classrooms', verbose_name="ឆ្នាំសិក្សា / Academic Year")
    room_number = models.CharField(max_length=100, blank=True, null=True, verbose_name="បន្ទប់រៀន / Room Number (e.g. បន្ទប់ 201)")
    capacity = models.IntegerField(default=40, null=True, blank=True, verbose_name="ចំនួនសិស្សអតិបរមា / Capacity")
    homeroom_teacher = models.ForeignKey('teachers.Teacher', on_delete=models.SET_NULL, null=True, blank=True, related_name='homeroom_classes', verbose_name="គ្រូបន្ទុកថ្នាក់ / Homeroom Teacher")
    assembly_duty_teacher = models.ForeignKey('teachers.Teacher', on_delete=models.SET_NULL, null=True, blank=True, related_name='assembly_duty_classes', verbose_name="គ្រូទទួលបន្ទុកស្រង់វត្តមានគោរពទង់ជាតិ / Assembly Duty Teacher")
    class_monitor = models.ForeignKey('students.Student', on_delete=models.SET_NULL, null=True, blank=True, related_name='monitor_classrooms', verbose_name="ប្រធានថ្នាក់ / Class Monitor")
    vice_monitor = models.ForeignKey('students.Student', on_delete=models.SET_NULL, null=True, blank=True, related_name='vice_monitor_classrooms', verbose_name="អនុប្រធានថ្នាក់ / Vice Class Monitor")
    telegram_chat_id = models.CharField(max_length=300, blank=True, null=True, verbose_name="Telegram Group/Chat ID (សម្រាប់ផ្ញើវត្តមានថ្នាក់ អាចដាក់ច្រើន Chat ID)")


    class Meta:
        ordering = ['grade_level', 'code']
        unique_together = ('code', 'academic_year')
        verbose_name = "ថ្នាក់រៀន / Classroom"
        verbose_name_plural = "ថ្នាក់រៀនទាំងអស់ / Classrooms"

    @property
    def total_students(self):
        return self.students.filter(status='ACTIVE').count()

    @property
    def female_students(self):
        return self.students.filter(status='ACTIVE', gender='F').count()

    def get_assigned_subject_ids(self):
        """Returns list of subject IDs assigned to this classroom"""
        return list(self.assigned_subjects.values_list('subject_id', flat=True))

    def get_assigned_subjects(self):
        """Returns subjects assigned to this classroom, or default subjects for its grade & track if none explicitly set"""
        assigned_ids = self.get_assigned_subject_ids()
        if assigned_ids:
            return Subject.objects.filter(id__in=assigned_ids).order_by('order', 'id')
        sub_ids = GradeLevelRule.objects.filter(
            grade_level=self.grade_level,
            track=self.track
        ).values_list('subject_id', flat=True)
        return Subject.objects.filter(id__in=sub_ids).order_by('order', 'id')

    def get_subject_rules(self):
        """Returns active subject max score rules applicable for this classroom, sorted by subject order"""
        assigned_ids = self.get_assigned_subject_ids()
        if assigned_ids:
            return GradeLevelRule.objects.filter(
                grade_level=self.grade_level,
                track=self.track,
                subject_id__in=assigned_ids
            ).select_related('subject').order_by('subject__order', 'id')

        return GradeLevelRule.objects.filter(
            grade_level=self.grade_level,
            track=self.track
        ).select_related('subject').order_by('subject__order', 'id')

    def get_total_max_score(self):
        """Returns sum of all max scores for this classroom's curriculum"""
        rules = self.get_subject_rules()
        return sum(r.max_score for r in rules)

    def sync_assigned_subjects(self, subject_ids):
        """
        Synchronizes ClassSubject records for this classroom.
        Keeps existing assignments (preserving teacher/hours), deletes unchecked ones, and creates new ones.
        """
        from apps.teachers.models import Teacher
        target_ids = [int(sid) for sid in subject_ids if str(sid).isdigit()]
        self.assigned_subjects.exclude(subject_id__in=target_ids).delete()
        existing_sub_ids = set(self.assigned_subjects.values_list('subject_id', flat=True))
        active_teachers = list(Teacher.objects.filter(status='ACTIVE'))
        for sid in target_ids:
            if sid not in existing_sub_ids:
                tch = None
                if active_teachers:
                    tch = active_teachers[(sid + (self.id or 0)) % len(active_teachers)]
                ClassSubject.objects.create(classroom=self, subject_id=sid, teacher=tch)

    def __str__(self):
        return f"{self.name} [{self.academic_year.name}]"


class Subject(models.Model):
    class SubjectCategory(models.TextChoices):
        SCIENCE = 'SCIENCE', 'វិទ្យាសាស្ត្រពិត (Science / STEM)'
        SOCIAL = 'SOCIAL', 'វិទ្យាសាស្ត្រសង្គម (Social Science / Humanities)'
        GENERAL = 'GENERAL', 'ចំណេះទូទៅ & ភាសា (General / Languages)'
        TECH = 'TECH', 'បច្ចេកទេស & IT (Technical & ICT)'
        SPECIALIZED = 'SPECIALIZED', 'មុខវិជ្ជាឯកទេស & វិជ្ជាជីវៈ (Specialized & Vocational)'

    name_kh = models.CharField(max_length=150, verbose_name="ឈ្មោះមុខវិជ្ជា (ខ្មែរ) / Subject Name (Khmer)")
    name_en = models.CharField(max_length=150, verbose_name="ឈ្មោះមុខវិជ្ជា (អង់គ្លេស) / Subject Name (English)")
    code = models.CharField(max_length=30, unique=True, verbose_name="អក្សរកាត់/កូដ / Subject Short Code (e.g. R, D, K, M)")
    category = models.CharField(max_length=30, choices=SubjectCategory.choices, default=SubjectCategory.GENERAL, verbose_name="ក្រុមមុខវិជ្ជា / Category")
    credit = models.IntegerField(default=2, verbose_name="ក្រេឌីត/មេគុណ / Credit Hours/Weight")
    color_code = models.CharField(max_length=20, default="#4f46e5", verbose_name="ពណ៌សម្គាល់ / Badge Color")
    order = models.IntegerField(default=1, verbose_name="លំដាប់លំដោយ / Sort Order")

    class Meta:
        ordering = ['order', 'id']
        verbose_name = "មុខវិជ្ជា / Subject"
        verbose_name_plural = "មុខវិជ្ជាទាំងអស់ / Subjects"

    @property
    def display_name(self):
        return f"{self.name_kh} ({self.name_en})"

    def __str__(self):
        return f"{self.name_kh} ({self.code})"


class GradeLevelRule(models.Model):
    """
    Official MoEYS Scoring & Curriculum Rule per Grade Level & Track
    Defines which subjects exist for each grade level stream and their exact max scores!
    """
    grade_level = models.IntegerField(verbose_name="កម្រិតថ្នាក់ (7-12) / Grade Level")
    track = models.CharField(max_length=30, default='GENERAL', verbose_name="មុខវិជ្ជា/ជំនាញ / Track")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='grade_rules', verbose_name="មុខវិជ្ជា / Subject")
    max_score = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('50.00'), verbose_name="ពិន្ទុអតិបរមា / Max Score")
    weekly_hours = models.IntegerField(default=2, verbose_name="ម៉ោងសិក្សាក្នុងមួយសប្តាហ៍ / Weekly Hours")
    order = models.IntegerField(default=1, verbose_name="លំដាប់លំដោយ / Sort Order")

    class Meta:
        ordering = ['grade_level', 'track', 'subject__order', 'order']
        unique_together = ('grade_level', 'track', 'subject')
        verbose_name = "ច្បាប់ពិន្ទុតាមកម្រិតថ្នាក់ / Grade Level Scoring Rule"
        verbose_name_plural = "ច្បាប់ពិន្ទុតាមកម្រិតថ្នាក់ទាំងអស់ / Grade Level Scoring Rules"

    def __str__(self):
        return f"ថ្នាក់ទី {self.grade_level} ({self.track}) - {self.subject.name_kh} (ម៉ោង: {self.weekly_hours}, ពិន្ទុ: {self.max_score})"


class SavedDefaultConfig(models.Model):
    """
    Stores system default configurations saved by Administrator so it can be restored anytime.
    """
    key = models.CharField(max_length=50, unique=True, default='custom_scoring_rules')
    data = models.JSONField(default=dict, verbose_name="ទិន្នន័យកំណត់លំនាំដើម / Default Config Data")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Default Preset [{self.key}] updated {self.updated_at.strftime('%Y-%m-%d %H:%M')}"


class ClassSubject(models.Model):
    classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE, related_name='assigned_subjects')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='class_assignments')
    teacher = models.ForeignKey('teachers.Teacher', on_delete=models.SET_NULL, null=True, blank=True, related_name='subject_assignments')
    weekly_hours = models.IntegerField(default=4, verbose_name="ម៉ោងក្នុងមួយសប្តាហ៍ / Weekly Hours")

    class Meta:
        unique_together = ('classroom', 'subject')
        verbose_name = "មុខវិជ្ជាប្រចាំថ្នាក់ / Class Subject Assignment"
        verbose_name_plural = "មុខវិជ្ជាប្រចាំថ្នាក់ / Class Subject Assignments"

    def __str__(self):
        teacher_name = self.teacher.khmer_name if self.teacher else "មិនទាន់ចាត់តាំង"
        return f"{self.classroom.name} - {self.subject.name_kh} (គ្រូ: {teacher_name})"


class Timetable(models.Model):
    class DayOfWeek(models.IntegerChoices):
        MONDAY = 1, 'ថ្ងៃច័ន្ទ / Monday'
        TUESDAY = 2, 'ថ្ងៃអង្គារ / Tuesday'
        WEDNESDAY = 3, 'ថ្ងៃពុធ / Wednesday'
        THURSDAY = 4, 'ថ្ងៃព្រហស្បតិ៍ / Thursday'
        FRIDAY = 5, 'ថ្ងៃសុក្រ / Friday'
        SATURDAY = 6, 'ថ្ងៃសៅរ៍ / Saturday'

    classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE, related_name='timetable_entries', verbose_name="ថ្នាក់រៀន / Classroom")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, verbose_name="មុខវិជ្ជា / Subject")
    teacher = models.ForeignKey('teachers.Teacher', on_delete=models.CASCADE, related_name='timetable_entries', verbose_name="គ្រូបង្រៀន / Teacher")
    day_of_week = models.IntegerField(choices=DayOfWeek.choices, verbose_name="ថ្ងៃក្នុងសប្តាហ៍ / Day of Week")
    period_number = models.IntegerField(default=1, verbose_name="ម៉ោងទី / Period (1-8)")
    start_time = models.TimeField(verbose_name="ម៉ោងចាប់ផ្តើម / Start Time")
    end_time = models.TimeField(verbose_name="ម៉ោងបញ្ចប់ / End Time")
    room = models.CharField(max_length=100, blank=True, null=True, verbose_name="បន្ទប់សិក្សា / Room (Optional)")

    class Meta:
        ordering = ['day_of_week', 'start_time']
        verbose_name = "កាលវិភាគ / Timetable Entry"
        verbose_name_plural = "កាលវិភាគទាំងអស់ / Timetable Entries"

    def clean(self):
        super().clean()
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError({'end_time': "ម៉ោងបញ្ចប់ត្រូវតែធំជាងម៉ោងចាប់ផ្តើម! (End time must be after start time)"})

        # 1. Teacher Conflict Check (strictly within the same academic year)
        teacher_clashes = Timetable.objects.filter(
            teacher=self.teacher,
            day_of_week=self.day_of_week,
            start_time__lt=self.end_time,
            end_time__gt=self.start_time
        )
        cls_obj = self.classroom if (hasattr(self, 'classroom') and self.classroom) else Classroom.objects.filter(id=self.classroom_id).first()
        if cls_obj and cls_obj.academic_year_id:
            teacher_clashes = teacher_clashes.filter(classroom__academic_year_id=cls_obj.academic_year_id)
        elif cls_obj and cls_obj.academic_year:
            teacher_clashes = teacher_clashes.filter(classroom__academic_year=cls_obj.academic_year)
        else:
            teacher_clashes = teacher_clashes.filter(classroom__academic_year__isnull=True)

        if self.pk:
            teacher_clashes = teacher_clashes.exclude(pk=self.pk)
        
        if teacher_clashes.exists():
            clash = teacher_clashes.first()
            year_name = f"ឆ្នាំសិក្សា {cls_obj.academic_year.name}" if cls_obj and cls_obj.academic_year else "ឆ្នាំសិក្សានេះ"
            raise ValidationError({
                'teacher': f"គ្រូ {self.teacher.khmer_name} មានម៉ោងបង្រៀនជាន់គ្នានៅ {clash.classroom.name} ({clash.start_time.strftime('%H:%M')} - {clash.end_time.strftime('%H:%M')}) ក្នុង{year_name}!"
            })

        # 2. Classroom Conflict Check
        classroom_clashes = Timetable.objects.filter(
            classroom=self.classroom,
            day_of_week=self.day_of_week,
            start_time__lt=self.end_time,
            end_time__gt=self.start_time
        )
        if self.pk:
            classroom_clashes = classroom_clashes.exclude(pk=self.pk)
        
        if classroom_clashes.exists():
            clash = classroom_clashes.first()
            raise ValidationError({
                'classroom': f"ថ្នាក់ {self.classroom.name} មានម៉ោងរៀនមុខវិជ្ជា {clash.subject.name_kh} ជាន់គ្នារួចហើយ ({clash.start_time.strftime('%H:%M')} - {clash.end_time.strftime('%H:%M')})!"
            })

    def __str__(self):
        return f"{self.classroom.name} | {self.get_day_of_week_display()} | {self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')} | {self.subject.name_kh} ({self.teacher.khmer_name})"


# =========================================================================
# Cambodia Administrative Hierarchy (ខេត្ត, ស្រុក, ឃុំ, ភូមិ)
# =========================================================================

class Province(models.Model):
    code = models.CharField(max_length=50, unique=True, verbose_name="កូដខេត្ត / Province Code")
    name_kh = models.CharField(max_length=150, verbose_name="ឈ្មោះខេត្ត/រាជធានី (ខ្មែរ)")
    name_en = models.CharField(max_length=150, blank=True, verbose_name="ឈ្មោះខេត្ត/រាជធានី (ឡាតាំង)")

    class Meta:
        ordering = ['code']
        verbose_name = "ខេត្ត/រាជធានី / Province"
        verbose_name_plural = "ខេត្ត/រាជធានីទាំងអស់ / Provinces"

    def __str__(self):
        return self.name_kh


class District(models.Model):
    province = models.ForeignKey(Province, on_delete=models.CASCADE, related_name='districts', verbose_name="ខេត្ត/រាជធានី")
    code = models.CharField(max_length=50, db_index=True, verbose_name="កូដស្រុក / District Code")
    name_kh = models.CharField(max_length=150, verbose_name="ឈ្មោះស្រុក/ខណ្ឌ/ក្រុង (ខ្មែរ)")
    name_en = models.CharField(max_length=150, blank=True, verbose_name="ឈ្មោះស្រុក/ខណ្ឌ/ក្រុង (ឡាតាំង)")

    class Meta:
        ordering = ['code']
        verbose_name = "ស្រុក/ខណ្ឌ/ក្រុង / District"
        verbose_name_plural = "ស្រុក/ខណ្ឌ/ក្រុងទាំងអស់ / Districts"

    def __str__(self):
        return f"{self.name_kh} ({self.province.name_kh})"


class Commune(models.Model):
    district = models.ForeignKey(District, on_delete=models.CASCADE, related_name='communes', verbose_name="ស្រុក/ខណ្ឌ/ក្រុង")
    code = models.CharField(max_length=50, db_index=True, verbose_name="កូដឃុំ / Commune Code")
    name_kh = models.CharField(max_length=150, verbose_name="ឈ្មោះឃុំ/សង្កាត់ (ខ្មែរ)")
    name_en = models.CharField(max_length=150, blank=True, verbose_name="ឈ្មោះឃុំ/សង្កាត់ (ឡាតាំង)")

    class Meta:
        ordering = ['code']
        verbose_name = "ឃុំ/សង្កាត់ / Commune"
        verbose_name_plural = "ឃុំ/សង្កាត់ទាំងអស់ / Communes"

    def __str__(self):
        return f"{self.name_kh} ({self.district.name_kh})"


class Village(models.Model):
    commune = models.ForeignKey(Commune, on_delete=models.CASCADE, related_name='villages', verbose_name="ឃុំ/សង្កាត់")
    code = models.CharField(max_length=50, db_index=True, blank=True, verbose_name="កូដភូមិ / Village Code")
    name_kh = models.CharField(max_length=150, verbose_name="ឈ្មោះភូមិ (ខ្មែរ)")
    name_en = models.CharField(max_length=150, blank=True, verbose_name="ឈ្មោះភូមិ (ឡាតាំង)")

    class Meta:
        ordering = ['code']
        verbose_name = "ភូមិ / Village"
        verbose_name_plural = "ភូមិទាំងអស់ / Villages"

    def __str__(self):
        return f"{self.name_kh} ({self.commune.name_kh})"


class AcademicCalendarRestriction(models.Model):
    class RestrictionType(models.TextChoices):
        VACATION = 'VACATION', 'វិស្សមកាល / Vacation Period'
        HOLIDAY = 'HOLIDAY', 'ថ្ងៃបុណ្យ/ឈប់សម្រាក / Public Holiday'
        MAINTENANCE = 'MAINTENANCE', 'បិទប្រព័ន្ធថែទាំ / System Maintenance'

    restriction_type = models.CharField(
        max_length=20,
        choices=RestrictionType.choices,
        default=RestrictionType.HOLIDAY,
        verbose_name="ប្រភេទ / Type"
    )
    title = models.CharField(max_length=200, verbose_name="ឈ្មោះកម្មវិធី/មូលហេតុ / Title/Reason")
    start_date = models.DateField(verbose_name="ថ្ងៃចាប់ផ្តើម / Start Date")
    end_date = models.DateField(verbose_name="ថ្ងៃបញ្ចប់ / End Date")
    block_attendance = models.BooleanField(default=True, verbose_name="ចាក់សោមិនឱ្យចុះវត្តមាន / Block Attendance")
    description = models.TextField(blank=True, null=True, verbose_name="ពិពណ៌នាបន្ថែម / Description")
    is_active = models.BooleanField(default=True, verbose_name="បើកដំណើរការ / Active")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="អ្នកបង្កើត / Created By"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date', 'title']
        verbose_name = "ប្រតិទិនវិស្សមកាល និងថ្ងៃឈប់សម្រាក / Academic Calendar Restriction"
        verbose_name_plural = "ប្រតិទិនវិស្សមកាល និងថ្ងៃឈប់សម្រាកទាំងអស់ / Academic Calendar Restrictions"

    def __str__(self):
        return f"[{self.get_restriction_type_display()}] {self.title} ({self.start_date} ~ {self.end_date})"


class GradeEnrollmentOption(models.Model):
    class FieldType(models.TextChoices):
        TEXT = 'TEXT', 'ប្រអប់អត្ថបទខ្លី (Short Text)'
        TEXTAREA = 'TEXTAREA', 'ប្រអប់អត្ថបទវែង (Long Text / Notes)'
        NUMBER = 'NUMBER', 'ប្រអប់លេខ (Number)'
        DATE = 'DATE', 'កាលបរិច្ឆេទ (Date Picker)'
        TIME = 'TIME', 'ពេលវេលា/ម៉ោង (Time Picker)'
        DATETIME = 'DATETIME', 'កាលបរិច្ឆេទ & ម៉ោង (Date & Time)'
        PHONE = 'PHONE', 'លេខទូរស័ព្ទ (Phone Number)'
        EMAIL = 'EMAIL', 'អ៊ីមែល (Email Address)'
        SELECT = 'SELECT', 'បញ្ជីជ្រើសរើសទោល (Dropdown Select)'
        RADIO = 'RADIO', 'ជម្រើសមូលទោល (Radio Buttons)'
        MULTISELECT = 'MULTISELECT', 'បញ្ជីជ្រើសរើសច្រើន (Multi-Select Checkboxes)'
        CHECKBOX = 'CHECKBOX', 'ប្រអប់ធីក (Checkbox / Yes-No)'
        FILE = 'FILE', 'ឯកសារភ្ជាប់/រូបភាព (File/Document Upload)'
        SECTION = 'SECTION', 'ចំណងជើងផ្នែក / ខណ្ឌស៊ុម (Section Header / Frame Divider)'

    COL_WIDTH_CHOICES = [
        (12, 'ពេញជួរ (100% - col-12)'),
        (6, 'កន្លះជួរ (50% - col-6)'),
        (4, 'មួយភាគបី (33% - col-4)'),
        (3, 'មួយភាគបួន (25% - col-3)'),
    ]

    grade_level = models.ForeignKey(GradeLevel, on_delete=models.CASCADE, related_name='enrollment_options', verbose_name="កម្រិតថ្នាក់ / Grade Level")
    label = models.CharField(max_length=200, verbose_name="ឈ្មោះជម្រើស/សំណួរ (Label)")
    field_name = models.CharField(max_length=100, verbose_name="កូដសម្គាល់ (Field Key)", help_text="e.g. primary_school, diploma_grade, elective_subject")
    field_type = models.CharField(max_length=20, choices=FieldType.choices, default=FieldType.TEXT, verbose_name="ប្រភេទប្រអប់ (Field Type)")
    col_width = models.PositiveSmallIntegerField(default=6, choices=COL_WIDTH_CHOICES, verbose_name="ទំហំទទឹងប្រអប់ (Column Width)")
    choices = models.TextField(blank=True, null=True, verbose_name="ជម្រើស (Choices)", help_text="បំបែកដោយសញ្ញាក្បៀស (,) សម្រាប់ប្រភេទ Dropdown Select, Radio, Multi-Select (ឧ. និទ្ទេស A, និទ្ទេស B, និទ្ទេស C)")
    placeholder = models.CharField(max_length=200, blank=True, null=True, verbose_name="Placeholder/ណែនាំ")
    is_required = models.BooleanField(default=False, verbose_name="តម្រូវឱ្យបំពេញ (Required)")
    order = models.PositiveIntegerField(default=1, verbose_name="លំដាប់លំដោយ (Sort Order)")
    is_active = models.BooleanField(default=True, verbose_name="សកម្ម (Active)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['grade_level__order', 'order', 'id']
        verbose_name = "ជម្រើសចុះឈ្មោះតាមកម្រិតថ្នាក់ / Grade Enrollment Option"
        verbose_name_plural = "ជម្រើសចុះឈ្មោះតាមកម្រិតថ្នាក់ទាំងអស់ / Grade Enrollment Options"

    def get_choices_list(self):
        if not self.choices:
            return []
        return [c.strip() for c in self.choices.split(',') if c.strip()]

    def save(self, *args, **kwargs):
        if not self.field_name:
            import re
            cleaned = re.sub(r'[^a-zA-Z0-9]', '_', self.label.strip().lower())
            self.field_name = cleaned[:30] or f"opt_{GradeEnrollmentOption.objects.count() + 1}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.grade_level.name} - {self.label} ({self.get_field_type_display()})"


class TeacherDutyType(models.Model):
    """
    Customizable On-Duty / Shift Types for Teachers & Office Staff.
    Allows Admins to dynamically create, edit, customize colors/icons, or delete duty types.
    """
    code = models.CharField(max_length=50, unique=True, verbose_name="កូដសម្គាល់ / Code")
    name = models.CharField(max_length=150, verbose_name="ឈ្មោះភារកិច្ច / Name")
    icon = models.CharField(max_length=50, default='fa-clock', verbose_name="រូបតំណាង / FontAwesome Icon")
    color = models.CharField(max_length=20, default='#4f46e5', verbose_name="ពណ៌ / Color (Hex)")
    order = models.IntegerField(default=0, verbose_name="លំដាប់លំដោយ / Order")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = "ប្រភេទប្រចាំការ / Duty Type"
        verbose_name_plural = "ប្រភេទប្រចាំការទាំងអស់ / Duty Types"

    def __str__(self):
        return f"{self.name} ({self.code})"

    @classmethod
    def get_all_duty_types(cls):
        """
        Returns all configured duty types from database.
        Seeds the initial 5 default types if table is empty.
        """
        types = list(cls.objects.all().order_by('order', 'id'))
        if not types:
            initial = [
                {'code': 'OFFICE', 'name': 'ប្រចាំការការិយាល័យ', 'icon': 'fa-building-columns', 'color': '#4f46e5', 'order': 1},
                {'code': 'DISCIPLINE', 'name': 'សម្របសម្រួលវិន័យ', 'icon': 'fa-user-shield', 'color': '#0ea5e9', 'order': 2},
                {'code': 'LIBRARY', 'name': 'ប្រចាំការបណ្ណាល័យ', 'icon': 'fa-book-open-reader', 'color': '#10b981', 'order': 3},
                {'code': 'ADMIN', 'name': 'រដ្ឋបាល & លិខិតស្នាម', 'icon': 'fa-file-signature', 'color': '#f59e0b', 'order': 4},
                {'code': 'GENERAL', 'name': 'ប្រចាំការទូទៅ', 'icon': 'fa-clock', 'color': '#8b5cf6', 'order': 5},
            ]
            for item in initial:
                t = cls.objects.create(**item)
                types.append(t)
        return types


class TeacherDutySchedule(models.Model):
    """
    Teacher & Office Staff On-Duty / Duty Shift Schedule per Academic Year.
    For deficit teachers needing extra duty hours to fulfill quota & 100% duty for office staff.
    """
    class DutyType(models.TextChoices):
        OFFICE = 'OFFICE', 'ប្រចាំការការិយាល័យ / Office Duty'
        DISCIPLINE = 'DISCIPLINE', 'សម្របសម្រួលវិន័យ / Discipline & Order'
        LIBRARY = 'LIBRARY', 'ប្រចាំការបណ្ណាល័យ / Library Duty'
        ADMIN = 'ADMIN', 'រដ្ឋបាល & លិខិតស្នាម / Administration'
        GENERAL = 'GENERAL', 'ប្រចាំការទូទៅ / General Duty'

    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='duty_schedules', verbose_name="ឆ្នាំសិក្សា / Academic Year")
    teacher = models.ForeignKey('teachers.Teacher', on_delete=models.CASCADE, related_name='duty_schedules', verbose_name="គ្រូបង្រៀន/បុគ្គលិក / Teacher/Staff")
    day_of_week = models.IntegerField(choices=Timetable.DayOfWeek.choices, verbose_name="ថ្ងៃក្នុងសប្តាហ៍ / Day of Week")
    period_number = models.IntegerField(default=1, verbose_name="ម៉ោងទី / Period (1-8)")
    duty_type = models.CharField(max_length=50, default='OFFICE', verbose_name="ប្រភេទភារកិច្ច / Duty Type")
    is_auto_assigned = models.BooleanField(default=False, verbose_name="បែងចែកស្វ័យប្រវត្តិ / Auto Assigned")
    notes = models.CharField(max_length=200, blank=True, null=True, verbose_name="កំណត់ចំណាំ/ទីតាំង / Notes/Location")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['academic_year', 'day_of_week', 'period_number', 'teacher']
        unique_together = ('academic_year', 'teacher', 'day_of_week', 'period_number')
        verbose_name = "ម៉ោងប្រចាំការ / Duty Schedule"
        verbose_name_plural = "ម៉ោងប្រចាំការទាំងអស់ / Duty Schedules"

    def __str__(self):
        return f"{self.teacher.khmer_name} - {self.get_day_of_week_display()} ម៉ោងទី {self.period_number} ({self.duty_type})"



