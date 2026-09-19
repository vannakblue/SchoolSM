import os
from pathlib import Path
from django.conf import settings
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
    send_daily_grade_student_absence_telegram,
    send_daily_teacher_absence_telegram,
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
    flag_path = Path(settings.BASE_DIR) / 'maintenance.flag'
    if att_settings.is_maintenance_mode or flag_path.exists() or os.environ.get('MAINTENANCE_MODE') == '1':
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
    req_class_id = request.POST.get('classroom') or request.GET.get('classroom')
    req_date_str = request.POST.get('date') or request.GET.get('date', today_date.strftime('%Y-%m-%d'))
    req_session = request.POST.get('session') or request.GET.get('session')
    req_period = request.POST.get('period') or request.GET.get('period')

    khmer_days = {
        1: 'ច័ន្ទ',
        2: 'អង្គារ',
        3: 'ពុធ',
        4: 'ព្រហស្បតិ៍',
        5: 'សុក្រ',
        6: 'សៅរ៍',
        7: 'អាទិត្យ',
    }

    selected_class = None
    selected_period = None
    selected_subject = None
    selected_session = None
    is_timetable_locked = False
    detected_slot_info = None
    teacher_schedule_alert = None
    today_slots = []

    if user.role == 'TEACHER':
        # RULE: Teachers CANNOT modify date, session, classroom, or period.
        # Date is ALWAYS today. Class, session, period come strictly from Timetable.
        selected_date = today_date
        day_name = khmer_days.get(today_date.isoweekday(), '')
        is_timetable_locked = True

        if teacher_profile:
            today_slots = Timetable.objects.filter(
                teacher=teacher_profile,
                day_of_week=today_date.isoweekday(),
                classroom__academic_year=active_year
            ).select_related('classroom', 'subject').order_by('period_number')

        if today_slots.exists():
            slot = None
            if req_period and req_class_id:
                try:
                    slot = today_slots.filter(period_number=int(req_period), classroom_id=int(req_class_id)).first()
                except (ValueError, TypeError):
                    slot = None
            if not slot and req_period:
                try:
                    slot = today_slots.filter(period_number=int(req_period)).first()
                except (ValueError, TypeError):
                    slot = None
            if not slot and req_class_id:
                try:
                    slot = today_slots.filter(classroom_id=int(req_class_id)).first()
                except (ValueError, TypeError):
                    slot = None
            if not slot:
                # Try auto period by time, or default to first slot of today
                slot = today_slots.filter(period_number=auto_period_num).first() or today_slots.first()

            selected_class = slot.classroom
            selected_period = slot.period_number
            selected_subject = slot.subject
            selected_session = StudentAttendance.Session.MORNING if slot.period_number <= 4 else StudentAttendance.Session.AFTERNOON
            detected_slot_info = {
                'classroom': selected_class,
                'period': selected_period,
                'subject': selected_subject,
                'session_name': 'ពេលព្រឹក (Morning)' if slot.period_number <= 4 else 'ពេលរសៀល (Afternoon)',
            }
        else:
            selected_class = None
            selected_period = auto_period_num
            selected_session = auto_session
            selected_subject = None
            detected_slot_info = None
            teacher_schedule_alert = {
                'show_modal': True,
                'alert_type': 'NO_CLASS_TODAY',
                'badge_text': 'គ្មានកាលវិភាគពេញមួយថ្ងៃ',
                'title': 'លោកគ្រូ-អ្នកគ្រូពុំមានម៉ោងបង្រៀនក្នុងថ្ងៃនេះទេ',
                'message': f'លោកគ្រូ-អ្នកគ្រូមិនមានម៉ោងបង្រៀននៅក្នុងថ្ងៃ{day_name} ទី {selected_date.strftime("%d/%m/%Y")} ឡើយ។ សូមពិនិត្យមើលកាលវិភាគបង្រៀនរួម ឬកាលវិភាគប្រចាំសប្តាហ៍។ ការកត់ត្រាវត្តមានត្រូវបានបិទ (Disabled)។',
                'icon': 'fa-calendar-xmark',
                'icon_color': 'text-danger',
                'bg_color': 'bg-danger-subtle',
                'has_classes_today': False,
                'other_slots': [],
            }
    else:
        # Admin / Accountant: Can manually choose date, classroom, session, period
        try:
            selected_date = datetime.strptime(req_date_str, '%Y-%m-%d').date()
        except ValueError:
            selected_date = today_date
        day_name = khmer_days.get(selected_date.isoweekday(), '')

        if req_class_id:
            selected_class = classrooms.filter(id=req_class_id).first() or Classroom.objects.filter(id=req_class_id).first()
        else:
            selected_class = classrooms.first()

        if req_period and str(req_period).isdigit():
            selected_period = int(req_period)
        else:
            selected_period = auto_period_num

        if req_session in ['MORNING', 'AFTERNOON']:
            selected_session = req_session
        else:
            selected_session = StudentAttendance.Session.MORNING if selected_period <= 4 else StudentAttendance.Session.AFTERNOON

    # 3. Evaluate Timing Window
    if user.role == 'ADMIN':
        timing_eval = {
            'can_submit': True,
            'status_code': 'ADMIN_OVERRIDE',
            'status_label': 'សិទ្ធិ Admin (ពេញលេញ)',
            'status_message': 'លោកអ្នកមានសិទ្ធិអាចស្រង់វត្តមាន ឬកែប្រែបានគ្រប់ពេលវេលា។',
            'badge_class': 'primary',
            'submission_log': AttendanceSubmissionLog.objects.filter(classroom=selected_class, date=selected_date, session=selected_session, period_number=selected_period).first() if selected_class else None,
            'start_time_str': '--:--',
            'end_time_str': '--:--'
        }
        is_form_disabled = False
    else:
        timing_eval = evaluate_attendance_timing_window(teacher_profile, selected_class, selected_period, selected_date, current_dt=now_dt)
        is_form_disabled = (not timing_eval['can_submit']) or (teacher_schedule_alert is not None)

    # 4. Handle POST: Absence-First Saving & Enforcement
    if request.method == 'POST' and selected_class:
        post_period = request.POST.get('period')
        period_num_save = int(post_period) if post_period and post_period.isdigit() else (selected_period or 1)

        # Enforce Teacher Timetable Schedule for POST
        if user.role == 'TEACHER':
            selected_date = today_date
            period_num_save = selected_period or period_num_save
            selected_session = StudentAttendance.Session.MORNING if period_num_save <= 4 else StudentAttendance.Session.AFTERNOON

            is_post_scheduled = teacher_profile and Timetable.objects.filter(
                teacher=teacher_profile,
                classroom=selected_class,
                period_number=period_num_save,
                day_of_week=today_date.isoweekday(),
                classroom__academic_year=active_year
            ).exists()
            if not is_post_scheduled:
                messages.error(
                    request,
                    f"❌ បរាជ័យក្នុងការរក្សាទុក៖ លោកគ្រូ-អ្នកគ្រូពុំមានម៉ោងបង្រៀននៅថ្នាក់ {selected_class.name} "
                    f"ក្នុងម៉ោងទី {period_num_save} (ថ្ងៃ{day_name}) ឡើយ! ការកត់ត្រាវត្តមានត្រូវបានបិទ (Disabled)។"
                )
                return redirect(f"/attendance/?classroom={selected_class.id}&period={period_num_save}")

        if user.role != 'ADMIN' and not timing_eval['can_submit']:
            messages.error(request, f"❌ បរាជ័យក្នុងការរក្សាទុក៖ {timing_eval['status_message']}")
            if user.role == 'TEACHER':
                return redirect(f"/attendance/?classroom={selected_class.id}&period={selected_period}")
            redirect_url = f"/attendance/?classroom={selected_class.id}&date={selected_date.strftime('%Y-%m-%d')}&session={selected_session}"
            if selected_period:
                redirect_url += f"&period={selected_period}"
            return redirect(redirect_url)

        notify_parents = request.POST.get('notify_parents') == '1'
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
            messages.success(request, f"✅ បានកែប្រែ និងរក្សាទុកការស្រង់អវត្តមានសិស្សថ្នាក់ {selected_class.name} (ម៉ោងទី {period_num_save}) ឡើងវិញជាលើកទី {log_obj.submission_count} ដោយជោគជ័យ! (សិស្សអវត្តមាន/សុំច្បាប់/យឺត សរុប៖ {saved_absent_count} នាក់)")
        else:
            messages.success(request, f"✅ បានរក្សាទុកការស្រង់អវត្តមានសិស្សថ្នាក់ {selected_class.name} (ម៉ោងទី {period_num_save}) ជោគជ័យ! (សិស្សអវត្តមាន/សុំច្បាប់/យឺត សរុប៖ {saved_absent_count} នាក់)")

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

        if user.role == 'TEACHER':
            redirect_url = f"/attendance/?classroom={selected_class.id}&period={period_num_save}"
        else:
            redirect_url = f"/attendance/?classroom={selected_class.id}&date={selected_date.strftime('%Y-%m-%d')}&session={selected_session}"
            if selected_period:
                redirect_url += f"&period={selected_period}"
        return redirect(redirect_url)

    # 5. Load Students Data with Absence Flags
    students_data = []
    existing_records = {}
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

    last_submit_log = timing_eval.get('submission_log') if timing_eval else None
    if not last_submit_log and selected_class:
        last_submit_log = AttendanceSubmissionLog.objects.filter(
            classroom=selected_class,
            date=selected_date,
            session=selected_session,
            period_number=selected_period
        ).first()

    has_already_submitted = bool(
        (last_submit_log is not None and last_submit_log.submission_count > 0) or
        existing_records
    )

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
        'has_already_submitted': has_already_submitted,
        'last_submit_log': last_submit_log,
    })





