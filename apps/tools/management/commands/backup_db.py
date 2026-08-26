from django.core.management.base import BaseCommand
from apps.tools.backup_utils import create_database_backup, list_backups, get_db_statistics

class Command(BaseCommand):
    help = 'Create an instant snapshot backup of the SQLite database (db.sqlite3)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--label',
            type=str,
            default='CLI Manual Backup',
            help='Optional note or label for this snapshot'
        )
        parser.add_argument(
            '--list',
            action='store_true',
            help='List all existing backups without creating a new one'
        )

    def handle(self, *args, **options):
        if options['list']:
            backups = list_backups()
            if not backups:
                self.stdout.write(self.style.WARNING("No backups found in backups/ directory."))
                return
            self.stdout.write(self.style.SUCCESS(f"Found {len(backups)} backup snapshot(s):"))
            for b in backups:
                self.stdout.write(f" - [{b['created_at']}] {b['filename']} ({b['size_formatted']}) - {b['label']}")
            return

        label = options['label']
        self.stdout.write(f"Creating database snapshot with label: '{label}'...")
        try:
            result = create_database_backup(label=label, user_info="CLI / run.bat")
            self.stdout.write(self.style.SUCCESS(f"[SUCCESS] Backup created: {result['filename']}"))
            self.stdout.write(f"Location: {result['filepath']}")
            self.stdout.write(f"Size: {result['metadata']['size_formatted']}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"[ERROR] Failed to create backup: {e}"))
