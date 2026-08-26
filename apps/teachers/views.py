from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
import json
import calendar
from datetime import datetime, date, timedelta

from decimal import Decimal
from apps.accounts.decorators import role_required
from apps.accounts.models import User
from .models import Teacher, TeacherAttendance
from .forms import TeacherForm
from apps.academics.models import ClassSubject, Timetable, AcademicYear
from apps.academics.utils import get_active_academic_year
from apps.finance.models import Payroll
from .utils import (
    get_teacher_daily_attendance_data,
    get_teacher_range_attendance_report,
    sync_teacher_attendance_from_student_logs
)

@login_required
def teacher_list(request):
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')

    teachers = Teacher.objects.all()

    if query:
        teachers = teachers.filter(
            Q(teacher_id__icontains=query) |
            Q(khmer_name__icontains=query) |
            Q(latin_name__icontains=query) |
            Q(specialization__icontains=query) |
            Q(phone__icontains=query)
        )

    if status_filter:
        teachers = teachers.filter(status=status_filter)

    return render(request, 'teachers/teacher_list.html', {
        'teachers': teachers,
        'query': query,
        'selected_status': status_filter,
        'total_count': teachers.count()
    })


@login_required
@role_required(['ADMIN'])
def teacher_create(request):
    if request.method == 'POST':
        form = TeacherForm(request.POST, request.FILES)
        if form.is_valid():
            teacher = form.save()

            # Create User account for Teacher login
            username = teacher.teacher_id.lower().replace('-', '_')
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(
                    username=username,
                    password='password123',
                    role=User.Role.TEACHER,
                    khmer_name=teacher.khmer_name,
                    latin_name=teacher.latin_name,
                    phone=teacher.phone,
                    email=teacher.email
                )
                teacher.user = user
                teacher.save()

            messages.success(request, f"🎉 បានបន្ថែមគ្រូបង្រៀន {teacher.khmer_name} (User: {username}) ដោយជោគជ័យ! Password: 'password123'")
            return redirect('teacher_detail', pk=teacher.pk)
    else:
        form = TeacherForm()

    return render(request, 'teachers/teacher_form.html', {
        'form': form,
        'title': 'បន្ថែមគ្រូបង្រៀនថ្មី / Add Teacher'
    })


@login_required
def teacher_detail(request, pk):
    teacher = get_object_or_404(Teacher, pk=pk)
    
    # Permission check: Teacher can only view their own profile
    if request.user.role == User.Role.TEACHER:
        if not hasattr(request.user, 'teacher_profile') or request.user.teacher_profile.id != teacher.id:
            messages.error(request, "លោកអ្នកអាចមើលបានតែប្រវត្តិរូបរបស់ខ្លួនឯងប៉ុណ្ណោះ!")
            return redirect('teacher_dashboard')

    class_subjects = ClassSubject.objects.filter(teacher=teacher).select_related('classroom', 'subject')
    timetables = Timetable.objects.filter(teacher=teacher).select_related('classroom', 'subject').order_by('day_of_week', 'start_time')
    attendances = TeacherAttendance.objects.filter(teacher=teacher).order_by('-date')[:30]
    payrolls = Payroll.objects.filter(teacher=teacher).order_by('-year', '-month')

    return render(request, 'teachers/teacher_detail.html', {
        'teacher': teacher,
        'class_subjects': class_subjects,
        'timetables': timetables,
        'attendances': attendances,
        'payrolls': payrolls,
    })


@login_required
@role_required(['ADMIN'])
def teacher_edit(request, pk):
    teacher = get_object_or_404(Teacher, pk=pk)
    if request.method == 'POST':
        form = TeacherForm(request.POST, request.FILES, instance=teacher)
        if form.is_valid():
            form.save()
            messages.success(request, f"បានកែប្រែព័ត៌មានគ្រូ {teacher.khmer_name} ជោគជ័យ!")
            return redirect('teacher_detail', pk=teacher.pk)
    else:
        form = TeacherForm(instance=teacher)

    return render(request, 'teachers/teacher_form.html', {
        'form': form,
        'title': f'កែប្រែព័ត៌មានគ្រូ {teacher.khmer_name}',
        'teacher': teacher
    })


