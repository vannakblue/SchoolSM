from decimal import Decimal
from django.db.models import Q
from .models import StandardizedExam, ExamCandidate, ExamSubject, CandidateSubjectScore


def get_subject_mention(score, max_score):
    """
    Computes official MoEYS subject letter grade (A..F):
    - A: >= 90%
    - B: >= 80% and < 90%
    - C: >= 70% and < 80%
    - D: >= 60% and < 70%
    - E: >= 50% and < 60%
    - F: < 50%
    """
    if score is None:
        return '-'
    try:
        s = float(score)
    except (ValueError, TypeError):
        return '-'
    m = float(max_score) if max_score and float(max_score) > 0 else 50.0
    pct = (s / m) * 100.0
    if pct >= 90.0:
        return 'A'
    if pct >= 80.0:
        return 'B'
    if pct >= 70.0:
        return 'C'
    if pct >= 60.0:
        return 'D'
    if pct >= 50.0:
        return 'E'
    return 'F'


def get_overall_mention(total_score, max_total_score):
    """
    Computes overall exam letter grade (A..F) based on percentage of total score.
    """
    if total_score is None:
        return '-'
    try:
        s = float(total_score)
    except (ValueError, TypeError):
        return '-'
    m = float(max_total_score) if max_total_score and float(max_total_score) > 0 else 100.0
    if m <= 0:
        return '-'
    pct = (s / m) * 100.0
    if pct >= 90.0:
        return 'A'
    if pct >= 80.0:
        return 'B'
    if pct >= 70.0:
        return 'C'
    if pct >= 60.0:
        return 'D'
    if pct >= 50.0:
        return 'E'
    return 'F'


