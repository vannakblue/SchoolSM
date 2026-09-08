from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db import transaction
from django.db.models import Count, Q, Avg, Max, Min, Sum
from decimal import Decimal
import json
import random
from django.conf import settings
from django.utils import timezone
import openpyxl
from io import BytesIO
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

from apps.accounts.decorators import role_required
from .models import (
    ExamTerm, Grade,
    OnlineExam, OnlineExamQuestion, OnlineExamOption,
    OnlineExamSubmission, OnlineExamAnswer
)
from .forms import OnlineExamForm, OnlineExamQuestionForm
from apps.academics.models import Classroom, Subject, AcademicYear, GradeLevelRule, ClassSubject
from apps.students.models import Student
from apps.teachers.models import Teacher
from apps.examinations.services import resolve_student_and_children_for_user


# ==============================================================================
# TEACHER & ADMIN: ONLINE EXAM MANAGEMENT
# ==============================================================================

@login_required
@role_required(['ADMIN', 'TEACHER'])
def online_exam_list(request):
    """
    List of online exams created for terms and subjects.
    Teachers can filter and manage exams for their subjects.
    """
    user = request.user
    is_admin = (user.role == 'ADMIN' or user.is_superuser)
    teacher = getattr(user, 'teacher_profile', None)

    # Base query
    exams = OnlineExam.objects.select_related('exam_term', 'subject', 'teacher', 'created_by').prefetch_related('target_classrooms', 'questions', 'submissions')

    # If teacher and not admin, show exams created by teacher or targeting teacher's assigned subjects
    if not is_admin and teacher:
        assigned_subject_ids = list(ClassSubject.objects.filter(teacher=teacher).values_list('subject_id', flat=True))
        if teacher.primary_subject_id:
            assigned_subject_ids.append(teacher.primary_subject_id)
        if teacher.secondary_subject_id:
            assigned_subject_ids.append(teacher.secondary_subject_id)
        
        exams = exams.filter(Q(created_by=user) | Q(teacher=teacher) | Q(subject_id__in=assigned_subject_ids)).distinct()

    # Filters
    selected_term = request.GET.get('term')
    if selected_term and selected_term.isdigit():
        exams = exams.filter(exam_term_id=int(selected_term))

    selected_subject = request.GET.get('subject')
    if selected_subject and selected_subject.isdigit():
        exams = exams.filter(subject_id=int(selected_subject))

    selected_grade = request.GET.get('grade')
    if selected_grade and selected_grade.isdigit():
        exams = exams.filter(grade_level=int(selected_grade))

    selected_status = request.GET.get('status')
    if selected_status:
        exams = exams.filter(status=selected_status)

    terms = ExamTerm.objects.all().order_by('-start_date')
    subjects = Subject.objects.all().order_by('order', 'id')

    return render(request, 'examinations/online_exams/exam_list.html', {
        'exams': exams,
        'terms': terms,
        'subjects': subjects,
        'selected_term': selected_term or '',
        'selected_subject': selected_subject or '',
        'selected_grade': selected_grade or '',
        'selected_status': selected_status or '',
        'is_admin': is_admin,
    })


@login_required
@role_required(['ADMIN', 'TEACHER'])
def online_exam_create(request):
    """
    Create a new online exam paper.
    """
    teacher = getattr(request.user, 'teacher_profile', None)
    if request.method == 'POST':
        form = OnlineExamForm(request.POST, teacher=teacher)
        if form.is_valid():
            exam = form.save(commit=False)
            exam.created_by = request.user
            if teacher:
                exam.teacher = teacher
            exam.save()
            form.save_m2m() # save target_classrooms
            messages.success(request, f'បានបង្កើតវិញ្ញាសា "{exam.title}" ដោយជោគជ័យ! សូមបន្ថែមសំណួរ និងចម្លើយខាងក្រោម។')
            return redirect('online_exam_questions_manage', exam_id=exam.id)
    else:
        initial_data = {
            'duration_minutes': 45,
            'total_score': Decimal('100.00'),
            'pass_score': Decimal('50.00'),
            'max_attempts': 1,
            'is_published': False,
            'status': OnlineExam.ExamStatus.DRAFT,
            'shuffle_questions': True,
            'shuffle_options': True,
            'show_result_immediately': True,
            'show_correct_answers': True,
        }
        form = OnlineExamForm(initial=initial_data, teacher=teacher)

    return render(request, 'examinations/online_exams/exam_form.html', {
        'form': form,
        'is_create': True,
        'title': 'បង្កើតវិញ្ញាសាប្រឡងអនឡាញថ្មី',
    })