@login_required
@role_required(['ADMIN', 'TEACHER'])
def teacher_attendance_view(request):
    """
    Teacher Daily Attendance Sheet (Admin & Duty Staff)
    Auto-detects whether teachers recorded student attendance for their scheduled classes.
    """
    active_year = get_active_academic_year(request)
    selected_date_str = request.GET.get('date', datetime.now().strftime('%Y-%m-%d'))
    try:
        selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
    except ValueError:
        selected_date = datetime.now().date()

    teachers_qs = Teacher.objects.filter(status='ACTIVE').order_by('teacher_id')
    query = request.GET.get('q', '').strip()
    if query:
        teachers_qs = teachers_qs.filter(
            Q(teacher_id__icontains=query) |
            Q(khmer_name__icontains=query) |
            Q(latin_name__icontains=query) |
            Q(specialization__icontains=query)
        )

    # Handle Auto-Sync action from student attendance logs
    if request.GET.get('action') == 'sync':
        synced_count = sync_teacher_attendance_from_student_logs(selected_date, active_year)
        messages.success(request, f"🔄 បានធ្វើសមកាលកម្ម (Sync) វត្តមានគ្រូចំនួន {synced_count} នាក់ពីការស្រង់វត្តមានសិស្សដោយជោគជ័យ!")
        return redirect(f"/teachers/attendance/?date={selected_date.strftime('%Y-%m-%d')}")

    # Handle Form POST
    if request.method == 'POST':
        saved_count = 0
        all_active_teachers = Teacher.objects.filter(status='ACTIVE')
        for teacher in all_active_teachers:
            status_val = request.POST.get(f'status_{teacher.id}')
            notes_val = request.POST.get(f'notes_{teacher.id}', '')
            if status_val:
                att, created = TeacherAttendance.objects.update_or_create(
                    teacher=teacher,
                    date=selected_date,
                    defaults={'status': status_val, 'notes': notes_val}
                )
                saved_count += 1

        messages.success(request, f"✅ បានកត់ត្រាវត្តមានគ្រូកាលបរិច្ឆេទ {selected_date.strftime('%d/%m/%Y')} ចំនួន {saved_count} នាក់ជោគជ័យ!")
        return redirect(f"/teachers/attendance/?date={selected_date.strftime('%Y-%m-%d')}")

    # Get daily attendance data evaluated from timetable & student attendance
    daily_data = get_teacher_daily_attendance_data(teachers_qs, selected_date, active_year)

    teacher_list_data = []
    for row in daily_data['rows']:
        teacher = row['teacher']
        existing_att = row['existing_att']
        
        # Suggested status based on student attendance:
        if existing_att:
            current_status = existing_att.status
            current_notes = existing_att.notes or ''
        else:
            current_status = row['daily_status'] if row['daily_status'] in ['PRESENT', 'UNEXCUSED_ABSENCE', 'EXCUSED_LEAVE'] else 'PRESENT'
            current_notes = ''
            if row['scheduled_count'] > 0 and row['unrecorded_count'] > 0:
                current_notes = f"មិនបានចុះវត្តមានសិស្ស {row['unrecorded_count']}/{row['scheduled_count']} ម៉ោង"

        teacher_list_data.append({
            'teacher': teacher,
            'status': current_status,
            'notes': current_notes,
            'deduction': row['deduction'],
            'scheduled_count': row['scheduled_count'],
            'recorded_count': row['recorded_count'],
            'unrecorded_count': row['unrecorded_count'],
            'pending_count': row['pending_count'],
            'compliance_rate': row['compliance_rate'],
            'status_label': row['status_label'],
            'badge_class': row['badge_class'],
            'slots_list': row['slots_list'],
            'period_slots': row['period_slots'],
        })

    return render(request, 'teachers/teacher_attendance.html', {
        'selected_date': selected_date.strftime('%Y-%m-%d'),
        'selected_date_obj': selected_date,
        'teacher_list_data': teacher_list_data,
        'summary': daily_data['summary'],
        'status_choices': TeacherAttendance.Status.choices,
        'active_year': active_year,
        'query': query,
    })


