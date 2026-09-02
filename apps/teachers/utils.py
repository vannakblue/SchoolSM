import calendar
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from django.db.models import Q
from apps.teachers.models import Teacher, TeacherAttendance, TeacherLeaveRequest, TeacherPunchLog
from apps.academics.models import Timetable, Classroom, AcademicYear

from apps.attendance.models import StudentAttendance, AttendanceSubmissionLog
from apps.academics.utils import get_active_academic_year

KHMER_LATIN_DICT = {
    'កង': 'Kang', 'កញ្ញា': 'Kanya', 'កន្យា': 'Kanya', 'កាន': 'Kan', 'កុសល': 'Kosal',
    'កឿន': 'Koeun', 'កែវ': 'Keo', 'ក្រឹង': 'Kreung', 'ខឹម': 'Khim', 'ខៀវ': 'Khiev',
    'ខេមរិន្ទ': 'Khemrinth', 'គង់': 'Kong', 'គន្ធា': 'Kunthea', 'គាន': 'Kean', 'គ្រីន': 'Krin',
    'ឃាង': 'Kheang', 'ឃឹម': 'Khim', 'ឃុត': 'Khut', 'ឃុន': 'Khun', 'ងួន': 'Nguon',
    'ចន្ថា': 'Chantha', 'ចន្ទ្រា': 'Chantrea', 'ចរិយា': 'Chariya', 'ចាន់': 'Chan',
    'ចាន់ណាក់': 'Channak', 'ចាន់ថា': 'Chantha', 'ចាន់នី': 'Channy', 'ចាន់រ៉ា': 'Chanra',
    'ចាន់សុផាន់ណា': 'Chansophanna', 'ចិន្តា': 'Chinda', 'ចេង': 'Cheng', 'ចំរើន': 'Chamroeun',
    'ច័ន្ទសុធី': 'Chansothey', 'ឆាយ': 'Chhay', 'ឆេង': 'Chheng', 'ជឹង': 'Cheung', 'ជឹម': 'Chim',
    'ជុំ': 'Chum', 'ជួ': 'Chou', 'ជួង': 'Chhoung', 'ជៀស': 'Chieas', 'ជៃ': 'Chay',
    'ជំនិត': 'Chomnit', 'ឈាង': 'Chheang', 'ឈឿន': 'Chhoeun', 'ដាវណ្ណ': 'Davann', 'ដាវី': 'Davy',
    'ដុក': 'Dok', 'ដួង': 'Duong', 'ឌីណា': 'Dina', 'ឌីនីន': 'Dinin', 'ឌីម៉ង់': 'Dimang',
    'ឌុច': 'Duch', 'ណារី': 'Nary', 'ណារ៉ា': 'Nara', 'ណាសួន': 'Nasoun', 'ណុប': 'Nop',
    'ណុំ': 'Nom', 'ថោង': 'Thaong', 'ទិត': 'Tith', 'ទិន': 'Tin', 'ទឹម': 'Tim',
    'ទុន': 'Tun', 'ទូច': 'Touch', 'ទ្រី': 'Try', 'ធី': 'Thy', 'ធីតា': 'Thida',
    'នាង': 'Neang', 'និមល': 'Nimol', 'និស្សិត': 'Nissith', 'នី': 'Ny', 'បុណ្ណវេទ': 'Bonnveth',
    'បូ': 'Bo', 'បូរាមី': 'Boramy', 'ប៉ន': 'Porn', 'ប៊ុន': 'Bun', 'ប៊ុនណារិទ្ធ': 'Bunnarith',
    'ប៊ុនថន': 'Bunthon', 'ប៊ុនធន': 'Bunthon', 'ប្រាក់': 'Prak', 'ផន': 'Phorn', 'ផល': 'Phal',
    'ផល្លី': 'Phally', 'ផាត់': 'Phat', 'ផេង': 'Pheng', 'ពិដោរ': 'Pidor', 'ពិសាល': 'Pisal',
    'ពិសី': 'Pisey', 'ពិសេស': 'Pises', 'ពឺន': 'Poeun', 'ពុទ្ធាវី': 'Putheavy', 'ពូន': 'Poun',
    'ពេជ្រ': 'Pech', 'ពៅ': 'Pov', 'ភារុន': 'Phearun', 'ភ័ស': 'Phorn', 'មករា': 'Makara',
    'មាស': 'Meas', 'មូល': 'Moul', 'មៀច': 'Miech', 'ម៉ង់': 'Mang', 'ម៉ានិន': 'Manin',
    'ម៉ាលីស': 'Malis', 'ម៉ូនីដា': 'Monida', 'ម៉ែន': 'Men', 'យូ': 'You', 'យូណៃ': 'Younai',
    'យ៉ន': 'Yorn', 'យ៉ាង': 'Yang', 'យ៉េន': 'Yen', 'រក្សា': 'Raksa', 'រចនា': 'Rachana',
    'រតនា': 'Rattana', 'រិទ្ធីយ៉ា': 'Rithiya', 'រុនស្រី': 'Ronsrey', 'រ៉ន': 'Rorn',
    'លក្ខិណា': 'Leakhena', 'លន': 'Lon', 'លាងឃន': 'Leangkhon', 'លី': 'Ly', 'លីឆាយ': 'Lychhay',
    'លឿង': 'Loeung', 'វណ្ណៈ': 'Vannak', 'វាសនា': 'Veasna', 'វិន': 'Vin', 'វិសាល': 'Visal',
    'វ៉ាង': 'Vang', 'វ៉ាន់': 'Van', 'វ៉េង': 'Veng', 'សម្បត្តិ': 'Sambath', 'សា': 'Sa',
    'សានម៉ូណាវី': 'Sanmonavy', 'សានសុផានី': 'Sansophanith', 'សាន់': 'San', 'សាមឌី': 'Samdy',
    'សារិន': 'Sarin', 'សាវិន': 'Savin', 'សីហា': 'Seyha', 'សុខ': 'Sok', 'សុខឃៀង': 'Sokkheang',
    'សុខចាន់': 'Sokchan', 'សុខម៉េត': 'Sokmet', 'សុខា': 'Sokha', 'សុខុម': 'Sokhom',
    'សុគង់': 'Sokong', 'សុគន្ធារី': 'Sokuntheary', 'សុង': 'Song', 'សុជាតា': 'Socheata',
    'សុដានី': 'Sodany', 'សុទ្ធ': 'Soth', 'សុន': 'Son', 'សុផន': 'Sophon', 'សុផា': 'Sopha',
    'សុផាន': 'Sophan', 'សុផារិទ្ធ': 'Sopharith', 'សុភារៈ': 'Sophearak', 'សុភី': 'Sophea',
    'សុភ័ក្រ': 'Sopheak', 'សុមនី': 'Somony', 'សុម៉ាឡា': 'Somala', 'សុសៅគន្ធ': 'Sosaokunth',
    'សូ': 'So', 'សូកាន': 'Sokan', 'សូរីយា': 'Soriya', 'សួន': 'Suon', 'សួរ': 'Sour',
    'សួស': 'Suos', 'សឿន': 'Soeun', 'សេង': 'Seng', 'សេងហៃ': 'Senghai', 'សេត': 'Seth',
    'សេរីពង្ស': 'Sereypong', 'សេស': 'Ses', 'សែត': 'Set', 'សោម៉នវីរៈ': 'Somonvirak',
    'សំ': 'Sam', 'សំអុល': 'Sam Ol', 'សំអឿន': 'Samoeun', 'ស៊ិន': 'Sin', 'ស៊ីដារ៉ា': 'Sidara',
    'ស៊ីនាង': 'Siniang', 'ស៊ុយ': 'Suy', 'ស៊ុំ': 'Sum', 'ស្រស់': 'Sros', 'ស្រីណែត': 'Sreynet',
    'ស្រីនាង': 'Sreyniang', 'ស្រីពៅ': 'Sreypov', 'ស្រីរ័ត្ន': 'Sreyroth', 'ស្រីលក្ខ័': 'Sreyleak',
    'ស្រ៊ុន': 'Srun', 'ហន': 'Horn', 'ហុង': 'Hong', 'ហួត': 'Huot', 'ហៀង': 'Heang',
    'ហេង': 'Heng', 'ហ៊ឺ': 'Heu', 'ហ៊ូ': 'Hou', 'ឡាង': 'Lang', 'ឡុច': 'Loch',
    'ឡេង': 'Leng', 'អមរា': 'Amara', 'អាន': 'An', 'អៀ': 'Iea', 'អេង': 'Eng',
    'អោម': 'Aom', 'អ៊ិន': 'In', 'អ៊ឹម': 'Im', 'អ៊ុយ': 'Uy', 'ឯក': 'Ek'
}


