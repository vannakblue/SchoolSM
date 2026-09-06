from django.core.management.base import BaseCommand
from apps.academics.models import AcademicYear
from apps.accounts.models import GoogleSheetsConfig
from apps.tools.google_sheets_service import GoogleSheetsService


class Command(BaseCommand):
    help = 'Restore / Re-import data from a specific Academic Year Google Sheet back into the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--year',
            type=str,
            required=True,
            help='Academic Year name or ID to restore from (e.g. "2025-2026")'
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm restoration without interactive prompt'
        )

    def handle(self, *args, **options):
        config = GoogleSheetsConfig.get_config()
        if not config.is_configured():
            self.stdout.write(self.style.ERROR("[ERROR] Google Sheets is not configured."))
            return

        year_str = options['year'].strip()
        ay = AcademicYear.objects.filter(name=year_str).first() or AcademicYear.objects.filter(id=year_str if year_str.isdigit() else None).first()
        if not ay:
            self.stdout.write(self.style.ERROR(f"[ERROR] Academic Year '{year_str}' not found."))
            return

        if not options['confirm']:
            self.stdout.write(self.style.WARNING(
                f"You are about to restore data from Google Sheets for Academic Year: '{ay.name}'.\n"
                "Existing matching records will be updated or new ones added. Pass --confirm to proceed."
            ))
            return

        self.stdout.write(f"Connecting to Google Sheets and restoring '{ay.name}'...")
        service = GoogleSheetsService(config=config)
        try:
            results = service.restore_from_academic_spreadsheet(ay)
            self.stdout.write(self.style.SUCCESS(f"[SUCCESS] Restore completed for {ay.name}:"))
            self.stdout.write(f" - Students Created: {results['students_created']}")
            self.stdout.write(f" - Students Updated: {results['students_restored']}")
            self.stdout.write(f" - Expenses Restored: {results['expenses_restored']}")
            if results['errors']:
                self.stdout.write(self.style.WARNING(f"Warnings/Errors: {len(results['errors'])}"))
                for err in results['errors']:
                    self.stdout.write(f"   * {err}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"[ERROR] Restoration failed: {e}"))
