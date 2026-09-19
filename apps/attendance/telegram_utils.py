import re
import logging
from datetime import datetime, date
from django.db.models import Count, Q
from apps.accounts.utils import send_telegram_notification
from apps.accounts.models import TelegramConfig
from apps.attendance.models import StudentAttendance, AttendanceSubmissionLog, AttendanceSetting
from apps.academics.models import Classroom, AcademicYear
from apps.teachers.models import Teacher, TeacherAttendance, TeacherLeaveRequest
from apps.teachers.utils import get_teacher_daily_attendance_data

logger = logging.getLogger(__name__)


def to_khmer_numeral(num):
    """
    Converts numbers or digit strings into Khmer numerals (0-9 -> ០-៩).
    E.g. 1 -> '១', 3 -> '៣', 10 -> '១០'.
    """
    if num is None:
        return ""
    khmer_digits = {
        '0': '០', '1': '១', '2': '២', '3': '៣', '4': '៤',
        '5': '៥', '6': '៦', '7': '៧', '8': '៨', '9': '៩'
    }
    return ''.join(khmer_digits.get(c, c) for c in str(num))


def natural_classroom_sort_key(cls):
    """
    Strict natural sort key for ordering classrooms sequentially:
    7A, 7B, 7C, 7D, 8A, 8B, 8C, ..., 12A, 12B, ...
    Accepts a Classroom instance or a string code/name.
    """
    grade = getattr(cls, 'grade_level', None)
    raw = getattr(cls, 'clean_code', None) or getattr(cls, 'code', None) or getattr(cls, 'name', None) or str(cls)
    c_str = str(raw).strip()

    # Strip common Khmer classroom prefixes
    for pfx in ['ថ្នាក់ទី', 'ថ្នាក់ ទី', 'ថ្នាក់', 'ថ្នាក់ ']:
        if c_str.startswith(pfx):
            c_str = c_str[len(pfx):].strip()

    # Extract leading grade number if grade_level is not already set or 0
    m = re.search(r'(\d+)', c_str)
    if (grade is None or grade == 0) and m:
        grade = int(m.group(1))
    elif grade is None:
        grade = 999

    # Split remaining into numeric chunks and uppercase strings for natural collation
    chunks = [int(t) if t.isdigit() else t.upper() for t in re.split(r'(\d+)', c_str) if t]
    return (grade, chunks, getattr(cls, 'id', 0))


def sort_khmer_attendance_records(records):
    """
    Sorts attendance records alphabetically by Khmer name from ក to អ (U+1780 to U+17A2).
    If Khmer names match, secondary sort is by student ID.
    """
    def _sort_key(r):
        student = getattr(r, 'student', None)
        if not student:
            return ("", "")
        k_name = (student.khmer_name or (student.user.get_full_name() if getattr(student, 'user', None) else '') or '').strip()
        sid = str(getattr(student, 'student_id', '') or '')
        return (k_name, sid)

    return sorted(records, key=_sort_key)


def format_student_absence_telegram_message(classroom, target_date, session='MORNING', period_number=None, records=None, teacher_name=None, footer_text=None):
    """
    Builds the official Telegram student absence notification format:

    ⚠️ ការជូនដំណឹងអវត្តមានសិស្ស
    📅 ថ្ងៃទី៖ 01/08/2026
    ⏰ ម៉ោងទី៖ ទី៣ (ព្រឹក)
    🏫 ថ្នាក់រៀន៖ 7D
    👤 ឈ្មោះគ្រូ៖ ចេង បុណ្ណាវុធ

    បញ្ជីសិស្សអវត្តមាន៖
    ១. 26343-គឹមលី ស្រីណែត  (ឥតច្បាប់)
    ២. 26354-ចាន់ថា លីហ្សា   (ឥតច្បាប់)
    ...
    ៦. 26540-ពិសិដ្ឋ វិសុត 🟡 (ច្បាប់)

    ℹ️ សូមគ្រូបន្ទុកថ្នាក់ជ្រាបជាព័ត៌មាន។
    """
    if isinstance(target_date, (datetime, date)):
        date_str = target_date.strftime('%d/%m/%Y')
    else:
        date_str = str(target_date)

    p_num_int = int(period_number) if period_number and str(period_number).isdigit() else None
    if session == 'AFTERNOON':
        session_label = "រសៀល"
    elif session == 'MORNING':
        session_label = "ព្រឹក"
    else:
        session_label = "រសៀល" if (p_num_int and p_num_int > 4) else "ព្រឹក"

    if p_num_int:
        period_text = f"ទី{to_khmer_numeral(p_num_int)} ({session_label})"
    else:
        period_text = f"ពេល{session_label}"

    # Classroom display code
    class_display = getattr(classroom, 'clean_code', None) or getattr(classroom, 'code', None) or getattr(classroom, 'name', '')
    for pfx in ['ថ្នាក់ទី', 'ថ្នាក់ ទី', 'ថ្នាក់', 'ថ្នាក់ ']:
        if class_display.startswith(pfx):
            class_display = class_display[len(pfx):].strip()

    # Teacher display name
    if not teacher_name:
        first_rec = records[0] if records else None
        if first_rec and getattr(first_rec, 'recorded_by', None):
            teacher_name = first_rec.recorded_by.display_name or first_rec.recorded_by.get_full_name()
        elif getattr(classroom, 'homeroom_teacher', None):
            teacher_name = classroom.homeroom_teacher.display_name or classroom.homeroom_teacher.khmer_name
        else:
            teacher_name = "មិនបានបញ្ជាក់"

    msg_lines = [
        "⚠️ ការជូនដំណឹងអវត្តមានសិស្ស",
        f"📅 ថ្ងៃទី៖ {date_str}",
        f"⏰ ម៉ោងទី៖ {period_text}",
        f"🏫 ថ្នាក់រៀន៖ {class_display}",
        f"👤 ឈ្មោះគ្រូ៖ {teacher_name}",
        "",
        "បញ្ជីសិស្សអវត្តមាន៖",
    ]

    absent_records = []
    if records:
        absent_records = [
            r for r in records
            if r.status in [StudentAttendance.Status.ABSENT, StudentAttendance.Status.PERMISSION, StudentAttendance.Status.LATE]
        ]

    if not absent_records:
        msg_lines.append("🎉 គ្មានសិស្សអវត្តមានទេ (វត្តមាន ១០០%)")
    else:
        # Sort alphabetically from ក to អ
        sorted_records = sort_khmer_attendance_records(absent_records)
        for idx, r in enumerate(sorted_records, 1):
            kh_idx = to_khmer_numeral(idx)
            sid = f"{r.student.student_id}-" if getattr(r.student, 'student_id', None) else ""
            sname = (r.student.khmer_name or (r.student.user.get_full_name() if getattr(r.student, 'user', None) else "") or "").strip()

            if r.status == StudentAttendance.Status.ABSENT:
                tag = f"  (ឥតច្បាប់ - {r.notes})" if r.notes else "  (ឥតច្បាប់)"
            elif r.status == StudentAttendance.Status.PERMISSION:
                tag = f" 🟡 (ច្បាប់ - {r.notes})" if r.notes else " 🟡 (ច្បាប់)"
            elif r.status == StudentAttendance.Status.LATE:
                tag = f" ⏰ (មកយឺត - {r.notes})" if r.notes else " ⏰ (មកយឺត)"
            else:
                tag = ""
            msg_lines.append(f"{kh_idx}. {sid}{sname}{tag}")

    msg_lines.append("")
    msg_lines.append(footer_text or "ℹ️ សូមគ្រូបន្ទុកថ្នាក់ជ្រាបជាព័ត៌មាន។")

    return "\n".join(msg_lines)


