from django.core.management.base import BaseCommand
from apps.accounts.system_defaults import ensure_system_defaults

class Command(BaseCommand):
    help = "Enforces permanent admin password (123) and keeps only Academic Years 2025-2026 and 2026-2027 as default for every update."

    def add_arguments(self, parser):
        parser.add_argument(
            '--purge',
            action='store_true',
            help='Purge non-default academic years (only when explicitly requested by admin)',
        )

    def handle(self, *args, **options):
        purge = options.get('purge', False)
        self.stdout.write("Applying system defaults (Admin password '123' & Academic Years '2025-2026', '2026-2027')...")
        ensure_system_defaults(stdout=self.stdout, purge_non_defaults=purge)
        self.stdout.write(self.style.SUCCESS("Successfully enforced system defaults!"))

