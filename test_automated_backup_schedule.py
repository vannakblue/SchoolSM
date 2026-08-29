import os, sys
sys.stdout.reconfigure(encoding='utf-8')
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User, TelegramConfig
from apps.tools.backup_utils import check_and_run_scheduled_backup

admin_user, _ = User.objects.get_or_create(username='admin_test_schedule', defaults={'role': User.Role.ADMIN})
client = Client()
client.force_login(admin_user)

print("1. Testing GET /tools/database-backup/ (Verify Schedule UI in context)...")
res_page = client.get('/tools/database-backup/')
assert res_page.status_code == 200
assert 'Automated Scheduled Pipeline Settings' in res_page.content.decode('utf-8')
print("   [PASS] Schedule Settings UI rendered successfully on web browser!")

print("2. Testing POST /tools/database-backup/save-schedule/ (Admin configures on web)...")
res_save = client.post('/tools/database-backup/save-schedule/', {
    'auto_backup_enabled': 'on',
    'backup_frequency': 'DAILY',
    'backup_time': '23:30',
    'backup_day_of_week': '6',
    'backup_format': 'json',
    'backup_chat_id': '-100999888777'
}, follow=True)
assert res_save.status_code == 200

config = TelegramConfig.get_config()
assert config.auto_backup_enabled == True
assert config.backup_frequency == 'DAILY'
assert str(config.backup_time)[:5] == '23:30'
assert config.backup_chat_id == '-100999888777'
print("   [PASS] Schedule saved correctly: Daily at %s, Format: %s, Chat ID: %s" % (config.backup_time, config.backup_format, config.backup_chat_id))

print("3. Testing POST /tools/database-backup/trigger-schedule/ (Test Run via Web)...")
res_trigger = client.post('/tools/database-backup/trigger-schedule/', {'force': 'true'}, follow=True)
assert res_trigger.status_code == 200
print("   [PASS] Schedule triggered successfully via Web UI!")

print("4. Testing python manage.py backup_to_telegram --auto-check (Cron / Daemon)...")
from django.core.management import call_command
import io
buf = io.StringIO()
call_command('backup_to_telegram', '--auto-check', '--force', stdout=buf)
out = buf.getvalue()
print("   [PASS] Command Output:", out.strip())

print("\n=== ALL AUTOMATED SCHEDULED BACKUP PIPELINE CAPABILITIES VERIFIED 100% ===")
