from decimal import Decimal
from django.db.models import Q
from .models import ExamTerm, Grade, StudentTransferGrade, ExamTermSubjectSetting, StudentConductAssessment
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


# MoEYS Semester Valid Academic Months Mapping
# Semester 1: October to February (+ September if early start)
# Semester 2: March to July (+ August if needed)
SEMESTER_VALID_MONTHS = {
    1: [9, 10, 11, 12, 1, 2],
    2: [3, 4, 5, 6, 7, 8],
}


class SemesterMonthDescriptor(dict):
    """
    Descriptor representing a distinct academic month in a semester.
    Supports both attribute and dict-key access for seamless template compatibility.
    """
    def __init__(self, month_num, display_month, primary_term, term_ids, terms):
        super().__init__(
            month=month_num,
            display_month=display_month,
            name=display_month,
            primary_term=primary_term,
            term_ids=term_ids,
            terms=terms,
            id=primary_term.id if primary_term else None,
            start_date=primary_term.start_date if primary_term else None,
            end_date=primary_term.end_date if primary_term else None,
        )
        self.month = month_num
        self.display_month = display_month
        self.name = display_month
        self.primary_term = primary_term
        self.term_ids = term_ids
        self.terms = terms
        self.id = primary_term.id if primary_term else None
        self.start_date = primary_term.start_date if primary_term else None
        self.end_date = primary_term.end_date if primary_term else None

    def __str__(self):
        return self.display_month


def extract_term_month_info(term):
    """
    Extracts the academic month number (1-12) and Khmer display name from an ExamTerm.
    Checks term.name first for Khmer/English month names, then falls back to term.start_date.month.
    """
    if not term:
        return None, ""

    name_lower = (term.name or "").lower()

    month_patterns = [
        (10, 'តុលា', ['តុលា', 'october', 'oct']),
        (11, 'វិច្ឆិកា', ['វិច្ឆិកា', 'november', 'nov']),
        (12, 'ធ្នូ', ['ធ្នូ', 'december', 'dec']),
        (1, 'មករា', ['មករា', 'january', 'jan']),
        (2, 'កុម្ភៈ', ['កុម្ភៈ', 'កុម្ភះ', 'february', 'feb']),
        (3, 'មីនា', ['មីនា', 'march', 'mar']),
        (4, 'មេសា', ['មេសា', 'april', 'apr']),
        (5, 'ឧសភា', ['ឧសភា', 'may']),
        (6, 'មិថុនា', ['មិថុនា', 'june', 'jun']),
        (7, 'កក្កដា', ['កក្កដា', 'july', 'jul']),
        (8, 'សីហា', ['សីហា', 'august', 'aug']),
        (9, 'កញ្ញា', ['កញ្ញា', 'september', 'sep', 'sept']),
    ]

    for m_num, m_kh, aliases in month_patterns:
        for alias in aliases:
            if alias in name_lower:
                return m_num, m_kh

    # Fallback to start_date or end_date month
    ref_date = term.start_date or getattr(term, 'end_date', None)
    if ref_date:
        m_num = ref_date.month
        kh_names = {
            1: 'មករា', 2: 'កុម្ភៈ', 3: 'មីនា', 4: 'មេសា',
            5: 'ឧសភា', 6: 'មិថុនា', 7: 'កក្កដា', 8: 'សីហា',
            9: 'កញ្ញា', 10: 'តុលា', 11: 'វិច្ឆិកា', 12: 'ធ្នូ',
        }
        return m_num, kh_names.get(m_num, f"ខែ {m_num}")

    return None, ""


def resolve_semester_monthly_terms(academic_year, semester):
    """
    Returns the distinct monthly terms configured by admin that legitimately belong to the given semester.
    Guarantees:
    1. Only includes months that belong to that semester (MoEYS standard).
    2. Only includes months defined by admin in ExamTerm for this academic year and semester.
    3. De-duplicates multiple terms in the same month into a single month descriptor.
    4. Orders months chronologically according to Cambodian school year.
    """
    if not academic_year:
        return []

    valid_months = SEMESTER_VALID_MONTHS.get(semester, [])

    terms = list(ExamTerm.objects.filter(
        academic_year=academic_year,
        semester=semester,
        term_type=ExamTerm.TermType.MONTHLY,
        is_counted_in_semester=True
    ).order_by('start_date', 'id'))

    grouped_months = {}
    for term in terms:
        m_num, m_kh = extract_term_month_info(term)
        if m_num in valid_months:
            if m_num not in grouped_months:
                grouped_months[m_num] = {
                    'month': m_num,
                    'display_month': m_kh,
                    'primary_term': term,
                    'term_ids': [term.id],
                    'terms': [term],
                }
            else:
                grouped_months[m_num]['term_ids'].append(term.id)
                grouped_months[m_num]['terms'].append(term)

    result = []
    for m in valid_months:
        if m in grouped_months:
            m_data = grouped_months[m]
            # If multiple terms exist in the same month, prefer the one with recorded grades
            if len(m_data['terms']) > 1:
                term_with_grades = None
                for t in m_data['terms']:
                    if Grade.objects.filter(exam_term=t).exists():
                        term_with_grades = t
                        break
                if term_with_grades:
                    m_data['primary_term'] = term_with_grades

            descriptor = SemesterMonthDescriptor(
                month_num=m,
                display_month=m_data['display_month'],
                primary_term=m_data['primary_term'],
                term_ids=m_data['term_ids'],
                terms=m_data['terms']
            )
            result.append(descriptor)

    return result


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
        if hasattr(term, 'term_ids'):
            grades = Grade.objects.filter(student=student, exam_term_id__in=term.term_ids)
        elif isinstance(term, dict) and 'term_ids' in term:
            grades = Grade.objects.filter(student=student, exam_term_id__in=term['term_ids'])
        else:
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

        # 2. Find Monthly Terms belonging to this semester (distinct configured months)
        monthly_terms = resolve_semester_monthly_terms(academic_year, semester)

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

                month_cols = [{
                    'term': getattr(t, 'primary_term', t),
                    'name': getattr(t, 'display_month', getattr(t, 'name', '')),
                    'display_month': getattr(t, 'display_month', getattr(t, 'name', '')),
                    'has_grades': False,
                    'percentage': None,
                    'score': None,
                    'max': None,
                } for t in monthly_terms]

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
                    t_display = getattr(t, 'display_month', getattr(t, 'name', ''))
                    t_obj = getattr(t, 'primary_term', t)
                    if t_res['has_grades']:
                        attended_percentages.append(t_res['percentage'])
                        month_cols.append({
                            'term': t_obj,
                            'name': t_display,
                            'display_month': t_display,
                            'has_grades': True,
                            'percentage': t_res['percentage'],
                            'score': t_res['total_score'],
                            'max': t_res['total_max']
                        })
                    else:
                        month_cols.append({
                            'term': t_obj,
                            'name': t_display,
                            'display_month': t_display,
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
        .prefetch_related('subject_scores__exam_subject__subject')
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

        # Provisional Results Release Data
        is_prov_open = bool(ex.is_provisional_published or ex.is_published)
        cand_scores_list = []
        exam_subj_objs = list(ex.exam_subjects.all().select_related('subject').order_by('order', 'id'))
        total_max = sum(es.max_score for es in exam_subj_objs) if exam_subj_objs else Decimal('100.00')

        if is_prov_open and cand:
            scores_dict = {sc.exam_subject_id: sc for sc in cand.subject_scores.all()}
            for es in exam_subj_objs:
                sc_obj = scores_dict.get(es.id)
                sc_val = sc_obj.score if sc_obj else None
                is_abs = sc_obj.is_absent if sc_obj else False
                cand_scores_list.append({
                    'subject_name': es.subject.name_kh,
                    'score': sc_val,
                    'max_score': es.max_score,
                    'coefficient': es.coefficient,
                    'is_absent': is_abs,
                })

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

            # Provisional results fields
            'is_provisional_published': is_prov_open,
            'provisional_published_at': ex.provisional_published_at,
            'total_score': cand.total_score if (cand and is_prov_open) else None,
            'average_score': cand.average_score if (cand and is_prov_open) else None,
            'grade_letter': cand.grade_letter if (cand and is_prov_open) else '-',
            'rank_overall': cand.rank_overall if (cand and is_prov_open) else None,
            'rank_in_room': cand.rank_in_room if (cand and is_prov_open) else None,
            'total_max_score': total_max,
            'subject_scores': cand_scores_list,
            'provisional_slip_url': f"/examinations/student/provisional-slip/{cand.id}/" if (cand and is_prov_open) else None,
        })

    return exam_seating_info


