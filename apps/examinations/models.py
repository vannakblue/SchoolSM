from django.db import models
from django.conf import settings
from decimal import Decimal
import random

class ExamTerm(models.Model):
    class TermType(models.TextChoices):
        MONTHLY = 'MONTHLY', 'ប្រឡងប្រចាំខែ / Monthly Exam'
        SEMESTER_1 = 'SEMESTER_1', 'ប្រឡងឆមាសទី១ / Semester 1 Final Exam'
        SEMESTER_2 = 'SEMESTER_2', 'ប្រឡងឆមាសទី២ / Semester 2 Final Exam'
        ANNUAL = 'ANNUAL', 'ប្រឡងចុងឆ្នាំ / Annual Final Exam'

    class ScoringMode(models.TextChoices):
        CLASSROOM = 'CLASSROOM', 'បញ្ចូលតាមថ្នាក់រៀន (Classroom-Based Matrix) - គ្រូប្រចាំមុខវិជ្ជា/បន្ទុកថ្នាក់'
        STANDARDIZED_ROOM = 'STANDARDIZED_ROOM', 'បញ្ចូលតាមបន្ទប់ប្រឡង (Room-Based Matrix 1-25 នាក់) - គណៈកម្មការប្រឡង'
        BOTH = 'BOTH', 'អនុញ្ញាតទាំងពីរ (Both Classroom & Room Entry)'

    class Semester(models.IntegerChoices):
        SEMESTER_1 = 1, 'ឆមាសទី១ / Semester 1'
        SEMESTER_2 = 2, 'ឆមាសទី២ / Semester 2'

    name = models.CharField(max_length=150, verbose_name="ឈ្មោះសម័យប្រឡង / Exam Term Name")
    academic_year = models.ForeignKey('academics.AcademicYear', on_delete=models.CASCADE, related_name='exam_terms', verbose_name="ឆ្នាំសិក្សា / Academic Year")
    semester = models.PositiveSmallIntegerField(choices=Semester.choices, default=Semester.SEMESTER_1, verbose_name="ឆមាស / Semester")
    term_type = models.CharField(max_length=30, choices=TermType.choices, default=TermType.MONTHLY, verbose_name="ប្រភេទការប្រឡង / Exam Type")
    scoring_mode = models.CharField(max_length=30, choices=ScoringMode.choices, default=ScoringMode.CLASSROOM, verbose_name="របៀបបញ្ចូលពិន្ទុ / Scoring Mode")
    is_counted_in_semester = models.BooleanField(default=True, verbose_name="រាប់ក្នុងមធ្យមភាគឆមាស / Count in Semester Average", help_text="កំណត់ថាតើសម័យប្រឡងនេះ ត្រូវរាប់បញ្ចូលក្នុងការគណនាមធ្យមភាគឆមាសដែរឬទេ")
    start_date = models.DateField(verbose_name="ថ្ងៃចាប់ផ្តើម / Start Date")
    end_date = models.DateField(verbose_name="ថ្ងៃបញ្ចប់ / End Date")
    is_published = models.BooleanField(default=True, verbose_name="ប្រកាសលទ្ធផលជាសាធារណៈ / Published")

    # Admin Grading Window & Deadline Controls
    grading_start_datetime = models.DateTimeField(null=True, blank=True, verbose_name="កាលបរិច្ឆេទ & ម៉ោងចាប់ផ្តើមបញ្ចូលពិន្ទុ / Grading Start Time")
    grading_end_datetime = models.DateTimeField(null=True, blank=True, verbose_name="កាលបរិច្ឆេទ & ម៉ោងបញ្ចប់បញ្ចូលពិន្ទុ / Grading Deadline")
    is_grading_locked = models.BooleanField(default=False, verbose_name="ចាក់សោការបញ្ចូលពិន្ទុ / Lock Grade Entry")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-start_date']
        verbose_name = "សម័យប្រឡង / Exam Term"
        verbose_name_plural = "សម័យប្រឡងទាំងអស់ / Exam Terms"

    def get_grading_status(self):
        """
        Returns (is_open: bool, status_code: str, message: str)
        status_code: 'OPEN', 'LOCKED', 'NOT_STARTED', 'EXPIRED'
        """
        from django.utils import timezone
        now = timezone.now()
        if self.is_grading_locked:
            return False, 'LOCKED', 'ការបញ្ចូលពិន្ទុត្រូវបានចាក់សោ (Locked by Admin)'
        if self.grading_start_datetime and now < self.grading_start_datetime:
            return False, 'NOT_STARTED', f'ការបញ្ចូលពិន្ទុនឹងបើកនៅថ្ងៃ {self.grading_start_datetime.strftime("%d/%m/%Y %H:%M")}'
        if self.grading_end_datetime and now > self.grading_end_datetime:
            return False, 'EXPIRED', f'ការបញ្ចូលពិន្ទុបានផុតកំណត់កាលពីថ្ងៃ {self.grading_end_datetime.strftime("%d/%m/%Y %H:%M")}'
        return True, 'OPEN', 'កំពុងបើកដំណើរការបញ្ចូលពិន្ទុ'

    def __str__(self):
        return f"{self.name} ({self.academic_year.name})"


