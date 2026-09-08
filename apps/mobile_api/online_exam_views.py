import datetime
from decimal import Decimal
from django.utils import timezone
from django.db.models import Q, Count, Avg
from django.shortcuts import get_object_or_404
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response

from apps.accounts.models import User
from apps.students.models import Student
from apps.examinations.models import (
    OnlineExam, OnlineExamQuestion, OnlineExamOption,
    OnlineExamSubmission, OnlineExamAnswer, Grade
)
from apps.examinations.services import resolve_student_and_children_for_user


class MobileOnlineExamListView(APIView):
    """
    Returns list of online examinations for the authenticated student or teacher.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.role == User.Role.STUDENT:
            student, _ = resolve_student_and_children_for_user(user)
            if not student:
                student = getattr(user, 'student_profile', None)
            if not student:
                student = Student.objects.filter(user=user).first()

            if not student:
                return Response({'status': 'success', 'exams': []})

            # Exams matching student's classroom or grade level
            classroom = student.classroom
            grade_level = classroom.grade_level if classroom else None

            base_q = Q(is_published=True)
            if classroom and grade_level:
                scope_q = (
                    Q(target_classrooms=classroom) |
                    Q(grade_level=grade_level) |
                    (Q(target_classrooms__isnull=True) & Q(grade_level__isnull=True))
                )
            elif classroom:
                scope_q = (
                    Q(target_classrooms=classroom) |
                    (Q(target_classrooms__isnull=True) & Q(grade_level__isnull=True))
                )
            else:
                scope_q = Q(target_classrooms__isnull=True) & Q(grade_level__isnull=True)

            exams = (
                OnlineExam.objects.filter(base_q & scope_q)
                .select_related('exam_term', 'subject', 'teacher', 'teacher__user')
                .prefetch_related('target_classrooms', 'questions')
                .distinct()
                .order_by('-created_at')
            )

            results = []
            for ex in exams:
                # Submissions by this student
                subs = OnlineExamSubmission.objects.filter(exam=ex, student=student)
                attempts_used = subs.filter(status=OnlineExamSubmission.SubmissionStatus.SUBMITTED).count()
                in_progress_sub = subs.filter(status=OnlineExamSubmission.SubmissionStatus.IN_PROGRESS).order_by('-started_at').first()
                latest_sub = subs.filter(status=OnlineExamSubmission.SubmissionStatus.SUBMITTED).order_by('-submitted_at').first()

                # Status check
                time_status_code, badge_color, time_status_label = ex.get_time_status()
                
                # Check if in_progress is still within time
                can_take = False
                action_label = "ចូលប្រឡង"

                if in_progress_sub:
                    # Check if session has expired
                    elapsed = (timezone.now() - in_progress_sub.started_at).total_seconds()
                    total_allowed = (ex.duration_minutes + 5) * 60  # 5 min grace period
                    if elapsed <= total_allowed:
                        can_take = True
                        action_label = "បន្តការប្រឡង"
                    else:
                        in_progress_sub.status = OnlineExamSubmission.SubmissionStatus.EXPIRED
                        in_progress_sub.calculate_results(save=True)
                        in_progress_sub = None

                if not in_progress_sub:
                    if time_status_code == 'OPEN' and attempts_used < ex.max_attempts:
                        can_take = True
                        action_label = "ចូលប្រឡង"

                exam_data = {
                    'id': ex.id,
                    'title': ex.title,
                    'description': ex.description or '',
                    'subject_id': ex.subject_id,
                    'subject_name': ex.subject.name_kh if ex.subject else '',
                    'subject_code': ex.subject.code if ex.subject else '',
                    'exam_term_id': ex.exam_term_id,
                    'exam_term_name': ex.exam_term.name if ex.exam_term else '',
                    'teacher_name': ex.teacher.khmer_name if ex.teacher else (ex.created_by.display_name if ex.created_by else 'លោកគ្រូ-អ្នកគ្រូ'),
                    'duration_minutes': ex.duration_minutes,
                    'total_score': float(ex.total_score),
                    'pass_score': float(ex.pass_score),
                    'max_attempts': ex.max_attempts,
                    'attempts_used': attempts_used,
                    'questions_count': ex.questions.count(),
                    'requires_access_code': bool(ex.access_code and ex.access_code.strip()),
                    'start_time': ex.start_time.isoformat() if ex.start_time else None,
                    'end_time': ex.end_time.isoformat() if ex.end_time else None,
                    'status_code': time_status_code,
                    'status_label': time_status_label,
                    'badge_color': badge_color,
                    'can_take': can_take,
                    'action_label': action_label,
                    'in_progress_submission_id': in_progress_sub.id if in_progress_sub else None,
                    'latest_submission': {
                        'id': latest_sub.id,
                        'score_obtained': float(latest_sub.score_obtained),
                        'total_possible_score': float(latest_sub.total_possible_score),
                        'percentage': float(latest_sub.percentage),
                        'letter_grade': latest_sub.letter_grade or '-',
                        'is_passed': latest_sub.is_passed,
                        'submitted_at': latest_sub.submitted_at.isoformat() if latest_sub.submitted_at else None,
                        'formatted_time': latest_sub.formatted_time_spent,
                    } if latest_sub else None,
                }
                results.append(exam_data)

            return Response({
                'status': 'success',
                'student_name': student.khmer_name,
                'classroom_name': student.classroom.name if student.classroom else '',
                'exams': results
            })

        # Teacher / Admin View
        teacher = getattr(user, 'teacher_profile', None)
        if user.role == User.Role.TEACHER and teacher:
            exams_qs = OnlineExam.objects.filter(Q(teacher=teacher) | Q(created_by=user))
        else:
            exams_qs = OnlineExam.objects.all()

        exams_qs = (
            exams_qs.select_related('exam_term', 'subject', 'teacher')
            .prefetch_related('target_classrooms', 'questions', 'submissions')
            .order_by('-created_at')[:50]
        )

        results = []
        for ex in exams_qs:
            subs = ex.submissions.filter(status=OnlineExamSubmission.SubmissionStatus.SUBMITTED)
            sub_count = subs.count()
            avg_score = subs.aggregate(Avg('score_obtained'))['score_obtained__avg'] or 0.0

            results.append({
                'id': ex.id,
                'title': ex.title,
                'subject_name': ex.subject.name_kh if ex.subject else '',
                'exam_term_name': ex.exam_term.name if ex.exam_term else '',
                'teacher_name': ex.teacher.khmer_name if ex.teacher else 'Admin',
                'duration_minutes': ex.duration_minutes,
                'total_score': float(ex.total_score),
                'pass_score': float(ex.pass_score),
                'questions_count': ex.questions.count(),
                'submissions_count': sub_count,
                'average_score': round(float(avg_score), 2),
                'is_published': ex.is_published,
                'created_at': ex.created_at.isoformat(),
            })

        return Response({
            'status': 'success',
            'exams': results
        })


class MobileOnlineExamTakeView(APIView):
    """
    Initializes or resumes an exam session, returning questions and options.
    Securely omits 'is_correct' to prevent cheating.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, exam_id):
        user = request.user
        student, _ = resolve_student_and_children_for_user(user)
        if not student:
            student = getattr(user, 'student_profile', None)
        if not student:
            student = Student.objects.filter(user=user).first()

        if not student:
            return Response({
                'status': 'error',
                'message': 'គណនីនេះមិនមែនជាសិស្សទេ (Student profile required)!'
            }, status=status.HTTP_403_FORBIDDEN)

        exam = get_object_or_404(
            OnlineExam.objects.select_related('subject', 'exam_term', 'teacher'),
            id=exam_id
        )

        if not exam.is_published or exam.status == OnlineExam.ExamStatus.CLOSED:
            return Response({
                'status': 'error',
                'message': 'វិញ្ញាសានេះមិនទាន់ផ្សព្វផ្សាយ ឬត្រូវបានបិទបញ្ចប់ហើយ!'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validate PIN / Access Code if required
        if exam.access_code and exam.access_code.strip():
            client_pin = request.data.get('access_code', '').strip()
            if client_pin != exam.access_code.strip():
                return Response({
                    'status': 'error',
                    'message': 'លេខកូដសម្ងាត់ (PIN) មិនត្រឹមត្រូវទេ! សូមសួរលោកគ្រូ-អ្នកគ្រូ។'
                }, status=status.HTTP_403_FORBIDDEN)

        # Check existing in-progress session
        submission = OnlineExamSubmission.objects.filter(
            exam=exam,
            student=student,
            status=OnlineExamSubmission.SubmissionStatus.IN_PROGRESS
        ).order_by('-started_at').first()

        completed_count = OnlineExamSubmission.objects.filter(
            exam=exam,
            student=student,
            status=OnlineExamSubmission.SubmissionStatus.SUBMITTED
        ).count()

        if not submission:
            if completed_count >= exam.max_attempts:
                return Response({
                    'status': 'error',
                    'message': f'អ្នកបានប្រឡងគ្រប់ចំនួនកំណត់ហើយ ({completed_count}/{exam.max_attempts} ដង)!'
                }, status=status.HTTP_400_BAD_REQUEST)

            now = timezone.now()
            if exam.start_time and now < exam.start_time:
                return Response({
                    'status': 'error',
                    'message': f'វិញ្ញាសានេះនឹងចាប់ផ្តើមនៅ {exam.start_time.strftime("%d/%m/%Y %H:%M")}'
                }, status=status.HTTP_400_BAD_REQUEST)

            if exam.end_time and now > exam.end_time:
                return Response({
                    'status': 'error',
                    'message': 'ការប្រឡងនេះបានផុតកំណត់កាលបរិច្ឆេទហើយ!'
                }, status=status.HTTP_400_BAD_REQUEST)

            submission = OnlineExamSubmission.objects.create(
                exam=exam,
                student=student,
                classroom=student.classroom,
                attempt_number=completed_count + 1,
                status=OnlineExamSubmission.SubmissionStatus.IN_PROGRESS,
            )

        # Compute remaining seconds
        elapsed = (timezone.now() - submission.started_at).total_seconds()
        total_secs = exam.duration_minutes * 60
        remaining_seconds = max(0, int(total_secs - elapsed))

        if remaining_seconds <= 0:
            # Auto-expire session
            submission.status = OnlineExamSubmission.SubmissionStatus.EXPIRED
            submission.calculate_results(save=True)
            return Response({
                'status': 'error',
                'message': 'ម៉ោងប្រឡងសម្រាប់វិញ្ញាសានេះបានផុតហើយ!'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Fetch previously answered questions if resuming
        saved_answers = {
            ans.question_id: ans.selected_option_id
            for ans in submission.answers.all()
        }

        # Fetch questions and options
        questions_qs = exam.questions.prefetch_related('options').order_by('order', 'id')
        questions_list = []

        for q in questions_qs:
            options_qs = q.options.all().order_by('order', 'id')
            options_list = [
                {
                    'id': opt.id,
                    'option_text': opt.option_text,
                    'order': opt.order
                }
                for opt in options_qs
            ]

            img_url = None
            if q.image:
                try:
                    img_url = request.build_absolute_uri(q.image.url)
                except Exception:
                    img_url = q.image.url

            questions_list.append({
                'id': q.id,
                'question_text': q.question_text,
                'image_url': img_url,
                'points': float(q.points),
                'order': q.order,
                'options': options_list,
                'saved_option_id': saved_answers.get(q.id)
            })

        return Response({
            'status': 'success',
            'submission_id': submission.id,
            'exam_id': exam.id,
            'exam_title': exam.title,
            'subject_name': exam.subject.name_kh if exam.subject else '',
            'duration_minutes': exam.duration_minutes,
            'remaining_seconds': remaining_seconds,
            'total_score': float(exam.total_score),
            'questions_count': len(questions_list),
            'questions': questions_list
        })


class MobileOnlineExamSubmitView(APIView):
    """
    Submits student exam answers, calculates instant grade and returns results.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, exam_id):
        user = request.user
        student, _ = resolve_student_and_children_for_user(user)
        if not student:
            student = getattr(user, 'student_profile', None)
        if not student:
            student = Student.objects.filter(user=user).first()

        if not student:
            return Response({
                'status': 'error',
                'message': 'សិស្សមិនត្រូវបានរកឃើញទេ!'
            }, status=status.HTTP_403_FORBIDDEN)

        exam = get_object_or_404(OnlineExam, id=exam_id)
        submission_id = request.data.get('submission_id')

        submission = get_object_or_404(
            OnlineExamSubmission,
            id=submission_id,
            exam=exam,
            student=student
        )

        if submission.status == OnlineExamSubmission.SubmissionStatus.SUBMITTED:
            # Already submitted, return existing result
            return Response({
                'status': 'success',
                'message': 'វិញ្ញាសានេះបានប្រគល់រួចហើយ!',
                'submission_id': submission.id,
                'score_obtained': float(submission.score_obtained),
                'total_possible_score': float(submission.total_possible_score),
                'percentage': float(submission.percentage),
                'letter_grade': submission.letter_grade or '-',
                'mention_khmer': submission.mention_khmer,
                'is_passed': submission.is_passed,
                'time_spent_seconds': submission.time_spent_seconds,
                'formatted_time_spent': submission.formatted_time_spent,
                'show_result_immediately': exam.show_result_immediately,
                'show_correct_answers': exam.show_correct_answers,
            })

        # Save answers: payload has {'answers': {question_id: option_id, ...}}
        answers_dict = request.data.get('answers', {})
        time_spent = int(request.data.get('time_spent_seconds', 0))
        submission.time_spent_seconds = time_spent

        for q_id_str, opt_id_val in answers_dict.items():
            if not opt_id_val:
                continue
            try:
                q_id = int(q_id_str)
                opt_id = int(opt_id_val)
                q_obj = OnlineExamQuestion.objects.filter(id=q_id, exam=exam).first()
                opt_obj = OnlineExamOption.objects.filter(id=opt_id, question=q_obj).first()
                if q_obj and opt_obj:
                    OnlineExamAnswer.objects.update_or_create(
                        submission=submission,
                        question=q_obj,
                        defaults={
                            'selected_option': opt_obj,
                            'is_correct': opt_obj.is_correct,
                            'points_awarded': q_obj.points if opt_obj.is_correct else Decimal('0.00'),
                        }
                    )
            except (ValueError, TypeError):
                continue

        # Evaluate and calculate score
        submission.calculate_results(save=True)

        # Automatic sync to Grade matrix
        try:
            Grade.objects.update_or_create(
                student=student,
                exam_term=exam.exam_term,
                subject=exam.subject,
                defaults={
                    'classroom': submission.classroom or student.classroom,
                    'score': submission.score_obtained,
                    'max_score': submission.total_possible_score,
                    'remarks': f"តេស្តអនឡាញ (Mobile)៖ {exam.title}",
                }
            )
            submission.synced_to_grade = True
            submission.save()
        except Exception:
            # Non-blocking sync failure log
            pass

        return Response({
            'status': 'success',
            'message': 'ការប្រឡងត្រូវបានប្រគល់ដោយជោគជ័យ!',
            'submission_id': submission.id,
            'score_obtained': float(submission.score_obtained),
            'total_possible_score': float(submission.total_possible_score),
            'percentage': float(submission.percentage),
            'letter_grade': submission.letter_grade or '-',
            'mention_khmer': submission.mention_khmer,
            'is_passed': submission.is_passed,
            'time_spent_seconds': submission.time_spent_seconds,
            'formatted_time_spent': submission.formatted_time_spent,
            'show_result_immediately': exam.show_result_immediately,
            'show_correct_answers': exam.show_correct_answers,
        })


class MobileOnlineExamResultView(APIView):
    """
    Returns detailed submission result and question review.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, submission_id):
        user = request.user
        submission = get_object_or_404(
            OnlineExamSubmission.objects.select_related('exam', 'student', 'classroom', 'exam__subject', 'exam__exam_term'),
            id=submission_id
        )

        # Permissions: only owner student or teacher/admin
        if user.role == User.Role.STUDENT:
            student, _ = resolve_student_and_children_for_user(user)
            if not student:
                student = getattr(user, 'student_profile', None)
            if not student:
                student = Student.objects.filter(user=user).first()

            if not student or submission.student_id != student.id:
                return Response({
                    'status': 'error',
                    'message': 'លោកអ្នកគ្មានសិទ្ធិមើលលទ្ធផលនេះទេ!'
                }, status=status.HTTP_403_FORBIDDEN)

        exam = submission.exam
        answers_map = {ans.question_id: ans for ans in submission.answers.select_related('selected_option').all()}

        # Build detailed question reviews if allowed
        questions_review = []
        can_view_answers = exam.show_correct_answers or user.role in [User.Role.ADMIN, User.Role.TEACHER]

        if can_view_answers:
            questions = exam.questions.prefetch_related('options').order_by('order', 'id')
            for q in questions:
                ans = answers_map.get(q.id)
                selected_opt = ans.selected_option if ans else None
                is_correct = ans.is_correct if ans else False

                options_list = []
                for opt in q.options.all().order_by('order', 'id'):
                    options_list.append({
                        'id': opt.id,
                        'option_text': opt.option_text,
                        'is_correct': opt.is_correct,
                        'is_selected': bool(selected_opt and selected_opt.id == opt.id)
                    })

                img_url = None
                if q.image:
                    try:
                        img_url = request.build_absolute_uri(q.image.url)
                    except Exception:
                        img_url = q.image.url

                questions_review.append({
                    'question_id': q.id,
                    'question_text': q.question_text,
                    'image_url': img_url,
                    'points': float(q.points),
                    'points_awarded': float(ans.points_awarded) if ans else 0.0,
                    'is_correct': is_correct,
                    'has_answered': ans is not None and selected_opt is not None,
                    'explanation': q.explanation or '',
                    'options': options_list
                })

        return Response({
            'status': 'success',
            'submission': {
                'id': submission.id,
                'exam_id': exam.id,
                'exam_title': exam.title,
                'subject_name': exam.subject.name_kh if exam.subject else '',
                'exam_term_name': exam.exam_term.name if exam.exam_term else '',
                'student_name': submission.student.khmer_name,
                'classroom_name': submission.classroom.name if submission.classroom else '',
                'score_obtained': float(submission.score_obtained),
                'total_possible_score': float(submission.total_possible_score),
                'percentage': float(submission.percentage),
                'letter_grade': submission.letter_grade or '-',
                'mention_khmer': submission.mention_khmer,
                'is_passed': submission.is_passed,
                'status': submission.status,
                'submitted_at': submission.submitted_at.isoformat() if submission.submitted_at else None,
                'formatted_time_spent': submission.formatted_time_spent,
                'time_spent_seconds': submission.time_spent_seconds,
                'pass_score': float(exam.pass_score),
                'show_correct_answers': exam.show_correct_answers,
                'questions_review': questions_review
            }
        })