@login_required
@role_required(['ADMIN', 'TEACHER'])
def online_exam_edit(request, exam_id):
    """
    Edit an existing online exam.
    """
    exam = get_object_or_404(OnlineExam, id=exam_id)
    teacher = getattr(request.user, 'teacher_profile', None)

    # Permission check
    if not (request.user.role == 'ADMIN' or request.user.is_superuser or exam.created_by == request.user or exam.teacher == teacher):
        messages.error(request, 'អ្នកគ្មានសិទ្ធិកែប្រែវិញ្ញាសានេះទេ។')
        return redirect('online_exam_list')

    if request.method == 'POST':
        form = OnlineExamForm(request.POST, instance=exam, teacher=teacher)
        if form.is_valid():
            form.save()
            messages.success(request, f'បានកែប្រែវិញ្ញាសា "{exam.title}" ដោយជោគជ័យ!')
            return redirect('online_exam_list')
    else:
        form = OnlineExamForm(instance=exam, teacher=teacher)

    return render(request, 'examinations/online_exams/exam_form.html', {
        'form': form,
        'exam': exam,
        'is_create': False,
        'title': f'កែប្រែវិញ្ញាសា៖ {exam.title}',
    })


@login_required
@role_required(['ADMIN', 'TEACHER'])
def online_exam_delete(request, exam_id):
    """
    Delete an online exam.
    """
    exam = get_object_or_404(OnlineExam, id=exam_id)
    if request.method == 'POST':
        title = exam.title
        exam.delete()
        messages.success(request, f'បានលុបវិញ្ញាសា "{title}" រួចរាល់។')
    return redirect('online_exam_list')


@login_required
@role_required(['ADMIN', 'TEACHER'])
def api_toggle_online_exam_publish(request, exam_id):
    """
    AJAX endpoint to quickly toggle published state.
    """
    exam = get_object_or_404(OnlineExam, id=exam_id)
    exam.is_published = not exam.is_published
    if exam.is_published:
        exam.status = OnlineExam.ExamStatus.PUBLISHED
    else:
        exam.status = OnlineExam.ExamStatus.DRAFT
    exam.save()
    return JsonResponse({
        'success': True,
        'is_published': exam.is_published,
        'status': exam.status,
        'badge_label': 'ផ្សព្វផ្សាយ' if exam.is_published else 'ព្រាង'
    })


