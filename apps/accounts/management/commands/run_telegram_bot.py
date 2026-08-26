import time
import logging
import requests
from django.core.management.base import BaseCommand
from apps.accounts.models import TelegramConfig
from apps.accounts.utils import edit_telegram_message, answer_telegram_callback_query
from apps.attendance.telegram_utils import process_teacher_leave_action

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Runs long-polling Telegram Bot listener to process interactive button clicks (Leave Approval, etc.).'

    def handle(self, *args, **options):
        config = TelegramConfig.objects.first()
        if not (config and config.is_active and config.bot_token):
            self.stderr.write(self.style.ERROR("Telegram Bot is not active or Bot Token is not configured!"))
            return

        bot_token = config.bot_token
        self.stdout.write(self.style.SUCCESS("🤖 Telegram Bot Polling started! Listening for interactive button clicks... (Press CTRL+C to stop)"))
        
        offset = 0
        while True:
            try:
                url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
                params = {'offset': offset, 'timeout': 30}
                resp = requests.get(url, params=params, timeout=35)
                
                if resp.status_code == 200:
                    updates = resp.json().get('result', [])
                    for u in updates:
                        offset = u['update_id'] + 1
                        
                        # Handle Callback Query
                        if 'callback_query' in u:
                            cb = u['callback_query']
                            cb_id = cb.get('id')
                            cb_data = cb.get('data', '')
                            user_info = cb.get('from', {})
                            first_name = user_info.get('first_name', '')
                            username = user_info.get('username')
                            user_disp = f"{first_name} (@{username})" if username else (first_name or "Admin តាម Telegram")
                            
                            msg = cb.get('message', {})
                            chat_id = msg.get('chat', {}).get('id')
                            message_id = msg.get('message_id')
                            
                            if cb_data.startswith('leave:'):
                                parts = cb_data.split(':')
                                if len(parts) >= 3:
                                    action = parts[1]
                                    leave_id = parts[2]
                                    res = process_teacher_leave_action(
                                        leave_id=leave_id,
                                        action=action,
                                        approver_name=user_disp
                                    )
                                    self.stdout.write(self.style.SUCCESS(f"Processed {action} for Leave #{leave_id}: {res.get('message')}"))
                                    
                                    toast_text = res.get('message', 'បានដំណើរការរួចរាល់!')
                                    answer_telegram_callback_query(cb_id, text=toast_text, show_alert=True)
                                    
                                    if chat_id and message_id and 'updated_text' in res:
                                        edit_telegram_message(
                                            chat_id=chat_id,
                                            message_id=message_id,
                                            text=res['updated_text'],
                                            reply_markup=None
                                        )
                time.sleep(1)
            except KeyboardInterrupt:
                self.stdout.write(self.style.NOTICE("Telegram Bot Poller stopped."))
                break
            except Exception as e:
                self.stderr.write(self.style.WARNING(f"Polling error (will retry): {e}"))
                time.sleep(3)