def export_student_attendance_report_excel(report_data, summary_stats, selected_class, selected_grade_level, target_classes_count, filter_label, active_year, search_query=''):
    """Generates a styled Excel export for student attendance matching the current view."""
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter
    from django.http import HttpResponse
    from apps.accounts.models import SchoolProfile

    try:
        school_info = SchoolProfile.get_settings()
        school_name = school_info.name_kh if school_info and school_info.name_kh else "ប្រព័ន្ធគ្រប់គ្រងសាលារៀន (SchoolSM)"
    except Exception:
        school_name = "ប្រព័ន្ធគ្រប់គ្រងសាលារៀន (SchoolSM)"

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "វត្តមានសិស្ស"
    ws.views.sheetView[0].showGridLines = True

    font_title = Font(name='Kantumruy Pro', size=14, bold=True, color='1E3A8A')
    font_subtitle = Font(name='Kantumruy Pro', size=11, bold=True, color='1E293B')
    font_meta = Font(name='Kantumruy Pro', size=10, italic=False, color='475569')
    font_header = Font(name='Kantumruy Pro', size=10, bold=True, color='FFFFFF')
    font_data = Font(name='Kantumruy Pro', size=10)
    font_data_bold = Font(name='Kantumruy Pro', size=10, bold=True)
    font_danger = Font(name='Kantumruy Pro', size=10, bold=True, color='DC2626')
    font_success = Font(name='Kantumruy Pro', size=10, bold=True, color='16A34A')
    font_warning = Font(name='Kantumruy Pro', size=10, bold=True, color='D97706')

    fill_header = PatternFill(start_color='1E40AF', end_color='1E40AF', fill_type='solid') # Royal Blue
    fill_sub_kpi = PatternFill(start_color='F1F5F9', end_color='F1F5F9', fill_type='solid') # Light Slate
    fill_zebra = PatternFill(start_color='F8FAFC', end_color='F8FAFC', fill_type='solid')
    fill_total = PatternFill(start_color='E2E8F0', end_color='E2E8F0', fill_type='solid')

    border_thin = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )
    border_double = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='double', color='1E293B')
    )

    align_center = Alignment(horizontal='center', vertical='center', wrap_text=True)
    align_left = Alignment(horizontal='left', vertical='center')

    # Row 1: School Name
    ws.merge_cells('A1:L1')
    ws['A1'] = school_name
    ws['A1'].font = font_title
    ws['A1'].alignment = align_center
    ws.row_dimensions[1].height = 28

    # Row 2: Report Title
    ws.merge_cells('A2:L2')
    ws['A2'] = "របាយការណ៍វត្តមានសិស្ស (STUDENT ATTENDANCE REPORT)"
    ws['A2'].font = font_subtitle
    ws['A2'].alignment = align_center
    ws.row_dimensions[2].height = 22

    # Row 3: Scope Description
    if selected_class:
        scope_txt = f"ថ្នាក់រៀន៖ {selected_class.name}"
    elif selected_grade_level:
        scope_txt = f"កម្រិតថ្នាក់៖ ថ្នាក់ទី {selected_grade_level} ({target_classes_count} ថ្នាក់)"
    else:
        scope_txt = f"វិសាលភាព៖ គ្រប់ថ្នាក់ទូទាំងសាលា ({target_classes_count} ថ្នាក់)"

    ay_txt = f"ឆ្នាំសិក្សា៖ {active_year.name if active_year else '-'}"
    filter_desc = f"{scope_txt}  |  ចន្លោះពេល៖ {filter_label}  |  {ay_txt}"
    if search_query:
        filter_desc += f"  |  ពាក្យស្វែងរក៖ \"{search_query}\""

    ws.merge_cells('A3:L3')
    ws['A3'] = filter_desc
    ws['A3'].font = font_meta
    ws['A3'].alignment = align_center
    ws.row_dimensions[3].height = 20

    # Row 4: Summary KPI Bar
    kpi_txt = (
        f"សិស្សសរុប៖ {summary_stats.get('total_students', 0)} នាក់   |   "
        f"វេនសិក្សាបានស្រង់៖ {summary_stats.get('total_sessions_held', 0)} ពេល   |   "
        f"អវត្តមានឥតច្បាប់៖ {summary_stats.get('total_absent_sessions', 0)} ពេល   |   "
        f"សុំច្បាប់៖ {summary_stats.get('total_permission_sessions', 0)} ពេល   |   "
        f"មកយឺត៖ {summary_stats.get('total_late_sessions', 0)} ពេល   |   "
        f"អត្រាវត្តមានមធ្យម៖ {summary_stats.get('avg_attendance_rate', 100.0)}%"
    )
    ws.merge_cells('A4:L4')
    ws['A4'] = kpi_txt
    ws['A4'].font = font_data_bold
    ws['A4'].fill = fill_sub_kpi
    ws['A4'].alignment = align_center
    ws['A4'].border = border_thin
    ws.row_dimensions[4].height = 24

    ws.row_dimensions[5].height = 8

    # Row 6: Table Headers
    headers = [
        "ល.រ",
        "អត្តលេខសិស្ស",
        "គោត្តនាម និងនាម",
        "ឈ្មោះឡាតាំង",
        "ថ្នាក់រៀន",
        "ភេទ",
        "វត្តមាន (Present)",
        "ច្បាប់ (Permission)",
        "អវត្តមាន (Absent)",
        "មកយឺត (Late)",
        "វេនសរុប (Total)",
        "អត្រាវត្តមាន (%)",
    ]
    ws.row_dimensions[6].height = 28
    for col_num, h_title in enumerate(headers, 1):
        cell = ws.cell(row=6, column=col_num, value=h_title)
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = align_center
        cell.border = border_thin

    # Data Rows
    current_row = 7
    total_present_sum = 0
    total_perm_sum = 0
    total_absent_sum = 0
    total_late_sum = 0
    total_held_sum = 0

    for idx, r in enumerate(report_data, 1):
        stu = r['student']
        gender_km = 'ស្រី' if getattr(stu, 'gender', '') == 'F' else 'ប្រុស'
        class_name = stu.classroom.name if getattr(stu, 'classroom', None) else '-'

        row_values = [
            idx,
            stu.student_id,
            stu.khmer_name,
            stu.latin_name or '',
            class_name,
            gender_km,
            r.get('present', 0),
            r.get('permission', 0),
            r.get('absent', 0),
            r.get('late', 0),
            r.get('total', 0),
            f"{r.get('rate', 100.0)}%",
        ]

        total_present_sum += r.get('present', 0)
        total_perm_sum += r.get('permission', 0)
        total_absent_sum += r.get('absent', 0)
        total_late_sum += r.get('late', 0)
        total_held_sum += r.get('total', 0)

        ws.row_dimensions[current_row].height = 22
        is_even = (idx % 2 == 0)

        for col_num, val in enumerate(row_values, 1):
            cell = ws.cell(row=current_row, column=col_num, value=val)
            cell.font = font_data
            cell.border = border_thin
            if is_even:
                cell.fill = fill_zebra

            if col_num in [1, 2, 5, 6, 7, 8, 9, 10, 11, 12]:
                cell.alignment = align_center
            else:
                cell.alignment = align_left

            # Highlights
            if col_num == 9 and r.get('absent', 0) > 0:
                cell.font = font_danger
            elif col_num == 8 and r.get('permission', 0) > 0:
                cell.font = font_warning
            elif col_num == 7 and r.get('present', 0) > 0:
                cell.font = font_success
            elif col_num == 12:
                rate_val = r.get('rate', 100.0)
                if rate_val >= 80:
                    cell.font = font_success
                elif rate_val >= 50:
                    cell.font = font_warning
                else:
                    cell.font = font_danger

        current_row += 1

    # Summary Total Row
    if report_data:
        ws.row_dimensions[current_row].height = 24
        ws.cell(row=current_row, column=1, value="")
        ws.cell(row=current_row, column=2, value="")
        total_label_cell = ws.cell(row=current_row, column=3, value="សរុបរួម (Overall Total)")
        total_label_cell.font = font_data_bold
        total_label_cell.alignment = align_left

        for c_idx in range(1, 7):
            c = ws.cell(row=current_row, column=c_idx)
            c.fill = fill_total
            c.border = border_double

        sums = [
            (7, total_present_sum),
            (8, total_perm_sum),
            (9, total_absent_sum),
            (10, total_late_sum),
            (11, total_held_sum),
            (12, f"{summary_stats.get('avg_attendance_rate', 100.0)}%"),
        ]
        for col_idx, s_val in sums:
            scell = ws.cell(row=current_row, column=col_idx, value=s_val)
            scell.font = font_data_bold
            scell.fill = fill_total
            scell.border = border_double
            scell.alignment = align_center

    ws.column_dimensions['A'].width = 8
    ws.column_dimensions['B'].width = 16
    ws.column_dimensions['C'].width = 24
    ws.column_dimensions['D'].width = 20
    ws.column_dimensions['E'].width = 14
    ws.column_dimensions['F'].width = 10
    ws.column_dimensions['G'].width = 18
    ws.column_dimensions['H'].width = 18
    ws.column_dimensions['I'].width = 18
    ws.column_dimensions['J'].width = 14
    ws.column_dimensions['K'].width = 14
    ws.column_dimensions['L'].width = 18

    target_tag = selected_class.name if selected_class else (f"Grade_{selected_grade_level}" if selected_grade_level else "All_Classes")
    safe_target = "".join(c for c in target_tag if c.isalnum() or c in ('-', '_'))
    filename = f"Student_Attendance_{safe_target}_{date.today().strftime('%Y%m%d')}.xlsx"

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


