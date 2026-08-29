import re
import requests
from django.conf import settings
from .models import TelegramConfig, NotificationLog


def extract_chat_ids(target):
    """
    Extracts a list of clean, unique Telegram chat IDs from string (comma/semicolon/newline separated) or list/tuple.
    Supports: "-100111, -100222, @channel", "-100111; -100222", etc.
    """
    if not target:
        return []
    if isinstance(target, (list, tuple, set)):
        items = target
    else:
        # Split by comma, semicolon, newline, or whitespace if formatted with multiple IDs
        items = re.split(r'[,;\n\r]+|\s+(?=[@\-\d])', str(target).strip())
    
    result = []
    for item in items:
        cleaned = str(item).strip()
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return result


def send_telegram_notification(title, message, recipient_name="សិស្ស / អាណាព្យាបាល", recipient_phone=None, recipient_type="Parent", custom_chat_id=None, reply_markup=None):
    """
    Dispatches a notification via Telegram Bot API to one or multiple Chat IDs.
    Supports multiple comma-separated chat IDs (e.g. "-100111, -100222, @channel").
    Optionally accepts reply_markup (inline keyboard).
    """
    config = TelegramConfig.objects.first()
    target_raw = custom_chat_id or (config.chat_id if config else None)
    chat_ids = extract_chat_ids(target_raw)
    bot_token = config.bot_token if config else None
    
    status = NotificationLog.Status.SIMULATED
    
    formatted_msg = f"🔔 *{title}*\n\n{message}\n\n🏫 _ប្រព័ន្ធគ្រប់គ្រងសាលារៀន (SchoolSM)_"
    
    if config and config.is_active and bot_token and chat_ids:
        any_success = False
        all_failed = True
        for cid in chat_ids:
            try:
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                payload = {
                    'chat_id': cid,
                    'text': formatted_msg,
                    'parse_mode': 'Markdown'
                }
                if reply_markup:
                    payload['reply_markup'] = reply_markup
                resp = requests.post(url, json=payload, timeout=5)
                if resp.status_code == 200:
                    any_success = True
                    all_failed = False
            except Exception:
                pass
        
        if any_success:
            status = NotificationLog.Status.SENT
        elif all_failed:
            status = NotificationLog.Status.FAILED

    # Always log the event in NotificationLog
    target_display = ", ".join(chat_ids) if chat_ids else ''
    log_recipient = recipient_name or 'គណៈគ្រប់គ្រង / អ្នកទទួល'
    if target_display and target_display not in log_recipient:
        log_recipient = f"{log_recipient} ({target_display})"

    log = NotificationLog.objects.create(
        title=title,
        message=message,
        recipient_type=recipient_type,
        recipient_name=log_recipient,
        recipient_phone=recipient_phone,
        channel=NotificationLog.Channel.TELEGRAM,
        status=status
    )
    return log