@login_required
@role_required(['ADMIN', 'TEACHER'])
def teacher_attendance_report(request):
    """
    Teacher Attendance & Compliance Report (Extracts both Recorded and Unrecorded teachers).
    Counts unrecorded periods/absences by Period/Hour (ម៉ោង), Day (ថ្ងៃ), Week (សប្តាហ៍), and Month (ខែ).
    """
    active_year = get_active_academic_year(request)
    filter_type = request.GET.get('filter_type', 'month') # 'period', 'day', 'week', 'month', 'custom'
    status_filter = request.GET.get('status', 'all') # 'all', 'present', 'unrecorded', 'leave', 'no_schedule'
    query = request.GET.get('q', '').strip()
    period_filter = request.GET.get('period', 'all') # 'all', '1'..'8'

    now_dt = datetime.now()
    today = now_dt.date()

    # Determine date range or single date based on filter_type
    if filter_type == 'period' or filter_type == 'day':
        date_str = request.GET.get('date', today.strftime('%Y-%m-%d'))
        try:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            selected_date = today
        start_date = selected_date
        end_date = selected_date
        week_date_str = selected_date.strftime('%Y-%m-%d')
        month_str = selected_date.strftime('%Y-%m')
        filter_label = f"ថ្ងៃ {selected_date.strftime('%d/%m/%Y')}"
    elif filter_type == 'week':
        week_date_str = request.GET.get('week_date', today.strftime('%Y-%m-%d'))
        try:
            ref_d = datetime.strptime(week_date_str, '%Y-%m-%d').date()
        except ValueError:
            ref_d = today
        # Cambodian school week: Monday (0) to Saturday (5)
        start_date = ref_d - timedelta(days=ref_d.weekday())
        end_date = start_date + timedelta(days=5)
        selected_date = ref_d
        month_str = ref_d.strftime('%Y-%m')
        filter_label = f"សប្តាហ៍ ({start_date.strftime('%d/%m/%Y')} ដល់ {end_date.strftime('%d/%m/%Y')})"
    elif filter_type == 'custom':
        start_str = request.GET.get('start_date', today.strftime('%Y-%m-%d'))
        end_str = request.GET.get('end_date', today.strftime('%Y-%m-%d'))
        try:
            start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
        except ValueError:
            start_date = today
            end_date = today
        selected_date = start_date
        week_date_str = today.strftime('%Y-%m-%d')
        month_str = today.strftime('%Y-%m')
        filter_label = f"ចន្លោះថ្ងៃ ({start_date.strftime('%d/%m/%Y')} ដល់ {end_date.strftime('%d/%m/%Y')})"
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
        selected_date = today
        week_date_str = today.strftime('%Y-%m-%d')
        filter_label = f"ប្រចាំខែ {month_str}"

    # Fetch Active Teachers
    teachers_qs = Teacher.objects.filter(status='ACTIVE').order_by('teacher_id')
    if query:
        teachers_qs = teachers_qs.filter(
            Q(teacher_id__icontains=query) |
            Q(khmer_name__icontains=query) |
            Q(latin_name__icontains=query) |
            Q(specialization__icontains=query)
        )

    # Action: Sync teacher attendance from student logs
    if request.GET.get('action') == 'sync':
        synced_count = sync_teacher_attendance_from_student_logs(selected_date, active_year)
        messages.success(request, f"🔄 បានធ្វើសមកាលកម្មវត្តមានគ្រូចំនួន {synced_count} នាក់ពីការស្រង់វត្តមានសិស្សជោគជ័យ!")
        redirect_url = f"/teachers/attendance/report/?filter_type={filter_type}&date={selected_date.strftime('%Y-%m-%d')}&month={month_str}&week_date={week_date_str}"
        return redirect(redirect_url)

    # Process data according to filter type
    daily_report_data = None
    range_report_data = None
    filtered_rows = []

    if filter_type in ['period', 'day']:
        daily_res = get_teacher_daily_attendance_data(teachers_qs, selected_date, active_year, now_dt)
        daily_report_data = daily_res
        rows = daily_res['rows']

        # Apply Status Filter
        for r in rows:
            if status_filter == 'present' and r['daily_status'] != 'PRESENT':
                continue
            if status_filter == 'unrecorded' and r['unrecorded_count'] == 0:
                continue
            if status_filter == 'leave' and r['daily_status'] != 'EXCUSED_LEAVE':
                continue
            if status_filter == 'no_schedule' and r['scheduled_count'] > 0:
                continue
            
            # Period specific filter for 'period' mode
            if filter_type == 'period' and period_filter != 'all' and period_filter.isdigit():
                p_num = int(period_filter)
                slot_info = r['period_slots'].get(p_num)
                # If filtered by period, check if slot exists
                r['focused_period_slot'] = slot_info
            
            filtered_rows.append(r)
        
        summary = daily_res['summary']

    else:
        # Week, Month, or Custom Range
        range_res = get_teacher_range_attendance_report(teachers_qs, start_date, end_date, active_year, now_dt)
        range_report_data = range_res
        rows = range_res['rows']

        # Apply Status Filter
        for r in rows:
            if status_filter == 'present' and (not r['is_perfect']):
                continue
            if status_filter == 'unrecorded' and (not r['has_unrecorded']):
                continue
            if status_filter == 'leave' and r['excused_days_count'] == 0:
                continue
            if status_filter == 'no_schedule' and (not r['no_schedule']):
                continue
            filtered_rows.append(r)

        summary = range_res['summary']

    return render(request, 'teachers/teacher_attendance_report.html', {
        'filter_type': filter_type,
        'filter_label': filter_label,
        'status_filter': status_filter,
        'period_filter': period_filter,
        'query': query,
        'selected_date': selected_date.strftime('%Y-%m-%d'),
        'selected_date_obj': selected_date,
        'week_date_str': week_date_str,
        'month_str': month_str,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'daily_report_data': daily_report_data,
        'range_report_data': range_report_data,
        'rows': filtered_rows,
        'summary': summary,
        'active_year': active_year,
        'period_range': range(1, 9),
    })


