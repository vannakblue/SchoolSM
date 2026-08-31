from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db import transaction
from django.db.models import Count, Q, Avg, Max, Min, Sum
from decimal import Decimal
import json
import datetime
from django.utils import timezone
import openpyxl
from io import BytesIO
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

from apps.accounts.decorators import role_required
from apps.accounts.utils import send_telegram_notification
from .models import (
    ExamTerm, Grade,
    StandardizedExam, ExamRoom, ExamSubject, ExamCandidate, CandidateSubjectScore,
    ExamRoomSubjectCode, ExamStudentExclusion
)
from .forms import ExamTermForm, StandardizedExamForm

from apps.academics.models import Classroom, Subject, AcademicYear, GradeLevelRule
from apps.students.models import Student

@login_required
def exam_term_list(request):
    from apps.academics.utils import get_active_academic_year
    active_year = get_active_academic_year(request)
    selected_year = request.GET.get('year') or request.GET.get('academic_year')
    if selected_year:
        if selected_year == 'all':
            active_year = None
        elif str(selected_year).isdigit():
            found_year = AcademicYear.objects.filter(id=int(selected_year)).first()
            if found_year:
                active_year = found_year

    terms = ExamTerm.objects.select_related('academic_year').all()
    if active_year:
        terms = terms.filter(academic_year=active_year)
    academic_years = AcademicYear.objects.all().order_by('-start_date')
    return render(request, 'examinations/exam_term_list.html', {
        'terms': terms,
        'academic_years': academic_years,
        'active_year': active_year,
        'selected_year': str(active_year.id) if active_year else '',
    })


@login_required
@role_required(['ADMIN'])
def exam_term_create(request):
    from apps.academics.utils import get_active_academic_year
    active_year = get_active_academic_year(request)
    if request.method == 'POST':
        form = ExamTermForm(request.POST)
        if form.is_valid():
            term = form.save()
            messages.success(request, f"បានបង្កើតសម័យប្រឡង {term.name} ជោគជ័យ!")
            return redirect('exam_term_list')
    else:
        form = ExamTermForm(initial={'academic_year': active_year})
    return render(request, 'examinations/exam_term_form.html', {'form': form, 'title': 'បង្កើតសម័យប្រឡងថ្មី / Create Exam Term'})


@login_required
@role_required(['ADMIN'])
def exam_term_edit(request, term_id):
    term = get_object_or_404(ExamTerm, id=term_id)
    if request.method == 'POST':
        form = ExamTermForm(request.POST, instance=term)
        if form.is_valid():
            term = form.save()
            messages.success(request, f"បានកែប្រែសម័យប្រឡង «{term.name}» ដោយជោគជ័យ!")
            return redirect('exam_term_list')
    else:
        form = ExamTermForm(instance=term)
    return render(request, 'examinations/exam_term_form.html', {
        'form': form,
        'term': term,
        'title': f'កែប្រែសម័យប្រឡង៖ {term.name}',
        'is_edit': True
    })


@login_required
@role_required(['ADMIN'])
def exam_term_delete(request, term_id):
    term = get_object_or_404(ExamTerm, id=term_id)
    if request.method == 'POST':
        name = term.name
        term.delete()
        messages.success(request, f"បានលុបសម័យប្រឡង «{name}» ដោយជោគជ័យ!")
        return redirect('exam_term_list')
    return redirect('exam_term_list')



@login_required
@role_required(['ADMIN', 'TEACHER'])
def grade_entry_matrix(request):
    """
    Rapid score entry grid for all students in a classroom across the exact subjects and max scores defined for that grade level & track.
    Strictly isolated per Academic Year!
    Enforces active student exam restrictions, Teacher Assigned Subject filters, and Admin grading deadline windows.
    """
    from apps.academics.utils import get_active_academic_year
    from apps.academics.models import ClassSubject
    active_year = get_active_academic_year(request)
    is_admin = request.user.is_superuser or getattr(request.user, 'role', '') == 'ADMIN'
    teacher_profile = getattr(request.user, 'teacher_profile', None) if not is_admin else None

    terms = ExamTerm.objects.filter(academic_year=active_year) if active_year else ExamTerm.objects.all()
    all_classrooms = Classroom.objects.filter(academic_year=active_year).order_by('grade_level', 'code') if active_year else Classroom.objects.all().order_by('grade_level', 'code')

    selected_term_id = request.GET.get('term') or request.POST.get('term') or str(terms.first().id if terms.first() else '')
    selected_class_id = request.GET.get('classroom') or request.POST.get('classroom') or str(classrooms.first().id if classrooms.first() else '')
    selected_subject_id = request.GET.get('subject') or request.POST.get('subject') or ''

    selected_term = ExamTerm.objects.filter(id=selected_term_id).first() if (selected_term_id and str(selected_term_id).isdigit()) else terms.first()
    selected_class = Classroom.objects.filter(id=selected_class_id).first() if (selected_class_id and str(selected_class_id).isdigit()) else classrooms.first()

    effective_year = selected_term.academic_year if selected_term else active_year

    # Teacher assigned classes and subjects filtering
    teacher_assigned_classes = set()
    teacher_assigned_subjects = set()
    homeroom_cls_ids = set()
    if teacher_profile:
        cs_qs = ClassSubject.objects.filter(teacher=teacher_profile)
        if effective_year:
            cs_qs = cs_qs.filter(classroom__academic_year=effective_year)
        teacher_assigned_classes = set(cs_qs.values_list('classroom_id', flat=True))
        teacher_assigned_subjects = set(cs_qs.values_list('subject_id', flat=True))
        # Add homeroom classroom
        homeroom_cls_ids = set(Classroom.objects.filter(homeroom_teacher=teacher_profile).values_list('id', flat=True))
        teacher_assigned_classes.update(homeroom_cls_ids)
        
        # Filter classrooms list to only assigned classes for this teacher
        classrooms = all_classrooms.filter(id__in=teacher_assigned_classes) if teacher_assigned_classes else all_classrooms
    else:
        classrooms = all_classrooms

    subject_rules = []
    students = []
    matrix_data = []
    excluded_students_map = {}
    is_grading_open = True
    grading_status_msg = "កំពុងបើកដំណើរការបញ្ចូលពិន្ទុ"

    if selected_term:
        is_grading_open, _, grading_status_msg = selected_term.get_grading_status()

    if selected_term and selected_class:
        # Load specific subject rules for this classroom's grade_level & track
        rules_qs = selected_class.get_subject_rules()
        if rules_qs.exists():
            subject_rules = list(rules_qs)
        else:
            # Fallback to all subjects if no custom rules set
            for s in Subject.objects.all():
                subject_rules.append(GradeLevelRule(grade_level=selected_class.grade_level, track=selected_class.track, subject=s, max_score=Decimal('100.00')))

        # If a specific subject is filtered
        if selected_subject_id and str(selected_subject_id).isdigit():
            subject_rules = [r for r in subject_rules if r.subject_id == int(selected_subject_id)]
        elif teacher_profile and teacher_assigned_subjects and not teacher_profile.current_duty.startswith('នាយក'):
            # Highlight teacher's assigned subjects or filter if preferred
            pass

        # Find all active exclusions for this term or month
        term_month = selected_term.start_date.month if selected_term.start_date else None
        exclusions_qs = ExamStudentExclusion.objects.filter(
            academic_year=selected_term.academic_year,
            is_active=True
        ).filter(
            Q(exam_term=selected_term) | (Q(month=term_month) if term_month else Q())
        ).select_related('student')

        for exc in exclusions_qs:
            excluded_students_map[exc.student_id] = exc

        # All students in classroom (active ones primarily, plus any existing students)
        students = Student.objects.filter(classroom=selected_class).order_by('student_id')
        
        existing_grades = {
            (g.student_id, g.subject_id): g
            for g in Grade.objects.filter(classroom=selected_class, exam_term=selected_term)
        }

        if request.method == 'POST':
            # Block saving if grading window is closed for regular teachers
            if not is_grading_open and not is_admin:
                messages.error(request, f"⚠️ មិនអាចរក្សាទុកបានទេ៖ {grading_status_msg}!")
                return redirect(f"/examinations/matrix/?term={selected_term.id}&classroom={selected_class.id}{f'&subject={selected_subject_id}' if selected_subject_id else ''}")

            saved_count = 0
            blocked_count = 0
            for student in students:
                is_student_excluded = (student.id in excluded_students_map) or (student.status != 'ACTIVE') or getattr(student, 'is_exam_suspended', False)
                
                # Non-admin cannot submit/modify positive scores for excluded/missed students
                if is_student_excluded and not is_admin:
                    blocked_count += 1
                    continue

                for rule in subject_rules:
                    subject = rule.subject
                    
                    # If teacher is not admin, only allow saving subjects they teach (or all in classroom if homeroom)
                    if teacher_profile and teacher_assigned_subjects and (subject.id not in teacher_assigned_subjects) and (selected_class.id not in homeroom_cls_ids):
                        continue

                    field_name = f"score_{student.id}_{subject.id}"
                    score_val = request.POST.get(field_name, '').strip()
                    if score_val != '':
                        try:
                            score_num = Decimal(score_val)
                            # Ensure score is within valid bounds
                            if score_num > rule.max_score:
                                score_num = rule.max_score
                            if score_num < Decimal('0.00'):
                                score_num = Decimal('0.00')

                            Grade.objects.update_or_create(
                                student=student,
                                subject=subject,
                                exam_term=selected_term,
                                classroom=selected_class,
                                defaults={
                                    'score': score_num,
                                    'max_score': rule.max_score
                                }
                            )
                            saved_count += 1
                        except (ValueError, Exception):
                            pass
                    elif is_student_excluded and is_admin:
                        # Admin can explicitly zero out score
                        pass

            if blocked_count > 0:
                messages.warning(request, f"⚠️ មានសិស្សចំនួន {blocked_count} នាក់ជាសិស្សផ្អាក/ឈប់រៀន ឬត្រូវបានលើកលែងមិនឱ្យប្រឡង ដែលមានតែ Admin ប៉ុណ្ណោះដែលអាចកែប្រែពិន្ទុបាន!")
            messages.success(request, f"🎉 បានរក្សាទុកពិន្ទុសិស្សថ្នាក់ {selected_class.name} ចំនួន {saved_count} មុខវិជ្ជាជោគជ័យ!")
            return redirect(f"/examinations/matrix/?term={selected_term.id}&classroom={selected_class.id}{f'&subject={selected_subject_id}' if selected_subject_id else ''}")

        for student in students:
            is_excluded = (student.id in excluded_students_map) or (student.status != 'ACTIVE') or getattr(student, 'is_exam_suspended', False)
            exc_obj = excluded_students_map.get(student.id)
            if getattr(student, 'is_exam_suspended', False):
                exc_reason = student.get_exam_suspension_reason_display()
            elif exc_obj:
                exc_reason = exc_obj.get_reason_display()
            elif student.status != 'ACTIVE':
                exc_reason = student.get_status_display()
            else:
                exc_reason = ''

            row_scores = []
            for rule in subject_rules:
                g = existing_grades.get((student.id, rule.subject_id))
                
                # If student is excluded and has no grade record, score defaults to 0.00
                display_score = ''
                display_letter = ''
                if g:
                    display_score = g.score
                    display_letter = g.grade_letter
                elif is_excluded:
                    display_score = '0.00'
                    display_letter = 'F'

                can_edit_subject = (is_admin or is_grading_open) and (
                    is_admin or not teacher_profile or (rule.subject_id in teacher_assigned_subjects) or (selected_class.id in homeroom_cls_ids)
                )

                row_scores.append({
                    'subject': rule.subject,
                    'max_score': rule.max_score,
                    'score': display_score,
                    'grade_letter': display_letter,
                    'can_edit_subject': can_edit_subject and not is_excluded,
                })
            matrix_data.append({
                'student': student,
                'is_excluded': is_excluded,
                'exclusion_reason': exc_reason,
                'can_edit': (is_admin or is_grading_open) and (is_admin or not is_excluded),
                'scores': row_scores
            })

    # All subjects for quick subject filter
    all_subjects = Subject.objects.exclude(code__in=['R', 'D']).order_by('order', 'id')

    return render(request, 'examinations/grade_matrix.html', {
        'terms': terms,
        'classrooms': classrooms,
        'all_subjects': all_subjects,
        'selected_term': selected_term,
        'selected_class': selected_class,
        'selected_subject_id': selected_subject_id,
        'subject_rules': subject_rules,
        'matrix_data': matrix_data,
        'active_year': active_year,
        'is_grading_open': is_grading_open,
        'grading_status_msg': grading_status_msg,
    })


