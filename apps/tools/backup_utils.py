import os
import shutil
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from django.conf import settings
from django.db import connection
from django.core.management import call_command


def get_backup_dir():
    """
    Returns the Path to the backups directory and ensures it exists.
    """
    backup_dir = settings.BASE_DIR / 'backups'
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def is_sqlite_database():
    """
    Checks if active database is SQLite.
    """
    engine = settings.DATABASES.get('default', {}).get('ENGINE', '')
    return 'sqlite' in engine.lower()


def get_db_path():
    """
    Returns the absolute path to the active sqlite3 database file if SQLite.
    """
    db_config = settings.DATABASES.get('default', {})
    db_name = db_config.get('NAME')
    return Path(db_name) if db_name else Path(settings.BASE_DIR / 'db.sqlite3')


def get_db_statistics():
    """
    Returns statistical overview of the active database content.
    """
    stats = {
        'db_size_bytes': 0,
        'db_size_formatted': '0 KB',
        'db_engine': 'PostgreSQL' if not is_sqlite_database() else 'SQLite',
        'last_modified': None,
        'users_count': 0,
        'students_count': 0,
        'teachers_count': 0,
        'classrooms_count': 0,
        'exam_scores_count': 0,
        'attendance_count': 0,
    }
    
    if is_sqlite_database():
        db_path = get_db_path()
        if db_path.exists():
            size_bytes = db_path.stat().st_size
            stats['db_size_bytes'] = size_bytes
            if size_bytes >= 1024 * 1024:
                stats['db_size_formatted'] = f"{size_bytes / (1024 * 1024):.2f} MB"
            else:
                stats['db_size_formatted'] = f"{size_bytes / 1024:.2f} KB"
            stats['last_modified'] = datetime.fromtimestamp(db_path.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
    else:
        stats['db_size_formatted'] = 'Cloud Managed (Supabase)'
        stats['last_modified'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    try:
        from apps.accounts.models import User
        from apps.students.models import Student
        from apps.teachers.models import Teacher
        from apps.academics.models import Classroom
        from apps.examinations.models import ExamScore
        from apps.attendance.models import AttendanceRecord

        stats['users_count'] = User.objects.count()
        stats['students_count'] = Student.objects.count()
        stats['teachers_count'] = Teacher.objects.count()
        stats['teachers_active_count'] = Teacher.objects.filter(status=Teacher.Status.ACTIVE).count()
        stats['teachers_inactive_count'] = Teacher.objects.exclude(status=Teacher.Status.ACTIVE).count()
        stats['classrooms_count'] = Classroom.objects.count()
        stats['exam_scores_count'] = ExamScore.objects.count()
        stats['attendance_count'] = AttendanceRecord.objects.count()
    except Exception as e:
        stats['error'] = str(e)

    return stats


def create_json_backup(label="Full JSON Snapshot", user_info="Admin"):
    """
    Creates a complete portable JSON dumpdata backup compatible with both SQLite and PostgreSQL.
    """
    backup_dir = get_backup_dir()
    now = datetime.now()
    timestamp_str = now.strftime('%Y%m%d_%H%M%S')
    clean_label = "".join(c for c in label if c.isalnum() or c in (' ', '_', '-')).strip()
    if clean_label:
        backup_filename = f"db_dump_{timestamp_str}_{clean_label[:30].replace(' ', '_')}.json"
    else:
        backup_filename = f"db_dump_{timestamp_str}.json"

    target_backup_file = backup_dir / backup_filename

    with open(target_backup_file, 'w', encoding='utf-8') as f:
        call_command(
            'dumpdata',
            '--exclude=contenttypes',
            '--exclude=auth.permission',
            '--exclude=sessions',
            '--indent=2',
            stdout=f
        )

    stats = get_db_statistics()
    size_bytes = target_backup_file.stat().st_size
    size_fmt = f"{size_bytes / (1024 * 1024):.2f} MB" if size_bytes >= 1024 * 1024 else f"{size_bytes / 1024:.2f} KB"

    meta_filename = target_backup_file.with_suffix('.meta.json')
    metadata = {
        'filename': backup_filename,
        'format': 'json',
        'created_at': now.strftime('%Y-%m-%d %H:%M:%S'),
        'timestamp': timestamp_str,
        'label': label or 'JSON Snapshot',
        'created_by': user_info,
        'size_bytes': size_bytes,
        'size_formatted': size_fmt,
        'students_count': stats.get('students_count', 0),
        'teachers_count': stats.get('teachers_count', 0),
        'classrooms_count': stats.get('classrooms_count', 0),
        'exam_scores_count': stats.get('exam_scores_count', 0),
    }
    with open(meta_filename, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    return {
        'success': True,
        'filename': backup_filename,
        'filepath': str(target_backup_file),
        'metadata': metadata
    }


def create_database_backup(label="Manual Snapshot", user_info="Admin"):
    """
    Creates a backup snapshot copy (SQLite file if sqlite, or JSON dump if PostgreSQL).
    """
    if not is_sqlite_database():
        return create_json_backup(label=label, user_info=user_info)

    db_path = get_db_path()
    if not db_path.exists():
        return create_json_backup(label=label, user_info=user_info)

    backup_dir = get_backup_dir()
    now = datetime.now()
    timestamp_str = now.strftime('%Y%m%d_%H%M%S')
    clean_label = "".join(c for c in label if c.isalnum() or c in (' ', '_', '-')).strip()
    if clean_label:
        backup_filename = f"db_backup_{timestamp_str}_{clean_label[:30].replace(' ', '_')}.sqlite3"
    else:
        backup_filename = f"db_backup_{timestamp_str}.sqlite3"

    target_backup_file = backup_dir / backup_filename

    source_con = None
    dest_con = None
    try:
        source_con = sqlite3.connect(str(db_path))
        dest_con = sqlite3.connect(str(target_backup_file))
        with dest_con:
            source_con.backup(dest_con)
    except Exception:
        shutil.copy2(str(db_path), str(target_backup_file))
    finally:
        if dest_con:
            try:
                dest_con.close()
            except Exception:
                pass
        if source_con:
            try:
                source_con.close()
            except Exception:
                pass

    meta_filename = target_backup_file.with_suffix('.json')
    stats = get_db_statistics()
    metadata = {
        'filename': backup_filename,
        'format': 'sqlite3',
        'created_at': now.strftime('%Y-%m-%d %H:%M:%S'),
        'timestamp': timestamp_str,
        'label': label or 'Snapshot',
        'created_by': user_info,
        'size_bytes': target_backup_file.stat().st_size,
        'size_formatted': f"{target_backup_file.stat().st_size / (1024 * 1024):.2f} MB" if target_backup_file.stat().st_size >= 1024 * 1024 else f"{target_backup_file.stat().st_size / 1024:.2f} KB",
        'students_count': stats.get('students_count', 0),
        'teachers_count': stats.get('teachers_count', 0),
        'classrooms_count': stats.get('classrooms_count', 0),
        'exam_scores_count': stats.get('exam_scores_count', 0),
    }
    with open(meta_filename, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    return {
        'success': True,
        'filename': backup_filename,
        'filepath': str(target_backup_file),
        'metadata': metadata
    }


def list_backups():
    """
    Returns a sorted list of all available backup files (.sqlite3 and .json) with metadata.
    """
    backup_dir = get_backup_dir()
    backup_files = [f for f in backup_dir.iterdir() if f.is_file() and f.suffix in ('.sqlite3', '.json') and not f.name.endswith('.meta.json')]
    backup_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    backups = []
    for f in backup_files:
        if f.suffix == '.json':
            meta_file = f.with_suffix('.meta.json')
        else:
            meta_file = f.with_suffix('.json')

        meta = {}
        if meta_file.exists():
            try:
                with open(meta_file, 'r', encoding='utf-8') as mf:
                    meta = json.load(mf)
            except Exception:
                meta = {}

        size_bytes = f.stat().st_size
        size_fmt = f"{size_bytes / (1024 * 1024):.2f} MB" if size_bytes >= 1024 * 1024 else f"{size_bytes / 1024:.2f} KB"
        mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')

        backups.append({
            'filename': f.name,
            'filepath': str(f),
            'format': 'JSON' if f.suffix == '.json' else 'SQLite',
            'label': meta.get('label', 'Backup Snapshot'),
            'created_at': meta.get('created_at', mtime),
            'created_by': meta.get('created_by', 'System'),
            'size_formatted': meta.get('size_formatted', size_fmt),
            'size_bytes': size_bytes,
            'students_count': meta.get('students_count', '-'),
            'teachers_count': meta.get('teachers_count', '-'),
            'classrooms_count': meta.get('classrooms_count', '-'),
            'exam_scores_count': meta.get('exam_scores_count', '-'),
        })

    return backups


def restore_database_backup(backup_filename, user_info="Admin"):
    """
    Restores the database from a backup file (.sqlite3 or .json).
    Supports both SQLite and PostgreSQL.
    """
    backup_dir = get_backup_dir()
    backup_file = backup_dir / backup_filename
    if not backup_file.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_filename}")

    # 1. Take a safety auto-backup of current DB state before overwriting
    try:
        create_database_backup(label="Auto Safety Backup Before Restore", user_info=f"System (Restore by {user_info})")
    except Exception:
        pass

    # If it is a JSON data dump, load it via loaddata
    if backup_filename.endswith('.json'):
        connection.close()
        call_command('loaddata', str(backup_file))
        return {
            'success': True,
            'restored_from': backup_filename,
            'message': f"បាន Restore Database ពី JSON Data Dump {backup_filename} ដោយជោគជ័យ!"
        }

    # SQLite file restore
    if not is_sqlite_database():
        raise ValueError("មិនអាច Restore ឯកសារ SQLite ចូលក្នុង PostgreSQL (Supabase) ដោយផ្ទាល់បានទេ។ សូមប្រើប្រាស់ឯកសារ JSON Backup (.json) ជំនួសវិញ។")

    db_path = get_db_path()
    connection.close()

    source_con = None
    dest_con = None
    try:
        source_con = sqlite3.connect(str(backup_file))
        dest_con = sqlite3.connect(str(db_path))
        with dest_con:
            source_con.backup(dest_con)
    except Exception:
        shutil.copy2(str(backup_file), str(db_path))
    finally:
        if dest_con:
            try:
                dest_con.close()
            except Exception:
                pass
        if source_con:
            try:
                source_con.close()
            except Exception:
                pass

    return {
        'success': True,
        'restored_from': backup_filename,
        'message': f"បាន Restore Database ពី Snapshot {backup_filename} ដោយជោគជ័យ!"
    }


def delete_backup(backup_filename):
    """
    Deletes a specific backup file and its companion metadata.
    """
    backup_dir = get_backup_dir()
    backup_file = backup_dir / backup_filename
    if not backup_file.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_filename}")

    backup_file.unlink()
    if backup_filename.endswith('.json'):
        meta_file = backup_file.with_suffix('.meta.json')
    else:
        meta_file = backup_file.with_suffix('.json')

    if meta_file.exists():
        meta_file.unlink()

    return {'success': True, 'deleted': backup_filename}


def send_database_backup_to_telegram(custom_chat_id=None, format_type='json', sender_user='System / Pipeline'):
    """
    Automated Database Backup Pipeline Delivered to Telegram:
    1. Creates a full portable JSON dump or SQLite snapshot.
    2. Gathers real-time database statistics (Students, Active/Retired Teachers, Classrooms, Scores, Attendance).
    3. Dispatches the backup file and detailed summary report directly to Telegram.
    """
    from apps.accounts.utils import send_telegram_document
    from apps.accounts.models import TelegramConfig
    from apps.attendance.models import AttendanceSetting

    config = TelegramConfig.objects.first()
    settings_att = AttendanceSetting.get_settings()

    target_chat = custom_chat_id or (settings_att.management_chat_id if settings_att else None) or (config.chat_id if config else None)
    if not target_chat:
        return {
            'success': False,
            'message': 'ពុំទាន់បានកំណត់ Telegram Chat ID សម្រាប់ទទួល Database Backup នៅឡើយទេ។ សូមកំណត់ក្នុង School Settings ឬ Telegram Config!'
        }

    now = datetime.now()
    now_str = now.strftime('%d/%m/%Y %H:%M:%S')
    
    # 1. Create Backup File
    if format_type == 'sqlite3' and is_sqlite_database():
        backup_res = create_database_backup(label="Telegram Auto Pipeline Snapshot", user_info=sender_user)
    else:
        backup_res = create_json_backup(label="Telegram Auto Pipeline Dump", user_info=sender_user)

    filepath = Path(backup_res['filepath'])
    filename = backup_res['filename']
    stats = get_db_statistics()

    with open(filepath, 'rb') as f:
        file_bytes = f.read()

    size_formatted = backup_res['metadata']['size_formatted']

    # 2. Build Rich Khmer Markdown Caption
    caption_lines = [
        f"🛡️ *របាយការណ៍ Database Backup ប្រចាំការ (Data Safety)*",
        f"📅 *កាលបរិច្ឆេទ:* {now_str}",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"📊 *ស្ថិតិទិន្នន័យក្នុងប្រព័ន្ធផ្ទាល់ (Live Statistics):*",
        f"• សិស្សសរុប: *{stats['students_count']}* នាក់",
        f"• គ្រូបង្រៀនសកម្ម: *{stats.get('teachers_active_count', stats['teachers_count'])}* នាក់",
        f"• គ្រូអសកម្ម/ចូលនិវត្តន៍: *{stats.get('teachers_inactive_count', 0)}* នាក់",
        f"• ថ្នាក់រៀនសរុប: *{stats['classrooms_count']}* ថ្នាក់",
        f"• កំណត់ត្រាពិន្ទុ: *{stats['exam_scores_count']}* កំណត់ត្រា",
        f"• កំណត់ត្រាវត្តមាន: *{stats['attendance_count']}* លើក",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"📁 *ឯកសារ Backup:* `{filename}`",
        f"📦 *ទំហំ:* `{size_formatted}`",
        f"⚙️ *Database Engine:* {stats['db_engine']}",
        f"🔒 *សុវត្ថិភាព:* រក្សាទុក ១០០% ដោយសុវត្ថិភាព",
        f"\n_ផ្ញើដោយ: {sender_user} (SchoolSM Automated Pipeline)_"
    ]
    caption = "\n".join(caption_lines)

    # 3. Dispatch to Telegram
    log = send_telegram_document(
        document_bytes=file_bytes,
        filename=filename,
        caption=caption,
        recipient_name="គណៈគ្រប់គ្រង (Database Backup Channel)",
        recipient_type="Database Backup Pipeline",
        custom_chat_id=target_chat
    )

    return {
        'success': True,
        'filename': filename,
        'size_formatted': size_formatted,
        'chat_id': target_chat,
        'log_id': log.id if log else None,
        'status': log.status if log else 'SENT',
        'message': f"🚀 បានបញ្ជូន Database Backup '{filename}' ({size_formatted}) ទៅកាន់ Telegram (Chat ID: {target_chat}) ដោយជោគជ័យ!"
    }


def check_and_run_scheduled_backup(force=False):
    """
    Evaluates the Admin-configured Automated Database Backup Schedule:
    1. Checks if auto_backup_enabled is active.
    2. Validates frequency (DAILY, WEEKLY, MONTHLY) and time windows.
    3. Triggers send_database_backup_to_telegram when conditions match.
    4. Updates last_backup_at timestamp.
    """
    from apps.accounts.models import TelegramConfig
    config = TelegramConfig.get_config()

    if not config.auto_backup_enabled and not force:
        return {
            'executed': False,
            'message': 'មុខងារ Auto-Backup ស្វ័យប្រវត្តិតាមម៉ោងត្រូវបានបិទ (Disabled) នៅក្នុងការកំណត់។'
        }

    from django.utils import timezone
    now = timezone.now()
    local_now = timezone.localtime(now)
    today_date = local_now.date()
    should_run = force

    if not should_run:
        # Check if already executed in the same scheduled window today
        if config.last_backup_at:
            last_local = timezone.localtime(config.last_backup_at)
            if last_local.date() == today_date:
                # If daily and already ran today, skip
                if config.backup_frequency == 'DAILY':
                    return {
                        'executed': False,
                        'message': f"បានធ្វើការ Auto-Backup រួចរាល់ហើយសម្រាប់ថ្ងៃនេះ ({last_local.strftime('%d/%m/%Y %H:%M')})។"
                    }

        # Check Frequency
        if config.backup_frequency == 'WEEKLY':
            # Check day of week (0=Mon, 6=Sun)
            if local_now.weekday() != config.backup_day_of_week:
                return {
                    'executed': False,
                    'message': f"មិនទាន់ដល់ថ្ងៃកំណត់សម្រាប់ Weekly Backup (ថ្ងៃកំណត់គឺ {config.get_backup_day_of_week_display()})។"
                }
        elif config.backup_frequency == 'MONTHLY':
            # Run on 1st of month
            if local_now.day != 1:
                return {
                    'executed': False,
                    'message': "មិនទាន់ដល់ថ្ងៃកំណត់សម្រាប់ Monthly Backup (រៀងរាល់ថ្ងៃទី ១ នៃខែ)។"
                }

        # Check Time Window (+/- 30 mins)
        target_time = config.backup_time
        now_total_mins = local_now.hour * 60 + local_now.minute
        target_total_mins = target_time.hour * 60 + target_time.minute

        if abs(now_total_mins - target_total_mins) <= 30 or now_total_mins >= target_total_mins:
            should_run = True
        else:
            return {
                'executed': False,
                'message': f"មិនទាន់ដល់ម៉ោងកំណត់ ({target_time.strftime('%H:%M')})។ ម៉ោងបច្ចុប្បន្ន: {local_now.strftime('%H:%M')}។"
            }

    if should_run:
        result = send_database_backup_to_telegram(
            custom_chat_id=config.backup_chat_id or config.chat_id,
            format_type=config.backup_format,
            sender_user=f"Automated Schedule ({config.get_backup_frequency_display()})"
        )
        if result.get('success'):
            config.last_backup_at = timezone.now()
            config.save(update_fields=['last_backup_at'])
            return {
                'executed': True,
                'result': result,
                'message': f"🎉 Auto-Backup Pipeline ត្រូវបានដំណើរការដោយជោគជ័យ! {result['message']}"
            }
        else:
            return {
                'executed': False,
                'error': result.get('message'),
                'message': f"⚠️ Auto-Backup បរាជ័យ: {result.get('message')}"
            }

    return {'executed': False, 'message': 'លក្ខខណ្ឌមិនត្រូវគ្នា។'}


# =====================================================================
# ACADEMIC YEAR DEDICATED DATA BACKUP & RESTORE SUITE
# =====================================================================

def get_academic_year_backup_dir():
    """
    Returns the directory for year-specific backup packages (backups/academic_years/).
    """
    backup_dir = settings.BASE_DIR / 'backups' / 'academic_years'
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def create_academic_year_backup(academic_year, label="Academic Year Snapshot", user_info="Admin"):
    """
    Creates a comprehensive, self-contained JSON backup package for a specific Academic Year:
    - Academic Year info & Classrooms
    - Enrolled Students, Profiles, and Classroom assignments
    - Exam Terms, Subjects, and all student Grades (ពិន្ទុ)
    - Student Transfer Grades (ពិន្ទុផ្ទេរចូល)
    - Complete Student Attendance records (វត្តមាន & អវត្តមាន)
    - Promotion and Retention Records (កំណត់ត្រាឡើង/ត្រួតថ្នាក់)
    """
    from apps.academics.models import AcademicYear, Classroom, Subject
    from apps.students.models import Student, StudentPromotionRecord
    from apps.examinations.models import ExamTerm, Grade, StudentTransferGrade
    from apps.attendance.models import StudentAttendance
    from django.db.models import Q

    if isinstance(academic_year, (int, str)) and str(academic_year).isdigit():
        ay = AcademicYear.objects.filter(id=int(academic_year)).first()
    elif isinstance(academic_year, str):
        ay = AcademicYear.objects.filter(name=academic_year).first()
    else:
        ay = academic_year

    if not ay:
        raise ValueError("រកមិនឃើញឆ្នាំសិក្សាដែលត្រូវ Backup ឡើយ។")

    now = datetime.now()
    timestamp_str = now.strftime('%Y%m%d_%H%M%S')
    clean_ay_name = ay.name.replace(' ', '_').replace('/', '-').replace('\\', '-')

    backup_dir = get_academic_year_backup_dir()
    backup_filename = f"year_backup_{clean_ay_name}_{timestamp_str}.json"
    target_filepath = backup_dir / backup_filename

    # 1. Classrooms
    classrooms_qs = Classroom.objects.filter(academic_year=ay).select_related('homeroom_teacher')
    classrooms_data = []
    for c in classrooms_qs:
        classrooms_data.append({
            'id': c.id,
            'name': c.name,
            'code': getattr(c, 'code', c.name),
            'grade_level': getattr(c, 'grade_level', 10),
            'grade_level_name': f"ថ្នាក់ទី{c.grade_level}" if getattr(c, 'grade_level', None) else '',
            'track': getattr(c, 'track', ''),
            'room_number': getattr(c, 'room_number', ''),
            'capacity': getattr(c, 'capacity', 40),
            'homeroom_teacher_name': c.homeroom_teacher.full_name_kh if c.homeroom_teacher else '',
        })

    # 2. Students
    students_qs = Student.objects.filter(
        Q(academic_year=ay) | Q(classroom__academic_year=ay)
    ).select_related('classroom', 'category').distinct()
    students_data = []
    for s in students_qs:
        students_data.append({
            'id': s.id,
            'student_id': s.student_id,
            'khmer_name': s.khmer_name,
            'latin_name': s.latin_name or '',
            'gender': s.gender,
            'gender_display': s.get_gender_display(),
            'date_of_birth': str(s.date_of_birth) if s.date_of_birth else '',
            'place_of_birth': s.place_of_birth or '',
            'current_address': s.current_address or '',
            'phone': s.phone or '',
            'classroom_id': s.classroom.id if s.classroom else None,
            'classroom_name': s.classroom.name if s.classroom else '',
            'status': s.status,
            'scholarship_type': s.scholarship_type or '',
            'category_name': s.category.name if s.category else '',
            'enrollment_data': s.enrollment_data or {},
            'is_repeating_grade': s.is_repeating_grade,
            'is_exam_suspended': s.is_exam_suspended,
            'exam_suspension_reason': s.exam_suspension_reason or '',
        })

    # 3. Exam Terms
    terms_qs = ExamTerm.objects.filter(academic_year=ay).order_by('start_date', 'id')
    terms_data = []
    for t in terms_qs:
        terms_data.append({
            'id': t.id,
            'name': t.name,
            'term_type': getattr(t, 'term_type', 'MONTHLY'),
            'start_date': str(t.start_date) if t.start_date else '',
            'end_date': str(t.end_date) if t.end_date else '',
        })

    # 4. Grades (Exam Scores)
    grades_qs = Grade.objects.filter(
        Q(classroom__academic_year=ay) | Q(exam_term__academic_year=ay)
    ).select_related('student', 'subject', 'exam_term', 'classroom')
    grades_data = []
    for g in grades_qs:
        grades_data.append({
            'id': g.id,
            'student_id': g.student.student_id if g.student else '',
            'student_name': g.student.khmer_name if g.student else '',
            'classroom_name': g.classroom.name if g.classroom else '',
            'subject_code': g.subject.code if g.subject else '',
            'subject_name': g.subject.name_kh if g.subject else '',
            'exam_term_name': g.exam_term.name if g.exam_term else '',
            'score': float(g.score) if g.score is not None else 0.0,
            'max_score': float(g.max_score) if g.max_score is not None else 100.0,
            'grade_letter': g.grade_letter or '',
            'remarks': g.remarks or '',
        })

    # 5. Transfer Grades
    transfer_qs = StudentTransferGrade.objects.filter(academic_year=ay).select_related('student')
    transfer_data = []
    for tg in transfer_qs:
        transfer_data.append({
            'student_id': tg.student.student_id if tg.student else '',
            'semester': tg.semester,
            'prior_school_name': tg.prior_school_name or '',
            'monthly_average': float(tg.monthly_average) if tg.monthly_average is not None else None,
            'semester_exam_score': float(tg.semester_exam_score) if tg.semester_exam_score is not None else None,
            'semester_final_average': float(tg.semester_final_average) if tg.semester_final_average is not None else 0.0,
            'letter_grade': tg.letter_grade or '',
            'subject_scores': tg.subject_scores or {},
            'remarks': tg.remarks or '',
        })

    # 6. Attendances
    attendances_qs = StudentAttendance.objects.filter(
        classroom__academic_year=ay
    ).select_related('student', 'classroom', 'subject')
    attendances_data = []
    for a in attendances_qs:
        attendances_data.append({
            'id': a.id,
            'student_id': a.student.student_id if a.student else '',
            'student_name': a.student.khmer_name if a.student else '',
            'classroom_name': a.classroom.name if a.classroom else '',
            'date': str(a.date) if a.date else '',
            'session': getattr(a, 'session', 'MORNING'),
            'period_number': getattr(a, 'period_number', 1),
            'status': a.status,
            'subject_code': a.subject.code if a.subject else '',
            'notes': getattr(a, 'notes', '') or '',
        })

    # 7. Promotions
    promotions_qs = StudentPromotionRecord.objects.filter(
        Q(from_academic_year=ay) | Q(to_academic_year=ay)
    ).select_related('student', 'from_classroom', 'to_classroom')
    promotions_data = []
    for pr in promotions_qs:
        promotions_data.append({
            'student_id': pr.student.student_id if pr.student else '',
            'student_name': pr.student.khmer_name if pr.student else '',
            'from_year_name': pr.from_academic_year.name if pr.from_academic_year else '',
            'to_year_name': pr.to_academic_year.name if pr.to_academic_year else '',
            'from_classroom_name': pr.from_classroom.name if pr.from_classroom else '',
            'to_classroom_name': pr.to_classroom.name if pr.to_classroom else '',
            'action': pr.action,
            'standard_reason': pr.standard_reason,
            'custom_notes': pr.custom_notes or '',
        })

    payload = {
        'version': '1.0',
        'format': 'schoolsm_academic_year_package',
        'academic_year': {
            'id': ay.id,
            'name': ay.name,
            'start_date': str(ay.start_date) if ay.start_date else '',
            'end_date': str(ay.end_date) if ay.end_date else '',
            'is_current': ay.is_current,
        },
        'metadata': {
            'created_at': now.strftime('%Y-%m-%d %H:%M:%S'),
            'timestamp': timestamp_str,
            'label': label or f"Backup {ay.name}",
            'created_by': user_info,
            'counts': {
                'classrooms': len(classrooms_data),
                'students': len(students_data),
                'exam_terms': len(terms_data),
                'grades': len(grades_data),
                'transfer_grades': len(transfer_data),
                'attendances': len(attendances_data),
                'promotions': len(promotions_data),
            }
        },
        'classrooms': classrooms_data,
        'students': students_data,
        'exam_terms': terms_data,
        'grades': grades_data,
        'transfer_grades': transfer_data,
        'attendances': attendances_data,
        'promotions': promotions_data,
    }

    with open(target_filepath, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return {
        'success': True,
        'filename': backup_filename,
        'filepath': str(target_filepath),
        'payload': payload,
        'metadata': payload['metadata'],
        'students_count': len(students_data),
        'classrooms_count': len(classrooms_data),
        'grades_count': len(grades_data),
        'attendances_count': len(attendances_data),
    }


def restore_academic_year_backup(backup_data_or_file, user_info="Admin"):
    """
    Restores an Academic Year Backup Package into the database with 100% relational integrity.
    Supports either a parsed dictionary payload or a filepath/JSON string.
    """
    from apps.academics.models import AcademicYear, Classroom, GradeLevel, Subject
    from apps.students.models import Student, StudentCategory, StudentPromotionRecord
    from apps.examinations.models import ExamTerm, Grade, StudentTransferGrade
    from apps.attendance.models import StudentAttendance
    from django.db import transaction

    if isinstance(backup_data_or_file, (str, Path)):
        p = Path(backup_data_or_file)
        if p.exists():
            with open(p, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = json.loads(str(backup_data_or_file))
    elif isinstance(backup_data_or_file, dict):
        data = backup_data_or_file
    else:
        raise ValueError("Invalid backup data format")

    # If payload is wrapped inside AcademicYearStudentArchive payload
    if 'archive_payload' in data:
        data = data['archive_payload']

    ay_info = data.get('academic_year')
    if not ay_info:
        # Fallback for Student Archive payloads that have academic_year_name at root
        ay_name = data.get('academic_year_name') or 'Year'
        ay_info = {'name': ay_name}

    ay_name = ay_info.get('name')
    if not ay_name:
        raise ValueError("មិនមានឈ្មោះឆ្នាំសិក្សា (Academic Year Name) នៅក្នុងទិន្នន័យ Backup ឡើយ។")

    results = {
        'academic_year_name': ay_name,
        'classrooms_restored': 0,
        'students_restored': 0,
        'grades_restored': 0,
        'attendances_restored': 0,
        'transfer_grades_restored': 0,
        'promotions_restored': 0,
    }

    with transaction.atomic():
        # 1. Match or Create Academic Year
        ay = AcademicYear.objects.filter(name=ay_name).first()
        if not ay:
            start_d = ay_info.get('start_date') or datetime.now().date()
            end_d = ay_info.get('end_date') or (datetime.now().date() + datetime.timedelta(days=300))
            ay = AcademicYear.objects.create(
                name=ay_name,
                start_date=start_d,
                end_date=end_d,
                is_current=ay_info.get('is_current', False)
            )

        # 2. Match or Create Classrooms
        classroom_map = {}
        for c_data in data.get('classrooms', []):
            c_name = c_data.get('name', '').strip()
            if not c_name:
                continue
            cls = Classroom.objects.filter(academic_year=ay, name=c_name).first()
            if not cls:
                gl_val = c_data.get('grade_level')
                if not gl_val:
                    import re
                    m = re.search(r'\d+', c_data.get('grade_level_name', '') or c_name)
                    gl_val = int(m.group(0)) if m else 10
                cls = Classroom.objects.create(
                    academic_year=ay,
                    name=c_name,
                    code=c_data.get('code') or c_name,
                    grade_level=int(gl_val),
                    track=c_data.get('track', 'GENERAL'),
                    room_number=c_data.get('room_number', ''),
                    capacity=c_data.get('capacity', 40)
                )
            classroom_map[c_name] = cls
            results['classrooms_restored'] += 1

        # Also load existing classrooms of this year into map
        for cls in Classroom.objects.filter(academic_year=ay):
            classroom_map[cls.name] = cls

        # 3. Match or Create Students & Assign Classrooms
        student_map = {}
        for s_data in data.get('students', []):
            s_id = s_data.get('student_id', '').strip()
            kh_name = s_data.get('khmer_name', '').strip()
            if not kh_name:
                continue

            student = None
            if s_id:
                student = Student.objects.filter(student_id=s_id).first()
            if not student and s_data.get('date_of_birth'):
                student = Student.objects.filter(khmer_name=kh_name, date_of_birth=s_data.get('date_of_birth')).first()

            assigned_cls = classroom_map.get(s_data.get('classroom_name'))

            cat = None
            if s_data.get('category_name'):
                cat = StudentCategory.objects.filter(name=s_data['category_name']).first()

            if student:
                student.khmer_name = kh_name
                student.academic_year = ay
                if assigned_cls:
                    student.classroom = assigned_cls
                if s_data.get('status'):
                    student.status = s_data['status']
                if s_data.get('latin_name'):
                    student.latin_name = s_data['latin_name']
                student.save()
            else:
                dob = s_data.get('date_of_birth') or '2010-01-01'
                student = Student.objects.create(
                    student_id=s_id or f"STU_RESTORE_{datetime.now().strftime('%Y%m%d%H%M%S%f')[:17]}",
                    khmer_name=kh_name,
                    latin_name=s_data.get('latin_name', ''),
                    gender=s_data.get('gender', Student.Gender.MALE),
                    date_of_birth=dob,
                    classroom=assigned_cls,
                    academic_year=ay,
                    status=s_data.get('status', Student.Status.ACTIVE),
                    scholarship_type=s_data.get('scholarship_type', 'FULL_PAY'),
                    phone=s_data.get('phone', ''),
                    category=cat,
                    enrollment_data=s_data.get('enrollment_data', {}),
                    is_repeating_grade=s_data.get('is_repeating_grade', False),
                    is_exam_suspended=s_data.get('is_exam_suspended', False)
                )

            if s_id:
                student_map[s_id] = student
            student_map[kh_name] = student
            results['students_restored'] += 1

        # 4. Match or Create Exam Terms
        term_map = {}
        for t_data in data.get('exam_terms', []):
            t_name = t_data.get('name', '').strip()
            if not t_name:
                continue
            term = ExamTerm.objects.filter(academic_year=ay, name=t_name).first()
            if not term:
                term = ExamTerm.objects.create(
                    academic_year=ay,
                    name=t_name,
                    term_type=t_data.get('term_type', 'MONTHLY')
                )
            term_map[t_name] = term

        # 5. Restore Grades (Exam Scores)
        for g_data in data.get('grades', []):
            st = student_map.get(g_data.get('student_id')) or student_map.get(g_data.get('student_name'))
            if not st:
                continue

            t_name = g_data.get('exam_term_name', '')
            term = term_map.get(t_name) or ExamTerm.objects.filter(academic_year=ay, name=t_name).first()
            if not term and t_name:
                term = ExamTerm.objects.create(academic_year=ay, name=t_name)
                term_map[t_name] = term

            if not term:
                continue

            s_code = g_data.get('subject_code', '').strip()
            s_name = g_data.get('subject_name', '').strip()
            subj = None
            if s_code:
                subj = Subject.objects.filter(code=s_code).first()
            if not subj and s_name:
                subj = Subject.objects.filter(name_kh=s_name).first()
            if not subj:
                subj = Subject.objects.first()

            if not subj:
                continue

            cls = classroom_map.get(g_data.get('classroom_name')) or st.classroom
            if not cls:
                continue

            Grade.objects.update_or_create(
                student=st,
                subject=subj,
                exam_term=term,
                defaults={
                    'classroom': cls,
                    'score': g_data.get('score', 0.0),
                    'max_score': g_data.get('max_score', 100.0),
                    'grade_letter': g_data.get('grade_letter', ''),
                    'remarks': g_data.get('remarks', ''),
                }
            )
            results['grades_restored'] += 1

        # 6. Restore Transfer Grades
        for tg_data in data.get('transfer_grades', []):
            st = student_map.get(tg_data.get('student_id'))
            if not st:
                continue
            StudentTransferGrade.objects.update_or_create(
                student=st,
                academic_year=ay,
                semester=tg_data.get('semester', 1),
                defaults={
                    'prior_school_name': tg_data.get('prior_school_name', ''),
                    'monthly_average': tg_data.get('monthly_average'),
                    'semester_exam_score': tg_data.get('semester_exam_score'),
                    'semester_final_average': tg_data.get('semester_final_average', 0.0),
                    'letter_grade': tg_data.get('letter_grade', ''),
                    'subject_scores': tg_data.get('subject_scores', {}),
                    'remarks': tg_data.get('remarks', ''),
                }
            )
            results['transfer_grades_restored'] += 1

        # 7. Restore Attendances
        for a_data in data.get('attendances', []):
            st = student_map.get(a_data.get('student_id')) or student_map.get(a_data.get('student_name'))
            if not st:
                continue
            cls = classroom_map.get(a_data.get('classroom_name')) or st.classroom
            if not cls:
                continue

            date_str = a_data.get('date')
            if not date_str:
                continue

            subj = None
            if a_data.get('subject_code'):
                subj = Subject.objects.filter(code=a_data['subject_code']).first()

            StudentAttendance.objects.update_or_create(
                student=st,
                classroom=cls,
                date=date_str,
                session=a_data.get('session', 'MORNING'),
                period_number=a_data.get('period_number', 1),
                defaults={
                    'status': a_data.get('status', StudentAttendance.Status.ABSENT),
                    'subject': subj,
                    'notes': a_data.get('notes', ''),
                }
            )
            results['attendances_restored'] += 1

        # 8. Restore Promotions
        for pr_data in data.get('promotions', []):
            st = student_map.get(pr_data.get('student_id'))
            if not st:
                continue
            from_cls = classroom_map.get(pr_data.get('from_classroom_name'))
            to_cls = classroom_map.get(pr_data.get('to_classroom_name'))
            StudentPromotionRecord.objects.get_or_create(
                student=st,
                from_academic_year=ay,
                from_classroom=from_cls,
                to_classroom=to_cls,
                action=pr_data.get('action', StudentPromotionRecord.Action.PROMOTE),
                standard_reason=pr_data.get('standard_reason', StudentPromotionRecord.StandardReason.PASSED_YEAR),
                defaults={
                    'custom_notes': pr_data.get('custom_notes', ''),
                }
            )
            results['promotions_restored'] += 1

    return {
        'success': True,
        'results': results,
        'counts': results,
        'message': (
            f"🎉 បាន Restore ឆ្នាំសិក្សា «{ay_name}» ដោយជោគជ័យ! "
            f"(សិស្ស: {results['students_restored']} នាក់, ថ្នាក់: {results['classrooms_restored']}, "
            f"ពិន្ទុ: {results['grades_restored']} កំណត់ត្រា, វត្តមាន: {results['attendances_restored']} លើក)"
        )
    }


def list_academic_year_backups():
    """
    Returns a sorted list of all available Academic Year backup JSON packages.
    """
    backup_dir = get_academic_year_backup_dir()
    files = [f for f in backup_dir.iterdir() if f.is_file() and f.suffix == '.json']
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    backups = []
    for f in files:
        meta = {}
        try:
            with open(f, 'r', encoding='utf-8') as jf:
                data = json.load(jf)
                meta = data.get('metadata', {})
                ay_info = data.get('academic_year', {})
        except Exception:
            data = {}
            ay_info = {}

        size_bytes = f.stat().st_size
        size_fmt = f"{size_bytes / (1024 * 1024):.2f} MB" if size_bytes >= 1024 * 1024 else f"{size_bytes / 1024:.2f} KB"
        mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')

        backups.append({
            'filename': f.name,
            'filepath': str(f),
            'academic_year_name': ay_info.get('name') or meta.get('label') or 'Year',
            'created_at': meta.get('created_at', mtime),
            'created_by': meta.get('created_by', 'System'),
            'size_formatted': size_fmt,
            'size_bytes': size_bytes,
            'counts': meta.get('counts', {}),
        })

    return backups