@login_required
@role_required(['ADMIN', 'TEACHER'])
def attendance_report(request):
    """
    Flexible Attendance aggregation report (Today, Week, Month, Custom).
    Supports:
    - All Classrooms (ជ្រើសរើសទាំងអស់)
    - By Grade Level (តាមកម្រិតថ្នាក់)
    - By Classroom (តាមជ្រើសរើសថ្នាក់រៀន)
    - Real-time instant search by Student ID or Name (show as typing)
    - Role restrictions for Teachers (restricted to assigned classrooms)
    Deduplication Rule:
    Absences are counted at most 1 time per session (Morning / Afternoon).
    Even if a student was absent across 4 morning periods, it counts as exactly 1 morning absence.
    """
    active_year = get_active_academic_year(request)
    base_classrooms = Classroom.objects.filter(academic_year=active_year).order_by('grade_level', 'code') if active_year else Classroom.objects.all().order_by('grade_level', 'code')

    # Teacher role isolation
    if getattr(request.user, 'role', None) == 'TEACHER':
        from apps.academics.utils import get_teacher_allowed_classroom_ids
        allowed_cls_ids = get_teacher_allowed_classroom_ids(request.user)
        base_classrooms = base_classrooms.filter(id__in=allowed_cls_ids)

    # Extract distinct available grades
    available_grades = sorted(list(set(base_classrooms.values_list('grade_level', flat=True).distinct())))

    grade_level = request.GET.get('grade_level', '').strip()
    selected_class_id = request.GET.get('classroom', '').strip()
    search_query = request.GET.get('q', '').strip()

    filtered_classrooms = base_classrooms
    if grade_level and grade_level != 'ALL':
        try:
            gl_int = int(grade_level)
            filtered_classrooms = base_classrooms.filter(grade_level=gl_int)
        except ValueError:
            pass

    # Determine target classes to include in the report
    if selected_class_id and selected_class_id != 'ALL':
        target_classes = filtered_classrooms.filter(id=selected_class_id)
        if not target_classes.exists():
            # If classroom ID doesn't exist in filtered_classrooms, check base_classrooms
            target_classes = base_classrooms.filter(id=selected_class_id)
            if target_classes.exists():
                c_grade = target_classes.first().grade_level
                grade_level = str(c_grade)
                filtered_classrooms = base_classrooms.filter(grade_level=c_grade)
            else:
                target_classes = filtered_classrooms
                selected_class_id = 'ALL'
    else:
        if not selected_class_id:
            selected_class_id = 'ALL'
        target_classes = filtered_classrooms

    selected_class = target_classes.first() if (selected_class_id != 'ALL' and target_classes.count() == 1) else None
    
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

    report_data = []
    summary_stats = {
        'total_students': 0,
        'total_sessions_held': 0,
        'avg_attendance_rate': 100.0,
        'total_absent_sessions': 0,
        'total_permission_sessions': 0,
        'total_late_sessions': 0,
    }

    if target_classes.exists():
        students_qs = Student.objects.filter(classroom__in=target_classes, status='ACTIVE')\
                                     .select_related('classroom')\
                                     .order_by('classroom__grade_level', 'classroom__name', 'student_id')

        if search_query:
            students_qs = students_qs.filter(
                Q(student_id__icontains=search_query) |
                Q(khmer_name__icontains=search_query) |
                Q(latin_name__icontains=search_query)
            )

        students = list(students_qs)
        summary_stats['total_students'] = len(students)

        # 1. Bulk calculate distinct sessions held per classroom in date range
        logged_sessions = AttendanceSubmissionLog.objects.filter(
            classroom__in=target_classes,
            date__range=(start_date, end_date)
        ).values_list('classroom_id', 'date', 'session')

        att_sessions = StudentAttendance.objects.filter(
            classroom__in=target_classes,
            date__range=(start_date, end_date)
        ).values_list('classroom_id', 'date', 'session')

        class_sessions_map = {c.id: set() for c in target_classes}
        all_school_sessions = set()
        for c_id, d, sess in logged_sessions:
            if c_id in class_sessions_map:
                class_sessions_map[c_id].add((d, sess))
            all_school_sessions.add((d, sess))
        for c_id, d, sess in att_sessions:
            if c_id in class_sessions_map:
                class_sessions_map[c_id].add((d, sess))
            all_school_sessions.add((d, sess))

        if selected_class:
            summary_stats['total_sessions_held'] = len(class_sessions_map.get(selected_class.id, set()))
        else:
            summary_stats['total_sessions_held'] = len(all_school_sessions)

        # 2. Bulk fetch all student attendance records in this range
        raw_atts = StudentAttendance.objects.filter(
            classroom__in=target_classes,
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

            cls_held = len(class_sessions_map.get(student.classroom_id, set()))

            # If sessions were recorded, present is total held minus absent and permission
            if cls_held > 0:
                present_cnt = max(0, cls_held - absent_cnt - perm_cnt)
                rate = round((present_cnt / cls_held) * 100, 1)
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
                'total': cls_held,
                'rate': rate,
            })

        if summary_stats['total_students'] > 0:
            summary_stats['avg_attendance_rate'] = round(total_rate_accum / summary_stats['total_students'], 1)

    is_admin = request.user.is_superuser or getattr(request.user, 'role', '') == 'ADMIN'

    # Admin export to Excel based on current filter & view
    if request.GET.get('export') == 'excel':
        if not is_admin:
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden("លោកអ្នកមិនមានសិទ្ធិទាញយករបាយការណ៍ជា Excel ឡើយ។")
        return export_student_attendance_report_excel(
            report_data=report_data,
            summary_stats=summary_stats,
            selected_class=selected_class,
            selected_grade_level=str(grade_level) if grade_level else '',
            target_classes_count=target_classes.count(),
            filter_label=filter_label,
            active_year=active_year,
            search_query=search_query,
        )

    return render(request, 'attendance/attendance_report.html', {
        'classrooms': base_classrooms,
        'filtered_classrooms': filtered_classrooms,
        'available_grades': available_grades,
        'selected_grade_level': str(grade_level) if grade_level else '',
        'selected_class_id': selected_class_id,
        'selected_class': selected_class,
        'target_classes_count': target_classes.count(),
        'search_query': search_query,
        'filter_type': filter_type,
        'filter_label': filter_label,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'week_date_str': week_date_str,
        'month_str': month_str,
        'report_data': report_data,
        'summary_stats': summary_stats,
        'active_year': active_year,
        'is_admin': is_admin,
    })


# ---------------------------------------------------------------------------
# Cumulative Multi-Month, Semester & Annual Student Absence Matrix
# ---------------------------------------------------------------------------

def get_academic_year_months_catalog(academic_year):
    """
    Generates an ordered list of academic month descriptors spanning the academic year.
    Semester 1: Months 9, 10, 11, 12, 1, 2 (កញ្ញា ដល់ កុម្ភៈ)
    Semester 2: Months 3, 4, 5, 6, 7, 8 (មីនា ដល់ កក្កដា/សីហា)
    """
    if not academic_year or not academic_year.start_date or not academic_year.end_date:
        start_d = date(2026, 9, 1)
        end_d = date(2027, 7, 31)
    else:
        start_d = academic_year.start_date
        end_d = academic_year.end_date

    kh_month_names = {
        1: 'មករា', 2: 'កុម្ភៈ', 3: 'មីនា', 4: 'មេសា',
        5: 'ឧសភា', 6: 'មិថុនា', 7: 'កក្កដា', 8: 'សីហា',
        9: 'កញ្ញា', 10: 'តុលា', 11: 'វិច្ឆិកា', 12: 'ធ្នូ',
    }
    en_month_names = {
        1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr',
        5: 'May', 6: 'Jun', 7: 'Jul', 8: 'Aug',
        9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec',
    }

    months = []
    curr_y, curr_m = start_d.year, start_d.month
    end_y, end_m = end_d.year, end_d.month

    while (curr_y < end_y) or (curr_y == end_y and curr_m <= end_m):
        sem = 1 if curr_m in [9, 10, 11, 12, 1, 2] else 2
        m_kh = kh_month_names.get(curr_m, str(curr_m))
        m_en = en_month_names.get(curr_m, str(curr_m))
        str_key = f"{curr_y}_{curr_m:02d}"
        months.append({
            'year': curr_y,
            'month': curr_m,
            'key': (curr_y, curr_m),
            'str_key': str_key,
            'name_kh': m_kh,
            'name_en': m_en,
            'short_label': m_kh,
            'full_label': f"{m_kh} {curr_y}",
            'semester': sem,
        })
        curr_m += 1
        if curr_m > 12:
            curr_m = 1
            curr_y += 1

    sem1_months = [m for m in months if m['semester'] == 1]
    sem2_months = [m for m in months if m['semester'] == 2]

    return {
        'all_months': months,
        'sem1_months': sem1_months,
        'sem2_months': sem2_months,
    }