@login_required
def grade_summary_view(request):
    """
    Computes and ranks all students in a class based on Cambodian scoring rules:
    Total Score / Total Max Score, Percentage %, Letter Grade, and Class Rank.
    Strictly isolated per Academic Year!
    """
    from apps.academics.utils import get_active_academic_year
    active_year = get_active_academic_year(request)

    terms = ExamTerm.objects.filter(academic_year=active_year) if active_year else ExamTerm.objects.all()
    classrooms = Classroom.objects.filter(academic_year=active_year).order_by('grade_level', 'code') if active_year else Classroom.objects.all().order_by('grade_level', 'code')

    selected_term_id = request.GET.get('term', str(terms.first().id if terms.first() else ''))
    selected_class_id = request.GET.get('classroom', str(classrooms.first().id if classrooms.first() else ''))

    selected_term = terms.filter(id=selected_term_id).first() if selected_term_id else None
    selected_class = classrooms.filter(id=selected_class_id).first() if selected_class_id else None

    subject_rules = []
    summary_results = []
    total_class_max = Decimal('0.00')

    if selected_term and selected_class:
        rules_qs = selected_class.get_subject_rules()
        if rules_qs.exists():
            subject_rules = list(rules_qs)
        else:
            for s in Subject.objects.all():
                subject_rules.append(GradeLevelRule(grade_level=selected_class.grade_level, track=selected_class.track, subject=s, max_score=Decimal('100.00')))

        total_class_max = sum(r.max_score for r in subject_rules)

        students = Student.objects.filter(classroom=selected_class, status='ACTIVE').order_by('student_id')
        
        grades_map = {}
        for g in Grade.objects.filter(classroom=selected_class, exam_term=selected_term):
            grades_map[(g.student_id, g.subject_id)] = g

        student_ranks = []
        for student in students:
            total_score = Decimal('0.00')
            subject_details = []

            for rule in subject_rules:
                sub = rule.subject
                grade_obj = grades_map.get((student.id, sub.id))
                if grade_obj:
                    score = grade_obj.score
                    total_score += score
                    subject_details.append({'subject': sub, 'score': score, 'max_score': rule.max_score, 'letter': grade_obj.grade_letter})
                else:
                    subject_details.append({'subject': sub, 'score': None, 'max_score': rule.max_score, 'letter': '-'})

            # Calculate percentage & MoEYS Letter Grade
            percentage = round((float(total_score) / float(total_class_max)) * 100, 2) if total_class_max > 0 else 0.0
            
            if percentage >= 90:
                letter = 'A'
            elif percentage >= 80:
                letter = 'B'
            elif percentage >= 70:
                letter = 'C'
            elif percentage >= 60:
                letter = 'D'
            elif percentage >= 50:
                letter = 'E'
            else:
                letter = 'F'

            student_ranks.append({
                'student': student,
                'subject_details': subject_details,
                'total_score': total_score,
                'total_max': total_class_max,
                'percentage': percentage,
                'letter': letter,
                'passed': percentage >= 50.0,
            })

        # Sort descending by total_score / percentage to determine Rank
        student_ranks.sort(key=lambda x: x['total_score'], reverse=True)
        for idx, item in enumerate(student_ranks, 1):
            item['rank'] = idx
            summary_results.append(item)

    # Handle telegram alert broadcast
    if request.method == 'POST' and 'broadcast_results' in request.POST and selected_term and selected_class:
        count = 0
        for item in summary_results:
            stu = item['student']
            msg = (
                f"សួស្តីលោក/លោកស្រីអាណាព្យាបាលសិស្ស {stu.khmer_name}!\n"
                f"លទ្ធផលប្រឡង៖ {selected_term.name}\n"
                f"ថ្នាក់៖ {selected_class.name}\n"
                f"📊 ពិន្ទុសរុប៖ {item['total_score']}/{item['total_max']} ({item['percentage']}%)\n"
                f"🏆 ចំណាត់ថ្នាក់ក្នុងថ្នាក់ (Rank)៖ លេខ {item['rank']} (និទ្ទេស {item['letter']})\n"
                f"លទ្ធផល៖ {'ជាប់កម្រិតមធ្យមសិក្សា' if item['passed'] else 'ធ្លាក់'}"
            )
            send_telegram_notification(
                title=f"🏆 លទ្ធផលប្រឡងសិស្ស: {stu.khmer_name}",
                message=msg,
                recipient_name=stu.father_name or stu.khmer_name,
                recipient_phone=stu.father_phone or stu.phone,
                custom_chat_id=stu.telegram_chat_id
            )
            count += 1
        messages.success(request, f"🔔 បានផ្ញើសារជូនដំណឹងលទ្ធផលប្រឡងទៅកាន់អាណាព្យាបាលសិស្ស {count} នាក់ជោគជ័យ!")
        return redirect(f"/examinations/summary/?term={selected_term.id}&classroom={selected_class.id}")

    return render(request, 'examinations/grade_summary.html', {
        'terms': terms,
        'classrooms': classrooms,
        'selected_term': selected_term,
        'selected_class': selected_class,
        'subject_rules': subject_rules,
        'total_class_max': total_class_max,
        'summary_results': summary_results,
    })


@login_required
def report_card_view(request, student_id, term_id):
    """
    Official MoEYS Academic Transcript & Report Card with accurate scoring rule breakdown
    """
    student = get_object_or_404(Student.objects.select_related('classroom', 'academic_year'), pk=student_id)
    term = get_object_or_404(ExamTerm, pk=term_id)
    classroom = student.classroom

    grades = Grade.objects.filter(student=student, exam_term=term).select_related('subject')
    
    total_score = Decimal('0.00')
    total_max = Decimal('0.00')

    for g in grades:
        total_score += g.score
        total_max += g.max_score

    # Fallback to classroom total max if needed
    if total_max == 0 and classroom:
        total_max = classroom.get_total_max_score()

    percentage = round((float(total_score) / float(total_max)) * 100, 2) if total_max > 0 else 0.0

    if percentage >= 90:
        overall_grade = 'A (ល្អប្រសើរ)'
    elif percentage >= 80:
        overall_grade = 'B (ល្អណាស់)'
    elif percentage >= 70:
        overall_grade = 'C (ល្អ)'
    elif percentage >= 60:
        overall_grade = 'D (ល្អបង្គួរ)'
    elif percentage >= 50:
        overall_grade = 'E (មធ្យម)'
    else:
        overall_grade = 'F (ធ្លាក់)'

    # Calculate class rank
    all_class_students = Student.objects.filter(classroom=classroom, status='ACTIVE') if classroom else []
    student_scores = []
    for s in all_class_students:
        s_grades = Grade.objects.filter(student=s, exam_term=term)
        s_tot = sum(g.score for g in s_grades)
        student_scores.append((s.id, s_tot))

    student_scores.sort(key=lambda x: x[1], reverse=True)
    rank = 1
    for idx, (s_id, _) in enumerate(student_scores, 1):
        if s_id == student.id:
            rank = idx
            break

    return render(request, 'examinations/report_card.html', {
        'student': student,
        'term': term,
        'classroom': classroom,
        'grades': grades,
        'total_score': total_score,
        'total_max': total_max,
        'percentage': percentage,
        'overall_grade': overall_grade,
        'rank': rank,
        'total_in_class': len(student_scores),
        'is_passed': percentage >= 50.0,
    })


from .telegram_report_card import (
    dispatch_student_report_card_to_telegram,
    generate_report_card_pdf_bytes,
    build_report_card_telegram_message
)


