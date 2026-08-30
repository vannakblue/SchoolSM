from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
import calendar
from datetime import datetime, date, time, timedelta, time as dtime
from apps.accounts.decorators import role_required
from apps.accounts.utils import send_telegram_notification
from .models import StudentAttendance, AttendanceSubmissionLog, AttendanceSetting
from apps.students.models import Student
from apps.academics.models import Classroom, AcademicYear, Timetable, Subject, AcademicCalendarRestriction
from apps.academics.utils import get_active_academic_year
from apps.teachers.models import Teacher, TeacherAttendance, TeacherLeaveRequest
from .telegram_utils import (
    send_teacher_leave_notification_telegram,
    send_hourly_period_absence_dispatch,
    send_classroom_attendance_telegram,
    send_missing_teachers_telegram,
    send_daily_summary_telegram,
)






DEFAULT_PERIOD_SCHEDULE = {
    1: {'start': (7, 0), 'end': (8, 0), 'session': StudentAttendance.Session.MORNING},
    2: {'start': (8, 0), 'end': (9, 0), 'session': StudentAttendance.Session.MORNING},
    3: {'start': (9, 0), 'end': (10, 0), 'session': StudentAttendance.Session.MORNING},
    4: {'start': (10, 0), 'end': (11, 0), 'session': StudentAttendance.Session.MORNING},
    5: {'start': (13, 0), 'end': (14, 0), 'session': StudentAttendance.Session.AFTERNOON},
    6: {'start': (14, 0), 'end': (15, 0), 'session': StudentAttendance.Session.AFTERNOON},
    7: {'start': (15, 0), 'end': (16, 0), 'session': StudentAttendance.Session.AFTERNOON},
    8: {'start': (16, 0), 'end': (17, 0), 'session': StudentAttendance.Session.AFTERNOON},
}


def get_current_period_info(t):
    """
    Returns (period_number, session_str) based on standard Cambodian school bell schedule.
    """
    h, m = t.hour, t.minute
    mins = h * 60 + m
    if mins < 8 * 60:
        return (1, StudentAttendance.Session.MORNING)
    elif mins < 9 * 60:
        return (2, StudentAttendance.Session.MORNING)
    elif mins < 10 * 60:
        return (3, StudentAttendance.Session.MORNING)
    elif mins < 11 * 60 + 30:
        return (4, StudentAttendance.Session.MORNING)
    elif mins < 14 * 60:
        return (5, StudentAttendance.Session.AFTERNOON)
    elif mins < 15 * 60:
        return (6, StudentAttendance.Session.AFTERNOON)
    elif mins < 16 * 60:
        return (7, StudentAttendance.Session.AFTERNOON)
    elif mins < 18 * 60:
        return (8, StudentAttendance.Session.AFTERNOON)
    else:
        return (1, StudentAttendance.Session.MORNING)


def evaluate_attendance_timing_window(teacher_profile, classroom, period_number, att_date, current_dt=None):
    """
    Evaluates whether attendance can be recorded/edited for (classroom, period_number, att_date).
    Rules:
    - 0. Maintenance mode check: If active -> completely locked with maintenance explanation.
    - 0b. Vacation / Public Holiday check: If active on att_date -> locked with calendar notice.
    - Configurable grace window (T_start - 30m to T_start + grace_minutes, default 30m): Multiple submissions allowed.
    - After grace cutoff up to class end (T_start + grace_minutes to T_end):
      * If already submitted at least once -> LOCKED / DISABLED.
      * If NOT submitted yet -> Grace period: 1-time submission only.
    - After class end (t > T_end): Completely LOCKED / DISABLED.
    """
    if current_dt is None:
        current_dt = datetime.now()

    current_date = current_dt.date()
    current_time = current_dt.time()

    # 1. System Maintenance Check
    att_settings = AttendanceSetting.get_settings()
    if att_settings.is_maintenance_mode:
        return {
            'can_submit': False,
            'status_code': 'LOCKED_MAINTENANCE',
            'status_label': 'ប្រព័ន្ធកំពុងបិទថែទាំ (System Maintenance)',
            'status_message': att_settings.maintenance_message or 'ប្រព័ន្ធស្រង់វត្តមានកំពុងបិទដំណើរការជាបណ្តោះអាសន្នដើម្បីថែទាំបច្ចេកទេស។',
            'badge_class': 'danger',
            'submission_log': None,
            'start_time_str': '--:--',
            'end_time_str': '--:--'
        }

    # 2. Calendar Restrictions (Vacations / Public Holidays) Check
    restriction = AcademicCalendarRestriction.objects.filter(
        is_active=True,
        block_attendance=True,
        start_date__lte=att_date,
        end_date__gte=att_date
    ).first()
    if restriction:
        type_label = restriction.get_restriction_type_display()
        date_range_str = f" (ចាប់ពី {restriction.start_date.strftime('%d/%m/%Y')} ដល់ {restriction.end_date.strftime('%d/%m/%Y')})" if restriction.start_date != restriction.end_date else ""
        return {
            'can_submit': False,
            'status_code': f'LOCKED_{restriction.restriction_type}',
            'status_label': f'{type_label}: {restriction.title}',
            'status_message': f'ស្ថិតក្នុងកាលវិភាគ {restriction.title}{date_range_str}។ មិនអនុញ្ញាតឱ្យចុះវត្តមានឡើយ។',
            'badge_class': 'warning',
            'submission_log': None,
            'start_time_str': '--:--',
            'end_time_str': '--:--'
        }

    if not period_number or period_number < 1 or period_number > 8:
        return {
            'can_submit': False,
            'status_code': 'LOCKED_NO_SCHEDULE',
            'status_label': 'ពុំមានម៉ោងបង្រៀន',
            'status_message': 'មិនមានព័ត៌មានម៉ោងបង្រៀនសម្រាប់ស្រង់វត្តមានឡើយ។',
            'badge_class': 'secondary',
            'submission_log': None,
            'start_time_str': '--:--',
            'end_time_str': '--:--'
        }

    # Fetch timetable slot if exists
    tt_slot = None
    if classroom:
        qs = Timetable.objects.filter(
            classroom=classroom,
            period_number=period_number,
            day_of_week=att_date.isoweekday()
        )
        if teacher_profile:
            qs = qs.filter(teacher=teacher_profile)
        tt_slot = qs.first()

    # Determine start and end time
    if tt_slot and tt_slot.start_time and tt_slot.end_time:
        start_h, start_m = tt_slot.start_time.hour, tt_slot.start_time.minute
        end_h, end_m = tt_slot.end_time.hour, tt_slot.end_time.minute
    else:
        sched = DEFAULT_PERIOD_SCHEDULE.get(period_number, DEFAULT_PERIOD_SCHEDULE[1])
        start_h, start_m = sched['start']
        end_h, end_m = sched['end']

    grace_mins = att_settings.get_grace_minutes_for_period(period_number)
    start_mins = start_h * 60 + start_m
    end_mins = end_h * 60 + end_m
    early_open_mins = start_mins - 30
    mid_cutoff_mins = start_mins + grace_mins

    now_mins = current_time.hour * 60 + current_time.minute

    start_time_str = f"{start_h:02d}:{start_m:02d}"
    end_time_str = f"{end_h:02d}:{end_m:02d}"

    session_val = StudentAttendance.Session.MORNING if period_number <= 4 else StudentAttendance.Session.AFTERNOON

    # Check previous submission logs
    submission_log = None
    if classroom:
        submission_log = AttendanceSubmissionLog.objects.filter(
            classroom=classroom,
            date=att_date,
            session=session_val,
            period_number=period_number
        ).first()

    has_submitted = (submission_log is not None and submission_log.submission_count > 0)

    # 1. Date Check: Only today is active for real-time attendance
    if att_date < current_date:
        return {
            'can_submit': False,
            'status_code': 'LOCKED_EXPIRED',
            'status_label': 'ផុតកាលបរិច្ឆេទ (Expired Date)',
            'status_message': f'កាលបរិច្ឆេទ {att_date.strftime("%d/%m/%Y")} បានកន្លងផុតហើយ។ មានតែ Admin ប៉ុណ្ណោះដែលអាចកែសម្រួលបាន។',
            'badge_class': 'secondary',
            'submission_log': submission_log,
            'start_time_str': start_time_str,
            'end_time_str': end_time_str,
        }
    elif att_date > current_date:
        return {
            'can_submit': False,
            'status_code': 'LOCKED_TOO_EARLY',
            'status_label': 'មិនទាន់ដល់ថ្ងៃ (Future Date)',
            'status_message': f'មិនអាចស្រង់វត្តមានទុកមុនសម្រាប់ថ្ងៃទី {att_date.strftime("%d/%m/%Y")} ឡើយ។',
            'badge_class': 'secondary',
            'submission_log': submission_log,
            'start_time_str': start_time_str,
            'end_time_str': end_time_str,
        }

    # 2. Time Window Check on Current Date
    # Case A: Too early (More than 30 mins before class start)
    if now_mins < early_open_mins:
        return {
            'can_submit': False,
            'status_code': 'LOCKED_TOO_EARLY',
            'status_label': 'មិនទាន់ដល់ម៉ោង (Too Early)',
            'status_message': f'ម៉ោងបង្រៀនចាប់ផ្តើមនៅម៉ោង {start_time_str}។ អាចចាប់ផ្តើមស្រង់វត្តមានបានចាប់ពីម៉ោង {early_open_mins//60:02d}:{early_open_mins%60:02d} (មុន ៣០នាទី)។',
            'badge_class': 'secondary',
            'submission_log': submission_log,
            'start_time_str': start_time_str,
            'end_time_str': end_time_str,
        }

    # Case B: Within 30 minutes before class up to grace_mins into class
    # (T_start - 30m <= t <= T_start + grace_mins) -> Multi-submissions allowed!
    elif early_open_mins <= now_mins <= mid_cutoff_mins:
        sub_text = f" (បានបញ្ជូន {submission_log.submission_count} ដង)" if has_submitted else ""
        return {
            'can_submit': True,
            'status_code': 'OPEN_MULTIPLE',
            'status_label': f'កំពុងបើកស្រង់វត្តមាន ({grace_mins}នាទីដំបូង)',
            'status_message': f'ស្ថិតក្នុងម៉ោងបង្រៀន ({start_time_str} - {end_time_str})៖ លោកគ្រូ-អ្នកគ្រូអាចស្រង់ និងកែប្រែវត្តមានបានច្រើនដង{sub_text}។',
            'badge_class': 'success',
            'submission_log': submission_log,
            'start_time_str': start_time_str,
            'end_time_str': end_time_str,
        }

    # Case C: Between grace_mins into class and class end (T_start + grace_mins < t <= T_end)
    elif mid_cutoff_mins < now_mins <= end_mins:
        if has_submitted:
            # Case C1: Already submitted during first grace_mins -> Locked!
            return {
                'can_submit': False,
                'status_code': 'LOCKED_ALREADY_SUBMITTED',
                'status_label': 'ផុតកំណត់កែប្រែ (បានបញ្ជូនរួច)',
                'status_message': f'លោកគ្រូ-អ្នកគ្រូបានបញ្ជូនវត្តមានរួចរាល់ហើយកាលពីម៉ោង {submission_log.updated_at.strftime("%H:%M")}។ ហួស {grace_mins} នាទីដំបូង ប្រព័ន្ធចាក់សោមិនឱ្យកែប្រែទៀតឡើយ។',
                'badge_class': 'danger',
                'submission_log': submission_log,
                'start_time_str': start_time_str,
                'end_time_str': end_time_str,
            }
        else:
            # Case C2: Has NOT submitted yet -> Grace period: 1-time submission only!
            return {
                'can_submit': True,
                'status_code': 'OPEN_ONCE',
                'status_label': 'អនុញ្ញាតបញ្ជូនយឺត (បានតែ ១ ដងគត់)',
                'status_message': f'លោកគ្រូ-អ្នកគ្រូមិនទាន់បានបញ្ចូលវត្តមានសោះ។ ប្រព័ន្ធអនុញ្ញាតឱ្យបញ្ជូនយឺតបានតែ ១ ដងគត់មុនម៉ោង {end_time_str} បន្ទាប់មកនឹងត្រូវចាក់សោភ្លាមៗ។',
                'badge_class': 'warning',
                'submission_log': submission_log,
                'start_time_str': start_time_str,
                'end_time_str': end_time_str,
            }

    # Case D: After class end (t > T_end)
    else:
        sub_info = f"កាលពីម៉ោង {submission_log.updated_at.strftime('%H:%M')}" if has_submitted else "ពុំបានបញ្ជូនវត្តមាន"
        return {
            'can_submit': False,
            'status_code': 'LOCKED_EXPIRED',
            'status_label': 'ផុតម៉ោងបង្រៀន (Period Ended)',
            'status_message': f'ម៉ោងបង្រៀន ({start_time_str} - {end_time_str}) បានបញ្ចប់ហើយ ({sub_info})។ មិនអាចស្រង់វត្តមានបានទៀតឡើយ។',
            'badge_class': 'danger',
            'submission_log': submission_log,
            'start_time_str': start_time_str,
            'end_time_str': end_time_str,
        }