def transliterate_khmer_name(kh_name):
    if not kh_name:
        return ''
    cleaned = kh_name.replace('\u200b', ' ').strip()
    words = cleaned.split()
    latin_words = []
    for w in words:
        w_clean = w.strip()
        if w_clean in KHMER_LATIN_DICT:
            latin_words.append(KHMER_LATIN_DICT[w_clean])
        else:
            latin_words.append(w_clean)
    return ' '.join(latin_words)


def format_phone_number(raw_phone):
    if not raw_phone:
        return ''
    p_str = str(raw_phone).strip()
    digits = ''.join(c for c in p_str if c.isdigit())
    if not digits:
        return ''
    if not digits.startswith('0'):
        digits = '0' + digits
    return digits



def get_teacher_daily_attendance_data(teachers, target_date, active_year=None, current_dt=None):
    """
    Evaluates timetable teaching slots vs. student attendance submission logs for all given teachers on target_date.
    Also incorporates TeacherPunchLog hardware/QR/Face check-in logs.
    
    Returns:
        dict with:
            - 'rows': list of teacher attendance objects for the date
            - 'summary': high-level count summary
    """
    if current_dt is None:
        current_dt = datetime.now()

    current_date = current_dt.date()
    current_time = current_dt.time()
    day_of_week = target_date.isoweekday() # 1=Mon ... 6=Sat, 7=Sun

    # 1. Fetch all timetable slots on this day_of_week for active academic year
    timetables_qs = Timetable.objects.filter(
        day_of_week=day_of_week
    ).select_related('classroom', 'subject', 'teacher')

    if active_year:
        timetables_qs = timetables_qs.filter(classroom__academic_year=active_year)

    # Group timetables by teacher_id
    teacher_slots_map = {}
    for entry in timetables_qs:
        t_id = entry.teacher_id
        if t_id not in teacher_slots_map:
            teacher_slots_map[t_id] = []
        teacher_slots_map[t_id].append(entry)

    # 2. Fetch all student attendance logs and records on target_date
    submission_logs = AttendanceSubmissionLog.objects.filter(
        date=target_date
    ).values('classroom_id', 'period_number', 'submission_count', 'updated_at', 'recorded_by_id')

    # (classroom_id, period_number) -> log dict
    logs_map = {(log['classroom_id'], log['period_number']): log for log in submission_logs}

    # Also check StudentAttendance records for backup
    raw_st_atts = StudentAttendance.objects.filter(
        date=target_date
    ).values('classroom_id', 'period_number').distinct()
    for item in raw_st_atts:
        k = (item['classroom_id'], item['period_number'])
        if k not in logs_map:
            logs_map[k] = {'submission_count': 1, 'updated_at': None, 'recorded_by_id': None}

    # 3. Fetch any manual TeacherAttendance records for this date
    existing_teacher_atts = {
        att.teacher_id: att for att in TeacherAttendance.objects.filter(date=target_date)
    }

    # 4. Fetch approved TeacherLeaveRequests covering target_date
    approved_leaves = {
        leave.teacher_id: leave for leave in TeacherLeaveRequest.objects.filter(
            status=TeacherLeaveRequest.Status.APPROVED,
            start_date__lte=target_date,
            end_date__gte=target_date
        )
    }

    # 5. Fetch all TeacherPunchLog records on target_date
    teacher_punches_map = {}
    for punch in TeacherPunchLog.objects.filter(date=target_date).order_by('punch_time'):
        t_id = punch.teacher_id
        if t_id not in teacher_punches_map:
            teacher_punches_map[t_id] = []
        teacher_punches_map[t_id].append(punch)



    results = []
    summary_stats = {
        'total_teachers': len(teachers),
        'teachers_with_schedule': 0,
        'teachers_full_present': 0,
        'teachers_with_unrecorded': 0,
        'teachers_on_leave': 0,
        'teachers_no_schedule': 0,
        'total_scheduled_periods': 0,
        'total_recorded_periods': 0,
        'total_unrecorded_periods': 0,
        'overall_compliance_rate': 100.0,
    }

    for teacher in teachers:
        slots = teacher_slots_map.get(teacher.id, [])
        # Sort slots by period number
        slots = sorted(slots, key=lambda s: s.period_number)

        period_slots_detail = {}
        # Slots details by period_number (1 to 8)
        for p in range(1, 9):
            period_slots_detail[p] = None

        scheduled_count = len(slots)
        recorded_count = 0
        unrecorded_count = 0
        pending_count = 0

        for slot in slots:
            p_num = slot.period_number
            is_recorded = False
            log_entry = logs_map.get((slot.classroom_id, p_num))

            if log_entry and log_entry.get('submission_count', 0) > 0:
                is_recorded = True

            # Determine slot status
            slot_status = 'NO_SCHEDULE'
            if is_recorded:
                slot_status = 'RECORDED'
                recorded_count += 1
            else:
                # Not recorded yet: is it past or future?
                if target_date < current_date:
                    slot_status = 'UNRECORDED'
                    unrecorded_count += 1
                elif target_date > current_date:
                    slot_status = 'FUTURE'
                    pending_count += 1
                else:
                    # target_date == current_date
                    slot_end_time = slot.end_time or time(17, 0)
                    if current_time > slot_end_time:
                        slot_status = 'UNRECORDED'
                        unrecorded_count += 1
                    else:
                        slot_status = 'PENDING'
                        pending_count += 1

            period_slots_detail[p_num] = {
                'slot': slot,
                'classroom': slot.classroom,
                'subject': slot.subject,
                'start_time': slot.start_time,
                'end_time': slot.end_time,
                'is_recorded': is_recorded,
                'status': slot_status,
                'log_entry': log_entry,
            }

        # Check existing TeacherAttendance & Approved Leave Request
        existing_att = existing_teacher_atts.get(teacher.id)
        approved_leave = approved_leaves.get(teacher.id)
        is_excused = (approved_leave is not None) or (existing_att and existing_att.status == TeacherAttendance.Status.EXCUSED_LEAVE)

        # Determine daily status
        if is_excused:
            daily_status = 'EXCUSED_LEAVE'
            leave_label = approved_leave.get_leave_type_display() if approved_leave else 'Excused Leave'
            status_label = f'ច្បាប់អនុញ្ញាត ({leave_label})'
            badge_class = 'warning'

        elif scheduled_count == 0:
            daily_status = 'NO_SCHEDULE'
            status_label = 'គ្មានម៉ោងបង្រៀន (No Schedule)'
            badge_class = 'secondary'
        elif unrecorded_count > 0:
            daily_status = 'UNEXCUSED_ABSENCE'
            status_label = f'អវត្តមាន ({unrecorded_count} ម៉ោងមិនបានចុះ)'
            badge_class = 'danger'
        elif pending_count > 0 and recorded_count == 0:
            daily_status = 'PENDING'
            status_label = 'កំពុងរង់ចាំ (Pending/Today)'
            badge_class = 'info'
        else:
            daily_status = 'PRESENT'
            status_label = 'វត្តមាន (បានចុះគ្រប់)'
            badge_class = 'success'

        compliance_rate = round((recorded_count / scheduled_count * 100), 1) if scheduled_count > 0 else 100.0

        # Deduction calculation disabled
        deduction = Decimal('0.00')

        # Accumulate summary stats
        summary_stats['total_scheduled_periods'] += scheduled_count
        summary_stats['total_recorded_periods'] += recorded_count
        if not is_excused:
            summary_stats['total_unrecorded_periods'] += unrecorded_count

        if scheduled_count > 0:
            summary_stats['teachers_with_schedule'] += 1
            if is_excused:
                summary_stats['teachers_on_leave'] += 1

            elif unrecorded_count > 0:
                summary_stats['teachers_with_unrecorded'] += 1
            else:
                summary_stats['teachers_full_present'] += 1
        else:
            summary_stats['teachers_no_schedule'] += 1

        teacher_punches = teacher_punches_map.get(teacher.id, [])
        first_punch = teacher_punches[0] if teacher_punches else None

        results.append({
            'teacher': teacher,
            'scheduled_count': scheduled_count,
            'recorded_count': recorded_count,
            'unrecorded_count': unrecorded_count,
            'pending_count': pending_count,
            'compliance_rate': compliance_rate,
            'daily_status': daily_status,
            'status_label': status_label,
            'badge_class': badge_class,
            'existing_att': existing_att,
            'notes': existing_att.notes if existing_att else '',
            'deduction': deduction,
            'period_slots': period_slots_detail,
            'slots_list': slots,
            'punch_logs': teacher_punches,
            'first_punch': first_punch,
            'check_in_time': existing_att.check_in_time if existing_att and existing_att.check_in_time else (first_punch.punch_time.time() if first_punch else None),
            'check_in_method': existing_att.check_in_method if existing_att and existing_att.check_in_method else (first_punch.get_method_display() if first_punch else None),
        })


    if summary_stats['total_scheduled_periods'] > 0:
        summary_stats['overall_compliance_rate'] = round(
            (summary_stats['total_recorded_periods'] / summary_stats['total_scheduled_periods'] * 100), 1
        )

    return {
        'target_date': target_date,
        'day_of_week': day_of_week,
        'rows': results,
        'summary': summary_stats,
    }