@login_required
def api_send_report_card_telegram(request):
    """
    AJAX Endpoint to dispatch an individual report card to Telegram as PDF, Rich message, or Both.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=400)

    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
        student_id = data.get('student_id')
        term_id = data.get('term_id')
        destination = data.get('destination', 'CLASS_GROUP')  # 'CLASS_GROUP', 'PARENT_INDIVIDUAL', 'CUSTOM_CHAT_ID'
        send_mode = data.get('send_mode', 'BOTH')  # 'PDF_ONLY', 'MESSAGE_ONLY', 'BOTH'
        custom_chat_id = data.get('custom_chat_id', '').strip() or None

        student = get_object_or_404(Student, id=student_id)
        term = get_object_or_404(ExamTerm, id=term_id)

        result = dispatch_student_report_card_to_telegram(
            student=student,
            term=term,
            destination=destination,
            send_mode=send_mode,
            custom_chat_id=custom_chat_id
        )

        return JsonResponse({
            'status': 'success',
            'message': f'បានផ្ញើប័ណ្ណពិន្ទុរបស់សិស្ស "{student.khmer_name}" ទៅកាន់ Telegram ដោយជោគជ័យ!',
            'data': result
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
def api_send_class_report_cards_telegram(request):
    """
    AJAX Endpoint to dispatch report cards for all students in a classroom to Telegram.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=400)

    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
        classroom_id = data.get('classroom_id')
        term_id = data.get('term_id')
        destination = data.get('destination', 'CLASS_GROUP')
        send_mode = data.get('send_mode', 'BOTH')
        custom_chat_id = data.get('custom_chat_id', '').strip() or None

        classroom = get_object_or_404(Classroom, id=classroom_id)
        term = get_object_or_404(ExamTerm, id=term_id)
        students = Student.objects.filter(classroom=classroom, status='ACTIVE')

        sent_count = 0
        for s in students:
            dispatch_student_report_card_to_telegram(
                student=s,
                term=term,
                destination=destination,
                send_mode=send_mode,
                custom_chat_id=custom_chat_id
            )
            sent_count += 1

        return JsonResponse({
            'status': 'success',
            'message': f'បានផ្ញើប័ណ្ណពិន្ទុសិស្សថ្នាក់ "{classroom.name}" ចំនួន {sent_count} នាក់ ទៅកាន់ Telegram ដោយជោគជ័យ!',
            'sent_count': sent_count
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


# =========================================================================
# STANDARDIZED EXAM MANAGEMENT VIEWS (ប្រព័ន្ធប្រឡងតេស្តស្តង់ដាវិទ្យាល័យ)
# =========================================================================

@login_required
def standardized_exam_list(request):
    """
    Overview list of all Standardized Exams, filterable by Academic Year and Grade Level.
    """
    from apps.academics.utils import get_active_academic_year
    active_year = get_active_academic_year(request)
    selected_year = request.GET.get('year') or request.GET.get('academic_year')
    if selected_year:
        if selected_year == 'all':
            active_year = None
        elif str(selected_year).isdigit():
            found_year = AcademicYear.objects.filter(id=int(selected_year)).first()
            if found_year:
                active_year = found_year

    selected_grade = request.GET.get('grade') or request.GET.get('grade_level')

    exams_qs = StandardizedExam.objects.select_related('academic_year').all()
    if active_year:
        exams_qs = exams_qs.filter(academic_year=active_year)
    if selected_grade and selected_grade != 'all' and selected_grade.isdigit():
        exams_qs = exams_qs.filter(grade_level=int(selected_grade))

    exams_data = []
    for ex in exams_qs:
        exams_data.append({
            'exam': ex,
            'total_candidates': ex.candidates.count(),
            'female_candidates': ex.candidates.filter(gender='F').count(),
            'total_rooms': ex.rooms.count(),
            'total_subjects': ex.exam_subjects.count(),
        })

    academic_years = AcademicYear.objects.all().order_by('-start_date')
    return render(request, 'examinations/standardized/exam_list.html', {
        'exams_data': exams_data,
        'academic_years': academic_years,
        'active_year': active_year,
        'selected_year': str(active_year.id) if active_year else '',
        'selected_grade': selected_grade or 'all',
    })



@login_required
@role_required(['ADMIN'])
def standardized_exam_create(request):
    """
    Creates a new Standardized Exam (Single or Multi-Grade Batch) and auto-populates Exam Subjects from MoEYS Grade Level Rules.
    """
    from apps.academics.utils import get_active_academic_year
    active_year = get_active_academic_year(request)

    if request.method == 'POST':
        selected_grades = request.POST.getlist('selected_grades')
        
        # If no selected_grades checkboxes (e.g. from standard single form), fallback to single grade_level
        if not selected_grades:
            single_grade = request.POST.get('grade_level')
            if single_grade and str(single_grade).isdigit():
                selected_grades = [str(single_grade)]
            else:
                selected_grades = ['12']

        base_name = request.POST.get('name', '').strip()
        academic_year_id = request.POST.get('academic_year')
        ay = AcademicYear.objects.filter(id=academic_year_id).first() if academic_year_id else active_year
        base_track = request.POST.get('track', 'ALL')
        base_session = request.POST.get('session', 'MORNING')
        base_date_str = request.POST.get('exam_date', datetime.date.today().strftime('%Y-%m-%d'))
        try:
            base_date = datetime.datetime.strptime(base_date_str, '%Y-%m-%d').date()
        except Exception:
            base_date = datetime.date.today()

        base_cpr = int(request.POST.get('candidates_per_room', '25')) if request.POST.get('candidates_per_room', '').isdigit() else 25
        base_desc = request.POST.get('description', '').strip()
        is_pub = request.POST.get('is_published') == 'on'

        created_exams = []

        with transaction.atomic():
            for g_str in selected_grades:
                if not g_str.isdigit():
                    continue
                g_val = int(g_str)

                # Read per-grade customized parameters or fallback to base
                g_name = request.POST.get(f'grade_name_{g_val}', '').strip()
                if not g_name:
                    if len(selected_grades) > 1:
                        if f'ថ្នាក់ទី {g_val}' not in base_name and f'ថ្នាក់ទី{g_val}' not in base_name:
                            g_name = f"{base_name} ថ្នាក់ទី {g_val}"
                        else:
                            g_name = base_name
                    else:
                        g_name = base_name

                g_track = request.POST.get(f'grade_track_{g_val}') or base_track
                g_session = request.POST.get(f'grade_session_{g_val}') or base_session
                g_date_str = request.POST.get(f'grade_date_{g_val}')
                if g_date_str:
                    try:
                        g_date = datetime.datetime.strptime(g_date_str, '%Y-%m-%d').date()
                    except Exception:
                        g_date = base_date
                else:
                    g_date = base_date

                g_cpr_str = request.POST.get(f'grade_cpr_{g_val}')
                g_cpr = int(g_cpr_str) if g_cpr_str and g_cpr_str.isdigit() else base_cpr

                exam = StandardizedExam.objects.create(
                    name=g_name,
                    academic_year=ay,
                    grade_level=g_val,
                    track=g_track,
                    session=g_session,
                    exam_date=g_date,
                    candidates_per_room=g_cpr,
                    description=base_desc,
                    is_published=is_pub
                )
                created_exams.append(exam)

                # Automatically populate default exam subjects based on grade_level and track
                rules = GradeLevelRule.objects.filter(grade_level=exam.grade_level)
                if exam.track != 'ALL':
                    rules = rules.filter(Q(track=exam.track) | Q(track='GENERAL'))

                seen_subjects = set()
                order_idx = 1
                for r in rules.select_related('subject').order_by('subject__order', 'id'):
                    if r.subject_id not in seen_subjects:
                        seen_subjects.add(r.subject_id)
                        coef = Decimal(str(r.subject.credit if r.subject.credit else 1))
                        ExamSubject.objects.create(
                            exam=exam,
                            subject=r.subject,
                            max_score=r.max_score or Decimal('50.00'),
                            coefficient=coef,
                            order=order_idx
                        )
                        order_idx += 1

                if not seen_subjects:
                    for s in Subject.objects.all().order_by('order', 'id')[:10]:
                        ExamSubject.objects.create(
                            exam=exam,
                            subject=s,
                            max_score=Decimal('50.00'),
                            coefficient=Decimal(str(s.credit or 1)),
                            order=order_idx
                        )
                        order_idx += 1

        if len(created_exams) == 1:
            messages.success(request, f"🎉 បានបង្កើតសម័យប្រឡងតេស្តស្តង់ដា «{created_exams[0].name}» ដោយជោគជ័យ!")
            return redirect('standardized_exam_manage', exam_id=created_exams[0].id)
        elif len(created_exams) > 1:
            grades_list_str = ", ".join([f"ថ្នាក់ទី {e.grade_level}" for e in created_exams])
            messages.success(request, f"🎉 បានបង្កើតសម័យប្រឡងតេស្តស្តង់ដាចំនួន {len(created_exams)} កម្រិតថ្នាក់ ({grades_list_str}) ដោយជោគជ័យ!")
            return redirect('standardized_exam_list')
        else:
            messages.error(request, "⚠️ សូមជ្រើសរើសយ៉ាងហោចណាស់មួយកម្រិតថ្នាក់!")
            return redirect('standardized_exam_create')
    else:
        form = StandardizedExamForm(initial={
            'academic_year': active_year,
            'grade_level': 12,
            'track': 'ALL',
            'exam_date': datetime.date.today(),
            'candidates_per_room': 25
        })

    return render(request, 'examinations/standardized/exam_form.html', {
        'form': form,
        'title': 'បង្កើតសម័យប្រឡងតេស្តស្តង់ដាថ្មី (Create Standardized Exam)',
        'is_edit': False
    })



@login_required
@role_required(['ADMIN'])
def standardized_exam_edit(request, exam_id):
    """
    Edits an existing Standardized Exam and its Exam Subjects.
    """
    exam = get_object_or_404(StandardizedExam, id=exam_id)

    if request.method == 'POST':
        form = StandardizedExamForm(request.POST, instance=exam)
        if form.is_valid():
            with transaction.atomic():
                exam = form.save()

                # Update existing exam subjects from POST fields
                for es in exam.exam_subjects.all():
                    max_s = request.POST.get(f'max_score_{es.id}')
                    coef = request.POST.get(f'coefficient_{es.id}')
                    sess = request.POST.get(f'session_{es.id}')
                    ex_date = request.POST.get(f'exam_date_{es.id}')

                    if max_s:
                        try:
                            es.max_score = Decimal(str(max_s))
                        except Exception:
                            pass
                    if coef:
                        try:
                            es.coefficient = Decimal(str(coef))
                        except Exception:
                            pass
                    if sess:
                        es.session = sess
                    if ex_date:
                        try:
                            es.exam_date = datetime.datetime.strptime(ex_date, '%Y-%m-%d').date()
                        except Exception:
                            pass
                    es.save()

            messages.success(request, f"បានកែប្រែព័ត៌មានសម័យប្រឡង «{exam.name}» ជោគជ័យ!")
            return redirect('standardized_exam_manage', exam_id=exam.id)
    else:
        form = StandardizedExamForm(instance=exam)

    subjects = exam.exam_subjects.select_related('subject').order_by('order', 'id')
    available_subjects = Subject.objects.exclude(id__in=subjects.values_list('subject_id', flat=True)).order_by('name_kh')

    return render(request, 'examinations/standardized/exam_form.html', {
        'form': form,
        'exam': exam,
        'subjects': subjects,
        'available_subjects': available_subjects,
        'title': f'កែប្រែសម័យប្រឡង៖ {exam.name}',
        'is_edit': True
    })


@login_required
@role_required(['ADMIN'])
def standardized_exam_delete(request, exam_id):
    """
    Deletes a Standardized Exam and its candidates, scores, and rooms.
    """
    exam = get_object_or_404(StandardizedExam, id=exam_id)
    if request.method == 'POST':
        name = exam.name
        exam.delete()
        messages.success(request, f"បានលុបសម័យប្រឡង «{name}» ដោយជោគជ័យ!")
        return redirect('standardized_exam_list')
    return redirect('standardized_exam_manage', exam_id=exam.id)


@login_required
def standardized_exam_manage(request, exam_id):
    """
    Central Operations Dashboard for a Standardized Exam.
    """
    exam = get_object_or_404(StandardizedExam.objects.select_related('academic_year'), id=exam_id)

    # Filtering Candidates
    candidates_qs = exam.candidates.select_related('room', 'student').order_by('room__room_number', 'desk_number', 'roll_number', 'id')
    
    room_filter = request.GET.get('room')
    gender_filter = request.GET.get('gender')
    search_q = request.GET.get('q', '').strip()

    if room_filter and room_filter.isdigit():
        candidates_qs = candidates_qs.filter(room_id=int(room_filter))
    elif room_filter == 'unassigned':
        candidates_qs = candidates_qs.filter(room__isnull=True)

    if gender_filter in ['M', 'F']:
        candidates_qs = candidates_qs.filter(gender=gender_filter)

    if search_q:
        candidates_qs = candidates_qs.filter(
            Q(candidate_name_kh__icontains=search_q) |
            Q(candidate_name_en__icontains=search_q) |
            Q(roll_number__icontains=search_q) |
            Q(origin_class__icontains=search_q) |
            Q(student_code__icontains=search_q)
        )

    rooms = exam.rooms.all().order_by('room_number')
    subjects = exam.exam_subjects.select_related('subject').order_by('order', 'id')

    total_candidates = exam.candidates.count()
    female_candidates = exam.candidates.filter(gender='F').count()
    total_rooms = rooms.count()

    total_max_score = sum(s.max_score for s in subjects)
    total_coefficients = sum(s.coefficient for s in subjects)

    return render(request, 'examinations/standardized/exam_manage.html', {
        'exam': exam,
        'candidates': candidates_qs,
        'rooms': rooms,
        'subjects': subjects,
        'total_candidates': total_candidates,
        'female_candidates': female_candidates,
        'total_rooms': total_rooms,
        'total_max_score': total_max_score,
        'total_coefficients': total_coefficients,
        'selected_room': room_filter or '',
        'selected_gender': gender_filter or '',
        'search_q': search_q,
    })


@login_required
@role_required(['ADMIN'])
def exam_pull_candidates(request, exam_id):
    """
    1-Click Auto-Pull all active students from classrooms matching this exam's Grade Level and Track.
    """
    exam = get_object_or_404(StandardizedExam, id=exam_id)

    classrooms = Classroom.objects.filter(
        academic_year=exam.academic_year,
        grade_level=exam.grade_level
    )
    if exam.track != 'ALL':
        classrooms = classrooms.filter(track=exam.track)

    students = Student.objects.filter(
        classroom__in=classrooms,
        status='ACTIVE',
        is_exam_suspended=False
    ).select_related('classroom').order_by('classroom__code', 'khmer_name')

    # Exclude students with active exclusions for this exam or month/year
    excluded_student_ids = set(
        ExamStudentExclusion.objects.filter(
            academic_year=exam.academic_year,
            is_active=True
        ).filter(
            Q(standardized_exam=exam) |
            (Q(month=exam.exam_date.month) if exam.exam_date else Q())
        ).values_list('student_id', flat=True)
    )
    if excluded_student_ids:
        students = students.exclude(id__in=excluded_student_ids)

    existing_student_ids = set(exam.candidates.values_list('student_id', flat=True))
    existing_roll_count = exam.candidates.count()

    new_candidates = []
    exam_subjects = list(exam.exam_subjects.all())

    with transaction.atomic():
        for idx, stu in enumerate(students):
            if stu.id in existing_student_ids:
                continue

            roll_str = f"{existing_roll_count + len(new_candidates) + 1:03d}"
            cand = ExamCandidate.objects.create(
                exam=exam,
                student=stu,
                roll_number=roll_str,
                desk_number=1,
                candidate_name_kh=stu.khmer_name,
                candidate_name_en=stu.latin_name or '',
                gender=stu.gender or 'M',
                dob=stu.date_of_birth,
                origin_class=stu.classroom.name if stu.classroom else '',
                student_code=stu.student_id or '',
            )
            # Create empty score rows for each subject
            for es in exam_subjects:
                CandidateSubjectScore.objects.create(
                    candidate=cand,
                    exam_subject=es
                )
            new_candidates.append(cand)

    messages.success(request, f"🎉 បានទាញបញ្ចូលបេក្ខជនសរុបចំនួន {len(new_candidates)} នាក់ ពីកម្រិតថ្នាក់ទី {exam.grade_level} ដោយជោគជ័យ!")
    return redirect('standardized_exam_manage', exam_id=exam.id)


@login_required
@role_required(['ADMIN'])
def exam_generate_rooms(request, exam_id):
    """
    Auto-Partitions all candidates into 25 candidates per room (or custom cap),
    generating Rooms 01, 02... and assigning Desk Numbers 01 to 25.
    """
    exam = get_object_or_404(StandardizedExam, id=exam_id)
    candidates = list(exam.candidates.all().order_by('origin_class', 'candidate_name_kh', 'id'))

    if not candidates:
        messages.warning(request, "មិនទាន់មានបេក្ខជនក្នុងសម័យប្រឡងនេះនៅឡើយទេ! សូមទាញ ឬបញ្ចូលបញ្ជីបេក្ខជនជាមុនសិន។")
        return redirect('standardized_exam_manage', exam_id=exam.id)

    cap = exam.candidates_per_room or 25
    total_candidates = len(candidates)
    needed_rooms = (total_candidates + cap - 1) // cap

    with transaction.atomic():
        # Clear existing room assignments
        exam.rooms.all().delete()

        created_rooms = []
        for r_num in range(1, needed_rooms + 1):
            room_obj = ExamRoom.objects.create(
                exam=exam,
                room_number=r_num,
                room_name=f"បន្ទប់លេខ {r_num:02d}",
                building="អគារ A"
            )
            created_rooms.append(room_obj)

        for idx, cand in enumerate(candidates):
            room_idx = idx // cap
            desk_num = (idx % cap) + 1

            cand.room = created_rooms[room_idx]
            cand.desk_number = desk_num
            cand.roll_number = f"{idx + 1:03d}"
            cand.save(update_fields=['room', 'desk_number', 'roll_number'])

        # Auto-generate unique secret codes for all rooms and subject envelopes
        exam.generate_all_secret_codes(force_regenerate=True)

    messages.success(request, f"🎉 បានរៀបចំ និងបែងចែកបេក្ខជនចំនួន {total_candidates} នាក់ ទៅកាន់បន្ទប់ប្រឡងចំនួន {needed_rooms} បន្ទប់ ({cap} នាក់/បន្ទប់) ព្រមទាំងបង្កើតលេខកូដសម្ងាត់សម្រាប់គ្រប់កញ្ចប់វិញ្ញាសាដោយជោគជ័យ!")
    return redirect('standardized_exam_manage', exam_id=exam.id)



@login_required
def exam_room_postings_view(request, exam_id):
    """
    Official MoEYS Exam Room Notice Board Posting Sheet (បញ្ជីបិទផ្សាយតាមបន្ទប់).
    25 Candidates per Room with national header, ready for direct print or batch print.
    """
    exam = get_object_or_404(StandardizedExam.objects.select_related('academic_year'), id=exam_id)
    rooms_qs = exam.rooms.prefetch_related('candidates').order_by('room_number')

    selected_room_id = request.GET.get('room_id')
    if selected_room_id and selected_room_id.isdigit():
        rooms_qs = rooms_qs.filter(id=int(selected_room_id))

    rooms_data = []
    for r in rooms_qs:
        cand_list = list(r.candidates.order_by('desk_number', 'roll_number', 'id'))
        rooms_data.append({
            'room': r,
            'candidates': cand_list,
            'total_candidates': len(cand_list),
            'female_candidates': len([c for c in cand_list if c.gender == 'F']),
        })

    all_rooms = exam.rooms.all().order_by('room_number')

    return render(request, 'examinations/standardized/room_postings_print.html', {
        'exam': exam,
        'rooms_data': rooms_data,
        'all_rooms': all_rooms,
        'selected_room_id': selected_room_id or '',
    })


@login_required
def exam_subject_attendance_view(request, exam_id):
    """
    Official MoEYS Subject Attendance & Signature Sheet per Room and per Subject (បញ្ជីវត្តមានចុះហត្ថលេខាតាមមុខវិជ្ជា).
    """
    exam = get_object_or_404(StandardizedExam.objects.select_related('academic_year'), id=exam_id)
    rooms = list(exam.rooms.all().order_by('room_number'))
    subjects = list(exam.exam_subjects.select_related('subject').order_by('order', 'id'))

    selected_room_id = request.GET.get('room_id')
    selected_subject_id = request.GET.get('subject_id')

    target_rooms = rooms
    if selected_room_id and selected_room_id.isdigit():
        target_rooms = [r for r in rooms if r.id == int(selected_room_id)]

    target_subjects = subjects
    if selected_subject_id and selected_subject_id.isdigit():
        target_subjects = [s for s in subjects if s.id == int(selected_subject_id)]

    sheets_data = []
    for r in target_rooms:
        cand_list = list(r.candidates.order_by('desk_number', 'roll_number', 'id'))
        for s in target_subjects:
            sheets_data.append({
                'room': r,
                'subject': s,
                'candidates': cand_list,
                'total_candidates': len(cand_list),
                'female_candidates': len([c for c in cand_list if c.gender == 'F']),
            })

    return render(request, 'examinations/standardized/attendance_sheets_print.html', {
        'exam': exam,
        'sheets_data': sheets_data,
        'rooms': rooms,
        'subjects': subjects,
        'selected_room_id': selected_room_id or '',
        'selected_subject_id': selected_subject_id or '',
    })


@login_required
@role_required(['ADMIN', 'TEACHER'])
def exam_room_scores_entry(request, exam_id):
    """
    Rapid Score Entry Matrix per Room for all subjects with dynamic calculation of
    Total Score, Weighted Average (coefficients included), MoEYS Letter Grade (A-F), and Room Rank.
    """
    exam = get_object_or_404(StandardizedExam.objects.select_related('academic_year'), id=exam_id)
    rooms = list(exam.rooms.all().order_by('room_number'))
    subjects = list(exam.exam_subjects.select_related('subject').order_by('order', 'id'))

    selected_room_id = request.GET.get('room_id')
    selected_room = None
    if selected_room_id and selected_room_id.isdigit():
        selected_room = exam.rooms.filter(id=int(selected_room_id)).first()
    if not selected_room and rooms:
        selected_room = rooms[0]

    candidates = []
    if selected_room:
        candidates = list(selected_room.candidates.prefetch_related('subject_scores__exam_subject').order_by('desk_number', 'roll_number', 'id'))

    if request.method == 'POST':
        # Handle saving score matrix
        with transaction.atomic():
            saved_count = 0
            for cand in candidates:
                for s in subjects:
                    field_key = f"score_{cand.id}_{s.id}"
                    absent_key = f"absent_{cand.id}_{s.id}"

                    score_val = request.POST.get(field_key, '').strip()
                    is_absent = (request.POST.get(absent_key) == '1') or (score_val.upper() == 'A')

                    score_obj, _ = CandidateSubjectScore.objects.get_or_create(
                        candidate=cand,
                        exam_subject=s
                    )
                    score_obj.is_absent = is_absent
                    if is_absent:
                        score_obj.score = Decimal('0.00')
                    elif score_val != '':
                        try:
                            score_num = Decimal(str(score_val))
                            score_obj.score = min(score_num, s.max_score)
                        except Exception:
                            score_obj.score = None
                    else:
                        score_obj.score = None

                    score_obj.save()
                    saved_count += 1

            # Recalculate ranks across the entire exam
            exam.recalculate_all_ranks()

        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
            return JsonResponse({'status': 'success', 'message': f'បានរក្សាទុកពិន្ទុ {saved_count} ក្រឡា ដោយជោគជ័យ!'})

        messages.success(request, f"🎉 បានរក្សាទុក និងគណនាលទ្ធផលពិន្ទុសម្រាប់ «{selected_room.room_name}» ដោយជោគជ័យ!")
        return redirect(f"{request.path}?room_id={selected_room.id}")

    # Build matrix map: (candidate_id, exam_subject_id) -> CandidateSubjectScore
    scores_map = {}
    for cand in candidates:
        for sc in cand.subject_scores.all():
            scores_map[(cand.id, sc.exam_subject_id)] = sc

    candidate_rows = []
    for cand in candidates:
        row_scores = []
        for s in subjects:
            sc = scores_map.get((cand.id, s.id))
            row_scores.append({
                'subject': s,
                'score_obj': sc,
                'score_val': sc.score if sc and sc.score is not None else '',
                'is_absent': sc.is_absent if sc else False,
            })
        candidate_rows.append({
            'candidate': cand,
            'scores': row_scores,
        })

    return render(request, 'examinations/standardized/room_scores_entry.html', {
        'exam': exam,
        'rooms': rooms,
        'selected_room': selected_room,
        'subjects': subjects,
        'candidate_rows': candidate_rows,
        'total_max_score': sum(s.max_score for s in subjects),
        'total_coefficients': sum(s.coefficient for s in subjects),
    })


@login_required
def exam_provisional_results_view(request, exam_id):
    """
    Master Grade-Level Provisional Results Posting Board (តារាងបិទផ្សាយបណ្តោះអាសន្នតាមកម្រិតថ្នាក់).
    Supports sorting by Name (Alphabetical) and by Rank, filtering by Grade (A-F) or Room,
    with summary stats, official print view, and Excel export.
    """
    exam = get_object_or_404(StandardizedExam.objects.select_related('academic_year'), id=exam_id)
    
    # Auto-recalculate ranks to guarantee freshness
    exam.recalculate_all_ranks()

    subjects = list(exam.exam_subjects.select_related('subject').order_by('order', 'id'))
    total_max_score = sum(s.max_score for s in subjects) if subjects else Decimal('100.00')

    candidates_qs = exam.candidates.select_related('room').prefetch_related('subject_scores__exam_subject')

    # Filtering
    room_filter = request.GET.get('room')
    grade_filter = request.GET.get('grade')
    gender_filter = request.GET.get('gender')
    search_q = request.GET.get('q', '').strip()
    sort_by = request.GET.get('sort', 'rank') # 'rank', 'name', 'desk', 'roll'

    if room_filter and room_filter.isdigit():
        candidates_qs = candidates_qs.filter(room_id=int(room_filter))
    if grade_filter in ['A', 'B', 'C', 'D', 'E', 'F']:
        candidates_qs = candidates_qs.filter(grade_letter=grade_filter)
    if gender_filter in ['M', 'F']:
        candidates_qs = candidates_qs.filter(gender=gender_filter)
    if search_q:
        candidates_qs = candidates_qs.filter(
            Q(candidate_name_kh__icontains=search_q) |
            Q(candidate_name_en__icontains=search_q) |
            Q(roll_number__icontains=search_q) |
            Q(origin_class__icontains=search_q)
        )

    all_candidates = list(candidates_qs)

    # Sorting
    if sort_by == 'name':
        all_candidates.sort(key=lambda c: (c.candidate_name_kh or '', c.roll_number or ''))
    elif sort_by == 'desk':
        all_candidates.sort(key=lambda c: (c.room.room_number if c.room else 999, c.desk_number, c.roll_number))
    elif sort_by == 'roll':
        all_candidates.sort(key=lambda c: c.roll_number or '')
    else:
        # Default sort by rank (rank_overall asc, total_score desc)
        all_candidates.sort(key=lambda c: (c.rank_overall if c.rank_overall else 9999, -(c.total_score or 0)))

    # Statistics
    total_cand = len(all_candidates)
    females = len([c for c in all_candidates if c.gender == 'F'])
    passed_cand = len([c for c in all_candidates if c.grade_letter in ['A', 'B', 'C', 'D', 'E']])
    failed_cand = len([c for c in all_candidates if c.grade_letter == 'F'])

    grade_counts = {
        'A': len([c for c in all_candidates if c.grade_letter == 'A']),
        'B': len([c for c in all_candidates if c.grade_letter == 'B']),
        'C': len([c for c in all_candidates if c.grade_letter == 'C']),
        'D': len([c for c in all_candidates if c.grade_letter == 'D']),
        'E': len([c for c in all_candidates if c.grade_letter == 'E']),
        'F': len([c for c in all_candidates if c.grade_letter == 'F']),
    }

    # Prepare rows with subject scores for template
    candidate_rows = []
    for cand in all_candidates:
        cand_scores = {sc.exam_subject_id: sc for sc in cand.subject_scores.all()}
        scores_list = []
        for s in subjects:
            sc = cand_scores.get(s.id)
            scores_list.append({
                'subject': s,
                'score': sc.score if sc and sc.score is not None else '-',
                'is_absent': sc.is_absent if sc else False,
            })
        candidate_rows.append({
            'candidate': cand,
            'scores': scores_list,
            'is_passed': cand.grade_letter in ['A', 'B', 'C', 'D', 'E'],
        })

    rooms = exam.rooms.all().order_by('room_number')

    return render(request, 'examinations/standardized/provisional_results_board.html', {
        'exam': exam,
        'candidate_rows': candidate_rows,
        'subjects': subjects,
        'rooms': rooms,
        'total_cand': total_cand,
        'females': females,
        'passed_cand': passed_cand,
        'failed_cand': failed_cand,
        'pass_rate': round((passed_cand / total_cand * 100), 1) if total_cand > 0 else 0,
        'grade_counts': grade_counts,
        'total_max_score': total_max_score,
        'selected_room': room_filter or '',
        'selected_grade': grade_filter or '',
        'selected_gender': gender_filter or '',
        'selected_sort': sort_by,
        'search_q': search_q,
    })


@login_required
def exam_export_candidates_excel(request, exam_id):
    """
    Exports candidates roster to Excel (.xlsx).
    """
    exam = get_object_or_404(StandardizedExam, id=exam_id)
    candidates = exam.candidates.select_related('room').order_by('room__room_number', 'desk_number', 'roll_number', 'id')

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "បញ្ជីបេក្ខជនប្រឡង"

    # Header Styles
    header_font = Font(name='Kantumruy Pro', size=11, bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='1E3A8A', end_color='1E3A8A', fill_type='solid')
    border_thin = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    # Title Rows
    ws.merge_cells('A1:I1')
    ws['A1'] = f"បញ្ជីឈ្មោះបេក្ខជន៖ {exam.name}"
    ws['A1'].font = Font(name='Kantumruy Pro', size=14, bold=True, color='1E3A8A')
    ws['A1'].alignment = Alignment(horizontal='center', vertical='center')

    ws.merge_cells('A2:I2')
    ws['A2'] = f"កម្រិតថ្នាក់ទី {exam.grade_level} • ឆ្នាំសិក្សា {exam.academic_year.name} • ចំនួនបេក្ខជនសរុប៖ {candidates.count()} នាក់ (ស្រី {candidates.filter(gender='F').count()} នាក់)"
    ws['A2'].font = Font(name='Kantumruy Pro', size=10, italic=True, color='475569')
    ws['A2'].alignment = Alignment(horizontal='center', vertical='center')

    # Table Header
    headers = [
        'ល.រ (No)', 'លេខបន្ទប់ (Room)', 'លេខតុ (Desk)', 'អត្តលេខ (Roll No)',
        'គោត្តនាម-នាម (Khmer Name)', 'ឈ្មោះឡាតាំង (Latin Name)', 'ភេទ (Sex)',
        'ថ្ងៃខែឆ្នាំកំណើត (DOB)', 'ថ្នាក់ដើម (Class)'
    ]
    ws.append([]) # Blank row 3
    ws.append(headers) # Row 4

    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=4, column=col_num)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

    for idx, c in enumerate(candidates, 1):
        row = [
            idx,
            c.room.room_name if c.room else 'មិនទាន់កំណត់',
            f"{c.desk_number:02d}",
            c.roll_number,
            c.candidate_name_kh,
            c.candidate_name_en or '',
            'ស្រី' if c.gender == 'F' else 'ប្រុស',
            c.dob.strftime('%d/%m/%Y') if c.dob else '',
            c.origin_class or ''
        ]
        ws.append(row)
        curr_row = 4 + idx
        for col_num in range(1, len(row) + 1):
            cell = ws.cell(row=curr_row, column=col_num)
            cell.font = Font(name='Kantumruy Pro', size=10)
            cell.border = border_thin
            if col_num in [1, 2, 3, 4, 7, 8]:
                cell.alignment = Alignment(horizontal='center', vertical='center')

    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Candidates_{exam.id}_{exam.grade_level}.xlsx"'
    wb.save(response)
    return response


@login_required
@role_required(['ADMIN'])
def exam_import_candidates_excel(request, exam_id):
    """
    Imports candidates roster from an Excel file.
    """
    exam = get_object_or_404(StandardizedExam, id=exam_id)

    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        try:
            wb = openpyxl.load_workbook(excel_file, data_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))

            if len(rows) < 2:
                messages.error(request, "ឯកសារ Excel គ្មានទិន្នន័យបេក្ខជនឡើយ!")
                return redirect('standardized_exam_manage', exam_id=exam.id)

            # Find header row
            header_row_idx = 0
            for idx, r in enumerate(rows[:10]):
                r_text = " ".join([str(c or '') for c in r])
                if 'គោត្តនាម' in r_text or 'Khmer Name' in r_text or 'ឈ្មោះ' in r_text:
                    header_row_idx = idx
                    break

            exam_subjects = list(exam.exam_subjects.all())
            imported_count = 0
            existing_count = exam.candidates.count()

            with transaction.atomic():
                for r in rows[header_row_idx + 1:]:
                    if not r or not any(r):
                        continue
                    name_kh = str(r[4] if len(r) > 4 else r[0] or '').strip()
                    if not name_kh or name_kh.lower() in ['none', 'ឈ្មោះ', 'គោត្តនាម-នាម']:
                        continue

                    name_en = str(r[5] if len(r) > 5 else '').strip()
                    gender_raw = str(r[6] if len(r) > 6 else 'M').strip()
                    gender = 'F' if gender_raw in ['F', 'ស្រី', 'Female', 'female', 'ស្រី្ត'] else 'M'
                    origin_class = str(r[8] if len(r) > 8 else '').strip()

                    roll_str = f"{existing_count + imported_count + 1:03d}"
                    cand = ExamCandidate.objects.create(
                        exam=exam,
                        roll_number=roll_str,
                        desk_number=1,
                        candidate_name_kh=name_kh,
                        candidate_name_en=name_en if name_en != 'None' else '',
                        gender=gender,
                        origin_class=origin_class if origin_class != 'None' else '',
                    )
                    for es in exam_subjects:
                        CandidateSubjectScore.objects.create(candidate=cand, exam_subject=es)
                    imported_count += 1

            messages.success(request, f"🎉 បាននាំចូលបេក្ខជនចំនួន {imported_count} នាក់ពី Excel ដោយជោគជ័យ!")
        except Exception as e:
            messages.error(request, f"មានបញ្ហាក្នុងការអានឯកសារ Excel៖ {str(e)}")

    return redirect('standardized_exam_manage', exam_id=exam.id)


