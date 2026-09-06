from django.core.management.base import BaseCommand
from apps.academics.models import AcademicYear
from apps.accounts.models import GoogleSheetsConfig
from apps.tools.google_sheets_service import GoogleSheetsService


class Command(BaseCommand):
    help = 'Sync data (Students with photos, Attendance, Incomes, Expenses) to Google Sheets organized by Academic Year'

    def add_arguments(self, parser):
        parser.add_argument(
            '--year',
            type=str,
            help='Academic Year name or ID (e.g. "2025-2026"). Defaults to the current active year.'
        )
        parser.add_argument(
            '--no-photos',
            action='store_true',
            help='Skip uploading student photos to Google Drive to speed up synchronization.'
        )
        parser.add_argument(
            '--all-years',
            action='store_true',
            help='Sync all registered Academic Years sequentially.'
        )

    def handle(self, *args, **options):
        config = GoogleSheetsConfig.get_config()
        if not config.is_configured():
            self.stdout.write(self.style.ERROR(
                "[ERROR] Google Sheets integration is not configured.\n"
                "Please add your google_service_account.json file or paste credentials in the Web Dashboard."
            ))
            return

        if options['no_photos']:
            config.sync_students_with_photos = False

        service = GoogleSheetsService(config=config)

        if options['all_years']:
            years = AcademicYear.objects.all().order_by('-start_date')
        elif options['year']:
            query = options['year'].strip()
            ay = AcademicYear.objects.filter(name=query).first() or AcademicYear.objects.filter(id=query if query.isdigit() else None).first()
            if not ay:
                self.stdout.write(self.style.ERROR(f"[ERROR] Academic Year '{options['year']}' not found."))
                return
            years = [ay]
        else:
            current_year = AcademicYear.objects.filter(is_current=True).first() or AcademicYear.objects.order_by('-start_date').first()
            if not current_year:
                self.stdout.write(self.style.ERROR("[ERROR] No Academic Year configured in system."))
                return
            years = [current_year]

        for ay in years:
            self.stdout.write(f"\n[SYNCING] Starting Google Sheets synchronization for Academic Year: {ay.name}...")
            try:
                stats = service.sync_academic_year(ay)
                self.stdout.write(self.style.SUCCESS(f"[SUCCESS] Academic Year: {ay.name} synced!"))
                self.stdout.write(f" - Students: {stats['students_synced']} (Photos uploaded: {stats['photos_uploaded']})")
                self.stdout.write(f" - Attendance records: {stats['attendance_synced']}")
                self.stdout.write(f" - Incomes: {stats['incomes_synced']}")
                self.stdout.write(f" - Expenses: {stats['expenses_synced']}")
                self.stdout.write(self.style.SUCCESS(f" - Spreadsheet URL: {stats['spreadsheet_url']}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"[ERROR] Failed syncing {ay.name}: {e}"))