@login_required
@role_required(['ADMIN', 'TEACHER'])
def online_exam_questions_manage(request, exam_id):
    """
    Manage questions and options for a given exam.
    Supports adding, editing, deleting, and bulk text import.
    """
    exam = get_object_or_404(OnlineExam.objects.select_related('exam_term', 'subject'), id=exam_id)
    questions = exam.questions.prefetch_related('options').order_by('order', 'id')

    if request.method == 'POST':
        action = request.POST.get('action')

        # 1. Add Single Question with Options
        if action == 'add_question':
            q_text = request.POST.get('question_text', '').strip()
            points = request.POST.get('points', '1')
            order = request.POST.get('order') or str(questions.count() + 1)
            explanation = request.POST.get('explanation', '').strip()
            correct_choice_idx = request.POST.get('correct_option', '0')

            if q_text:
                q = OnlineExamQuestion.objects.create(
                    exam=exam,
                    question_text=q_text,
                    points=Decimal(str(points) if points else '1.00'),
                    order=int(order) if order.isdigit() else 0,
                    explanation=explanation or None,
                    image=request.FILES.get('image')
                )
                # Create options A, B, C, D...
                for i in range(1, 7):
                    opt_text = request.POST.get(f'option_{i}', '').strip()
                    if opt_text:
                        is_corr = (str(i) == str(correct_choice_idx))
                        OnlineExamOption.objects.create(
                            question=q,
                            option_text=opt_text,
                            is_correct=is_corr,
                            order=i
                        )
                messages.success(request, 'បានបន្ថែមសំណួរថ្មីដោយជោគជ័យ!')
            else:
                messages.error(request, 'សូមបញ្ចូលខ្លឹមសារសំណួរ។')
            return redirect('online_exam_questions_manage', exam_id=exam.id)

        # 2. Edit Question
        elif action == 'edit_question':
            q_id = request.POST.get('question_id')
            q = get_object_or_404(OnlineExamQuestion, id=q_id, exam=exam)
            q.question_text = request.POST.get('question_text', '').strip()
            points = request.POST.get('points', '1')
            q.points = Decimal(str(points) if points else '1.00')
            q.order = int(request.POST.get('order', 0))
            q.explanation = request.POST.get('explanation', '').strip() or None
            if request.FILES.get('image'):
                q.image = request.FILES.get('image')
            q.save()

            correct_choice_idx = request.POST.get('correct_option', '0')
            # Update or recreate options
            q.options.all().delete()
            for i in range(1, 7):
                opt_text = request.POST.get(f'option_{i}', '').strip()
                if opt_text:
                    is_corr = (str(i) == str(correct_choice_idx))
                    OnlineExamOption.objects.create(
                        question=q,
                        option_text=opt_text,
                        is_correct=is_corr,
                        order=i
                    )
            messages.success(request, f'បានកែប្រែសំណួរលំដាប់ទី {q.order} ដោយជោគជ័យ!')
            return redirect('online_exam_questions_manage', exam_id=exam.id)

        # 3. Delete Question
        elif action == 'delete_question':
            q_id = request.POST.get('question_id')
            q = get_object_or_404(OnlineExamQuestion, id=q_id, exam=exam)
            q.delete()
            messages.success(request, 'បានលុបសំណួររួចរាល់។')
            return redirect('online_exam_questions_manage', exam_id=exam.id)

        # 4. Bulk Import from Raw Text
        elif action == 'bulk_import':
            raw_text = request.POST.get('raw_import_text', '')
            imported_count = parse_and_import_raw_questions(exam, raw_text)
            if imported_count > 0:
                messages.success(request, f'បានបញ្ចូលសំណួរចំនួន {imported_count} សំណួរដោយស្វ័យប្រវត្តិ!')
            else:
                messages.warning(request, 'មិនអាចរកឃើញសំណួរតាមទម្រង់ដែលបានកំណត់ទេ។ សូមពិនិត្យគំរូទម្រង់ឡើងវិញ។')
            return redirect('online_exam_questions_manage', exam_id=exam.id)

    return render(request, 'examinations/online_exams/questions_manage.html', {
        'exam': exam,
        'questions': questions,
        'total_points': exam.total_question_points,
    })


def parse_and_import_raw_questions(exam, text):
    """
    Helper to parse questions pasted in plain text.
    Format example:
    1. តើព្រះរាជាណាចក្រកម្ពុជាមានប៉ុន្មានខេត្ត-រាជធានី?
    A. 24
    B. 25* (or Answer: B)
    C. 26
    D. 23
    """
    import re
    lines = [ln.strip() for ln in text.split('\n') if ln.strip()]
    if not lines:
        return 0

    current_q_text = None
    current_options = []
    correct_char = None
    imported = 0
    order_counter = exam.questions.count() + 1

    def commit_question(q_txt, opts, corr_ch):
        nonlocal imported, order_counter
        if not q_txt or not opts:
            return
        q_obj = OnlineExamQuestion.objects.create(
            exam=exam,
            question_text=q_txt,
            points=Decimal('1.00'),
            order=order_counter
        )
        order_counter += 1
        for idx, (letter, o_txt, is_c) in enumerate(opts, 1):
            flag = bool(is_c or (corr_ch and corr_ch.upper() == letter.upper()))
            OnlineExamOption.objects.create(
                question=q_obj,
                option_text=o_txt,
                is_correct=flag,
                order=idx
            )
        imported += 1

    for line in lines:
        # Check if new question starts (e.g. 1. or ១. or Q1:)
        q_match = re.match(r'^(?:[០-៩0-9]+[\.\:\)]|សំណួរ\s*[០-៩0-9]+[\.\:\)])\s*(.*)', line, re.IGNORECASE)
        if q_match:
            # Commit previous question
            if current_q_text and current_options:
                commit_question(current_q_text, current_options, correct_char)
            current_q_text = q_match.group(1).strip()
            current_options = []
            correct_char = None
            continue

        # Check for answer line like "Answer: A" or "ចម្លើយ: B"
        ans_match = re.match(r'^(?:Answer|ចម្លើយ|Ans|Key)\s*[\:\=]\s*([A-Za-zក-ឃ])', line, re.IGNORECASE)
        if ans_match:
            correct_char = ans_match.group(1).strip()
            continue

        # Check option line like A. or B) or ក.
        opt_match = re.match(r'^([A-Fa-fក-ង1-6])[\.\)\-]\s*(.*)', line)
        if opt_match and current_q_text:
            letter = opt_match.group(1).upper()
            txt = opt_match.group(2).strip()
            is_c = False
            if '*' in txt:
                is_c = True
                txt = txt.replace('*', '').strip()
            current_options.append((letter, txt, is_c))
        elif current_q_text and not current_options:
            current_q_text += " " + line

    # Final commit
    if current_q_text and current_options:
        commit_question(current_q_text, current_options, correct_char)

    return imported