@login_required
def exam_export_provisional_excel(request, exam_id):
    """
    Exports the complete Provisional Results Master Matrix to Excel (.xlsx).
    """
    exam = get_object_or_404(StandardizedExam, id=exam_id)
    exam.recalculate_all_ranks()

    subjects = list(exam.exam_subjects.select_related('subject').order_by('order', 'id'))
    candidates = list(exam.candidates.select_related('room').prefetch_related('subject_scores__exam_subject').order_by('rank_overall', '-total_score', 'candidate_name_kh'))

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "លទ្ធផលបណ្តោះអាសន្ន"

    # Header Styles
    header_font = Font(name='Kantumruy Pro', size=10, bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='1E3A8A', end_color='1E3A8A', fill_type='solid')
    border_thin = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    # Title
    num_cols = 8 + len(subjects) + 4
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=num_cols)
    ws['A1'] = f"តារាងបិទផ្សាយបណ្តោះអាសន្នលទ្ធផលប្រឡង៖ {exam.name}"
    ws['A1'].font = Font(name='Kantumruy Pro', size=14, bold=True, color='1E3A8A')
    ws['A1'].alignment = Alignment(horizontal='center', vertical='center')

    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=num_cols)
    ws['A2'] = f"កម្រិតថ្នាក់ទី {exam.grade_level} • ឆ្នាំសិក្សា {exam.academic_year.name} • បេក្ខជនសរុប៖ {len(candidates)} នាក់"
    ws['A2'].font = Font(name='Kantumruy Pro', size=10, italic=True, color='475569')
    ws['A2'].alignment = Alignment(horizontal='center', vertical='center')

    # Headers
    headers = ['ចំណាត់ថ្នាក់', 'អត្តលេខ', 'បន្ទប់', 'លេខតុ', 'គោត្តនាម-នាម', 'ឈ្មោះឡាតាំង', 'ភេទ', 'ថ្នាក់ដើម']
    for s in subjects:
        headers.append(f"{s.subject.name_kh} (/{s.max_score:g})")
    headers.extend(['ពិន្ទុសរុប', 'មធ្យមភាគ', 'និទ្ទេស', 'លទ្ធផល'])

    ws.append([]) # Row 3 blank
    ws.append(headers) # Row 4

    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=4, column=col_num)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

    for idx, c in enumerate(candidates, 1):
        cand_scores = {sc.exam_subject_id: sc for sc in c.subject_scores.all()}
        row = [
            c.rank_overall or idx,
            c.roll_number,
            c.room.room_name if c.room else '-',
            f"{c.desk_number:02d}",
            c.candidate_name_kh,
            c.candidate_name_en or '',
            'ស្រី' if c.gender == 'F' else 'ប្រុស',
            c.origin_class or '',
        ]
        for s in subjects:
            sc = cand_scores.get(s.id)
            if sc and sc.is_absent:
                row.append('អវត្តមាន')
            elif sc and sc.score is not None:
                row.append(float(sc.score))
            else:
                row.append('-')

        row.extend([
            float(c.total_score),
            float(c.average_score),
            c.grade_letter,
            'ជាប់' if c.grade_letter in ['A', 'B', 'C', 'D', 'E'] else 'ធ្លាក់'
        ])
        ws.append(row)
        curr_row = 4 + idx
        for col_num in range(1, len(row) + 1):
            cell = ws.cell(row=curr_row, column=col_num)
            cell.font = Font(name='Kantumruy Pro', size=10)
            cell.border = border_thin
            if col_num in [1, 2, 3, 4, 7, 8, len(row)-2, len(row)-1, len(row)]:
                cell.alignment = Alignment(horizontal='center', vertical='center')

    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 11)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Provisional_Results_{exam.id}_{exam.grade_level}.xlsx"'
    wb.save(response)
    return response


