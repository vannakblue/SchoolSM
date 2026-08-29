from django.core.management.base import BaseCommand
from apps.tools.backup_utils import send_database_backup_to_telegram, check_and_run_scheduled_backup


class Command(BaseCommand):
    help = 'Automated Database Backup Pipeline: Generates snapshot/dump and delivers directly to Telegram.'

    def add_arguments(self, parser):
        parser.add_argument('--auto-check', action='store_true', help='Checks Admin-configured schedule from Web UI before running')
        parser.add_argument('--force', action='store_true', help='Forces dispatch regardless of schedule or time match')
        parser.add_argument('--chat-id', type=str, default=None, help='Target Telegram Chat ID / Channel ID')
        parser.add_argument('--format', type=str, default=None, choices=['json', 'sqlite3'], help='Backup format: json or sqlite3')
        parser.add_argument('--sender', type=str, default='Cron Pipeline / Server', help='Sender display label')

    def handle(self, *args, **options):
        auto_check = options.get('auto_check', False)
        force = options.get('force', False)
        chat_id = options.get('chat_id')
        format_type = options.get('format')
        sender = options.get('sender')

        if auto_check:
            self.stdout.write("Checking Admin-configured automated backup schedule from Web UI...")
            res = check_and_run_scheduled_backup(force=force)
            if res.get('executed'):
                self.stdout.write(self.style.SUCCESS(res.get('message', 'Backup executed successfully!')))
            else:
                self.stdout.write(self.style.NOTICE(res.get('message', 'No backup needed at this time.')))
            return

        fmt = format_type or 'json'
        self.stdout.write(f"Initiating Database Backup Pipeline to Telegram (Format: {fmt})...")
        result = send_database_backup_to_telegram(
            custom_chat_id=chat_id,
            format_type=fmt,
            sender_user=sender
        )

        if result['success']:
            self.stdout.write(self.style.SUCCESS(result['message']))
        else:
            self.stdout.write(self.style.ERROR(result['message']))