@login_required
def teacher_leave_list(request):
    """
    Lists teacher leave requests.
    Teachers see their own requests; Admins see all requests.
    Supports filtering by Status (ALL, PENDING, APPROVED, REJECTED) and Category (EMERGENCY, PLANNED).
    """
    from apps.teachers.models import TeacherLeaveRequest
    user = request.user
    status_filter = request.GET.get('status', 'ALL')
    category_filter = request.GET.get('category', 'ALL')
    
    if user.role == 'TEACHER':
        teacher_profile = getattr(user, 'teacher_profile', None)
        if not teacher_profile:
            messages.error(request, "ពុំមានគណនីគ្រូបង្រៀនភ្ជាប់ជាមួយអ្នកប្រើប្រាស់នេះឡើយ។")
            return redirect('dashboard')
        leaves_qs = TeacherLeaveRequest.objects.filter(teacher=teacher_profile)
    else:
        leaves_qs = TeacherLeaveRequest.objects.all()

    if status_filter != 'ALL':
        leaves_qs = leaves_qs.filter(status=status_filter)

    if category_filter != 'ALL':
        leaves_qs = leaves_qs.filter(category=category_filter)

    leaves = leaves_qs.select_related('teacher', 'substitute_teacher', 'applied_by', 'approved_by').order_by('-created_at')

    return render(request, 'teachers/teacher_leave_list.html', {

        'leaves': leaves,
        'status_filter': status_filter,
        'category_filter': category_filter,
        'status_choices': TeacherLeaveRequest.Status.choices,
        'category_choices': TeacherLeaveRequest.Category.choices,
        'leave_type_choices': TeacherLeaveRequest.LeaveType.choices,
    })