# ==============================================================================
# BLIND EXAM SCORING SYSTEM (ផ្ទាំងបញ្ចូលពិន្ទុសិស្សដោយលេខកូដសម្ងាត់ ៤ ជំហាន)
# ==============================================================================

@login_required
@role_required(['ADMIN', 'TEACHER'])
def exam_blind_scoring_portal(request):
    """
    Step-by-Step Blind / Secret-Coded Exam Score Entry Interface (4 Steps):
    - Step 1: Select Grade Level & Exam
    - Step 2: Select Subject
    - Step 3: Enter Secret Code
    - Step 4: Rapid Score Entry from Desk 01 to 25
    """
    from apps.academics.utils import get_active_academic_year
    active_year = get_active_academic_year(request)
    
    exams_qs = StandardizedExam.objects.select_related('academic_year').order_by('-exam_date', '-id')
    if active_year:
        exams_qs = exams_qs.filter(academic_year=active_year)

    # Regular teachers can only see published / admin-permitted exams
    if not request.user.is_superuser and getattr(request.user, 'role', '') == 'TEACHER':
        exams_qs = exams_qs.filter(is_published=True)
    
    pre_exam_id = request.GET.get('exam_id')
    pre_subject_id = request.GET.get('subject_id')
    pre_code = request.GET.get('code', '').strip()

    selected_exam = None
    subjects = []
    if pre_exam_id and str(pre_exam_id).isdigit():
        selected_exam = StandardizedExam.objects.filter(id=int(pre_exam_id)).first()
        if selected_exam:
            subjects = selected_exam.exam_subjects.select_related('subject').order_by('order', 'id')

    return render(request, 'examinations/standardized/blind_scoring_portal.html', {
        'exams': exams_qs,
        'selected_exam': selected_exam,
        'subjects': subjects,
        'pre_exam_id': pre_exam_id or '',
        'pre_subject_id': pre_subject_id or '',
        'pre_code': pre_code,
    })


@login_required
@role_required(['ADMIN', 'TEACHER'])
def api_exam_get_subjects(request, exam_id):
    """
    JSON API returning all subjects, grading rules, and secret codes for a standardized exam.
    Regular teachers only get subject metadata (secret codes directory is restricted to Admin).
    """
    exam = get_object_or_404(StandardizedExam, id=exam_id)
    subjects = exam.exam_subjects.select_related('subject').order_by('order', 'id')
    is_admin = request.user.is_superuser or getattr(request.user, 'role', '') == 'ADMIN'

    # Query room subject codes (Only Admin can see full directory of secret codes)
    codes_by_subject = {}
    if is_admin:
        room_codes_qs = ExamRoomSubjectCode.objects.filter(exam_room__exam=exam).select_related('exam_room', 'graded_by')
        for rc in room_codes_qs:
            if rc.exam_subject_id not in codes_by_subject:
                codes_by_subject[rc.exam_subject_id] = []
            codes_by_subject[rc.exam_subject_id].append({
                'secret_code': rc.secret_code,
                'is_graded': rc.is_graded,
                'graded_by': rc.graded_by.username if rc.graded_by else '',
                'graded_at': rc.graded_at.strftime('%d/%m/%Y %H:%M') if rc.graded_at else '',
                'room_name': rc.exam_room.room_name,
            })
    
    return JsonResponse({
        'status': 'success',
        'exam_id': exam.id,
        'exam_name': exam.name,
        'grade_level': exam.grade_level,
        'candidates_per_room': exam.candidates_per_room,
        'is_admin': is_admin,
        'subjects': [
            {
                'id': s.id,
                'name': s.subject.name_kh,
                'code': s.subject.code,
                'max_score': float(s.max_score),
                'coefficient': float(s.coefficient),
                'session': s.get_session_display(),
                'exam_date': s.exam_date.strftime('%d/%m/%Y') if s.exam_date else '',
                'secret_codes': codes_by_subject.get(s.id, []) if is_admin else [],
            }
            for s in subjects
        ]
    })


