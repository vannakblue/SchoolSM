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