class Grade(models.Model):
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='grades', verbose_name="សិស្ស / Student")
    subject = models.ForeignKey('academics.Subject', on_delete=models.CASCADE, related_name='subject_grades', verbose_name="មុខវិជ្ជា / Subject")
    exam_term = models.ForeignKey(ExamTerm, on_delete=models.CASCADE, related_name='term_grades', verbose_name="សម័យប្រឡង / Exam Term")
    classroom = models.ForeignKey('academics.Classroom', on_delete=models.CASCADE, related_name='classroom_grades', verbose_name="ថ្នាក់រៀន / Classroom")
    score = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="ពិន្ទុទទួលបាន / Score")
    max_score = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('100.00'), verbose_name="ពិន្ទុពេញ / Max Score")
    grade_letter = models.CharField(max_length=5, blank=True, null=True, verbose_name="និទ្ទេស / Letter Grade (A-F)")
    remarks = models.CharField(max_length=255, blank=True, null=True, verbose_name="មតិយោបល់ / Remarks")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['classroom', 'student', 'subject']
        unique_together = ('student', 'subject', 'exam_term')
        verbose_name = "ពិន្ទុ / Grade Entry"
        verbose_name_plural = "ពិន្ទុទាំងអស់ / Grade Entries"

    def save(self, *args, **kwargs):
        percentage = (float(self.score) / float(self.max_score)) * 100 if self.max_score and float(self.max_score) > 0 else 0
        if percentage >= 90:
            self.grade_letter = 'A'
        elif percentage >= 80:
            self.grade_letter = 'B'
        elif percentage >= 70:
            self.grade_letter = 'C'
        elif percentage >= 60:
            self.grade_letter = 'D'
        elif percentage >= 50:
            self.grade_letter = 'E'
        else:
            self.grade_letter = 'F'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student.khmer_name} - {self.subject.name_kh}: {self.score}/{self.max_score} ({self.grade_letter})"


class StudentTransferGrade(models.Model):
    """
    Historical / Transfer-in Semester or Monthly Scores from a student's prior school.
    Allows Admin or authorized users to input Semester 1 scores for students who transferred mid-year.
    """
    class Semester(models.IntegerChoices):
        SEMESTER_1 = 1, 'ឆមាសទី១ (Semester 1)'
        SEMESTER_2 = 2, 'ឆមាសទី២ (Semester 2)'

    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='transfer_grades', verbose_name="សិស្ស / Student")
    academic_year = models.ForeignKey('academics.AcademicYear', on_delete=models.CASCADE, related_name='transfer_grades', verbose_name="ឆ្នាំសិក្សា / Academic Year")
    semester = models.PositiveSmallIntegerField(choices=Semester.choices, default=Semester.SEMESTER_1, verbose_name="ឆមាស / Semester")
    prior_school_name = models.CharField(max_length=200, blank=True, null=True, verbose_name="ឈ្មោះសាលាចាស់ / Prior School Name")

    # Core scores from prior school
    monthly_average = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name="មធ្យមភាគប្រចាំខែពីសាលាចាស់ / Prior Monthly Average")
    semester_exam_score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name="ពិន្ទុប្រឡងឆមាសពីសាលាចាស់ / Prior Semester Exam Score")
    semester_final_average = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="មធ្យមភាគប្រចាំឆមាសពីសាលាចាស់ / Prior Semester Final Average")
    
    letter_grade = models.CharField(max_length=5, blank=True, null=True, verbose_name="និទ្ទេស / Letter Grade (A-F)")
    subject_scores = models.JSONField(default=dict, blank=True, verbose_name="ពិន្ទុតកមុខវិជ្ជា / Subject Breakdown")
    remarks = models.TextField(blank=True, null=True, verbose_name="កំណត់សម្គាល់ / Remarks")

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="បញ្ចូលដោយ / Created By")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['student', 'academic_year', 'semester']
        unique_together = ('student', 'academic_year', 'semester')
        verbose_name = "ពិន្ទុសិស្សផ្ទេរចូល / Transfer-in Grade"
        verbose_name_plural = "ពិន្ទុសិស្សផ្ទេរចូលទាំងអស់ / Transfer-in Grades"

    def save(self, *args, **kwargs):
        if self.monthly_average is not None and self.semester_exam_score is not None and not self.semester_final_average:
            self.semester_final_average = round((Decimal(str(self.monthly_average)) + Decimal(str(self.semester_exam_score))) / Decimal('2.0'), 2)
        
        if self.semester_final_average is not None and not self.letter_grade:
            val = float(self.semester_final_average)
            scale_100 = val if val > 10 else val * 10
            if scale_100 >= 90:
                self.letter_grade = 'A'
            elif scale_100 >= 80:
                self.letter_grade = 'B'
            elif scale_100 >= 70:
                self.letter_grade = 'C'
            elif scale_100 >= 60:
                self.letter_grade = 'D'
            elif scale_100 >= 50:
                self.letter_grade = 'E'
            else:
                self.letter_grade = 'F'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student.khmer_name} - ឆមាសទី{self.semester} ({self.academic_year.name}): {self.semester_final_average}"


# =========================================================================
# CAMBODIAN HIGH SCHOOL STANDARDIZED EXAMINATION SYSTEM (តេស្តស្តង់ដា)
# =========================================================================