def send_classroom_attendance_telegram(classroom, target_date, session='MORNING', period_number=None, custom_chat_id=None, sender_user=None):
    """
    Formats and sends the student absence notification for a specific classroom and period/session to Telegram.
    Student absence list is sorted alphabetically in Khmer order from ក to អ with Khmer numbering.
    Dispatches to:
    1. custom_chat_id or classroom.telegram_chat_id or TelegramConfig.chat_id
    2. Group គ្រូបន្ទុកថ្នាក់ (settings.homeroom_group_chat_id)
    3. Custom dispatch groups (settings.custom_dispatch_groups)
    """
    config = TelegramConfig.objects.first()
    settings = AttendanceSetting.get_settings()

    primary_chat_id = custom_chat_id or classroom.telegram_chat_id or (config.chat_id if config else None)
    if not primary_chat_id and not settings.homeroom_group_chat_id:
        return {
            'success': False,
            'message': f'ពុំទាន់មាន Telegram Chat ID សម្រាប់ថ្នាក់ {classroom.name} ឬ Group គ្រូបន្ទុកថ្នាក់នៅឡើយទេ។ សូមកំណត់ Chat ID ជាមុនសិន!'
        }

    # Fetch attendance records
    atts_qs = StudentAttendance.objects.filter(
        classroom=classroom,
        date=target_date,
        session=session
    ).select_related('student', 'subject', 'recorded_by')

    if period_number:
        atts_qs = atts_qs.filter(period_number=period_number)

    records = list(atts_qs)

    first_rec = records[0] if records else None
    teacher_name = None
    if first_rec and getattr(first_rec, 'recorded_by', None):
        teacher_name = first_rec.recorded_by.display_name or first_rec.recorded_by.get_full_name()
    elif classroom.homeroom_teacher:
        teacher_name = classroom.homeroom_teacher.display_name or classroom.homeroom_teacher.khmer_name

    message = format_student_absence_telegram_message(
        classroom=classroom,
        target_date=target_date,
        session=session,
        period_number=period_number,
        records=records,
        teacher_name=teacher_name
    )

    # Collect destination chat IDs
    dest_chats = []
    if primary_chat_id:
        for cid in str(primary_chat_id).split(','):
            cid = cid.strip()
            if cid and cid not in dest_chats:
                dest_chats.append(cid)

    # Also notify Group គ្រូបន្ទុកថ្នាក់ if configured
    if settings.homeroom_group_chat_id:
        for cid in str(settings.homeroom_group_chat_id).split(','):
            cid = cid.strip()
            if cid and cid not in dest_chats:
                dest_chats.append(cid)

    # Also notify custom groups if configured
    if getattr(settings, 'custom_dispatch_groups', None):
        for cid in str(settings.custom_dispatch_groups).split(','):
            cid = cid.strip()
            if cid and cid not in dest_chats:
                dest_chats.append(cid)

    last_log = None
    for chat_id in dest_chats:
        last_log = send_telegram_notification(
            title="",
            message=message,
            recipient_name=f"ថ្នាក់ {classroom.clean_code or classroom.name}",
            recipient_type="Classroom Telegram",
            custom_chat_id=chat_id,
            raw_mode=True
        )

    return {
        'success': True,
        'chat_id': ", ".join(dest_chats),
        'log_id': last_log.id if last_log else None,
        'status': last_log.status if last_log else 'SENT',
        'message': f'បានផ្ញើការជូនដំណឹងអវត្តមានថ្នាក់ {classroom.clean_code or classroom.name} ទៅកាន់ Telegram ដោយជោគជ័យ!'
    }