@login_required
@role_required(['ADMIN', 'TEACHER'])
def api_exam_validate_secret_code(request):
    """
    Step 3 Validation API:
    Validates the Secret Code against ExamRoomSubjectCode or ExamRoom.secret_code,
    and returns anonymous candidate desks list (Desks 01 to 25) without student names.
    Conceals physical room names from regular teachers to ensure 100% blind grading privacy!
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

    try:
        data = json.loads(request.body)
    except Exception:
        data = request.POST

    exam_id = data.get('exam_id')
    subject_id = data.get('subject_id')
    secret_code = str(data.get('secret_code', '')).strip().upper()

    if not exam_id or not subject_id or not secret_code:
        return JsonResponse({'status': 'error', 'message': 'សូមជ្រើសរើសព័ត៌មានឱ្យបានគ្រប់គ្រាន់ (កម្រិតថ្នាក់, មុខវិជ្ជា និងលេខកូដសម្ងាត់)!'})

    exam = get_object_or_404(StandardizedExam, id=exam_id)
    exam_subject = get_object_or_404(ExamSubject.objects.select_related('subject'), id=subject_id, exam=exam)
    is_admin = request.user.is_superuser or getattr(request.user, 'role', '') == 'ADMIN'

    # Search for matching ExamRoomSubjectCode first
    code_obj = ExamRoomSubjectCode.objects.filter(
        secret_code__iexact=secret_code,
        exam_subject=exam_subject
    ).select_related('exam_room').first()

    room = None
    if code_obj:
        room = code_obj.exam_room
    else:
        # Check by ExamRoom secret_code
        room = ExamRoom.objects.filter(exam=exam, secret_code__iexact=secret_code).first()

    if not room:
        return JsonResponse({
            'status': 'error',
            'message': f'លេខកូដសម្ងាត់ «{secret_code}» មិនត្រឹមត្រូវ ឬមិនត្រូវគ្នានឹងមុខវិជ្ជា {exam_subject.subject.name_kh} នៃសម័យប្រឡងនេះឡើយ! សូមផ្ទៀងផ្ទាត់លេខកូដលើកញ្ចប់ក្រដាសប្រឡងម្តងទៀត។'
        })

    is_grading_open, _, grading_msg = exam.get_grading_status()

    # Retrieve candidates in this room sorted by desk_number (1 to N)
    candidates = room.candidates.all().order_by('desk_number', 'id')
    if not candidates.exists():
        return JsonResponse({
            'status': 'error',
            'message': f'កញ្ចប់ប្រឡងលេខកូដ «{secret_code}» មិនទាន់មានបេក្ខជនត្រូវបានបែងចែកនៅឡើយទេ។ សូមទាក់ទង Admin។'
        })

    scores_map = {
        sc.candidate_id: sc
        for sc in CandidateSubjectScore.objects.filter(
            candidate__in=candidates,
            exam_subject=exam_subject
        )
    }

    desks_data = []
    for cand in candidates:
        sc = scores_map.get(cand.id)
        score_val = ''
        is_absent = False
        if sc:
            is_absent = sc.is_absent
            if sc.score is not None and not is_absent:
                score_val = float(sc.score)

        desks_data.append({
            'desk_number': cand.desk_number,
            'candidate_id': cand.id,
            'score': score_val,
            'is_absent': is_absent,
        })

    # For regular teachers, mask physical room name for blind confidentiality
    display_room_name = room.room_name if is_admin else f"កញ្ចប់កូដសម្ងាត់ #{secret_code}"

    return JsonResponse({
        'status': 'success',
        'room_id': room.id,
        'room_name': display_room_name,
        'is_blind_mode': not is_admin,
        'is_grading_open': is_grading_open or is_admin,
        'grading_status_msg': grading_msg,
        'subject_id': exam_subject.id,
        'subject_name': exam_subject.subject.name_kh,
        'max_score': float(exam_subject.max_score),
        'coefficient': float(exam_subject.coefficient),
        'candidate_count': len(desks_data),
        'is_already_graded': code_obj.is_graded if code_obj else False,
        'graded_by': (code_obj.graded_by.get_full_name() or code_obj.graded_by.username) if (code_obj and code_obj.graded_by) else '',
        'graded_at': code_obj.graded_at.strftime('%d/%m/%Y %H:%M') if (code_obj and code_obj.graded_at) else '',
        'desks': desks_data
    })


@login_required
@role_required(['ADMIN', 'TEACHER'])
def api_exam_save_blind_scores(request):
    """
    Step 4 Save API:
    Saves scores submitted blindly by desk number (01 to N), matches with candidates,
    updates CandidateSubjectScore, marks envelope code as graded, and recalculates exam ranks.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

    try:
        data = json.loads(request.body)
    except Exception:
        data = request.POST

    exam_id = data.get('exam_id')
    subject_id = data.get('subject_id')
    secret_code = str(data.get('secret_code', '')).strip().upper()
    scores_list = data.get('scores', [])

    if not exam_id or not subject_id or not secret_code or not scores_list:
        return JsonResponse({'status': 'error', 'message': 'ទិន្នន័យមិនពេញលេញ!'})

    exam = get_object_or_404(StandardizedExam, id=exam_id)
    exam_subject = get_object_or_404(ExamSubject.objects.select_related('subject'), id=subject_id, exam=exam)
    is_admin = request.user.is_superuser or getattr(request.user, 'role', '') == 'ADMIN'

    # Enforce Grading Window for regular teachers
    is_grading_open, _, grading_msg = exam.get_grading_status()
    if not is_grading_open and not is_admin:
        return JsonResponse({'status': 'error', 'message': f'⚠️ មិនអាចរក្សាទុកបានទេ៖ {grading_msg}!'})

    code_obj = ExamRoomSubjectCode.objects.filter(
        secret_code__iexact=secret_code,
        exam_subject=exam_subject
    ).select_related('exam_room').first()

    room = None
    if code_obj:
        room = code_obj.exam_room
    else:
        room = ExamRoom.objects.filter(exam=exam, secret_code__iexact=secret_code).first()

    if not room:
        return JsonResponse({'status': 'error', 'message': 'លេខកូដសម្ងាត់មិនត្រឹមត្រូវ!'})

    candidates_by_desk = {c.desk_number: c for c in room.candidates.all()}

    saved_count = 0
    absent_count = 0
    total_score_sum = Decimal('0.00')
    valid_scores = []

    with transaction.atomic():
        for item in scores_list:
            desk_num = int(item.get('desk_number', 0))
            score_raw = str(item.get('score', '')).strip().upper()
            is_absent = bool(item.get('is_absent', False)) or (score_raw == 'A')

            cand = candidates_by_desk.get(desk_num)
            if not cand:
                continue

            score_obj, _ = CandidateSubjectScore.objects.get_or_create(
                candidate=cand,
                exam_subject=exam_subject
            )

            if is_absent:
                score_obj.is_absent = True
                score_obj.score = Decimal('0.00')
                absent_count += 1
            elif score_raw != '' and score_raw != '-':
                try:
                    val = Decimal(score_raw)
                    if val > exam_subject.max_score:
                        val = exam_subject.max_score
                    if val < Decimal('0.00'):
                        val = Decimal('0.00')
                    score_obj.score = val
                    score_obj.is_absent = False
                    total_score_sum += val
                    valid_scores.append(val)
                except Exception:
                    score_obj.score = Decimal('0.00')
                    score_obj.is_absent = False
            else:
                score_obj.score = None
                score_obj.is_absent = False

            score_obj.save()
            saved_count += 1

        if code_obj:
            code_obj.is_graded = True
            code_obj.graded_by = request.user
            code_obj.graded_at = timezone.now()
            code_obj.save(update_fields=['is_graded', 'graded_by', 'graded_at'])

        # Recalculate ranks & grades
        exam.recalculate_all_ranks()

    avg_val = (float(total_score_sum) / len(valid_scores)) if valid_scores else 0.0
    max_val = float(max(valid_scores)) if valid_scores else 0.0
    min_val = float(min(valid_scores)) if valid_scores else 0.0

    return JsonResponse({
        'status': 'success',
        'message': f'🎉 បានរក្សាទុកពិន្ទុមុខវិជ្ជា «{exam_subject.subject.name_kh}» សម្រាប់កញ្ចប់កូដ «{secret_code}» ({room.room_name}) ដោយជោគជ័យ!',
        'summary': {
            'saved_count': saved_count,
            'graded_count': len(valid_scores),
            'absent_count': absent_count,
            'average_score': round(avg_val, 2),
            'max_score': round(max_val, 2),
            'min_score': round(min_val, 2),
        }
    })


@login_required
@role_required(['ADMIN'])
def exam_secret_codes_directory(request, exam_id):
    """
    Admin-Only Master Secret Codes Directory & Printable Stickers:
    Shows all generated secret codes per room and subject envelope.
    """
    exam = get_object_or_404(StandardizedExam.objects.select_related('academic_year'), id=exam_id)
    rooms = exam.rooms.all().order_by('room_number')
    subjects = exam.exam_subjects.select_related('subject').order_by('order', 'id')

    # Ensure all codes are initialized
    exam.generate_all_secret_codes(force_regenerate=False)

    subject_codes_qs = ExamRoomSubjectCode.objects.filter(
        exam_room__exam=exam
    ).select_related('exam_room', 'exam_subject__subject', 'graded_by').order_by('exam_room__room_number', 'exam_subject__order')

    # Build matrix: room x subject -> code_obj
    matrix = {}
    for sc in subject_codes_qs:
        matrix[(sc.exam_room_id, sc.exam_subject_id)] = sc

    rows = []
    for r in rooms:
        row_items = []
        for s in subjects:
            code_obj = matrix.get((r.id, s.id))
            row_items.append({
                'subject': s,
                'code_obj': code_obj,
            })
        rows.append({
            'room': r,
            'items': row_items
        })

    return render(request, 'examinations/standardized/secret_codes_directory.html', {
        'exam': exam,
        'rooms': rooms,
        'subjects': subjects,
        'rows': rows,
        'total_codes': subject_codes_qs.count(),
        'graded_codes': subject_codes_qs.filter(is_graded=True).count(),
    })


@login_required
@role_required(['ADMIN'])
def exam_regenerate_secret_codes(request, exam_id):
    """
    Regenerates all secret codes for this exam based on custom rules:
    - Subject prefix (M, R, D, K, P, C, B...)
    - Grade letter (7:S, 8:E, 9:N, 10:T, 11sc:Y, 11ss:I, 12sc:W, 12ss:Z...)
    - Month code (A..L, Q...) - Optional
    - 1 or 2 Random letters
    """
    exam = get_object_or_404(StandardizedExam, id=exam_id)
    if request.method == 'POST':
        include_month = request.POST.get('include_month') == '1'
        month_code = request.POST.get('month_code', '').strip().upper()
        custom_grade_letter = request.POST.get('custom_grade_letter', '').strip().upper()
        use_two_random_letters = request.POST.get('use_two_random_letters') == '1'

        exam.generate_all_secret_codes(
            force_regenerate=True,
            include_month=include_month,
            month_code=month_code,
            use_two_random_letters=use_two_random_letters,
            custom_grade_letter=custom_grade_letter
        )
        messages.success(request, f"🎉 បានបង្កើតឡើងវិញនូវលេខកូដសម្ងាត់កញ្ចប់វិញ្ញាសាគ្រប់បន្ទប់សម្រាប់សម័យប្រឡង «{exam.name}» ដោយជោគជ័យ!")
    return redirect('exam_secret_codes_directory', exam_id=exam.id)


# ==============================================================================
# DISCIPLINARY HOLD & CONTRACT BLOCKING APIS (ការគ្រប់គ្រងវិន័យ & ផ្អាកបិទផ្សាយ)
# ==============================================================================