@login_required
def teacher_leave_create(request):
    """
    Form for teacher or admin to submit a leave application.
    Supports:
      1. ការសុំច្បាប់ភ្លាមៗ (Emergency Leave): Strictly restricted to TODAY or TOMORROW where the teacher has scheduled classes, prior to cutoff time (e.g. 5:00 PM).
      2. ការសុំច្បាប់ទុកជាមុន (Planned Leave): In advance for formal approval & printable hardcopy.
    """
    from apps.teachers.models import TeacherLeaveRequest, TeacherAttendanceConfig
    from apps.teachers.utils import get_teacher_emergency_leave_schedule
    from apps.attendance.telegram_utils import send_teacher_leave_notification_telegram
    from datetime import time as dtime

    config = TeacherAttendanceConfig.get_settings()
    user = request.user

    teacher_profile = getattr(user, 'teacher_profile', None)
    all_teachers = Teacher.objects.filter(status='ACTIVE').order_by('teacher_id')
    available_substitutes = all_teachers.exclude(id=teacher_profile.id) if teacher_profile else all_teachers

    today = date.today()
    cutoff_time = config.emergency_leave_cutoff_time or dtime(17, 0)
    cutoff_str = cutoff_time.strftime('%H:%M')

    # Initial teacher for emergency schedule evaluation
    initial_teacher = teacher_profile or (all_teachers.first() if all_teachers else None)
    emergency_schedule = get_teacher_emergency_leave_schedule(initial_teacher) if initial_teacher else {'options': [], 'cutoff_str': cutoff_str, 'has_available_dates': False}

    # Precompute emergency schedules for Admin teacher dropdown
    emergency_schedules_map = {}
    if user.role == 'ADMIN':
        for t in all_teachers:
            emergency_schedules_map[str(t.id)] = get_teacher_emergency_leave_schedule(t)

    if request.method == 'POST':
        if user.role == 'ADMIN':
            teacher_id = request.POST.get('teacher_id')
            selected_teacher = get_object_or_404(Teacher, pk=teacher_id)
        else:
            if not teacher_profile:
                messages.error(request, "⚠️ អ្នកគ្មានសិទ្ធិដាក់ពាក្យសុំច្បាប់ឡើយ!")
                return redirect('dashboard')
            selected_teacher = teacher_profile

        category = request.POST.get('category', TeacherLeaveRequest.Category.PLANNED)
        leave_type = request.POST.get('leave_type', 'PERSONAL')
        start_date_str = request.POST.get('start_date')
        end_date_str = request.POST.get('end_date') or start_date_str
        reason = request.POST.get('reason', '').strip()
        substitute_id = request.POST.get('substitute_teacher_id')
        attachment = request.FILES.get('attachment')

        substitute_teacher = Teacher.objects.filter(id=substitute_id).first() if substitute_id else None

        if start_date_str and reason:
            try:
                s_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                e_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

                if e_date < s_date:
                    messages.error(request, "⚠️ ថ្ងៃបញ្ចប់មិនអាចតូចជាងថ្ងៃចាប់ផ្តើមឡើយ!")
                elif s_date < today:
                    messages.error(request, "⚠️ មិនអាចដាក់ពាក្យសុំច្បាប់សម្រាប់កាលបរិច្ឆេទក្នុងអតីតកាលឡើយ!")
                else:
                    # Validate Category 1: Strict Timetable & Cutoff Rules
                    if category == TeacherLeaveRequest.Category.EMERGENCY:
                        schedule_info = get_teacher_emergency_leave_schedule(selected_teacher)
                        matched_option = next((opt for opt in schedule_info['options'] if opt['date_str'] == start_date_str), None)

                        if not matched_option:
                            messages.error(
                                request,
                                f"⚠️ លោកគ្រូ-អ្នកគ្រូ {selected_teacher.khmer_name} គ្មានកាលវិភាគបង្រៀននៅថ្ងៃ {start_date_str} ឡើយ! ការសុំច្បាប់បន្ទាន់អនុញ្ញាតតែថ្ងៃដែលមានកាលវិភាគបង្រៀន (ថ្ងៃនេះ ឬស្អែក) ប៉ុណ្ណោះ។"
                            )
                            return render(request, 'teachers/teacher_leave_form.html', {
                                'teacher_profile': teacher_profile,
                                'all_teachers': all_teachers if user.role == 'ADMIN' else None,
                                'available_substitutes': available_substitutes,
                                'category_choices': TeacherLeaveRequest.Category.choices,
                                'leave_type_choices': TeacherLeaveRequest.LeaveType.choices,
                                'config': config,
                                'emergency_schedule': emergency_schedule,
                                'emergency_schedules_json': json.dumps(emergency_schedules_map),
                                'today_str': today.strftime('%Y-%m-%d'),
                            })

                        if not matched_option['is_allowed'] and user.role != 'ADMIN':
                            messages.error(
                                request,
                                f"⚠️ ការសុំច្បាប់បន្ទាន់សម្រាប់ {matched_option['label']} បានផុតម៉ោងកំណត់ {schedule_info['cutoff_str']} រសៀលហើយ!"
                            )
                            return render(request, 'teachers/teacher_leave_form.html', {
                                'teacher_profile': teacher_profile,
                                'all_teachers': all_teachers if user.role == 'ADMIN' else None,
                                'available_substitutes': available_substitutes,
                                'category_choices': TeacherLeaveRequest.Category.choices,
                                'leave_type_choices': TeacherLeaveRequest.LeaveType.choices,
                                'config': config,
                                'emergency_schedule': emergency_schedule,
                                'emergency_schedules_json': json.dumps(emergency_schedules_map),
                                'today_str': today.strftime('%Y-%m-%d'),
                            })

                        # Emergency leave is for the specific timetable teaching date
                        e_date = s_date

                    # Generate Unique Leave Code
                    count_today = TeacherLeaveRequest.objects.filter(created_at__date=today).count() + 1
                    leave_code = f"LV-{today.strftime('%Y%m%d')}-{count_today:03d}"
                    proxy_note = request.POST.get('proxy_note', '').strip() if user.role == 'ADMIN' else ''

                    leave_req = TeacherLeaveRequest.objects.create(
                        category=category,
                        leave_code=leave_code,
                        teacher=selected_teacher,
                        applied_by=user,
                        proxy_note=proxy_note,
                        substitute_teacher=substitute_teacher,
                        leave_type=leave_type,
                        start_date=s_date,
                        end_date=e_date,
                        reason=reason,
                        attachment=attachment,
                        status=TeacherLeaveRequest.Status.PENDING
                    )
                    # Notify management via Telegram
                    send_teacher_leave_notification_telegram(leave_req)


                    cat_badge = "ការសុំច្បាប់ភ្លាមៗ (បន្ទាន់)" if category == TeacherLeaveRequest.Category.EMERGENCY else "ការសុំច្បាប់ទុកជាមុន"
                    messages.success(
                        request,
                        f"📨 បានដាក់ពាក្យសុំច្បាប់ [{cat_badge} • លេខកូដ: {leave_code}] ដោយជោគជ័យ! ប្រព័ន្ធបានជូនដំណឹងទៅគណៈគ្រប់គ្រងសាលាហើយ។"
                    )
                    return redirect('teacher_leave_list')
            except Exception as ex:
                messages.error(request, f"⚠️ កំហុសកាលបរិច្ឆេទ ឬប្រព័ន្ធ៖ {str(ex)}")
        else:
            messages.error(request, "⚠️ សូមបំពេញកាលបរិច្ឆេទ និងមូលហេតុសុំច្បាប់ឱ្យបានគ្រប់គ្រាន់!")

    return render(request, 'teachers/teacher_leave_form.html', {
        'teacher_profile': teacher_profile,
        'all_teachers': all_teachers if user.role == 'ADMIN' else None,
        'available_substitutes': available_substitutes,
        'category_choices': TeacherLeaveRequest.Category.choices,
        'leave_type_choices': TeacherLeaveRequest.LeaveType.choices,
        'config': config,
        'emergency_schedule': emergency_schedule,
        'emergency_schedules_json': json.dumps(emergency_schedules_map),
        'today_str': today.strftime('%Y-%m-%d'),
    })