def send_hourly_period_absence_dispatch(target_date, period_number, session=None, sender_user=None, force=False):
    """
    Automated Hourly Absence Dispatch System for a specific period (P1-P8):
    1. Classrooms are strictly sorted in sequential order: 7A, 7B, 7C, 7D, ..., 12A, 12B, ...
    2. Direct Guardians: Instant direct alerts to parents of absent/permission/late students.
    3. Group គ្រូបន្ទុកថ្នាក់ & Custom Groups: Dispatched classroom-by-classroom in strict 7A...12B order.
    4. Homeroom Teachers & Class Groups: Formatted classroom absence notice sorted from ក to អ.
    5. Management Group: Dispatched in 7A...12B order and overall schoolwide summary.
    """
    settings = AttendanceSetting.get_settings()
    config = TelegramConfig.objects.first()

    if not settings.hourly_dispatch_enabled and not force:
        return {'success': False, 'message': 'ការផ្ញើអវត្តមានស្វ័យប្រវត្តិតាមម៉ោងត្រូវបានបិទ (Hourly Dispatch Disabled)។'}

    period_num_int = int(period_number) if str(period_number).isdigit() else 1
    if session is None:
        session = 'MORNING' if period_num_int <= 4 else 'AFTERNOON'

    date_str = target_date.strftime('%d/%m/%Y')
    session_str = "ពេលព្រឹក (Morning)" if session == 'MORNING' else "ពេលរសៀល (Afternoon)"

    # 1. Fetch classrooms and sort strictly in natural order starting from 7A, 7B, ..., 12A, 12B, ...
    active_year = AcademicYear.objects.filter(is_current=True).first()
    classrooms_qs = Classroom.objects.all().select_related('homeroom_teacher', 'homeroom_teacher__user')
    if active_year:
        classrooms_qs = classrooms_qs.filter(academic_year=active_year)
    classrooms = list(classrooms_qs)
    classrooms.sort(key=natural_classroom_sort_key)

    # 2. Fetch all student attendance records for this period & date
    records_qs = StudentAttendance.objects.filter(
        date=target_date,
        session=session,
        period_number=period_num_int
    ).select_related('student', 'classroom', 'subject', 'recorded_by')

    records_by_class = {}
    for rec in records_qs:
        records_by_class.setdefault(rec.classroom_id, []).append(rec)

    total_absent_all = 0
    total_permission_all = 0
    total_late_all = 0
    guardian_sent_count = 0
    homeroom_sent_count = 0
    group_sent_count = 0
    management_sent_count = 0

    class_reports = []

    # Prepare shared destination groups: Group គ្រូបន្ទុកថ្នាក់ and custom groups
    shared_group_targets = []
    if getattr(settings, 'homeroom_group_chat_id', None):
        for cid in str(settings.homeroom_group_chat_id).split(','):
            cid = cid.strip()
            if cid and cid not in shared_group_targets:
                shared_group_targets.append(cid)

    if getattr(settings, 'custom_dispatch_groups', None):
        for cid in str(settings.custom_dispatch_groups).split(','):
            cid = cid.strip()
            if cid and cid not in shared_group_targets:
                shared_group_targets.append(cid)

    # 3. Process each classroom in strict 7A, 7B, ..., 12A, 12B, ... order
    for cls in classrooms:
        cls_records = records_by_class.get(cls.id, [])
        if not cls_records:
            continue

        absents = [r for r in cls_records if r.status == StudentAttendance.Status.ABSENT]
        permissions = [r for r in cls_records if r.status == StudentAttendance.Status.PERMISSION]
        lates = [r for r in cls_records if r.status == StudentAttendance.Status.LATE]

        total_absent_all += len(absents)
        total_permission_all += len(permissions)
        total_late_all += len(lates)

        total_absent_class = len(absents) + len(permissions) + len(lates)

        class_reports.append({
            'classroom': cls,
            'absents': absents,
            'permissions': permissions,
            'lates': lates,
            'total_absent_class': total_absent_class,
            'first_rec': cls_records[0] if cls_records else None
        })

        # --- (A) Send to Direct Guardians (អាណាព្យាបាលផ្ទាល់) ---
        if settings.dispatch_to_guardians:
            for r in cls_records:
                if r.status in [StudentAttendance.Status.ABSENT, StudentAttendance.Status.PERMISSION, StudentAttendance.Status.LATE]:
                    student = r.student
                    parent_chat = getattr(student, 'telegram_chat_id', None)
                    if parent_chat:
                        status_kh = "អវត្តមានឥតច្បាប់ (Absent)" if r.status == StudentAttendance.Status.ABSENT else ("អវត្តមានមានច្បាប់ (Permission)" if r.status == StudentAttendance.Status.PERMISSION else "មកយឺត (Late)")
                        status_icon = "❌" if r.status == StudentAttendance.Status.ABSENT else ("🟡" if r.status == StudentAttendance.Status.PERMISSION else "⏰")
                        msg = (
                            f"សួស្តីលោក/លោកស្រីអាណាព្យាបាលសិស្ស *{student.khmer_name}*!\n\n"
                            f"🏫 *ថ្នាក់រៀន:* {cls.clean_code or cls.name}\n"
                            f"📅 *កាលបរិច្ឆេទ:* {date_str} (ម៉ោងទី {period_num_int})\n"
                            f"📚 *មុខវិជ្ជា:* {r.subject.name_kh if r.subject else 'មុខវិជ្ជាប្រចាំម៉ោង'}\n"
                            f"{status_icon} *ស្ថានភាពវត្តមាន:* {status_kh}\n"
                        )
                        if r.notes:
                            msg += f"💬 *កំណត់សម្គាល់:* {r.notes}\n"
                        msg += f"\n_សេចក្តីជូនដំណឹងស្វ័យប្រវត្តិតាមម៉ោងពីសាលារៀន_"

                        send_telegram_notification(
                            title=f"⚠️ សេចក្តីជូនដំណឹងវត្តមានសិស្ស: {student.khmer_name}",
                            message=msg,
                            recipient_name=student.father_name or student.mother_name or student.khmer_name,
                            recipient_phone=student.father_phone or student.phone,
                            recipient_type="Parent",
                            custom_chat_id=parent_chat
                        )
                        guardian_sent_count += 1

        # Format student absence message for this classroom (sorted from ក to អ with Khmer numbers)
        cls_absence_msg = format_student_absence_telegram_message(
            classroom=cls,
            target_date=target_date,
            session=session,
            period_number=period_num_int,
            records=cls_records
        )

        # --- (B) Send to Homeroom Teachers & Class Group (គ្រូបន្ទុកថ្នាក់ & Group ថ្នាក់) ---
        if settings.dispatch_to_homeroom:
            homeroom_chat = cls.telegram_chat_id
            if not homeroom_chat and cls.homeroom_teacher:
                homeroom_chat = getattr(cls.homeroom_teacher, 'telegram_chat_id', None)
                if not homeroom_chat and getattr(cls.homeroom_teacher, 'user', None):
                    homeroom_chat = getattr(cls.homeroom_teacher.user, 'telegram_chat_id', None)

            if homeroom_chat:
                send_telegram_notification(
                    title="",
                    message=cls_absence_msg,
                    recipient_name=f"ថ្នាក់ {cls.clean_code or cls.name}",
                    recipient_type="Classroom / Homeroom",
                    custom_chat_id=homeroom_chat,
                    raw_mode=True
                )
                homeroom_sent_count += 1

        # --- (C) Send to Group គ្រូបន្ទុកថ្នាក់ & Custom Groups (in strict 7A...12B order) ---
        # Dispatches classroom absence notices to shared groups (for classes with absences, or if forced)
        if shared_group_targets and (total_absent_class > 0 or force):
            for g_chat in shared_group_targets:
                send_telegram_notification(
                    title="",
                    message=cls_absence_msg,
                    recipient_name="Group គ្រូបន្ទុកថ្នាក់ / Custom Group",
                    recipient_type="Homeroom Group",
                    custom_chat_id=g_chat,
                    raw_mode=True
                )
                group_sent_count += 1

    # --- (D) Send to Management Telegram Group ---
    if settings.dispatch_to_management:
        mgmt_targets = []
        if settings.management_chat_id:
            for cid in str(settings.management_chat_id).split(','):
                cid = cid.strip()
                if cid and cid not in mgmt_targets:
                    mgmt_targets.append(cid)
        if not mgmt_targets and not shared_group_targets and config and config.chat_id:
            mgmt_targets.append(config.chat_id)

        if mgmt_targets:
            master_lines = [
                f"📢 *របាយការណ៍អវត្តមានសិស្សប្រចាំម៉ោងទី {period_num_int}*",
                f"📅 *កាលបរិច្ឆេទ:* {date_str} ({session_str})",
                f"━━━━━━━━━━━━━━━━━━━━",
                f"📊 *ស្ថិតិរួមទូទាំងសាលា:*",
                f"• សិស្សអវត្តមានឥតច្បាប់ (Absent): *{total_absent_all}* នាក់",
                f"• សិស្សសុំច្បាប់ (Permission): *{total_permission_all}* នាក់",
                f"• សិស្សមកយឺត (Late): *{total_late_all}* នាក់",
                f"━━━━━━━━━━━━━━━━━━━━",
                f"📑 *បញ្ជីអវត្តមានតាមលំដាប់ថ្នាក់ (កម្រិត ៧ ដល់ ១២):*",
            ]

            if not class_reports:
                master_lines.append("\n🎉 *ពុំមានសិស្សអវត្តមានក្នុងម៉ោងនេះឡើយ (វត្តមាន ១០០%) ឬមិនទាន់មានការស្រង់វត្តមាន។*")
            else:
                for cr in class_reports:
                    c_cls = cr['classroom']
                    c_abs = cr['absents']
                    c_perm = cr['permissions']
                    c_late = cr['lates']

                    hr_name = c_cls.homeroom_teacher.khmer_name if c_cls.homeroom_teacher else "គ្មានគ្រូបន្ទុក"
                    c_display = c_cls.clean_code or c_cls.name
                    master_lines.append(f"\n🏫 *ថ្នាក់ {c_display}* (អវត្តមានសរុប: {cr['total_absent_class']} នាក់ • គ្រូបន្ទុក: {hr_name})")

                    counter = 1
                    all_abs = sort_khmer_attendance_records(c_abs + c_perm + c_late)
                    for r in all_abs:
                        sid_str = f"{r.student.student_id}-" if r.student.student_id else ""
                        sname = r.student.khmer_name or ""
                        if r.status == StudentAttendance.Status.ABSENT:
                            tag = "❌ ឥតច្បាប់"
                        elif r.status == StudentAttendance.Status.PERMISSION:
                            tag = f"🟡 មានច្បាប់ ({r.notes})" if r.notes else "🟡 មានច្បាប់"
                        else:
                            tag = "⏰ យឺត"
                        master_lines.append(f"  {to_khmer_numeral(counter)}. {sid_str}{sname} {tag}")
                        counter += 1

            master_msg = "\n".join(master_lines)
            for t_chat in mgmt_targets:
                send_telegram_notification(
                    title=f"របាយការណ៍អវត្តមានទូទាំងសាលា ម៉ោងទី {period_num_int}",
                    message=master_msg,
                    recipient_name="Management Group",
                    recipient_type="Management Group",
                    custom_chat_id=t_chat
                )
                management_sent_count += 1

    return {
        'success': True,
        'period_number': period_num_int,
        'guardian_sent_count': guardian_sent_count,
        'homeroom_sent_count': homeroom_sent_count,
        'group_sent_count': group_sent_count,
        'management_sent_count': management_sent_count,
        'total_absent': total_absent_all,
        'total_permission': total_permission_all,
        'total_late': total_late_all,
        'message': f"🚀 បានផ្ញើបញ្ជីអវត្តមានម៉ោងទី {period_num_int} ដោយជោគជ័យ! (អាណាព្យាបាល: {guardian_sent_count}, គ្រូបន្ទុក/ថ្នាក់: {homeroom_sent_count}, Group គ្រូបន្ទុកថ្នាក់: {group_sent_count}, គណៈគ្រប់គ្រង: {management_sent_count})"
    }



def format_classroom_display_code(classroom):
    """
    Formats classroom code into the style '8 (A)', '11 (F)', '11 (H)', etc.
    as displayed in the teacher absence notification.
    """
    if not classroom:
        return ""
    raw = getattr(classroom, 'clean_code', None) or getattr(classroom, 'code', None) or getattr(classroom, 'name', None) or str(classroom)
    c_str = str(raw).strip()
    for pfx in ['ថ្នាក់ទី', 'ថ្នាក់ ទី', 'ថ្នាក់', 'ថ្នាក់ ']:
        if c_str.startswith(pfx):
            c_str = c_str[len(pfx):].strip()

    # Matches patterns like '8A', '8 (A)', '8-A', '11F', '11 (H)'
    m = re.match(r'^(\d+)\s*[-_]?\s*(?:\(?([A-Za-z0-9\-_]+)\)?)?$', c_str)
    if m:
        grade_num = m.group(1)
        sec = m.group(2)
        if sec:
            return f"{grade_num} ({sec.upper()})"
        return grade_num

    grade = getattr(classroom, 'grade_level', None)
    if grade:
        letters = re.findall(r'[A-Za-z]+', c_str)
        if letters:
            return f"{grade} ({letters[0].upper()})"
        return str(grade)

    return c_str