def edit_telegram_message(chat_id, message_id, text, reply_markup=None, parse_mode='Markdown'):
    """
    Edits an existing Telegram message in place (e.g. updating approval status and removing buttons).
    """
    config = TelegramConfig.objects.first()
    bot_token = config.bot_token if config else None
    if not (config and config.is_active and bot_token and chat_id and message_id):
        return False

    try:
        url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
        payload = {
            'chat_id': chat_id,
            'message_id': message_id,
            'text': text,
            'parse_mode': parse_mode
        }
        if reply_markup is not None:
            payload['reply_markup'] = reply_markup
        resp = requests.post(url, json=payload, timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def answer_telegram_callback_query(callback_query_id, text=None, show_alert=False):
    """
    Answers an incoming callback query to dismiss loading state or show toast/alert on user's Telegram client.
    """
    config = TelegramConfig.objects.first()
    bot_token = config.bot_token if config else None
    if not (config and config.is_active and bot_token and callback_query_id):
        return False

    try:
        url = f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery"
        payload = {
            'callback_query_id': callback_query_id,
            'show_alert': show_alert
        }
        if text:
            payload['text'] = text
        resp = requests.post(url, json=payload, timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def send_telegram_document(document_bytes, filename, caption, recipient_name="គណៈគ្រប់គ្រង / អ្នកទទួល", recipient_type="Management", custom_chat_id=None, content_type=None):
    """
    Dispatches a document file (e.g. JSON Backup, SQLite3 Database, Excel, PDF) to Telegram.
    """
    import mimetypes
    config = TelegramConfig.objects.first()
    target_raw = custom_chat_id or (config.chat_id if config else None)
    chat_ids = extract_chat_ids(target_raw)
    bot_token = config.bot_token if config else None

    if not content_type:
        if filename.endswith('.json'):
            content_type = 'application/json'
        elif filename.endswith(('.sqlite3', '.db')):
            content_type = 'application/x-sqlite3'
        elif filename.endswith('.xlsx'):
            content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        elif filename.endswith('.pdf'):
            content_type = 'application/pdf'
        else:
            content_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'

    status = NotificationLog.Status.SIMULATED
    if config and config.is_active and bot_token and chat_ids:
        any_success = False
        all_failed = True
        for cid in chat_ids:
            try:
                url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
                files = {
                    'document': (filename, document_bytes, content_type)
                }
                data = {
                    'chat_id': cid,
                    'caption': caption,
                    'parse_mode': 'Markdown'
                }
                resp = requests.post(url, data=data, files=files, timeout=30)
                if resp.status_code == 200:
                    any_success = True
                    all_failed = False
            except Exception:
                pass

        if any_success:
            status = NotificationLog.Status.SENT
        elif all_failed:
            status = NotificationLog.Status.FAILED

    target_display = ", ".join(chat_ids) if chat_ids else ''
    log_recipient = recipient_name or 'គណៈគ្រប់គ្រង / អ្នកទទួល'
    if target_display and target_display not in log_recipient:
        log_recipient = f"{log_recipient} ({target_display})"

    log = NotificationLog.objects.create(
        title=f"ឯកសារ: {filename}",
        message=caption,
        recipient_type=recipient_type,
        recipient_name=log_recipient,
        channel=NotificationLog.Channel.TELEGRAM,
        status=status
    )
    return log


def send_telegram_photo(photo_bytes, filename, caption, recipient_name="សិស្ស / អាណាព្យាបាល", recipient_type="Parent", custom_chat_id=None):
    """
    Dispatches a photo/image snapshot (e.g. Report Card Image) to Telegram.
    """
    config = TelegramConfig.objects.first()
    target_raw = custom_chat_id or (config.chat_id if config else None)
    chat_ids = extract_chat_ids(target_raw)
    bot_token = config.bot_token if config else None

    status = NotificationLog.Status.SIMULATED
    if config and config.is_active and bot_token and chat_ids:
        any_success = False
        all_failed = True
        for cid in chat_ids:
            try:
                url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
                files = {
                    'photo': (filename, photo_bytes, 'image/png')
                }
                data = {
                    'chat_id': cid,
                    'caption': caption,
                    'parse_mode': 'Markdown'
                }
                resp = requests.post(url, data=data, files=files, timeout=15)
                if resp.status_code == 200:
                    any_success = True
                    all_failed = False
            except Exception:
                pass

        if any_success:
            status = NotificationLog.Status.SENT
        elif all_failed:
            status = NotificationLog.Status.FAILED

    target_display = ", ".join(chat_ids) if chat_ids else ''
    log_recipient = recipient_name or 'គណៈគ្រប់គ្រង / អ្នកទទួល'
    if target_display and target_display not in log_recipient:
        log_recipient = f"{log_recipient} ({target_display})"

    log = NotificationLog.objects.create(
        title=f"រូបភាព: {filename}",
        message=caption,
        recipient_type=recipient_type,
        recipient_name=log_recipient,
        channel=NotificationLog.Channel.TELEGRAM,
        status=status
    )
    return log


