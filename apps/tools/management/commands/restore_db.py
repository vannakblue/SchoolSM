from django.core.management.base import BaseCommand
from apps.tools.backup_utils import restore_database_backup, list_backups

class Command(BaseCommand):
    help = 'Restore the SQLite database from a selected backup snapshot file'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            help='Filename of the backup in backups/ directory to restore'
        )
        parser.add_argument(
            '--latest',
            action='store_true',
            help='Automatically restore the latest backup snapshot'
        )

    def handle(self, *args, **options):
        filename = options.get('file')
        latest = options.get('latest')

        backups = list_backups()
        if not backups:
            self.stdout.write(self.style.ERROR("[ERROR] No backups found in backups/ directory!"))
            return

        if latest:
            filename = backups[0]['filename']

        if not filename:
            self.stdout.write(self.style.WARNING("Available backup files:"))
            for idx, b in enumerate(backups, 1):
                self.stdout.write(f"  [{idx}] {b['filename']} ({b['created_at']}, {b['size_formatted']}) - {b['label']}")
            self.stdout.write("\nPlease specify --file <filename> or --latest to restore.")
            return

        self.stdout.write(f"Restoring database from: {filename}...")
        try:
            result = restore_database_backup(filename, user_info="CLI / run.bat")
            self.stdout.write(self.style.SUCCESS(f"[SUCCESS] {result['message']}"))
            self.stdout.write("A safety backup was automatically saved before replacing the database.")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"[ERROR] Failed to restore backup: {e}"))