def export_student_semester_annual_attendance_report_excel(
    view_scope,
    absence_type,
    unit,
    all_months,
    sem1_months,
    sem2_months,
    class_groups,
    school_total,
    student_rows,
    roster_total,
    active_year,
    selected_grade_level,
    selected_class
):
    """Generates a professional Excel spreadsheet with dual-level group headers for Semester & Annual Absences."""
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter
    from django.http import HttpResponse
    from apps.accounts.models import SchoolProfile

    try:
        school_info = SchoolProfile.get_settings()
        school_name = school_info.name_kh if school_info and school_info.name_kh else "ប្រព័ន្ធគ្រប់គ្រងសាលារៀន (SchoolSM)"
    except Exception:
        school_name = "ប្រព័ន្ធគ្រប់គ្រងសាលារៀន (SchoolSM)"

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "អវត្តមានខែ-ឆមាស-ប្រចាំឆ្នាំ"
    ws.views.sheetView[0].showGridLines = True

    font_title = Font(name='Kantumruy Pro', size=14, bold=True, color='1E3A8A')
    font_subtitle = Font(name='Kantumruy Pro', size=11, bold=True, color='1E293B')
    font_meta = Font(name='Kantumruy Pro', size=10, italic=False, color='475569')
    font_group_header = Font(name='Kantumruy Pro', size=10, bold=True, color='FFFFFF')
    font_sub_header = Font(name='Kantumruy Pro', size=9, bold=True, color='1E293B')
    font_data = Font(name='Kantumruy Pro', size=9)
    font_data_bold = Font(name='Kantumruy Pro', size=9, bold=True)
    font_danger = Font(name='Kantumruy Pro', size=9, bold=True, color='DC2626')

    fill_group_info = PatternFill(start_color='1E3A8A', end_color='1E3A8A', fill_type='solid')
    fill_group_sem1 = PatternFill(start_color='1D4ED8', end_color='1D4ED8', fill_type='solid')
    fill_group_sem2 = PatternFill(start_color='0D9488', end_color='0D9488', fill_type='solid')
    fill_group_annual = PatternFill(start_color='B45309', end_color='B45309', fill_type='solid')
    fill_sub_hdr = PatternFill(start_color='F1F5F9', end_color='F1F5F9', fill_type='solid')
    fill_zebra = PatternFill(start_color='F8FAFC', end_color='F8FAFC', fill_type='solid')
    fill_subtotal = PatternFill(start_color='E2E8F0', end_color='E2E8F0', fill_type='solid')
    fill_total = PatternFill(start_color='CBD5E1', end_color='CBD5E1', fill_type='solid')

    border_thin = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )
    border_double = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='double', color='0F172A')
    )

    align_center = Alignment(horizontal='center', vertical='center', wrap_text=True)
    align_left = Alignment(horizontal='left', vertical='center')

    num_info_cols = 4
    s1_start_col = num_info_cols + 1
    s1_end_col = s1_start_col + len(sem1_months)
    s2_start_col = s1_end_col + 1
    s2_end_col = s2_start_col + len(sem2_months)
    annual_col = s2_end_col + 1
    total_cols = annual_col
    last_col_letter = get_column_letter(total_cols)

    # Row 1: School Name
    ws.merge_cells(f'A1:{last_col_letter}1')
    ws['A1'] = school_name
    ws['A1'].font = font_title
    ws['A1'].alignment = align_center
    ws.row_dimensions[1].height = 28

    # Row 2: Title
    ws.merge_cells(f'A2:{last_col_letter}2')
    scope_title_km = "សរុបតាមកម្រិតថ្នាក់ & ថ្នាក់នីមួយៗ" if view_scope == 'CLASS_SUMMARY' else f"សរុបសិស្សម្នាក់ៗ ({selected_class.name if selected_class else 'ថ្នាក់រៀន'})"
    ws['A2'] = f"របាយការណ៍អវត្តមានសិស្សតាមខែ ឆមាស & ប្រចាំឆ្នាំ ({scope_title_km})"
    ws['A2'].font = font_subtitle
    ws['A2'].alignment = align_center
    ws.row_dimensions[2].height = 22

    # Row 3: Meta
    unit_label = "គិតជាថ្ងៃ (0.5 ថ្ងៃ/វេន)" if unit == 'DAYS' else "គិតជាចំនួនដង/វេន"
    type_label_map = {'TOTAL': 'សរុប (ច្បាប់+ឥតច្បាប់)', 'UNEXCUSED': 'អវត្តមានឥតច្បាប់', 'PERMISSION': 'សុំច្បាប់', 'DUAL': 'បង្ហាញទាំងពីរ (ច្បាប់ / ឥតច្បាប់)'}
    type_label = type_label_map.get(absence_type, 'សរុប')
    ay_label = active_year.name if active_year else '-'
    meta_str = f"ប្រភេទអវត្តមាន៖ {type_label}  |  ខ្នាតរាប់៖ {unit_label}  |  ឆ្នាំសិក្សា៖ {ay_label}"
    ws.merge_cells(f'A3:{last_col_letter}3')
    ws['A3'] = meta_str
    ws['A3'].font = font_meta
    ws['A3'].alignment = align_center
    ws.row_dimensions[3].height = 20

    ws.row_dimensions[4].height = 8

    # Row 5: Group Headers (Level 1)
    ws.merge_cells(f'A5:{get_column_letter(num_info_cols)}5')
    ws['A5'] = "ព័ត៌មានទូទៅ (GENERAL INFO)"
    ws['A5'].font = font_group_header
    ws['A5'].fill = fill_group_info
    ws['A5'].alignment = align_center
    for c in range(1, num_info_cols + 1):
        ws.cell(row=5, column=c).border = border_thin
        ws.cell(row=5, column=c).fill = fill_group_info

    ws.merge_cells(f'{get_column_letter(s1_start_col)}5:{get_column_letter(s1_end_col)}5')
    cell_s1 = ws.cell(row=5, column=s1_start_col, value="ឆមាសទី ១ (SEMESTER 1: យកខែក្នុងឆមាសទី១ បូកបញ្ចូលគ្នា)")
    cell_s1.font = font_group_header
    cell_s1.fill = fill_group_sem1
    cell_s1.alignment = align_center
    for c in range(s1_start_col, s1_end_col + 1):
        ws.cell(row=5, column=c).border = border_thin
        ws.cell(row=5, column=c).fill = fill_group_sem1

    ws.merge_cells(f'{get_column_letter(s2_start_col)}5:{get_column_letter(s2_end_col)}5')
    cell_s2 = ws.cell(row=5, column=s2_start_col, value="ឆមាសទី ២ (SEMESTER 2: យកខែក្នុងឆមាសទី២ បូកបញ្ចូលគ្នា)")
    cell_s2.font = font_group_header
    cell_s2.fill = fill_group_sem2
    cell_s2.alignment = align_center
    for c in range(s2_start_col, s2_end_col + 1):
        ws.cell(row=5, column=c).border = border_thin
        ws.cell(row=5, column=c).fill = fill_group_sem2

    cell_ann = ws.cell(row=5, column=annual_col, value="សរុបប្រចាំឆ្នាំ")
    cell_ann.font = font_group_header
    cell_ann.fill = fill_group_annual
    cell_ann.alignment = align_center
    cell_ann.border = border_thin
    ws.row_dimensions[5].height = 26

    # Row 6: Sub Headers (Level 2)
    if view_scope == 'CLASS_SUMMARY':
        sub_headers = ["ល.រ", "កម្រិតថ្នាក់", "ថ្នាក់រៀន", "សិស្សសរុប"]
    else:
        sub_headers = ["ល.រ", "អត្តលេខសិស្ស", "គោត្តនាម និងនាម", "ភេទ"]

    for m in sem1_months:
        sub_headers.append(m['short_label'])
    sub_headers.append("សរុបឆមាស១")

    for m in sem2_months:
        sub_headers.append(m['short_label'])
    sub_headers.append("សរុបឆមាស២")

    sub_headers.append("សរុបប្រចាំឆ្នាំ (S1+S2)")

    ws.row_dimensions[6].height = 26
    for col_idx, h_name in enumerate(sub_headers, 1):
        c = ws.cell(row=6, column=col_idx, value=h_name)
        c.font = font_sub_header
        c.fill = fill_sub_hdr
        c.alignment = align_center
        c.border = border_thin

    current_row = 7

    # Data Rows
    if view_scope == 'CLASS_SUMMARY':
        overall_idx = 1
        for grp in class_groups:
            for c_info in grp['classrooms']:
                row_vals = [
                    overall_idx,
                    f"ថ្នាក់ទី {c_info['grade_level']}",
                    c_info['classroom_name'],
                    c_info['student_count'],
                ]
                for cell_item in c_info['sem1_cells']:
                    row_vals.append(cell_item['display'])
                row_vals.append(c_info['sem1_total_cell']['display'])

                for cell_item in c_info['sem2_cells']:
                    row_vals.append(cell_item['display'])
                row_vals.append(c_info['sem2_total_cell']['display'])

                row_vals.append(c_info['annual_total_cell']['display'])

                ws.row_dimensions[current_row].height = 20
                for c_idx, val in enumerate(row_vals, 1):
                    cell = ws.cell(row=current_row, column=c_idx, value=val)
                    cell.font = font_data
                    cell.border = border_thin
                    cell.alignment = align_center if c_idx not in [3] else align_left
                    if c_idx > num_info_cols and str(val) not in ['0', '0.0', '0 / 0', '0/0', '-']:
                        cell.font = font_danger
                overall_idx += 1
                current_row += 1

            # Subtotal row for Grade Level
            sub_vals = [
                "",
                f"សរុប {grp['grade_name']}",
                f"{len(grp['classrooms'])} ថ្នាក់",
                grp['subtotal']['student_count'],
            ]
            for cell_item in grp['subtotal']['sem1_cells']:
                sub_vals.append(cell_item['display'])
            sub_vals.append(grp['subtotal']['sem1_total_cell']['display'])

            for cell_item in grp['subtotal']['sem2_cells']:
                sub_vals.append(cell_item['display'])
            sub_vals.append(grp['subtotal']['sem2_total_cell']['display'])

            sub_vals.append(grp['subtotal']['annual_total_cell']['display'])

            ws.row_dimensions[current_row].height = 22
            for c_idx, val in enumerate(sub_vals, 1):
                cell = ws.cell(row=current_row, column=c_idx, value=val)
                cell.font = font_data_bold
                cell.fill = fill_subtotal
                cell.border = border_thin
                cell.alignment = align_center if c_idx not in [2] else align_left
                if c_idx > num_info_cols and str(val) not in ['0', '0.0', '0 / 0', '0/0', '-']:
                    cell.font = font_danger
            current_row += 1

        # Grand School Total Row
        grand_vals = [
            "",
            "សរុបរួមទូទាំងសាលា",
            f"{school_total['classrooms_count']} ថ្នាក់",
            school_total['student_count'],
        ]
        for cell_item in school_total['sem1_cells']:
            grand_vals.append(cell_item['display'])
        grand_vals.append(school_total['sem1_total_cell']['display'])

        for cell_item in school_total['sem2_cells']:
            grand_vals.append(cell_item['display'])
        grand_vals.append(school_total['sem2_total_cell']['display'])

        grand_vals.append(school_total['annual_total_cell']['display'])

        ws.row_dimensions[current_row].height = 24
        for c_idx, val in enumerate(grand_vals, 1):
            cell = ws.cell(row=current_row, column=c_idx, value=val)
            cell.font = font_data_bold
            cell.fill = fill_total
            cell.border = border_double
            cell.alignment = align_center if c_idx not in [2] else align_left
            if c_idx > num_info_cols and str(val) not in ['0', '0.0', '0 / 0', '0/0', '-']:
                cell.font = font_danger
        current_row += 1

    else:
        # STUDENT_ROSTER Mode
        for idx, stu_row in enumerate(student_rows, 1):
            stu = stu_row['student']
            gender_km = 'ស្រី' if getattr(stu, 'gender', '') == 'F' else 'ប្រុស'
            row_vals = [
                idx,
                stu.student_id,
                stu.khmer_name,
                gender_km,
            ]
            for cell_item in stu_row['sem1_cells']:
                row_vals.append(cell_item['display'])
            row_vals.append(stu_row['sem1_total_cell']['display'])

            for cell_item in stu_row['sem2_cells']:
                row_vals.append(cell_item['display'])
            row_vals.append(stu_row['sem2_total_cell']['display'])

            row_vals.append(stu_row['annual_total_cell']['display'])

            ws.row_dimensions[current_row].height = 20
            is_even = (idx % 2 == 0)

            for c_idx, val in enumerate(row_vals, 1):
                cell = ws.cell(row=current_row, column=c_idx, value=val)
                cell.font = font_data
                cell.border = border_thin
                cell.alignment = align_center if c_idx not in [3] else align_left
                if is_even:
                    cell.fill = fill_zebra
                if c_idx > num_info_cols and str(val) not in ['0', '0.0', '0 / 0', '0/0', '-']:
                    cell.font = font_danger
            current_row += 1

        # Roster Total Row
        r_vals = [
            "",
            "សរុបរួមប្រចាំថ្នាក់",
            f"{len(student_rows)} នាក់",
            "",
        ]
        for cell_item in roster_total['sem1_cells']:
            r_vals.append(cell_item['display'])
        r_vals.append(roster_total['sem1_total_cell']['display'])

        for cell_item in roster_total['sem2_cells']:
            r_vals.append(cell_item['display'])
        r_vals.append(roster_total['sem2_total_cell']['display'])

        r_vals.append(roster_total['annual_total_cell']['display'])

        ws.row_dimensions[current_row].height = 24
        for c_idx, val in enumerate(r_vals, 1):
            cell = ws.cell(row=current_row, column=c_idx, value=val)
            cell.font = font_data_bold
            cell.fill = fill_total
            cell.border = border_double
            cell.alignment = align_center if c_idx not in [2] else align_left
            if c_idx > num_info_cols and str(val) not in ['0', '0.0', '0 / 0', '0/0', '-']:
                cell.font = font_danger
        current_row += 1

    ws.column_dimensions['A'].width = 8
    ws.column_dimensions['B'].width = 16
    ws.column_dimensions['C'].width = 22
    ws.column_dimensions['D'].width = 12

    for c in range(s1_start_col, annual_col + 1):
        col_l = get_column_letter(c)
        if c == s1_end_col or c == s2_end_col:
            ws.column_dimensions[col_l].width = 14
        elif c == annual_col:
            ws.column_dimensions[col_l].width = 16
        else:
            ws.column_dimensions[col_l].width = 11

    filename = f"Student_Semester_Annual_Absences_{date.today().strftime('%Y%m%d')}.xlsx"
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