@login_required
@role_required(['ADMIN', 'TEACHER'])
def online_exam_submissions_list(request, exam_id):
    """
    View all student submissions for an online exam, with class statistics
    and option to Sync directly to the Grade Matrix.
    """
    exam = get_object_or_404(OnlineExam.objects.select_related('exam_term', 'subject', 'teacher'), id=exam_id)
    submissions = exam.submissions.select_related('student', 'classroom').order_by('-score_obtained', 'student__khmer_name')

    # Calculate statistics
    total_subs = submissions.count()
    pass_subs = submissions.filter(is_passed=True).count()
    pass_rate = round((pass_subs / total_subs) * 100, 1) if total_subs > 0 else 0.0

    stats = submissions.aggregate(
        avg_score=Avg('score_obtained'),
        max_score=Max('score_obtained'),
        min_score=Min('score_obtained'),
    )

    return render(request, 'examinations/online_exams/submissions_list.html', {
        'exam': exam,
        'submissions': submissions,
        'total_subs': total_subs,
        'pass_subs': pass_subs,
        'pass_rate': pass_rate,
        'avg_score': round(stats['avg_score'] or 0, 2),
        'max_score': stats['max_score'] or 0,
        'min_score': stats['min_score'] or 0,
    })


@login_required
@role_required(['ADMIN', 'TEACHER'])
def online_exam_submission_detail(request, submission_id):
    """
    View detailed answers and review for an individual student submission.
    """
    submission = get_object_or_404(
        OnlineExamSubmission.objects.select_related('exam', 'student', 'classroom', 'exam__subject', 'exam__exam_term'),
        id=submission_id
    )
    answers = submission.answers.select_related('question', 'selected_option').prefetch_related('question__options').order_by('question__order', 'question__id')

    return render(request, 'examinations/online_exams/submission_detail.html', {
        'submission': submission,
        'exam': submission.exam,
        'answers': answers,
    })


@login_required
@role_required(['ADMIN', 'TEACHER'])
def api_sync_online_exam_to_grades(request, exam_id):
    """
    Syncs scores from completed OnlineExamSubmissions directly into the official Grade Matrix.
    Creates or updates Grade entries for each student.
    """
    exam = get_object_or_404(OnlineExam, id=exam_id)
    submissions = exam.submissions.filter(status=OnlineExamSubmission.SubmissionStatus.SUBMITTED).select_related('student', 'classroom')

    synced_count = 0
    updated_count = 0

    with transaction.atomic():
        for sub in submissions:
            classroom = sub.classroom or sub.student.classroom
            if not classroom:
                continue

            grade_obj, created = Grade.objects.get_or_create(
                student=sub.student,
                subject=exam.subject,
                exam_term=exam.exam_term,
                defaults={
                    'classroom': classroom,
                    'score': sub.score_obtained,
                    'max_score': exam.total_score,
                    'remarks': f'តេស្តអនឡាញ៖ {exam.title}',
                }
            )

            if not created:
                grade_obj.score = sub.score_obtained
                grade_obj.max_score = exam.total_score
                grade_obj.classroom = classroom
                grade_obj.remarks = f'តេស្តអនឡាញ៖ {exam.title}'
                grade_obj.save()
                updated_count += 1
            else:
                synced_count += 1

            sub.synced_to_grade = True
            sub.save()

    total_affected = synced_count + updated_count
    return JsonResponse({
        'success': True,
        'message': f'បានបញ្ចូលពិន្ទុទៅក្នុងបញ្ជីផ្លូវការ (Grade Matrix) ដោយជោគជ័យ ចំនួន {total_affected} នាក់ (ថ្មី៖ {synced_count}, កែប្រែ៖ {updated_count})!',
        'synced_count': synced_count,
        'updated_count': updated_count,
    })