@login_required
@role_required(['ADMIN', 'TEACHER'])
def student_attendance_grid(request):
    """
    Absence-Focused Smart Attendance Recording View with Strict Timing Constraints
    """
    active_year = get_active_academic_year(request)
    classrooms = Classroom.objects.filter(academic_year=active_year).order_by('grade_level', 'code') if active_year else Classroom.objects.all().order_by('grade_level', 'code')
    user = request.user
    teacher_profile = getattr(user, 'teacher_profile', None)

    now_dt = datetime.now()
    today_date = now_dt.date()
    current_dow = today_date.isoweekday() # 1=Mon ... 6=Sat, 7=Sun
    auto_period_num, auto_session = get_current_period_info(now_dt.time())

    # 1. Determine Selected Date & Timetable Slots for Teacher
    req_class_id = request.GET.get('classroom')
    req_date_str = request.GET.get('date', today_date.strftime('%Y-%m-%d'))
    req_session = request.GET.get('session')
    req_period = request.GET.get('period')

    try:
        selected_date = datetime.strptime(req_date_str, '%Y-%m-%d').date()
    except ValueError:
        selected_date = today_date

    today_slots = []
    if teacher_profile:
        today_slots = Timetable.objects.filter(
            teacher=teacher_profile,
            day_of_week=selected_date.isoweekday(),
            classroom__academic_year=active_year
        ).select_related('classroom', 'subject').order_by('period_number')

    selected_class = None
    selected_period = None
    selected_subject = None
    selected_session = req_session or auto_session
    is_timetable_locked = False
    detected_slot_info = None

    teacher_schedule_alert = None
    if teacher_profile and user.role == 'TEACHER':
        khmer_days = {
            1: 'ច័ន្ទ',
            2: 'អង្គារ',
            3: 'ពុធ',
            4: 'ព្រហស្បតិ៍',
            5: 'សុក្រ',
            6: 'សៅរ៍',
            7: 'អាទិត្យ',
        }
        day_name = khmer_days.get(selected_date.isoweekday(), '')
        date_slots = today_slots

        if not date_slots.exists():
            # Scenario 1: No classes for the entire day (1 ថ្ងៃ)
            teacher_schedule_alert = {
                'show_modal': True,
                'alert_type': 'NO_CLASS_TODAY',
                'badge_text': 'គ្មានកាលវិភាគពេញមួយថ្ងៃ',
                'title': 'លោកគ្រូ-អ្នកគ្រូពុំមានម៉ោងបង្រៀនក្នុងថ្ងៃនេះទេ',
                'message': f'លោកគ្រូ-អ្នកគ្រូមិនមានម៉ោងបង្រៀននៅក្នុងថ្ងៃ{day_name} ទី {selected_date.strftime("%d/%m/%Y")} ឡើយ។ សូមពិនិត្យមើលកាលវិភាគបង្រៀនរួម ឬកាលវិភាគប្រចាំសប្តាហ៍។',
                'icon': 'fa-calendar-xmark',
                'icon_color': 'text-danger',
                'bg_color': 'bg-danger-subtle',
                'has_classes_today': False,
                'other_slots': [],
            }
        else:
            # Has classes today. Check session and period
            target_period = int(req_period) if (req_period and req_period.isdigit()) else auto_period_num
            target_session = req_session if req_session else (
                StudentAttendance.Session.AFTERNOON if target_period > 4 else StudentAttendance.Session.MORNING
            )

            session_slots = [
                s for s in date_slots
                if (s.period_number <= 4 and target_session == StudentAttendance.Session.MORNING) or
                   (s.period_number > 4 and target_session == StudentAttendance.Session.AFTERNOON)
            ]
            current_period_slot = next((s for s in date_slots if s.period_number == target_period), None)
            is_explicit_valid_slot = (
                req_period and req_class_id and
                date_slots.filter(period_number=int(req_period), classroom_id=int(req_class_id)).exists()
            )

            if not is_explicit_valid_slot:
                if len(session_slots) == 0:
                    # Scenario 2: No classes in this session (1 ពេល - ពេលព្រឹក ឬ ពេលរសៀល)
                    session_kh = 'ពេលព្រឹក (Morning)' if target_session == StudentAttendance.Session.MORNING else 'ពេលរសៀល (Afternoon)'
                    other_session_kh = 'ពេលរសៀល (Afternoon)' if target_session == StudentAttendance.Session.MORNING else 'ពេលព្រឹក (Morning)'
                    other_periods_text = ', '.join([f"ម៉ោងទី {s.period_number} ({s.classroom.code} - {s.subject.name_kh})" for s in date_slots])
                    
                    teacher_schedule_alert = {
                        'show_modal': True,
                        'alert_type': 'NO_CLASS_THIS_SESSION',
                        'badge_text': f'គ្មានកាលវិភាគក្នុង{session_kh}',
                        'title': f'ពុំមានម៉ោងបង្រៀនក្នុង{session_kh}នេះទេ',
                        'message': f'នៅ{session_kh}នេះ លោកគ្រូ-អ្នកគ្រូពុំមានម៉ោងបង្រៀនឡើយ។ លោកគ្រូ-អ្នកគ្រូមានម៉ោងបង្រៀននៅ{other_session_kh}៖ {other_periods_text}។',
                        'icon': 'fa-cloud-sun',
                        'icon_color': 'text-warning',
                        'bg_color': 'bg-warning-subtle',
                        'has_classes_today': True,
                        'other_slots': date_slots,
                    }
                elif current_period_slot is None:
                    # Scenario 3: Has classes in this session, but NOT at this specific period/hour (1 ម៉ោង)
                    next_slot = next((s for s in date_slots if s.period_number > target_period), None)
                    next_slot_text = (
                        f"ម៉ោងបង្រៀនបន្ទាប់របស់លោកគ្រូ-អ្នកគ្រូគឺ <strong>ម៉ោងទី {next_slot.period_number}</strong> ({next_slot.classroom.code} - {next_slot.subject.name_kh})។"
                        if next_slot else "លោកគ្រូ-អ្នកគ្រូបានបញ្ចប់រាល់ម៉ោងបង្រៀនសម្រាប់វេននេះហើយ។"
                    )
                    teacher_schedule_alert = {
                        'show_modal': True,
                        'alert_type': 'NO_CLASS_THIS_PERIOD',
                        'badge_text': f'គ្មានកាលវិភាគនៅម៉ោងទី {target_period}',
                        'title': f'ពុំមានម៉ោងបង្រៀននៅម៉ោងទី {target_period} នេះទេ',
                        'message': f'នៅម៉ោងទី {target_period} នេះ លោកគ្រូ-អ្នកគ្រូពុំមានម៉ោងបង្រៀនឡើយ។ {next_slot_text}',
                        'icon': 'fa-hourglass-start',
                        'icon_color': 'text-info',
                        'bg_color': 'bg-info-subtle',
                        'has_classes_today': True,
                        'other_slots': date_slots,
                        'current_period_num': target_period,
                    }

    if teacher_profile and today_slots.exists():
        matching_slot = None
        if req_period and req_class_id:
            matching_slot = today_slots.filter(period_number=int(req_period), classroom_id=int(req_class_id)).first()
        elif selected_date == today_date:
            matching_slot = today_slots.filter(period_number=auto_period_num).first()

        if matching_slot:
            selected_class = matching_slot.classroom
            selected_period = matching_slot.period_number
            selected_subject = matching_slot.subject
            selected_session = StudentAttendance.Session.MORNING if matching_slot.period_number <= 4 else StudentAttendance.Session.AFTERNOON
            is_timetable_locked = True
            teacher_schedule_alert = None
            detected_slot_info = {
                'classroom': selected_class,
                'period': selected_period,
                'subject': selected_subject,
                'session_name': 'ពេលព្រឹក (Morning)' if matching_slot.period_number <= 4 else 'ពេលរសៀល (Afternoon)',
            }



    # Fallback for Admin or Teacher without timetable match
    if not selected_class:
        if req_class_id:
            selected_class = classrooms.filter(id=req_class_id).first()
        elif teacher_profile:
            teacher_class = Classroom.objects.filter(homeroom_teacher=teacher_profile, academic_year=active_year).first()
            selected_class = teacher_class or classrooms.first()
        else:
            selected_class = classrooms.first()

        if req_period and req_period.isdigit():
            selected_period = int(req_period)
        else:
            selected_period = auto_period_num

        if not selected_session:
            selected_session = StudentAttendance.Session.MORNING if selected_period <= 4 else StudentAttendance.Session.AFTERNOON

    # 3. Evaluate Timing Window
    if user.role == 'ADMIN':
        timing_eval = {
            'can_submit': True,
            'status_code': 'ADMIN_OVERRIDE',
            'status_label': 'សិទ្ធិ Admin (ពេញលេញ)',
            'status_message': 'លោកអ្នកមានសិទ្ធិជា Admin អាចស្រង់វត្តមាន ឬកែប្រែបានគ្រប់ពេលវេលា។',
            'badge_class': 'primary',
            'submission_log': AttendanceSubmissionLog.objects.filter(classroom=selected_class, date=selected_date, session=selected_session, period_number=selected_period).first() if selected_class else None,
            'start_time_str': '--:--',
            'end_time_str': '--:--'
        }
        is_form_disabled = False
    else:
        timing_eval = evaluate_attendance_timing_window(teacher_profile, selected_class, selected_period, selected_date, current_dt=now_dt)
        is_form_disabled = not timing_eval['can_submit']

    # 4. Handle POST: Absence-First Saving & Enforcement
    if request.method == 'POST' and selected_class:
        if user.role != 'ADMIN' and not timing_eval['can_submit']:
            messages.error(request, f"❌ បរាជ័យក្នុងការរក្សាទុក៖ {timing_eval['status_message']}")
            redirect_url = f"/attendance/?classroom={selected_class.id}&date={selected_date.strftime('%Y-%m-%d')}&session={selected_session}"
            if selected_period:
                redirect_url += f"&period={selected_period}"
            return redirect(redirect_url)

        notify_parents = request.POST.get('notify_parents') == '1'
        post_period = request.POST.get('period')
        post_subject_id = request.POST.get('subject')
        
        period_num_save = int(post_period) if post_period and post_period.isdigit() else selected_period
        subject_save = Subject.objects.filter(id=post_subject_id).first() if post_subject_id else selected_subject

        saved_absent_count = 0
        unexcused_count = 0

        students = Student.objects.filter(classroom=selected_class, status='ACTIVE')
        for student in students:
            is_ticked_absent = request.POST.get(f'is_absent_{student.id}') == '1'

            if is_ticked_absent:
                status_val = request.POST.get(f'status_{student.id}', StudentAttendance.Status.ABSENT)
                notes_val = request.POST.get(f'notes_{student.id}', '').strip()

                StudentAttendance.objects.update_or_create(
                    student=student,
                    classroom=selected_class,
                    date=selected_date,
                    session=selected_session,
                    period_number=period_num_save,
                    defaults={
                        'status': status_val,
                        'subject': subject_save,
                        'notes': notes_val,
                        'recorded_by': request.user
                    }
                )
                saved_absent_count += 1

                if status_val == StudentAttendance.Status.ABSENT:
                    unexcused_count += 1
                    if notify_parents:
                        msg = (
                            f"សួស្តីលោក/លោកស្រីអាណាព្យាបាលសិស្ស {student.khmer_name}!\n"
                            f"សាលាជម្រាបជូនថា នៅថ្ងៃទី {selected_date.strftime('%d/%m/%Y')} "
                            f"សិស្សពុំបានមកចូលរៀននៅ {selected_class.name} ឡើយ (អវត្តមានឥតច្បាប់)។ "
                            f"សូមទាក់ទងមកកាន់សាលាដើម្បីបញ្ជាក់ព័ត៌មានបន្ថែម។"
                        )
                        send_telegram_notification(
                            title=f"⚠️ សេចក្តីជូនដំណឹងអវត្តមានសិស្ស: {student.khmer_name}",
                            message=msg,
                            recipient_name=student.father_name or student.mother_name or student.khmer_name,
                            recipient_phone=student.father_phone or student.phone,
                            recipient_type="Parent",
                            custom_chat_id=student.telegram_chat_id
                        )
            else:
                # If unticked, remove any existing absence record for this student/period so ONLY absent students exist in DB!
                StudentAttendance.objects.filter(
                    student=student,
                    classroom=selected_class,
                    date=selected_date,
                    session=selected_session,
                    period_number=period_num_save
                ).delete()

        # Update Submission Log
        log_obj, created = AttendanceSubmissionLog.objects.get_or_create(
            classroom=selected_class,
            date=selected_date,
            session=selected_session,
            period_number=period_num_save,
            defaults={
                'recorded_by': request.user,
                'submission_count': 1
            }
        )
        if not created:
            log_obj.submission_count += 1
            log_obj.recorded_by = request.user
            log_obj.save()

        # Trigger Automated Hourly Period Absence Dispatch (Guardians, Homeroom, Management)
        att_settings = AttendanceSetting.get_settings()
        if att_settings.hourly_dispatch_enabled:
            send_hourly_period_absence_dispatch(
                target_date=selected_date,
                period_number=period_num_save,
                session=selected_session,
                sender_user=request.user
            )

        messages.success(request, f"✅ បានរក្សាទុកការស្រង់អវត្តមានសិស្សថ្នាក់ {selected_class.name} ជោគជ័យ! (សិស្សអវត្តមាន/សុំច្បាប់/យឺត សរុប៖ {saved_absent_count} នាក់)")

        if notify_parents and unexcused_count > 0:
            messages.info(request, f"🔔 បានផ្ញើសារជូនដំណឹងអវត្តមានទៅកាន់អាណាព្យាបាលសិស្ស {unexcused_count} នាក់រួចរាល់។")

        redirect_url = f"/attendance/?classroom={selected_class.id}&date={selected_date.strftime('%Y-%m-%d')}&session={selected_session}"
        if selected_period:
            redirect_url += f"&period={selected_period}"
        return redirect(redirect_url)

    # 5. Load Students Data with Absence Flags
    students_data = []
    if selected_class:
        students = Student.objects.filter(classroom=selected_class, status='ACTIVE').order_by('student_id')
        records_qs = StudentAttendance.objects.filter(
            classroom=selected_class,
            date=selected_date,
            session=selected_session
        )
        if selected_period:
            records_qs = records_qs.filter(period_number=selected_period)
        existing_records = {att.student_id: att for att in records_qs}


        for student in students:
            att = existing_records.get(student.id)
            is_absent = (att.status in [StudentAttendance.Status.ABSENT, StudentAttendance.Status.PERMISSION, StudentAttendance.Status.LATE]) if att else False
            students_data.append({
                'student': student,
                'is_absent': is_absent,
                'status': att.status if (att and is_absent) else StudentAttendance.Status.ABSENT,
                'notes': att.notes if att else '',
            })

    return render(request, 'attendance/attendance_grid.html', {
        'classrooms': classrooms,
        'selected_class': selected_class,
        'selected_class_id': str(selected_class.id) if selected_class else '',
        'selected_date': selected_date.strftime('%Y-%m-%d'),
        'selected_session': selected_session,
        'selected_period': selected_period,
        'selected_subject': selected_subject,
        'is_timetable_locked': is_timetable_locked,
        'detected_slot_info': detected_slot_info,
        'today_slots': today_slots,
        'sessions': StudentAttendance.Session.choices,
        'statuses': StudentAttendance.Status.choices,
        'students_data': students_data,
        'active_year': active_year,
        'total_students_count': len(students_data),
        'absent_students_count': sum(1 for s in students_data if s['is_absent']),
        'timing_eval': timing_eval,
        'is_form_disabled': is_form_disabled,
        'teacher_schedule_alert': teacher_schedule_alert,
    })





