import re
import io
from decimal import Decimal
from datetime import date
from django.db import transaction
from django.db.models import Q
from apps.academics.models import AcademicYear, Classroom
from apps.students.models import Student, StudentPromotionRecord
from apps.examinations.models import StandardizedExam, ExamCandidate, CandidateSubjectScore, StudentTransferGrade
from apps.examinations.services import AcademicResultService


class ClassroomAllocationService:
    """
    Comprehensive Service for Student Classroom Allocation & Division by Academic Scores (ការបែងចែកថ្នាក់រៀនសិស្សតាមពិន្ទុ).
    Supports:
    1. Standardized / Baseline Exam Scores (ពិន្ទុតេស្តដើមឆ្នាំ / តេស្តស្តង់ដា)
    2. Previous Year Final Annual Scores [(Semester 1 + Semester 2) / 2] (ពិន្ទុមធ្យមភាគប្រចាំឆ្នាំចាស់)
    3. Custom / Manual / Equal distribution
    Strategies:
    - Top-Down / Stratified (ពិន្ទុខ្ពស់មកទាបតាមលំដាប់ថ្នាក់ A, B, C...)
    - Balanced Snake / Serpentine (បែងចែកស្មើដៃគ្នាតាមកម្រិតពិន្ទុ)
    - Gender Balanced (បែងចែកស្មើដៃគ្នាតាមពិន្ទុ និងយេនឌ័រ)
    """

    @staticmethod
    def get_available_score_sources(academic_year, grade_level, track='ALL'):
        """
        Retrieves all available score sources (exams, past academic years, target classrooms)
        for a given grade level and target academic year.
        """
        # 1. Target Classrooms in this academic year for this grade
        target_classes_qs = Classroom.objects.filter(
            academic_year=academic_year,
            grade_level=grade_level
        ).order_by('name')

        if track and track != 'ALL':
            target_classes_qs = target_classes_qs.filter(Q(track=track) | Q(track='GENERAL'))

        target_classes = list(target_classes_qs.values('id', 'name', 'code', 'grade_level', 'track', 'capacity'))
        for tc in target_classes:
            tc['current_students_count'] = Student.objects.filter(classroom_id=tc['id'], status='ACTIVE').count()

        # 2. Standardized / Baseline Exams matching this grade level
        exams_qs = StandardizedExam.objects.filter(
            grade_level=grade_level
        ).select_related('academic_year').order_by('-exam_date', '-id')

        # Prioritize exams in current academic year
        curr_year_exams = []
        other_year_exams = []
        for ex in exams_qs:
            cand_count = ex.candidates.count()
            scored_count = ex.candidates.filter(total_score__gt=0).count()
            ex_info = {
                'id': ex.id,
                'name': ex.name,
                'academic_year_id': ex.academic_year_id,
                'academic_year_name': ex.academic_year.name if ex.academic_year else '',
                'exam_date': ex.exam_date.strftime('%d/%m/%Y') if ex.exam_date else '',
                'candidates_count': cand_count,
                'scored_count': scored_count,
                'exam_type': ex.exam_type,
            }
            if ex.academic_year_id == academic_year.id:
                curr_year_exams.append(ex_info)
            else:
                other_year_exams.append(ex_info)

        available_exams = curr_year_exams + other_year_exams

        # 3. Available past academic years for Annual Average Scores [(S1 + S2) / 2]
        past_years = list(AcademicYear.objects.exclude(id=academic_year.id).order_by('-start_date').values('id', 'name', 'start_date', 'end_date'))
        # Suggest previous academic year if available
        suggested_past_year = past_years[0] if past_years else None

        # 4. Current students count in this grade level
        current_students_count = Student.objects.filter(
            academic_year=academic_year,
            classroom__grade_level=grade_level,
            status='ACTIVE'
        ).count()

        return {
            'target_classrooms': target_classes,
            'available_exams': available_exams,
            'past_academic_years': past_years,
            'suggested_past_year': suggested_past_year,
            'current_students_count': current_students_count,
            'suggested_previous_grade': (grade_level - 1) if grade_level > 7 else 7,
        }

    @staticmethod
    def get_students_with_scores(target_year, grade_level, score_source_type, exam_id=None, source_year_id=None, track='ALL'):
        """
        Pulls all active students for this grade level and attaches their computed score and ranking
        based on the selected score source.
        """
        students_qs = Student.objects.filter(
            academic_year=target_year,
            classroom__grade_level=grade_level,
            status='ACTIVE'
        ).select_related('classroom', 'academic_year').order_by('classroom__name', 'student_id')

        if track and track != 'ALL':
            students_qs = students_qs.filter(Q(classroom__track=track) | Q(classroom__track='GENERAL'))

        students = list(students_qs)
        if not students:
            # Fallback: if students don't have academic_year populated on student model, check classroom's academic_year
            students = list(Student.objects.filter(
                classroom__academic_year=target_year,
                classroom__grade_level=grade_level,
                status='ACTIVE'
            ).select_related('classroom', 'academic_year').order_by('classroom__name', 'student_id'))

        student_scores = {}
        score_source_title = ""

        # =====================================================================
        # SOURCE 1: Standardized / Baseline Exam Scores (ពិន្ទុតេស្តដើមឆ្នាំ / តេស្តស្តង់ដា)
        # =====================================================================
        if score_source_type == 'STANDARDIZED_EXAM' and exam_id:
            exam = StandardizedExam.objects.filter(id=exam_id).first()
            if exam:
                score_source_title = f"ពិន្ទុតេស្ត៖ {exam.name}"
                # Refresh ranks if candidates haven't been computed
                candidates = list(exam.candidates.select_related('student').all())
                
                # Check if recalculate is needed
                has_any_score = exam.candidates.filter(total_score__gt=0).exists()
                if not has_any_score and CandidateSubjectScore.objects.filter(candidate__exam=exam, score__isnull=False).exists():
                    try:
                        exam.recalculate_all_ranks()
                        candidates = list(exam.candidates.select_related('student').all())
                    except Exception:
                        pass

                cand_map_by_student_id = {}
                cand_map_by_code = {}
                cand_map_by_name = {}

                for c in candidates:
                    if c.student_id:
                        cand_map_by_student_id[c.student_id] = c
                    if c.student_code:
                        cand_map_by_code[str(c.student_code).strip()] = c
                    if c.candidate_name_kh:
                        cand_map_by_name[c.candidate_name_kh.strip()] = c

                for s in students:
                    cand = (
                        cand_map_by_student_id.get(s.id) or
                        cand_map_by_code.get(str(s.student_id).strip()) or
                        cand_map_by_name.get(s.khmer_name.strip())
                    )
                    if cand:
                        score_val = cand.average_score if (cand.average_score and cand.average_score > 0) else cand.total_score
                        score_val = Decimal(str(score_val or '0.00'))
                        detail = f"ពិន្ទុសរុប: {cand.total_score:.2f} (មធ្យមភាគ: {cand.average_score:.2f})"
                        student_scores[s.id] = {
                            'score': score_val,
                            'total_score': cand.total_score,
                            'average_score': cand.average_score,
                            'has_score': (cand.total_score > 0 or cand.average_score > 0),
                            'detail': detail,
                            'exam_rank': cand.rank_overall or 0,
                        }
                    else:
                        student_scores[s.id] = {
                            'score': Decimal('0.00'),
                            'total_score': Decimal('0.00'),
                            'average_score': Decimal('0.00'),
                            'has_score': False,
                            'detail': "មិនមានទិន្នន័យបេក្ខជនក្នុងសម័យប្រឡងនេះ",
                            'exam_rank': 0,
                        }
        # =====================================================================
        # SOURCE 2: Previous Year Final Annual Scores [(S1 + S2) / 2] (ពិន្ទុចុងឆ្នាំចាស់)
        # =====================================================================
        elif score_source_type == 'PREVIOUS_YEAR_ANNUAL' and source_year_id:
            source_year = AcademicYear.objects.filter(id=source_year_id).first()
            if source_year:
                score_source_title = f"ពិន្ទុចុងឆ្នាំចាស់ [(ឆ.១ + ឆ.២)/២] ({source_year.name})"
                source_grade = (grade_level - 1) if grade_level > 7 else 7

                # Pre-calculate annual results for all classrooms of source_grade in source_year
                source_classrooms = list(Classroom.objects.filter(academic_year=source_year, grade_level=source_grade))
                classroom_annual_cache = {}

                for s_cls in source_classrooms:
                    try:
                        res = AcademicResultService.compute_annual_results(s_cls, source_year)
                        for item in res.get('students_data', []):
                            st = item.get('student')
                            if st:
                                classroom_annual_cache[st.id] = item
                                if st.student_id:
                                    classroom_annual_cache[str(st.student_id).strip()] = item
                    except Exception:
                        pass

                # Also pre-fetch transfer grades in source year
                transfer_grades_map = {}
                for tg in StudentTransferGrade.objects.filter(academic_year=source_year):
                    transfer_grades_map.setdefault(tg.student_id, []).append(tg)

                for s in students:
                    cached_item = classroom_annual_cache.get(s.id) or classroom_annual_cache.get(str(s.student_id).strip())
                    if cached_item:
                        ann_avg = cached_item.get('annual_average') or Decimal('0.00')
                        s1_avg = cached_item.get('s1_average')
                        s2_avg = cached_item.get('s2_average')
                        s1_str = f"{s1_avg:.2f}" if s1_avg is not None else "-"
                        s2_str = f"{s2_avg:.2f}" if s2_avg is not None else "-"
                        detail = f"ឆ.១: {s1_str} + ឆ.២: {s2_str} => មធ្យមភាគប្រចាំឆ្នាំ: {ann_avg:.2f}"
                        student_scores[s.id] = {
                            'score': ann_avg,
                            'total_score': ann_avg,
                            'average_score': ann_avg,
                            'has_score': cached_item.get('has_record', True),
                            'detail': detail,
                            'exam_rank': cached_item.get('rank', 0),
                        }
                    else:
                        # Check transfer grades
                        tg_list = transfer_grades_map.get(s.id, [])
                        if tg_list:
                            sem_avgs = [tg.semester_final_average for tg in tg_list if tg.semester_final_average is not None]
                            if sem_avgs:
                                ann_avg = round(sum(sem_avgs) / Decimal(str(len(sem_avgs))), 2)
                                detail = f"ពិន្ទុផ្ទេរ (Transfer): {ann_avg:.2f}"
                                student_scores[s.id] = {
                                    'score': ann_avg,
                                    'total_score': ann_avg,
                                    'average_score': ann_avg,
                                    'has_score': True,
                                    'detail': detail,
                                    'exam_rank': 0,
                                }
                                continue
                        # No previous record found in source year
                        student_scores[s.id] = {
                            'score': Decimal('0.00'),
                            'total_score': Decimal('0.00'),
                            'average_score': Decimal('0.00'),
                            'has_score': False,
                            'detail': f"គ្មានទិន្នន័យពិន្ទុចុងឆ្នាំក្នុងឆ្នាំសិក្សា {source_year.name}",
                            'exam_rank': 0,
                        }
        else:
            score_source_title = "ពិន្ទុលំនាំដើម / តាមអក្ខរក្រម"
            for s in students:
                student_scores[s.id] = {
                    'score': Decimal('0.00'),
                    'total_score': Decimal('0.00'),
                    'average_score': Decimal('0.00'),
                    'has_score': False,
                    'detail': "រៀបតាមលំដាប់អក្ខរក្រម/កូដសិស្ស",
                    'exam_rank': 0,
                }

        # Build combined student list
        students_data = []
        for s in students:
            score_meta = student_scores.get(s.id, {
                'score': Decimal('0.00'),
                'total_score': Decimal('0.00'),
                'average_score': Decimal('0.00'),
                'has_score': False,
                'detail': '',
                'exam_rank': 0,
            })
            students_data.append({
                'id': s.id,
                'student_id': s.student_id,
                'khmer_name': s.khmer_name,
                'latin_name': s.latin_name or '',
                'gender': s.gender,
                'gender_display': 'ស្រី' if s.gender == 'F' else 'ប្រុស',
                'current_class_id': s.classroom_id,
                'current_class_name': s.classroom.name if s.classroom else 'មិនទាន់មានថ្នាក់',
                'score': score_meta['score'],
                'total_score': score_meta['total_score'],
                'average_score': score_meta['average_score'],
                'has_score': score_meta['has_score'],
                'score_detail': score_meta['detail'],
                'score_source_type': score_source_type,
            })

        # Sort students descending from Highest Score to Lowest Score (ពិន្ទុខ្ពស់មកទាប)
        students_data.sort(key=lambda x: (
            -(float(x['score']) if x['score'] is not None else 0.0),
            0 if x['has_score'] else 1,
            x['khmer_name']
        ))

        # Assign Overall Rank
        current_rank = 1
        for idx, item in enumerate(students_data):
            if idx > 0:
                prev = students_data[idx - 1]
                if prev['score'] == item['score'] and item['has_score']:
                    item['rank'] = prev['rank']
                else:
                    item['rank'] = idx + 1
            else:
                item['rank'] = 1

        return {
            'students': students_data,
            'total_students': len(students_data),
            'scored_students_count': sum(1 for s in students_data if s['has_score']),
            'score_source_title': score_source_title,
        }

    @staticmethod
    def distribute_students_to_classrooms(students, target_classrooms, strategy='TOP_DOWN', capacities=None):
        """
        Distributes sorted students into target classrooms using selected strategy:
        1. 'TOP_DOWN' (រៀបពីពិន្ទុខ្ពស់មកទាបតាមលំដាប់ថ្នាក់ 7A, 7B, 7C...)
        2. 'BALANCED_SNAKE' (បែងចែកស្មើដៃគ្នាតាមលំដាប់ពិន្ទុ Serpentine)
        3. 'GENDER_BALANCED' (បែងចែកស្មើដៃគ្នាតាមពិន្ទុ និងសមាមាត្រស្រី-ប្រុស)
        """
        if not target_classrooms or not students:
            return {
                'classroom_buckets': [],
                'summary': {
                    'total_students': len(students),
                    'total_classes': len(target_classrooms),
                }
            }

        num_classes = len(target_classrooms)
        capacities = capacities or {}

        # Prepare bucket structures for each classroom
        buckets = []
        for tc in target_classrooms:
            cap = capacities.get(tc['id']) or tc.get('capacity') or 45
            buckets.append({
                'classroom_id': tc['id'],
                'classroom_name': tc['name'],
                'classroom_code': tc.get('code', tc['name']),
                'grade_level': tc.get('grade_level'),
                'track': tc.get('track', 'GENERAL'),
                'capacity': cap,
                'students': [],
            })

        # =====================================================================
        # STRATEGY 1: TOP_DOWN (ពិន្ទុខ្ពស់មកទាបតាមលំដាប់ថ្នាក់)
        # =====================================================================
        if strategy == 'TOP_DOWN':
            # Even quota or capacity based
            total_students = len(students)
            base_quota = total_students // num_classes
            extra = total_students % num_classes

            quotas = []
            for i in range(num_classes):
                q = base_quota + (1 if i < extra else 0)
                quotas.append(q)

            cur_idx = 0
            for i, b in enumerate(buckets):
                quota = quotas[i]
                assigned_chunk = students[cur_idx:cur_idx + quota]
                for s in assigned_chunk:
                    s_copy = dict(s)
                    s_copy['target_classroom_id'] = b['classroom_id']
                    s_copy['target_classroom_name'] = b['classroom_name']
                    b['students'].append(s_copy)
                cur_idx += quota

        # =====================================================================
        # STRATEGY 2: BALANCED_SNAKE (បែងចែកស្មើដៃគ្នាតាមលំដាប់ពិន្ទុ Serpentine)
        # =====================================================================
        elif strategy == 'BALANCED_SNAKE':
            forward = True
            bucket_idx = 0
            for s in students:
                b = buckets[bucket_idx]
                s_copy = dict(s)
                s_copy['target_classroom_id'] = b['classroom_id']
                s_copy['target_classroom_name'] = b['classroom_name']
                b['students'].append(s_copy)

                if forward:
                    if bucket_idx == num_classes - 1:
                        forward = False
                    else:
                        bucket_idx += 1
                else:
                    if bucket_idx == 0:
                        forward = True
                    else:
                        bucket_idx -= 1

        # =====================================================================
        # STRATEGY 3: GENDER_BALANCED (ស្មើដៃទាំងពិន្ទុ និងសមាមាត្រស្រី-ប្រុស)
        # =====================================================================
        elif strategy == 'GENDER_BALANCED':
            females = [s for s in students if s['gender'] == 'F']
            males = [s for s in students if s['gender'] != 'F']

            for group in [females, males]:
                forward = True
                bucket_idx = 0
                for s in group:
                    b = buckets[bucket_idx]
                    s_copy = dict(s)
                    s_copy['target_classroom_id'] = b['classroom_id']
                    s_copy['target_classroom_name'] = b['classroom_name']
                    b['students'].append(s_copy)

                    if forward:
                        if bucket_idx == num_classes - 1:
                            forward = False
                        else:
                            bucket_idx += 1
                    else:
                        if bucket_idx == 0:
                            forward = True
                        else:
                            bucket_idx -= 1

        # Compute per-bucket metrics
        for b in buckets:
            b_students = b['students']
            b['total_students'] = len(b_students)
            b['female_count'] = sum(1 for s in b_students if s['gender'] == 'F')
            b['male_count'] = sum(1 for s in b_students if s['gender'] != 'F')
            b['female_percentage'] = round((b['female_count'] / b['total_students'] * 100), 1) if b['total_students'] > 0 else 0.0

            scored_in_b = [s['score'] for s in b_students if s.get('has_score')]
            if scored_in_b:
                b['average_score'] = round(sum(scored_in_b) / Decimal(str(len(scored_in_b))), 2)
                b['max_score'] = max(scored_in_b)
                b['min_score'] = min(scored_in_b)
            else:
                b['average_score'] = Decimal('0.00')
                b['max_score'] = Decimal('0.00')
                b['min_score'] = Decimal('0.00')

            # Sort bucket students by Rank within the classroom
            b['students'].sort(key=lambda x: (x.get('rank', 9999), x['khmer_name']))
            for idx, s in enumerate(b['students'], 1):
                s['rank_in_class'] = idx

        overall_avg = Decimal('0.00')
        all_scored = [s['score'] for s in students if s.get('has_score')]
        if all_scored:
            overall_avg = round(sum(all_scored) / Decimal(str(len(all_scored))), 2)

        return {
            'classroom_buckets': buckets,
            'summary': {
                'total_students': len(students),
                'total_classes': num_classes,
                'overall_average_score': overall_avg,
                'strategy': strategy,
            }
        }

    @staticmethod
    def apply_classroom_allocation(allocations_list, target_academic_year, user=None, audit_reason="បែងចែកថ្នាក់រៀនតាមពិន្ទុ"):
        """
        Executes the final classroom allocation atomically:
        - Updates Student.classroom and Student.academic_year
        - Logs audit trail in StudentPromotionRecord
        """
        if not allocations_list:
            return {'status': 'error', 'message': 'គ្មានទិន្នន័យបែងចែកថ្នាក់ឡើយ'}

        updated_count = 0
        with transaction.atomic():
            for item in allocations_list:
                s_id = item.get('student_id')
                target_cls_id = item.get('target_classroom_id')
                custom_score = item.get('score', 0)
                rank_val = item.get('rank', 0)

                if not s_id or not target_cls_id:
                    continue

                student = Student.objects.filter(id=s_id).first()
                target_cls = Classroom.objects.filter(id=target_cls_id).first()

                if not student or not target_cls:
                    continue

                old_class = student.classroom
                old_year = student.academic_year

                # Update Student
                student.classroom = target_cls
                student.academic_year = target_academic_year
                student.last_promotion_status = f"បែងចែកទៅ {target_cls.name}"
                student.last_promotion_reason = f"{audit_reason} (ពិន្ទុ: {custom_score}, ចំណាត់ថ្នាក់: {rank_val})"
                student.save(update_fields=['classroom', 'academic_year', 'last_promotion_status', 'last_promotion_reason'])

                # Log Audit Trail
                action_type = StudentPromotionRecord.Action.TRANSFER
                if old_class and target_cls.grade_level > old_class.grade_level:
                    action_type = StudentPromotionRecord.Action.PROMOTE

                StudentPromotionRecord.objects.create(
                    student=student,
                    from_academic_year=old_year,
                    to_academic_year=target_academic_year,
                    from_classroom=old_class,
                    to_classroom=target_cls,
                    action=action_type,
                    standard_reason=StudentPromotionRecord.StandardReason.PASSED_YEAR,
                    custom_notes=f"{audit_reason} (ពិន្ទុ: {custom_score}, ចំណាត់ថ្នាក់: {rank_val})",
                    processed_by=user
                )
                updated_count += 1

        return {
            'status': 'success',
            'updated_count': updated_count,
            'message': f"🎉 ជោគជ័យ! បានធ្វើបច្ចុប្បន្នភាពបែងចែកសិស្សចំនួន {updated_count} នាក់ ទៅកាន់ថ្នាក់រៀនថ្មីដោយជោគជ័យ!"
        }

    @staticmethod
    def export_allocation_to_excel(preview_result, grade_level, academic_year_name, score_source_title):
        """
        Generates an official Cambodian School Excel Workbook (.xlsx) of the classroom allocation.
        Contains:
        - Sheet 1: Master Summary (តារាងសង្ខេបការបែងចែកថ្នាក់គ្រប់ថ្នាក់)
        - Following Sheets: Individual Class Lists (បញ្ជីឈ្មោះសិស្សតាមថ្នាក់នីមួយៗ)
        """
        import openpyxl
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        from openpyxl.utils import get_column_letter

        wb = openpyxl.Workbook()
        # Default active sheet
        ws_master = wb.active
        ws_master.title = f"សង្ខេបបែងចែក ថ្នាក់ទី{grade_level}"

        # Styles
        font_header_kh = Font(name='Khmer OS Siemreap', size=14, bold=True, color='1E3A8A')
        font_sub_kh = Font(name='Khmer OS Siemreap', size=11, bold=True, color='475569')
        font_table_hdr = Font(name='Khmer OS Siemreap', size=10, bold=True, color='FFFFFF')
        font_data = Font(name='Khmer OS Siemreap', size=10)
        font_bold = Font(name='Khmer OS Siemreap', size=10, bold=True)

        fill_hdr = PatternFill(start_color='1E3A8A', end_color='1E3A8A', fill_type='solid')
        fill_sub_hdr = PatternFill(start_color='3B82F6', end_color='3B82F6', fill_type='solid')
        fill_zebra = PatternFill(start_color='F8FAFC', end_color='F8FAFC', fill_type='solid')
        
        border_thin = Border(
            left=Side(style='thin', color='CBD5E1'),
            right=Side(style='thin', color='CBD5E1'),
            top=Side(style='thin', color='CBD5E1'),
            bottom=Side(style='thin', color='CBD5E1')
        )

        align_center = Alignment(horizontal='center', vertical='center')
        align_left = Alignment(horizontal='left', vertical='center')
        align_right = Alignment(horizontal='right', vertical='center')

        # ---------------------------------------------------------------------
        # SHEET 1: Master Summary Sheet
        # ---------------------------------------------------------------------
        ws_master.merge_cells('A1:G1')
        ws_master['A1'] = f"តារាងសង្ខេបការបែងចែកថ្នាក់រៀនសិស្ស ថ្នាក់ទី {grade_level}"
        ws_master['A1'].font = font_header_kh
        ws_master['A1'].alignment = align_center

        ws_master.merge_cells('A2:G2')
        ws_master['A2'] = f"ឆ្នាំសិក្សា {academic_year_name} | ប្រភពពិន្ទុ៖ {score_source_title}"
        ws_master['A2'].font = font_sub_kh
        ws_master['A2'].alignment = align_center

        headers_master = [
            'ល.រ', 'ថ្នាក់រៀនគោលដៅ', 'ជំនាញ/Track', 'សិស្សសរុប', 'ស្រី', 'ភាគរយស្រី (%)', 'ពិន្ទុមធ្យមភាគថ្នាក់'
        ]
        ws_master.append([])
        ws_master.append(headers_master)
        hdr_row = 4
        for col_num, h in enumerate(headers_master, 1):
            c = ws_master.cell(row=hdr_row, column=col_num)
            c.font = font_table_hdr
            c.fill = fill_hdr
            c.alignment = align_center
            c.border = border_thin

        buckets = preview_result.get('classroom_buckets', [])
        total_all_stu = 0
        total_all_fem = 0

        for idx, b in enumerate(buckets, 1):
            row_vals = [
                idx,
                b['classroom_name'],
                b.get('track', 'GENERAL'),
                b['total_students'],
                b['female_count'],
                f"{b['female_percentage']:.1f}%",
                f"{b['average_score']:.2f}"
            ]
            ws_master.append(row_vals)
            r_idx = hdr_row + idx
            for col_idx in range(1, 8):
                cell = ws_master.cell(row=r_idx, column=col_idx)
                cell.font = font_data
                cell.border = border_thin
                if col_idx in [1, 3, 4, 5, 6, 7]:
                    cell.alignment = align_center
                else:
                    cell.alignment = align_left
                if idx % 2 == 0:
                    cell.fill = fill_zebra

            total_all_stu += b['total_students']
            total_all_fem += b['female_count']

        # Total Row
        tot_row_idx = hdr_row + len(buckets) + 1
        ws_master.append([
            'សរុបរួម', '', '', total_all_stu, total_all_fem,
            f"{(total_all_fem / total_all_stu * 100):.1f}%" if total_all_stu > 0 else "0.0%",
            f"{preview_result.get('summary', {}).get('overall_average_score', 0):.2f}"
        ])
        ws_master.merge_cells(start_row=tot_row_idx, start_column=1, end_row=tot_row_idx, end_column=3)
        for col_idx in range(1, 8):
            c = ws_master.cell(row=tot_row_idx, column=col_idx)
            c.font = font_bold
            c.border = border_thin
            c.alignment = align_center

        for col in ws_master.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws_master.column_dimensions[col_letter].width = max(max_len + 5, 14)

        # ---------------------------------------------------------------------
        # INDIVIDUAL CLASS SHEETS
        # ---------------------------------------------------------------------
        for b in buckets:
            sheet_title = re.sub(r'[\/:*?"<>|]', '_', b['classroom_name'])[:30]
            ws_cls = wb.create_sheet(title=sheet_title)

            ws_cls.merge_cells('A1:H1')
            ws_cls['A1'] = f"បញ្ជីរាយនាមសិស្ស {b['classroom_name']} ឆ្នាំសិក្សា {academic_year_name}"
            ws_cls['A1'].font = font_header_kh
            ws_cls['A1'].alignment = align_center

            ws_cls.merge_cells('A2:H2')
            ws_cls['A2'] = f"សិស្សសរុប៖ {b['total_students']} នាក់ (ស្រី {b['female_count']} នាក់) | ពិន្ទុមធ្យមភាគ៖ {b['average_score']:.2f} | ប្រភពពិន្ទុ៖ {score_source_title}"
            ws_cls['A2'].font = font_sub_kh
            ws_cls['A2'].alignment = align_center

            ws_cls.append([])
            cls_headers = [
                'ល.រ ក្នុងថ្នាក់', 'ចំណាត់ថ្នាក់ទូទៅ', 'អត្តលេខសិស្ស', 'គោត្តនាម និងនាម', 'ភេទ', 'ថ្នាក់ដើម/ចាស់', 'ពិន្ទុទទួលបាន', 'កំណត់សម្គាល់ពិន្ទុ'
            ]
            ws_cls.append(cls_headers)
            c_hdr_row = 4
            for col_num, h in enumerate(cls_headers, 1):
                c = ws_cls.cell(row=c_hdr_row, column=col_num)
                c.font = font_table_hdr
                c.fill = fill_sub_hdr
                c.alignment = align_center
                c.border = border_thin

            for s_idx, s in enumerate(b['students'], 1):
                row_vals = [
                    s_idx,
                    s.get('rank', s_idx),
                    s.get('student_id', ''),
                    s.get('khmer_name', ''),
                    s.get('gender_display', 'ប្រុស'),
                    s.get('current_class_name', ''),
                    f"{s.get('score', 0):.2f}",
                    s.get('score_detail', '')
                ]
                ws_cls.append(row_vals)
                r_pos = c_hdr_row + s_idx
                for col_idx in range(1, 9):
                    cell = ws_cls.cell(row=r_pos, column=col_idx)
                    cell.font = font_data
                    cell.border = border_thin
                    if col_idx in [1, 2, 3, 5, 7]:
                        cell.alignment = align_center
                    else:
                        cell.alignment = align_left
                    if s_idx % 2 == 0:
                        cell.fill = fill_zebra

            for col in ws_cls.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = get_column_letter(col[0].column)
                ws_cls.column_dimensions[col_letter].width = max(max_len + 4, 12)

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output.getvalue()
