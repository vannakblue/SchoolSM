from decimal import Decimal
from django.db.models import Q
from .models import ExamTerm, Grade, StudentTransferGrade, ExamTermSubjectSetting
from apps.academics.models import GradeLevelRule, Subject
from apps.students.models import Student


def get_effective_term_subjects(exam_term=None, classroom=None, grade_level=None, track=None, month=None, include_non_tested=False):
    """
    Resolves the effective list of subject rules for an exam term, month, classroom, or grade level:
    - Default behavior: All subjects assigned to class/grade are tested (is_tested=True).
    - Checks ExamTermSubjectSetting for overrides per classroom or per grade_level/track.
    - If include_non_tested=False: returns only rules where is_tested=True.
    - If include_non_tested=True: returns all rules, each annotated with `is_tested` and `custom_max_score`.
    """
    g_level = grade_level or (classroom.grade_level if classroom else None)
    t_track = track or (classroom.track if classroom else 'GENERAL')

    # 1. Base rules
    if classroom:
        base_rules = list(classroom.get_subject_rules())
    elif g_level:
        base_rules = list(GradeLevelRule.objects.filter(grade_level=g_level, track=t_track).select_related('subject').order_by('subject__order', 'id'))
    else:
        base_rules = [
            GradeLevelRule(grade_level=10, track='GENERAL', subject=s, max_score=Decimal('100.00'))
            for s in Subject.objects.all().order_by('order', 'id')
        ]

    # Fallback if no rules
    if not base_rules:
        base_rules = [
            GradeLevelRule(grade_level=g_level or 10, track=t_track, subject=s, max_score=Decimal('100.00'))
            for s in Subject.objects.all().order_by('order', 'id')
        ]

    # 2. Determine term & month filters
    t_month = month
    if not t_month and exam_term and exam_term.start_date:
        if hasattr(exam_term.start_date, 'month'):
            t_month = exam_term.start_date.month
        elif isinstance(exam_term.start_date, str):
            try:
                from datetime import datetime
                t_month = datetime.strptime(str(exam_term.start_date).split('T')[0], "%Y-%m-%d").month
            except Exception:
                pass

    # 3. Fetch overrides
    settings_qs = ExamTermSubjectSetting.objects.all()
    if exam_term:
        settings_qs = settings_qs.filter(Q(exam_term=exam_term) | (Q(month=t_month) if t_month else Q()))
    elif t_month:
        settings_qs = settings_qs.filter(month=t_month)

    class_settings = {}
    grade_track_settings = {}
    grade_settings = {}

    for st in settings_qs:
        if st.classroom_id:
            class_settings[(st.classroom_id, st.subject_id)] = st
        elif st.grade_level and st.track:
            grade_track_settings[(st.grade_level, st.track, st.subject_id)] = st
        elif st.grade_level:
            grade_settings[(st.grade_level, st.subject_id)] = st

    effective_rules = []
    for r in base_rules:
        # Match override: class first, then grade+track, then grade
        setting = None
        if classroom and (classroom.id, r.subject_id) in class_settings:
            setting = class_settings[(classroom.id, r.subject_id)]
        elif g_level and (g_level, t_track, r.subject_id) in grade_track_settings:
            setting = grade_track_settings[(g_level, t_track, r.subject_id)]
        elif g_level and (g_level, r.subject_id) in grade_settings:
            setting = grade_settings[(g_level, r.subject_id)]

        is_tested = setting.is_tested if setting is not None else True
        max_score = setting.custom_max_score if (setting is not None and setting.custom_max_score is not None) else r.max_score

        rule_obj = GradeLevelRule(
            id=r.id,
            grade_level=r.grade_level,
            track=r.track,
            subject=r.subject,
            max_score=max_score,
            weekly_hours=r.weekly_hours,
            order=r.order
        )
        rule_obj.is_tested = is_tested
        rule_obj.setting = setting

        if include_non_tested or is_tested:
            effective_rules.append(rule_obj)

    return effective_rules