def get_teacher_range_attendance_report(teachers, start_date, end_date, active_year=None, current_dt=None):
    """
    Aggregates teacher attendance across a date range (e.g. week, month, custom).
    
    Returns:
        dict with:
            - 'rows': aggregated stats per teacher
            - 'dates_list': list of distinct teaching dates in range (Mon-Sat)
            - 'summary': overall summary stats
            - 'daily_data_map': date -> daily data
    """
    if current_dt is None:
        current_dt = datetime.now()

    # Generate list of dates in range, excluding Sundays (isoweekday == 7)
    cur = start_date
    dates_list = []
    while cur <= end_date:
        if cur.isoweekday() <= 6: # Monday (1) to Saturday (6)
            dates_list.append(cur)
        cur += timedelta(days=1)

    daily_data_map = {}
    for d in dates_list:
        daily_data_map[d] = get_teacher_daily_attendance_data(teachers, d, active_year, current_dt)

    teacher_rows = []
    total_scheduled_accum = 0
    total_recorded_accum = 0
    total_unrecorded_accum = 0

    for teacher in teachers:
        t_id = teacher.id
        scheduled_hours = 0
        recorded_hours = 0
        unrecorded_hours = 0
        unrecorded_days_count = 0
        excused_days_count = 0
        teaching_days_count = 0
        day_by_day = {}

        for d in dates_list:
            d_data = daily_data_map[d]
            t_row = next((r for r in d_data['rows'] if r['teacher'].id == t_id), None)
            if t_row:
                day_by_day[d] = t_row
                s_cnt = t_row['scheduled_count']
                r_cnt = t_row['recorded_count']
                u_cnt = t_row['unrecorded_count']

                scheduled_hours += s_cnt
                recorded_hours += r_cnt
                unrecorded_hours += u_cnt

                if s_cnt > 0:
                    teaching_days_count += 1
                    if t_row['daily_status'] == 'EXCUSED_LEAVE':
                        excused_days_count += 1
                    elif u_cnt > 0:
                        unrecorded_days_count += 1

        compliance_rate = round((recorded_hours / scheduled_hours * 100), 1) if scheduled_hours > 0 else 100.0

        # Estimated deduction disabled
        estimated_deduction = Decimal('0.00')

        total_scheduled_accum += scheduled_hours
        total_recorded_accum += recorded_hours
        total_unrecorded_accum += unrecorded_hours

        teacher_rows.append({
            'teacher': teacher,
            'scheduled_hours': scheduled_hours,
            'recorded_hours': recorded_hours,
            'unrecorded_hours': unrecorded_hours,
            'teaching_days_count': teaching_days_count,
            'unrecorded_days_count': unrecorded_days_count,
            'excused_days_count': excused_days_count,
            'compliance_rate': compliance_rate,
            'estimated_deduction': estimated_deduction,
            'day_by_day': day_by_day,
            'has_unrecorded': unrecorded_hours > 0,
            'is_perfect': (scheduled_hours > 0 and unrecorded_hours == 0),
            'no_schedule': (scheduled_hours == 0),
        })

    overall_compliance_rate = round(
        (total_recorded_accum / total_scheduled_accum * 100), 1
    ) if total_scheduled_accum > 0 else 100.0

    summary_stats = {
        'total_teachers': len(teachers),
        'total_teaching_dates': len(dates_list),
        'total_scheduled_hours': total_scheduled_accum,
        'total_recorded_hours': total_recorded_accum,
        'total_unrecorded_hours': total_unrecorded_accum,
        'overall_compliance_rate': overall_compliance_rate,
        'teachers_with_unrecorded': sum(1 for r in teacher_rows if r['has_unrecorded']),
        'teachers_perfect': sum(1 for r in teacher_rows if r['is_perfect']),
        'teachers_no_schedule': sum(1 for r in teacher_rows if r['no_schedule']),
    }

    return {
        'start_date': start_date,
        'end_date': end_date,
        'dates_list': dates_list,
        'rows': teacher_rows,
        'summary': summary_stats,
        'daily_data_map': daily_data_map,
    }