@login_required
@role_required(['ADMIN', 'TEACHER'])
def student_semester_annual_attendance_report(request):
    """
    Cumulative Student Absence Matrix:
    - Grouped by Grade Level & Classroom (សរុបតាមកម្រិតថ្នាក់/ថ្នាក់នីមួយៗ)
    - By Each Academic Month (តាមខែនីមួយៗ)
    - By Semester (ប្រចាំឆមាសនីមួយៗ: ឆមាសទី១ និង ឆមាសទី២ ដោយយកតាមខែក្នុងឆមាសបូកបញ្ចូលគ្នា)
    - By Academic Year (ប្រចាំឆ្នាំ: ឆមាសទី១ + ឆមាសទី២)
    - Fully downloadable as Excel for Admin according to currently viewed filters.
    """
    active_year = get_active_academic_year(request)
    months_catalog = get_academic_year_months_catalog(active_year)
    all_months = months_catalog['all_months']
    sem1_months = months_catalog['sem1_months']
    sem2_months = months_catalog['sem2_months']

    grade_level = request.GET.get('grade_level', '').strip()
    selected_class_id = request.GET.get('classroom', '').strip()
    view_scope = request.GET.get('view_scope', '').strip() or request.GET.get('scope', '').strip()
    absence_type = request.GET.get('absence_type', 'TOTAL').strip().upper()
    unit = request.GET.get('unit', 'SESSIONS').strip().upper()
    search_query = request.GET.get('q', '').strip()

    if not view_scope:
        view_scope = 'STUDENT_ROSTER' if (selected_class_id and selected_class_id != 'ALL') else 'CLASS_SUMMARY'

    base_classrooms = Classroom.objects.filter(academic_year=active_year).order_by('grade_level', 'code') if active_year else Classroom.objects.all().order_by('grade_level', 'code')

    if getattr(request.user, 'role', None) == 'TEACHER':
        from apps.academics.utils import get_teacher_allowed_classroom_ids
        allowed_cls_ids = get_teacher_allowed_classroom_ids(request.user)
        base_classrooms = base_classrooms.filter(id__in=allowed_cls_ids)

    available_grades = sorted(list(set(base_classrooms.values_list('grade_level', flat=True).distinct())))

    filtered_classrooms = base_classrooms
    if grade_level and grade_level != 'ALL':
        try:
            gl_int = int(grade_level)
            filtered_classrooms = base_classrooms.filter(grade_level=gl_int)
        except ValueError:
            pass

    if selected_class_id and selected_class_id != 'ALL':
        target_classes = filtered_classrooms.filter(id=selected_class_id)
        if not target_classes.exists():
            target_classes = base_classrooms.filter(id=selected_class_id)
            if target_classes.exists():
                c_grade = target_classes.first().grade_level
                grade_level = str(c_grade)
                filtered_classrooms = base_classrooms.filter(grade_level=c_grade)
            else:
                target_classes = filtered_classrooms
                selected_class_id = 'ALL'
    else:
        selected_class_id = 'ALL'
        target_classes = filtered_classrooms

    selected_class = target_classes.first() if (selected_class_id != 'ALL' and target_classes.count() == 1) else None

    # Fetch distinct attendance records
    start_d = active_year.start_date if active_year and active_year.start_date else date(2026, 9, 1)
    end_d = active_year.end_date if active_year and active_year.end_date else date(2027, 7, 31)

    raw_records = list(StudentAttendance.objects.filter(
        classroom__in=target_classes,
        date__range=(start_d, end_d),
        status__in=[StudentAttendance.Status.ABSENT, StudentAttendance.Status.PERMISSION]
    ).order_by().values_list('classroom_id', 'student_id', 'date', 'session', 'status').distinct())

    session_map = {}
    for cls_id, stu_id, d, sess, st in raw_records:
        key = (stu_id, d, sess)
        if key not in session_map or st == StudentAttendance.Status.ABSENT:
            session_map[key] = (cls_id, st)

    mult = 0.5 if unit == 'DAYS' else 1.0

    student_att = {}
    class_att = {}

    for (stu_id, d, sess), (cls_id, st) in session_map.items():
        y_m = (d.year, d.month)
        if stu_id not in student_att:
            student_att[stu_id] = {}
        if y_m not in student_att[stu_id]:
            student_att[stu_id][y_m] = {'unexcused': 0.0, 'permission': 0.0}

        if cls_id not in class_att:
            class_att[cls_id] = {}
        if y_m not in class_att[cls_id]:
            class_att[cls_id][y_m] = {'unexcused': 0.0, 'permission': 0.0}

        if st == StudentAttendance.Status.ABSENT:
            student_att[stu_id][y_m]['unexcused'] += mult
            class_att[cls_id][y_m]['unexcused'] += mult
        elif st == StudentAttendance.Status.PERMISSION:
            student_att[stu_id][y_m]['permission'] += mult
            class_att[cls_id][y_m]['permission'] += mult

    def make_cell_val(unexcused, permission):
        u = unexcused
        p = permission
        tot = u + p
        if absence_type == 'UNEXCUSED':
            num = u
            disp = f"{round(num, 1)}" if isinstance(num, float) and num % 1 != 0 else f"{int(num)}"
        elif absence_type == 'PERMISSION':
            num = p
            disp = f"{round(num, 1)}" if isinstance(num, float) and num % 1 != 0 else f"{int(num)}"
        elif absence_type == 'DUAL':
            num = tot
            p_s = f"{round(p, 1)}" if isinstance(p, float) and p % 1 != 0 else f"{int(p)}"
            u_s = f"{round(u, 1)}" if isinstance(u, float) and u % 1 != 0 else f"{int(u)}"
            disp = f"{p_s} / {u_s}"
        else: # TOTAL
            num = tot
            disp = f"{round(num, 1)}" if isinstance(num, float) and num % 1 != 0 else f"{int(num)}"

        return {
            'unexcused': u,
            'permission': p,
            'total': tot,
            'num': num,
            'display': disp,
            'is_positive': (num > 0),
        }

    def compute_cells_bundle(data_map):
        sem1_cells = []
        sem2_cells = []
        s1_u, s1_p = 0.0, 0.0
        s2_u, s2_p = 0.0, 0.0

        for m in sem1_months:
            rec = data_map.get(m['key'], {'unexcused': 0.0, 'permission': 0.0})
            u = rec['unexcused']
            p = rec['permission']
            s1_u += u
            s1_p += p
            sem1_cells.append(make_cell_val(u, p))

        for m in sem2_months:
            rec = data_map.get(m['key'], {'unexcused': 0.0, 'permission': 0.0})
            u = rec['unexcused']
            p = rec['permission']
            s2_u += u
            s2_p += p
            sem2_cells.append(make_cell_val(u, p))

        ann_u = s1_u + s2_u
        ann_p = s1_p + s2_p

        return {
            'sem1_cells': sem1_cells,
            'sem1_total_cell': make_cell_val(s1_u, s1_p),
            'sem2_cells': sem2_cells,
            'sem2_total_cell': make_cell_val(s2_u, s2_p),
            'annual_total_cell': make_cell_val(ann_u, ann_p),
            'raw_s1': {'unexcused': s1_u, 'permission': s1_p, 'total': s1_u + s1_p},
            'raw_s2': {'unexcused': s2_u, 'permission': s2_p, 'total': s2_u + s2_p},
            'raw_annual': {'unexcused': ann_u, 'permission': ann_p, 'total': ann_u + ann_p},
        }

    # 1. Classroom & Grade Summary
    class_groups = []
    grade_map = {}

    school_total_raw = {
        'classrooms_count': target_classes.count(),
        'student_count': 0,
        'months': {m['key']: {'unexcused': 0.0, 'permission': 0.0} for m in all_months},
    }

    active_students_qs = Student.objects.filter(classroom__in=target_classes, status='ACTIVE')
    student_class_counts = dict(active_students_qs.values('classroom_id').annotate(cnt=Count('id')).values_list('classroom_id', 'cnt'))

    for c in target_classes:
        c_att = class_att.get(c.id, {})
        bundle = compute_cells_bundle(c_att)
        stu_cnt = student_class_counts.get(c.id, 0)
        school_total_raw['student_count'] += stu_cnt

        c_data = {
            'classroom': c,
            'classroom_name': c.name,
            'grade_level': c.grade_level,
            'student_count': stu_cnt,
            'sem1_cells': bundle['sem1_cells'],
            'sem1_total_cell': bundle['sem1_total_cell'],
            'sem2_cells': bundle['sem2_cells'],
            'sem2_total_cell': bundle['sem2_total_cell'],
            'annual_total_cell': bundle['annual_total_cell'],
        }

        gl = c.grade_level
        if gl not in grade_map:
            grade_map[gl] = {
                'grade_level': gl,
                'grade_name': f"កម្រិតថ្នាក់ទី {gl}",
                'classrooms': [],
                'student_count': 0,
                'months': {m['key']: {'unexcused': 0.0, 'permission': 0.0} for m in all_months},
            }
        grade_map[gl]['classrooms'].append(c_data)
        grade_map[gl]['student_count'] += stu_cnt

        for m in all_months:
            m_key = m['key']
            rec = c_att.get(m_key, {'unexcused': 0.0, 'permission': 0.0})
            grade_map[gl]['months'][m_key]['unexcused'] += rec['unexcused']
            grade_map[gl]['months'][m_key]['permission'] += rec['permission']
            school_total_raw['months'][m_key]['unexcused'] += rec['unexcused']
            school_total_raw['months'][m_key]['permission'] += rec['permission']

    for gl in sorted(grade_map.keys()):
        grp = grade_map[gl]
        grp_bundle = compute_cells_bundle(grp['months'])
        grp['subtotal'] = {
            'student_count': grp['student_count'],
            'sem1_cells': grp_bundle['sem1_cells'],
            'sem1_total_cell': grp_bundle['sem1_total_cell'],
            'sem2_cells': grp_bundle['sem2_cells'],
            'sem2_total_cell': grp_bundle['sem2_total_cell'],
            'annual_total_cell': grp_bundle['annual_total_cell'],
        }
        class_groups.append(grp)

    school_bundle = compute_cells_bundle(school_total_raw['months'])
    school_total = {
        'classrooms_count': school_total_raw['classrooms_count'],
        'student_count': school_total_raw['student_count'],
        'sem1_cells': school_bundle['sem1_cells'],
        'sem1_total_cell': school_bundle['sem1_total_cell'],
        'sem2_cells': school_bundle['sem2_cells'],
        'sem2_total_cell': school_bundle['sem2_total_cell'],
        'annual_total_cell': school_bundle['annual_total_cell'],
    }

    # 2. Student Individual Roster
    student_rows = []
    roster_raw = {
        'student_count': 0,
        'months': {m['key']: {'unexcused': 0.0, 'permission': 0.0} for m in all_months},
    }

    if view_scope == 'STUDENT_ROSTER':
        students_qs = Student.objects.filter(classroom__in=target_classes, status='ACTIVE')\
                                     .select_related('classroom')\
                                     .order_by('classroom__grade_level', 'classroom__name', 'student_id')
        if search_query:
            students_qs = students_qs.filter(
                Q(student_id__icontains=search_query) |
                Q(khmer_name__icontains=search_query) |
                Q(latin_name__icontains=search_query)
            )

        students = list(students_qs)
        roster_raw['student_count'] = len(students)

        for s in students:
            s_att = student_att.get(s.id, {})
            bundle = compute_cells_bundle(s_att)

            student_rows.append({
                'student': s,
                'sem1_cells': bundle['sem1_cells'],
                'sem1_total_cell': bundle['sem1_total_cell'],
                'sem2_cells': bundle['sem2_cells'],
                'sem2_total_cell': bundle['sem2_total_cell'],
                'annual_total_cell': bundle['annual_total_cell'],
            })

            for m in all_months:
                m_key = m['key']
                rec = s_att.get(m_key, {'unexcused': 0.0, 'permission': 0.0})
                roster_raw['months'][m_key]['unexcused'] += rec['unexcused']
                roster_raw['months'][m_key]['permission'] += rec['permission']

    roster_bundle = compute_cells_bundle(roster_raw['months'])
    roster_total = {
        'student_count': roster_raw['student_count'],
        'sem1_cells': roster_bundle['sem1_cells'],
        'sem1_total_cell': roster_bundle['sem1_total_cell'],
        'sem2_cells': roster_bundle['sem2_cells'],
        'sem2_total_cell': roster_bundle['sem2_total_cell'],
        'annual_total_cell': roster_bundle['annual_total_cell'],
    }

    is_admin = request.user.is_superuser or getattr(request.user, 'role', '') == 'ADMIN'

    # Excel Export
    if request.GET.get('export') == 'excel':
        if not is_admin:
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden("លោកអ្នកមិនមានសិទ្ធិទាញយករបាយការណ៍ជា Excel ឡើយ។")
        return export_student_semester_annual_attendance_report_excel(
            view_scope=view_scope,
            absence_type=absence_type,
            unit=unit,
            all_months=all_months,
            sem1_months=sem1_months,
            sem2_months=sem2_months,
            class_groups=class_groups,
            school_total=school_total,
            student_rows=student_rows,
            roster_total=roster_total,
            active_year=active_year,
            selected_grade_level=str(grade_level) if grade_level else '',
            selected_class=selected_class,
        )

    # Top KPI Metrics
    summary_kpis = {
        'total_students': school_total['student_count'] if view_scope == 'CLASS_SUMMARY' else roster_total['student_count'],
        'sem1_absences': school_total['sem1_total_cell']['display'] if view_scope == 'CLASS_SUMMARY' else roster_total['sem1_total_cell']['display'],
        'sem2_absences': school_total['sem2_total_cell']['display'] if view_scope == 'CLASS_SUMMARY' else roster_total['sem2_total_cell']['display'],
        'annual_absences': school_total['annual_total_cell']['display'] if view_scope == 'CLASS_SUMMARY' else roster_total['annual_total_cell']['display'],
    }

    return render(request, 'attendance/student_semester_annual_attendance_report.html', {
        'active_year': active_year,
        'all_months': all_months,
        'sem1_months': sem1_months,
        'sem2_months': sem2_months,
        'sem1_count': len(sem1_months),
        'sem2_count': len(sem2_months),
        'classrooms': base_classrooms,
        'filtered_classrooms': filtered_classrooms,
        'available_grades': available_grades,
        'selected_grade_level': str(grade_level) if grade_level else '',
        'selected_class_id': selected_class_id,
        'selected_class': selected_class,
        'view_scope': view_scope,
        'absence_type': absence_type,
        'unit': unit,
        'search_query': search_query,
        'class_groups': class_groups,
        'school_total': school_total,
        'student_rows': student_rows,
        'roster_total': roster_total,
        'summary_kpis': summary_kpis,
        'is_admin': is_admin,
    })