class StandardizedExam(models.Model):
    class Track(models.TextChoices):
        ALL = 'ALL', 'គ្រប់ជំនាញទាំងអស់ (All Tracks)'
        GENERAL = 'GENERAL', 'កម្មវិធីទូទៅ (General Track)'
        SCIENCE = 'SCIENCE', 'ថ្នាក់វិទ្យាសាស្ត្រ (Science Track)'
        SOCIAL = 'SOCIAL', 'ថ្នាក់វិទ្យាសាស្ត្រសង្គម (Social Science Track)'

    class Session(models.TextChoices):
        MORNING = 'MORNING', 'វេនពេលព្រឹក (Morning Session: 07:00 - 11:00)'
        AFTERNOON = 'AFTERNOON', 'វេនពេលរសៀល (Afternoon Session: 13:00 - 17:00)'
        FULL_DAY = 'FULL_DAY', 'ពេញមួយថ្ងៃ (Full Day / Both Sessions)'

    name = models.CharField(max_length=200, verbose_name="ឈ្មោះសម័យប្រឡង / Exam Title")
    academic_year = models.ForeignKey('academics.AcademicYear', on_delete=models.CASCADE, related_name='standardized_exams', verbose_name="ឆ្នាំសិក្សា / Academic Year")
    grade_level = models.IntegerField(default=12, verbose_name="កម្រិតថ្នាក់ (7-12) / Grade Level")
    track = models.CharField(max_length=20, choices=Track.choices, default=Track.ALL, verbose_name="ជំនាញសិក្សា / Academic Track")
    session = models.CharField(max_length=20, choices=Session.choices, default=Session.MORNING, verbose_name="វេនប្រឡងចម្បង / Grade Exam Shift")
    exam_date = models.DateField(verbose_name="កាលបរិច្ឆេទប្រឡង / Exam Date")
    candidates_per_room = models.IntegerField(default=25, verbose_name="ចំនួនបេក្ខជនក្នុងមួយបន្ទប់ / Candidates Per Room")
    description = models.TextField(blank=True, null=True, verbose_name="ការពិពណ៌នា/សេចក្តីណែនាំ / Description")
    is_published = models.BooleanField(default=True, verbose_name="ប្រកាសលទ្ធផល / Published")

    # Admin Grading Window & Deadline Controls
    grading_start_datetime = models.DateTimeField(null=True, blank=True, verbose_name="កាលបរិច្ឆេទ & ម៉ោងចាប់ផ្តើមបញ្ចូលពិន្ទុ / Grading Start Time")
    grading_end_datetime = models.DateTimeField(null=True, blank=True, verbose_name="កាលបរិច្ឆេទ & ម៉ោងបញ្ចប់បញ្ចូលពិន្ទុ / Grading Deadline")
    is_grading_locked = models.BooleanField(default=False, verbose_name="ចាក់សោការបញ្ចូលពិន្ទុ / Lock Grade Entry")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-exam_date', '-id']
        verbose_name = "ការប្រឡងតេស្តស្តង់ដា / Standardized Exam"
        verbose_name_plural = "ការប្រឡងតេស្តស្តង់ដាទាំងអស់ / Standardized Exams"

    def get_grading_status(self):
        """
        Returns (is_open: bool, status_code: str, message: str)
        status_code: 'OPEN', 'LOCKED', 'NOT_STARTED', 'EXPIRED'
        """
        from django.utils import timezone
        now = timezone.now()
        if self.is_grading_locked:
            return False, 'LOCKED', 'ការបញ្ចូលពិន្ទុត្រូវបានចាក់សោ (Locked by Admin)'
        if self.grading_start_datetime and now < self.grading_start_datetime:
            return False, 'NOT_STARTED', f'ការបញ្ចូលពិន្ទុនឹងបើកនៅថ្ងៃ {self.grading_start_datetime.strftime("%d/%m/%Y %H:%M")}'
        if self.grading_end_datetime and now > self.grading_end_datetime:
            return False, 'EXPIRED', f'ការបញ្ចូលពិន្ទុបានផុតកំណត់កាលពីថ្ងៃ {self.grading_end_datetime.strftime("%d/%m/%Y %H:%M")}'
        return True, 'OPEN', 'កំពុងបើកដំណើរការបញ្ចូលពិន្ទុ'

    def __str__(self):
        return f"{self.name} (ថ្នាក់ទី {self.grade_level} - {self.academic_year.name})"

    @property
    def total_candidates(self):
        return self.candidates.count()

    @property
    def total_female_candidates(self):
        return self.candidates.filter(gender='F').count()

    @property
    def total_rooms(self):
        return self.rooms.count()

    def recalculate_all_ranks(self):
        """
        Recalculates total scores, weighted averages, letter grades (A-F),
        room ranks, and overall grade ranks across all candidates in this exam.
        """
        subjects = list(self.exam_subjects.all().select_related('subject'))
        total_max_score = sum(s.max_score for s in subjects) if subjects else Decimal('100.00')
        total_coefficients = sum(s.coefficient for s in subjects) if subjects else Decimal('1.00')

        candidates = list(self.candidates.all().prefetch_related('subject_scores__exam_subject'))
        for cand in candidates:
            cand_scores = {sc.exam_subject_id: sc for sc in cand.subject_scores.all()}
            cand_total = Decimal('0.00')
            weighted_sum = Decimal('0.00')
            has_any_score = False

            for s in subjects:
                sc_obj = cand_scores.get(s.id)
                if sc_obj and sc_obj.score is not None:
                    has_any_score = True
                    cand_total += sc_obj.score
                    weighted_sum += (sc_obj.score * s.coefficient)

            cand.total_score = cand_total
            if total_coefficients > 0 and has_any_score:
                cand.average_score = round(weighted_sum / total_coefficients, 2)
            else:
                cand.average_score = Decimal('0.00')

            # Grade Letter determination based on MoEYS High School Standard:
            percentage = (float(cand.total_score) / float(total_max_score)) * 100 if total_max_score > 0 and has_any_score else 0.0

            if not has_any_score:
                cand.grade_letter = '-'
            elif percentage >= 85.0:
                cand.grade_letter = 'A'
            elif percentage >= 75.0:
                cand.grade_letter = 'B'
            elif percentage >= 65.0:
                cand.grade_letter = 'C'
            elif percentage >= 55.0:
                cand.grade_letter = 'D'
            elif percentage >= 45.0:
                cand.grade_letter = 'E'
            else:
                cand.grade_letter = 'F'

            cand.save(update_fields=['total_score', 'average_score', 'grade_letter'])

        # Calculate Overall Rank (sorted by total_score desc, average_score desc, candidate_name_kh asc)
        ranked_overall = sorted(candidates, key=lambda c: (c.total_score or 0, c.average_score or 0), reverse=True)
        for idx, cand in enumerate(ranked_overall):
            if idx > 0:
                prev = ranked_overall[idx - 1]
                if cand.total_score == prev.total_score and cand.average_score == prev.average_score:
                    cand.rank_overall = prev.rank_overall
                else:
                    cand.rank_overall = idx + 1
            else:
                cand.rank_overall = 1
            cand.save(update_fields=['rank_overall'])

        # Calculate Room Rank for each room
        for room in self.rooms.all():
            room_candidates = sorted(
                [c for c in candidates if c.room_id == room.id],
                key=lambda c: (c.total_score or 0, c.average_score or 0),
                reverse=True
            )
            for idx, cand in enumerate(room_candidates):
                if idx > 0:
                    prev = room_candidates[idx - 1]
                    if cand.total_score == prev.total_score and cand.average_score == prev.average_score:
                        cand.rank_in_room = prev.rank_in_room
                    else:
                        cand.rank_in_room = idx + 1
                else:
                    cand.rank_in_room = 1
                cand.save(update_fields=['rank_in_room'])

    def generate_all_secret_codes(self, force_regenerate=False, include_month=False, month_code=None, use_two_random_letters=False, custom_grade_letter=None):
        """
        Generates unique standard secret codes based on:
        1. Subject abbreviation (e.g. M, R, D, K, P, C, B)
        2. Grade level code (7:S, 8:E, 9:N, 10:T, 11sc:Y, 11ss:I, 12sc:W, 12ss:Z)
        3. Month code (A..L, Q for early test) - Optional if ticked
        4. Random letter(s) (1 letter if rooms <= 26 and not 2-letter, 2 letters if rooms > 26 or 2-letter enabled)
        Guarantees 100% uniqueness per subject across all rooms.
        """
        import string
        rooms = list(self.rooms.all().order_by('room_number'))
        total_rooms = len(rooms)

        # 1. Determine Grade Letter
        if custom_grade_letter and str(custom_grade_letter).strip():
            gl_letter = custom_grade_letter.strip().upper()
        else:
            grade_defaults = {
                (7, 'GENERAL'): 'S', (7, 'ALL'): 'S',
                (8, 'GENERAL'): 'E', (8, 'ALL'): 'E',
                (9, 'GENERAL'): 'N', (9, 'ALL'): 'N',
                (10, 'GENERAL'): 'T', (10, 'ALL'): 'T',
                (11, 'SCIENCE'): 'Y', (11, 'SOCIAL'): 'I', (11, 'GENERAL'): 'Y', (11, 'ALL'): 'Y',
                (12, 'SCIENCE'): 'W', (12, 'SOCIAL'): 'Z', (12, 'GENERAL'): 'W', (12, 'ALL'): 'W',
            }
            gl_letter = grade_defaults.get((self.grade_level, self.track), 'G' + str(self.grade_level))

        # 2. Determine Month Code if enabled
        month_str = ""
        if include_month:
            if month_code and str(month_code).strip():
                month_str = str(month_code).strip().upper()
            elif self.exam_date:
                # Default mapping Jan=A, Feb=B, ... Dec=L
                month_idx = self.exam_date.month  # 1 to 12
                month_str = chr(64 + month_idx) if 1 <= month_idx <= 26 else 'M'

        # 3. Determine Random Letters Mode
        force_two_letters = use_two_random_letters or (total_rooms > 26)

        for room in rooms:
            if not room.secret_code or force_regenerate:
                room.secret_code = f"SEC-{room.room_number:02d}-{random.randint(1000, 9999)}"
                room.save(update_fields=['secret_code'])

        for subj in self.exam_subjects.all().select_related('subject'):
            # Subject prefix (e.g. M, R, D, K, P, C, B)
            sub_code = (subj.subject.code or subj.subject.name_en[:1] or 'S').strip().upper()

            # Pre-generate unique random letter suffix for each room in this subject
            if force_two_letters:
                # 2 letters (AA..ZZ)
                all_combos = [a + b for a in string.ascii_uppercase for b in string.ascii_uppercase]
                random.shuffle(all_combos)
                assigned_suffixes = all_combos[:total_rooms] if len(all_combos) >= total_rooms else [f"{i:02d}" for i in range(1, total_rooms + 1)]
            else:
                # 1 letter (A..Z)
                all_letters = list(string.ascii_uppercase)
                random.shuffle(all_letters)
                assigned_suffixes = all_letters[:total_rooms] if len(all_letters) >= total_rooms else [f"{i:02d}" for i in range(1, total_rooms + 1)]

            for idx, room in enumerate(rooms):
                code_obj = ExamRoomSubjectCode.objects.filter(exam_room=room, exam_subject=subj).first()
                if not code_obj or force_regenerate:
                    rand_suffix = assigned_suffixes[idx] if idx < len(assigned_suffixes) else f"R{idx+1}"
                    sec_str = f"{sub_code}{gl_letter}{month_str}{rand_suffix}"

                    # Guarantee uniqueness globally in this exam subject
                    while ExamRoomSubjectCode.objects.filter(secret_code=sec_str).exclude(pk=code_obj.pk if code_obj else None).exists():
                        extra_rand = ''.join(random.choices(string.ascii_uppercase, k=2))
                        sec_str = f"{sub_code}{gl_letter}{month_str}{extra_rand}"

                    if code_obj:
                        code_obj.secret_code = sec_str
                        code_obj.save(update_fields=['secret_code'])
                    else:
                        ExamRoomSubjectCode.objects.create(
                            exam_room=room,
                            exam_subject=subj,
                            secret_code=sec_str
                        )


