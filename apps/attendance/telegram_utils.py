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

def send_classroom_attendance_telegram(classroom, target_date, session='MORNING', period_number=None, custom_chat_id=None, sender_user=None):
    """
    Formats and sends the student attendance report for a specific classroom and period/session to Telegram.
    Student names are sorted alphabetically by Khmer name.
    Target chat: custom_chat_id or classroom.telegram_chat_id or default TelegramConfig.chat_id.
    """
    config = TelegramConfig.objects.first()
    settings = AttendanceSetting.get_settings()
    
    target_chat_id = custom_chat_id or classroom.telegram_chat_id or (config.chat_id if config else None)
    if not target_chat_id:
        return {
            'success': False,
            'message': f'ពុំទាន់មាន Telegram Chat ID សម្រាប់ថ្នាក់ {classroom.name} ឬប្រព័ន្ធរួមនៅឡើយទេ។ សូមកំណត់ Chat ID ជាមុនសិន!'
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
    total_students = classroom.total_students or len(records)
    
    # Sort students alphabetically by khmer_name
    absent_list = sorted([r for r in records if r.status == StudentAttendance.Status.ABSENT], key=lambda r: (r.student.khmer_name, r.student.student_id))
    permission_list = sorted([r for r in records if r.status == StudentAttendance.Status.PERMISSION], key=lambda r: (r.student.khmer_name, r.student.student_id))
    late_list = sorted([r for r in records if r.status == StudentAttendance.Status.LATE], key=lambda r: (r.student.khmer_name, r.student.student_id))
    present_count = total_students - len(absent_list) - len(permission_list)

    date_str = target_date.strftime('%d/%m/%Y')
    session_str = "ពេលព្រឹក (Morning)" if session == 'MORNING' else "ពេលរសៀល (Afternoon)"
    period_str = f" • ម៉ោងទី {period_number}" if period_number else ""

    # Subject and Teacher info
    first_rec = records[0] if records else None
    subject_name = first_rec.subject.name_kh if (first_rec and first_rec.subject) else "គ្រប់មុខវិជ្ជា"
    teacher_name = first_rec.recorded_by.display_name if (first_rec and first_rec.recorded_by) else (classroom.homeroom_teacher.display_name if classroom.homeroom_teacher else "មិនបានបញ្ជាក់")

    title = f"របាយការណ៍អវត្តមានសិស្ស ថ្នាក់ {classroom.name}"
    
    msg_lines = [
        f"🏫 *ថ្នាក់រៀន:* {classroom.name} ({classroom.code})",
        f"📅 *កាលបរិច្ឆេទ:* {date_str} ({session_str}{period_str})",
        f"📚 *មុខវិជ្ជា:* {subject_name}",
        f"👨‍🏫 *គ្រូបង្រៀន/អ្នកស្រង់:* {teacher_name}",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"📊 *ស្ថិតិវត្តមានសរុប:*",
        f"• សិស្សសរុប: *{total_students}* នាក់",
        f"• វត្តមាន: *{present_count}* នាក់",
        f"• អវត្តមានឥតច្បាប់ (Absent): *{len(absent_list)}* នាក់",
        f"• អវត្តមានមានច្បាប់ (Permission): *{len(permission_list)}* នាក់",
        f"• មកយឺត (Late): *{len(late_list)}* នាក់",
    ]

    if absent_list:
        msg_lines.append("\n❌ *បញ្ជីសិស្សអវត្តមានឥតច្បាប់ (តម្រៀបតាមអក្ខរក្រម):*")
        for idx, a in enumerate(absent_list, 1):
            note_str = f" ({a.notes})" if a.notes else ""
            msg_lines.append(f" {idx}. {a.student.khmer_name} (អត្តលេខ: {a.student.student_id}){note_str}")

    if permission_list:
        msg_lines.append("\n📝 *បញ្ជីសិស្សសុំច្បាប់ (Permission):*")
        for idx, p in enumerate(permission_list, 1):
            note_str = f" ({p.notes})" if p.notes else ""
            msg_lines.append(f" {idx}. {p.student.khmer_name} (អត្តលេខ: {p.student.student_id}){note_str}")

    if late_list:
        msg_lines.append("\n⏰ *បញ្ជីសិស្សមកយឺត (Late):*")
        for idx, l in enumerate(late_list, 1):
            note_str = f" ({l.notes})" if l.notes else ""
            msg_lines.append(f" {idx}. {l.student.khmer_name} (អត្តលេខ: {l.student.student_id}){note_str}")

    if not absent_list and not permission_list:
        msg_lines.append("\n🎉 *អបអរសាទរ! ថ្នាក់នេះមានវត្តមានសិស្សពេញ ១០០% គ្រប់ចំនួន។*")

    msg_lines.append(f"\n_ផ្ញើដោយ: {sender_user.display_name if sender_user else 'Admin'}_")

    message = "\n".join(msg_lines)

    log = send_telegram_notification(
        title=title,
        message=message,
        recipient_name=f"ថ្នាក់ {classroom.name}",
        recipient_type="Classroom Telegram",
        custom_chat_id=target_chat_id
    )

    return {
        'success': True,
        'chat_id': target_chat_id,
        'log_id': log.id if log else None,
        'status': log.status if log else 'SENT',
        'message': f'បានផ្ញើរបាយការណ៍អវត្តមានថ្នាក់ {classroom.name} ទៅ Telegram (Chat ID: {target_chat_id}) ដោយជោគជ័យ!'
    }


def send_hourly_period_absence_dispatch(target_date, period_number, session=None, sender_user=None, force=False):
    """
    Automated Hourly Absence Dispatch System for a specific period (P1-P8):
    1. Direct Guardians: Instant direct alerts to parents of absent/permission/late students.
    2. Homeroom Teachers & Class Groups: Formatted classroom absence list sorted alphabetically.
    3. Management Group & Custom Groups: Schoolwide summary ordered strictly by class hierarchy (Grade 7 to 12).
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

    # 1. Fetch classrooms ordered strictly by grade_level (7 to 12) and code (7A, 7B, 8A... 12A)
    active_year = AcademicYear.objects.filter(is_current=True).first()
    classrooms_qs = Classroom.objects.all().select_related('homeroom_teacher', 'homeroom_teacher__user').order_by('grade_level', 'code')
    if active_year:
        classrooms_qs = classrooms_qs.filter(academic_year=active_year)
    classrooms = list(classrooms_qs)

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
    management_sent_count = 0

    class_reports = []

    # 3. Process each classroom in Grade 7-12 order
    for cls in classrooms:
        cls_records = records_by_class.get(cls.id, [])
        if not cls_records:
            continue

        # Sort students strictly alphabetically by khmer_name, student_id
        sorted_records = sorted(cls_records, key=lambda r: (r.student.khmer_name, r.student.student_id))

        absents = [r for r in sorted_records if r.status == StudentAttendance.Status.ABSENT]
        permissions = [r for r in sorted_records if r.status == StudentAttendance.Status.PERMISSION]
        lates = [r for r in sorted_records if r.status == StudentAttendance.Status.LATE]

        total_absent_all += len(absents)
        total_permission_all += len(permissions)
        total_late_all += len(lates)

        class_reports.append({
            'classroom': cls,
            'absents': absents,
            'permissions': permissions,
            'lates': lates,
            'total_absent_class': len(absents) + len(permissions) + len(lates),
            'first_rec': sorted_records[0] if sorted_records else None
        })

        # --- (A) Send to Direct Guardians (អាណាព្យាបាលផ្ទាល់) ---
        if settings.dispatch_to_guardians:
            for r in sorted_records:
                student = r.student
                parent_chat = student.telegram_chat_id
                if parent_chat:
                    status_kh = "អវត្តមានឥតច្បាប់ (Absent)" if r.status == StudentAttendance.Status.ABSENT else ("អវត្តមានមានច្បាប់ (Permission)" if r.status == StudentAttendance.Status.PERMISSION else "មកយឺត (Late)")
                    status_icon = "❌" if r.status == StudentAttendance.Status.ABSENT else ("📝" if r.status == StudentAttendance.Status.PERMISSION else "⏰")
                    msg = (
                        f"សួស្តីលោក/លោកស្រីអាណាព្យាបាលសិស្ស *{student.khmer_name}*!\n\n"
                        f"🏫 *ថ្នាក់រៀន:* {cls.name}\n"
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

        # --- (B) Send to Homeroom Teachers & Class Groups (គ្រូបន្ទុកថ្នាក់) ---
        if settings.dispatch_to_homeroom:
            homeroom_chat = cls.telegram_chat_id
            if not homeroom_chat and cls.homeroom_teacher and cls.homeroom_teacher.user:
                homeroom_chat = cls.homeroom_teacher.user.telegram_chat_id

            if homeroom_chat:
                first_rec = sorted_records[0] if sorted_records else None
                subject_name = first_rec.subject.name_kh if (first_rec and first_rec.subject) else "មុខវិជ្ជាប្រចាំម៉ោង"
                teacher_name = first_rec.recorded_by.display_name if (first_rec and first_rec.recorded_by) else (cls.homeroom_teacher.display_name if cls.homeroom_teacher else "គ្រូបង្រៀន")

                lines = [
                    f"🏫 *របាយការណ៍អវត្តមានសិស្ស ថ្នាក់ {cls.name}*",
                    f"📅 *កាលបរិច្ឆេទ:* {date_str} ({session_str} • ម៉ោងទី {period_num_int})",
                    f"📚 *មុខវិជ្ជា:* {subject_name} | 👨‍🏫 *អ្នកស្រង់:* {teacher_name}",
                    f"━━━━━━━━━━━━━━━━━━━━",
                    f"📊 *ស្ថិតិអវត្តមានសរុប:* ឥតច្បាប់: *{len(absents)}* | ច្បាប់: *{len(permissions)}* | យឺត: *{len(lates)}*",
                ]
                if absents:
                    lines.append("\n❌ *បញ្ជីសិស្សអវត្តមានឥតច្បាប់ (តម្រៀបតាមអក្ខរក្រម):*")
                    for idx, a in enumerate(absents, 1):
                        note_str = f" ({a.notes})" if a.notes else ""
                        lines.append(f" {idx}. {a.student.khmer_name} (ID: {a.student.student_id}){note_str}")
                if permissions:
                    lines.append("\n📝 *បញ្ជីសិស្សសុំច្បាប់ (Permission):*")
                    for idx, p in enumerate(permissions, 1):
                        note_str = f" ({p.notes})" if p.notes else ""
                        lines.append(f" {idx}. {p.student.khmer_name} (ID: {p.student.student_id}){note_str}")
                if lates:
                    lines.append("\n⏰ *បញ្ជីសិស្សមកយឺត (Late):*")
                    for idx, l in enumerate(lates, 1):
                        note_str = f" ({l.notes})" if l.notes else ""
                        lines.append(f" {idx}. {l.student.khmer_name} (ID: {l.student.student_id}){note_str}")

                send_telegram_notification(
                    title=f"របាយការណ៍អវត្តមាន ថ្នាក់ {cls.name} (ម៉ោងទី {period_num_int})",
                    message="\n".join(lines),
                    recipient_name=f"ថ្នាក់ {cls.name}",
                    recipient_type="Classroom / Homeroom",
                    custom_chat_id=homeroom_chat
                )
                homeroom_sent_count += 1

    # --- (C) Send Master Schoolwide Absence Report to Management & Custom Groups ---
    if settings.dispatch_to_management:
        targets = []
        if settings.management_chat_id:
            for cid in settings.management_chat_id.split(','):
                cid = cid.strip()
                if cid and cid not in targets:
                    targets.append(cid)
        if settings.custom_dispatch_groups:
            for cid in settings.custom_dispatch_groups.split(','):
                cid = cid.strip()
                if cid and cid not in targets:
                    targets.append(cid)
        if not targets and config and config.chat_id:
            targets.append(config.chat_id)

        if targets:
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
                    cls = cr['classroom']
                    c_abs = cr['absents']
                    c_perm = cr['permissions']
                    c_late = cr['lates']

                    hr_name = cls.homeroom_teacher.khmer_name if cls.homeroom_teacher else "គ្មានគ្រូបន្ទុក"
                    master_lines.append(f"\n🏫 *ថ្នាក់ទី {cls.name}* (អវត្តមានសរុប: {cr['total_absent_class']} នាក់ • គ្រូបន្ទុក: {hr_name})")

                    counter = 1
                    for a in c_abs:
                        master_lines.append(f"  {counter}. {a.student.khmer_name} (ID: {a.student.student_id}) ❌ ឥតច្បាប់")
                        counter += 1
                    for p in c_perm:
                        note = f" ({p.notes})" if p.notes else ""
                        master_lines.append(f"  {counter}. {p.student.khmer_name} (ID: {p.student.student_id}) 📝 មានច្បាប់{note}")
                        counter += 1
                    for l in c_late:
                        master_lines.append(f"  {counter}. {l.student.khmer_name} (ID: {l.student.student_id}) ⏰ យឺត")
                        counter += 1

            master_msg = "\n".join(master_lines)
            for t_chat in targets:
                send_telegram_notification(
                    title=f"របាយការណ៍អវត្តមានទូទាំងសាលា ម៉ោងទី {period_num_int}",
                    message=master_msg,
                    recipient_name="Management / Custom Group",
                    recipient_type="Management Group",
                    custom_chat_id=t_chat
                )
                management_sent_count += 1

    return {
        'success': True,
        'period_number': period_num_int,
        'guardian_sent_count': guardian_sent_count,
        'homeroom_sent_count': homeroom_sent_count,
        'management_sent_count': management_sent_count,
        'total_absent': total_absent_all,
        'total_permission': total_permission_all,
        'total_late': total_late_all,
        'message': f"🚀 បានផ្ញើបញ្ជីអវត្តមានម៉ោងទី {period_num_int} ដោយជោគជ័យ! (អាណាព្យាបាល: {guardian_sent_count}, គ្រូបន្ទុក: {homeroom_sent_count}, គណៈគ្រប់គ្រង/Groups: {management_sent_count})"
    }



def send_missing_teachers_telegram(target_date, period_number=None, custom_chat_id=None, sender_user=None):
    """
    Identifies teachers who have NOT submitted student attendance for scheduled teaching slots on target_date.
    Teachers on approved leave are excluded.
    Dispatches warning alert to Management Telegram group or custom_chat_id.
    """
    settings = AttendanceSetting.get_settings()
    config = TelegramConfig.objects.first()
    
    target_chat_id = custom_chat_id or settings.management_chat_id or (config.chat_id if config else None)
    if not target_chat_id:
        return {
            'success': False,
            'message': 'ពុំទាន់បានកំណត់ Telegram Chat ID សម្រាប់គណៈគ្រប់គ្រងសាលា (Management Chat ID) នៅឡើយទេ។'
        }

    teachers = Teacher.objects.filter(status='ACTIVE').order_by('teacher_id')
    att_data = get_teacher_daily_attendance_data(teachers, target_date)
    rows = att_data['rows']

    # Filter teachers with unrecorded slots
    missing_teachers = []
    for r in rows:
        # Check if teacher has unrecorded periods (and is NOT on approved leave)
        if r['daily_status'] == 'EXCUSED_LEAVE':
            continue # Exclude excused teachers!
        
        unrec_slots = []
        for p_num, p_info in r['period_slots'].items():
            if p_info and p_info['status'] == 'UNRECORDED':
                if period_number is None or p_num == period_number:
                    unrec_slots.append(p_info)

        if unrec_slots:
            missing_teachers.append({
                'teacher': r['teacher'],
                'unrec_slots': unrec_slots,
                'phone': r['teacher'].phone or 'គ្មានលេខទូរស័ព្ទ',
            })

    date_str = target_date.strftime('%d/%m/%Y')
    period_title = f"នៅម៉ោងទី {period_number}" if period_number else "ប្រចាំថ្ងៃ"
    title = f"🚨 របាយការណ៍គ្រូមិនទាន់ស្រង់វត្តមានសិស្ស ({period_title})"

    if not missing_teachers:
        message = f"🎉 *អបអរសាទរ!* នៅថ្ងៃទី {date_str} {period_title} លោកគ្រូ-អ្នកគ្រូទាំងអស់បានចុះវត្តមានសិស្សបានគ្រប់ចំនួន ១០០% គ្មានចន្លោះឡើយ។"
    else:
        msg_lines = [
            f"⚠️ *សូមជម្រាបជូនគណៈគ្រប់គ្រងសាលា៖*",
            f"ខាងក្រោមនេះជាបញ្ជីឈ្មោះលោកគ្រូ-អ្នកគ្រូដែល*មិនទាន់បានស្រង់អវត្តមានសិស្ស* សម្រាប់ថ្ងៃទី *{date_str}* ({period_title})៖",
            f"━━━━━━━━━━━━━━━━━━━━",
        ]
        
        for idx, item in enumerate(missing_teachers, 1):
            t = item['teacher']
            slots_text = []
            for s in item['unrec_slots']:
                cls_code = s['classroom'].code if s['classroom'] else ''
                sub_name = s['subject'].name_kh if s['subject'] else ''
                slots_text.append(f"ម៉ោងទី {s['slot'].period_number} ({cls_code} - {sub_name})")
            
            slots_str = ", ".join(slots_text)
            msg_lines.append(f"*{idx}. {t.khmer_name}* (ID: {t.teacher_id} • ទូរស័ព្ទ: `{item['phone']}`)")
            msg_lines.append(f"   👉 មិនទាន់ចុះ៖ {slots_str}")

        msg_lines.append(f"━━━━━━━━━━━━━━━━━━━━")
        msg_lines.append(f"📌 *សរុបគ្រូមិនទាន់ចុះ:* *{len(missing_teachers)}* នាក់")
        msg_lines.append(f"_ប្រព័ន្ធសូមរំលឹកដល់លោកគ្រូ-អ្នកគ្រូ សូមមេត្តាបំពេញវត្តមានឱ្យបានទាន់ពេលវេលា។_")

        message = "\n".join(msg_lines)

    log = send_telegram_notification(
        title=title,
        message=message,
        recipient_name="គណៈគ្រប់គ្រងសាលា (School Management)",
        recipient_type="Management Telegram",
        custom_chat_id=target_chat_id
    )

    return {
        'success': True,
        'chat_id': target_chat_id,
        'missing_count': len(missing_teachers),
        'log_id': log.id if log else None,
        'status': log.status if log else 'SENT',
        'message': f'បានផ្ញើរបាយការណ៍គ្រូមិនទាន់ស្រង់វត្តមាន ({len(missing_teachers)} នាក់) ទៅ Telegram គណៈគ្រប់គ្រងដោយជោគជ័យ!'
    }


def send_daily_summary_telegram(target_date=None, send_students=True, send_teachers=True, custom_chat_id=None):
    """
    Compiles and dispatches the daily school-wide student and teacher attendance summary digest.
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

    return {
        'success': True,
        'chat_id': target_chat_id,
        'log_id': log.id if log else None,
        'status': log.status if log else 'SENT',
        'message': f'បានផ្ញើរបាយការណ៍សង្ខេបប្រចាំថ្ងៃ ({date_str}) ទៅកាន់ Telegram ដោយជោគជ័យ!'
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

