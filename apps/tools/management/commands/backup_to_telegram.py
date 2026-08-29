from django.core.management.base import BaseCommand
from apps.tools.backup_utils import send_database_backup_to_telegram


class Command(BaseCommand):
    help = 'Automated Database Backup Pipeline: Generates snapshot/dump and delivers directly to Telegram.'

    def add_arguments(self, parser):
        parser.add_argument('--chat-id', type=str, default=None, help='Target Telegram Chat ID / Channel ID')
        parser.add_argument('--format', type=str, default='json', choices=['json', 'sqlite3'], help='Backup format: json or sqlite3')
        parser.add_argument('--sender', type=str, default='Cron Pipeline / Server', help='Sender display label')

    def handle(self, *args, **options):
        chat_id = options.get('chat_id')
        format_type = options.get('format')
        sender = options.get('sender')

        self.stdout.write(f"Initiating Database Backup Pipeline to Telegram (Format: {format_type})...")
        result = send_database_backup_to_telegram(
            custom_chat_id=chat_id,
            format_type=format_type,
            sender_user=sender
        )

        if result['success']:
            self.stdout.write(self.style.SUCCESS(result['message']))
        else:
            self.stdout.write(self.style.ERROR(result['message']))
