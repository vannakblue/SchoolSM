from django.core.management.base import BaseCommand
from apps.accounts.permanent_data_manager import export_permanent_admin_defaults, import_permanent_admin_defaults


class Command(BaseCommand):
    help = "Exports or imports permanent admin defaults to prevent any automated resets across Render deployments"

    def add_arguments(self, parser):
        parser.add_argument(
            '--load',
            action='store_true',
            help='Load and restore permanent admin defaults instead of exporting',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force reload/overwrite even if existing records exist',
        )

    def handle(self, *args, **options):
        if options.get('load'):
            self.stdout.write("Restoring permanent admin defaults...")
            success = import_permanent_admin_defaults(stdout=self.stdout, force=options.get('force', False))
            if success:
                self.stdout.write(self.style.SUCCESS("Permanent admin defaults successfully restored!"))
            else:
                self.stdout.write(self.style.WARNING("No permanent defaults found or import completed."))
        else:
            self.stdout.write("Exporting permanent admin defaults...")
            path = export_permanent_admin_defaults(stdout=self.stdout)
            self.stdout.write(self.style.SUCCESS(f"Saved snapshot to {path}"))