@login_required
def attendance_report(request):
    """
    Flexible Attendance aggregation report (Today, Week, Month, Custom).
    Deduplication Rule:
    Absences are counted at most 1 time per session (Morning / Afternoon).
    Even if a student was absent across 4 morning periods, it counts as exactly 1 morning absence.
    """
    active_year = get_active_academic_year(request)
    classrooms = Classroom.objects.filter(academic_year=active_year).order_by('grade_level', 'code') if active_year else Classroom.objects.all().order_by('grade_level', 'code')
    selected_class_id = request.GET.get('classroom', str(classrooms.first().id if classrooms.first() else ''))
    
    filter_type = request.GET.get('filter_type', 'month')
    now_dt = datetime.now()
    today = now_dt.date()

    if filter_type == 'today':
        start_date = today
        end_date = today
        filter_label = f"ថ្ងៃនេះ ({today.strftime('%d/%m/%Y')})"
        week_date_str = today.strftime('%Y-%m-%d')
        month_str = today.strftime('%Y-%m')
    elif filter_type == 'week':
        week_date_str = request.GET.get('week_date', today.strftime('%Y-%m-%d'))
        try:
            ref_d = datetime.strptime(week_date_str, '%Y-%m-%d').date()
        except ValueError:
            ref_d = today
        # Cambodian school week: Monday to Saturday
        start_date = ref_d - timedelta(days=ref_d.weekday())
        end_date = start_date + timedelta(days=5)
        filter_label = f"សប្តាហ៍ ({start_date.strftime('%d/%m/%Y')} ដល់ {end_date.strftime('%d/%m/%Y')})"
        month_str = ref_d.strftime('%Y-%m')
    elif filter_type == 'custom':
        start_str = request.GET.get('start_date', today.strftime('%Y-%m-%d'))
        end_str = request.GET.get('end_date', today.strftime('%Y-%m-%d'))
        try:
            start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
        except ValueError:
            start_date = today
            end_date = today
        filter_label = f"ចន្លោះថ្ងៃ ({start_date.strftime('%d/%m/%Y')} ដល់ {end_date.strftime('%d/%m/%Y')})"
        week_date_str = today.strftime('%Y-%m-%d')
        month_str = today.strftime('%Y-%m')
    else: # Default: 'month'
        filter_type = 'month'
        month_str = request.GET.get('month', today.strftime('%Y-%m'))
        try:
            y, m = map(int, month_str.split('-'))
        except ValueError:
            y, m = today.year, today.month
            month_str = today.strftime('%Y-%m')
        start_date = date(y, m, 1)
        _, last_day = calendar.monthrange(y, m)
        end_date = date(y, m, last_day)
        filter_label = f"ប្រចាំខែ {month_str}"
        week_date_str = today.strftime('%Y-%m-%d')

    selected_class = classrooms.filter(id=selected_class_id).first() if selected_class_id else None
    report_data = []

    summary_stats = {
        'total_students': 0,
        'total_sessions_held': 0,
        'avg_attendance_rate': 100.0,
        'total_absent_sessions': 0,
        'total_permission_sessions': 0,
        'total_late_sessions': 0,
    }

    if selected_class:
        students = Student.objects.filter(classroom=selected_class, status='ACTIVE').order_by('student_id')
        summary_stats['total_students'] = students.count()

        # 1. Total distinct sessions held for this class in date range
        logged_sessions = set(
            AttendanceSubmissionLog.objects.filter(
                classroom=selected_class,
                date__range=(start_date, end_date)
            ).values_list('date', 'session')
        )
        att_sessions = set(
            StudentAttendance.objects.filter(
                classroom=selected_class,
                date__range=(start_date, end_date)
            ).values_list('date', 'session')
        )
        all_class_sessions = logged_sessions.union(att_sessions)
        total_sessions_held = len(all_class_sessions)
        summary_stats['total_sessions_held'] = total_sessions_held

        # 2. Fetch all student attendance records in this range
        raw_atts = StudentAttendance.objects.filter(
            classroom=selected_class,
            date__range=(start_date, end_date)
        ).values('student_id', 'date', 'session', 'status')

        # Map student_id -> (date, session) -> status (ABSENT > PERMISSION > LATE)
        student_session_map = {}
        for a in raw_atts:
            s_id = a['student_id']
            key = (a['date'], a['session'])
            st = a['status']
            if s_id not in student_session_map:
                student_session_map[s_id] = {}

            existing_st = student_session_map[s_id].get(key)
            if not existing_st:
                student_session_map[s_id][key] = st
            else:
                # Priority: ABSENT takes precedence over PERMISSION/LATE for the session
                if st == StudentAttendance.Status.ABSENT:
                    student_session_map[s_id][key] = StudentAttendance.Status.ABSENT
                elif st == StudentAttendance.Status.PERMISSION and existing_st != StudentAttendance.Status.ABSENT:
                    student_session_map[s_id][key] = StudentAttendance.Status.PERMISSION

        # 3. Calculate per-student metrics
        total_rate_accum = 0.0
        for student in students:
            s_sessions = student_session_map.get(student.id, {})
            absent_cnt = sum(1 for st in s_sessions.values() if st == StudentAttendance.Status.ABSENT)
            perm_cnt = sum(1 for st in s_sessions.values() if st == StudentAttendance.Status.PERMISSION)
            late_cnt = sum(1 for st in s_sessions.values() if st == StudentAttendance.Status.LATE)

            # If sessions were recorded, present is total held minus absent and permission
            if total_sessions_held > 0:
                present_cnt = max(0, total_sessions_held - absent_cnt - perm_cnt)
                rate = round((present_cnt / total_sessions_held) * 100, 1)
            else:
                present_cnt = 0
                rate = 100.0

            total_rate_accum += rate
            summary_stats['total_absent_sessions'] += absent_cnt
            summary_stats['total_permission_sessions'] += perm_cnt
            summary_stats['total_late_sessions'] += late_cnt

            report_data.append({
                'student': student,
                'present': present_cnt,
                'absent': absent_cnt,
                'permission': perm_cnt,
                'late': late_cnt,
                'total': total_sessions_held,
                'rate': rate,
            })

        if summary_stats['total_students'] > 0:
            summary_stats['avg_attendance_rate'] = round(total_rate_accum / summary_stats['total_students'], 1)

    return render(request, 'attendance/attendance_report.html', {
        'classrooms': classrooms,
        'selected_class_id': selected_class_id,
        'selected_class': selected_class,
        'filter_type': filter_type,
        'filter_label': filter_label,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'week_date_str': week_date_str,
        'month_str': month_str,
        'report_data': report_data,
        'summary_stats': summary_stats,
        'active_year': active_year,
    })