class AcademicResultService:
    """
    Core Calculation Service for MoEYS Academic Results:
    1. Semester Average = (Monthly Average of semester terms + Semester Final Exam Score) / 2
    2. Annual Average = (Semester 1 Average + Semester 2 Average) / 2
    3. Handles Late-enrolled students pro-rated based on actual attended/available terms.
    4. Incorporates Transfer-in student grades from previous schools.
    """

    @staticmethod
    def get_letter_grade(percentage_val):
        """Standard Cambodian MoEYS Letter Grade Mapping (0 - 100%)"""
        val = float(percentage_val or 0)
        if val >= 90.0:
            return 'A', 'ល្អប្រសើរ (Outstanding)', 'passed'
        elif val >= 80.0:
            return 'B', 'ល្អណាស់ (Very Good)', 'passed'
        elif val >= 70.0:
            return 'C', 'ល្អ (Good)', 'passed'
        elif val >= 60.0:
            return 'D', 'ល្អបង្គួរ (Fair / Above Average)', 'passed'
        elif val >= 50.0:
            return 'E', 'មធ្យម (Pass / Average)', 'passed'
        else:
            return 'F', 'ធ្លាក់ (Fail)', 'failed'

    @staticmethod
    def compute_student_term_score(student, term, subject_rules):
        """
        Computes total score, max score, percentage, and letter grade for a student in a specific exam term.
        """
        grades = Grade.objects.filter(student=student, exam_term=term)
        if not grades.exists():
            return {
                'has_grades': False,
                'total_score': Decimal('0.00'),
                'total_max': Decimal('0.00'),
                'percentage': Decimal('0.00'),
                'average_10': Decimal('0.00'),
                'letter': '-',
                'subject_map': {}
            }

        grade_map = {g.subject_id: g for g in grades}
        total_score = Decimal('0.00')
        total_max = Decimal('0.00')

        # Filter active tested rules to exclude non-tested subjects from max score calculation
        active_rules = [r for r in subject_rules if getattr(r, 'is_tested', True)]

        subject_results = {}
        for rule in subject_rules:
            is_tested = getattr(rule, 'is_tested', True)
            g = grade_map.get(rule.subject_id)
            if not is_tested:
                subject_results[rule.subject_id] = {
                    'score': None,
                    'max_score': rule.max_score,
                    'letter': '-',
                    'is_tested': False,
                }
                continue

            if g:
                total_score += g.score
                total_max += rule.max_score
                subject_results[rule.subject_id] = {
                    'score': g.score,
                    'max_score': rule.max_score,
                    'letter': g.grade_letter or '-',
                    'is_tested': True,
                }
            else:
                total_max += rule.max_score
                subject_results[rule.subject_id] = {
                    'score': None,
                    'max_score': rule.max_score,
                    'letter': '-',
                    'is_tested': True,
                }

        percentage = round((total_score / total_max) * Decimal('100.0'), 2) if total_max > 0 else Decimal('0.00')
        average_10 = round(percentage / Decimal('10.0'), 2)
        letter, _, _ = AcademicResultService.get_letter_grade(percentage)

        return {
            'has_grades': True,
            'total_score': total_score,
            'total_max': total_max,
            'percentage': percentage,
            'average_10': average_10,
            'letter': letter,
            'subject_map': subject_results
        }

    @staticmethod
    def compute_semester_results(classroom, academic_year, semester):
        """
        Computes Semester 1 or Semester 2 results for all students in a classroom.
        Formula: Semester Average = (Monthly Average + Semester Exam Score) / 2
        """
        # 1. Fetch Subject Rules for this class (resolving tested subjects for semester)
        sem_type = ExamTerm.TermType.SEMESTER_1 if semester == 1 else ExamTerm.TermType.SEMESTER_2
        sem_exam_term = ExamTerm.objects.filter(
            academic_year=academic_year,
            semester=semester,
            term_type=sem_type
        ).first()

        subject_rules = get_effective_term_subjects(
            exam_term=sem_exam_term,
            classroom=classroom,
            include_non_tested=False
        )

        # 2. Find Monthly Terms belonging to this semester
        monthly_terms = list(ExamTerm.objects.filter(
            academic_year=academic_year,
            semester=semester,
            term_type=ExamTerm.TermType.MONTHLY,
            is_counted_in_semester=True
        ).order_by('start_date', 'id'))

        # 3. Find Semester Final Exam Term
        sem_type = ExamTerm.TermType.SEMESTER_1 if semester == 1 else ExamTerm.TermType.SEMESTER_2
        sem_exam_term = ExamTerm.objects.filter(
            academic_year=academic_year,
            semester=semester,
            term_type=sem_type
        ).first()

        # 4. Pull all students in classroom
        students = Student.objects.filter(classroom=classroom).order_by('student_id')

        # 5. Pull transfer records in advance
        transfer_map = {
            tg.student_id: tg
            for tg in StudentTransferGrade.objects.filter(
                academic_year=academic_year,
                semester=semester,
                student__classroom=classroom
            )
        }

        results = []

        for student in students:
            is_disqualified = getattr(student, 'is_disqualified_from_exams', False)
            transfer_record = transfer_map.get(student.id)

            if transfer_record:
                # Student transferred in with historical prior school grades
                m_avg = transfer_record.monthly_average
                ex_score = transfer_record.semester_exam_score
                sem_final = transfer_record.semester_final_average
                letter = transfer_record.letter_grade or AcademicResultService.get_letter_grade(sem_final)[0]
                letter_desc = AcademicResultService.get_letter_grade(sem_final)[1]
                passed = float(sem_final or 0) >= 50.0

                month_cols = [{'term': t, 'has_grades': False, 'percentage': None, 'score': None} for t in monthly_terms]

                results.append({
                    'student': student,
                    'is_transfer': True,
                    'transfer_school': transfer_record.prior_school_name or 'សាលាចាស់',
                    'transfer_record_id': transfer_record.id,
                    'is_disqualified': False,
                    'month_cols': month_cols,
                    'attended_months_count': len(monthly_terms),
                    'monthly_average': m_avg,
                    'semester_exam_score': ex_score,
                    'semester_final_average': sem_final,
                    'average_10': round(sem_final / Decimal('10.0'), 2) if sem_final else Decimal('0.00'),
                    'letter_grade': letter,
                    'letter_desc': letter_desc,
                    'passed': passed,
                    'has_record': True,
                    'notes': f"ផ្ទេរចូលពី {transfer_record.prior_school_name}" if transfer_record.prior_school_name else "ពិន្ទុសិស្សផ្ទេរចូល",
                })
            else:
                # Regular or Late-Enrolled Student Computation
                month_cols = []
                attended_percentages = []

                for t in monthly_terms:
                    t_res = AcademicResultService.compute_student_term_score(student, t, subject_rules)
                    if t_res['has_grades']:
                        attended_percentages.append(t_res['percentage'])
                        month_cols.append({
                            'term': t,
                            'has_grades': True,
                            'percentage': t_res['percentage'],
                            'score': t_res['total_score'],
                            'max': t_res['total_max']
                        })
                    else:
                        month_cols.append({
                            'term': t,
                            'has_grades': False,
                            'percentage': None,
                            'score': None,
                            'max': None
                        })

                # Compute Monthly Average over actual attended months
                if len(attended_percentages) > 0:
                    monthly_avg = round(sum(attended_percentages) / Decimal(str(len(attended_percentages))), 2)
                else:
                    monthly_avg = None

                # Compute Semester Exam Score
                exam_score = None
                if sem_exam_term:
                    e_res = AcademicResultService.compute_student_term_score(student, sem_exam_term, subject_rules)
                    if e_res['has_grades']:
                        exam_score = e_res['percentage']

                # Compute Final Semester Average
                if monthly_avg is not None and exam_score is not None:
                    sem_final = round((monthly_avg + exam_score) / Decimal('2.0'), 2)
                    has_record = True
                elif monthly_avg is not None:
                    # Enrolled for months, but missed final exam
                    sem_final = monthly_avg
                    has_record = True
                elif exam_score is not None:
                    # Transferred in late right before semester exam
                    sem_final = exam_score
                    has_record = True
                else:
                    sem_final = Decimal('0.00')
                    has_record = False

                if is_disqualified:
                    letter = 'F'
                    letter_desc = 'ដកសិទ្ធិប្រឡង (Disqualified)'
                    passed = False
                    notes = f"ដកសិទ្ធិ ({student.get_exam_suspension_reason_display()})"
                else:
                    letter, letter_desc, _ = AcademicResultService.get_letter_grade(sem_final)
                    passed = float(sem_final) >= 50.0
                    notes = ""
                    if len(attended_percentages) > 0 and len(attended_percentages) < len(monthly_terms):
                        notes = f"ចូលរៀនបាន {len(attended_percentages)}/{len(monthly_terms)} ខែ"

                results.append({
                    'student': student,
                    'is_transfer': False,
                    'transfer_school': None,
                    'transfer_record_id': None,
                    'is_disqualified': is_disqualified,
                    'month_cols': month_cols,
                    'attended_months_count': len(attended_percentages),
                    'monthly_average': monthly_avg,
                    'semester_exam_score': exam_score,
                    'semester_final_average': sem_final,
                    'average_10': round(sem_final / Decimal('10.0'), 2) if sem_final else Decimal('0.00'),
                    'letter_grade': letter,
                    'letter_desc': letter_desc,
                    'passed': passed,
                    'has_record': has_record,
                    'notes': notes,
                })

        # Rank students descending by semester_final_average
        results.sort(key=lambda x: (x['semester_final_average'] or Decimal('0.00')), reverse=True)
        for idx, item in enumerate(results, 1):
            item['rank'] = idx

        return {
            'classroom': classroom,
            'academic_year': academic_year,
            'semester': semester,
            'monthly_terms': monthly_terms,
            'sem_exam_term': sem_exam_term,
            'subject_rules': subject_rules,
            'students_data': results,
            'total_students': len(results),
            'passed_count': sum(1 for r in results if r['passed']),
            'failed_count': sum(1 for r in results if not r['passed']),
        }

    @staticmethod
    def compute_annual_results(classroom, academic_year):
        """
        Computes Annual Academic Results for all students in a classroom.
        Formula: Annual Average = (Semester 1 Average + Semester 2 Average) / 2
        """
        s1_res = AcademicResultService.compute_semester_results(classroom, academic_year, semester=1)
        s2_res = AcademicResultService.compute_semester_results(classroom, academic_year, semester=2)

        s1_map = {item['student'].id: item for item in s1_res['students_data']}
        s2_map = {item['student'].id: item for item in s2_res['students_data']}

        students = Student.objects.filter(classroom=classroom).order_by('student_id')
        annual_results = []

        for student in students:
            s1_data = s1_map.get(student.id)
            s2_data = s2_map.get(student.id)

            s1_avg = s1_data['semester_final_average'] if (s1_data and s1_data['has_record']) else None
            s2_avg = s2_data['semester_final_average'] if (s2_data and s2_data['has_record']) else None

            is_disqualified = getattr(student, 'is_disqualified_from_exams', False)
            is_transfer = (s1_data and s1_data.get('is_transfer')) or (s2_data and s2_data.get('is_transfer'))

            notes = []
            if s1_data and s1_data.get('is_transfer'):
                notes.append(f"ឆ.១ ផ្ទេរពី {s1_data.get('transfer_school')}")
            if s2_data and s2_data.get('is_transfer'):
                notes.append(f"ឆ.២ ផ្ទេរពី {s2_data.get('transfer_school')}")

            # Compute Annual Average
            if s1_avg is not None and s2_avg is not None:
                annual_avg = round((s1_avg + s2_avg) / Decimal('2.0'), 2)
                has_record = True
            elif s2_avg is not None:
                # Student enrolled in Semester 2 (no S1 record) -> based on actual S2 performance
                annual_avg = s2_avg
                has_record = True
                if not notes:
                    notes.append("ចូលរៀនឆមាសទី២")
            elif s1_avg is not None:
                annual_avg = s1_avg
                has_record = True
                if not notes:
                    notes.append("មានទិន្នន័យតែឆមាសទី១")
            else:
                annual_avg = Decimal('0.00')
                has_record = False

            if is_disqualified:
                letter = 'F'
                letter_desc = 'ដកសិទ្ធិប្រឡង (Disqualified)'
                passed = False
                promotion_status = 'មិនអនុញ្ញាតឱ្យឡើងថ្នាក់ (Disqualified)'
            else:
                letter, letter_desc, _ = AcademicResultService.get_letter_grade(annual_avg)
                passed = float(annual_avg) >= 50.0
                if passed:
                    promotion_status = 'អនុញ្ញាតឱ្យឡើងថ្នាក់ (Promoted)'
                else:
                    promotion_status = 'ត្រួតថ្នាក់ / ធ្លាក់ (Retained)'

            annual_results.append({
                'student': student,
                's1_data': s1_data,
                's2_data': s2_data,
                's1_average': s1_avg,
                's2_average': s2_avg,
                'annual_average': annual_avg,
                'average_10': round(annual_avg / Decimal('10.0'), 2) if annual_avg else Decimal('0.00'),
                'letter_grade': letter,
                'letter_desc': letter_desc,
                'passed': passed,
                'promotion_status': promotion_status,
                'is_transfer': is_transfer,
                'is_disqualified': is_disqualified,
                'has_record': has_record,
                'notes': " | ".join(notes) if notes else "",
            })

        # Rank students descending by annual_average
        annual_results.sort(key=lambda x: (x['annual_average'] or Decimal('0.00')), reverse=True)
        for idx, item in enumerate(annual_results, 1):
            item['rank'] = idx

        return {
            'classroom': classroom,
            'academic_year': academic_year,
            's1_summary': s1_res,
            's2_summary': s2_res,
            'students_data': annual_results,
            'total_students': len(annual_results),
            'passed_count': sum(1 for r in annual_results if r['passed']),
            'failed_count': sum(1 for r in annual_results if not r['passed']),
        }