def compute_classroom_subject_annual_ranks(classroom, academic_year):
    """
    Computes annual subject score, class rank, and letter grade for all students
    in a classroom across all tested subjects.
    Returns: dict[student_id][subject_id] = {'annual_score': Decimal, 'rank': int, 'letter': str}
    """
    if not classroom or not academic_year:
        return {}

    from decimal import Decimal
    from apps.examinations.models import ExamTerm, Grade
    from apps.students.models import Student

    subject_rules = get_effective_term_subjects(classroom=classroom, include_non_tested=False)
    if not subject_rules:
        subject_rules = get_effective_term_subjects(grade_level=classroom.grade_level, include_non_tested=False)
    if not subject_rules:
        return {}

    students = list(Student.objects.filter(classroom=classroom).order_by('student_id'))
    if not students:
        return {}

    s1_monthly_ids = list(ExamTerm.objects.filter(
        academic_year=academic_year, semester=1, term_type=ExamTerm.TermType.MONTHLY, is_counted_in_semester=True
    ).values_list('id', flat=True))
    s1_exam_id = ExamTerm.objects.filter(
        academic_year=academic_year, semester=1, term_type=ExamTerm.TermType.SEMESTER_1
    ).values_list('id', flat=True).first()

    s2_monthly_ids = list(ExamTerm.objects.filter(
        academic_year=academic_year, semester=2, term_type=ExamTerm.TermType.MONTHLY, is_counted_in_semester=True
    ).values_list('id', flat=True))
    s2_exam_id = ExamTerm.objects.filter(
        academic_year=academic_year, semester=2, term_type=ExamTerm.TermType.SEMESTER_2
    ).values_list('id', flat=True).first()

    all_term_ids = s1_monthly_ids + ([s1_exam_id] if s1_exam_id else []) + s2_monthly_ids + ([s2_exam_id] if s2_exam_id else [])
    grades_qs = Grade.objects.filter(Q(classroom=classroom) | Q(student__in=students), exam_term_id__in=all_term_ids)

    g_map = {}
    for g in grades_qs:
        g_map[(g.student_id, g.subject_id, g.exam_term_id)] = g.score

    student_subject_results = {s.id: {} for s in students}

    for rule in subject_rules:
        sub = rule.subject
        max_sc = rule.max_score or Decimal('100.00')
        scores_for_ranking = []

        for stu in students:
            # S1 monthly
            s1_m_scores = [g_map[(stu.id, sub.id, tid)] for tid in s1_monthly_ids if (stu.id, sub.id, tid) in g_map and g_map[(stu.id, sub.id, tid)] is not None]
            s1_m_avg = round(sum(s1_m_scores) / Decimal(str(len(s1_m_scores))), 2) if s1_m_scores else None
            s1_ex = g_map.get((stu.id, sub.id, s1_exam_id)) if s1_exam_id else None

            if s1_m_avg is not None and s1_ex is not None:
                s1_final = round((s1_m_avg + s1_ex) / Decimal('2.0'), 2)
            elif s1_ex is not None:
                s1_final = s1_ex
            elif s1_m_avg is not None:
                s1_final = s1_m_avg
            else:
                s1_final = None

            # S2 monthly
            s2_m_scores = [g_map[(stu.id, sub.id, tid)] for tid in s2_monthly_ids if (stu.id, sub.id, tid) in g_map and g_map[(stu.id, sub.id, tid)] is not None]
            s2_m_avg = round(sum(s2_m_scores) / Decimal(str(len(s2_m_scores))), 2) if s2_m_scores else None
            s2_ex = g_map.get((stu.id, sub.id, s2_exam_id)) if s2_exam_id else None

            if s2_m_avg is not None and s2_ex is not None:
                s2_final = round((s2_m_avg + s2_ex) / Decimal('2.0'), 2)
            elif s2_ex is not None:
                s2_final = s2_ex
            elif s2_m_avg is not None:
                s2_final = s2_m_avg
            else:
                s2_final = None

            if s1_final is not None and s2_final is not None:
                ann_sub = round((s1_final + s2_final) / Decimal('2.0'), 2)
            elif s2_final is not None:
                ann_sub = s2_final
            elif s1_final is not None:
                ann_sub = s1_final
            else:
                ann_sub = None

            letter = '-'
            if ann_sub is not None and max_sc > 0:
                pct = round((ann_sub / max_sc) * Decimal('100.0'), 2)
                letter = AcademicResultService.get_letter_grade(pct)[0]

            student_subject_results[stu.id][sub.id] = {
                'annual_score': ann_sub,
                'letter': letter,
                'max_score': max_sc,
            }
            if ann_sub is not None:
                scores_for_ranking.append((stu.id, ann_sub))

        scores_for_ranking.sort(key=lambda x: x[1], reverse=True)
        cur_rank = 1
        for idx, (s_id, sc_val) in enumerate(scores_for_ranking):
            if idx > 0 and sc_val < scores_for_ranking[idx - 1][1]:
                cur_rank = idx + 1
            student_subject_results[s_id][sub.id]['rank'] = cur_rank

    return student_subject_results


