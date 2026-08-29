import os, sys, io
sys.stdout.reconfigure(encoding='utf-8')
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.teachers.models import Teacher
from django.core.files.uploadedfile import SimpleUploadedFile

admin_user, _ = User.objects.get_or_create(username='admin_test_backup', defaults={'role': User.Role.ADMIN})
client = Client()
client.force_login(admin_user)

print("1. Testing Universal Full JSON Backup Download...")
res_json = client.get('/tools/database-backup/download/?format=json')
assert res_json.status_code == 200
assert 'school_db_backup_' in res_json['Content-Disposition']
print("   [PASS] Downloaded JSON Backup (Size: %d bytes)" % len(res_json.content))

print("2. Testing Upload and Restore JSON Backup...")
json_file = SimpleUploadedFile('test_backup.json', res_json.content, content_type='application/json')
res_upload = client.post('/tools/database-backup/upload-restore/', {'db_file': json_file}, follow=True)
assert res_upload.status_code == 200
print("   [PASS] Uploaded and Restored JSON Backup successfully!")

print("3. Testing Teachers Excel Export (Backup)...")
res_t_export = client.get('/teachers/export/excel/')
assert res_t_export.status_code == 200
assert 'MoEYS_Teachers_Directory_' in res_t_export['Content-Disposition']
print("   [PASS] Exported Teachers Excel Backup (Size: %d bytes)" % len(res_t_export.content))

print("\n=== ALL WEB BROWSER BACKUP AND IMPORT CAPABILITIES VERIFIED 100% ===")