def sync_teacher_attendance_from_student_logs(target_date, active_year=None, current_dt=None):
    """
    Synchronizes TeacherAttendance model records for target_date based on student attendance submission logs.
    
    Rules:
    - If teacher has scheduled classes and unrecorded_count > 0 -> UNEXCUSED_ABSENCE
    - If teacher has scheduled classes and unrecorded_count == 0 -> PRESENT
    - If existing record is EXCUSED_LEAVE, preserves EXCUSED_LEAVE.
    """
    teachers = Teacher.objects.filter(status='ACTIVE')
    daily_res = get_teacher_daily_attendance_data(teachers, target_date, active_year, current_dt)
    
    synced_count = 0
    for row in daily_res['rows']:
        teacher = row['teacher']
        existing_att = row['existing_att']

        # Don't overwrite explicit EXCUSED_LEAVE
        if existing_att and existing_att.status == TeacherAttendance.Status.EXCUSED_LEAVE:
            continue

        if row['scheduled_count'] > 0:
            if row['unrecorded_count'] > 0:
                new_status = TeacherAttendance.Status.UNEXCUSED_ABSENCE
                notes = f"មិនបានចុះវត្តមានសិស្សចំនួន {row['unrecorded_count']}/{row['scheduled_count']} ម៉ោង (ស្វ័យប្រវត្តិ)"
            else:
                new_status = TeacherAttendance.Status.PRESENT
                notes = f"បានចុះវត្តមានសិស្សគ្រប់ {row['scheduled_count']} ម៉ោង"

            att_obj, created = TeacherAttendance.objects.update_or_create(
                teacher=teacher,
                date=target_date,
                defaults={
                    'status': new_status,
                    'notes': notes,
                }
            )
            synced_count += 1

    return synced_count