@login_required
@role_required(['ADMIN', 'TEACHER'])
def at_risk_attendance_view(request):
    """
    At-Risk Attendance & Chronic Absentee Warning Tracker
    Identifies students with high unexcused absences (>= 3 days) and allows urgent parent contact.
    Strictly isolated per Academic Year!
    """
    active_year = get_active_academic_year(request)
    min_absences = int(request.GET.get('threshold', 2))
    class_id = request.GET.get('classroom', '')

    students = Student.objects.filter(status='ACTIVE').select_related('classroom')
    if active_year:
        students = students.filter(Q(academic_year=active_year) | Q(classroom__academic_year=active_year))
    if class_id:
        students = students.filter(classroom_id=class_id)

    at_risk_list = []
    for s in students:
        absent_cnt = StudentAttendance.objects.filter(
            student=s,
            status=StudentAttendance.Status.ABSENT
        ).count()

        perm_cnt = StudentAttendance.objects.filter(
            student=s,
            status=StudentAttendance.Status.PERMISSION
        ).count()

        total_cnt = StudentAttendance.objects.filter(student=s).count()

        if absent_cnt >= min_absences:
            rate = round(((total_cnt - absent_cnt) / total_cnt) * 100, 1) if total_cnt > 0 else 100.0
            risk_level = 'HIGH' if absent_cnt >= 4 else 'MEDIUM'
            at_risk_list.append({
                'student': s,
                'absent_count': absent_cnt,
                'perm_count': perm_cnt,
                'total_days': total_cnt,
                'attendance_rate': rate,
                'risk_level': risk_level,
            })

    # Sort descending by absent count
    at_risk_list.sort(key=lambda x: x['absent_count'], reverse=True)

    if request.method == 'POST' and 'send_warning' in request.POST:
        student_id = request.POST.get('student_id')
        stu = get_object_or_404(Student, pk=student_id)
        absent_days = request.POST.get('absent_days', '៣')
        class_name = stu.classroom.name if stu.classroom else '-'
        
        msg = (
            f"🚨 *លិខិតអញ្ជើញ & សេចក្តីជូនដំណឹងបន្ទាន់អំពីអវត្តមានសិស្ស*\n\n"
            f"សូមគោរពជម្រាបជូនលោក/លោកស្រីអាណាព្យាបាលសិស្ស *{stu.khmer_name}* (ថ្នាក់៖ {class_name})!\n\n"
            f"សាលាជម្រាបជូនថាសិស្សបានអវត្តមានឥតច្បាប់ចំនួន *{absent_days} ថ្ងៃ* ដែលប្រឈមនឹងការធ្លាក់ការសិក្សា ឬលុបឈ្មោះ។ "
            f"សូមលោក/លោកស្រីមេត្តាអញ្ជើញមកជួបគណៈគ្រប់គ្រងសាលា និងគ្រូបន្ទុកថ្នាក់ជាបន្ទាន់។ សូមអរគុណ!"
        )
        send_telegram_notification(
            title=f"🚨 លិខិតក្រើនរំលឹកអវត្តមានសិស្ស: {stu.khmer_name}",
            message=msg,
            recipient_name=stu.father_name or stu.mother_name or stu.khmer_name,
            recipient_phone=stu.father_phone or stu.phone,
            custom_chat_id=stu.telegram_chat_id
        )
        messages.success(request, f"🔔 បានផ្ញើសារក្រើនរំលឹកបន្ទាន់ទៅកាន់អាណាព្យាបាលសិស្ស {stu.khmer_name} ជោគជ័យ!")
        return redirect('at_risk_attendance')


    classrooms = Classroom.objects.filter(academic_year=active_year).order_by('grade_level', 'code') if active_year else Classroom.objects.all().order_by('grade_level', 'code')

    return render(request, 'attendance/at_risk_attendance.html', {
        'at_risk_list': at_risk_list,
        'classrooms': classrooms,
        'selected_class': class_id,
        'threshold': min_absences,
        'active_year': active_year,
    })