def format_teacher_absence_telegram_message(unrec_items, target_date, period_number=None, session=None, footer_text=None):
    """
    Builds the official Telegram teacher absence notification format for teachers
    who have not submitted student attendance on time (after 30 minutes of class start):

    ⚠️ ការជូនដំណឹងអវត្តមានគ្រូ
    📅 ថ្ងៃទី៖ 22/07/2026
    ⏰ ម៉ោងទី៖ ទី៣ (រសៀល)

    ទី១៖
    👤 ឈ្មោះគ្រូ៖ ទូច សុខម៉េត
    🏫 បង្រៀនថ្នាក់ទី៖ 8 (A)

    ទី២៖
    👤 ឈ្មោះគ្រូ៖ សឿន សម្បត្តិ
    🏫 បង្រៀនថ្នាក់ទី៖ 11 (F)

    ទី៣៖
    👤 ឈ្មោះគ្រូ៖ ឈឿន លីឆាយ
    🏫 បង្រៀនថ្នាក់ទី៖ 11 (H)

    ℹ️ សូមបញ្ជាក់មូលហេតុសម្រាប់ម៉ោងនេះ។
    """
    if isinstance(target_date, (datetime, date)):
        date_str = target_date.strftime('%d/%m/%Y')
    else:
        date_str = str(target_date)

    p_num_int = int(period_number) if period_number and str(period_number).isdigit() else None
    if session == 'AFTERNOON':
        session_label = "រសៀល"
    elif session == 'MORNING':
        session_label = "ព្រឹក"
    else:
        session_label = "រសៀល" if (p_num_int and p_num_int > 4) else "ព្រឹក"

    if p_num_int:
        period_text = f"ទី{to_khmer_numeral(p_num_int)} ({session_label})"
    else:
        period_text = f"ពេល{session_label}"

    msg_lines = [
        "⚠️ ការជូនដំណឹងអវត្តមានគ្រូ",
        f"📅 ថ្ងៃទី៖ {date_str}",
        f"⏰ ម៉ោងទី៖ {period_text}",
        "",
    ]

    if not unrec_items:
        msg_lines.append("🎉 គ្មានគ្រូអវត្តមាន ឬខកខានស្រង់វត្តមានសិស្សឡើយ (១០០% គ្រប់ចំនួន)")
        msg_lines.append("")
        msg_lines.append("ℹ️ សូមគណៈគ្រប់គ្រងសាលាជ្រាបជាព័ត៌មាន។")
        return "\n".join(msg_lines)

    # Sort strictly by classroom starting from 7A, 7B, ..., 12A, 12B, ...
    def _teacher_absence_sort_key(item):
        cls = item.get('classroom')
        t = item.get('teacher')
        cls_key = natural_classroom_sort_key(cls)
        t_name = getattr(t, 'khmer_name', '') or getattr(t, 'display_name', '') or ''
        return (cls_key, t_name)

    sorted_items = sorted(unrec_items, key=_teacher_absence_sort_key)

    for idx, item in enumerate(sorted_items, 1):
        kh_idx = to_khmer_numeral(idx)
        teacher = item.get('teacher')
        classroom = item.get('classroom')
        t_name = (getattr(teacher, 'khmer_name', '') or getattr(teacher, 'display_name', '') or (teacher.user.get_full_name() if getattr(teacher, 'user', None) else '') or "មិនបានបញ្ជាក់").strip()
        cls_disp = format_classroom_display_code(classroom)

        msg_lines.append(f"ទី{kh_idx}៖")
        msg_lines.append(f"👤 ឈ្មោះគ្រូ៖ {t_name}")
        msg_lines.append(f"🏫 បង្រៀនថ្នាក់ទី៖ {cls_disp}")
        msg_lines.append("")

    msg_lines.append(footer_text or "ℹ️ សូមបញ្ជាក់មូលហេតុសម្រាប់ម៉ោងនេះ។")
    return "\n".join(msg_lines)


def send_missing_teachers_telegram(target_date, period_number=None, session=None, custom_chat_id=None, sender_user=None, current_dt=None):
    """
    Identifies teachers who have NOT submitted student attendance for scheduled teaching slots on target_date
    after the 30-minute grace window past class start time.
    Teachers on approved leave are excluded.
    Dispatches to:
    1. custom_chat_id (if provided)
    2. Management Telegram Group (settings.management_chat_id)
    3. Homeroom Teachers Group (settings.homeroom_group_chat_id)
    4. Custom Telegram Groups (settings.custom_dispatch_groups)
    5. Bot default chat ID
    Sorted strictly by classroom (7A, 7B, ..., 12A, 12B, ...).
    """
    settings = AttendanceSetting.get_settings()
    config = TelegramConfig.objects.first()

    teachers = Teacher.objects.filter(status='ACTIVE').order_by('teacher_id')
    att_data = get_teacher_daily_attendance_data(teachers, target_date, current_dt=current_dt)
    rows = att_data['rows']

    p_num_int = int(period_number) if period_number and str(period_number).isdigit() else None
    if session is None and p_num_int:
        session = 'MORNING' if p_num_int <= 4 else 'AFTERNOON'

    # Filter unrecorded slots
    unrec_items = []
    seen_slots = set()

    for r in rows:
        if r.get('daily_status') == 'EXCUSED_LEAVE':
            continue  # Exclude approved leaves

        teacher = r['teacher']
        for p_num, p_info in r.get('period_slots', {}).items():
            if p_info and p_info.get('status') == 'UNRECORDED':
                if p_num_int is None or p_num == p_num_int:
                    slot = p_info.get('slot')
                    cls = p_info.get('classroom')
                    key = (teacher.id, cls.id if cls else None, p_num)
                    if key not in seen_slots:
                        seen_slots.add(key)
                        unrec_items.append({
                            'teacher': teacher,
                            'classroom': cls,
                            'slot': slot,
                            'subject': p_info.get('subject'),
                            'period_number': p_num,
                        })

    # Sort strictly by classroom: 7A, 7B, ..., 12A, 12B, ...
    unrec_items.sort(key=lambda x: (natural_classroom_sort_key(x['classroom']), getattr(x['teacher'], 'khmer_name', '') or ''))

    message = format_teacher_absence_telegram_message(
        unrec_items=unrec_items,
        target_date=target_date,
        period_number=p_num_int,
        session=session
    )

    # Collect destination chat IDs
    dest_chats = []
    if custom_chat_id:
        for cid in str(custom_chat_id).split(','):
            cid = cid.strip()
            if cid and cid not in dest_chats:
                dest_chats.append(cid)

    if settings.management_chat_id:
        for cid in str(settings.management_chat_id).split(','):
            cid = cid.strip()
            if cid and cid not in dest_chats:
                dest_chats.append(cid)

    if getattr(settings, 'homeroom_group_chat_id', None):
        for cid in str(settings.homeroom_group_chat_id).split(','):
            cid = cid.strip()
            if cid and cid not in dest_chats:
                dest_chats.append(cid)

    if getattr(settings, 'custom_dispatch_groups', None):
        for cid in str(settings.custom_dispatch_groups).split(','):
            cid = cid.strip()
            if cid and cid not in dest_chats:
                dest_chats.append(cid)

    if not dest_chats and config and config.chat_id:
        dest_chats.append(config.chat_id)

    if not dest_chats:
        return {
            'success': False,
            'message': 'ពុំទាន់បានកំណត់ Telegram Chat ID សម្រាប់ទទួលការជូនដំណឹងអវត្តមានគ្រូនៅឡើយទេ។'
        }

    last_log = None
    for chat_id in dest_chats:
        last_log = send_telegram_notification(
            title="",
            message=message,
            recipient_name="Management / Telegram Groups",
            recipient_type="Teacher Absence Notification",
            custom_chat_id=chat_id,
            raw_mode=True
        )

    return {
        'success': True,
        'chat_id': ", ".join(dest_chats),
        'unrec_count': len(unrec_items),
        'log_id': last_log.id if last_log else None,
        'status': last_log.status if last_log else 'SENT',
        'message': f'បានផ្ញើការជូនដំណឹងអវត្តមានគ្រូ ({len(unrec_items)} នាក់) ទៅ Telegram ដោយជោគជ័យ!'
    }


def get_teacher_display_name(t):
    """
    Extracts clean Khmer display name for a Teacher instance, dictionary, or string.
    """
    if not t:
        return ""
    if isinstance(t, str):
        return t.strip()
    if isinstance(t, dict):
        return (t.get('name') or t.get('khmer_name') or t.get('display_name') or str(t)).strip()
    if hasattr(t, 'teacher'):
        t = t.teacher
    return (getattr(t, 'khmer_name', None) or getattr(t, 'display_name', None) or (t.user.get_full_name() if getattr(t, 'user', None) else '') or str(t)).strip()


def sort_khmer_teacher_entries(teachers):
    """
    Sorts teachers alphabetically by Khmer name from ក to អ (U+1780 to U+17A2)
    using Khmer linguistic collation.
    """
    import locale
    try:
        locale.setlocale(locale.LC_COLLATE, 'km_KH')
        col_key = locale.strxfrm
    except Exception:
        col_key = lambda s: s

    def _sort_key(t):
        name = get_teacher_display_name(t)
        return (col_key(name), name)

    return sorted(teachers, key=_sort_key)