class ExamRoom(models.Model):
    exam = models.ForeignKey(StandardizedExam, on_delete=models.CASCADE, related_name='rooms', verbose_name="សម័យប្រឡង / Exam")
    room_number = models.IntegerField(default=1, verbose_name="បន្ទប់លេខ / Room Number (1, 2, 3...)")
    room_name = models.CharField(max_length=100, verbose_name="ឈ្មោះបន្ទប់ / Room Display Name (e.g. បន្ទប់លេខ ០១)")
    building = models.CharField(max_length=100, blank=True, null=True, verbose_name="អគារ / Building")
    secret_code = models.CharField(max_length=50, blank=True, null=True, verbose_name="លេខកូដសម្ងាត់បន្ទប់ / Secret Room Code")
    invigilator_1 = models.CharField(max_length=150, blank=True, null=True, verbose_name="អនុរក្សទី១ / Chief Invigilator 1")
    invigilator_2 = models.CharField(max_length=150, blank=True, null=True, verbose_name="អនុរក្សទី២ / Invigilator 2")

    class Meta:
        ordering = ['room_number', 'id']
        unique_together = ('exam', 'room_number')
        verbose_name = "បន្ទប់ប្រឡង / Exam Room"
        verbose_name_plural = "បន្ទប់ប្រឡងទាំងអស់ / Exam Rooms"

    def save(self, *args, **kwargs):
        if not self.secret_code:
            self.secret_code = f"SEC-{self.room_number:02d}-{random.randint(1000, 9999)}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.room_name} ({self.exam.name})"

    @property
    def candidate_count(self):
        return self.candidates.count()

    @property
    def female_count(self):
        return self.candidates.filter(gender='F').count()