@login_required
@role_required(allowed_roles=['ADMIN'])
def attendance_admin_hub(request):
    """
    Comprehensive Control Center for Admin:
    1. Attendance rules & deadline window configuration
    2. Telegram automation & Classroom Chat IDs table
    3. Vacation & Public Holiday restrictions calendar
    4. System maintenance mode toggle & custom notice
    5. Teacher leave requests review & approval
    """
    from django.http import JsonResponse
    from apps.teachers.models import Teacher, TeacherLeaveRequest
    from apps.accounts.models import TelegramConfig
    from .telegram_utils import (
        send_classroom_attendance_telegram,
        send_missing_teachers_telegram,
        send_daily_summary_telegram,
        send_teacher_leave_notification_telegram,
    )

    active_year = get_active_academic_year(request)
    att_settings = AttendanceSetting.get_settings()
    telegram_config = TelegramConfig.objects.first()

    if request.method == 'POST':
        action = request.POST.get('action')

        # 1. Save Attendance & Telegram Rules
        if action == 'save_rules':
            grace_mins = request.POST.get('submission_grace_minutes', '30')
            mgmt_chat_id = request.POST.get('management_chat_id', '').strip()
            custom_groups = request.POST.get('custom_dispatch_groups', '').strip()
            auto_dispatch = request.POST.get('auto_daily_dispatch_enabled') == 'on'
            auto_students = request.POST.get('auto_send_student_summary') == 'on'
            auto_teachers = request.POST.get('auto_send_teacher_summary') == 'on'
            hourly_enabled = request.POST.get('hourly_dispatch_enabled') == 'on'
            dispatch_guardians = request.POST.get('dispatch_to_guardians') == 'on'
            dispatch_homeroom = request.POST.get('dispatch_to_homeroom') == 'on'
            dispatch_mgmt = request.POST.get('dispatch_to_management') == 'on'

            # Parse custom weekly schedule
            sched = {}
            for day_idx in range(1, 8):
                day_time = request.POST.get(f'schedule_day_{day_idx}', '').strip()
                sched[str(day_idx)] = day_time if day_time else None

            # Parse per-period grace minutes & dispatch deadline times for all 8 periods
            fallback_grace = int(grace_mins) if grace_mins.isdigit() else 30
            period_grace = {}
            period_dispatch_times = {}
            default_times = {"1": "07:35", "2": "08:30", "3": "09:25", "4": "10:20", "5": "13:35", "6": "14:30", "7": "15:25", "8": "16:20"}

            for p in range(1, 9):
                p_val = request.POST.get(f'period_grace_{p}', '').strip()
                period_grace[str(p)] = int(p_val) if p_val.isdigit() else fallback_grace

                p_time = request.POST.get(f'period_dispatch_time_{p}', '').strip()
                period_dispatch_times[str(p)] = p_time if p_time else default_times.get(str(p), "17:00")

            att_settings.submission_grace_minutes = fallback_grace
            att_settings.period_grace_minutes = period_grace
            att_settings.period_dispatch_times = period_dispatch_times
            att_settings.management_chat_id = mgmt_chat_id or None
            att_settings.auto_daily_dispatch_enabled = auto_dispatch
            att_settings.auto_send_student_summary = auto_students
            att_settings.auto_send_teacher_summary = auto_teachers
            att_settings.hourly_dispatch_enabled = hourly_enabled
            att_settings.dispatch_to_guardians = dispatch_guardians
            att_settings.dispatch_to_homeroom = dispatch_homeroom
            att_settings.dispatch_to_management = dispatch_mgmt
            att_settings.daily_dispatch_schedule = sched

            # Assembly / Flag Ceremony Configuration
            att_settings.enable_assembly_attendance = request.POST.get('enable_assembly_attendance') == 'on'
            att_settings.assembly_morning_start = request.POST.get('assembly_morning_start', '06:30').strip() or '06:30'
            att_settings.assembly_morning_end = request.POST.get('assembly_morning_end', '06:50').strip() or '06:50'
            att_settings.assembly_afternoon_start = request.POST.get('assembly_afternoon_start', '12:30').strip() or '12:30'
            att_settings.assembly_afternoon_end = request.POST.get('assembly_afternoon_end', '12:50').strip() or '12:50'
            att_settings.allow_all_teachers_assembly_recording = request.POST.get('allow_all_teachers_assembly_recording') == 'on'
            att_settings.allow_monitor_assembly_recording = request.POST.get('allow_monitor_assembly_recording') == 'on'
            att_settings.assembly_telegram_alert = request.POST.get('assembly_telegram_alert') == 'on'
            att_settings.assembly_alarm_enabled = request.POST.get('assembly_alarm_enabled') == 'on'
            att_settings.assembly_alarm_message = request.POST.get('assembly_alarm_message', '').strip() or "⏰ ដល់ម៉ោងស្រង់វត្តមានពេលគោរពទង់ជាតិហើយ! សូមស្រង់ឱ្យបានមុនម៉ោងកំណត់"

            # Assembly Active Weekdays (1=Mon ... 7=Sun)
            active_days = []
            for d in range(1, 8):
                if request.POST.get(f'assembly_day_{d}') == 'on':
                    active_days.append(str(d))
            att_settings.assembly_active_days = active_days or ["1", "2", "3", "4", "5", "6"]

            att_settings.save()

            messages.success(request, "💾 បានរក្សាទុកការកំណត់ប្រព័ន្ធវត្តមាន និង Telegram ដោយជោគជ័យ!")
            return redirect('attendance_admin_hub')

        # 2. Toggle Assembly Today (Emergency Cancellation / Pop-Chat Broadcast)
        elif action == 'toggle_assembly_today':
            now_date = timezone.localtime(timezone.now()).date()
            is_disable = request.POST.get('disable_today') == '1'
            reason = request.POST.get('assembly_disabled_reason', '').strip()

            att_settings.is_assembly_disabled_today = is_disable
            att_settings.assembly_disabled_date = now_date if is_disable else None
            att_settings.assembly_disabled_reason = reason if is_disable else ""
            att_settings.save()

            if is_disable:
                from .telegram_utils import send_telegram_notification
                tg_msg = (
                    f"📢 <strong>[សេចក្តីជូនដំណឹងបន្ទាន់ / Urgent Notice]</strong>\n"
                    f"🏛️ <strong>ពីគណៈគ្រប់គ្រងសាលា៖</strong>\n"
                    f"🚫 <strong>ផ្អាកការស្រង់វត្តមានពេលគោរពទង់ជាតិសម្រាប់ថ្ងៃនេះ ({now_date.strftime('%d/%m/%Y')})</strong>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📝 <strong>មូលហេតុ / Reason៖</strong>\n"
                    f"{reason or 'ការសម្រេចផ្អាកជាបណ្តោះអាសន្នដោយគណៈគ្រប់គ្រងសាលា'}\n\n"
                    f"⚠️ <em>ចំណាំ៖ ម៉ោងទី ១ (០៧:០០) និងម៉ោងបន្តបន្ទាប់នៅតែស្រង់វត្តមានជាធម្មតា។</em>"
                )
                if att_settings.management_chat_id:
                    for cid in [c.strip() for c in att_settings.management_chat_id.split(',') if c.strip()]:
                        send_telegram_notification(title="📢 ផ្អាកការស្រង់វត្តមានគោរពទង់ជាតិថ្ងៃនេះ", message=tg_msg, custom_chat_id=cid)
                messages.warning(request, f"🚫 បានផ្អាកការស្រង់វត្តមានពេលគោរពទង់ជាតិសម្រាប់ថ្ងៃនេះ ({now_date}) និងបានផ្ញើសារ Pop-Chat ជូនដំណឹងរួចរាល់!")
            else:
                messages.success(request, "✅ បានបើកដំណើរការស្រង់វត្តមានពេលគោរពទង់ជាតិឡើងវិញសម្រាប់ថ្ងៃនេះ!")
            return redirect('attendance_admin_hub')

        # 3. Trigger Assembly Alarm Reminder
        elif action == 'trigger_assembly_alarm':
            now_dt = timezone.localtime(timezone.now())
            att_settings.assembly_last_alarm_sent = now_dt
            att_settings.save(update_fields=['assembly_last_alarm_sent'])

            custom_msg = request.POST.get('alarm_message', '').strip() or att_settings.assembly_alarm_message
            m_end = att_settings.assembly_morning_end or dtime(6, 50)

            from .telegram_utils import send_telegram_notification
            tg_msg = (
                f"🚨 <strong>[រោទ៍ដាស់តឿន / Assembly Alarm Reminder]</strong>\n"
                f"⏰ {custom_msg}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"⏳ <strong>ម៉ោងបញ្ចប់ស្រង់វត្តមាន៖</strong> ម៉ោង <strong>{m_end.strftime('%H:%M')}</strong> ព្រឹក\n"
                f"✍️ សូមលោកគ្រូ-អ្នកគ្រូ និងប្រធានថ្នាក់/អនុប្រធានថ្នាក់ មេត្តាចូលស្រង់វត្តមានឱ្យបានទាន់ពេលវេលា!"
            )
            if att_settings.management_chat_id:
                for cid in [c.strip() for c in att_settings.management_chat_id.split(',') if c.strip()]:
                    send_telegram_notification(title="🚨 រោទ៍ដាស់តឿនស្រង់វត្តមានគោរពទង់ជាតិ", message=tg_msg, custom_chat_id=cid)

            messages.success(request, "🔔 បានបន្លឺ Alarm និងផ្ញើសារដាស់តឿនទៅកាន់គ្រូ និងប្រធានថ្នាក់ទាំងអស់ដោយជោគជ័យ!")
            return redirect('attendance_admin_hub')

        # 4. Toggle Maintenance Mode
        elif action == 'toggle_maintenance':
            is_maint = request.POST.get('is_maintenance_mode') == 'on'
            maint_msg = request.POST.get('maintenance_message', '').strip()
            att_settings.is_maintenance_mode = is_maint
            if maint_msg:
                att_settings.maintenance_message = maint_msg
            att_settings.save()

            status_text = "បើកដំណើរការ (Maintenance ON)" if is_maint else "បិទបញ្ចប់ (Maintenance OFF)"
            messages.warning(request, f"🛠️ ការបិទប្រព័ន្ធថែទាំត្រូវបាន៖ {status_text}!")
            return redirect('attendance_admin_hub')

        # 3. Save Classroom Telegram Chat IDs (Bulk)
        elif action == 'save_class_chat_ids':
            classrooms_to_update = Classroom.objects.filter(academic_year=active_year) if active_year else Classroom.objects.all()
            updated_count = 0
            for cls in classrooms_to_update:
                field_name = f"chat_id_class_{cls.id}"
                if field_name in request.POST:
                    new_val = request.POST.get(field_name, '').strip()
                    if cls.telegram_chat_id != new_val:
                        cls.telegram_chat_id = new_val or None
                        cls.save(update_fields=['telegram_chat_id'])
                        updated_count += 1
            messages.success(request, f"✈️ បានកែប្រែ Telegram Chat ID សម្រាប់ {updated_count} ថ្នាក់រៀនដោយជោគជ័យ!")
            return redirect('attendance_admin_hub')

        # 4. Add Calendar Restriction (Vacation / Holiday)
        elif action == 'add_calendar_restriction':
            r_type = request.POST.get('restriction_type', 'HOLIDAY')
            title = request.POST.get('title', '').strip()
            start_d_str = request.POST.get('start_date')
            end_d_str = request.POST.get('end_date') or start_d_str
            block_att = request.POST.get('block_attendance') == 'on'
            desc = request.POST.get('description', '').strip()

            if title and start_d_str:
                try:
                    s_date = datetime.strptime(start_d_str, '%Y-%m-%d').date()
                    e_date = datetime.strptime(end_d_str, '%Y-%m-%d').date()
                    AcademicCalendarRestriction.objects.create(
                        restriction_type=r_type,
                        title=title,
                        start_date=s_date,
                        end_date=e_date,
                        block_attendance=block_att,
                        description=desc,
                        created_by=request.user,
                        is_active=True
                    )
                    messages.success(request, f"🌴 បានបញ្ចូលប្រតិទិនឈប់សម្រាក «{title}» ដោយជោគជ័យ!")
                except Exception as ex:
                    messages.error(request, f"⚠️ កំហុសកាលបរិច្ឆេទ៖ {str(ex)}")
            else:
                messages.error(request, "⚠️ សូមបំពេញឈ្មោះកម្មវិធី និងកាលបរិច្ឆេទឱ្យបានត្រឹមត្រូវ!")
            return redirect('attendance_admin_hub')

        # 5. Teacher Leave Approval / Rejection
        elif action in ['approve_leave', 'reject_leave']:
            leave_id = request.POST.get('leave_id')
            leave_req = get_object_or_404(TeacherLeaveRequest, pk=leave_id)
            if action == 'approve_leave':
                leave_req.status = TeacherLeaveRequest.Status.APPROVED
                leave_req.approved_by = request.user
                leave_req.save()
                # Create/Update TeacherAttendance records for the date range
                curr_d = leave_req.start_date
                while curr_d <= leave_req.end_date:
                    TeacherAttendance.objects.update_or_create(
                        teacher=leave_req.teacher,
                        date=curr_d,
                        defaults={
                            'status': TeacherAttendance.Status.EXCUSED_LEAVE,
                            'deduction_amount': 0,
                            'notes': f"សម្រាកច្បាប់ ({leave_req.get_leave_type_display()}): {leave_req.reason}"
                        }
                    )
                    curr_d += timedelta(days=1)
                
                send_teacher_leave_notification_telegram(leave_req)
                messages.success(request, f"✅ បានអនុម័តច្បាប់ឈប់សម្រាករបស់លោកគ្រូ-អ្នកគ្រូ {leave_req.teacher.khmer_name} ដោយជោគជ័យ!")
            else:
                rej_reason = request.POST.get('rejection_reason', '').strip()
                leave_req.status = TeacherLeaveRequest.Status.REJECTED
                leave_req.approved_by = request.user
                leave_req.rejection_reason = rej_reason
                leave_req.save()
                send_teacher_leave_notification_telegram(leave_req)
                messages.warning(request, f"❌ បានបដិសេធពាក្យសុំច្បាប់របស់ {leave_req.teacher.khmer_name}។")
            return redirect('attendance_admin_hub')

        # 6. Immediate Hourly Telegram Absence Dispatch
        elif action == 'dispatch_hourly_now':
            target_date_str = request.POST.get('target_date', date.today().strftime('%Y-%m-%d'))
            period_num = request.POST.get('period_number', '1')
            try:
                t_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
            except ValueError:
                t_date = date.today()
            
            res = send_hourly_period_absence_dispatch(
                target_date=t_date,
                period_number=int(period_num) if period_num.isdigit() else 1,
                sender_user=request.user,
                force=True
            )
            if res.get('success'):
                messages.success(request, f"🚀 {res.get('message')}")
            else:
                messages.error(request, f"⚠️ {res.get('message')}")
            return redirect('attendance_admin_hub')

        # 7. Immediate Daily Summary Dispatch
        elif action == 'dispatch_daily_now':
            target_date_str = request.POST.get('target_date', date.today().strftime('%Y-%m-%d'))
            try:
                t_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
            except ValueError:
                t_date = date.today()
            res = send_daily_summary_telegram(
                target_date=t_date,
                send_students=att_settings.auto_send_student_summary,
                send_teachers=att_settings.auto_send_teacher_summary
            )
            if res.get('success'):
                messages.success(request, f"🚀 {res.get('message')}")
            else:
                messages.error(request, f"⚠️ {res.get('message')}")
            return redirect('attendance_admin_hub')

    classrooms = Classroom.objects.filter(academic_year=active_year).select_related('homeroom_teacher').order_by('grade_level', 'code') if active_year else Classroom.objects.all().select_related('homeroom_teacher').order_by('grade_level', 'code')
    restrictions = AcademicCalendarRestriction.objects.all().order_by('-start_date')
    leave_requests = TeacherLeaveRequest.objects.all().select_related('teacher', 'approved_by').order_by('-created_at')
    teachers = Teacher.objects.filter(status='ACTIVE').order_by('teacher_id')

    # Weekly schedule mapping (1 to 7)
    schedule_data = att_settings.daily_dispatch_schedule or {}
    weekdays_info = [
        {'idx': 1, 'name_kh': 'ច័ន្ទ (Monday)', 'time': schedule_data.get('1', '17:00')},
        {'idx': 2, 'name_kh': 'អង្គារ (Tuesday)', 'time': schedule_data.get('2', '17:00')},
        {'idx': 3, 'name_kh': 'ពុធ (Wednesday)', 'time': schedule_data.get('3', '17:00')},
        {'idx': 4, 'name_kh': 'ព្រហស្បតិ៍ (Thursday)', 'time': schedule_data.get('4', '17:00')},
        {'idx': 5, 'name_kh': 'សុក្រ (Friday)', 'time': schedule_data.get('5', '17:00')},
        {'idx': 6, 'name_kh': 'សៅរ៍ (Saturday)', 'time': schedule_data.get('6', '11:30')},
        {'idx': 7, 'name_kh': 'អាទិត្យ (Sunday)', 'time': schedule_data.get('7', '')},
    ]

    # 8 Periods information
    period_grace_dict = att_settings.period_grace_minutes or {}
    period_dispatch_dict = att_settings.period_dispatch_times or {}
    default_dispatch_times = {"1": "07:35", "2": "08:30", "3": "09:25", "4": "10:20", "5": "13:35", "6": "14:30", "7": "15:25", "8": "16:20"}

    period_schedules = [
        {'num': 1, 'name_kh': 'ម៉ោងទី ១', 'time': '07:00 - 08:00', 'session': 'MORNING', 'session_kh': 'ពេលព្រឹក (Morning)'},
        {'num': 2, 'name_kh': 'ម៉ោងទី ២', 'time': '08:00 - 09:00', 'session': 'MORNING', 'session_kh': 'ពេលព្រឹក (Morning)'},
        {'num': 3, 'name_kh': 'ម៉ោងទី ៣', 'time': '09:00 - 10:00', 'session': 'MORNING', 'session_kh': 'ពេលព្រឹក (Morning)'},
        {'num': 4, 'name_kh': 'ម៉ោងទី ៤', 'time': '10:00 - 11:00', 'session': 'MORNING', 'session_kh': 'ពេលព្រឹក (Morning)'},
        {'num': 5, 'name_kh': 'ម៉ោងទី ៥', 'time': '13:00 - 14:00', 'session': 'AFTERNOON', 'session_kh': 'ពេលរសៀល (Afternoon)'},
        {'num': 6, 'name_kh': 'ម៉ោងទី ៦', 'time': '14:00 - 15:00', 'session': 'AFTERNOON', 'session_kh': 'ពេលរសៀល (Afternoon)'},
        {'num': 7, 'name_kh': 'ម៉ោងទី ៧', 'time': '15:00 - 16:00', 'session': 'AFTERNOON', 'session_kh': 'ពេលរសៀល (Afternoon)'},
        {'num': 8, 'name_kh': 'ម៉ោងទី ៨', 'time': '16:00 - 17:00', 'session': 'AFTERNOON', 'session_kh': 'ពេលរសៀល (Afternoon)'},
    ]
    periods_info = []
    for p in period_schedules:
        p_num_str = str(p['num'])
        p_grace = period_grace_dict.get(p_num_str, att_settings.submission_grace_minutes or 30)
        p_dispatch = period_dispatch_dict.get(p_num_str, default_dispatch_times.get(p_num_str, '17:00'))
        periods_info.append({
            **p,
            'grace_mins': p_grace,
            'dispatch_time': p_dispatch
        })


    return render(request, 'attendance/attendance_admin_hub.html', {
        'att_settings': att_settings,
        'telegram_config': telegram_config,
        'classrooms': classrooms,
        'restrictions': restrictions,
        'leave_requests': leave_requests,
        'teachers': teachers,
        'weekdays_info': weekdays_info,
        'periods_info': periods_info,
        'active_year': active_year,
        'today_str': date.today().strftime('%Y-%m-%d'),
    })