def format_daily_teacher_absence_report_message(unrecorded_teachers, on_leave_teachers, target_date, footer_text=None):
    """
    Builds the official Telegram daily teacher absence report format:

    ⚠️ របាយការណ៍អវត្តមានគ្រូប្រចាំថ្ងៃ
    📅 ថ្ងៃទី៖ 22/07/2026

    ❌ គ្រូមិនបានបញ្ចូលអវត្តមាន៖
    ទី១៖ កាន ដាវី
    ទី២៖ ក្រឹង ចន្ធា
    ...
    ទី២៦៖ អេង រតនា

    🟡 គ្រូមានច្បាប់ឈប់សម្រាក៖
    ទី១៖ សុទ្ធ ចរិយា
    """
    if isinstance(target_date, (datetime, date)):
        date_str = target_date.strftime('%d/%m/%Y')
    else:
        date_str = str(target_date)

    msg_lines = [
        "⚠️ របាយការណ៍អវត្តមានគ្រូប្រចាំថ្ងៃ",
        f"📅 ថ្ងៃទី៖ {date_str}",
        "",
        "❌ គ្រូមិនបានបញ្ចូលអវត្តមាន៖",
    ]

    # Sort unrecorded teachers alphabetically by Khmer name (ក to អ)
    sorted_unrec = sort_khmer_teacher_entries(unrecorded_teachers)
    if sorted_unrec:
        for idx, t in enumerate(sorted_unrec, 1):
            kh_idx = to_khmer_numeral(idx)
            t_name = get_teacher_display_name(t)
            msg_lines.append(f"ទី{kh_idx}៖ {t_name}")
    else:
        msg_lines.append("🎉 គ្មានគ្រូខកខានស្រង់វត្តមានទេ (១០០% គ្រប់ចំនួន)")

    msg_lines.append("")
    msg_lines.append("🟡 គ្រូមានច្បាប់ឈប់សម្រាក៖")

    # Sort on-leave teachers alphabetically by Khmer name (ក to អ)
    sorted_leave = sort_khmer_teacher_entries(on_leave_teachers)
    if sorted_leave:
        for idx, t in enumerate(sorted_leave, 1):
            kh_idx = to_khmer_numeral(idx)
            t_name = get_teacher_display_name(t)
            msg_lines.append(f"ទី{kh_idx}៖ {t_name}")
    else:
        msg_lines.append("🎉 គ្មានគ្រូសុំច្បាប់សម្រាកទេ")

    if footer_text:
        msg_lines.append("")
        msg_lines.append(footer_text)

    return "\n".join(msg_lines)


def get_daily_teacher_absence_data(target_date=None, active_year=None, current_dt=None):
    """
    Evaluates attendance for all active teachers on target_date and groups them into:
    - unrecorded_teachers: Teachers who had scheduled teaching slots but did not submit attendance (and are not on approved leave)
    - on_leave_teachers: Teachers on approved leave (EXCUSED_LEAVE)
    Deduplicates teachers so each teacher appears only once.
    """
    if target_date is None:
        target_date = date.today()

    teachers = Teacher.objects.filter(status='ACTIVE').order_by('teacher_id')
    att_data = get_teacher_daily_attendance_data(teachers, target_date, active_year=active_year, current_dt=current_dt)
    rows = att_data.get('rows', [])

    unrecorded_map = {}
    on_leave_map = {}

    for r in rows:
        teacher = r['teacher']
        d_status = r.get('daily_status')

        if d_status == 'EXCUSED_LEAVE':
            on_leave_map[teacher.id] = teacher
            continue

        # Check if teacher has unrecorded periods
        unrec_slots = 0
        for p_num, p_info in r.get('period_slots', {}).items():
            if p_info and p_info.get('status') == 'UNRECORDED':
                unrec_slots += 1

        if unrec_slots > 0 or d_status == 'UNEXCUSED_ABSENCE':
            unrecorded_map[teacher.id] = teacher

    # Also check manual TeacherAttendance records for target_date
    manual_atts = TeacherAttendance.objects.filter(date=target_date)
    for ma in manual_atts:
        t = ma.teacher
        if ma.status == TeacherAttendance.Status.EXCUSED_LEAVE:
            on_leave_map[t.id] = t
            if t.id in unrecorded_map:
                del unrecorded_map[t.id]
        elif ma.status in [TeacherAttendance.Status.ABSENT, TeacherAttendance.Status.UNEXCUSED_ABSENCE]:
            if t.id not in on_leave_map:
                unrecorded_map[t.id] = t

    unrecorded_teachers = list(unrecorded_map.values())
    on_leave_teachers = list(on_leave_map.values())

    return {
        'unrecorded_teachers': sort_khmer_teacher_entries(unrecorded_teachers),
        'on_leave_teachers': sort_khmer_teacher_entries(on_leave_teachers),
        'total_unrecorded': len(unrecorded_teachers),
        'total_on_leave': len(on_leave_teachers),
    }


def send_daily_teacher_absence_telegram(
    target_date=None,
    custom_chat_id=None,
    send_to_management=True,
    send_to_homeroom_group=True,
    send_to_custom_groups=True,
    current_dt=None
):
    """
    Compiles and dispatches the daily teacher absence report (sorted alphabetically from ក to អ)
    to Telegram (Management, Homeroom Teachers Group, Custom Groups).
    """
    if target_date is None:
        target_date = date.today()

    settings = AttendanceSetting.get_settings()
    config = TelegramConfig.objects.first()

    dest_chats = []
    if custom_chat_id:
        for cid in str(custom_chat_id).split(','):
            cid = cid.strip()
            if cid and cid not in dest_chats:
                dest_chats.append(cid)

    if send_to_management and settings.management_chat_id:
        for cid in str(settings.management_chat_id).split(','):
            cid = cid.strip()
            if cid and cid not in dest_chats:
                dest_chats.append(cid)

    if send_to_homeroom_group and getattr(settings, 'homeroom_group_chat_id', None):
        for cid in str(settings.homeroom_group_chat_id).split(','):
            cid = cid.strip()
            if cid and cid not in dest_chats:
                dest_chats.append(cid)

    if send_to_custom_groups and getattr(settings, 'custom_dispatch_groups', None):
        for cid in str(settings.custom_dispatch_groups).split(','):
            cid = cid.strip()
            if cid and cid not in dest_chats:
                dest_chats.append(cid)

    if not dest_chats and config and config.chat_id:
        dest_chats.append(config.chat_id)

    if not dest_chats:
        return {
            'success': False,
            'message': 'ពុំទាន់បានកំណត់ Telegram Chat ID សម្រាប់ទទួលរបាយការណ៍អវត្តមានគ្រូប្រចាំថ្ងៃឡើយ។'
        }

    teacher_data = get_daily_teacher_absence_data(target_date=target_date, current_dt=current_dt)
    message = format_daily_teacher_absence_report_message(
        unrecorded_teachers=teacher_data['unrecorded_teachers'],
        on_leave_teachers=teacher_data['on_leave_teachers'],
        target_date=target_date
    )

    last_log = None
    sent_count = 0
    for chat_id in dest_chats:
        last_log = send_telegram_notification(
            title="",
            message=message,
            recipient_name="Management & Telegram Groups",
            recipient_type="Daily Teacher Absence Report",
            custom_chat_id=chat_id,
            raw_mode=True
        )
        sent_count += 1

    date_str = target_date.strftime('%d/%m/%Y') if isinstance(target_date, (datetime, date)) else str(target_date)
    return {
        'success': True,
        'target_date': date_str,
        'unrecorded_count': teacher_data['total_unrecorded'],
        'on_leave_count': teacher_data['total_on_leave'],
        'dest_chats': dest_chats,
        'log_id': last_log.id if last_log else None,
        'status': last_log.status if last_log else 'SENT',
        'message': f"បានផ្ញើរបាយការណ៍អវត្តមានគ្រូប្រចាំថ្ងៃ ({date_str}) [ខកខាន: {teacher_data['total_unrecorded']} នាក់, ច្បាប់: {teacher_data['total_on_leave']} នាក់] ទៅកាន់ Telegram ដោយជោគជ័យ!"
    }


def format_classroom_short_name(cls):
    """
    Returns clean classroom code/name without 'ថ្នាក់ទី' or 'ថ្នាក់' prefix.
    E.g. 'ថ្នាក់ទី 7B' -> '7B', '7B' -> '7B', 'ថ្នាក់ 11A' -> '11A'
    """
    if not cls:
        return ""
    raw = getattr(cls, 'clean_code', None) or getattr(cls, 'code', None) or getattr(cls, 'name', None) or str(cls)
    c_str = str(raw).strip()
    changed = True
    while changed:
        changed = False
        for pfx in ['ថ្នាក់ទី', 'ថ្នាក់ ទី', 'ថ្នាក់', 'ថ្នាក់ ']:
            if c_str.startswith(pfx):
                c_str = c_str[len(pfx):].strip()
                changed = True
    return c_str or str(cls)