def get_student_cumulative_dossier_data(student, class_ranks_cache=None):
    """
    Constructs comprehensive multi-year Academic Dossier (សៀវភៅសិក្ខាគារិក) data
    for Grades 7 to 12 up to the student's actual current grade.
    Standardized to Cambodian Ministry of Education, Youth and Sport (MoEYS) Secondary & High School standards.
    Includes full annual subject breakdown matrix (Score, Class Rank, Letter Grade) for every grade level studied.
    """
    if not student:
        return None

    if class_ranks_cache is None:
        class_ranks_cache = {}

    from django.db.models import Q
    from apps.accounts.models import SchoolProfile
    from apps.academics.models import Classroom, Subject, GradeLevelRule
    from apps.students.models import StudentPromotionRecord
    from apps.attendance.models import StudentAttendance
    from apps.examinations.models import StudentTransferGrade, Grade

    school_profile = SchoolProfile.objects.first()
    default_school_name = (
        getattr(school_profile, 'name_kh', None) or 
        getattr(school_profile, 'school_name_kh', None) or 
        "វិទ្យាល័យសម្តេចហ៊ុនសែន"
    )

    current_cls = student.classroom
    current_grade = current_cls.grade_level if current_cls else 7
    current_ay = current_cls.academic_year if (current_cls and current_cls.academic_year) else getattr(student, 'academic_year', None)

    # 1. Historical promotion records
    promotions = list(StudentPromotionRecord.objects.filter(student=student).select_related(
        'from_academic_year', 'to_academic_year', 'from_classroom', 'to_classroom'
    ).order_by('created_at'))

    # 2. Transfer grades
    transfer_grades = list(StudentTransferGrade.objects.filter(student=student).select_related('academic_year'))
    transfers_by_year = {}
    for tg in transfer_grades:
        if tg.academic_year_id not in transfers_by_year:
            transfers_by_year[tg.academic_year_id] = {}
        transfers_by_year[tg.academic_year_id][tg.semester] = tg

    # 3. Collect historical grade classrooms
    past_classes_qs = Classroom.objects.filter(
        id__in=Grade.objects.filter(student=student).values_list('classroom_id', flat=True).distinct()
    ).select_related('academic_year', 'homeroom_teacher')
    classes_by_grade = {c.grade_level: c for c in past_classes_qs}

    for p in promotions:
        if p.from_classroom and p.from_classroom.grade_level:
            if p.from_classroom.grade_level not in classes_by_grade:
                classes_by_grade[p.from_classroom.grade_level] = p.from_classroom
        if p.to_classroom and p.to_classroom.grade_level:
            if p.to_classroom.grade_level not in classes_by_grade:
                classes_by_grade[p.to_classroom.grade_level] = p.to_classroom

    if current_cls and current_cls.grade_level:
        classes_by_grade[current_cls.grade_level] = current_cls

    # 4. Current year results computed via AcademicResultService
    current_annual_info = None
    if current_cls and current_ay:
        try:
            annual_res = AcademicResultService.compute_annual_results(current_cls, current_ay)
            for item in annual_res.get('students_data', []):
                if item['student'].id == student.id:
                    current_annual_info = item
                    break
        except Exception:
            current_annual_info = None

    # 5. Build record for Grades 7 to 12
    grade_records = []
    grade_ranks_map = {}

    for g_num in range(7, 13):
        is_current = (g_num == current_grade)
        is_past = (g_num < current_grade)
        is_future = (g_num > current_grade)

        cls_obj = classes_by_grade.get(g_num)
        hr_teacher_name = "-"
        ay_name = "-"
        cls_name = f"{g_num}A"
        school_name = default_school_name
        s1_avg = None
        s2_avg = None
        annual_avg = None
        grade_letter = "-"
        rank_val = "-"
        total_stus = cls_obj.total_students if cls_obj else "-"
        excused_abs = 0
        unexcused_abs = 0
        conduct_val = "ល្អ"
        decision_val = "-"
        remarks = ""

        # Subject ranks caching for this grade
        if cls_obj and cls_obj.academic_year:
            cache_key = (cls_obj.id, cls_obj.academic_year.id)
            if cache_key not in class_ranks_cache:
                class_ranks_cache[cache_key] = compute_classroom_subject_annual_ranks(cls_obj, cls_obj.academic_year)
            grade_ranks_map[g_num] = class_ranks_cache[cache_key].get(student.id, {})
        else:
            grade_ranks_map[g_num] = {}

        if cls_obj:
            cls_name = cls_obj.name
            ay_name = cls_obj.academic_year.name if cls_obj.academic_year else "-"
            hr_teacher_name = cls_obj.homeroom_teacher.khmer_name if cls_obj.homeroom_teacher else "-"

        if is_current and current_annual_info:
            s1_avg = current_annual_info.get('s1_average')
            s2_avg = current_annual_info.get('s2_average')
            annual_avg = current_annual_info.get('annual_average')
            grade_letter = current_annual_info.get('grade_letter', '-')
            rank_val = current_annual_info.get('rank', '-')
            total_stus = current_cls.total_students if current_cls else "-"
            decision_val = "កំពុងសិក្សា (Enrolled)"
            if current_annual_info.get('passed'):
                conduct_val = "ល្អណាស់"

            # Attendance for current year - supports both standard & legacy status values
            if current_ay:
                att_qs = StudentAttendance.objects.filter(student=student)
                if current_ay.start_date and current_ay.end_date:
                    att_qs = att_qs.filter(date__gte=current_ay.start_date, date__lte=current_ay.end_date)
                excused_abs = att_qs.filter(Q(status='PERMISSION') | Q(status='EXCUSED_LEAVE')).count()
                unexcused_abs = att_qs.filter(Q(status='ABSENT') | Q(status='UNEXCUSED_ABSENCE')).count()

        elif is_past:
            # Check promotion records
            p_rec = next((p for p in promotions if p.from_classroom and p.from_classroom.grade_level == g_num), None)
            if p_rec:
                ay_name = p_rec.from_academic_year.name if p_rec.from_academic_year else ay_name
                cls_name = p_rec.from_classroom.name if p_rec.from_classroom else cls_name
                hr_teacher_name = p_rec.from_classroom.homeroom_teacher.khmer_name if (p_rec.from_classroom and p_rec.from_classroom.homeroom_teacher) else hr_teacher_name
                decision_val = p_rec.get_action_display()
                remarks = p_rec.get_standard_reason_display()

            # Past grades calculation if class object exists
            if cls_obj and cls_obj.academic_year and cls_obj.id != getattr(current_cls, 'id', None):
                try:
                    p_res = AcademicResultService.compute_annual_results(cls_obj, cls_obj.academic_year)
                    for item in p_res.get('students_data', []):
                        if item['student'].id == student.id:
                            s1_avg = item.get('s1_average')
                            s2_avg = item.get('s2_average')
                            annual_avg = item.get('annual_average')
                            grade_letter = item.get('grade_letter', '-')
                            rank_val = item.get('rank', '-')
                            if item.get('passed'):
                                decision_val = "អនុញ្ញាតឱ្យឡើងថ្នាក់ (Promoted)"
                            break
                except Exception:
                    pass

            if not decision_val or decision_val == "-":
                decision_val = "បានបញ្ចប់ការសិក្សាថ្នាក់នេះ"

        elif is_future:
            decision_val = "មិនទាន់រៀនដល់"
            ay_name = "-"
            cls_name = "-"
            hr_teacher_name = "-"

        grade_records.append({
            'grade_level': g_num,
            'grade_label': f"ថ្នាក់ទី {g_num}",
            'is_current': is_current,
            'is_past': is_past,
            'is_future': is_future,
            'school_name': school_name,
            'academic_year_name': ay_name,
            'classroom_name': cls_name,
            'homeroom_teacher_name': hr_teacher_name,
            'semester_1_average': s1_avg,
            'semester_2_average': s2_avg,
            'annual_average': annual_avg,
            'grade_letter': grade_letter,
            'rank': rank_val,
            'total_students': total_stus,
            'conduct': conduct_val,
            'excused_absence': excused_abs,
            'unexcused_absence': unexcused_abs,
            'total_absence': excused_abs + unexcused_abs,
            'decision': decision_val,
            'remarks': remarks,
        })

    # 6. Multi-Year Subject Breakdown Matrix (ថ្នាក់ទី ៧ ដល់ ទី ១២)
    relevant_subject_ids = set(
        GradeLevelRule.objects.filter(grade_level__gte=7, grade_level__lte=12).values_list('subject_id', flat=True)
    )
    student_grade_subject_ids = set(
        Grade.objects.filter(student=student).values_list('subject_id', flat=True)
    )
    all_sub_ids = relevant_subject_ids.union(student_grade_subject_ids)

    if all_sub_ids:
        all_subjects_qs = list(Subject.objects.filter(id__in=all_sub_ids).order_by('order', 'id'))
    else:
        all_subjects_qs = list(Subject.objects.all().order_by('order', 'id'))

    cumulative_subjects = []
    for sub in all_subjects_qs:
        grade_cells = []
        has_any_score = False

        for g_num in range(7, 13):
            is_current = (g_num == current_grade)
            is_past = (g_num < current_grade)
            is_future = (g_num > current_grade)

            sub_rank_info = grade_ranks_map.get(g_num, {}).get(sub.id)
            if sub_rank_info and sub_rank_info.get('annual_score') is not None:
                has_any_score = True
                grade_cells.append({
                    'grade_level': g_num,
                    'annual_score': sub_rank_info['annual_score'],
                    'rank': sub_rank_info.get('rank', '-'),
                    'letter': sub_rank_info.get('letter', '-'),
                    'max_score': sub_rank_info.get('max_score', Decimal('100.00')),
                    'is_current': is_current,
                    'is_past': is_past,
                    'is_future': is_future,
                    'has_data': True,
                })
            else:
                grade_cells.append({
                    'grade_level': g_num,
                    'annual_score': None,
                    'rank': '-',
                    'letter': '-',
                    'max_score': None,
                    'is_current': is_current,
                    'is_past': is_past,
                    'is_future': is_future,
                    'has_data': False,
                })

        cumulative_subjects.append({
            'subject': sub,
            'subject_name': sub.name_kh,
            'subject_code': sub.code,
            'grade_cells': grade_cells,
            'has_any_score': has_any_score,
        })

    active_rules_sub_ids = set(GradeLevelRule.objects.filter(grade_level__lte=max(current_grade, 7), grade_level__gte=7).values_list('subject_id', flat=True))
    filtered_cumulative_subjects = [
        s for s in cumulative_subjects
        if s['has_any_score'] or s['subject'].id in active_rules_sub_ids
    ]
    if filtered_cumulative_subjects:
        cumulative_subjects = filtered_cumulative_subjects

    # Grade totals row for footer
    cumulative_grade_totals = []
    for g_idx, g_num in enumerate(range(7, 13)):
        rec = next((r for r in grade_records if r['grade_level'] == g_num), None)
        scores = [
            row['grade_cells'][g_idx]['annual_score']
            for row in cumulative_subjects
            if row['grade_cells'][g_idx]['annual_score'] is not None
        ]
        tot_sc = round(sum(scores), 2) if scores else None
        ann_avg = rec['annual_average'] if rec else None
        rk_val = rec['rank'] if rec else '-'
        lt_val = rec['grade_letter'] if rec else '-'
        cumulative_grade_totals.append({
            'grade_level': g_num,
            'total_score': tot_sc,
            'annual_average': ann_avg,
            'rank': rk_val,
            'letter': lt_val,
            'is_current': (g_num == current_grade),
            'is_past': (g_num < current_grade),
            'is_future': (g_num > current_grade),
            'has_data': (tot_sc is not None or ann_avg is not None),
        })

    # Health & Physical Record (កាយសម្បទា និងសុខភាព)
    enr_data = getattr(student, 'enrollment_data', {}) or {}
    health_info = {
        'height': enr_data.get('height') or getattr(student, 'height', None) or '..........',
        'weight': enr_data.get('weight') or getattr(student, 'weight', None) or '..........',
        'blood_type': enr_data.get('blood_type') or getattr(student, 'blood_type', None) or '..........',
        'disabilities': enr_data.get('disabilities') or 'គ្មាន',
        'chronic_illness': enr_data.get('chronic_illness') or 'គ្មាន',
        'general_health': enr_data.get('general_health') or 'មាំមួនល្អ',
    }

    # Primary School History (ប្រវត្តិបឋមសិក្សា)
    primary_info = {
        'previous_school': student.previous_school or default_school_name,
        'certificate_year': enr_data.get('primary_cert_year') or '................',
        'certificate_no': enr_data.get('primary_cert_no') or '................',
    }

    # National Examination Records (ការប្រឡងថ្នាក់ជាតិ៖ ឌីប្លូម & បាក់ឌុប)
    diploma_info = {
        'session_year': enr_data.get('diploma_session_year') or (current_ay.name if current_grade > 9 and current_ay else '................'),
        'exam_center': enr_data.get('diploma_center') or default_school_name,
        'desk_number': enr_data.get('diploma_desk_no') or '............',
        'room_number': enr_data.get('diploma_room_no') or '............',
        'result': enr_data.get('diploma_result') or ('ជាប់សញ្ញាបត្របឋមភូមិ' if current_grade > 9 else 'មិនទាន់ប្រឡង'),
        'letter_grade': enr_data.get('diploma_grade') or ('ល្អបង្គួរ (C)' if current_grade > 9 else '-'),
    }

    bac2_info = {
        'session_year': enr_data.get('bac2_session_year') or '................',
        'exam_center': enr_data.get('bac2_center') or default_school_name,
        'desk_number': enr_data.get('bac2_desk_no') or '............',
        'room_number': enr_data.get('bac2_room_no') or '............',
        'result': enr_data.get('bac2_result') or ('ជាប់បាក់ឌុប' if current_grade > 12 else 'មិនទាន់ប្រឡង'),
        'letter_grade': enr_data.get('bac2_grade') or '-',
    }

    return {
        'student': student,
        'school_profile': school_profile,
        'school_name': default_school_name,
        'current_grade': current_grade,
        'current_classroom': current_cls,
        'current_academic_year': current_ay,
        'grade_records': grade_records,
        'grade_numbers': list(range(7, 13)),
        'cumulative_subjects': cumulative_subjects,
        'cumulative_grade_totals': cumulative_grade_totals,
        'health_info': health_info,
        'primary_info': primary_info,
        'diploma_info': diploma_info,
        'bac2_info': bac2_info,
    }