@login_required
@role_required(['ADMIN', 'TEACHER'])
def api_toggle_candidate_disciplinary_hold(request):
    """
    AJAX API: Toggles disciplinary hold (Tick / Untick) on an Exam Candidate.
    When ticked (is_disciplinary_blocked=True):
    - Candidate's name & details are masked on Room Notice Postings.
    - Candidate's signature box is blocked on Subject Attendance Sheets.
    When unticked (is_disciplinary_blocked=False):
    - Candidate's full info & signature box are instantly restored.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)

    try:
        data = json.loads(request.body) if request.body else request.POST
    except Exception:
        data = request.POST

    candidate_id = data.get('candidate_id')
    reason = str(data.get('reason', '')).strip()
    force_state = data.get('force_state')

    if not candidate_id:
        return JsonResponse({'status': 'error', 'message': 'Candidate ID is required'}, status=400)

    candidate = get_object_or_404(ExamCandidate.objects.select_related('exam'), id=candidate_id)
    
    if force_state is not None:
        candidate.is_disciplinary_blocked = bool(force_state)
    else:
        candidate.is_disciplinary_blocked = not candidate.is_disciplinary_blocked

    if candidate.is_disciplinary_blocked:
        candidate.disciplinary_reason = reason or "បញ្ហាវិន័យ / ត្រូវមកធ្វើកិច្ចសន្យាជាមុនសិន"
        candidate.disciplinary_blocked_by = request.user
        candidate.disciplinary_blocked_at = timezone.now()
        action_text = "បានដាក់វិន័យ (ផ្អាកបិទផ្សាយ និងចុះហត្ថលេខា)"
    else:
        candidate.disciplinary_reason = ""
        candidate.disciplinary_blocked_by = None
        candidate.disciplinary_blocked_at = None
        action_text = "បានដោះវិន័យ (បង្ហាញឈ្មោះក្នុងបញ្ជីទាំង២វិញធម្មតា)"

    candidate.save(update_fields=['is_disciplinary_blocked', 'disciplinary_reason', 'disciplinary_blocked_by', 'disciplinary_blocked_at'])

    return JsonResponse({
        'status': 'success',
        'is_disciplinary_blocked': candidate.is_disciplinary_blocked,
        'candidate_id': candidate.id,
        'candidate_name': candidate.candidate_name_kh,
        'roll_number': candidate.roll_number,
        'desk_number': candidate.desk_number,
        'disciplinary_reason': candidate.disciplinary_reason or '',
        'message': f"🎉 {action_text} សម្រាប់បេក្ខជន «{candidate.candidate_name_kh}» ដោយជោគជ័យ!"
    })


@login_required
@role_required(['ADMIN', 'TEACHER'])
def api_batch_toggle_disciplinary_hold(request):
    """
    AJAX API: Batch Ticks / Unticks disciplinary hold for multiple exam candidates.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)

    try:
        data = json.loads(request.body) if request.body else request.POST
    except Exception:
        data = request.POST

    candidate_ids = data.get('candidate_ids', [])
    action = data.get('action', 'block')  # 'block' or 'unblock'
    reason = str(data.get('reason', '')).strip() or "បញ្ហាវិន័យ / ត្រូវមកធ្វើកិច្ចសន្យាជាមុនសិន"

    if not candidate_ids:
        return JsonResponse({'status': 'error', 'message': 'No candidates selected'}, status=400)

    is_blocked = (action == 'block')
    candidates_qs = ExamCandidate.objects.filter(id__in=candidate_ids)
    count = candidates_qs.count()

    with transaction.atomic():
        if is_blocked:
            candidates_qs.update(
                is_disciplinary_blocked=True,
                disciplinary_reason=reason,
                disciplinary_blocked_by=request.user,
                disciplinary_blocked_at=timezone.now()
            )
        else:
            candidates_qs.update(
                is_disciplinary_blocked=False,
                disciplinary_reason="",
                disciplinary_blocked_by=None,
                disciplinary_blocked_at=None
            )

    return JsonResponse({
        'status': 'success',
        'action': action,
        'updated_count': count,
        'message': f"🎉 បាន{'ដាក់វិន័យ' if is_blocked else 'ដោះវិន័យ'}លើបេក្ខជនចំនួន {count} នាក់ដោយជោគជ័យ!"
    })


# ==============================================================================
# MONTHLY STUDENT EXAM EXCLUSIONS (ការកំណត់លើកលែងសិស្សមិនឱ្យប្រឡងតាមខែ)
# ==============================================================================

@login_required
def exam_exclusions_manage(request):
    """
    Master page to manage students excluded/disqualified from monthly exams & standardized exams.
    Shows active and historical exclusions, with easy creation and instant reactivation when students return.
    """
    from apps.academics.utils import get_active_academic_year
    active_year = get_active_academic_year(request)
    is_admin = request.user.is_superuser or getattr(request.user, 'role', '') == 'ADMIN'

    selected_year_id = request.GET.get('academic_year')
    selected_term_id = request.GET.get('term')
    selected_month = request.GET.get('month')
    selected_class_id = request.GET.get('classroom')
    selected_reason = request.GET.get('reason')
    search_q = request.GET.get('q', '').strip()

    target_year = active_year
    if selected_year_id and selected_year_id.isdigit():
        target_year = AcademicYear.objects.filter(id=int(selected_year_id)).first() or active_year

    exclusions_qs = ExamStudentExclusion.objects.select_related(
        'student', 'student__classroom', 'academic_year', 'exam_term', 'standardized_exam', 'excluded_by'
    ).order_by('-is_active', '-created_at')

    if target_year:
        exclusions_qs = exclusions_qs.filter(academic_year=target_year)

    if selected_term_id and selected_term_id.isdigit():
        exclusions_qs = exclusions_qs.filter(exam_term_id=int(selected_term_id))

    if selected_month and selected_month.isdigit():
        exclusions_qs = exclusions_qs.filter(month=int(selected_month))

    if selected_class_id and selected_class_id.isdigit():
        exclusions_qs = exclusions_qs.filter(student__classroom_id=int(selected_class_id))

    if selected_reason:
        exclusions_qs = exclusions_qs.filter(reason=selected_reason)

    if search_q:
        exclusions_qs = exclusions_qs.filter(
            Q(student__khmer_name__icontains=search_q) |
            Q(student__latin_name__icontains=search_q) |
            Q(student__student_id__icontains=search_q) |
            Q(notes__icontains=search_q)
        )

    # Handle POST Actions (Create Exclusion / Toggle / Delete)
    if request.method == 'POST':
        if not is_admin:
            messages.error(request, "លោកអ្នកមិនមានសិទ្ធិកែប្រែការកំណត់នេះទេ! (Admin Only)")
            return redirect('exam_exclusions_manage')

        action = request.POST.get('action')

        if action == 'create':
            student_id = request.POST.get('student_id')
            exam_term_id = request.POST.get('exam_term_id')
            month_val = request.POST.get('month')
            reason = request.POST.get('reason', ExamStudentExclusion.Reason.DROPPED)
            notes = request.POST.get('notes', '').strip()

            if student_id and student_id.isdigit():
                stu = get_object_or_404(Student, id=int(student_id))
                term_obj = ExamTerm.objects.filter(id=int(exam_term_id)).first() if exam_term_id and exam_term_id.isdigit() else None
                m_int = int(month_val) if month_val and month_val.isdigit() else None

                exclusion, created = ExamStudentExclusion.objects.update_or_create(
                    student=stu,
                    academic_year=stu.academic_year or target_year or AcademicYear.objects.first(),
                    exam_term=term_obj,
                    month=m_int,
                    defaults={
                        'reason': reason,
                        'notes': notes,
                        'is_active': True,
                        'excluded_by': request.user
                    }
                )
                messages.success(request, f"🎉 បានកំណត់លើកលែងសិស្ស «{stu.khmer_name}» មិនឱ្យប្រឡងដោយជោគជ័យ!")
            else:
                messages.error(request, "សូមជ្រើសរើសសិស្សឱ្យបានត្រឹមត្រូវ!")

            return redirect('exam_exclusions_manage')

        elif action == 'toggle':
            exc_id = request.POST.get('exclusion_id')
            if exc_id and exc_id.isdigit():
                exc = get_object_or_404(ExamStudentExclusion, id=int(exc_id))
                exc.is_active = not exc.is_active
                exc.save(update_fields=['is_active', 'updated_at'])
                status_text = "កំពុងលើកលែង" if exc.is_active else "បានអនុញ្ញាតឱ្យចូលប្រឡងវិញ"
                messages.success(request, f"🎉 សិស្ស «{exc.student.khmer_name}» ត្រូវបានប្តូរស្ថានភាពទៅជា៖ {status_text}")
            return redirect('exam_exclusions_manage')

        elif action == 'delete':
            exc_id = request.POST.get('exclusion_id')
            if exc_id and exc_id.isdigit():
                exc = get_object_or_404(ExamStudentExclusion, id=int(exc_id))
                name = exc.student.khmer_name
                exc.delete()
                messages.success(request, f"🗑️ បានលុបកំណត់ត្រាលើកលែងរបស់សិស្ស «{name}» ដោយជោគជ័យ!")
            return redirect('exam_exclusions_manage')

    academic_years = AcademicYear.objects.all().order_by('-start_date')
    classrooms = Classroom.objects.filter(academic_year=target_year).order_by('grade_level', 'code') if target_year else Classroom.objects.all().order_by('grade_level', 'code')
    exam_terms = ExamTerm.objects.filter(academic_year=target_year).order_by('-start_date') if target_year else ExamTerm.objects.all().order_by('-start_date')
    
    total_exclusions = exclusions_qs.count()
    active_exclusions = exclusions_qs.filter(is_active=True).count()

    return render(request, 'examinations/exclusions_manage.html', {
        'exclusions': exclusions_qs,
        'academic_years': academic_years,
        'classrooms': classrooms,
        'exam_terms': exam_terms,
        'target_year': target_year,
        'total_exclusions': total_exclusions,
        'active_exclusions': active_exclusions,
        'selected_year_id': str(target_year.id) if target_year else '',
        'selected_term_id': selected_term_id or '',
        'selected_month': selected_month or '',
        'selected_class_id': selected_class_id or '',
        'selected_reason': selected_reason or '',
        'search_q': search_q,
        'reasons': ExamStudentExclusion.Reason.choices,
        'month_choices': Student.MONTH_CHOICES,
        'is_admin': is_admin,
    })