@login_required
def teacher_leave_print_letter(request, pk):
    """
    Formal Khmer A4 Printable Leave Application Letter (លិខិតសុំច្បាប់ផ្លូវការ)
    """
    from apps.teachers.models import TeacherLeaveRequest
    from apps.accounts.models import SchoolProfile

    leave_req = get_object_or_404(TeacherLeaveRequest, pk=pk)
    user = request.user

    # Security check: Teacher can only print their own leave form unless Admin
    if user.role == 'TEACHER':
        if not hasattr(user, 'teacher_profile') or user.teacher_profile.id != leave_req.teacher.id:
            messages.error(request, "លោកអ្នកអាចបោះពុម្ពបានតែលិខិតសុំច្បាប់របស់ខ្លួនឯងប៉ុណ្ណោះ!")
            return redirect('teacher_leave_list')

    school_profile = SchoolProfile.get_settings()

    return render(request, 'teachers/teacher_leave_print.html', {
        'leave': leave_req,
        'school': school_profile,
        'today': date.today(),
        'page_title': f"លិខិតសុំច្បាប់ - {leave_req.teacher.khmer_name} ({leave_req.leave_code or leave_req.id})"
    })



# ----------------- TEACHER EXPORT & IMPORT (EXCEL / CSV) -----------------

@login_required
@role_required(['ADMIN'])
def teacher_export_excel(request):
    """
    Exports all teachers into a beautifully formatted Excel sheet for Timetable / HR management.
    """
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter
    from django.http import HttpResponse

    teachers = Teacher.objects.all().order_by('teacher_id')
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Teachers Directory"
    ws.views.sheetView[0].showGridLines = True

    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    data_font = Font(name="Calibri", size=10)
    center_align = Alignment(horizontal="center", vertical="center")
    left_align = Alignment(horizontal="left", vertical="center")
    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    headers = [
        "ល.រ / No",
        "អត្តលេខ / Teacher ID",
        "ឈ្មោះខ្មែរ / Khmer Name",
        "ឈ្មោះឡាតាំង / Latin Name",
        "ភេទ / Gender",
        "ថ្ងៃខែឆ្នាំកំណើត / DOB",
        "លេខទូរស័ព្ទ / Phone",
        "អ៊ីមែល / Email",
        "ឯកទេសបង្រៀន / Specialization",
        "កម្រិតវប្បធម៌ / Qualification",
        "ម៉ោងអតិបរមា/សប្តាហ៍ / Max Weekly Hours",
        "ប្រាក់ខែគោល ($) / Base Salary",
        "ស្ថានភាព / Status"
    ]

    ws.append(headers)
    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align
        cell.border = thin_border
    ws.row_dimensions[1].height = 28

    for idx, t in enumerate(teachers, 1):
        row = [
            idx,
            t.teacher_id,
            t.khmer_name,
            t.latin_name,
            t.get_gender_display(),
            t.date_of_birth.strftime('%Y-%m-%d') if t.date_of_birth else '',
            t.phone or '',
            t.email or '',
            t.specialization or '',
            t.qualification or '',
            t.max_weekly_hours,
            float(t.base_salary or 0),
            t.get_status_display()
        ]
        ws.append(row)
        curr_row = idx + 1
        ws.row_dimensions[curr_row].height = 22
        for c_idx in range(1, len(row) + 1):
            cell = ws.cell(row=curr_row, column=c_idx)
            cell.font = data_font
            cell.border = thin_border
            if c_idx in [1, 2, 5, 6, 11, 13]:
                cell.alignment = center_align
            else:
                cell.alignment = left_align

    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="Teachers_Directory_{date.today().strftime("%Y%m%d")}.xlsx"'
    wb.save(response)
    return response