def get_student_study_tracking_book_data(student, academic_year=None, context_cache=None):
    """
    Constructs comprehensive Individual Student Study Tracking Book data
    (សៀវភៅតាមដានការសិក្សារបស់សិស្សម្នាក់ / Carnet Scolaire Individuel)
    standardized to Cambodian Ministry of Education, Youth and Sport (MoEYS) specifications.
    """
    if not student:
        return None

    if context_cache is None:
        context_cache = {}

    from django.db.models import Q
    from apps.accounts.models import SchoolProfile
    from apps.academics.models import Classroom, AcademicYear
    from apps.attendance.models import StudentAttendance
    from apps.examinations.models import ExamTerm, Grade

    if 'school_profile' not in context_cache:
        context_cache['school_profile'] = SchoolProfile.objects.first()
    school_profile = context_cache['school_profile']

    default_school_name = (
        getattr(school_profile, 'name_kh', None) or 
        getattr(school_profile, 'school_name_kh', None) or 
        "វិទ្យាល័យសម្តេចហ៊ុនសែន"
    )

    classroom = student.classroom
    grade_level = classroom.grade_level if classroom else 7
    ay = academic_year or (classroom.academic_year if classroom else student.academic_year)
    if not ay:
        if 'default_ay' not in context_cache:
            context_cache['default_ay'] = AcademicYear.objects.filter(is_current=True).first() or AcademicYear.objects.first()
        ay = context_cache['default_ay']

    homeroom_teacher = classroom.homeroom_teacher if classroom else None

    # 1. Exam Terms Resolution (Distinct months defined by admin for each semester)
    s1_monthly_terms_key = ('s1_monthly_terms', ay.id if ay else None)
    if s1_monthly_terms_key not in context_cache:
        context_cache[s1_monthly_terms_key] = resolve_semester_monthly_terms(ay, semester=1) if ay else []
    s1_monthly_terms = context_cache[s1_monthly_terms_key]

    s1_exam_term_key = ('s1_exam_term', ay.id if ay else None)
    if s1_exam_term_key not in context_cache:
        context_cache[s1_exam_term_key] = ExamTerm.objects.filter(
            academic_year=ay,
            semester=1,
            term_type=ExamTerm.TermType.SEMESTER_1
        ).first() if ay else None
    s1_exam_term = context_cache[s1_exam_term_key]

    s2_monthly_terms_key = ('s2_monthly_terms', ay.id if ay else None)
    if s2_monthly_terms_key not in context_cache:
        context_cache[s2_monthly_terms_key] = resolve_semester_monthly_terms(ay, semester=2) if ay else []
    s2_monthly_terms = context_cache[s2_monthly_terms_key]

    s2_exam_term_key = ('s2_exam_term', ay.id if ay else None)
    if s2_exam_term_key not in context_cache:
        context_cache[s2_exam_term_key] = ExamTerm.objects.filter(
            academic_year=ay,
            semester=2,
            term_type=ExamTerm.TermType.SEMESTER_2
        ).first() if ay else None
    s2_exam_term = context_cache[s2_exam_term_key]

    # 2. Subject Rules & Grade Mapping (Guarantee all subjects in this classroom/grade are included)
    classroom_subjects_key = ('classroom_subjects', classroom.id if classroom else None, grade_level)
    if classroom_subjects_key not in context_cache:
        c_subs = []
        if classroom:
            assigned_subs = list(classroom.assigned_subjects.select_related('subject').order_by('subject__order', 'id'))
            if assigned_subs:
                rule_map = {r.subject_id: r for r in GradeLevelRule.objects.filter(grade_level=grade_level, track=classroom.track).select_related('subject')}
                for cs in assigned_subs:
                    rule = rule_map.get(cs.subject_id) or GradeLevelRule(
                        grade_level=grade_level, track=classroom.track, subject=cs.subject, max_score=Decimal('100.00')
                    )
                    c_subs.append(rule)
            else:
                c_subs = list(GradeLevelRule.objects.filter(grade_level=grade_level, track=classroom.track).select_related('subject').order_by('subject__order', 'id'))

        if not c_subs:
            c_subs = list(GradeLevelRule.objects.filter(grade_level=grade_level).select_related('subject').order_by('subject__order', 'id'))
        context_cache[classroom_subjects_key] = c_subs

    classroom_subjects = list(context_cache[classroom_subjects_key])

    # 2. Subject Rules & Grade Mapping (Guarantee all subjects in this classroom/grade are included)
    grades_cache_key = ('classroom_grades', classroom.id if classroom else None, ay.id if ay else None)
    if grades_cache_key not in context_cache:
        if classroom and ay:
            from collections import defaultdict
            cg_map = defaultdict(dict)
            all_grades = Grade.objects.filter(student__classroom=classroom, exam_term__academic_year=ay).values_list('student_id', 'subject_id', 'exam_term_id', 'score')
            for stu_id, sub_id, et_id, sc in all_grades:
                cg_map[stu_id][(sub_id, et_id)] = sc
            context_cache[grades_cache_key] = cg_map
        else:
            context_cache[grades_cache_key] = None

    cg_map = context_cache.get(grades_cache_key)
    if cg_map is not None:
        grade_map = cg_map.get(student.id, {})
    else:
        grades_qs = Grade.objects.filter(student=student)
        if ay:
            grades_qs = grades_qs.filter(exam_term__academic_year=ay)
        grade_map = {(g.subject_id, g.exam_term_id): g.score for g in grades_qs}

    # Also include any subjects that have recorded grades for this student
    existing_sub_ids = {r.subject_id for r in classroom_subjects}
    extra_grade_sub_ids = {sub_id for (sub_id, et_id) in grade_map.keys()} - existing_sub_ids
    if extra_grade_sub_ids:
        extra_subs = Subject.objects.filter(id__in=extra_grade_sub_ids).order_by('order', 'id')
        for es in extra_subs:
            classroom_subjects.append(GradeLevelRule(
                grade_level=grade_level, track=classroom.track if classroom else 'GENERAL', subject=es, max_score=Decimal('100.00')
            ))

    subject_rules = classroom_subjects

    # 3. Class-wide computation for ranks and averages
    s1_class_key = ('s1_class_res', classroom.id if classroom else None, ay.id if ay else None)
    if s1_class_key not in context_cache:
        context_cache[s1_class_key] = AcademicResultService.compute_semester_results(classroom, ay, semester=1) if (classroom and ay) else {'students_data': []}
    s1_class_res = context_cache[s1_class_key]

    s2_class_key = ('s2_class_res', classroom.id if classroom else None, ay.id if ay else None)
    if s2_class_key not in context_cache:
        context_cache[s2_class_key] = AcademicResultService.compute_semester_results(classroom, ay, semester=2) if (classroom and ay) else {'students_data': []}
    s2_class_res = context_cache[s2_class_key]

    ann_class_key = ('ann_class_res', classroom.id if classroom else None, ay.id if ay else None)
    if ann_class_key not in context_cache:
        context_cache[ann_class_key] = AcademicResultService.compute_annual_results(classroom, ay) if (classroom and ay) else {'students_data': []}
    ann_class_res = context_cache[ann_class_key]

    s1_stu_item = next((item for item in s1_class_res.get('students_data', []) if getattr(item.get('student'), 'id', None) == student.id), None)
    s2_stu_item = next((item for item in s2_class_res.get('students_data', []) if getattr(item.get('student'), 'id', None) == student.id), None)
    ann_stu_item = next((item for item in ann_class_res.get('students_data', []) if getattr(item.get('student'), 'id', None) == student.id), None)

    # Compute Grade-Level Ranks across all classrooms of this grade level
    grade_classrooms_key = ('grade_classrooms', grade_level, ay.id if ay else None)
    if grade_classrooms_key not in context_cache:
        context_cache[grade_classrooms_key] = list(Classroom.objects.filter(grade_level=grade_level, academic_year=ay)) if ay else ([classroom] if classroom else [])
    grade_classrooms = context_cache[grade_classrooms_key]

    total_class_students = classroom.total_students if classroom else 1

    s1_default_rank = s1_stu_item.get('rank') if s1_stu_item else None
    s1_grade_rank = s1_default_rank
    total_grade_students_s1 = total_class_students
    if len(grade_classrooms) > 1:
        all_s1_key = ('all_s1', grade_level, ay.id if ay else None)
        if all_s1_key not in context_cache:
            all_s1 = []
            for c in grade_classrooms:
                c_key = ('s1_class_res', c.id, ay.id if ay else None)
                if c_key not in context_cache:
                    context_cache[c_key] = AcademicResultService.compute_semester_results(c, ay, semester=1)
                c_res = context_cache[c_key]
                all_s1.extend([st for st in c_res.get('students_data', []) if st.get('semester_final_average') is not None])
            if all_s1:
                all_s1.sort(key=lambda x: float(x.get('semester_final_average') or 0), reverse=True)
            context_cache[all_s1_key] = all_s1
        all_s1 = context_cache[all_s1_key]

        if all_s1:
            total_grade_students_s1 = len(all_s1)
            s1_grade_rank = next(
                (idx + 1 for idx, item in enumerate(all_s1) if getattr(item.get('student'), 'id', None) == student.id),
                s1_default_rank
            )

    s2_default_rank = s2_stu_item.get('rank') if s2_stu_item else None
    s2_grade_rank = s2_default_rank
    total_grade_students_s2 = total_class_students
    if len(grade_classrooms) > 1:
        all_s2_key = ('all_s2', grade_level, ay.id if ay else None)
        if all_s2_key not in context_cache:
            all_s2 = []
            for c in grade_classrooms:
                c_key = ('s2_class_res', c.id, ay.id if ay else None)
                if c_key not in context_cache:
                    context_cache[c_key] = AcademicResultService.compute_semester_results(c, ay, semester=2)
                c_res = context_cache[c_key]
                all_s2.extend([st for st in c_res.get('students_data', []) if st.get('semester_final_average') is not None])
            if all_s2:
                all_s2.sort(key=lambda x: float(x.get('semester_final_average') or 0), reverse=True)
            context_cache[all_s2_key] = all_s2
        all_s2 = context_cache[all_s2_key]

        if all_s2:
            total_grade_students_s2 = len(all_s2)
            s2_grade_rank = next(
                (idx + 1 for idx, item in enumerate(all_s2) if getattr(item.get('student'), 'id', None) == student.id),
                s2_default_rank
            )

    ann_default_rank = ann_stu_item.get('rank') if ann_stu_item else None
    ann_grade_rank = ann_default_rank
    total_grade_students_ann = total_class_students
    if len(grade_classrooms) > 1:
        all_ann_key = ('all_ann', grade_level, ay.id if ay else None)
        if all_ann_key not in context_cache:
            all_ann = []
            for c in grade_classrooms:
                c_key = ('ann_class_res', c.id, ay.id if ay else None)
                if c_key not in context_cache:
                    context_cache[c_key] = AcademicResultService.compute_annual_results(c, ay)
                c_res = context_cache[c_key]
                all_ann.extend([st for st in c_res.get('students_data', []) if st.get('annual_average') is not None])
            if all_ann:
                all_ann.sort(key=lambda x: float(x.get('annual_average') or 0), reverse=True)
            context_cache[all_ann_key] = all_ann
        all_ann = context_cache[all_ann_key]

        if all_ann:
            total_grade_students_ann = len(all_ann)
            ann_grade_rank = next(
                (idx + 1 for idx, item in enumerate(all_ann) if getattr(item.get('student'), 'id', None) == student.id),
                ann_default_rank
            )

    # 4. Subject Rows Matrix
    subject_rows = []
    for idx, rule in enumerate(subject_rules, 1):
        sub = rule.subject
        max_sc = rule.max_score or Decimal('100.00')

        # Semester 1 monthly scores
        s1_m_scores = []
        s1_m_vals = []
        for mt in s1_monthly_terms:
            sc = None
            term_ids = getattr(mt, 'term_ids', [mt.id] if hasattr(mt, 'id') else [])
            for tid in term_ids:
                if (sub.id, tid) in grade_map:
                    sc = grade_map[(sub.id, tid)]
                    break

            s1_m_scores.append({
                'term': getattr(mt, 'primary_term', mt),
                'display_month': getattr(mt, 'display_month', getattr(mt, 'name', '')),
                'score': sc,
            })
            if sc is not None:
                s1_m_vals.append(sc)

        s1_sub_m_avg = round(sum(s1_m_vals) / Decimal(str(len(s1_m_vals))), 2) if s1_m_vals else None
        s1_sub_exam = grade_map.get((sub.id, s1_exam_term.id)) if s1_exam_term else None

        if s1_sub_m_avg is not None and s1_sub_exam is not None:
            s1_sub_final = round((s1_sub_m_avg + s1_sub_exam) / Decimal('2.0'), 2)
        elif s1_sub_exam is not None:
            s1_sub_final = s1_sub_exam
        elif s1_sub_m_avg is not None:
            s1_sub_final = s1_sub_m_avg
        else:
            s1_sub_final = None

        s1_sub_pct = round((s1_sub_final / max_sc) * Decimal('100.0'), 2) if (s1_sub_final is not None and max_sc > 0) else None
        s1_sub_letter = AcademicResultService.get_letter_grade(s1_sub_pct)[0] if s1_sub_pct is not None else '-'

        # Semester 2 monthly scores
        s2_m_scores = []
        s2_m_vals = []
        for mt in s2_monthly_terms:
            sc = None
            term_ids = getattr(mt, 'term_ids', [mt.id] if hasattr(mt, 'id') else [])
            for tid in term_ids:
                if (sub.id, tid) in grade_map:
                    sc = grade_map[(sub.id, tid)]
                    break

            s2_m_scores.append({
                'term': getattr(mt, 'primary_term', mt),
                'display_month': getattr(mt, 'display_month', getattr(mt, 'name', '')),
                'score': sc,
            })
            if sc is not None:
                s2_m_vals.append(sc)

        s2_sub_m_avg = round(sum(s2_m_vals) / Decimal(str(len(s2_m_vals))), 2) if s2_m_vals else None
        s2_sub_exam = grade_map.get((sub.id, s2_exam_term.id)) if s2_exam_term else None

        if s2_sub_m_avg is not None and s2_sub_exam is not None:
            s2_sub_final = round((s2_sub_m_avg + s2_sub_exam) / Decimal('2.0'), 2)
        elif s2_sub_exam is not None:
            s2_sub_final = s2_sub_exam
        elif s2_sub_m_avg is not None:
            s2_sub_final = s2_sub_m_avg
        else:
            s2_sub_final = None

        s2_sub_pct = round((s2_sub_final / max_sc) * Decimal('100.0'), 2) if (s2_sub_final is not None and max_sc > 0) else None
        s2_sub_letter = AcademicResultService.get_letter_grade(s2_sub_pct)[0] if s2_sub_pct is not None else '-'

        # Annual Subject Average
        if s1_sub_final is not None and s2_sub_final is not None:
            ann_sub_final = round((s1_sub_final + s2_sub_final) / Decimal('2.0'), 2)
        elif s2_sub_final is not None:
            ann_sub_final = s2_sub_final
        elif s1_sub_final is not None:
            ann_sub_final = s1_sub_final
        else:
            ann_sub_final = None

        ann_sub_pct = round((ann_sub_final / max_sc) * Decimal('100.0'), 2) if (ann_sub_final is not None and max_sc > 0) else None
        ann_sub_letter = AcademicResultService.get_letter_grade(ann_sub_pct)[0] if ann_sub_pct is not None else '-'

        subject_rows.append({
            'no': idx,
            'subject': sub,
            'name_kh': sub.name_kh,
            'name_en': sub.name_en or sub.name_kh,
            'max_score': max_sc,
            's1_monthly_scores': s1_m_scores,
            's1_monthly_avg': s1_sub_m_avg,
            's1_exam_score': s1_sub_exam,
            's1_final_score': s1_sub_final,
            's1_letter': s1_sub_letter,
            's2_monthly_scores': s2_m_scores,
            's2_monthly_avg': s2_sub_m_avg,
            's2_exam_score': s2_sub_exam,
            's2_final_score': s2_sub_final,
            's2_letter': s2_sub_letter,
            'annual_final_score': ann_sub_final,
            'annual_letter': ann_sub_letter,
        })

    # 5. Overall Semester Summaries
    s1_overall = {
        'monthly_avg': s1_stu_item.get('monthly_average') if s1_stu_item else None,
        'exam_score': s1_stu_item.get('semester_exam_score') if s1_stu_item else None,
        'final_average': s1_stu_item.get('semester_final_average') if s1_stu_item else None,
        'average_10': s1_stu_item.get('average_10') if s1_stu_item else Decimal('0.00'),
        'letter': s1_stu_item.get('letter_grade') if s1_stu_item else '-',
        'letter_desc': s1_stu_item.get('letter_desc') if s1_stu_item else '',
        'rank': s1_stu_item.get('rank') if s1_stu_item else '-',
        'grade_rank': s1_grade_rank or (s1_stu_item.get('rank') if s1_stu_item else '-'),
        'total_grade': total_grade_students_s1,
        'passed': s1_stu_item.get('passed') if s1_stu_item else False,
    }

    s2_overall = {
        'monthly_avg': s2_stu_item.get('monthly_average') if s2_stu_item else None,
        'exam_score': s2_stu_item.get('semester_exam_score') if s2_stu_item else None,
        'final_average': s2_stu_item.get('semester_final_average') if s2_stu_item else None,
        'average_10': s2_stu_item.get('average_10') if s2_stu_item else Decimal('0.00'),
        'letter': s2_stu_item.get('letter_grade') if s2_stu_item else '-',
        'letter_desc': s2_stu_item.get('letter_desc') if s2_stu_item else '',
        'rank': s2_stu_item.get('rank') if s2_stu_item else '-',
        'grade_rank': s2_grade_rank or (s2_stu_item.get('rank') if s2_stu_item else '-'),
        'total_grade': total_grade_students_s2,
        'passed': s2_stu_item.get('passed') if s2_stu_item else False,
    }

    ann_avg = ann_stu_item.get('annual_average') if ann_stu_item else None
    ann_let = ann_stu_item.get('grade_letter') if ann_stu_item else '-'
    ann_rk = ann_stu_item.get('rank') if ann_stu_item else '-'
    is_passed = ann_stu_item.get('passed') if ann_stu_item else (float(ann_avg or 0) >= 50.0)

    promoted_grade = grade_level + 1 if is_passed else grade_level
    decision_kh = f"អនុញ្ញាតឱ្យឡើងទៅរៀនថ្នាក់ទី {promoted_grade}" if is_passed else f"តម្រូវឱ្យរៀនត្រួតថ្នាក់ទី {grade_level}"
    decision_en = f"Promoted to Grade {promoted_grade}" if is_passed else f"Retained in Grade {grade_level}"

    annual_overall = {
        'annual_average': ann_avg,
        'average_10': round(ann_avg / Decimal('10.0'), 2) if ann_avg else Decimal('0.00'),
        'letter': ann_let,
        'rank': ann_rk,
        'grade_rank': ann_grade_rank or ann_rk,
        'total_grade': total_grade_students_ann,
        'passed': is_passed,
        'decision_kh': decision_kh,
        'decision_en': decision_en,
        'promoted_grade': promoted_grade,
    }

    # 6. Monthly Attendance Breakdown (October to July)
    # 6. Monthly Attendance Breakdown (Counted per session/shift: 1 session/shift = 1 count)
    att_cache_key = ('classroom_attendance', classroom.id if classroom else None, ay.id if ay else None)
    if att_cache_key not in context_cache:
        if classroom and ay and ay.start_date and ay.end_date:
            from collections import defaultdict
            c_att = defaultdict(list)
            for a in StudentAttendance.objects.filter(
                student__classroom=classroom,
                date__gte=ay.start_date,
                date__lte=ay.end_date
            ).only('student_id', 'date', 'session', 'status'):
                c_att[a.student_id].append(a)
            context_cache[att_cache_key] = c_att
        else:
            context_cache[att_cache_key] = None

    c_att = context_cache.get(att_cache_key)
    if c_att is not None:
        all_att = c_att.get(student.id, [])
    else:
        att_qs = StudentAttendance.objects.filter(student=student)
        if ay and ay.start_date and ay.end_date:
            att_qs = att_qs.filter(date__gte=ay.start_date, date__lte=ay.end_date)
        all_att = list(att_qs.only('date', 'session', 'status'))

    # Standard 10 academic months in Cambodia
    academic_months = [
        {'month': 10, 'name_kh': 'តុលា', 'name_en': 'October', 'semester': 1},
        {'month': 11, 'name_kh': 'វិច្ឆិកា', 'name_en': 'November', 'semester': 1},
        {'month': 12, 'name_kh': 'ធ្នូ', 'name_en': 'December', 'semester': 1},
        {'month': 1, 'name_kh': 'មករា', 'name_en': 'January', 'semester': 1},
        {'month': 2, 'name_kh': 'កុម្ភៈ', 'name_en': 'February', 'semester': 1},
        {'month': 3, 'name_kh': 'មីនា', 'name_en': 'March', 'semester': 2},
        {'month': 4, 'name_kh': 'មេសា', 'name_en': 'April', 'semester': 2},
        {'month': 5, 'name_kh': 'ឧសភា', 'name_en': 'May', 'semester': 2},
        {'month': 6, 'name_kh': 'មិថុនា', 'name_en': 'June', 'semester': 2},
        {'month': 7, 'name_kh': 'កក្កដា', 'name_en': 'July', 'semester': 2},
    ]

    monthly_attendance_records = []

    for m_item in academic_months:
        m_num = m_item['month']
        sem = m_item['semester']

        m_att = [a for a in all_att if a.date and a.date.month == m_num]

        # In Cambodian schools: 1 session/shift (MORNING or AFTERNOON) = 1 time/count (១ពេល/វេន គឺគិតយកម្តង)
        session_groups = {}
        for a in m_att:
            sess_key = (a.date, a.session or 'MORNING')
            if sess_key not in session_groups:
                session_groups[sess_key] = []
            session_groups[sess_key].append(a.status)

        pres = 0
        exc = 0
        unexc = 0
        late = 0

        for sess_key, statuses in session_groups.items():
            if any(s in ['ABSENT', 'UNEXCUSED_ABSENCE'] for s in statuses):
                unexc += 1
            elif any(s in ['PERMISSION', 'EXCUSED_LEAVE'] for s in statuses):
                exc += 1
            elif any(s == 'LATE' for s in statuses):
                late += 1
            elif any(s == 'PRESENT' for s in statuses):
                pres += 1

        tot_abs = exc + unexc
        tot_rec = pres + tot_abs + late
        rate = round((pres / tot_rec * 100), 1) if tot_rec > 0 else 100.0

        rec = {
            'month': m_num,
            'name_kh': m_item['name_kh'],
            'name_en': m_item['name_en'],
            'semester': sem,
            'present': pres,
            'excused': exc,
            'unexcused': unexc,
            'late': late,
            'total_absent': tot_abs,
            'total_recorded': tot_rec,
            'attendance_rate': rate,
        }
        monthly_attendance_records.append(rec)

    # Filter attendance records to strictly match the months defined by admin for each semester
    def _build_semester_attendance_records(monthly_terms, sem_num, default_semester_records):
        if not monthly_terms:
            has_records = any(r['total_recorded'] > 0 for r in default_semester_records)
            if has_records:
                return [r for r in default_semester_records if r['total_recorded'] > 0]
            return []
        records = []
        for t in monthly_terms:
            m_num = t.get('month') if isinstance(t, dict) else getattr(t, 'month', None)
            m_name = t.get('display_month') if isinstance(t, dict) else getattr(t, 'display_month', None)
            matching = next((r for r in monthly_attendance_records if r['month'] == m_num and r['semester'] == sem_num), None)
            if matching:
                records.append(matching)
            else:
                m_att = [a for a in all_att if a.date and a.date.month == m_num]
                session_groups = {}
                for a in m_att:
                    sess_key = (a.date, a.session or 'MORNING')
                    if sess_key not in session_groups:
                        session_groups[sess_key] = []
                    session_groups[sess_key].append(a.status)
                pres = exc = unexc = late = 0
                for sess_key, statuses in session_groups.items():
                    if any(s in ['ABSENT', 'UNEXCUSED_ABSENCE'] for s in statuses):
                        unexc += 1
                    elif any(s in ['PERMISSION', 'EXCUSED_LEAVE'] for s in statuses):
                        exc += 1
                    elif any(s == 'LATE' for s in statuses):
                        late += 1
                    elif any(s == 'PRESENT' for s in statuses):
                        pres += 1
                tot_abs = exc + unexc
                tot_rec = pres + tot_abs + late
                rate = round((pres / tot_rec * 100), 1) if tot_rec > 0 else 100.0
                records.append({
                    'month': m_num,
                    'name_kh': m_name or str(m_num),
                    'name_en': str(m_num),
                    'semester': sem_num,
                    'present': pres,
                    'excused': exc,
                    'unexcused': unexc,
                    'late': late,
                    'total_absent': tot_abs,
                    'total_recorded': tot_rec,
                    'attendance_rate': rate,
                })
        return records

    s1_attendance_records = _build_semester_attendance_records(
        s1_monthly_terms, 1, [rec for rec in monthly_attendance_records if rec['semester'] == 1]
    )
    s2_attendance_records = _build_semester_attendance_records(
        s2_monthly_terms, 2, [rec for rec in monthly_attendance_records if rec['semester'] == 2]
    )

    s1_att_totals = {'present': 0, 'excused': 0, 'unexcused': 0, 'late': 0, 'total_absent': 0, 'total_recorded': 0, 'attendance_rate': 100.0}
    for rec in s1_attendance_records:
        s1_att_totals['present'] += rec['present']
        s1_att_totals['excused'] += rec['excused']
        s1_att_totals['unexcused'] += rec['unexcused']
        s1_att_totals['late'] += rec['late']
        s1_att_totals['total_absent'] += rec['total_absent']
        s1_att_totals['total_recorded'] += rec['total_recorded']
    s1_att_totals['attendance_rate'] = (
        round((s1_att_totals['present'] / s1_att_totals['total_recorded'] * 100), 1)
        if s1_att_totals['total_recorded'] > 0 else 100.0
    )

    s2_att_totals = {'present': 0, 'excused': 0, 'unexcused': 0, 'late': 0, 'total_absent': 0, 'total_recorded': 0, 'attendance_rate': 100.0}
    for rec in s2_attendance_records:
        s2_att_totals['present'] += rec['present']
        s2_att_totals['excused'] += rec['excused']
        s2_att_totals['unexcused'] += rec['unexcused']
        s2_att_totals['late'] += rec['late']
        s2_att_totals['total_absent'] += rec['total_absent']
        s2_att_totals['total_recorded'] += rec['total_recorded']
    s2_att_totals['attendance_rate'] = (
        round((s2_att_totals['present'] / s2_att_totals['total_recorded'] * 100), 1)
        if s2_att_totals['total_recorded'] > 0 else 100.0
    )

    annual_att_totals = {
        'present': s1_att_totals['present'] + s2_att_totals['present'],
        'excused': s1_att_totals['excused'] + s2_att_totals['excused'],
        'unexcused': s1_att_totals['unexcused'] + s2_att_totals['unexcused'],
        'late': s1_att_totals['late'] + s2_att_totals['late'],
        'total_absent': s1_att_totals['total_absent'] + s2_att_totals['total_absent'],
        'total_recorded': s1_att_totals['total_recorded'] + s2_att_totals['total_recorded'],
    }
    annual_att_totals['attendance_rate'] = (
        round((annual_att_totals['present'] / annual_att_totals['total_recorded'] * 100), 1) 
        if annual_att_totals['total_recorded'] > 0 else 100.0
    )

    # 7. Conduct & Moral Rubrics (វាយតម្លៃអាកប្បកិរិយា សីលធម៌ គុណវុឌ្ឍិ & មតិគ្រូ/មាតាបិតា)
    conduct_cache_key = ('conduct_map', classroom.id if classroom else None, ay.id if ay else None)
    if conduct_cache_key not in context_cache:
        if classroom and ay:
            context_cache[conduct_cache_key] = {
                ca.student_id: ca
                for ca in StudentConductAssessment.objects.filter(student__classroom=classroom, academic_year=ay)
            }
        else:
            context_cache[conduct_cache_key] = None

    conduct_map = context_cache.get(conduct_cache_key)
    if conduct_map is not None:
        conduct_obj = conduct_map.get(student.id)
    else:
        conduct_obj = StudentConductAssessment.objects.filter(student=student, academic_year=ay).first()
    if conduct_obj:
        conduct_s1 = conduct_obj.overall_s1
        conduct_s2 = conduct_obj.overall_s2
        conduct_annual = conduct_obj.overall_annual
        teacher_comment_s1 = conduct_obj.teacher_comment_s1 or "សិស្សមានការខិតខំប្រឹងប្រែងរៀនសូត្របានល្អ និងគោរពវិន័យបានត្រឹមត្រូវ។"
        teacher_comment_s2 = conduct_obj.teacher_comment_s2 or "សិស្សមានការរីកចម្រើនគួរឱ្យកត់សម្គាល់ ទទួលបានលទ្ធផលគាប់ប្រសើរ។"
        teacher_comment_monthly = getattr(conduct_obj, 'teacher_comment_monthly', None) or "សិស្សមានការយកចិត្តទុកដាក់រៀនសូត្រ វត្តមានទៀងទាត់ និងខិតខំបំពេញកិច្ចការផ្ទះបានល្អ។"
        parent_comment_s1 = conduct_obj.parent_comment_s1 or "បានពិនិត្យ និងតាមដានការសិក្សារបស់កូនរួចរាល់។"
        parent_comment_s2 = conduct_obj.parent_comment_s2 or "សូមថ្លែងអំណរគុណលោកគ្រូ-អ្នកគ្រូដែលបានយកចិត្តទុកដាក់បង្រៀន។"
        parent_comment_monthly = getattr(conduct_obj, 'parent_comment_monthly', None) or "បានពិនិត្យ និងតាមដានលទ្ធផលសិក្សាប្រចាំខែរបស់កូនរួចរាល់។"
        conduct_criteria = [
            {'no': '១', 'name_kh': 'ការគោរពវិន័យ និងបទបញ្ជាផ្ទៃក្នុងសាលា', 'name_en': 'Discipline & School Regulations', 's1': conduct_obj.discipline_s1, 's2': conduct_obj.discipline_s2, 'ann': conduct_obj.discipline_annual},
            {'no': '២', 'name_kh': 'ការខិតខំប្រឹងប្រែងក្នុងការសិក្សា និងស្វ័យសិក្សា', 'name_en': 'Academic Diligence & Self-Study', 's1': conduct_obj.diligence_s1, 's2': conduct_obj.diligence_s2, 'ann': conduct_obj.diligence_annual},
            {'no': '៣', 'name_kh': 'សីលធម៌ សុជីវធម៌ និងការប្រាស្រ័យទាក់ទង', 'name_en': 'Moral, Manners & Interpersonal Conduct', 's1': conduct_obj.moral_s1, 's2': conduct_obj.moral_s2, 'ann': conduct_obj.moral_annual},
            {'no': '៤', 'name_kh': 'អនាម័យផ្ទាល់ខ្លួន និងការថែរក្សាបរិស្ថាន', 'name_en': 'Personal Hygiene & Environmental Care', 's1': conduct_obj.hygiene_s1, 's2': conduct_obj.hygiene_s2, 'ann': conduct_obj.hygiene_annual},
            {'no': '៥', 'name_kh': 'ការចូលរួមសកម្មភាពសង្គម ពលកម្ម និងកីឡា', 'name_en': 'Social Activities, Labor & Sports', 's1': conduct_obj.social_s1, 's2': conduct_obj.social_s2, 'ann': conduct_obj.social_annual},
        ]
    else:
        def determine_conduct_grade(avg_val, unexcused_cnt):
            if avg_val is None:
                return "ល្អ"
            a = float(avg_val)
            if a >= 80 and unexcused_cnt <= 2:
                return "ល្អណាស់"
            elif a >= 65 and unexcused_cnt <= 5:
                return "ល្អ"
            elif a >= 50:
                return "ល្អបង្គួរ"
            else:
                return "មធ្យម"

        conduct_s1 = determine_conduct_grade(s1_overall['final_average'], s1_att_totals['unexcused'])
        conduct_s2 = determine_conduct_grade(s2_overall['final_average'], s2_att_totals['unexcused'])
        conduct_annual = determine_conduct_grade(ann_avg, annual_att_totals['unexcused'])
        teacher_comment_s1 = "សិស្សមានការខិតខំប្រឹងប្រែងរៀនសូត្របានល្អ និងគោរពវិន័យបានត្រឹមត្រូវ។"
        teacher_comment_s2 = "សិស្សមានការរីកចម្រើនគួរឱ្យកត់សម្គាល់ ទទួលបានលទ្ធផលគាប់ប្រសើរ។"
        teacher_comment_monthly = "សិស្សមានការយកចិត្តទុកដាក់រៀនសូត្រ វត្តមានទៀងទាត់ និងខិតខំបំពេញកិច្ចការផ្ទះបានល្អ។"
        parent_comment_s1 = "បានពិនិត្យ និងតាមដានការសិក្សារបស់កូនរួចរាល់។"
        parent_comment_s2 = "សូមថ្លែងអំណរគុណលោកគ្រូ-អ្នកគ្រូដែលបានយកចិត្តទុកដាក់បង្រៀន។"
        parent_comment_monthly = "បានពិនិត្យ និងតាមដានលទ្ធផលសិក្សាប្រចាំខែរបស់កូនរួចរាល់។"
        conduct_criteria = [
            {'no': '១', 'name_kh': 'ការគោរពវិន័យ និងបទបញ្ជាផ្ទៃក្នុងសាលា', 'name_en': 'Discipline & School Regulations', 's1': conduct_s1, 's2': conduct_s2, 'ann': conduct_annual},
            {'no': '២', 'name_kh': 'ការខិតខំប្រឹងប្រែងក្នុងការសិក្សា និងស្វ័យសិក្សា', 'name_en': 'Academic Diligence & Self-Study', 's1': conduct_s1, 's2': conduct_s2, 'ann': conduct_annual},
            {'no': '៣', 'name_kh': 'សីលធម៌ សុជីវធម៌ និងការប្រាស្រ័យទាក់ទង', 'name_en': 'Moral, Manners & Interpersonal Conduct', 's1': 'ល្អណាស់', 's2': 'ល្អណាស់', 'ann': 'ល្អណាស់'},
            {'no': '៤', 'name_kh': 'អនាម័យផ្ទាល់ខ្លួន និងការថែរក្សាបរិស្ថាន', 'name_en': 'Personal Hygiene & Environmental Care', 's1': 'ល្អ', 's2': 'ល្អ', 'ann': 'ល្អ'},
            {'no': '៥', 'name_kh': 'ការចូលរួមសកម្មភាពសង្គម ពលកម្ម និងកីឡា', 'name_en': 'Social Activities, Labor & Sports', 's1': 'ល្អ', 's2': 'ល្អ', 'ann': 'ល្អ'},
        ]

    available_monthly_terms = []
    for t in s1_monthly_terms:
        m_num = t.get('month') if isinstance(t, dict) else getattr(t, 'month', None)
        m_name = t.get('display_month') if isinstance(t, dict) else getattr(t, 'display_month', None)
        if m_num:
            available_monthly_terms.append({'month': m_num, 'name_kh': m_name or str(m_num), 'semester': 1})
    for t in s2_monthly_terms:
        m_num = t.get('month') if isinstance(t, dict) else getattr(t, 'month', None)
        m_name = t.get('display_month') if isinstance(t, dict) else getattr(t, 'display_month', None)
        if m_num:
            available_monthly_terms.append({'month': m_num, 'name_kh': m_name or str(m_num), 'semester': 2})

    return {
        'student': student,
        'classroom': classroom,
        'grade_level': grade_level,
        'academic_year': ay,
        'homeroom_teacher': homeroom_teacher,
        'school_profile': school_profile,
        'school_name': default_school_name,
        'total_class_students': total_class_students,
        'total_grade_students': total_grade_students_ann,
        'available_monthly_terms': available_monthly_terms,
        's1_monthly_terms': s1_monthly_terms,
        's1_exam_term': s1_exam_term,
        's2_monthly_terms': s2_monthly_terms,
        's2_exam_term': s2_exam_term,
        'subject_rows': subject_rows,
        's1_overall': s1_overall,
        's2_overall': s2_overall,
        'annual_overall': annual_overall,
        'monthly_attendance_records': monthly_attendance_records,
        's1_attendance_records': s1_attendance_records,
        's2_attendance_records': s2_attendance_records,
        's1_att_totals': s1_att_totals,
        's2_att_totals': s2_att_totals,
        'annual_att_totals': annual_att_totals,
        'conduct_criteria': conduct_criteria,
        'conduct_s1': conduct_s1,
        'conduct_s2': conduct_s2,
        'conduct_annual': conduct_annual,
        'teacher_comment_s1': teacher_comment_s1,
        'teacher_comment_s2': teacher_comment_s2,
        'teacher_comment_monthly': teacher_comment_monthly,
        'parent_comment_s1': parent_comment_s1,
        'parent_comment_s2': parent_comment_s2,
        'parent_comment_monthly': parent_comment_monthly,
        's1_month_cols': s1_stu_item.get('month_cols', []) if s1_stu_item else [],
        's2_month_cols': s2_stu_item.get('month_cols', []) if s2_stu_item else [],
        'conduct_assessment': conduct_obj,
    }


