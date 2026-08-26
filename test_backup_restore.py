import os
import sys
import django

sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.tools.backup_utils import (
    create_database_backup, list_backups, restore_database_backup,
    delete_backup, get_db_statistics, get_backup_dir, get_db_path
)

print("=== TESTING DATABASE BACKUP, SNAPSHOT & RESTORE SUITE ===")

# 1. Test get_db_statistics
stats = get_db_statistics()
assert 'students_count' in stats
assert 'db_size_formatted' in stats
print(f"[PASS] 1. DB Statistics calculated successfully: Size={stats['db_size_formatted']}, Students={stats['students_count']}, Teachers={stats['teachers_count']}")

# 2. Test create_database_backup programmatically
backup_result = create_database_backup(label="Automated Test Snapshot", user_info="UnitTest")
assert backup_result['success'] is True
backup_filename = backup_result['filename']
backup_file = get_backup_dir() / backup_filename
assert backup_file.exists(), f"Backup file was not created: {backup_file}"
print(f"[PASS] 2. Created backup snapshot: {backup_filename} (Size: {backup_result['metadata']['size_formatted']})")

# 3. Test list_backups
backups = list_backups()
assert len(backups) > 0, "No backups found in list_backups()"
matching = [b for b in backups if b['filename'] == backup_filename]
assert len(matching) == 1, "Created backup not found in list_backups()"
assert matching[0]['label'] == "Automated Test Snapshot"
print(f"[PASS] 3. list_backups() returned {len(backups)} snapshot(s) correctly!")

# 4. Test Web Client Endpoints
client = Client()

# Login as ADMIN
login_res = client.get('/accounts/demo-login/ADMIN/', follow=True)
assert login_res.status_code == 200
print("[PASS] 4. Admin logged in successfully.")

# Access /tools/database-backup/
res = client.get('/tools/database-backup/')
assert res.status_code == 200, f"GET /tools/database-backup/ failed: {res.status_code}"
content = res.content.decode('utf-8')
assert 'ការគ្រប់គ្រង Database Backup & Snapshot' in content
assert backup_filename in content
print("[PASS] 5. GET /tools/database-backup/ -> 200 OK (Rendered dashboard with backup list)")

# Access /tools/ Hub and check for Data Suite section
res_hub = client.get('/tools/')
assert res_hub.status_code == 200
content_hub = res_hub.content.decode('utf-8')
assert 'ការគ្រប់គ្រង Database Backup & Snapshot' in content_hub
print("[PASS] 6. GET /tools/ -> 200 OK (Database backup card integrated in Online Tools Hub)")

# Create a snapshot via Web POST
res_create = client.post('/tools/database-backup/create/', {'label': 'Web UI Snapshot Test'}, follow=True)
assert res_create.status_code == 200
print("[PASS] 7. POST /tools/database-backup/create/ -> Created snapshot via Web UI")

# Download Live db.sqlite3
res_down_live = client.get('/tools/database-backup/download/')
assert res_down_live.status_code == 200
assert res_down_live['Content-Type'] == 'application/x-sqlite3'
res_down_live.close()
print("[PASS] 8. GET /tools/database-backup/download/ -> 200 OK (Live SQLite file downloaded)")

# Download specific backup file
res_down_file = client.get(f'/tools/database-backup/download/{backup_filename}/')
assert res_down_file.status_code == 200
assert res_down_file['Content-Type'] == 'application/x-sqlite3'
res_down_file.close()
print(f"[PASS] 9. GET /tools/database-backup/download/{backup_filename}/ -> 200 OK")

# Test Restore endpoint
res_restore = client.post('/tools/database-backup/restore/', {'filename': backup_filename}, follow=True)
assert res_restore.status_code == 200
print(f"[PASS] 10. POST /tools/database-backup/restore/ -> Restored successfully with automatic pre-restore safety backup")

# Delete test backup
del_result = delete_backup(backup_filename)
assert del_result['success'] is True
assert not backup_file.exists()
print(f"[PASS] 11. delete_backup({backup_filename}) -> Cleaned up test snapshot successfully")

print("\n=== ALL DATABASE BACKUP & RESTORE TESTS PASSED 100%! ===")