class ExamSubject(models.Model):
    class Session(models.TextChoices):
        MORNING = 'MORNING', 'ពេលព្រឹក (Morning Session)'
        AFTERNOON = 'AFTERNOON', 'ពេលរសៀល (Afternoon Session)'

    exam = models.ForeignKey(StandardizedExam, on_delete=models.CASCADE, related_name='exam_subjects', verbose_name="សម័យប្រឡង / Exam")
    subject = models.ForeignKey('academics.Subject', on_delete=models.CASCADE, related_name='standardized_exam_subjects', verbose_name="មុខវិជ្ជា / Subject")
    max_score = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('50.00'), verbose_name="ពិន្ទុពេញ / Max Score")
    coefficient = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal('1.00'), verbose_name="មេគុណ / Weight / Coefficient")
    exam_date = models.DateField(blank=True, null=True, verbose_name="ថ្ងៃប្រឡង / Subject Exam Date")
    session = models.CharField(max_length=20, choices=Session.choices, default=Session.MORNING, verbose_name="ពេលប្រឡង / Session")
    start_time = models.TimeField(blank=True, null=True, verbose_name="ម៉ោងចាប់ផ្តើម / Start Time")
    end_time = models.TimeField(blank=True, null=True, verbose_name="ម៉ោងបញ្ចប់ / End Time")
    order = models.IntegerField(default=1, verbose_name="លំដាប់មុខវិជ្ជា / Display Order")

    class Meta:
        ordering = ['order', 'id']
        unique_together = ('exam', 'subject')
        verbose_name = "មុខវិជ្ជាប្រឡងតេស្ត / Exam Subject"
        verbose_name_plural = "មុខវិជ្ជាប្រឡងតេស្តទាំងអស់ / Exam Subjects"

    def __str__(self):
        return f"{self.subject.name_kh} (ពេញ {self.max_score}, មេគុណ {self.coefficient}) - {self.exam.name}"


class ExamRoomSubjectCode(models.Model):
    exam_room = models.ForeignKey(ExamRoom, on_delete=models.CASCADE, related_name='subject_codes', verbose_name="បន្ទប់ប្រឡង / Exam Room")
    exam_subject = models.ForeignKey(ExamSubject, on_delete=models.CASCADE, related_name='room_codes', verbose_name="មុខវិជ្ជាប្រឡង / Exam Subject")
    secret_code = models.CharField(max_length=50, unique=True, verbose_name="លេខកូដសម្ងាត់កញ្ចប់ / Secret Code")
    is_graded = models.BooleanField(default=False, verbose_name="បានបញ្ចូលពិន្ទុរួច / Graded")
    graded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="បញ្ចូលដោយ / Graded By")
    graded_at = models.DateTimeField(null=True, blank=True, verbose_name="កាលបរិច្ឆេទបញ្ចូល / Graded At")

    class Meta:
        ordering = ['exam_room__room_number', 'exam_subject__order', 'id']
        unique_together = ('exam_room', 'exam_subject')
        verbose_name = "កូដសម្ងាត់កញ្ចប់វិញ្ញាសា / Envelope Secret Code"
        verbose_name_plural = "កូដសម្ងាត់កញ្ចប់វិញ្ញាសាទាំងអស់ / Envelope Secret Codes"

    def __str__(self):
        return f"{self.secret_code} ({self.exam_room.room_name} - {self.exam_subject.subject.name_kh})"



