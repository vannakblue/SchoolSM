import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from apps.accounts.models import User

count = 0
for u in User.objects.all():
    if u.check_password('password123'):
        u.set_password('p123456')
        u.save(update_fields=['password'])
        count += 1

print(f"DONE: Updated {count} existing users with password123 to p123456.")