@login_required
@role_required(['ADMIN'])
def teacher_import_template_excel(request):
    """Generates a downloadable sample Excel template for importing teachers."""
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter
    from django.http import HttpResponse

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Teacher Import Template"
    ws.views.sheetView[0].showGridLines = True

    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    headers = [
        "Teacher ID *",
        "Khmer Name *",
        "Latin Name *",
        "Gender (M/F) *",
        "DOB (YYYY-MM-DD)",
        "Phone *",
        "Email",
        "Specialization *",
        "Qualification",
        "Max Weekly Hours",
        "Base Salary ($)",
        "Status (ACTIVE/ON_LEAVE/RESIGNED)"
    ]
    ws.append(headers)
    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border
    ws.row_dimensions[1].height = 28

    sample_rows = [
        ["T-001", "សុខ វិបុល", "Sok Vibol", "M", "1985-05-15", "012345678", "vibol@school.edu.kh", "គណិតវិទ្យា", "បរិញ្ញាបត្រអប់រំ", 18, 500, "ACTIVE"],
        ["T-002", "ចាន់ រិទ្ធី", "Chan Rithy", "M", "1990-08-20", "017888999", "rithy@school.edu.kh", "រូបវិទ្យា", "បរិញ្ញាបត្រជាន់ខ្ពស់", 18, 550, "ACTIVE"],
        ["T-003", "ម៉ៅ ស្រីពៅ", "Mao Sreypov", "F", "1992-12-10", "096123456", "sreypov@school.edu.kh", "ភាសាខ្មែរ", "បរិញ្ញាបត្រអក្សរសាស្ត្រ", 18, 500, "ACTIVE"],
        ["T-004", "ហេង សុផល", "Heng Sophal", "M", "1988-03-25", "077112233", "sophal@school.edu.kh", "ព័ត៌មានវិទ្យា & ICT", "បរិញ្ញាបត្រវិទ្យាសាស្ត្រកុំព្យូទ័រ", 18, 520, "ACTIVE"],
    ]
    for r in sample_rows:
        ws.append(r)
        curr_row = ws.max_row
        ws.row_dimensions[curr_row].height = 22
        for c_idx in range(1, len(r) + 1):
            cell = ws.cell(row=curr_row, column=c_idx)
            cell.font = Font(name="Calibri", size=10)
            cell.border = thin_border
            if c_idx in [1, 4, 5, 6, 10, 12]:
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")

    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 14)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="teacher_import_template.xlsx"'
    wb.save(response)
    return response


@login_required
@role_required(['ADMIN'])
def teacher_import_template_csv(request):
    """Generates a downloadable sample CSV template for importing teachers."""
    import csv
    from django.http import HttpResponse

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="teacher_import_template.csv"'
    writer = csv.writer(response)
    writer.writerow([
        "Teacher ID *",
        "Khmer Name *",
        "Latin Name *",
        "Gender (M/F) *",
        "DOB (YYYY-MM-DD)",
        "Phone *",
        "Email",
        "Specialization *",
        "Qualification",
        "Max Weekly Hours",
        "Base Salary ($)",
        "Status (ACTIVE/ON_LEAVE/RESIGNED)"
    ])
    writer.writerow(["T-001", "សុខ វិបុល", "Sok Vibol", "M", "1985-05-15", "012345678", "vibol@school.edu.kh", "គណិតវិទ្យា", "បរិញ្ញាបត្រអប់រំ", "18", "500", "ACTIVE"])
    writer.writerow(["T-002", "ចាន់ រិទ្ធី", "Chan Rithy", "M", "1990-08-20", "017888999", "rithy@school.edu.kh", "រូបវិទ្យា", "បរិញ្ញាបត្រជាន់ខ្ពស់", "18", "550", "ACTIVE"])
    return response