@login_required
def delete_calendar_restriction_view(request, pk):
    if not (request.user.role == 'ADMIN' or request.user.is_superuser):
        messages.error(request, "⚠️ អ្នកគ្មានសិទ្ធិលុបប្រតិទិននេះឡើយ!")
        return redirect('attendance_admin_hub')
    restriction = get_object_or_404(AcademicCalendarRestriction, pk=pk)
    title = restriction.title
    restriction.delete()
    messages.success(request, f"🗑️ បានលុប «{title}» ចេញពីប្រតិទិនឈប់សម្រាកដោយជោគជ័យ!")
    return redirect('attendance_admin_hub')


@login_required
def send_class_attendance_telegram_view(request):
    """
    Ajax/POST endpoint to send attendance report of a class to Telegram.
    """
    from django.http import JsonResponse
    from .telegram_utils import send_classroom_attendance_telegram

    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid HTTP Method'}, status=405)

    class_id = request.POST.get('classroom_id')
    date_str = request.POST.get('date')
    session = request.POST.get('session', 'MORNING')
    period = request.POST.get('period')
    custom_chat_id = request.POST.get('custom_chat_id', '').strip() or None

    classroom = get_object_or_404(Classroom, pk=class_id)
    try:
        t_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today()
    except ValueError:
        t_date = date.today()

    period_num = int(period) if period and period.isdigit() else None

    result = send_classroom_attendance_telegram(
        classroom=classroom,
        target_date=t_date,
        session=session,
        period_number=period_num,
        custom_chat_id=custom_chat_id,
        sender_user=request.user
    )

    return JsonResponse(result)