def resolve_student_and_children_for_user(user, selected_student_id=None):
    """
    Resolves the primary student and all associated children (for parents) based on:
    1. Direct 1-to-1 link via user.student_profile
    2. Explicit ?student_id= query param (if user is parent/admin)
    3. Matching by student_id == username or phone
    4. Matching by student.phone == username or phone
    5. Matching by father_phone / mother_phone / emergency_phone == username or phone
    6. Matching by khmer_name / latin_name
    7. Fallback for Admin / Superuser
    Returns: (primary_student, children_list)
    """
    if not user or not user.is_authenticated:
        return None, []

    # Clean user phone and username
    u_phone = (getattr(user, 'phone', None) or '').replace(' ', '').replace('-', '').strip()
    u_name = (getattr(user, 'username', None) or '').replace(' ', '').replace('-', '').strip()
    u_khmer = (getattr(user, 'khmer_name', None) or '').strip()
    u_latin = (getattr(user, 'latin_name', None) or '').strip()

    q_filter = Q()
    if hasattr(user, 'student_profile') and user.student_profile:
        q_filter |= Q(id=user.student_profile.id)

    q_filter |= Q(user=user)

    if u_name:
        q_filter |= (
            Q(student_id__iexact=u_name) |
            Q(phone__iexact=u_name) |
            Q(father_phone__iexact=u_name) |
            Q(mother_phone__iexact=u_name) |
            Q(emergency_phone__iexact=u_name)
        )
    if u_phone:
        q_filter |= (
            Q(student_id__iexact=u_phone) |
            Q(phone__iexact=u_phone) |
            Q(father_phone__iexact=u_phone) |
            Q(mother_phone__iexact=u_phone) |
            Q(emergency_phone__iexact=u_phone)
        )
    if u_khmer:
        q_filter |= Q(khmer_name__iexact=u_khmer)
    if u_latin:
        q_filter |= Q(latin_name__iexact=u_latin)

    matching_students = list(
        Student.objects.filter(q_filter)
        .select_related('classroom', 'academic_year', 'user')
        .distinct()
        .order_by('id')
    )

    # If user is admin/superuser and no student found, fallback to active student
    if not matching_students and (getattr(user, 'is_superuser', False) or getattr(user, 'role', '') == 'ADMIN'):
        first_act = Student.objects.filter(status='ACTIVE').select_related('classroom', 'academic_year', 'user').first() or Student.objects.first()
        if first_act:
            matching_students = [first_act]

    # Select primary student
    primary_student = None
    if selected_student_id and str(selected_student_id).isdigit():
        target_id = int(selected_student_id)
        for s in matching_students:
            if s.id == target_id:
                primary_student = s
                break
        if not primary_student and (getattr(user, 'is_superuser', False) or getattr(user, 'role', '') == 'ADMIN'):
            primary_student = Student.objects.filter(id=target_id).select_related('classroom', 'academic_year', 'user').first()

    if not primary_student and matching_students:
        # Prefer student directly linked to user
        for s in matching_students:
            if s.user_id == user.id:
                primary_student = s
                break
        if not primary_student:
            primary_student = matching_students[0]

    # If student exists but user not linked, link user if user role is STUDENT
    if primary_student and not primary_student.user and getattr(user, 'role', '') == 'STUDENT':
        try:
            primary_student.user = user
            primary_student.save(update_fields=['user'])
        except Exception:
            pass

    return primary_student, matching_students


