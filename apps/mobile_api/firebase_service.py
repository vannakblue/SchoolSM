import logging
import os
from django.conf import settings
from .models import DeviceFCMToken, MobileNotificationLog

logger = logging.getLogger(__name__)

_firebase_initialized = False

def initialize_firebase():
    """
    Initializes Firebase Admin SDK if service account key JSON is present.
    """
    global _firebase_initialized
    if _firebase_initialized:
        return True

    try:
        import firebase_admin
        from firebase_admin import credentials

        import json
        raw_json = os.environ.get('FIREBASE_CREDENTIALS_JSON')
        if raw_json:
            try:
                cert_dict = json.loads(raw_json)
                cred = credentials.Certificate(cert_dict)
                firebase_admin.initialize_app(cred)
                _firebase_initialized = True
                logger.info("Firebase Admin SDK initialized from environment variable.")
                return True
            except Exception as e:
                logger.warning(f"Failed to parse FIREBASE_CREDENTIALS_JSON env var: {e}")

        cred_path = getattr(settings, 'FIREBASE_CREDENTIALS_PATH', None) or os.environ.get('FIREBASE_CREDENTIALS_PATH')
        if not cred_path:
            # Check default paths (project root or Render /etc/secrets/)
            candidate_paths = [
                os.path.join(settings.BASE_DIR, 'firebase_credentials.json'),
                '/etc/secrets/firebase_credentials.json',
            ]
            for p in candidate_paths:
                if os.path.exists(p):
                    cred_path = p
                    break

        if cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            _firebase_initialized = True
            logger.info("Firebase Admin SDK initialized successfully from file.")
            return True
        else:
            logger.info("Firebase credentials file not found. Push notifications will be logged to database only.")
            return False
    except Exception as e:
        logger.warning(f"Failed to initialize Firebase Admin SDK: {e}")
        return False


def send_mobile_push_notification(user, title, body, data=None):
    """
    Sends a push notification to all active devices of a given user via Firebase FCM,
    and records the notification in MobileNotificationLog.
    """
    if data is None:
        data = {}

    # 1. Log to database
    try:
        MobileNotificationLog.objects.create(
            user=user,
            title=title,
            body=body,
            data_payload=data
        )
    except Exception as e:
        logger.error(f"Failed to log mobile notification: {e}")

    # 2. Get active FCM tokens
    tokens = list(DeviceFCMToken.objects.filter(user=user, is_active=True).values_list('token', flat=True))
    if not tokens:
        return {'success': False, 'message': 'No registered active devices found for user.'}

    # 3. Send via Firebase
    if not initialize_firebase():
        return {'success': True, 'message': 'Logged in database. (Firebase credentials not yet provided)'}

    try:
        from firebase_admin import messaging

        # Convert data dict values to strings for FCM
        str_data = {str(k): str(v) for k, v in data.items()}

        messages = [
            messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                data=str_data,
                token=token,
            )
            for token in tokens
        ]

        response = messaging.send_all(messages)
        logger.info(f"FCM Multicast sent: {response.success_count} success, {response.failure_count} failures.")
        return {
            'success': True,
            'success_count': response.success_count,
            'failure_count': response.failure_count
        }
    except Exception as e:
        logger.error(f"Error sending FCM push notification: {e}")
        return {'success': False, 'error': str(e)}