def get_teacher_emergency_leave_schedule(teacher, current_dt=None):
    """
    Evaluates timetable teaching schedule for a teacher on TODAY and TOMORROW.
    Returns available emergency dates with schedule info and cutoff validation.
    """
    from apps.academics.models import Timetable
    from apps.academics.utils import get_active_academic_year
    from apps.teachers.models import TeacherAttendanceConfig
    from datetime import time as dtime

    if current_dt is None:
        current_dt = datetime.now()

    current_date = current_dt.date()
    current_time = current_dt.time()
    tomorrow_date = current_date + timedelta(days=1)

    config = TeacherAttendanceConfig.get_settings()
    cutoff_time = config.emergency_leave_cutoff_time or dtime(17, 0)
    cutoff_str = cutoff_time.strftime('%H:%M')
    active_year = get_active_academic_year()

    today_dow = current_date.isoweekday()
    tomorrow_dow = tomorrow_date.isoweekday()

    options = []

    # 1. Evaluate TODAY (Same day)
    today_qs = Timetable.objects.filter(teacher=teacher, day_of_week=today_dow)
    if active_year:
        today_qs = today_qs.filter(classroom__academic_year=active_year)
    
    today_slots = list(today_qs.select_related('classroom', 'subject'))
    if today_slots:
        is_past_cutoff = (current_time > cutoff_time)
        day_kh = today_slots[0].get_day_of_week_display().split('/')[0].strip()
        classes_summary = ", ".join([f"{s.classroom.name} ({s.subject.name_kh})" for s in today_slots])
        options.append({
            'date': current_date,
            'date_str': current_date.strftime('%Y-%m-%d'),
            'label': f"ថ្ងៃនេះ - {day_kh} ({current_date.strftime('%d/%m/%Y')})",
            'is_today': True,
            'slots_count': len(today_slots),
            'classes_summary': classes_summary,
            'is_allowed': not is_past_cutoff,
            'blocked_reason': f"ហួសម៉ោងកំណត់ {cutoff_str} រសៀល" if is_past_cutoff else None
        })

    # 2. Evaluate TOMORROW (1 day advance)
    tomorrow_qs = Timetable.objects.filter(teacher=teacher, day_of_week=tomorrow_dow)
    if active_year:
        tomorrow_qs = tomorrow_qs.filter(classroom__academic_year=active_year)
    
    tomorrow_slots = list(tomorrow_qs.select_related('classroom', 'subject'))
    if tomorrow_slots:
        is_past_cutoff = (current_time > cutoff_time)
        day_kh = tomorrow_slots[0].get_day_of_week_display().split('/')[0].strip()
        classes_summary = ", ".join([f"{s.classroom.name} ({s.subject.name_kh})" for s in tomorrow_slots])
        options.append({
            'date': tomorrow_date,
            'date_str': tomorrow_date.strftime('%Y-%m-%d'),
            'label': f"ថ្ងៃស្អែក - {day_kh} ({tomorrow_date.strftime('%d/%m/%Y')})",
            'is_today': False,
            'slots_count': len(tomorrow_slots),
            'classes_summary': classes_summary,
            'is_allowed': not is_past_cutoff,
            'blocked_reason': f"ហួសម៉ោងកំណត់ {cutoff_str} រសៀល" if is_past_cutoff else None
        })

    return {
        'options': options,
        'cutoff_time': cutoff_time,
        'cutoff_str': cutoff_str,
        'has_available_dates': any(opt['is_allowed'] for opt in options),
    }

