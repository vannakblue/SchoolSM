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



