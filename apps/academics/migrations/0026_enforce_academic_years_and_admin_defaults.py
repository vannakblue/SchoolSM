# Data migration to enforce Academic Years 2025-2026 & 2026-2027 and permanent admin password '123'
from django.db import migrations
from datetime import date


def enforce_defaults(apps, schema_editor):
    from apps.accounts.system_defaults import ensure_system_defaults
    ensure_system_defaults()


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0025_clean_classroom_codes'),
    ]

    operations = [
        migrations.RunPython(enforce_defaults, reverse_code=migrations.RunPython.noop),
    ]
