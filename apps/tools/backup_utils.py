import os
import shutil
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from django.conf import settings
from django.db import connection

def get_backup_dir():
    """
    Returns the Path to the backups directory and ensures it exists.
    """
    backup_dir = settings.BASE_DIR / 'backups'
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir

def get_db_path():
    """
    Returns the absolute path to the active sqlite3 database file.
    """
    db_config = settings.DATABASES.get('default', {})
    db_name = db_config.get('NAME')
    return Path(db_name)

def get_db_statistics():
    """
    Returns statistical overview of the active database content.
    """
    stats = {
        'db_size_bytes': 0,
        'db_size_formatted': '0 KB',
        'last_modified': None,
        'users_count': 0,
        'students_count': 0,
        'teachers_count': 0,
        'classrooms_count': 0,
        'exam_scores_count': 0,
        'attendance_count': 0,
    }
    
    db_path = get_db_path()
    if db_path.exists():
        size_bytes = db_path.stat().st_size
        stats['db_size_bytes'] = size_bytes
        if size_bytes >= 1024 * 1024:
            stats['db_size_formatted'] = f"{size_bytes / (1024 * 1024):.2f} MB"
        else:
            stats['db_size_formatted'] = f"{size_bytes / 1024:.2f} KB"
        stats['last_modified'] = datetime.fromtimestamp(db_path.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')

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
        stats['classrooms_count'] = Classroom.objects.count()
        stats['exam_scores_count'] = ExamScore.objects.count()
        stats['attendance_count'] = AttendanceRecord.objects.count()
    except Exception as e:
        stats['error'] = str(e)

    return stats

def create_database_backup(label="Manual Snapshot", user_info="Admin"):
    """
    Creates a timestamped snapshot copy of db.sqlite3 in the backups folder.
    Also creates a companion .json metadata file.
    """
    db_path = get_db_path()
    if not db_path.exists():
        raise FileNotFoundError(f"Database file not found at: {db_path}")

    backup_dir = get_backup_dir()
    now = datetime.now()
    timestamp_str = now.strftime('%Y%m%d_%H%M%S')
    clean_label = "".join(c for c in label if c.isalnum() or c in (' ', '_', '-')).strip()
    if clean_label:
        backup_filename = f"db_backup_{timestamp_str}_{clean_label[:30].replace(' ', '_')}.sqlite3"
    else:
        backup_filename = f"db_backup_{timestamp_str}.sqlite3"

    target_backup_file = backup_dir / backup_filename

    # Ensure WAL checkpoint and write out cleanly using sqlite3 backup API if possible, or copyfile
    source_con = None
    dest_con = None
    try:
        source_con = sqlite3.connect(str(db_path))
        dest_con = sqlite3.connect(str(target_backup_file))
        with dest_con:
            source_con.backup(dest_con)
    except Exception:
        # Fallback to direct safe file copy
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

    # Save metadata
    meta_filename = target_backup_file.with_suffix('.json')
    stats = get_db_statistics()
    metadata = {
        'filename': backup_filename,
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
    Returns a sorted list of all available backup files with metadata.
    """
    backup_dir = get_backup_dir()
    sqlite_files = list(backup_dir.glob('*.sqlite3'))
    # Sort newest first
    sqlite_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    backups = []
    for f in sqlite_files:
        meta_file = f.with_suffix('.json')
        if meta_file.exists():
            try:
                with open(meta_file, 'r', encoding='utf-8') as mf:
                    meta = json.load(mf)
            except Exception:
                meta = {}
        else:
            meta = {}

        size_bytes = f.stat().st_size
        size_fmt = f"{size_bytes / (1024 * 1024):.2f} MB" if size_bytes >= 1024 * 1024 else f"{size_bytes / 1024:.2f} KB"
        mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')

        backups.append({
            'filename': f.name,
            'filepath': str(f),
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
    Restores the database from a backup file in the backups folder.
    First takes an automatic safety backup of the current database state.
    """
    backup_dir = get_backup_dir()
    backup_file = backup_dir / backup_filename
    if not backup_file.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_filename}")

    # 1. Take a safety auto-backup of current DB state before overwriting
    db_path = get_db_path()
    if db_path.exists():
        create_database_backup(label="Auto Safety Backup Before Restore", user_info=f"System (Restore by {user_info})")

    # 2. Close active Django database connections
    connection.close()

    # 3. Restore backup using sqlite3 online backup or copy
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
    meta_file = backup_file.with_suffix('.json')
    if meta_file.exists():
        meta_file.unlink()

    return {'success': True, 'deleted': backup_filename}