class ExamAnalyticsService:
    """
    Comprehensive Analytics Service for Standardized Examination Sessions
    Reproduces reports across 3 breakdown scopes:
      1. 'school': Across all grades in the examination session
      2. 'grade': Filtered by specific grade level (e.g. 7, 8, 9, 10, 11, 12)
      3. 'class': Filtered by specific classroom (e.g. 7A, 10A, 12A1)
    """

    @classmethod
    def get_analytics_payload(cls, exams, scope='school', grade_level=None, classroom_name=None):
        """
        Main calculation engine returning full data structures for all 4 report components:
        - overall_mentions (Image 2 - Left)
        - quality_evaluation (Image 2 - Right)
        - subject_mentions (Images 3 & 4 - Single and Detailed views)
        - subject_percentages (Image 5)
        - slow_learners (Image 1 - Candidates & scores table)
        """
        if not hasattr(exams, '__iter__'):
            exams = [exams]
        else:
            exams = list(exams)

        if not exams:
            return cls._empty_payload()

        # Apply Scope Filtering to Exams
        if scope == 'grade' and grade_level:
            try:
                g_int = int(grade_level)
                active_exams = [e for e in exams if e.grade_level == g_int]
                if not active_exams:
                    active_exams = exams
            except (ValueError, TypeError):
                active_exams = exams
        else:
            active_exams = exams

        exam_ids = [e.id for e in active_exams]

        # Fetch Candidates with scores preloaded
        candidates_qs = ExamCandidate.objects.filter(
            exam_id__in=exam_ids
        ).select_related('exam', 'student', 'room').prefetch_related(
            'subject_scores__exam_subject__subject'
        ).order_by('exam__grade_level', 'origin_class', 'roll_number', 'id')

        if scope == 'class' and classroom_name:
            candidates_qs = candidates_qs.filter(origin_class__iexact=str(classroom_name).strip())

        candidates = list(candidates_qs)

        # Collect and deduplicate subjects in logical display order
        # Map: subject_id -> {'name': subject_name, 'max_score': max_score, 'order': order}
        subjects_map = {}
        for exam in active_exams:
            for es in exam.exam_subjects.select_related('subject').order_by('order', 'id'):
                s_id = es.subject_id
                if s_id not in subjects_map:
                    subjects_map[s_id] = {
                        'id': s_id,
                        'code': es.subject.code or f"sub_{s_id}",
                        'name': es.subject.name_kh or es.subject.name_en,
                        'short': es.subject.name_kh[:4] if es.subject.name_kh else es.subject.name_en[:4],
                        'max_score': float(es.max_score),
                        'order': es.order,
                    }
                else:
                    # Update max score if larger
                    if float(es.max_score) > subjects_map[s_id]['max_score']:
                        subjects_map[s_id]['max_score'] = float(es.max_score)

        subjects_list = sorted(subjects_map.values(), key=lambda s: (s['order'], s['id']))

        # Process Candidates: Compute individual candidate subject scores, mentions, and overall total
        processed_candidates = []
        for cand in candidates:
            # Build quick score lookup for candidate: subject_id -> score_obj
            c_scores = {}
            for sc in cand.subject_scores.all():
                if sc.exam_subject and sc.exam_subject.subject_id:
                    c_scores[sc.exam_subject.subject_id] = sc

            cand_subject_data = {}
            cand_total_score = 0.0
            cand_max_total = 0.0
            has_any_score = False

            for s in subjects_list:
                s_id = s['id']
                sc_obj = c_scores.get(s_id)
                score_val = None
                is_absent = False
                if sc_obj:
                    is_absent = sc_obj.is_absent
                    if sc_obj.score is not None and not is_absent:
                        score_val = float(sc_obj.score)
                        cand_total_score += score_val
                        has_any_score = True

                mention = get_subject_mention(score_val, s['max_score'])
                cand_max_total += s['max_score']

                cand_subject_data[s_id] = {
                    'score': score_val,
                    'is_absent': is_absent,
                    'mention': mention,
                    'is_weak': mention in ['E', 'F'] or (score_val is not None and score_val < (s['max_score'] * 0.5)),
                    'max_score': s['max_score'],
                }

            # If candidate total_score was already stored on model, use it or computed sum
            final_tot = float(cand.total_score) if (cand.total_score and float(cand.total_score) > 0) else cand_total_score
            overall_m = cand.grade_letter if (cand.grade_letter and cand.grade_letter in ['A', 'B', 'C', 'D', 'E', 'F']) else get_overall_mention(final_tot, cand_max_total)

            # Overall percentage
            pct = (final_tot / cand_max_total * 100.0) if cand_max_total > 0 and has_any_score else 0.0

            processed_candidates.append({
                'id': cand.id,
                'student_code': cand.student_code or (cand.student.student_id if cand.student else '') or cand.roll_number,
                'candidate_name_kh': cand.candidate_name_kh,
                'gender': cand.gender,
                'gender_kh': 'ស្រី' if cand.gender == 'F' else 'ប្រុស',
                'gender_short': 'ស' if cand.gender == 'F' else 'ប',
                'grade_level': cand.exam.grade_level,
                'origin_class': cand.origin_class or f"ថ្នាក់ទី{cand.exam.grade_level}",
                'total_score': round(final_tot, 2),
                'overall_mention': overall_m,
                'percentage': round(pct, 1),
                'subjects': cand_subject_data,
            })

        total_candidates_count = len(processed_candidates)
        female_candidates_count = sum(1 for c in processed_candidates if c['gender'] == 'F')
        male_candidates_count = total_candidates_count - female_candidates_count

        # -------------------------------------------------------------
        # 1. Overall Mentions Matrix (Image 2 - Left)
        # -------------------------------------------------------------
        # Mentions: A, B, C, D, E, F, A+B+C, Total
        grades_list = ['A', 'B', 'C', 'D', 'E', 'F']
        
        counts_total = {g: 0 for g in grades_list}
        counts_female = {g: 0 for g in grades_list}
        counts_male = {g: 0 for g in grades_list}

        for c in processed_candidates:
            m = c['overall_mention']
            if m in counts_total:
                counts_total[m] += 1
                if c['gender'] == 'F':
                    counts_female[m] += 1
                else:
                    counts_male[m] += 1

        sum_abc_total = counts_total['A'] + counts_total['B'] + counts_total['C']
        sum_abc_female = counts_female['A'] + counts_female['B'] + counts_female['C']
        sum_abc_male = counts_male['A'] + counts_male['B'] + counts_male['C']

        overall_mentions = {
            'grades': grades_list,
            'total_row': {
                'label': 'សរុប',
                'counts': [counts_total[g] for g in grades_list],
                'sum_abc': sum_abc_total,
                'grand_total': total_candidates_count,
            },
            'female_row': {
                'label': 'ស្រី',
                'counts': [counts_female[g] for g in grades_list],
                'sum_abc': sum_abc_female,
                'grand_total': female_candidates_count,
            },
            'male_row': {
                'label': 'ប្រុស',
                'counts': [counts_male[g] for g in grades_list],
                'sum_abc': sum_abc_male,
                'grand_total': male_candidates_count,
            }
        }

        # -------------------------------------------------------------
        # 2. Quality Evaluation Matrix (Image 2 - Right)
        # -------------------------------------------------------------
        # Tiers:
        # - ល្អ (>=40 or >=80%): matches A + B
        # - ល្អបង្គួរ (>=32.5 or 65%..79.9%): matches C + high D
        # - មធ្យម (>=25 or 50%..64.9%): matches low D + E
        # - ខ្សោយ (<25 or <50%): matches F
        quality_counts = {
            'good': {'total': 0, 'female': 0, 'male': 0},         # >=80%
            'fairly_good': {'total': 0, 'female': 0, 'male': 0},  # 65% - 79.9%
            'average': {'total': 0, 'female': 0, 'male': 0},      # 50% - 64.9%
            'weak': {'total': 0, 'female': 0, 'male': 0},         # < 50%
        }

        for c in processed_candidates:
            pct = c['percentage']
            gen = 'female' if c['gender'] == 'F' else 'male'
            
            if pct >= 80.0:
                tier = 'good'
            elif pct >= 65.0:
                tier = 'fairly_good'
            elif pct >= 50.0:
                tier = 'average'
            else:
                tier = 'weak'

            quality_counts[tier]['total'] += 1
            quality_counts[tier][gen] += 1

        quality_evaluation = {
            'headers': [
                {'key': 'good', 'label': 'ល្អ (>=40)', 'sub': '>=80%', 'class': 'text-primary'},
                {'key': 'fairly_good', 'label': 'ល្អបង្គួរ (>=32.5)', 'sub': '>=65%', 'class': 'text-success'},
                {'key': 'average', 'label': 'មធ្យម (>=25)', 'sub': '>=50%', 'class': 'text-warning text-dark'},
                {'key': 'weak', 'label': 'ខ្សោយ (<25)', 'sub': '<50%', 'class': 'text-danger'},
                {'key': 'total', 'label': 'សរុប', 'sub': '', 'class': 'text-dark'},
            ],
            'total_row': {
                'label': 'សរុប',
                'good': quality_counts['good']['total'],
                'fairly_good': quality_counts['fairly_good']['total'],
                'average': quality_counts['average']['total'],
                'weak': quality_counts['weak']['total'],
                'grand_total': total_candidates_count,
            },
            'female_row': {
                'label': 'ស្រី',
                'good': quality_counts['good']['female'],
                'fairly_good': quality_counts['fairly_good']['female'],
                'average': quality_counts['average']['female'],
                'weak': quality_counts['weak']['female'],
                'grand_total': female_candidates_count,
            },
            'male_row': {
                'label': 'ប្រុស',
                'good': quality_counts['good']['male'],
                'fairly_good': quality_counts['fairly_good']['male'],
                'average': quality_counts['average']['male'],
                'weak': quality_counts['weak']['male'],
                'grand_total': male_candidates_count,
            },
        }

        # -------------------------------------------------------------
        # 3. Subject Mentions Matrix (Images 3 & 4)
        # -------------------------------------------------------------
        # For each subject:
        # Counts of A, B, C, D, E, F, A+B+C, Total
        # Single mode: Total counts per subject
        # Detailed mode: Total, Female, Male counts for each grade
        subject_mentions_single = []
        subject_mentions_detailed = []

        for s in subjects_list:
            s_id = s['id']
            max_s = int(s['max_score']) if s['max_score'] == int(s['max_score']) else s['max_score']
            subj_display_title = f"{s['name']} ({max_s})"

            # Count per grade
            s_counts = {g: {'total': 0, 'female': 0, 'male': 0} for g in grades_list}
            
            for c in processed_candidates:
                s_data = c['subjects'].get(s_id)
                if s_data and s_data['mention'] in s_counts:
                    m = s_data['mention']
                    s_counts[m]['total'] += 1
                    if c['gender'] == 'F':
                        s_counts[m]['female'] += 1
                    else:
                        s_counts[m]['male'] += 1

            # Calculations
            abc_tot = s_counts['A']['total'] + s_counts['B']['total'] + s_counts['C']['total']
            abc_fem = s_counts['A']['female'] + s_counts['B']['female'] + s_counts['C']['female']
            abc_mal = s_counts['A']['male'] + s_counts['B']['male'] + s_counts['C']['male']

            total_tot = sum(s_counts[g]['total'] for g in grades_list)
            total_fem = sum(s_counts[g]['female'] for g in grades_list)
            total_mal = sum(s_counts[g]['male'] for g in grades_list)

            # Single row structure (Image 3)
            subject_mentions_single.append({
                'subject_id': s_id,
                'title': subj_display_title,
                'name': s['name'],
                'max_score': s['max_score'],
                'a': s_counts['A']['total'],
                'b': s_counts['B']['total'],
                'c': s_counts['C']['total'],
                'd': s_counts['D']['total'],
                'e': s_counts['E']['total'],
                'f': s_counts['F']['total'],
                'sum_abc': abc_tot,
                'total': total_tot,
            })

            # Detailed row structure (Image 4)
            subject_mentions_detailed.append({
                'subject_id': s_id,
                'title': subj_display_title,
                'name': s['name'],
                'max_score': s['max_score'],
                'grades': {
                    g: {
                        'tot': s_counts[g]['total'],
                        'fem': s_counts[g]['female'],
                        'mal': s_counts[g]['male']
                    } for g in grades_list
                },
                'sum_abc': {
                    'tot': abc_tot,
                    'fem': abc_fem,
                    'mal': abc_mal
                },
                'total': {
                    'tot': total_tot,
                    'fem': total_fem,
                    'mal': total_mal
                }
            })

        # -------------------------------------------------------------
        # 4. Subject Percentage Matrix (Image 5)
        # -------------------------------------------------------------
        # Thresholds:
        # Group 1 (>=): 95%, 90%, 85%, 80%, 75%, 70%, 65%, 60%, 55%, 50%
        # Group 2 (Between): 60-80%, 50-<80%
        # Group 3 Weak (<): 60%, 50% (highlighted in red)
        percentage_thresholds = [95, 90, 85, 80, 75, 70, 65, 60, 55, 50]
        subject_percentage_rows = []

        for s in subjects_list:
            s_id = s['id']
            max_s = int(s['max_score']) if s['max_score'] == int(s['max_score']) else s['max_score']
            subj_display_title = f"{s['name']} ({max_s})"

            # Collect percentages for all candidates who took this subject
            candidate_pcts = []
            for c in processed_candidates:
                s_data = c['subjects'].get(s_id)
                if s_data and s_data['score'] is not None and not s_data['is_absent']:
                    pct = (s_data['score'] / s['max_score']) * 100.0
                    candidate_pcts.append(pct)

            # Calculate >= thresholds
            gte_counts = []
            for th in percentage_thresholds:
                cnt = sum(1 for p in candidate_pcts if p >= th)
                gte_counts.append(cnt if cnt > 0 else '-')

            # Calculate Ranges: 60-80%, 50-<80%
            between_60_80 = sum(1 for p in candidate_pcts if 60.0 <= p < 80.0)
            between_50_80 = sum(1 for p in candidate_pcts if 50.0 <= p < 80.0)

            # Calculate Weak: < 60%, < 50%
            lt_60 = sum(1 for p in candidate_pcts if p < 60.0)
            lt_50 = sum(1 for p in candidate_pcts if p < 50.0)

            subject_percentage_rows.append({
                'subject_id': s_id,
                'title': subj_display_title,
                'name': s['name'],
                'max_score': s['max_score'],
                'gte_counts': gte_counts,
                'between_60_80': between_60_80,
                'between_50_80': between_50_80,
                'lt_60': lt_60,
                'lt_50': lt_50,
            })

        # -------------------------------------------------------------
        # 5. Slow Learners / Candidates Matrix (Image 1)
        # -------------------------------------------------------------
        # In Image 1, rows display student records with scores or mentions
        # Default view shows students who scored E or F in any subject
        slow_learners_data = []
        for idx, c in enumerate(processed_candidates, 1):
            cand_row = {
                'index': idx,
                'id': c['id'],
                'student_code': c['student_code'],
                'candidate_name_kh': c['candidate_name_kh'],
                'gender': c['gender'],
                'gender_short': c['gender_short'],
                'origin_class': c['origin_class'],
                'overall_mention': c['overall_mention'],
                'has_weak_grade': any(c['subjects'][s['id']]['is_weak'] for s in subjects_list if s['id'] in c['subjects']),
                'subject_scores': {},
                'subject_mentions': {},
                'subject_weak_flags': {},
            }
            for s in subjects_list:
                s_id = s['id']
                s_data = c['subjects'].get(s_id, {})
                cand_row['subject_scores'][s_id] = s_data.get('score')
                cand_row['subject_mentions'][s_id] = s_data.get('mention', '-')
                cand_row['subject_weak_flags'][s_id] = s_data.get('is_weak', False)

            slow_learners_data.append(cand_row)

        # Collect unique classroom names across active exams for classroom scope filter
        all_classrooms = sorted(list(set(
            c['origin_class'] for c in processed_candidates if c['origin_class']
        )))

        # Available grade levels across the active exams
        available_grades = sorted(list(set(e.grade_level for e in active_exams)))

        return {
            'scope': scope,
            'selected_grade': grade_level,
            'selected_class': classroom_name,
            'available_grades': available_grades,
            'all_classrooms': all_classrooms,
            'subjects_list': subjects_list,
            'total_candidates': total_candidates_count,
            'female_candidates': female_candidates_count,
            'male_candidates': male_candidates_count,
            'overall_mentions': overall_mentions,
            'quality_evaluation': quality_evaluation,
            'subject_mentions_single': subject_mentions_single,
            'subject_mentions_detailed': subject_mentions_detailed,
            'subject_percentage_rows': subject_percentage_rows,
            'percentage_thresholds': percentage_thresholds,
            'slow_learners_data': slow_learners_data,
        }

    @classmethod
    def generate_mock_scores(cls, exams):
        """
        Generates realistic, natural mock examination scores with grades A to F
        for all candidates across all subjects for the given list of exams.
        """
        import random
        from decimal import Decimal

        if not hasattr(exams, '__iter__'):
            exams = [exams]
        else:
            exams = list(exams)

        # Realistic tier definitions: (tier_name, target_weight, pct_min, pct_max)
        tiers = [
            ('A', 0.10, 90.0, 98.0),   # 10% A
            ('B', 0.18, 80.0, 89.0),   # 18% B
            ('C', 0.30, 70.0, 79.0),   # 30% C
            ('D', 0.22, 60.0, 69.0),   # 22% D
            ('E', 0.12, 50.0, 59.0),   # 12% E
            ('F', 0.08, 28.0, 48.0),   # 8% F (slow learners)
        ]
        tier_choices = [t[0] for t in tiers]
        tier_weights = [t[1] for t in tiers]
        tier_ranges = {t[0]: (t[2], t[3]) for t in tiers}

        total_candidates_scored = 0
        total_scores_saved = 0

        for exam in exams:
            subjects = list(exam.exam_subjects.all().select_related('subject'))
            if not subjects:
                continue

            candidates = list(exam.candidates.all())
            if not candidates:
                continue

            # Preload existing CandidateSubjectScore objects
            existing_scores = {
                (sc.candidate_id, sc.exam_subject_id): sc
                for sc in CandidateSubjectScore.objects.filter(candidate__exam=exam)
            }

            scores_to_create = []
            scores_to_update = []

            for cand in candidates:
                chosen_tier = random.choices(tier_choices, weights=tier_weights, k=1)[0]
                t_min, t_max = tier_ranges[chosen_tier]
                student_absent = (random.random() < 0.015)  # 1.5% chance absent

                for s in subjects:
                    max_s = float(s.max_score) if s.max_score and float(s.max_score) > 0 else 50.0

                    if student_absent:
                        is_absent = True
                        score_val = Decimal('0.00')
                    else:
                        is_absent = False
                        base_pct = random.uniform(t_min, t_max)
                        subj_jitter = random.uniform(-6.0, 6.0)
                        final_pct = max(15.0, min(100.0, base_pct + subj_jitter))
                        calculated_score = round((final_pct / 100.0) * max_s, 1)
                        score_val = Decimal(str(calculated_score))

                    key = (cand.id, s.id)
                    if key in existing_scores:
                        sc = existing_scores[key]
                        sc.score = score_val
                        sc.is_absent = is_absent
                        sc.signature_present = not is_absent
                        scores_to_update.append(sc)
                    else:
                        scores_to_create.append(CandidateSubjectScore(
                            candidate=cand,
                            exam_subject=s,
                            score=score_val,
                            is_absent=is_absent,
                            signature_present=not is_absent
                        ))

                total_candidates_scored += 1

            if scores_to_create:
                CandidateSubjectScore.objects.bulk_create(scores_to_create, batch_size=1000)
                total_scores_saved += len(scores_to_create)
            if scores_to_update:
                CandidateSubjectScore.objects.bulk_update(scores_to_update, ['score', 'is_absent', 'signature_present'], batch_size=1000)
                total_scores_saved += len(scores_to_update)

            # Recalculate candidate averages, ranks, and grade letters
            exam.recalculate_all_ranks()

        return {
            'exams_count': len(exams),
            'candidates_count': total_candidates_scored,
            'scores_count': total_scores_saved,
        }

    @classmethod
    def clear_mock_scores(cls, exams):
        """
        Clears all scores and resets grades back to '-' for the given exams.
        """
        from decimal import Decimal

        if not hasattr(exams, '__iter__'):
            exams = [exams]
        else:
            exams = list(exams)

        total_candidates_cleared = 0
        for exam in exams:
            cands = exam.candidates.all()
            CandidateSubjectScore.objects.filter(candidate__in=cands).update(score=None, is_absent=False)
            cands.update(
                total_score=Decimal('0.00'),
                average_score=Decimal('0.00'),
                grade_letter='-',
                rank_overall=None,
                rank_in_room=None,
            )
            total_candidates_cleared += cands.count()

        return {
            'exams_count': len(exams),
            'candidates_count': total_candidates_cleared,
        }

    @classmethod
    def _empty_payload(cls):
        return {
            'scope': 'school',
            'selected_grade': None,
            'selected_class': None,
            'available_grades': [],
            'all_classrooms': [],
            'subjects_list': [],
            'total_candidates': 0,
            'female_candidates': 0,
            'male_candidates': 0,
            'overall_mentions': {'grades': ['A', 'B', 'C', 'D', 'E', 'F'], 'total_row': {'counts': [0]*6, 'sum_abc': 0, 'grand_total': 0}, 'female_row': {'counts': [0]*6, 'sum_abc': 0, 'grand_total': 0}, 'male_row': {'counts': [0]*6, 'sum_abc': 0, 'grand_total': 0}},
            'quality_evaluation': {'headers': [], 'total_row': {'good': 0, 'fairly_good': 0, 'average': 0, 'weak': 0, 'grand_total': 0}, 'female_row': {'good': 0, 'fairly_good': 0, 'average': 0, 'weak': 0, 'grand_total': 0}, 'male_row': {'good': 0, 'fairly_good': 0, 'average': 0, 'weak': 0, 'grand_total': 0}},
            'subject_mentions_single': [],
            'subject_mentions_detailed': [],
            'subject_percentage_rows': [],
            'percentage_thresholds': [95, 90, 85, 80, 75, 70, 65, 60, 55, 50],
            'slow_learners_data': [],
        }