class ExamCandidate(models.Model):
    class Gender(models.TextChoices):
        MALE = 'M', 'ប្រុស / Male'
        FEMALE = 'F', 'ស្រី / Female'

    exam = models.ForeignKey(StandardizedExam, on_delete=models.CASCADE, related_name='candidates', verbose_name="សម័យប្រឡង / Exam")
    student = models.ForeignKey('students.Student', on_delete=models.SET_NULL, null=True, blank=True, related_name='standard_exam_candidacies', verbose_name="សិស្សក្នុងប្រព័ន្ធ / Student")
    room = models.ForeignKey(ExamRoom, on_delete=models.SET_NULL, null=True, blank=True, related_name='candidates', verbose_name="បន្ទប់ប្រឡង / Exam Room")
    roll_number = models.CharField(max_length=30, verbose_name="អត្តលេខបេក្ខជន / Candidate Roll No (e.g. 001)")
    desk_number = models.IntegerField(default=1, verbose_name="លេខតុក្នុងបន្ទប់ / Desk No (1-25)")
    candidate_name_kh = models.CharField(max_length=150, verbose_name="គោត្តនាម-នាម / Khmer Name")
    candidate_name_en = models.CharField(max_length=150, blank=True, null=True, verbose_name="ឈ្មោះឡាតាំង / Latin Name")
    gender = models.CharField(max_length=5, choices=Gender.choices, default=Gender.MALE, verbose_name="ភេទ / Gender")
    dob = models.DateField(blank=True, null=True, verbose_name="ថ្ងៃខែឆ្នាំកំណើត / Date of Birth")
    origin_class = models.CharField(max_length=100, blank=True, null=True, verbose_name="ថ្នាក់ដើម / Origin Class (e.g. 12A1)")
    student_code = models.CharField(max_length=50, blank=True, null=True, verbose_name="អត្តលេខសិស្ស / Student ID")
    
    # Computed Metrics
    total_score = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal('0.00'), verbose_name="ពិន្ទុសរុប / Total Score")
    average_score = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'), verbose_name="មធ្យមភាគ / Weighted Average")
    grade_letter = models.CharField(max_length=5, default='-', verbose_name="និទ្ទេស / Letter Grade (A-F)")
    rank_in_room = models.IntegerField(null=True, blank=True, verbose_name="ចំណាត់ថ្នាក់ក្នុងបន្ទប់ / Room Rank")
    rank_overall = models.IntegerField(null=True, blank=True, verbose_name="ចំណាត់ថ្នាក់ទូទាំងកម្រិត / Overall Rank")
    is_present = models.BooleanField(default=True, verbose_name="មានវត្តមានប្រឡង / Present")
    remarks = models.CharField(max_length=255, blank=True, null=True, verbose_name="ផ្សេងៗ / Remarks")

    # Disciplinary Hold / Contract Blocking
    is_disciplinary_blocked = models.BooleanField(default=False, verbose_name="ជាប់កិច្ចសន្យាវិន័យ / Disciplinary Hold")
    disciplinary_reason = models.CharField(max_length=255, blank=True, null=True, verbose_name="មូលហេតុវិន័យ / Disciplinary Reason")
    disciplinary_blocked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='disciplinary_blocked_candidates', verbose_name="ចាត់ចែងវិន័យដោយ / Blocked By")
    disciplinary_blocked_at = models.DateTimeField(null=True, blank=True, verbose_name="កាលបរិច្ឆេទដាក់វិន័យ / Blocked At")

    class Meta:
        ordering = ['room__room_number', 'desk_number', 'roll_number', 'id']
        verbose_name = "បេក្ខជនប្រឡង / Exam Candidate"
        verbose_name_plural = "បេក្ខជនប្រឡងទាំងអស់ / Exam Candidates"

    def __str__(self):
        return f"{self.roll_number} - {self.candidate_name_kh} ({self.gender}) [តុ: {self.desk_number:02d}, បន្ទប់: {self.room.room_name if self.room else 'គ្មាន'}]"


class CandidateSubjectScore(models.Model):
    candidate = models.ForeignKey(ExamCandidate, on_delete=models.CASCADE, related_name='subject_scores', verbose_name="បេក្ខជន / Candidate")
    exam_subject = models.ForeignKey(ExamSubject, on_delete=models.CASCADE, related_name='candidate_scores', verbose_name="មុខវិជ្ជាប្រឡង / Exam Subject")
    score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name="ពិន្ទុទទួលបាន / Score")
    is_absent = models.BooleanField(default=False, verbose_name="អវត្តមាន / Absent")
    signature_present = models.BooleanField(default=True, verbose_name="បានចុះហត្ថលេខា / Signed")
    notes = models.CharField(max_length=255, blank=True, null=True, verbose_name="ចំណាំ / Notes")

    # Grader Information & Audit Trail (ព័ត៌មានអ្នកបញ្ចូលពិន្ទុ)
    entered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='entered_candidate_scores', verbose_name="អ្នកបញ្ចូលពិន្ទុ / Entered By")
    entered_at = models.DateTimeField(null=True, blank=True, verbose_name="កាលបរិច្ឆេទ & ម៉ោងបញ្ចូល / Entered At")
    secret_code_used = models.CharField(max_length=50, blank=True, null=True, verbose_name="អក្សរសម្ងាត់ដែលបានប្រើ / Secret Code Used")
    last_modified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='modified_candidate_scores', verbose_name="អ្នកកែប្រែចុងក្រោយ / Last Modified By")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['exam_subject__order', 'id']
        unique_together = ('candidate', 'exam_subject')
        verbose_name = "ពិន្ទុមុខវិជ្ជាបេក្ខជន / Candidate Subject Score"
        verbose_name_plural = "ពិន្ទុមុខវិជ្ជាបេក្ខជនទាំងអស់ / Candidate Subject Scores"

    def __str__(self):
        return f"{self.candidate.candidate_name_kh} - {self.exam_subject.subject.name_kh}: {self.score}"