@login_required
@role_required(['ADMIN'])
def teacher_import(request):
    """Bulk imports teachers from Excel or CSV file."""
    import csv
    import io
    import openpyxl
    from decimal import Decimal
    from apps.accounts.models import User

    if request.method == 'POST' and request.FILES.get('file'):
        file = request.FILES['file']
        filename = file.name.lower()
        rows_data = []

        try:
            if filename.endswith('.xlsx'):
                wb = openpyxl.load_workbook(file, data_only=True)
                ws = wb.active
                for row in ws.iter_rows(min_row=2, values_only=True):
                    if row and any(row):
                        rows_data.append(list(row))
            elif filename.endswith('.csv'):
                decoded_file = file.read().decode('utf-8-sig')
                io_string = io.StringIO(decoded_file)
                reader = csv.reader(io_string)
                header = next(reader, None)
                for row in reader:
                    if row and any(row):
                        rows_data.append(row)
            else:
                messages.error(request, "⚠️ ទម្រង់ឯកសារមិនត្រឹមត្រូវ! សូមជ្រើសរើសឯកសារ .xlsx ឬ .csv")
                return redirect('teacher_import')

            success_count = 0
            updated_count = 0
            errors = []

            for idx, r in enumerate(rows_data, 2):
                if len(r) < 3:
                    continue
                t_id = str(r[0] or '').strip()
                k_name = str(r[1] or '').strip()
                l_name = str(r[2] or '').strip()
                gender_raw = str(r[3] or 'M').strip().upper()
                dob_raw = r[4] if len(r) > 4 else None
                phone = str(r[5] or '').strip() if len(r) > 5 else ''
                email = str(r[6] or '').strip() if len(r) > 6 else ''
                spec = str(r[7] or '').strip() if len(r) > 7 else 'ទូទៅ'
                qual = str(r[8] or '').strip() if len(r) > 8 else ''
                max_hours = int(r[9]) if len(r) > 9 and str(r[9]).isdigit() else 18
                salary_str = str(r[10] or '500.00').replace('$', '').replace(',', '').strip() if len(r) > 10 else '500.00'
                salary = Decimal(salary_str) if salary_str else Decimal('500.00')
                status_raw = str(r[11] or 'ACTIVE').strip().upper() if len(r) > 11 else 'ACTIVE'

                if not t_id or not k_name:
                    errors.append(f"ជួរទី {idx}៖ ខ្វះ Teacher ID ឬឈ្មោះគ្រូ")
                    continue

                gender = Teacher.Gender.FEMALE if gender_raw in ['F', 'ស្រី', 'FEMALE'] else Teacher.Gender.MALE
                status = Teacher.Status.ON_LEAVE if status_raw == 'ON_LEAVE' else (Teacher.Status.RESIGNED if status_raw == 'RESIGNED' else Teacher.Status.ACTIVE)

                dob = None
                if dob_raw:
                    if isinstance(dob_raw, (datetime, date)):
                        dob = dob_raw if isinstance(dob_raw, date) else dob_raw.date()
                    else:
                        try:
                            dob = datetime.strptime(str(dob_raw).strip(), '%Y-%m-%d').date()
                        except Exception:
                            pass

                teacher, created = Teacher.objects.update_or_create(
                    teacher_id=t_id,
                    defaults={
                        'khmer_name': k_name,
                        'latin_name': l_name or k_name,
                        'gender': gender,
                        'date_of_birth': dob,
                        'phone': phone,
                        'email': email or None,
                        'specialization': spec,
                        'qualification': qual,
                        'max_weekly_hours': max_hours,
                        'base_salary': salary,
                        'status': status,
                    }
                )

                # Auto-create or link User Account
                username = t_id.lower().replace('-', '_').replace(' ', '_')
                user = User.objects.filter(username=username).first()
                if not user:
                    user = User.objects.create_user(
                        username=username,
                        password='password123',
                        role=User.Role.TEACHER,
                        khmer_name=k_name,
                        latin_name=l_name,
                        phone=phone,
                        email=email or ''
                    )
                teacher.user = user
                teacher.save(update_fields=['user'])

                if created:
                    success_count += 1
                else:
                    updated_count += 1

            if success_count > 0 or updated_count > 0:
                messages.success(request, f"🎉 ជោគជ័យ! បានបញ្ចូលគ្រូបង្រៀនថ្មី {success_count} នាក់ និងកែប្រែទិន្នន័យចាស់ {updated_count} នាក់។ គណនី Login ត្រូវបានបង្កើតដោយស្វ័យប្រវត្តិ (Password: password123)")
            if errors:
                for err in errors[:5]:
                    messages.warning(request, f"⚠️ {err}")
            return redirect('teacher_list')

        except Exception as e:
            messages.error(request, f"⚠️ មានបញ្ហាក្នុងការ Import៖ {str(e)}")
            return redirect('teacher_import')

    return render(request, 'teachers/teacher_import.html')