def sort_khmer_student_entries(entries):
    """
    Sorts student entries or objects alphabetically by Khmer name (from ក to អ).
    Secondary sort is by student_id.
    Accepts dicts with 'name'/'khmer_name'/'student_id', Student objects, or Attendance records.
    """
    def _key(item):
        if isinstance(item, dict):
            name = item.get('name') or item.get('khmer_name') or ''
            sid = str(item.get('student_id') or item.get('id') or '')
        elif hasattr(item, 'student'):
            st = getattr(item, 'student', None)
            name = (getattr(st, 'khmer_name', None) or (st.user.get_full_name() if getattr(st, 'user', None) else '') or '') if st else ''
            sid = str(getattr(st, 'student_id', '') or '')
        elif hasattr(item, 'khmer_name'):
            name = getattr(item, 'khmer_name', '') or (item.user.get_full_name() if getattr(item, 'user', None) else '') or ''
            sid = str(getattr(item, 'student_id', '') or '')
        else:
            name = str(item)
            sid = ''
        return (name.strip(), sid)

    return sorted(entries, key=_key)


def format_daily_grade_student_absence_message(grade_level, classrooms_data, target_date, footer_text=None):
    """
    Builds the official Telegram daily student absence report for a specific grade level:

    ⚠️ របាយការណ៍អវត្តមានសិស្សប្រចាំថ្ងៃ - កម្រិតថ្នាក់ទី ៧
    📅 ថ្ងៃទី៖ 22/07/2026

    🏫 ថ្នាក់ 7B
    ១. 26398-នីន ដាលីស (១ពេល)
    ២. 26462-វ៉ែត ម៉ារីន (១ពេល)
    ៣. 26512-ឡិក គីមឡុង (១ពេល)

    🏫 ថ្នាក់ 7C
    ១. 26342-គឹម រចនា (១ពេល)
    ...
    """
    if isinstance(target_date, (datetime, date)):
        date_str = target_date.strftime('%d/%m/%Y')
    else:
        date_str = str(target_date)

    grade_khmer = to_khmer_numeral(grade_level)
    msg_lines = [
        f"⚠️ របាយការណ៍អវត្តមានសិស្សប្រចាំថ្ងៃ - កម្រិតថ្នាក់ទី {grade_khmer}",
        f"📅 ថ្ងៃទី៖ {date_str}",
    ]

    active_classrooms = []
    if classrooms_data:
        for item in classrooms_data:
            cls = item.get('classroom')
            students = item.get('students', [])
            if students:
                active_classrooms.append((cls, students))

    if not active_classrooms:
        msg_lines.append("")
        msg_lines.append("🎉 គ្មានសិស្សអវត្តមានទេ (វត្តមាន ១០០%)")
        if footer_text:
            msg_lines.append("")
            msg_lines.append(footer_text)
        return "\n".join(msg_lines)

    # Sort classrooms strictly: 7A, 7B, 7C, 7D...
    sorted_classrooms = sorted(active_classrooms, key=lambda x: natural_classroom_sort_key(x[0]))

    for cls, students in sorted_classrooms:
        cls_code = format_classroom_short_name(cls)
        msg_lines.append("")
        msg_lines.append(f"🏫 ថ្នាក់ {cls_code}")

        # Sort students alphabetically by Khmer name (from ក to អ)
        sorted_students = sort_khmer_student_entries(students)
        for idx, s in enumerate(sorted_students, 1):
            kh_idx = to_khmer_numeral(idx)
            sid = s.get('student_id') or s.get('id')
            sid_str = f"{sid}-" if sid else ""
            s_name = s.get('name') or s.get('khmer_name') or ""
            count = s.get('count', 1)
            count_kh = to_khmer_numeral(count)
            msg_lines.append(f"{kh_idx}. {sid_str}{s_name} ({count_kh}ពេល)")

    if footer_text:
        msg_lines.append("")
        msg_lines.append(footer_text)

    return "\n".join(msg_lines)


def get_daily_grade_student_absences(target_date, grade_level, active_year=None):
    """
    Collects absent/excused students for all classrooms of a given grade level on target_date.
    Classrooms are ordered sequentially: 7A, 7B, 7C, 7D...
    Each absent student is listed once with total missed sessions e.g. (១ពេល) or (២ពេល).
    Students are sorted alphabetically by Khmer name (ក to អ).
    """
    if active_year is None:
        active_year = AcademicYear.objects.filter(is_current=True).first()

    classrooms_qs = Classroom.objects.filter(grade_level=grade_level)
    if active_year:
        classrooms_qs = classrooms_qs.filter(academic_year=active_year)

    classrooms = sorted(classrooms_qs, key=natural_classroom_sort_key)
    result = []

    for cls in classrooms:
        records = StudentAttendance.objects.filter(
            classroom=cls,
            date=target_date,
            status__in=[StudentAttendance.Status.ABSENT, StudentAttendance.Status.PERMISSION, StudentAttendance.Status.LATE]
        ).select_related('student', 'student__user')

        if not records.exists():
            continue

        # Group by student
        student_groups = {}
        for r in records:
            st = r.student
            if not st:
                continue
            if st.id not in student_groups:
                student_groups[st.id] = {
                    'student': st,
                    'records': [],
                    'sessions': set(),
                }
            student_groups[st.id]['records'].append(r)
            sess = r.session
            if not sess and r.period_number:
                sess = 'MORNING' if r.period_number <= 4 else 'AFTERNOON'
            student_groups[st.id]['sessions'].add(sess or 'MORNING')

        student_list = []
        for st_id, data in student_groups.items():
            st = data['student']
            s_name = (st.khmer_name or (st.user.get_full_name() if getattr(st, 'user', None) else '') or '').strip()
            sid = str(getattr(st, 'student_id', '') or '')
            sess_count = len(data['sessions']) if data['sessions'] else 1
            student_list.append({
                'student': st,
                'student_id': sid,
                'name': s_name,
                'count': sess_count,
            })

        # Sort students alphabetically by Khmer name (ក to អ)
        sorted_students = sort_khmer_student_entries(student_list)
        if sorted_students:
            result.append({
                'classroom': cls,
                'students': sorted_students,
            })

    return result


def send_daily_grade_student_absence_telegram(
    target_date=None,
    grade_levels=None,
    custom_chat_id=None,
    send_to_homeroom_group=True,
    send_to_management=True,
    send_to_custom_groups=True,
    only_with_absences=True
):
    """
    Compiles and dispatches the daily student absence report by grade level
    from Grade 7 up to Grade 12 (ordered by classroom: 7A, 7B, ..., 12A, 12B, ... and sorted by student name).
    Each grade level is dispatched in its own dedicated message.
    """
    if target_date is None:
        target_date = date.today()

    if grade_levels is None:
        # Default Grades 7 to 12 as requested
        grade_levels = [7, 8, 9, 10, 11, 12]

    settings = AttendanceSetting.get_settings()
    config = TelegramConfig.objects.first()

    # Collect destination chats
    dest_chats = []
    if custom_chat_id:
        for cid in str(custom_chat_id).split(','):
            cid = cid.strip()
            if cid and cid not in dest_chats:
                dest_chats.append(cid)

    if send_to_management and settings.management_chat_id:
        for cid in str(settings.management_chat_id).split(','):
            cid = cid.strip()
            if cid and cid not in dest_chats:
                dest_chats.append(cid)

    if send_to_homeroom_group and getattr(settings, 'homeroom_group_chat_id', None):
        for cid in str(settings.homeroom_group_chat_id).split(','):
            cid = cid.strip()
            if cid and cid not in dest_chats:
                dest_chats.append(cid)

    if send_to_custom_groups and getattr(settings, 'custom_dispatch_groups', None):
        for cid in str(settings.custom_dispatch_groups).split(','):
            cid = cid.strip()
            if cid and cid not in dest_chats:
                dest_chats.append(cid)

    if not dest_chats and config and config.chat_id:
        dest_chats.append(config.chat_id)

    if not dest_chats:
        return {
            'success': False,
            'message': 'ពុំទាន់បានកំណត់ Telegram Chat ID សម្រាប់ទទួលរបាយការណ៍អវត្តមានសិស្សប្រចាំថ្ងៃឡើយ។'
        }

    active_year = AcademicYear.objects.filter(is_current=True).first()
    sent_grades = []
    total_messages_sent = 0
    total_absent_students = 0

    for grade in grade_levels:
        classrooms_data = get_daily_grade_student_absences(target_date, grade, active_year=active_year)
        student_count = sum(len(c['students']) for c in classrooms_data)

        if not classrooms_data and only_with_absences:
            continue

        message = format_daily_grade_student_absence_message(
            grade_level=grade,
            classrooms_data=classrooms_data,
            target_date=target_date
        )

        grade_sent_count = 0
        for chat_id in dest_chats:
            send_telegram_notification(
                title="",
                message=message,
                recipient_name=f"Telegram Group (Grade {grade})",
                recipient_type=f"Daily Absence Grade {grade}",
                custom_chat_id=chat_id,
                raw_mode=True
            )
            grade_sent_count += 1
            total_messages_sent += 1

        total_absent_students += student_count
        sent_grades.append({
            'grade': grade,
            'classrooms_count': len(classrooms_data),
            'students_count': student_count,
            'recipients_count': grade_sent_count
        })

    date_str = target_date.strftime('%d/%m/%Y') if isinstance(target_date, (datetime, date)) else str(target_date)
    return {
        'success': True,
        'target_date': date_str,
        'grades_sent': sent_grades,
        'total_messages_sent': total_messages_sent,
        'total_absent_students': total_absent_students,
        'dest_chats': dest_chats,
        'message': f"បានផ្ញើរបាយការណ៍អវត្តមានសិស្សប្រចាំថ្ងៃ ({date_str}) តាមកម្រិតថ្នាក់ ({len(sent_grades)} កម្រិត, សរុប {total_absent_students} នាក់) ទៅកាន់ Telegram ដោយជោគជ័យ!"
    }