class ExamStudentExclusion(models.Model):
    """
    Tracks students excluded/disqualified from specific monthly exams or standardized exam terms.
    Students with active exclusions cannot sit exams and automatically receive score 0.00 unless overridden by Admin.
    """
    class Reason(models.TextChoices):
        DROPPED = 'DROPPED', 'ឈប់រៀន / Dropped Out'
        SUSPENDED = 'SUSPENDED', 'ផ្អាកការសិក្សា / Suspended'
        DISCIPLINARY = 'DISCIPLINARY', 'បញ្ហាវិន័យ / ជាប់កិច្ចសន្យា / Disciplinary'
        HEALTH = 'HEALTH', 'បញ្ហាសុខភាព / សម្រាកព្យាបាល / Health Issue'
        UNEXCUSED_ABSENCE = 'UNEXCUSED_ABSENCE', 'អវត្តមានឥតច្បាប់ / Unexcused Absence'
        FEE_OVERDUE = 'FEE_OVERDUE', 'ជំពាក់ប្រាក់កម្រៃ / Fee Overdue'
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

    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='exam_exclusions', verbose_name="សិស្ស / Student")
    academic_year = models.ForeignKey('academics.AcademicYear', on_delete=models.CASCADE, related_name='exam_exclusions', verbose_name="ឆ្នាំសិក្សា / Academic Year")
    exam_term = models.ForeignKey(ExamTerm, on_delete=models.CASCADE, null=True, blank=True, related_name='student_exclusions', verbose_name="សម័យប្រឡងប្រចាំខែ/ឆមាស / Exam Term")
    standardized_exam = models.ForeignKey(StandardizedExam, on_delete=models.CASCADE, null=True, blank=True, related_name='student_exclusions', verbose_name="សម័យប្រឡងតេស្តស្តង់ដា / Standardized Exam")
    month = models.PositiveSmallIntegerField(blank=True, null=True, choices=MONTH_CHOICES, verbose_name="ខែប្រឡង / Exam Month")
    reason = models.CharField(max_length=30, choices=Reason.choices, default=Reason.DROPPED, verbose_name="មូលហេតុលើកលែង / Exclusion Reason")
    notes = models.TextField(blank=True, null=True, verbose_name="កំណត់សម្គាល់បន្ថែម / Reason Notes")
    is_active = models.BooleanField(default=True, verbose_name="សកម្ម (កំពុងលើកលែង) / Is Active")
    excluded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='student_exclusions_given', verbose_name="កំណត់ដោយ / Excluded By")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', 'student__khmer_name']
        verbose_name = "ការលើកលែងសិស្សមិនឱ្យប្រឡង / Student Exam Exclusion"
        verbose_name_plural = "ការលើកលែងសិស្សមិនឱ្យប្រឡងទាំងអស់ / Student Exam Exclusions"

    def __str__(self):
        target = self.exam_term.name if self.exam_term else (self.standardized_exam.name if self.standardized_exam else f"ខែទី {self.month}")
        return f"{self.student.khmer_name} - លើកលែង: {target} ({self.get_reason_display()})"


# ==============================================================================
# TEACHER EXAM INVIGILATOR / PROCTOR SHIFT REQUEST SYSTEM (ប្រព័ន្ធសុំវេនអនុរក្ស)
# ==============================================================================

class ExamInvigilatorPlan(models.Model):
    """
    Master configuration plan for Exam Invigilators / Proctors shift requests.
    Admin controls:
    - is_active: MUST be True for the request feature to be visible or accessible to teachers.
    - allow_teacher_registration: True when teachers can register/cancel their own slots.
    """
    academic_year = models.ForeignKey('academics.AcademicYear', on_delete=models.CASCADE, related_name='invigilator_plans', verbose_name="ឆ្នាំសិក្សា / Academic Year")
    title = models.CharField(max_length=200, verbose_name="ចំណងជើងគម្រោង / Plan Title")
    description = models.TextField(blank=True, null=True, verbose_name="សេចក្តីណែនាំ / Description & Guidelines")
    start_date = models.DateField(verbose_name="ថ្ងៃចាប់ផ្តើមប្រឡង / Exam Start Date")
    end_date = models.DateField(verbose_name="ថ្ងៃបញ្ចប់ការប្រឡង / Exam End Date")
    
    is_active = models.BooleanField(default=False, verbose_name="បើកដំណើរការ (Active) / Is Active", help_text="បើក/បិទ ដំណើរការការស្នើសុំ។ លុះត្រាតែបើកទើបគ្រូអាចមើលឃើញ និងស្នើសុំបាន")
    allow_teacher_registration = models.BooleanField(default=True, verbose_name="អនុញ្ញាតឱ្យគ្រូចុះឈ្មោះ / Allow Teacher Registration")
    registration_deadline = models.DateTimeField(null=True, blank=True, verbose_name="ថ្ងៃផុតកំណត់ចុះឈ្មោះ / Registration Deadline")
    
    default_regular_quota = models.PositiveIntegerField(default=4, verbose_name="កូតាលំនាំដើមគ្រូធម្មតា / Regular Teacher Default Quota (4 វេន)")
    default_office_quota = models.PositiveIntegerField(default=5, verbose_name="កូតាលំនាំដើមគ្រូការិយាល័យ / Office Teacher Default Quota (5 វេន)")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date', '-created_at']
        verbose_name = "គម្រោងវេនអនុរក្សប្រឡង / Exam Invigilator Plan"
        verbose_name_plural = "គម្រោងវេនអនុរក្សប្រឡងទាំងអស់ / Exam Invigilator Plans"

    def __str__(self):
        return f"{self.title} ({self.academic_year.name}) - {'🟢 បើកដំណើរការ' if self.is_active else '🔴 បិទ'}"

    @property
    def total_slots_count(self):
        return self.shift_slots.count()

    @property
    def total_required_spots(self):
        return sum(s.max_invigilators for s in self.shift_slots.all())

    @property
    def total_filled_spots(self):
        return sum(s.registered_count for s in self.shift_slots.all())


class TeacherDutyGroup(models.Model):
    """
    Teacher groups (e.g. Regular Teachers = 4 shifts, Office Staff = 5 shifts, Management = 2 shifts)
    """
    plan = models.ForeignKey(ExamInvigilatorPlan, on_delete=models.CASCADE, related_name='duty_groups', verbose_name="គម្រោង / Plan")
    name = models.CharField(max_length=150, verbose_name="ឈ្មោះក្រុម / Group Name")
    required_shifts = models.PositiveIntegerField(default=4, verbose_name="ចំនួនវេនតម្រូវ / Required Shifts")
    description = models.CharField(max_length=255, blank=True, null=True, verbose_name="ការពិពណ៌នា / Description")
    order = models.PositiveIntegerField(default=1, verbose_name="លំដាប់ / Order")

    class Meta:
        ordering = ['order', 'id']
        verbose_name = "ក្រុមគ្រូ & កូតាវេន / Teacher Duty Group"
        verbose_name_plural = "ក្រុមគ្រូ & កូតាវេន / Teacher Duty Groups"

    def __str__(self):
        return f"{self.name} ({self.required_shifts} វេន)"