@login_required
@role_required(['ADMIN', 'TEACHER'])
def at_risk_attendance_view(request):
    """
    At-Risk Attendance & Chronic Absentee Warning Tracker.
    Calculates absences based on academic sessions (1 session = 1 time = 0.5 day).
    Allows Admin & Teachers to filter students by custom absence thresholds in either DAYS (ថ្ងៃ) or TIMES (ចំនួនដង)
    and by absence type (Unexcused, Excused, Total).
    Strictly isolated per Academic Year.
    """
    active_year = get_active_academic_year(request)
    
    # Filter parameters
    unit = request.GET.get('unit', 'DAYS').upper().strip() # 'DAYS' or 'TIMES'
    min_str = request.GET.get('min_absences', request.GET.get('threshold', '1' if unit == 'DAYS' else '2')).strip()
    max_str = request.GET.get('max_absences', '').strip()
    absence_type = request.GET.get('absence_type', 'UNEXCUSED').strip() # 'UNEXCUSED', 'PERMISSION', 'TOTAL'
    class_id = request.GET.get('classroom', '').strip()

    try:
        min_val = float(min_str) if min_str else (1.0 if unit == 'DAYS' else 2.0)
    except Exception:
        min_val = 1.0 if unit == 'DAYS' else 2.0

    try:
        max_val = float(max_str) if (max_str and max_str.replace('.', '', 1).isdigit()) else None
    except Exception:
        max_val = None

    students = Student.objects.filter(status='ACTIVE').select_related('classroom')
    if active_year:
        students = students.filter(Q(academic_year=active_year) | Q(classroom__academic_year=active_year))
    if class_id:
        students = students.filter(classroom_id=class_id)

    # Pre-aggregate distinct (date, session) pairs per student to eliminate N+1 queries and prevent worker timeouts on PostgreSQL
    base_att_qs = StudentAttendance.objects.filter(student__in=students)

    absent_counts = {}
    for stu_id, d, sess in base_att_qs.filter(status=StudentAttendance.Status.ABSENT).order_by().values_list('student_id', 'date', 'session').distinct():
        absent_counts[stu_id] = absent_counts.get(stu_id, 0) + 1

    perm_counts = {}
    for stu_id, d, sess in base_att_qs.filter(status=StudentAttendance.Status.PERMISSION).order_by().values_list('student_id', 'date', 'session').distinct():
        perm_counts[stu_id] = perm_counts.get(stu_id, 0) + 1

    total_sessions_counts = {}
    for stu_id, d, sess in base_att_qs.order_by().values_list('student_id', 'date', 'session').distinct():
        total_sessions_counts[stu_id] = total_sessions_counts.get(stu_id, 0) + 1

    at_risk_list = []
    for s in students:
        absent_times = absent_counts.get(s.id, 0)
        absent_days = round(absent_times * 0.5, 1)

        perm_times = perm_counts.get(s.id, 0)
        perm_days = round(perm_times * 0.5, 1)

        total_absent_times = absent_times + perm_times
        total_absent_days = round(total_absent_times * 0.5, 1)

        total_sessions = total_sessions_counts.get(s.id, 0)
        total_days = round(total_sessions * 0.5, 1)

        # Determine target metric based on filter type and unit
        if absence_type == 'PERMISSION':
            target_metric = perm_days if unit == 'DAYS' else perm_times
            target_times = perm_times
            target_days = perm_days
        elif absence_type == 'TOTAL':
            target_metric = total_absent_days if unit == 'DAYS' else total_absent_times
            target_times = total_absent_times
            target_days = total_absent_days
        else: # UNEXCUSED
            target_metric = absent_days if unit == 'DAYS' else absent_times
            target_times = absent_times
            target_days = absent_days

        # Check range (min_val <= target_metric <= max_val)
        matches_min = target_metric >= min_val
        matches_max = (max_val is None) or (target_metric <= max_val)

        if matches_min and matches_max and target_times > 0:
            rate = round(((total_sessions - absent_times) / total_sessions) * 100, 1) if total_sessions > 0 else 100.0
            if absent_times >= 8 or total_absent_times >= 12: # >= 4 days absent
                risk_level = 'HIGH'
            elif absent_times >= 4 or total_absent_times >= 6: # >= 2 days absent
                risk_level = 'MEDIUM'
            else:
                risk_level = 'LOW'

            at_risk_list.append({
                'student': s,
                'absent_times': absent_times,
                'absent_days': absent_days,
                'perm_times': perm_times,
                'perm_days': perm_days,
                'total_absent_times': total_absent_times,
                'total_absent_days': total_absent_days,
                'target_times': target_times,
                'target_days': target_days,
                'target_metric': target_metric,
                'total_sessions': total_sessions,
                'total_days': total_days,
                'attendance_rate': rate,
                'risk_level': risk_level,
            })

    # Sort descending by target metric
    at_risk_list.sort(key=lambda x: (x['target_metric'], x['absent_times']), reverse=True)

    if request.method == 'POST' and 'send_warning' in request.POST:
        student_id = request.POST.get('student_id')
        stu = get_object_or_404(Student, pk=student_id)
        absent_days_str = request.POST.get('absent_days', '៣')
        absent_times_str = request.POST.get('absent_times', '')
        class_name = stu.classroom.name if stu.classroom else '-'
        
        detail_txt = f"{absent_days_str} ថ្ងៃ"
        if absent_times_str:
            detail_txt += f" ({absent_times_str} ដង/វេន)"

        msg = (
            f"🚨 *លិខិតអញ្ជើញ & សេចក្តីជូនដំណឹងបន្ទាន់អំពីអវត្តមានសិស្ស*\n\n"
            f"សូមគោរពជម្រាបជូនលោក/លោកស្រីអាណាព្យាបាលសិស្ស *{stu.khmer_name}* (ថ្នាក់៖ {class_name})!\n\n"
            f"សាលាជម្រាបជូនថាសិស្សបានអវត្តមានចំនួន *{detail_txt}* ដែលប្រឈមនឹងការធ្លាក់ការសិក្សា ឬលុបឈ្មោះ។ "
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
        return redirect(f"/attendance/at-risk/?classroom={class_id}&unit={unit}&min_absences={min_str}&max_absences={max_str}&absence_type={absence_type}")

    classrooms = Classroom.objects.filter(academic_year=active_year).order_by('grade_level', 'code') if active_year else Classroom.objects.all().order_by('grade_level', 'code')

    is_admin = request.user.is_superuser or getattr(request.user, 'role', '') == 'ADMIN'

    return render(request, 'attendance/at_risk_attendance.html', {
        'at_risk_list': at_risk_list,
        'classrooms': classrooms,
        'selected_class': class_id,
        'unit': unit,
        'min_absences': min_str,
        'max_absences': max_str,
        'absence_type': absence_type,
        'active_year': active_year,
        'total_found': len(at_risk_list),
        'exam_reasons': Student.ExamExclusionReason.choices,
        'is_admin': is_admin,
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

    flag_path = Path(settings.BASE_DIR) / 'maintenance.flag'
    flag_exists = flag_path.exists()
    if flag_exists != att_settings.is_maintenance_mode:
        att_settings.is_maintenance_mode = flag_exists
        att_settings.save(update_fields=['is_maintenance_mode'])

    if request.method == 'POST':
        action = request.POST.get('action')

        # 1. Save Attendance & Telegram Rules
        if action == 'save_rules':
            grace_mins = request.POST.get('submission_grace_minutes', '30')
            mgmt_chat_id = request.POST.get('management_chat_id', '').strip()
            homeroom_group_id = request.POST.get('homeroom_group_chat_id', '').strip()
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
            att_settings.homeroom_group_chat_id = homeroom_group_id or None
            att_settings.custom_dispatch_groups = custom_groups or None
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
            att_settings.enable_assembly_morning = request.POST.get('enable_assembly_morning') == 'on'
            att_settings.assembly_morning_start = AttendanceSetting._parse_time(request.POST.get('assembly_morning_start'), dtime(6, 30))
            att_settings.assembly_morning_end = AttendanceSetting._parse_time(request.POST.get('assembly_morning_end'), dtime(6, 50))
            att_settings.enable_assembly_afternoon = request.POST.get('enable_assembly_afternoon') == 'on'
            att_settings.assembly_afternoon_start = AttendanceSetting._parse_time(request.POST.get('assembly_afternoon_start'), dtime(12, 30))
            att_settings.assembly_afternoon_end = AttendanceSetting._parse_time(request.POST.get('assembly_afternoon_end'), dtime(12, 50))
            att_settings.allow_all_teachers_assembly_recording = request.POST.get('allow_all_teachers_assembly_recording') == 'on'
            att_settings.allow_monitor_assembly_recording = request.POST.get('allow_monitor_assembly_recording') == 'on'
            att_settings.assembly_telegram_alert = request.POST.get('assembly_telegram_alert') == 'on'
            att_settings.assembly_alarm_enabled = request.POST.get('assembly_alarm_enabled') == 'on'
            att_settings.assembly_auto_alarm_enabled = request.POST.get('assembly_auto_alarm_enabled') == 'on'
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

            flag_path = Path(settings.BASE_DIR) / 'maintenance.flag'
            try:
                if is_maint:
                    flag_path.write_text('active\n', encoding='utf-8')
                else:
                    if flag_path.exists():
                        flag_path.unlink()
            except Exception:
                pass

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

        # 8. Immediate Daily Grade Student Absence Reports (Grades 7 to 12)
        elif action == 'dispatch_daily_grades_now':
            target_date_str = request.POST.get('target_date', date.today().strftime('%Y-%m-%d'))
            try:
                t_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
            except ValueError:
                t_date = date.today()
            res = send_daily_grade_student_absence_telegram(target_date=t_date)
            if res.get('success'):
                messages.success(request, f"🚀 {res.get('message')}")
            else:
                messages.error(request, f"⚠️ {res.get('message')}")
            return redirect('attendance_admin_hub')

        # 9. Immediate Daily Teacher Absence Report (Sorted Alphabetically from ក to អ)
        elif action == 'dispatch_daily_teachers_now':
            target_date_str = request.POST.get('target_date', date.today().strftime('%Y-%m-%d'))
            try:
                t_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
            except ValueError:
                t_date = date.today()
            res = send_daily_teacher_absence_telegram(target_date=t_date)
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
    session = request.POST.get('session')

    result = send_missing_teachers_telegram(
        target_date=t_date,
        period_number=period_num,
        session=session,
        custom_chat_id=custom_chat_id,
        sender_user=request.user
    )

    return JsonResponse(result)


# ---------------------------------------------------------------------------
# Morning Assembly / Flag Ceremony Student Attendance (វត្តមានពេលគោរពទង់ជាតិ)
# ---------------------------------------------------------------------------

@login_required
@role_required(['ADMIN', 'TEACHER', 'STUDENT'])
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
    m_start = att_settings.morning_start_time
    m_end = att_settings.morning_end_time
    a_start = att_settings.afternoon_start_time
    a_end = att_settings.afternoon_end_time

    if selected_session == 'MORNING':
        window_start = m_start
        window_end = m_end
        session_title = "ពេលព្រឹក (Morning Flag Ceremony)"
    else:
        window_start = a_start
        window_end = a_end
        session_title = "ពេលរសៀល (Afternoon Pre-Class Assembly)"

    if not isinstance(window_start, dtime):
        window_start = AttendanceSetting._parse_time(window_start, dtime(6, 30))
    if not isinstance(window_end, dtime):
        window_end = AttendanceSetting._parse_time(window_end, dtime(6, 50))

    # Day of Week, Session Enablement & Emergency Cancellation Check
    today_weekday_str = str(today_date.isoweekday()) # 1=Monday ... 7=Sunday
    is_active_day = today_weekday_str in (att_settings.assembly_active_days or ["1", "2", "3", "4", "5", "6"])
    is_cancelled_today = att_settings.is_assembly_disabled_today and (att_settings.assembly_disabled_date == today_date or not att_settings.assembly_disabled_date)
    
    session_disabled = False
    session_disabled_reason = ""
    if selected_session == 'MORNING' and not att_settings.enable_assembly_morning:
        session_disabled = True
        session_disabled_reason = "ការស្រង់វត្តមានពេលគោរពទង់ជាតិ (ពេលព្រឹក) ត្រូវបានបិទដំណើរការដោយគណៈគ្រប់គ្រងសាលា។"
    elif selected_session == 'AFTERNOON' and not att_settings.enable_assembly_afternoon:
        session_disabled = True
        session_disabled_reason = "ការស្រង់វត្តមានមុនម៉ោងចូលរៀន (ពេលរសៀល) ត្រូវបានបិទដំណើរការដោយគណៈគ្រប់គ្រងសាលា។"

    is_disabled_today = (not is_active_day) or is_cancelled_today or (not att_settings.enable_assembly_attendance) or session_disabled
    disabled_reason = ""
    if not att_settings.enable_assembly_attendance:
        disabled_reason = "ប្រព័ន្ធស្រង់វត្តមានពេលគោរពទង់ជាតិត្រូវបានបិទដំណើរការជាបណ្តោះអាសន្នដោយគណៈគ្រប់គ្រងសាលា។"
    elif is_cancelled_today:
        disabled_reason = att_settings.assembly_disabled_reason or "គណៈគ្រប់គ្រងសាលាបានសម្រេចផ្អាកការស្រង់វត្តមានពេលគោរពទង់ជាតិសម្រាប់ថ្ងៃនេះ។"
    elif not is_active_day:
        disabled_reason = "ថ្ងៃនេះមិនមែនជាថ្ងៃដែលត្រូវស្រង់វត្តមានពេលគោរពទង់ជាតិនោះឡើយ។"
    elif session_disabled:
        disabled_reason = session_disabled_reason

    is_admin_override = (user.role == 'ADMIN' or user.is_superuser)
    is_within_window = (window_start <= current_time <= window_end)

    # Calculate remaining minutes until window end
    remaining_minutes = 0
    if is_within_window:
        end_dt = datetime.combine(today_date, window_end)
        curr_dt = datetime.combine(today_date, current_time)
        diff = (end_dt - curr_dt).total_seconds()
        remaining_minutes = max(0, int(diff // 60))

    # Auto-Alarm on Session Start or Manual Trigger
    alarm_active = False
    if att_settings.assembly_alarm_enabled:
        if att_settings.assembly_auto_alarm_enabled and is_within_window and not is_disabled_today:
            alarm_active = True
        elif att_settings.assembly_last_alarm_sent:
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

    # Format Khmer Date: ថ្ងៃ ពុធ ទី ២ ខែ កញ្ញា ឆ្នាំ ២០២៦
    kh_days = {0: 'ចន្ទ', 1: 'អង្គារ', 2: 'ពុធ', 3: 'ព្រហស្បតិ៍', 4: 'សុក្រ', 5: 'សៅរ៍', 6: 'អាទិត្យ'}
    kh_months = {1: 'មករា', 2: 'កុម្ភៈ', 3: 'មីនា', 4: 'មេសា', 5: 'ឧសភា', 6: 'មិថុនា', 7: 'កក្កដា', 8: 'សីហា', 9: 'កញ្ញា', 10: 'តុលា', 11: 'វិច្ឆិកា', 12: 'ធ្នូ'}
    kh_digits = {'0': '០', '1': '១', '2': '២', '3': '៣', '4': '៤', '5': '៥', '6': '៦', '7': '៧', '8': '៨', '9': '៩'}
    
    day_kh = ''.join(kh_digits.get(c, c) for c in str(today_date.day))
    year_kh = ''.join(kh_digits.get(c, c) for c in str(today_date.year))
    today_date_kh = f"ថ្ងៃ {kh_days.get(today_date.weekday(), '')} ទី {day_kh} ខែ {kh_months.get(today_date.month, '')} ឆ្នាំ {year_kh}"

    context = {
        'active_year': active_year,
        'att_settings': att_settings,
        'authorized_classrooms': authorized_classrooms,
        'selected_class': selected_class,
        'selected_session': selected_session,
        'session_title': session_title,
        'today_date': today_date,
        'today_date_kh': today_date_kh,
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


# =====================================================================
# HOMEROOM TEACHER ATTENDANCE ROLL CALL SHEET (ROSTER PRINT)
# =====================================================================

@login_required
@role_required(['ADMIN', 'TEACHER'])
def homeroom_attendance_roster_view(request, classroom_id: int):
    """
    Official Monthly Student Attendance Roll Call Register (បញ្ជីហៅឈ្មោះសិស្សប្រចាំខែ ថ្ងៃទី១ ដល់ ៣១)
    Standardized to Cambodian Ministry of Education (MoEYS) classroom roll call standards.
    Restricted to Homeroom Teacher of this classroom and Administrators.
    """
    import calendar
    from datetime import date, datetime
    from django.shortcuts import get_object_or_404, redirect
    from django.contrib import messages
    from apps.academics.models import Classroom
    from apps.students.models import Student
    from apps.attendance.models import StudentAttendance
    from apps.accounts.models import SchoolProfile
    from apps.teachers.permissions import can_teacher_manage_homeroom

    classroom = get_object_or_404(Classroom.objects.select_related('academic_year', 'homeroom_teacher'), id=classroom_id)
    if not can_teacher_manage_homeroom(request.user, classroom.id):
        messages.error(request, f"⚠️ លោកគ្រូ-អ្នកគ្រូ មិនមែនជាគ្រូទទួលបន្ទុកថ្នាក់ «{classroom.name}» ឡើយ!")
        return redirect('teacher_dashboard')

    now = datetime.now()
    selected_month_raw = request.GET.get('month')
    selected_year_raw = request.GET.get('year')

    selected_month = int(selected_month_raw) if (selected_month_raw and selected_month_raw.isdigit() and 1 <= int(selected_month_raw) <= 12) else now.month
    selected_year = int(selected_year_raw) if (selected_year_raw and selected_year_raw.isdigit()) else now.year

    # Days in month
    _, total_days = calendar.monthrange(selected_year, selected_month)

    day_numbers = []
    for d in range(1, total_days + 1):
        cur_d = date(selected_year, selected_month, d)
        day_numbers.append({
            'day': d,
            'is_sunday': (cur_d.weekday() == 6),
            'date': cur_d,
        })

    students = Student.objects.filter(classroom=classroom, status='ACTIVE').order_by('student_id')

    # Pull existing attendances for this month
    start_date = date(selected_year, selected_month, 1)
    end_date = date(selected_year, selected_month, total_days)

    att_qs = StudentAttendance.objects.filter(
        student__classroom=classroom,
        date__gte=start_date,
        date__lte=end_date
    )

    attendance_map = {} # (student_id, day) -> status
    for a in att_qs:
        attendance_map[(a.student_id, a.date.day)] = a.status

    students_data = []
    female_cnt = 0
    male_cnt = 0

    for stu in students:
        if stu.gender == 'F':
            female_cnt += 1
        else:
            male_cnt += 1

        day_logs = []
        excused = 0
        unexcused = 0
        late = 0
        present = 0

        for d_info in day_numbers:
            d = d_info['day']
            st = attendance_map.get((stu.id, d))
            if st == 'PRESENT':
                present += 1
            elif st == 'EXCUSED_LEAVE':
                excused += 1
            elif st == 'UNEXCUSED_ABSENCE':
                unexcused += 1
            elif st == 'LATE':
                late += 1

            day_logs.append({
                'day': d,
                'is_sunday': d_info['is_sunday'],
                'status': st,
            })

        students_data.append({
            'student': stu,
            'day_logs': day_logs,
            'excused_count': excused,
            'unexcused_count': unexcused,
            'late_count': late,
            'present_count': present,
            'total_absence': excused + unexcused,
        })

    KHMER_MONTHS = [
        "", "មករា (January)", "កុម្ភៈ (February)", "មីនា (March)", "មេសា (April)",
        "ឧសភា (May)", "មិថុនា (June)", "កក្កដា (July)", "សីហា (August)",
        "កញ្ញា (September)", "តុលា (October)", "វិច្ឆិកា (November)", "ធ្នូ (December)"
    ]

    month_list = [{'number': m, 'name': f"ខែ {KHMER_MONTHS[m]}"} for m in range(1, 13)]
    selected_month_name = f"ខែ {KHMER_MONTHS[selected_month]}"
    school_profile = SchoolProfile.objects.first()

    return render(request, 'attendance/homeroom_roster_print.html', {
        'classroom': classroom,
        'selected_month': selected_month,
        'selected_year': selected_year,
        'selected_month_name': selected_month_name,
        'month_list': month_list,
        'days_in_month': total_days,
        'day_numbers': day_numbers,
        'students_data': students_data,
        'female_count': female_cnt,
        'male_count': male_cnt,
        'school_profile': school_profile,
    })