def send_daily_summary_telegram(target_date=None, send_students=True, send_teachers=True, custom_chat_id=None, send_grade_reports=True):
    """
    Compiles and dispatches the daily school-wide student and teacher attendance summary digest,
    and dispatches the grade-by-grade student absence reports from Grade 7 up to Grade 12.
    """
    if target_date is None:
        target_date = date.today()

    settings = AttendanceSetting.get_settings()
    config = TelegramConfig.objects.first()
    target_chat_id = custom_chat_id or settings.management_chat_id or (config.chat_id if config else None)

    if not target_chat_id:
        return {'success': False, 'message': 'ពុំមាន Telegram Management Chat ID សម្រាប់ទទួលរបាយការណ៍សង្ខេបឡើយ។'}

    date_str = target_date.strftime('%d/%m/%Y')
    title = f"📊 របាយការណ៍សង្ខេបវត្តមានប្រចាំថ្ងៃ ({date_str})"
    
    msg_lines = [
        f"📋 *របាយការណ៍សង្ខេបវត្តមានសាលារៀនប្រចាំថ្ងៃ*",
        f"📅 *កាលបរិច្ឆេទ:* {date_str}",
        f"━━━━━━━━━━━━━━━━━━━━",
    ]

    # 1. Student Statistics
    if send_students:
        active_year = AcademicYear.objects.filter(is_current=True).first()
        classrooms = Classroom.objects.filter(academic_year=active_year) if active_year else Classroom.objects.all()
        
        st_atts = StudentAttendance.objects.filter(date=target_date)
        total_absent = st_atts.filter(status=StudentAttendance.Status.ABSENT).count()
        total_permission = st_atts.filter(status=StudentAttendance.Status.PERMISSION).count()
        total_late = st_atts.filter(status=StudentAttendance.Status.LATE).count()
        total_recorded_logs = AttendanceSubmissionLog.objects.filter(date=target_date).count()

        msg_lines.extend([
            f"🎓 *១. ស្ថិតិអវត្តមានសិស្ស (Student Attendance):*",
            f"• ចំនួនថ្នាក់រៀនសរុប: *{classrooms.count()}* ថ្នាក់",
            f"• ចំនួនវេន/ម៉ោងបានស្រង់រួច: *{total_recorded_logs}* លើក",
            f"• សិស្សអវត្តមានឥតច្បាប់ (Absent): *{total_absent}* នាក់",
            f"• សិស្សអវត្តមានមានច្បាប់ (Permission): *{total_permission}* នាក់",
            f"• សិស្សមកយឺត (Late): *{total_late}* នាក់",
            f"━━━━━━━━━━━━━━━━━━━━",
        ])

    # 2. Teacher Statistics
    if send_teachers:
        teachers = Teacher.objects.filter(status='ACTIVE')
        t_data = get_teacher_daily_attendance_data(teachers, target_date)
        summary = t_data['summary']

        msg_lines.extend([
            f"👨‍🏫 *២. ស្ថិតិការស្រង់វត្តមានរបស់គ្រូបង្រៀន (Teacher Compliance):*",
            f"• គ្រូមានម៉ោងបង្រៀនថ្ងៃនេះ: *{summary['teachers_with_schedule']}* នាក់",
            f"• គ្រូចុះវត្តមានបានពេញលេញ: *{summary['teachers_full_present']}* នាក់",
            f"• គ្រូខកខានមិនបានចុះវត្តមាន: *{summary['teachers_with_unrecorded']}* នាក់",
            f"• គ្រូសម្រាកមានច្បាប់: *{summary['teachers_on_leave']}* នាក់",
            f"• ម៉ោងបង្រៀនសរុប: *{summary['total_scheduled_periods']}* ម៉ោង",
            f"• ម៉ោងបានស្រង់វត្តមានរួច: *{summary['total_recorded_periods']}* ម៉ោង",
            f"• ម៉ោងខកខានមិនបានស្រង់: *{summary['total_unrecorded_periods']}* ម៉ោង",
            f"• អត្រាអនុវត្តរួម (Compliance Rate): *{summary['overall_compliance_rate']}%*",
            f"━━━━━━━━━━━━━━━━━━━━",
        ])

    msg_lines.append("🏫 _ប្រព័ន្ធគ្រប់គ្រងសាលារៀន (SchoolSM Automation)_")
    message = "\n".join(msg_lines)

    log = send_telegram_notification(
        title=title,
        message=message,
        recipient_name="គណៈគ្រប់គ្រងសាលា",
        recipient_type="Daily Digest Telegram",
        custom_chat_id=target_chat_id
    )

    # 3. Dispatches Grade-by-Grade Student Absence Reports (Grades 7 to 12)
    grade_report_res = None
    if send_students and send_grade_reports:
        grade_report_res = send_daily_grade_student_absence_telegram(
            target_date=target_date,
            grade_levels=[7, 8, 9, 10, 11, 12],
            custom_chat_id=custom_chat_id
        )

    # 4. Dispatches Daily Teacher Absence Report (Sorted Alphabetically from ក to អ)
    teacher_report_res = None
    if send_teachers:
        teacher_report_res = send_daily_teacher_absence_telegram(
            target_date=target_date,
            custom_chat_id=custom_chat_id
        )

    return {
        'success': True,
        'chat_id': target_chat_id,
        'log_id': log.id if log else None,
        'status': log.status if log else 'SENT',
        'grade_reports': grade_report_res,
        'teacher_reports': teacher_report_res,
        'message': f'បានផ្ញើរបាយការណ៍សង្ខេបប្រចាំថ្ងៃ ({date_str}), របាយការណ៍សិស្ស (៧-១២) និងរបាយការណ៍អវត្តមានគ្រូ ទៅកាន់ Telegram ដោយជោគជ័យ!'
    }


def format_teacher_leave_telegram_message(leave_request, approver_name=None):
    """
    Formats the complete markdown text for a teacher leave request notification.
    """
    t = leave_request.teacher
    title = f"📝 ពាក្យសុំច្បាប់របស់គ្រូបង្រៀន៖ {t.khmer_name}"
    
    status_icon = "⏳"
    if leave_request.status == 'APPROVED':
        status_icon = "✅"
    elif leave_request.status == 'REJECTED':
        status_icon = "❌"

    msg_lines = [
        f"🔔 *{title}*\n",
        f"👨‍🏫 *គ្រូបង្រៀន:* {t.khmer_name} (ID: {t.teacher_id})",
        f"📞 *លេខទូរស័ព្ទ:* `{t.phone or 'គ្មាន'}`",
        f"📋 *ប្រភេទច្បាប់:* {leave_request.get_leave_type_display()}",
        f"📅 *កាលបរិច្ឆេទ:* {leave_request.start_date.strftime('%d/%m/%Y')} ដល់ {leave_request.end_date.strftime('%d/%m/%Y')} ({leave_request.total_days} ថ្ងៃ)",
        f"💬 *មូលហេតុ:* {leave_request.reason}",
        f"📌 *ស្ថានភាព:* {status_icon} *{leave_request.get_status_display()}*",
    ]
    if approver_name:
        msg_lines.append(f"👤 *អនុម័ត/ពិនិត្យដោយ:* {approver_name}")
    elif leave_request.approved_by:
        msg_lines.append(f"👤 *អ្នកអនុម័ត:* {leave_request.approved_by.display_name}")
    
    if leave_request.rejection_reason:
        msg_lines.append(f"⚠️ *មូលហេតុបដិសេធ:* {leave_request.rejection_reason}")

    msg_lines.append("\n🏫 _ប្រព័ន្ធគ្រប់គ្រងសាលារៀន (SchoolSM)_")
    return "\n".join(msg_lines)