class TeacherDutyQuota(models.Model):
    """
    Specific quota assignment for an individual teacher for a specific plan.
    """
    plan = models.ForeignKey(ExamInvigilatorPlan, on_delete=models.CASCADE, related_name='teacher_quotas', verbose_name="គម្រោង / Plan")
    teacher = models.ForeignKey('teachers.Teacher', on_delete=models.CASCADE, related_name='exam_duty_quotas', verbose_name="គ្រូបង្រៀន / Teacher")
    duty_group = models.ForeignKey(TeacherDutyGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_quotas', verbose_name="ក្រុមគ្រូ / Duty Group")
    custom_required_shifts = models.PositiveIntegerField(null=True, blank=True, verbose_name="កូតាជាក់លាក់ (Override) / Custom Shifts")
    is_exempt = models.BooleanField(default=False, verbose_name="លើកលែងមិនបាច់ធ្វើអនុរក្ស / Exempt")
    exemption_reason = models.CharField(max_length=255, blank=True, null=True, verbose_name="មូលហេតុលើកលែង / Exemption Reason")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('plan', 'teacher')
        ordering = ['teacher__khmer_name']
        verbose_name = "កូតាវេនគ្រូបង្រៀន / Teacher Shift Quota"
        verbose_name_plural = "កូតាវេនគ្រូបង្រៀនទាំងអស់ / Teacher Shift Quotas"

    @property
    def effective_required_shifts(self):
        if self.is_exempt:
            return 0
        if self.custom_required_shifts is not None:
            return self.custom_required_shifts
        if self.duty_group:
            return self.duty_group.required_shifts
        return self.plan.default_regular_quota

    def __str__(self):
        return f"{self.teacher.khmer_name} - កូតា: {self.effective_required_shifts} វេន"


class ExamShiftSlot(models.Model):
    """
    An individual shift slot (e.g. Day 1 Morning 07:00-11:00).
    """
    class Session(models.TextChoices):
        MORNING = 'MORNING', '🌅 ពេលព្រឹក (Morning 07:00 - 11:00)'
        AFTERNOON = 'AFTERNOON', '⛅ ពេលរសៀល (Afternoon 13:00 - 17:00)'
        CUSTOM = 'CUSTOM', '🕒 ម៉ោងជាក់លាក់ (Custom Time)'

    plan = models.ForeignKey(ExamInvigilatorPlan, on_delete=models.CASCADE, related_name='shift_slots', verbose_name="គម្រោង / Plan")
    date = models.DateField(verbose_name="កាលបរិច្ឆេទ / Date")
    session = models.CharField(max_length=20, choices=Session.choices, default=Session.MORNING, verbose_name="វេន / Session")
    session_name = models.CharField(max_length=150, verbose_name="ឈ្មោះវេន / Slot Name")
    start_time = models.TimeField(default="07:00", verbose_name="ម៉ោងចាប់ផ្តើម / Start Time")
    end_time = models.TimeField(default="11:00", verbose_name="ម៉ោងបញ្ចប់ / End Time")
    max_invigilators = models.PositiveIntegerField(default=20, verbose_name="ចំនួនអនុរក្សអតិបរមា / Max Invigilators")
    notes = models.CharField(max_length=255, blank=True, null=True, verbose_name="កំណត់ចំណាំ / Notes")
    order = models.PositiveIntegerField(default=1, verbose_name="លំដាប់ / Order")

    class Meta:
        ordering = ['date', 'start_time', 'order']
        verbose_name = "វេនប្រឡង / Exam Shift Slot"
        verbose_name_plural = "វេនប្រឡងទាំងអស់ / Exam Shift Slots"

    @property
    def registered_count(self):
        return self.registrations.exclude(status='CANCELLED').count()

    @property
    def is_full(self):
        return self.registered_count >= self.max_invigilators

    @property
    def remaining_spots(self):
        return max(0, self.max_invigilators - self.registered_count)

    def __str__(self):
        return f"{self.date.strftime('%d/%m/%Y')} - {self.session_name} ({self.registered_count}/{self.max_invigilators})"


class TeacherShiftRegistration(models.Model):
    """
    A teacher's registration / assigned slot.
    """
    class Status(models.TextChoices):
        CONFIRMED = 'CONFIRMED', 'បានបញ្ជាក់ / Confirmed'
        ADMIN_ASSIGNED = 'ADMIN_ASSIGNED', 'ចាត់តាំងដោយ Admin / Admin Assigned'
        PENDING = 'PENDING', 'រង់ចាំការអនុម័ត / Pending'
        CANCELLED = 'CANCELLED', 'បានបោះបង់ / Cancelled'

    slot = models.ForeignKey(ExamShiftSlot, on_delete=models.CASCADE, related_name='registrations', verbose_name="វេនប្រឡង / Shift Slot")
    teacher = models.ForeignKey('teachers.Teacher', on_delete=models.CASCADE, related_name='exam_shift_registrations', verbose_name="គ្រូបង្រៀន / Teacher")
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.CONFIRMED, verbose_name="ស្ថានភាព / Status")
    room_assignment = models.CharField(max_length=100, blank=True, null=True, verbose_name="បន្ទប់ដែលត្រូវឈរ / Room Assignment")
    registered_at = models.DateTimeField(auto_now_add=True)
    notes = models.CharField(max_length=255, blank=True, null=True, verbose_name="កំណត់ចំណាំ / Notes")

    class Meta:
        unique_together = ('slot', 'teacher')
        ordering = ['slot__date', 'slot__start_time', 'teacher__khmer_name']
        verbose_name = "ការចុះឈ្មោះវេនអនុរក្ស / Teacher Shift Registration"
        verbose_name_plural = "ការចុះឈ្មោះវេនអនុរក្សទាំងអស់ / Teacher Shift Registrations"

    def __str__(self):
        return f"{self.teacher.khmer_name} -> {self.slot.session_name} ({self.slot.date})"