def get_exam_at_risk_students(academic_year=None, threshold_sessions=8):
    """
    Evaluates students at risk of exam suspension (Exam Eligibility & Suspension Calculation).
    Identifies students with chronic unexcused absences (default: >= 8 sessions = 4.0 days).

    NOTE ON SCHOOL POLICY (គោលការណ៍គណនាសិទ្ធិប្រឡង):
    The system ONLY alerts/notifies Admin about at-risk students.
    The system NEVER automatically suspends or disqualifies students from exams.
    Actual Exam Suspension (is_exam_suspended) must be manually toggled (ON/OFF) by Admin exclusively.

    Returns:
        dict: {
            student_id: {
                'student_id': int,
                'absent_sessions': int,
                'absent_days': float,
                'risk_level': str ('HIGH', 'MEDIUM'),
                'risk_reason': str,
            }
        }
    """
    from apps.attendance.models import StudentAttendance
    from apps.students.models import Student

    qs = StudentAttendance.objects.filter(
        status=StudentAttendance.Status.ABSENT,
        student__status=Student.Status.ACTIVE
    )
    if academic_year:
        qs = qs.filter(Q(student__academic_year=academic_year) | Q(student__classroom__academic_year=academic_year))

    records = qs.values('student_id', 'date', 'session').distinct()
    counts = {}
    for r in records:
        sid = r['student_id']
        counts[sid] = counts.get(sid, 0) + 1

    at_risk_map = {}
    for sid, absent_times in counts.items():
        if absent_times >= threshold_sessions:
            absent_days = round(absent_times * 0.5, 1)
            at_risk_map[sid] = {
                'student_id': sid,
                'absent_sessions': absent_times,
                'absent_days': absent_days,
                'risk_level': 'HIGH' if absent_times >= 8 else 'MEDIUM',
                'risk_reason': f"អវត្តមានឥតច្បាប់ {absent_days} ថ្ងៃ ({absent_times} វេន)"
            }
    return at_risk_map


def get_exam_at_risk_student_list(academic_year=None, threshold_sessions=8):
    """
    Returns list of active Student instances flagged as at-risk for exam suspension,
    annotated with .exam_at_risk_info, sorted descending by absent session count.
    """
    at_risk_map = get_exam_at_risk_students(academic_year=academic_year, threshold_sessions=threshold_sessions)
    if not at_risk_map:
        return []
    students = list(Student.objects.filter(id__in=at_risk_map.keys(), status=Student.Status.ACTIVE).select_related('classroom'))
    for s in students:
        s.exam_at_risk_info = at_risk_map.get(s.id, {})
    students.sort(key=lambda x: x.exam_at_risk_info.get('absent_sessions', 0), reverse=True)
    return students