@login_required
@role_required(allowed_roles=['ADMIN'])
def send_missing_teachers_telegram_view(request):
    """
    Ajax/POST endpoint to dispatch unrecorded teacher compliance alert to Management Telegram.
    """
    from django.http import JsonResponse
    from .telegram_utils import send_missing_teachers_telegram

    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid HTTP Method'}, status=405)

    date_str = request.POST.get('date')
    period = request.POST.get('period')
    custom_chat_id = request.POST.get('custom_chat_id', '').strip() or None

    try:
        t_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today()
    except ValueError:
        t_date = date.today()

    period_num = int(period) if period and period.isdigit() else None

    result = send_missing_teachers_telegram(
        target_date=t_date,
        period_number=period_num,
        custom_chat_id=custom_chat_id,
        sender_user=request.user
    )

    return JsonResponse(result)


# ---------------------------------------------------------------------------
# Morning Assembly / Flag Ceremony Student Attendance (វត្តមានពេលគោរពទង់ជាតិ)
# ---------------------------------------------------------------------------

@login_required
def assembly_attendance_view(request):
    """
    Pre-Class & Morning Assembly / Flag Ceremony Attendance Recording View.
    Designed specifically for mobile/tablet & touch-friendly smartphone operations!
    
    Permissions:
      - Super Admin: Can view and record for ANY classroom.
      - Homeroom Teacher: Can view and record for assigned homeroom classes.
      - Class Monitor / Vice Monitor: Can view and record for their own classroom.
    """
    user = request.user
    active_year = get_active_academic_year(request)
    att_settings = AttendanceSetting.get_settings()
    now_dt = timezone.localtime(timezone.now())
    current_time = now_dt.time()
    today_date = now_dt.date()

    # Determine caller's authorized classrooms
    authorized_classrooms = Classroom.objects.none()
    student_profile = getattr(user, 'student_profile', None)
    teacher_profile = getattr(user, 'teacher_profile', None)
    is_monitor = False
    is_vice_monitor = False
    is_homeroom = False
    user_role_label = "អ្នកប្រើប្រាស់ទូទៅ"

    if user.role == 'ADMIN' or user.is_superuser:
        authorized_classrooms = Classroom.objects.filter(academic_year=active_year).order_by('grade_level', 'code') if active_year else Classroom.objects.all().order_by('grade_level', 'code')
        user_role_label = "គណៈគ្រប់គ្រង / Admin"
    elif user.role == 'TEACHER' and teacher_profile:
        if att_settings.allow_all_teachers_assembly_recording:
            # Admin allows all teachers to participate in assembly attendance
            authorized_classrooms = Classroom.objects.filter(academic_year=active_year).order_by('grade_level', 'code') if active_year else Classroom.objects.all().order_by('grade_level', 'code')
        else:
            # Restricted to homeroom or assigned assembly duty teacher
            duty_classes = Classroom.objects.filter(
                Q(homeroom_teacher=teacher_profile) | Q(assembly_duty_teacher=teacher_profile),
                academic_year=active_year
            ).order_by('grade_level', 'code')
            if duty_classes.exists():
                authorized_classrooms = duty_classes
            else:
                authorized_classrooms = Classroom.objects.filter(academic_year=active_year).order_by('grade_level', 'code') if active_year else Classroom.objects.all().order_by('grade_level', 'code')

        user_role_label = f"លោកគ្រូ/អ្នកគ្រូ ({teacher_profile.khmer_name})"
    elif student_profile:
        # Check if student is class monitor or vice monitor
        monitor_classes = Classroom.objects.filter(
            Q(class_monitor=student_profile) | Q(vice_monitor=student_profile),
            academic_year=active_year
        )
        if monitor_classes.exists():
            authorized_classrooms = monitor_classes
            matched_cls = monitor_classes.first()
            if matched_cls.class_monitor_id == student_profile.id:
                is_monitor = True
                user_role_label = f"ប្រធានថ្នាក់ ({student_profile.khmer_name})"
            else:
                is_vice_monitor = True
                user_role_label = f"អនុប្រធានថ្នាក់ ({student_profile.khmer_name})"

    if not authorized_classrooms.exists():
        messages.error(request, "⚠️ លោកអ្នកមិនមានសិទ្ធិចូលទៅកាន់ការស្រង់វត្តមានពេលគោរពទង់ជាតិឡើយ! (ត្រូវការសិទ្ធិជា Admin, គ្រូបង្រៀន, ឬប្រធានថ្នាក់/អនុប្រធានថ្នាក់)")
        return redirect('student_attendance_grid')

    # Selected classroom
    req_class_id = request.GET.get('classroom') or request.POST.get('classroom')
    selected_class = None
    if req_class_id and str(req_class_id).isdigit():
        selected_class = authorized_classrooms.filter(id=int(req_class_id)).first()
    if not selected_class:
        selected_class = authorized_classrooms.first()

    # Dynamic teacher label based on selected classroom
    if user.role == 'TEACHER' and teacher_profile and selected_class:
        if selected_class.homeroom_teacher_id == teacher_profile.id:
            is_homeroom = True
            user_role_label = f"លោកគ្រូ/អ្នកគ្រូបន្ទុកថ្នាក់ ({teacher_profile.khmer_name})"
        elif getattr(selected_class, 'assembly_duty_teacher_id', None) == teacher_profile.id:
            user_role_label = f"លោកគ្រូ/អ្នកគ្រូប្រចាំការស្រង់វត្តមាន ({teacher_profile.khmer_name})"
        else:
            user_role_label = f"លោកគ្រូ/អ្នកគ្រូ ({teacher_profile.khmer_name})"

    # Session Determination: Default is ALWAYS MORNING unless explicitly specified
    req_session = request.GET.get('session') or request.POST.get('session')
    if req_session in ['MORNING', 'AFTERNOON']:
        selected_session = req_session
    else:
        selected_session = 'MORNING'

    # Time Window Evaluation
    m_start = att_settings.assembly_morning_start or dtime(6, 30)
    m_end = att_settings.assembly_morning_end or dtime(6, 50)
    a_start = att_settings.assembly_afternoon_start or dtime(12, 30)
    a_end = att_settings.assembly_afternoon_end or dtime(12, 50)

    if selected_session == 'MORNING':
        window_start = m_start
        window_end = m_end
        session_title = "ពេលព្រឹក (Morning Flag Ceremony)"
    else:
        window_start = a_start
        window_end = a_end
        session_title = "ពេលរសៀល (Afternoon Pre-Class Assembly)"

    # Day of Week & Emergency Cancellation Check
    today_weekday_str = str(today_date.isoweekday()) # 1=Monday ... 7=Sunday
    is_active_day = today_weekday_str in (att_settings.assembly_active_days or ["1", "2", "3", "4", "5", "6"])
    is_cancelled_today = att_settings.is_assembly_disabled_today and (att_settings.assembly_disabled_date == today_date or not att_settings.assembly_disabled_date)
    
    is_disabled_today = (not is_active_day) or is_cancelled_today or (not att_settings.enable_assembly_attendance)
    disabled_reason = ""
    if not att_settings.enable_assembly_attendance:
        disabled_reason = "ប្រព័ន្ធស្រង់វត្តមានពេលគោរពទង់ជាតិត្រូវបានបិទដំណើរការជាបណ្តោះអាសន្នដោយគណៈគ្រប់គ្រងសាលា។"
    elif is_cancelled_today:
        disabled_reason = att_settings.assembly_disabled_reason or "គណៈគ្រប់គ្រងសាលាបានសម្រេចផ្អាកការស្រង់វត្តមានពេលគោរពទង់ជាតិសម្រាប់ថ្ងៃនេះ។"
    elif not is_active_day:
        disabled_reason = "ថ្ងៃនេះមិនមែនជាថ្ងៃដែលត្រូវស្រង់វត្តមានពេលគោរពទង់ជាតិនោះឡើយ។"

    is_admin_override = (user.role == 'ADMIN' or user.is_superuser)
    is_within_window = (window_start <= current_time <= window_end)

    # Calculate remaining minutes until window end
    remaining_minutes = 0
    if is_within_window:
        end_dt = datetime.combine(today_date, window_end)
        curr_dt = datetime.combine(today_date, current_time)
        diff = (end_dt - curr_dt).total_seconds()
        remaining_minutes = max(0, int(diff // 60))

    alarm_active = False
    if att_settings.assembly_last_alarm_sent:
        alarm_diff = (now_dt - att_settings.assembly_last_alarm_sent).total_seconds()
        if alarm_diff < 3600: # Alarm dispatched within past hour
            alarm_active = True

    if is_disabled_today and not is_admin_override:
        window_status = 'CANCELLED'
        window_message = f'ផ្អាកការស្រង់វត្តមាន៖ {disabled_reason}'
        can_submit = False
    elif is_admin_override:
        window_status = 'OPEN_ADMIN'
        window_message = 'លោកអ្នកមានសិទ្ធិជា Admin អាចស្រង់ ឬកែប្រែបានគ្រប់ពេលវេលា។'
        can_submit = True
    elif is_within_window:
        window_status = 'OPEN'
        window_message = f'កំពុងស្ថិតក្នុងម៉ោងស្រង់វត្តមាន ({window_start.strftime("%H:%M")} - {window_end.strftime("%H:%M")})'
        can_submit = True
    elif current_time < window_start:
        window_status = 'EARLY'
        window_message = f'មិនទាន់ដល់ម៉ោងស្រង់វត្តមានឡើយ (បើកនៅម៉ោង {window_start.strftime("%H:%M")})'
        can_submit = False
    else:
        window_status = 'CLOSED'
        window_message = f'ផុតម៉ោងស្រង់វត្តមានពេលគោរពទង់ជាតិហើយ (ផុតកំណត់ម៉ោង {window_end.strftime("%H:%M")})'
        can_submit = False

    # Fetch active students for selected classroom
    students = Student.objects.filter(classroom=selected_class, status='ACTIVE').order_by('khmer_name') if selected_class else []

    # Handle POST Submission
    if request.method == 'POST' and selected_class:
        if not can_submit and not is_admin_override:
            messages.error(request, f"❌ បរាជ័យ៖ {window_message}")
            return redirect(f"/attendance/assembly/?classroom={selected_class.id}&session={selected_session}")

        saved_absent_count = 0
        saved_permission_count = 0
        saved_late_count = 0
        absent_student_names = []

        with transaction.atomic():
            # Clean up prior records for Period 0 today
            StudentAttendance.objects.filter(
                classroom=selected_class,
                date=today_date,
                session=selected_session,
                period_number=0
            ).delete()

            new_records = []
            for st in students:
                is_marked = request.POST.get(f'status_{st.id}')
                notes = request.POST.get(f'notes_{st.id}', '').strip()

                if is_marked in [StudentAttendance.Status.ABSENT, StudentAttendance.Status.PERMISSION, StudentAttendance.Status.LATE]:
                    new_records.append(StudentAttendance(
                        student=st,
                        classroom=selected_class,
                        date=today_date,
                        session=selected_session,
                        period_number=0, # 0 indicates Assembly / Flag Ceremony
                        status=is_marked,
                        notes=notes or 'វត្តមានពេលគោរពទង់ជាតិ',
                        recorded_by=request.user
                    ))
                    if is_marked == StudentAttendance.Status.ABSENT:
                        saved_absent_count += 1
                        absent_student_names.append(f"• {st.khmer_name} (ឥតច្បាប់)")
                    elif is_marked == StudentAttendance.Status.PERMISSION:
                        saved_permission_count += 1
                        absent_student_names.append(f"• {st.khmer_name} (មានច្បាប់)")
                    elif is_marked == StudentAttendance.Status.LATE:
                        saved_late_count += 1
                        absent_student_names.append(f"• {st.khmer_name} (មកយឺត)")

            if new_records:
                StudentAttendance.objects.bulk_create(new_records)

            # Update / Log submission
            AttendanceSubmissionLog.objects.update_or_create(
                classroom=selected_class,
                date=today_date,
                session=selected_session,
                period_number=0,
                defaults={
                    'recorded_by': request.user,
                }
            )

        # Telegram Instant Alert to Management & Homeroom
        if att_settings.assembly_telegram_alert:
            from .telegram_utils import send_telegram_notification
            total_students_cnt = students.count()
            present_cnt = total_students_cnt - (saved_absent_count + saved_permission_count)
            absent_details_str = "\n".join(absent_student_names) if absent_student_names else "✅ សិស្សមានវត្តមានគ្រប់ៗគ្នា ១០០%"
            
            tg_msg = (
                f"🚩 <strong>របាយការណ៍វត្តមានពេលគោរពទង់ជាតិ / Assembly Report</strong>\n"
                f"🏫 <strong>ថ្នាក់រៀន៖</strong> {selected_class.name}\n"
                f"📅 <strong>កាលបរិច្ឆេទ៖</strong> {today_date.strftime('%d/%m/%Y')} ({session_title})\n"
                f"✍️ <strong>អ្នកស្រង់វត្តមាន៖</strong> {user.display_name} ({user_role_label})\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"👥 សិស្សសរុប៖ <strong>{total_students_cnt}</strong> នាក់\n"
                f"✅ វត្តមាន៖ <strong>{present_cnt}</strong> នាក់\n"
                f"❌ អវត្តមានឥតច្បាប់៖ <strong>{saved_absent_count}</strong> នាក់\n"
                f"📝 អវត្តមានមានច្បាប់៖ <strong>{saved_permission_count}</strong> នាក់\n"
                f"⏰ មកយឺត៖ <strong>{saved_late_count}</strong> នាក់\n\n"
                f"<strong>បញ្ជីឈ្មោះសិស្សអវត្តមាន/យឺត៖</strong>\n"
                f"{absent_details_str}\n"
            )

            # 1. Send to School Management Telegram
            if att_settings.management_chat_id:
                for cid in [c.strip() for c in att_settings.management_chat_id.split(',') if c.strip()]:
                    send_telegram_notification(
                        title=f"🚩 វត្តមានគោរពទង់ជាតិ: {selected_class.name}",
                        message=tg_msg,
                        custom_chat_id=cid
                    )

            # 2. Send to Classroom / Homeroom Telegram
            class_chat = selected_class.telegram_chat_id
            if class_chat:
                for cid in [c.strip() for c in class_chat.split(',') if c.strip()]:
                    send_telegram_notification(
                        title=f"🚩 វត្តមានគោរពទង់ជាតិ: {selected_class.name}",
                        message=tg_msg,
                        custom_chat_id=cid
                    )

        messages.success(request, f"✅ បានរក្សាទុកវត្តមានពេលគោរពទង់ជាតិ ({selected_class.name}) ជោគជ័យ! (អវត្តមាន: {saved_absent_count}, ច្បាប់: {saved_permission_count}, យឺត: {saved_late_count})")
        return redirect(f"/attendance/assembly/?classroom={selected_class.id}&session={selected_session}")

    # Query existing Period 0 attendance records for today
    today_records = {}
    if selected_class:
        records_qs = StudentAttendance.objects.filter(
            classroom=selected_class,
            date=today_date,
            session=selected_session,
            period_number=0
        )
        for r in records_qs:
            today_records[r.student_id] = {
                'status': r.status,
                'notes': r.notes or ''
            }

    student_roster = []
    absent_count = 0
    permission_count = 0
    late_count = 0

    for st in students:
        rec = today_records.get(st.id)
        status_val = rec['status'] if rec else 'PRESENT'
        notes_val = rec['notes'] if rec else ''
        
        if status_val == StudentAttendance.Status.ABSENT:
            absent_count += 1
        elif status_val == StudentAttendance.Status.PERMISSION:
            permission_count += 1
        elif status_val == StudentAttendance.Status.LATE:
            late_count += 1

        student_roster.append({
            'student': st,
            'status': status_val,
            'notes': notes_val,
        })

    submission_log = AttendanceSubmissionLog.objects.filter(
        classroom=selected_class,
        date=today_date,
        session=selected_session,
        period_number=0
    ).select_related('recorded_by').first() if selected_class else None

    context = {
        'active_year': active_year,
        'att_settings': att_settings,
        'authorized_classrooms': authorized_classrooms,
        'selected_class': selected_class,
        'selected_session': selected_session,
        'session_title': session_title,
        'today_date': today_date,
        'current_time': current_time,
        'window_start': window_start,
        'window_end': window_end,
        'window_status': window_status,
        'window_message': window_message,
        'can_submit': can_submit,
        'is_admin_override': is_admin_override,
        'user_role_label': user_role_label,
        'is_monitor': is_monitor,
        'is_vice_monitor': is_vice_monitor,
        'is_homeroom': is_homeroom,
        'student_roster': student_roster,
        'total_students_count': len(student_roster),
        'absent_count': absent_count,
        'permission_count': permission_count,
        'late_count': late_count,
        'present_count': len(student_roster) - (absent_count + permission_count),
        'submission_log': submission_log,
        'is_disabled_today': is_disabled_today,
        'disabled_reason': disabled_reason,
        'is_cancelled_today': is_cancelled_today,
        'remaining_minutes': remaining_minutes,
        'alarm_active': alarm_active,
    }
    return render(request, 'attendance/assembly_attendance.html', context)