def send_teacher_leave_notification_telegram(leave_request, custom_chat_id=None):
    """
    Sends notification to management Telegram when a teacher applies for leave or when status changes.
    Attaches interactive inline buttons [Approve] and [Reject] for PENDING leave requests.
    """
    settings = AttendanceSetting.get_settings()
    config = TelegramConfig.objects.first()
    target_chat_id = custom_chat_id or settings.management_chat_id or (config.chat_id if config else None)

    if not target_chat_id:
        return {'success': False, 'message': 'ពុំមាន Management Chat ID សម្រាប់ផ្ញើដំណឹងច្បាប់គ្រូឡើយ។'}

    t = leave_request.teacher
    is_emergency = (leave_request.category == 'EMERGENCY')
    cat_label = "🚨 សុំច្បាប់ភ្លាមៗ (បន្ទាន់)" if is_emergency else "📅 សុំច្បាប់ទុកជាមុន (គ្រោងទុក)"
    title = f"{'🚨' if is_emergency else '📝'} ពាក្យ{cat_label}៖ {t.khmer_name}"
    
    status_icon = "⏳"
    if leave_request.status == 'APPROVED':
        status_icon = "✅"
    elif leave_request.status == 'REJECTED':
        status_icon = "❌"

    msg_lines = [
        f"🏷️ *ប្រភេទសំណើ:* *{cat_label}*",
        f"🔢 *លេខកូដលិខិត:* `{leave_request.leave_code or leave_request.id}`",
        f"👨‍🏫 *គ្រូបង្រៀន:* {t.khmer_name} (ID: {t.teacher_id})",
        f"📞 *លេខទូរស័ព្ទ:* `{t.phone}`",
        f"📋 *ប្រភេទច្បាប់:* {leave_request.get_leave_type_display()}",
        f"📅 *កាលបរិច្ឆេទ:* {leave_request.start_date.strftime('%d/%m/%Y')} ដល់ {leave_request.end_date.strftime('%d/%m/%Y')} ({leave_request.total_days} ថ្ងៃ)",
    ]
    if leave_request.substitute_teacher:
        st = leave_request.substitute_teacher
        msg_lines.append(f"🔄 *គ្រូជំនួស:* {st.khmer_name} (ID: {st.teacher_id} • 📞 `{st.phone}`)")

    if leave_request.is_proxy_application and leave_request.applied_by:
        proxy_str = f"👤 *ដាក់ពាក្យជំនួសដោយ:* {leave_request.applied_by.display_name} (Admin)"
        if leave_request.proxy_note:
            proxy_str += f" _({leave_request.proxy_note})_"
        msg_lines.append(proxy_str)
    
    msg_lines.extend([
        f"💬 *មូលហេតុ:* {leave_request.reason}",
        f"📌 *ស្ថានភាព:* {status_icon} *{leave_request.get_status_display()}*",
    ])


    if leave_request.approved_by:
        msg_lines.append(f"👤 *អ្នកអនុម័ត:* {leave_request.approved_by.display_name}")
    if leave_request.rejection_reason:
        msg_lines.append(f"⚠️ *មូលហេតុបដិសេធ:* {leave_request.rejection_reason}")

    # Attach interactive buttons for PENDING requests
    reply_markup = None
    if leave_request.status == 'PENDING':
        msg_lines.append("\n👇 *សូមជ្រើសរើសសកម្មភាពពិនិត្យផ្ទាល់លើ Telegram៖*")
        reply_markup = {
            "inline_keyboard": [
                [
                    {
                        "text": "✅ អនុម័ត (Approve)",
                        "callback_data": f"leave:approve:{leave_request.id}"
                    },
                    {
                        "text": "❌ បដិសេធ (Reject)",
                        "callback_data": f"leave:reject:{leave_request.id}"
                    }
                ]
            ]
        }

    message = "\n".join(msg_lines)

    log = send_telegram_notification(
        title=title,
        message=message,
        recipient_name=f"ច្បាប់គ្រូ {t.khmer_name}",
        recipient_type="Teacher Leave Telegram",
        custom_chat_id=target_chat_id,
        reply_markup=reply_markup
    )

    return {
        'success': True,
        'chat_id': target_chat_id,
        'message': f'បានផ្ញើដំណឹងពាក្យសុំច្បាប់របស់គ្រូ {t.khmer_name} ទៅ Telegram រួចរាល់!'
    }


def process_teacher_leave_action(leave_id, action, approver_name='គណៈគ្រប់គ្រង (Admin តាម Telegram)', approver_user=None):
    """
    Processes approve or reject action for a TeacherLeaveRequest.
    If approve:
      - Sets status to APPROVED
      - Syncs TeacherAttendance records for the leave date range to EXCUSED_LEAVE ($0 deduction)
    If reject:
      - Sets status to REJECTED
    Returns dict: {'success': bool, 'message': str, 'updated_text': str, 'leave_req': leave_req}
    """
    from datetime import timedelta
    from apps.teachers.models import TeacherLeaveRequest, TeacherAttendance
    from apps.academics.models import AcademicYear

    try:
        leave_req = TeacherLeaveRequest.objects.select_related('teacher').get(id=leave_id)
    except TeacherLeaveRequest.DoesNotExist:
        return {'success': False, 'message': f'ពុំរកឃើញពាក្យសុំច្បាប់លេខ #{leave_id} ឡើយ។'}

    if leave_req.status != TeacherLeaveRequest.Status.PENDING:
        curr_disp = leave_req.get_status_display()
        return {
            'success': False,
            'message': f'ពាក្យសុំច្បាប់នេះត្រូវបាន {curr_disp} រួចហើយ!',
            'updated_text': format_teacher_leave_telegram_message(leave_req),
            'leave_req': leave_req
        }

    if action == 'approve':
        leave_req.status = TeacherLeaveRequest.Status.APPROVED
        if approver_user:
            leave_req.approved_by = approver_user
        leave_req.rejection_reason = None
        leave_req.save()

        # Sync TeacherAttendance to EXCUSED_LEAVE for all dates in [start_date, end_date]
        cur_d = leave_req.start_date
        while cur_d <= leave_req.end_date:
            TeacherAttendance.objects.update_or_create(
                teacher=leave_req.teacher,
                date=cur_d,
                defaults={
                    'status': TeacherAttendance.Status.EXCUSED_LEAVE,
                    'deduction_amount': 0,
                    'notes': f"សម្រាកច្បាប់៖ {leave_req.get_leave_type_display()} ({leave_req.reason})"
                }
            )
            cur_d += timedelta(days=1)

        updated_text = format_teacher_leave_telegram_message(leave_req, approver_name=approver_name)
        return {
            'success': True,
            'action': 'approved',
            'message': f'✅ បានអនុម័តពាក្យសុំច្បាប់របស់ {leave_req.teacher.khmer_name} ដោយជោគជ័យ!',
            'updated_text': updated_text,
            'leave_req': leave_req
        }

    elif action == 'reject':
        leave_req.status = TeacherLeaveRequest.Status.REJECTED
        leave_req.rejection_reason = f"បដិសេធដោយ {approver_name}"
        leave_req.save()

        updated_text = format_teacher_leave_telegram_message(leave_req, approver_name=approver_name)
        return {
            'success': True,
            'action': 'rejected',
            'message': f'❌ បានបដិសេធពាក្យសុំច្បាប់របស់ {leave_req.teacher.khmer_name} រួចរាល់!',
            'updated_text': updated_text,
            'leave_req': leave_req
        }

    return {'success': False, 'message': f'ពុំស្គាល់សកម្មភាព៖ {action}'}