def get_student_exam_seating_data(student):
    """
    Computes examination seating, desk number, room number, schedule, and exclusion status
    for the specified student.
    Returns: list of dicts ordered by exam_date desc.
    """
    if not student:
        return []

    import re
    from datetime import date
    from apps.academics.models import AcademicYear
    from apps.examinations.models import StandardizedExam, ExamCandidate, ExamStudentExclusion

    grade_num = student.classroom.grade_level if (student.classroom and hasattr(student.classroom, 'grade_level')) else None
    if not grade_num and student.classroom:
        m = re.search(r'\d+', student.classroom.name)
        if m:
            grade_num = int(m.group())

    ay = student.classroom.academic_year if (student.classroom and student.classroom.academic_year) else None
    if not ay:
        ay = getattr(student, 'academic_year', None) or AcademicYear.objects.filter(is_active=True).first()

    exam_qs = (
        StandardizedExam.objects.all()
        .select_related('academic_year', 'exam_term')
        .prefetch_related('exam_subjects__subject', 'rooms')
    )
    if ay:
        exam_qs = exam_qs.filter(academic_year=ay)
    if grade_num:
        exam_qs = exam_qs.filter(grade_level=grade_num)

    exams = list(exam_qs.order_by('-exam_date')[:10])

    # Candidacies for this student
    cands = list(
        ExamCandidate.objects.filter(
            Q(student=student) |
            (Q(student_code__iexact=student.student_id) if student.student_id else Q())
        ).select_related('exam', 'room', 'exam__academic_year')
    )

    candidacies_map = {}
    for c in cands:
        # Link foreign key if missing
        if not c.student_id and student:
            try:
                c.student = student
                c.save(update_fields=['student'])
            except Exception:
                pass
        candidacies_map[c.exam_id] = c
        if c.exam and c.exam not in exams:
            exams.append(c.exam)

    # Exclusions
    exclusions_qs = ExamStudentExclusion.objects.filter(student=student, is_active=True).select_related('standardized_exam', 'exam_term')
    exclusions_by_exam = {}
    global_exclusion = None
    for ex_item in exclusions_qs:
        if ex_item.standardized_exam_id:
            exclusions_by_exam[ex_item.standardized_exam_id] = ex_item
        else:
            global_exclusion = ex_item

    exams.sort(key=lambda x: x.exam_date or date.min, reverse=True)

    exam_seating_info = []
    for ex in exams:
        cand = candidacies_map.get(ex.id)
        exclusion = exclusions_by_exam.get(ex.id) or global_exclusion
        is_excluded = False
        exclusion_reason = ""
        exclusion_reason_code = ""
        exclusion_notes = ""

        if exclusion:
            is_excluded = True
            exclusion_reason_code = exclusion.reason
            exclusion_reason = exclusion.get_reason_display()
            exclusion_notes = exclusion.notes or ""
        elif cand and cand.is_disciplinary_blocked:
            is_excluded = True
            exclusion_reason_code = "DISCIPLINARY"
            exclusion_reason = "បញ្ហាវិន័យ / ជាប់កិច្ចសន្យា (Disciplinary Hold)"
            exclusion_notes = cand.disciplinary_reason or ""

        if not is_excluded and getattr(student, 'is_exam_suspended', False):
            is_excluded = True
            exclusion_reason_code = getattr(student, 'exam_suspension_reason', '') or 'DISCIPLINARY'
            exclusion_reason = student.get_exam_suspension_reason_display() if hasattr(student, 'get_exam_suspension_reason_display') else "ដកសិទ្ធិប្រឡង"
            exclusion_notes = getattr(student, 'exam_suspension_notes', '') or ""

        has_room = bool(cand and cand.room and cand.desk_number)

        exam_subjects_list = [
            {
                'name': es.subject.name_kh,
                'max_score': float(es.max_score) if es.max_score is not None else 0,
                'exam_date': es.exam_date.strftime('%d-%m-%Y') if es.exam_date else (ex.exam_date.strftime('%d-%m-%Y') if ex.exam_date else ''),
                'start_time': es.start_time.strftime('%H:%M') if es.start_time else '',
                'end_time': es.end_time.strftime('%H:%M') if es.end_time else '',
                'session': es.get_session_display(),
            }
            for es in ex.exam_subjects.all().select_related('subject').order_by('order')
        ]

        desk_num = cand.desk_number if (cand and cand.desk_number) else None
        desk_display = f"តុលេខ {desk_num:02d}" if desk_num else "មិនទាន់មានលេខតុ"
        room_name = cand.room.room_name if (cand and cand.room) else "មិនទាន់កំណត់"
        building = cand.room.building if (cand and cand.room and cand.room.building) else "អគារ A"
        roll_num = cand.roll_number if (cand and cand.roll_number) else (student.student_id or "-")

        exam_seating_info.append({
            'exam': ex,
            'exam_id': ex.id,
            'name': ex.name,
            'exam_date': ex.exam_date,
            'grade_level': ex.grade_level,
            'session_name': ex.get_session_display(),
            'track_name': ex.get_track_display() if hasattr(ex, 'get_track_display') else '',
            'candidate': cand,
            'candidate_id': cand.id if cand else None,
            'has_room': has_room,
            'room_name': room_name,
            'room_number': cand.room.room_number if (cand and cand.room) else None,
            'building': building,
            'desk_number': desk_num,
            'desk_number_display': desk_display,
            'roll_number': roll_num,
            'is_excluded': is_excluded,
            'exclusion_reason_code': exclusion_reason_code,
            'exclusion_reason': exclusion_reason,
            'exclusion_notes': exclusion_notes,
            'admission_slip_url': f"/examinations/student/admission-slip/{cand.id}/" if cand else None,
            'subjects': exam_subjects_list,
            'total_subjects': len(exam_subjects_list),
        })

    return exam_seating_info