@login_required
@role_required(['ADMIN', 'TEACHER'])
def online_exam_export_excel(request, exam_id):
    """
    Exports online exam submissions to an Excel file with Khmer header formatting.
    """
    exam = get_object_or_404(OnlineExam.objects.select_related('exam_term', 'subject'), id=exam_id)
    submissions = exam.submissions.select_related('student', 'classroom').order_by('-score_obtained', 'student__khmer_name')

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "លទ្ធផលប្រឡងអនឡាញ"

    # Header styling
    header_fill = PatternFill(start_color="1E40AF", end_color="1E40AF", fill_type="solid")
    header_font = Font(name="Battambang", size=11, bold=True, color="FFFFFF")
    title_font = Font(name="Battambang", size=14, bold=True, color="1E3A8A")
    regular_font = Font(name="Battambang", size=10)
    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    # Title rows
    ws.append([f"របាយការណ៍លទ្ធផលប្រឡងអនឡាញ៖ {exam.title}"])
    ws.merge_cells("A1:I1")
    ws["A1"].font = title_font
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 30

    ws.append([f"សម័យប្រឡង៖ {exam.exam_term.name} | មុខវិជ្ជា៖ {exam.subject.name_kh} | ពិន្ទុពេញ៖ {exam.total_score} | ពិន្ទុជាប់៖ {exam.pass_score}"])
    ws.merge_cells("A2:I2")
    ws["A2"].font = Font(name="Battambang", size=10, italic=True)
    ws["A2"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[2].height = 20

    ws.append([]) # Blank row

    headers = ["ល.រ", "អត្តលេខ", "គោត្តនាម-នាម", "ភេទ", "ថ្នាក់", "ពិន្ទុទទួលបាន", "ភាគរយ", "និទ្ទេស", "លទ្ធផល"]
    ws.append(headers)
    ws.row_dimensions[4].height = 25

    for col_idx, _ in enumerate(headers, 1):
        cell = ws.cell(row=4, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    row_idx = 5
    for idx, sub in enumerate(submissions, 1):
        gender_kh = "ស្រី" if sub.student.gender == 'F' else "ប្រុស"
        class_name = sub.classroom.name if sub.classroom else (sub.student.classroom.name if sub.student.classroom else "-")
        status_kh = "ជាប់" if sub.is_passed else "ធ្លាក់"

        row_data = [
            idx,
            sub.student.student_id or "-",
            sub.student.khmer_name,
            gender_kh,
            class_name,
            float(sub.score_obtained),
            f"{sub.percentage}%",
            sub.letter_grade or "-",
            status_kh
        ]
        ws.append(row_data)

        for c_idx in range(1, len(row_data) + 1):
            cell = ws.cell(row=row_idx, column=c_idx)
            cell.font = regular_font
            cell.border = thin_border
            if c_idx in [1, 2, 4, 5, 7, 8, 9]:
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif c_idx == 6:
                cell.alignment = Alignment(horizontal="right", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")
        row_idx += 1

    # Adjust column widths
    column_widths = [8, 15, 25, 10, 14, 16, 12, 12, 12]
    for i, w in enumerate(column_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"online_exam_results_{exam.id}_{timezone.now().strftime('%Y%m%d')}.xlsx"
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ==============================================================================
# STUDENT PORTAL: TAKING EXAMS & INSTANT RESULTS
# ==============================================================================

@login_required
def student_online_exams_list(request):
    """
    Student View: Lists available online exams for the student's classroom/grade.
    """
    student, _ = resolve_student_and_children_for_user(request.user)
    
    # If no student profile linked (e.g. Admin/Teacher testing the portal view), pick first active student
    if not student and (request.user.role in ['ADMIN', 'TEACHER'] or request.user.is_superuser):
        student = Student.objects.filter(status='ACTIVE').first()

    if not student:
        messages.warning(request, 'មិនទាន់មានទម្រង់សិស្សភ្ជាប់ជាមួយគណនីរបស់អ្នកនៅឡើយទេ។')
        return redirect('student_dashboard')

    classroom = student.classroom

    # Query published exams matching student's classroom or grade level
    exams_qs = OnlineExam.objects.filter(is_published=True).select_related('exam_term', 'subject', 'teacher')

    if classroom:
        exams_qs = exams_qs.filter(
            Q(target_classrooms=classroom) |
            Q(grade_level=classroom.grade_level) |
            Q(target_classrooms__isnull=True, grade_level__isnull=True)
        ).distinct()

    exams_qs = exams_qs.order_by('-start_time', '-id')

    # Attach student's submission status for each exam
    exam_cards = []
    for ex in exams_qs:
        sub = OnlineExamSubmission.objects.filter(exam=ex, student=student).order_by('-attempt_number').first()
        attempts_used = OnlineExamSubmission.objects.filter(exam=ex, student=student, status=OnlineExamSubmission.SubmissionStatus.SUBMITTED).count()
        can_take = (attempts_used < ex.max_attempts) and ex.is_active_now
        exam_cards.append({
            'exam': ex,
            'submission': sub,
            'attempts_used': attempts_used,
            'can_take': can_take,
            'status_info': ex.get_time_status(),
        })

    return render(request, 'examinations/online_exams/student_exam_list.html', {
        'student': student,
        'classroom': classroom,
        'exam_cards': exam_cards,
    })


@login_required
def student_take_online_exam(request, exam_id):
    """
    Student takes the online exam.
    Provides live timer, focus mode, auto-save in browser, and instant submission evaluation.
    """
    student, _ = resolve_student_and_children_for_user(request.user)
    if not student and (request.user.role in ['ADMIN', 'TEACHER'] or request.user.is_superuser):
        student = Student.objects.filter(status='ACTIVE').first()

    if not student:
        messages.error(request, 'រកមិនឃើញព័ត៌មានសិស្សសម្រាប់ការប្រឡងទេ។')
        return redirect('student_online_exams_list')

    exam = get_object_or_404(OnlineExam.objects.select_related('subject', 'exam_term'), id=exam_id)

    # Check publication and status
    if not exam.is_published or exam.status == OnlineExam.ExamStatus.CLOSED:
        messages.error(request, 'វិញ្ញាសានេះត្រូវបានបិទបញ្ចប់ ឬមិនទាន់ផ្សព្វផ្សាយនៅឡើយទេ។')
        return redirect('student_online_exams_list')

    # Check timing
    now = timezone.now()
    if exam.start_time and now < exam.start_time:
        messages.warning(request, f'វិញ្ញាសានេះនឹងចាប់ផ្តើមនៅម៉ោង {exam.start_time.strftime("%d/%m/%Y %H:%M")}')
        return redirect('student_online_exams_list')

    if exam.end_time and now > exam.end_time:
        messages.error(request, 'វិញ្ញាសានេះបានផុតកំណត់ម៉ោងប្រឡងហើយ។')
        return redirect('student_online_exams_list')

    # Check max attempts
    completed_subs = OnlineExamSubmission.objects.filter(
        exam=exam, student=student, status=OnlineExamSubmission.SubmissionStatus.SUBMITTED
    )
    if completed_subs.count() >= exam.max_attempts:
        last_sub = completed_subs.order_by('-submitted_at').first()
        messages.info(request, 'អ្នកបានប្រឡងវិញ្ញាសានេះរួចរាល់ហើយ។')
        return redirect('student_exam_result_view', submission_id=last_sub.id)

    # Find or create in-progress submission
    submission = OnlineExamSubmission.objects.filter(
        exam=exam, student=student, status=OnlineExamSubmission.SubmissionStatus.IN_PROGRESS
    ).first()

    if not submission:
        attempt_num = completed_subs.count() + 1
        submission = OnlineExamSubmission.objects.create(
            exam=exam,
            student=student,
            classroom=student.classroom,
            attempt_number=attempt_num,
            status=OnlineExamSubmission.SubmissionStatus.IN_PROGRESS,
            started_at=timezone.now()
        )

    # Calculate remaining seconds based on duration_minutes
    elapsed_seconds = int((now - submission.started_at).total_seconds())
    total_allowed_seconds = exam.duration_minutes * 60
    remaining_seconds = max(0, total_allowed_seconds - elapsed_seconds)

    # If timer has completely run out before POST, auto-submit
    if remaining_seconds <= 0 and request.method == 'GET':
        submission.calculate_results(save=True)
        messages.warning(request, 'ពេលវេលាប្រឡងបានផុតកំណត់។ ប្រព័ន្ធបានប្រគល់កិច្ចការដោយស្វ័យប្រវត្តិ។')
        return redirect('student_exam_result_view', submission_id=submission.id)

    # POST: Evaluate Submission Immediately
    if request.method == 'POST':
        time_spent = request.POST.get('time_spent_seconds', '0')
        submission.time_spent_seconds = int(time_spent) if time_spent.isdigit() else elapsed_seconds

        with transaction.atomic():
            for question in exam.questions.all():
                ans_key = f"question_{question.id}"
                selected_opt_id = request.POST.get(ans_key)

                selected_opt = None
                if selected_opt_id and str(selected_opt_id).isdigit():
                    selected_opt = OnlineExamOption.objects.filter(id=int(selected_opt_id), question=question).first()

                # Save answer
                OnlineExamAnswer.objects.update_or_create(
                    submission=submission,
                    question=question,
                    defaults={
                        'selected_option': selected_opt,
                        'is_correct': (selected_opt.is_correct if selected_opt else False),
                        'points_awarded': (question.points if (selected_opt and selected_opt.is_correct) else Decimal('0.00'))
                    }
                )

            # Compute and commit instant grade results!
            submission.calculate_results(save=True)

        messages.success(request, 'អ្នកបានប្រគល់កិច្ចការប្រឡងដោយជោគជ័យ!')
        return redirect('student_exam_result_view', submission_id=submission.id)

    # Prepare Questions & Options
    questions_list = list(exam.questions.prefetch_related('options').all())
    if exam.shuffle_questions:
        # Seed by submission ID so refresh maintains consistent order
        rng = random.Random(submission.id)
        rng.shuffle(questions_list)

    questions_data = []
    for q in questions_list:
        opts = list(q.options.all())
        if exam.shuffle_options:
            rng_opts = random.Random(submission.id + q.id)
            rng_opts.shuffle(opts)
        questions_data.append({
            'question': q,
            'options': opts,
        })

    return render(request, 'examinations/online_exams/student_take_exam.html', {
        'exam': exam,
        'student': student,
        'submission': submission,
        'questions_data': questions_data,
        'remaining_seconds': remaining_seconds,
        'total_duration_minutes': exam.duration_minutes,
    })


@login_required
def student_exam_result_view(request, submission_id):
    """
    Displays instant exam results, score, percentage, mention,
    and detailed question-by-question review.
    """
    submission = get_object_or_404(
        OnlineExamSubmission.objects.select_related('exam', 'student', 'classroom', 'exam__subject', 'exam__exam_term'),
        id=submission_id
    )

    user = request.user
    is_staff = (user.role in ['ADMIN', 'TEACHER'] or user.is_superuser)
    student, _ = resolve_student_and_children_for_user(user)

    # Permission check: either staff or student who took the test
    if not is_staff and (not student or student.id != submission.student_id):
        messages.error(request, 'អ្នកគ្មានសិទ្ធិមើលលទ្ធផលប្រឡងនេះទេ។')
        return redirect('student_dashboard')

    exam = submission.exam
    answers = submission.answers.select_related('question', 'selected_option').prefetch_related('question__options').order_by('question__order', 'question__id')

    # Prepare review breakdown
    breakdown = []
    correct_count = 0
    wrong_count = 0
    unanswered_count = 0

    for ans in answers:
        if ans.is_correct:
            correct_count += 1
        elif ans.selected_option is None:
            unanswered_count += 1
        else:
            wrong_count += 1

        breakdown.append({
            'answer': ans,
            'question': ans.question,
            'selected_option': ans.selected_option,
            'correct_option': ans.question.correct_option,
            'is_correct': ans.is_correct,
            'points_awarded': ans.points_awarded,
            'explanation': ans.question.explanation,
        })

    return render(request, 'examinations/online_exams/student_exam_result.html', {
        'submission': submission,
        'exam': exam,
        'student': submission.student,
        'breakdown': breakdown,
        'correct_count': correct_count,
        'wrong_count': wrong_count,
        'unanswered_count': unanswered_count,
        'show_correct_answers': exam.show_correct_answers or is_staff,
    })