@login_required
@role_required(['ADMIN'])
def api_toggle_exam_exclusion(request):
    """
    AJAX API to toggle an exclusion on/off.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)

    try:
        data = json.loads(request.body) if request.body else request.POST
    except Exception:
        data = request.POST

    exc_id = data.get('exclusion_id')
    if not exc_id:
        return JsonResponse({'status': 'error', 'message': 'Exclusion ID is required'}, status=400)

    exc = get_object_or_404(ExamStudentExclusion, id=exc_id)
    exc.is_active = not exc.is_active
    exc.save(update_fields=['is_active', 'updated_at'])

    return JsonResponse({
        'status': 'success',
        'exclusion_id': exc.id,
        'is_active': exc.is_active,
        'student_name': exc.student.khmer_name,
        'message': f"🎉 បានប្តូរស្ថានភាពលើកលែងរបស់ «{exc.student.khmer_name}» ទៅជា៖ {'កំពុងលើកលែង (មិនឱ្យប្រឡង)' if exc.is_active else 'អនុញ្ញាតឱ្យប្រឡងវិញ'} ដោយជោគជ័យ!"
    })


@login_required
def api_get_students_by_classroom(request, classroom_id):
    """
    AJAX API returning list of students in a classroom for modal dropdowns.
    """
    classroom = get_object_or_404(Classroom, id=classroom_id)
    students = Student.objects.filter(classroom=classroom).order_by('student_id', 'khmer_name')

    data = [
        {
            'id': s.id,
            'student_id': s.student_id,
            'khmer_name': s.khmer_name,
            'latin_name': s.latin_name or '',
            'status': s.status,
            'status_display': s.get_status_display(),
        }
        for s in students
    ]

    return JsonResponse({
        'status': 'success',
        'classroom_id': classroom.id,
        'classroom_name': classroom.name,
        'students': data
    })


# =========================================================================
# MOEYS SEMESTER & ANNUAL ACADEMIC RESULTS AND TRANSFER GRADES
# =========================================================================

from .services import AcademicResultService
from .models import StudentTransferGrade

@login_required
def semester_results_view(request):
    """
    Computes and displays Semester 1 or Semester 2 Official MoEYS Academic Results.
    Formula: Semester Average = (Monthly Average of semester terms + Semester Exam Score) / 2
    """
    from apps.academics.utils import get_active_academic_year
    active_year = get_active_academic_year(request)
    
    selected_year_id = request.GET.get('year') or request.GET.get('academic_year')
    target_year = active_year
    if selected_year_id:
        if selected_year_id == 'all':
            target_year = None
        elif str(selected_year_id).isdigit():
            found_year = AcademicYear.objects.filter(id=int(selected_year_id)).first()
            if found_year:
                target_year = found_year

    academic_years = AcademicYear.objects.all().order_by('-start_date')
    classrooms = Classroom.objects.filter(academic_year=target_year).order_by('grade_level', 'code') if target_year else Classroom.objects.all().order_by('grade_level', 'code')

    selected_class_id = request.GET.get('classroom', str(classrooms.first().id if classrooms.first() else ''))
    selected_semester = int(request.GET.get('semester', '1'))

    selected_class = classrooms.filter(id=selected_class_id).first() if selected_class_id else None

    semester_data = None
    if selected_class and target_year:
        semester_data = AcademicResultService.compute_semester_results(
            classroom=selected_class,
            academic_year=target_year,
            semester=selected_semester
        )

    is_admin = request.user.is_superuser or getattr(request.user, 'role', '') in ['ADMIN', 'TEACHER']

    return render(request, 'examinations/semester_results.html', {
        'academic_years': academic_years,
        'classrooms': classrooms,
        'target_year': target_year,
        'selected_year_id': str(target_year.id) if target_year else '',
        'selected_class': selected_class,
        'selected_class_id': str(selected_class.id) if selected_class else '',
        'selected_semester': selected_semester,
        'semester_data': semester_data,
        'is_admin': is_admin,
    })


@login_required
def annual_results_view(request):
    """
    Computes and displays Annual Overall Academic Results for a classroom.
    Formula: Annual Average = (Semester 1 Average + Semester 2 Average) / 2
    """
    from apps.academics.utils import get_active_academic_year
    active_year = get_active_academic_year(request)

    selected_year_id = request.GET.get('year') or request.GET.get('academic_year')
    target_year = active_year
    if selected_year_id:
        if selected_year_id == 'all':
            target_year = None
        elif str(selected_year_id).isdigit():
            found_year = AcademicYear.objects.filter(id=int(selected_year_id)).first()
            if found_year:
                target_year = found_year

    academic_years = AcademicYear.objects.all().order_by('-start_date')
    classrooms = Classroom.objects.filter(academic_year=target_year).order_by('grade_level', 'code') if target_year else Classroom.objects.all().order_by('grade_level', 'code')

    selected_class_id = request.GET.get('classroom', str(classrooms.first().id if classrooms.first() else ''))
    selected_class = classrooms.filter(id=selected_class_id).first() if selected_class_id else None

    annual_data = None
    if selected_class and target_year:
        annual_data = AcademicResultService.compute_annual_results(
            classroom=selected_class,
            academic_year=target_year
        )

    is_admin = request.user.is_superuser or getattr(request.user, 'role', '') in ['ADMIN', 'TEACHER']

    return render(request, 'examinations/annual_results.html', {
        'academic_years': academic_years,
        'classrooms': classrooms,
        'target_year': target_year,
        'selected_year_id': str(target_year.id) if target_year else '',
        'selected_class': selected_class,
        'selected_class_id': str(selected_class.id) if selected_class else '',
        'annual_data': annual_data,
        'is_admin': is_admin,
    })


@login_required
@role_required(['ADMIN', 'TEACHER'])
def api_save_transfer_grade(request):
    """
    POST/AJAX endpoint allowing Admin or Teachers to input prior school scores for a transfer student.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body) if request.body and request.content_type == 'application/json' else request.POST
    except Exception:
        data = request.POST

    student_id = data.get('student_id')
    semester = data.get('semester', 1)
    prior_school = data.get('prior_school_name', '').strip()
    m_avg = data.get('monthly_average')
    sem_exam = data.get('semester_exam_score')
    sem_final = data.get('semester_final_average')
    remarks = data.get('remarks', '').strip()

    if not student_id:
        return JsonResponse({'success': False, 'error': 'Student ID is required'}, status=400)

    student = get_object_or_404(Student, id=int(student_id))
    academic_year = student.academic_year or (student.classroom.academic_year if student.classroom else None) or AcademicYear.objects.first()

    # Parse Decimals safely
    m_avg_dec = Decimal(str(m_avg)) if m_avg and str(m_avg).strip() != '' else None
    sem_exam_dec = Decimal(str(sem_exam)) if sem_exam and str(sem_exam).strip() != '' else None
    sem_final_dec = Decimal(str(sem_final)) if sem_final and str(sem_final).strip() != '' else None

    if sem_final_dec is None:
        if m_avg_dec is not None and sem_exam_dec is not None:
            sem_final_dec = round((m_avg_dec + sem_exam_dec) / Decimal('2.0'), 2)
        elif m_avg_dec is not None:
            sem_final_dec = m_avg_dec
        elif sem_exam_dec is not None:
            sem_final_dec = sem_exam_dec
        else:
            return JsonResponse({'success': False, 'error': 'សូមបញ្ចូលមធ្យមភាគប្រចាំខែ ឬពិន្ទុប្រឡងឆមាសពីសាលាចាស់!'}, status=400)

    record, created = StudentTransferGrade.objects.update_or_create(
        student=student,
        academic_year=academic_year,
        semester=int(semester),
        defaults={
            'prior_school_name': prior_school,
            'monthly_average': m_avg_dec,
            'semester_exam_score': sem_exam_dec,
            'semester_final_average': sem_final_dec,
            'remarks': remarks,
            'created_by': request.user,
        }
    )

    msg = f"🎉 បានបញ្ចូលពិន្ទុសិស្សផ្ទេរចូល «{student.khmer_name}» ឆមាសទី{semester} (មធ្យមភាគ៖ {record.semester_final_average}) ដោយជោគជ័យ!"
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('format') == 'json':
        return JsonResponse({
            'success': True,
            'record_id': record.id,
            'semester_final_average': str(record.semester_final_average),
            'letter_grade': record.letter_grade,
            'message': msg
        })

    messages.success(request, msg)
    redirect_url = request.META.get('HTTP_REFERER') or 'semester_results'
    return redirect(redirect_url)


@login_required
def api_get_transfer_grade(request, student_id):
    """
    AJAX API to fetch existing transfer grade records for a student.
    """
    student = get_object_or_404(Student, id=student_id)
    semester = request.GET.get('semester', '1')
    academic_year = student.academic_year or (student.classroom.academic_year if student.classroom else None) or AcademicYear.objects.first()

    record = StudentTransferGrade.objects.filter(
        student=student,
        academic_year=academic_year,
        semester=int(semester)
    ).first()

    if record:
        return JsonResponse({
            'success': True,
            'exists': True,
            'student_name': student.khmer_name,
            'student_id': student.student_id,
            'semester': record.semester,
            'prior_school_name': record.prior_school_name or '',
            'monthly_average': str(record.monthly_average) if record.monthly_average is not None else '',
            'semester_exam_score': str(record.semester_exam_score) if record.semester_exam_score is not None else '',
            'semester_final_average': str(record.semester_final_average),
            'letter_grade': record.letter_grade,
            'remarks': record.remarks or '',
        })
    else:
        return JsonResponse({
            'success': True,
            'exists': False,
            'student_name': student.khmer_name,
            'student_id': student.student_id,
            'semester': int(semester),
        })


@login_required
def export_semester_results_excel(request):
    """
    Exports Semester Results table to Microsoft Excel (.xlsx).
    """
    classroom_id = request.GET.get('classroom')
    semester = int(request.GET.get('semester', '1'))
    academic_year_id = request.GET.get('year')

    classroom = get_object_or_404(Classroom, id=classroom_id) if classroom_id else None
    academic_year = AcademicYear.objects.filter(id=academic_year_id).first() if academic_year_id else (classroom.academic_year if classroom else None)

    if not classroom or not academic_year:
        messages.error(request, "សូមជ្រើសរើសថ្នាក់រៀន និងឆ្នាំសិក្សា!")
        return redirect('semester_results')

    data = AcademicResultService.compute_semester_results(classroom, academic_year, semester)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"លទ្ធផលឆមាសទី{semester}"

    # Header fonts and styles
    title_font = Font(name='Khmer OS Siemreap', size=14, bold=True, color='1E293B')
    header_font = Font(name='Khmer OS Siemreap', size=10, bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='1E40AF', end_color='1E40AF', fill_type='solid')
    border_thin = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    # Title rows
    ws.merge_cells('A1:J1')
    ws['A1'] = f"តារាងលទ្ធផលសិក្សាប្រចាំឆមាសទី{semester} ឆ្នាំសិក្សា {academic_year.name}"
    ws['A1'].font = title_font
    ws['A1'].alignment = Alignment(horizontal='center', vertical='center')

    ws.merge_cells('A2:J2')
    ws['A2'] = f"ថ្នាក់ទី៖ {classroom.name} ({classroom.get_track_display()}) | សិស្សសរុប៖ {data['total_students']} នាក់ (ជាប់ {data['passed_count']} ធ្លាក់ {data['failed_count']})"
    ws['A2'].alignment = Alignment(horizontal='center', vertical='center')

    # Column Headers
    headers = ['ចំណាត់ថ្នាក់', 'កូដសិស្ស', 'ឈ្មោះសិស្ស', 'ភេទ']
    for t in data['monthly_terms']:
        headers.append(f"{t.name} (%)")
    headers.extend(['មធ្យមភាគប្រចាំខែ', 'ពិន្ទុប្រឡងឆមាស', f'មធ្យមភាគឆមាសទី{semester}', 'និទ្ទេស', 'លទ្ធផល', 'កំណត់សម្គាល់'])

    ws.append([]) # empty row
    ws.append(headers)

    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=4, column=col_num)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center')

    # Data Rows
    for r in data['students_data']:
        row_data = [
            r['rank'],
            r['student'].student_id,
            r['student'].khmer_name,
            r['student'].get_gender_display(),
        ]
        for mc in r['month_cols']:
            row_data.append(f"{mc['percentage']}%" if mc['percentage'] is not None else "-")
        
        row_data.extend([
            f"{r['monthly_average']}%" if r['monthly_average'] is not None else "-",
            f"{r['semester_exam_score']}%" if r['semester_exam_score'] is not None else "-",
            f"{r['semester_final_average']}%",
            r['letter_grade'],
            "ជាប់" if r['passed'] else "ធ្លាក់",
            r['notes']
        ])
        ws.append(row_data)

    # Set column widths & borders
    for row in ws.iter_rows(min_row=4, max_row=ws.max_row, min_col=1, max_col=len(headers)):
        for cell in row:
            cell.border = border_thin
            if cell.row > 4:
                cell.alignment = Alignment(vertical='center')

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    filename = f"Semester_{semester}_Results_{classroom.code}_{academic_year.name}.xlsx"
    response = HttpResponse(buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def export_annual_results_excel(request):
    """
    Exports Annual Results table to Microsoft Excel (.xlsx).
    """
    classroom_id = request.GET.get('classroom')
    academic_year_id = request.GET.get('year')

    classroom = get_object_or_404(Classroom, id=classroom_id) if classroom_id else None
    academic_year = AcademicYear.objects.filter(id=academic_year_id).first() if academic_year_id else (classroom.academic_year if classroom else None)

    if not classroom or not academic_year:
        messages.error(request, "សូមជ្រើសរើសថ្នាក់រៀន និងឆ្នាំសិក្សា!")
        return redirect('annual_results')

    data = AcademicResultService.compute_annual_results(classroom, academic_year)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "លទ្ធផលប្រចាំឆ្នាំ"

    title_font = Font(name='Khmer OS Siemreap', size=14, bold=True, color='1E293B')
    header_font = Font(name='Khmer OS Siemreap', size=10, bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='15803D', end_color='15803D', fill_type='solid')
    border_thin = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    ws.merge_cells('A1:J1')
    ws['A1'] = f"តារាងលទ្ធផលសិក្សាប្រចាំឆ្នាំ ឆ្នាំសិក្សា {academic_year.name}"
    ws['A1'].font = title_font
    ws['A1'].alignment = Alignment(horizontal='center', vertical='center')

    ws.merge_cells('A2:J2')
    ws['A2'] = f"ថ្នាក់ទី៖ {classroom.name} ({classroom.get_track_display()}) | សិស្សសរុប៖ {data['total_students']} នាក់ (ជាប់ {data['passed_count']} ធ្លាក់ {data['failed_count']})"
    ws['A2'].alignment = Alignment(horizontal='center', vertical='center')

    headers = ['ចំណាត់ថ្នាក់', 'កូដសិស្ស', 'ឈ្មោះសិស្ស', 'ភេទ', 'មធ្យមភាគឆមាសទី១', 'មធ្យមភាគឆមាសទី២', 'មធ្យមភាគប្រចាំឆ្នាំ', 'និទ្ទេស', 'លទ្ធផលឡើងថ្នាក់', 'កំណត់សម្គាល់']

    ws.append([])
    ws.append(headers)

    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=4, column=col_num)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center')

    for r in data['students_data']:
        ws.append([
            r['rank'],
            r['student'].student_id,
            r['student'].khmer_name,
            r['student'].get_gender_display(),
            f"{r['s1_average']}%" if r['s1_average'] is not None else "-",
            f"{r['s2_average']}%" if r['s2_average'] is not None else "-",
            f"{r['annual_average']}%",
            r['letter_grade'],
            r['promotion_status'],
            r['notes']
        ])

    for row in ws.iter_rows(min_row=4, max_row=ws.max_row, min_col=1, max_col=len(headers)):
        for cell in row:
            cell.border = border_thin
            if cell.row > 4:
                cell.alignment = Alignment(vertical='center')

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    filename = f"Annual_Results_{classroom.code}_{academic_year.name}.xlsx"
    response = HttpResponse(buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response



