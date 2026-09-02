import logging
import os
from decimal import Decimal
from datetime import datetime
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)

_firestore_client = None
_firestore_initialized = False


def get_firestore_db():
    """
    Initializes and returns the Google Firebase Firestore client.
    Uses firebase_credentials.json from project root or environment variables.
    """
    global _firestore_client, _firestore_initialized
    if _firestore_client is not None:
        return _firestore_client

    try:
        import firebase_admin
        from firebase_admin import credentials, firestore

        # Check if already initialized in firebase_admin
        if not firebase_admin._apps:
            raw_json = os.environ.get('FIREBASE_CREDENTIALS_JSON')
            if raw_json:
                import json
                cert_dict = json.loads(raw_json)
                cred = credentials.Certificate(cert_dict)
                firebase_admin.initialize_app(cred)
            else:
                cred_path = getattr(settings, 'FIREBASE_CREDENTIALS_PATH', None) or os.environ.get('FIREBASE_CREDENTIALS_PATH')
                if not cred_path:
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
                else:
                    logger.warning("Firebase credentials JSON file not found for Firestore.")
                    return None

        _firestore_client = firestore.client()
        _firestore_initialized = True
        logger.info("Firestore client initialized successfully.")
        return _firestore_client
    except Exception as e:
        logger.warning(f"Failed to initialize Firebase Firestore client: {e}")
        return None


def serialize_data(val):
    """Recursively converts Decimal and datetime objects for Firestore compatibility."""
    if isinstance(val, Decimal):
        return float(val)
    elif isinstance(val, datetime):
        return val.isoformat()
    elif isinstance(val, dict):
        return {k: serialize_data(v) for k, v in val.items()}
    elif isinstance(val, (list, tuple, set)):
        return [serialize_data(i) for i in val]
    return val


def log_fee_inquiry_to_firestore(student, chat_id, total_due, details=None, user_disp="Parent"):
    """
    Logs student fee inquiry event in local audit log and syncs to Firestore collection 'student_fee_inquiries'.
    """
    from apps.finance.models import FirestorePaymentAuditLog
    if details is None:
        details = {}

    student_id = student.student_id if student else "N/A"
    student_name = student.khmer_name if student else "N/A"
    classroom_name = student.classroom.name if (student and student.classroom) else "N/A"
    amount = Decimal(str(total_due or 0.00))

    payload = {
        'student_id': student_id,
        'student_name': student_name,
        'student_latin_name': student.latin_name if student else '',
        'classroom': classroom_name,
        'chat_id': str(chat_id),
        'user_disp': str(user_disp),
        'total_due': float(amount),
        'currency': '៛',
        'details': serialize_data(details),
        'queried_at': timezone.now().isoformat(),
        'source': 'TELEGRAM_BOT'
    }

    # 1. Create local audit mirror
    audit_log = FirestorePaymentAuditLog.objects.create(
        event_type=FirestorePaymentAuditLog.EventType.INQUIRY,
        student=student,
        student_id_str=student_id,
        student_name=student_name,
        classroom_name=classroom_name,
        amount=amount,
        currency='៛',
        fee_category_name='Inquiry: ទឹកភ្លើង & ថវិកាដើមឆ្នាំ',
        channel='TELEGRAM_BOT',
        telegram_user_info=f"{user_disp} (Chat: {chat_id})",
        payload_data=payload
    )

    # 2. Push to Firestore
    db = get_firestore_db()
    if db:
        try:
            doc_ref = db.collection('student_fee_inquiries').document()
            doc_ref.set(payload)
            audit_log.firestore_doc_id = doc_ref.id
            audit_log.is_synced_to_firestore = True
            audit_log.save(update_fields=['firestore_doc_id', 'is_synced_to_firestore'])
            logger.info(f"Logged fee inquiry for {student_id} to Firestore doc {doc_ref.id}")
            return {'success': True, 'firestore_id': doc_ref.id}
        except Exception as e:
            logger.error(f"Error syncing inquiry to Firestore: {e}")
            return {'success': False, 'error': str(e), 'local_id': audit_log.id}

    return {'success': True, 'local_id': audit_log.id, 'synced': False}


def log_qr_dispatch_to_firestore(student, bank_method, amount, currency="៛", memo="", chat_id=None, user_disp="Parent"):
    """
    Logs bank QR code dispatch in local audit log and syncs to Firestore collection 'qr_code_dispatches'.
    """
    from apps.finance.models import FirestorePaymentAuditLog

    student_id = student.student_id if student else "N/A"
    student_name = student.khmer_name if student else "N/A"
    classroom_name = student.classroom.name if (student and student.classroom) else "N/A"
    bank_name = bank_method.bank_name if bank_method else "ABA Bank"
    account_name = bank_method.account_name if bank_method else "School Management"
    account_number = bank_method.account_number if bank_method else ""

    payload = {
        'student_id': student_id,
        'student_name': student_name,
        'classroom': classroom_name,
        'bank_name': bank_name,
        'account_name': account_name,
        'account_number': account_number,
        'amount': float(amount or 0),
        'currency': currency,
        'memo': memo,
        'chat_id': str(chat_id) if chat_id else '',
        'dispatched_at': timezone.now().isoformat(),
        'source': 'TELEGRAM_BOT'
    }

    audit_log = FirestorePaymentAuditLog.objects.create(
        event_type=FirestorePaymentAuditLog.EventType.QR_DISPATCH,
        student=student,
        student_id_str=student_id,
        student_name=student_name,
        classroom_name=classroom_name,
        amount=Decimal(str(amount or 0)),
        currency=currency,
        fee_category_name=f"QR: {bank_name}",
        channel='TELEGRAM_BOT',
        telegram_user_info=f"{user_disp} (Chat: {chat_id})",
        payload_data=payload
    )

    db = get_firestore_db()
    if db:
        try:
            doc_ref = db.collection('qr_code_dispatches').document()
            doc_ref.set(payload)
            audit_log.firestore_doc_id = doc_ref.id
            audit_log.is_synced_to_firestore = True
            audit_log.save(update_fields=['firestore_doc_id', 'is_synced_to_firestore'])
            return {'success': True, 'firestore_id': doc_ref.id}
        except Exception as e:
            logger.error(f"Error syncing QR dispatch to Firestore: {e}")
            return {'success': False, 'error': str(e), 'local_id': audit_log.id}

    return {'success': True, 'local_id': audit_log.id, 'synced': False}


def log_payment_slip_to_firestore(slip_obj):
    """
    Logs payment slip submission to Firestore collection 'payment_slip_submissions'.
    """
    from apps.finance.models import FirestorePaymentAuditLog

    student = slip_obj.student
    student_id = student.student_id if student else "N/A"
    student_name = student.khmer_name if student else "N/A"
    classroom_name = student.classroom.name if (student and student.classroom) else "N/A"

    payload = {
        'slip_id': slip_obj.id,
        'student_id': student_id,
        'student_name': student_name,
        'classroom': classroom_name,
        'fee_type': slip_obj.fee_type,
        'target_months': slip_obj.target_months,
        'claimed_amount': float(slip_obj.claimed_amount),
        'currency': slip_obj.currency,
        'status': slip_obj.status,
        'telegram_user_id': slip_obj.telegram_user_id or '',
        'telegram_username': slip_obj.telegram_username or '',
        'telegram_chat_id': slip_obj.telegram_chat_id or '',
        'submitted_at': slip_obj.created_at.isoformat() if slip_obj.created_at else timezone.now().isoformat(),
        'reviewed_by': str(slip_obj.reviewed_by) if slip_obj.reviewed_by else '',
        'reviewed_at': slip_obj.reviewed_at.isoformat() if slip_obj.reviewed_at else None,
        'notes': slip_obj.notes or ''
    }

    audit_log = FirestorePaymentAuditLog.objects.create(
        event_type=FirestorePaymentAuditLog.EventType.SLIP_SUBMISSION,
        student=student,
        student_id_str=student_id,
        student_name=student_name,
        classroom_name=classroom_name,
        amount=slip_obj.claimed_amount,
        currency=slip_obj.currency,
        fee_category_name=f"Slip: {slip_obj.get_fee_type_display()}",
        channel='TELEGRAM_BOT',
        telegram_user_info=f"@{slip_obj.telegram_username or 'user'} ({slip_obj.telegram_chat_id})",
        payload_data=payload
    )

    db = get_firestore_db()
    if db:
        try:
            doc_id = f"slip_{slip_obj.id}"
            doc_ref = db.collection('payment_slip_submissions').document(doc_id)
            doc_ref.set(payload)
            slip_obj.firestore_doc_id = doc_id
            slip_obj.save(update_fields=['firestore_doc_id'])
            audit_log.firestore_doc_id = doc_id
            audit_log.is_synced_to_firestore = True
            audit_log.save(update_fields=['firestore_doc_id', 'is_synced_to_firestore'])
            return {'success': True, 'firestore_id': doc_id}
        except Exception as e:
            logger.error(f"Error syncing slip to Firestore: {e}")
            return {'success': False, 'error': str(e), 'local_id': audit_log.id}

    return {'success': True, 'local_id': audit_log.id, 'synced': False}


def log_payment_transaction_to_firestore(payment_record, user_disp="Admin", receipt_no=None, payment_type="MONTHLY_UTILITY"):
    """
    Logs confirmed payment transaction to Firestore collection 'school_payment_logs'.
    Handles both StudentMonthlyPayment and Invoice/PaymentTransaction records.
    """
    from apps.finance.models import FirestorePaymentAuditLog, StudentMonthlyPayment, PaymentTransaction

    if isinstance(payment_record, StudentMonthlyPayment):
        student = payment_record.student
        amount = payment_record.paid_amount
        currency = "៛"
        rec_no = payment_record.receipt_no or receipt_no or f"REC-UF-{payment_record.id}"
        fee_title = f"ថ្លៃទឹកភ្លើង ខែ {payment_record.month}"
        method = payment_record.payment_method
        pay_date = payment_record.payment_date or timezone.now()
    elif isinstance(payment_record, PaymentTransaction):
        student = payment_record.invoice.student
        amount = payment_record.amount
        currency = "$"
        rec_no = payment_record.receipt_number or receipt_no or f"REC-INV-{payment_record.id}"
        fee_title = payment_record.invoice.fee_category.name
        method = payment_record.payment_method
        pay_date = payment_record.payment_date or timezone.now()
    else:
        return {'success': False, 'message': 'Unknown payment record type'}

    student_id = student.student_id if student else "N/A"
    student_name = student.khmer_name if student else "N/A"
    classroom_name = student.classroom.name if (student and student.classroom) else "N/A"

    payload = {
        'receipt_number': rec_no,
        'student_id': student_id,
        'student_name': student_name,
        'student_latin_name': student.latin_name if student else '',
        'classroom': classroom_name,
        'fee_title': fee_title,
        'payment_type': payment_type,
        'amount': float(amount),
        'currency': currency,
        'payment_method': method,
        'payment_date': pay_date.isoformat() if hasattr(pay_date, 'isoformat') else str(pay_date),
        'recorded_by': str(user_disp),
        'synced_at': timezone.now().isoformat(),
        'status': 'PAID'
    }

    audit_log = FirestorePaymentAuditLog.objects.create(
        event_type=FirestorePaymentAuditLog.EventType.PAYMENT_CONFIRMED,
        student=student,
        student_id_str=student_id,
        student_name=student_name,
        classroom_name=classroom_name,
        amount=amount,
        currency=currency,
        fee_category_name=fee_title,
        channel='TELEGRAM_BOT' if 'Telegram' in str(user_disp) else 'WEB_ADMIN',
        telegram_user_info=str(user_disp),
        payload_data=payload
    )

    db = get_firestore_db()
    if db:
        try:
            doc_id = f"tx_{rec_no.replace('/', '_').replace(' ', '_')}"
            doc_ref = db.collection('school_payment_logs').document(doc_id)
            doc_ref.set(payload)
            audit_log.firestore_doc_id = doc_id
            audit_log.is_synced_to_firestore = True
            audit_log.save(update_fields=['firestore_doc_id', 'is_synced_to_firestore'])
            return {'success': True, 'firestore_id': doc_id}
        except Exception as e:
            logger.error(f"Error syncing payment transaction to Firestore: {e}")
            return {'success': False, 'error': str(e), 'local_id': audit_log.id}

    return {'success': True, 'local_id': audit_log.id, 'synced': False}


def sync_all_local_payments_to_firestore():
    """
    Bulk syncs all un-synced FirestorePaymentAuditLog entries and payment transactions to Firebase Firestore.
    """
    from apps.finance.models import FirestorePaymentAuditLog, StudentMonthlyPayment, PaymentTransaction

    db = get_firestore_db()
    if not db:
        return {'success': False, 'message': 'Firebase Firestore មិនអាចតភ្ជាប់បានឡើយ។ សូមពិនិត្យឯកសារ credentials JSON។'}

    synced_count = 0
    failed_count = 0

    # 1. Sync pending local audit logs
    unsynced_logs = FirestorePaymentAuditLog.objects.filter(is_synced_to_firestore=False)
    for log in unsynced_logs:
        try:
            col_name = 'school_payment_logs' if log.event_type == FirestorePaymentAuditLog.EventType.PAYMENT_CONFIRMED else 'student_fee_inquiries'
            doc_ref = db.collection(col_name).document()
            doc_ref.set(log.payload_data or {'event_type': log.event_type, 'student': log.student_name, 'amount': float(log.amount)})
            log.firestore_doc_id = doc_ref.id
            log.is_synced_to_firestore = True
            log.save(update_fields=['firestore_doc_id', 'is_synced_to_firestore'])
            synced_count += 1
        except Exception as e:
            logger.error(f"Failed to sync audit log #{log.id}: {e}")
            failed_count += 1
            if '404' in str(e) or 'does not exist' in str(e):
                return {
                    'success': True,
                    'synced_count': 0,
                    'failed_count': unsynced_logs.count(),
                    'message': 'ទិន្នន័យត្រូវបានរក្សាទុកក្នុង Local Audit Logs។ សូមបង្កើត Firestore Database លើ Google Cloud Console ដើម្បី Sync ទៅ Cloud។'
                }

    # 2. Sync any StudentMonthlyPayment with paid_amount > 0 that might not be synced
    paid_monthly = StudentMonthlyPayment.objects.filter(paid_amount__gt=0).select_related('student', 'student__classroom')
    for p in paid_monthly[:100]:
        rec_no = p.receipt_no or f"UF-M{p.month}-{p.student.id}"
        doc_id = f"tx_{rec_no.replace('/', '_')}"
        try:
            doc_ref = db.collection('school_payment_logs').document(doc_id)
            doc_snap = doc_ref.get()
            if not doc_snap.exists:
                doc_ref.set({
                    'receipt_number': rec_no,
                    'student_id': p.student.student_id,
                    'student_name': p.student.khmer_name,
                    'classroom': p.student.classroom.name if p.student.classroom else '',
                    'fee_title': f"ថ្លៃទឹកភ្លើង ខែ {p.month}",
                    'payment_type': 'MONTHLY_UTILITY',
                    'amount': float(p.paid_amount),
                    'currency': '៛',
                    'payment_method': p.payment_method,
                    'payment_date': p.payment_date.isoformat() if p.payment_date else p.created_at.isoformat(),
                    'recorded_by': 'System Sync',
                    'synced_at': timezone.now().isoformat(),
                    'status': 'PAID'
                })
                synced_count += 1
        except Exception as e:
            logger.warning(f"Error bulk syncing monthly payment {rec_no}: {e}")
            if '404' in str(e) or 'does not exist' in str(e):
                break

    return {
        'success': True,
        'synced_count': synced_count,
        'failed_count': failed_count,
        'message': f"បាន Sync ទិន្នន័យ {synced_count} កំណត់ត្រាទៅកាន់ Google Firebase Firestore ជោគជ័យ!"
    }


def export_firestore_payment_logs(limit=500):
    """
    Fetches real-time records from Firebase Firestore collections for backup or audit viewer.
    Falls back gracefully to local audit logs if Firestore is offline or collection is empty.
    """
    from apps.finance.models import FirestorePaymentAuditLog

    def get_local_fallback():
        local_logs = FirestorePaymentAuditLog.objects.all().order_by('-created_at')[:limit]
        return [
            {
                'id': str(l.id),
                'doc_id': l.firestore_doc_id or str(l.id),
                'event_type': l.get_event_type_display(),
                'student_id': l.student_id_str or '',
                'student_name': l.student_name or '',
                'amount': float(l.amount),
                'currency': l.currency,
                'fee_category': l.fee_category_name or '',
                'channel': l.channel,
                'timestamp': l.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'is_synced': l.is_synced_to_firestore,
                'source': 'Local Database (Firestore Ready)'
            }
            for l in local_logs
        ]

    db = get_firestore_db()
    if not db:
        return get_local_fallback()

    try:
        results = []
        docs = db.collection('school_payment_logs').order_by('synced_at', direction='DESCENDING').limit(limit).stream()
        for d in docs:
            data = d.to_dict()
            results.append({
                'id': d.id,
                'doc_id': d.id,
                'event_type': 'PAYMENT_CONFIRMED',
                'student_id': data.get('student_id', ''),
                'student_name': data.get('student_name', ''),
                'amount': data.get('amount', 0.0),
                'currency': data.get('currency', '៛'),
                'fee_category': data.get('fee_title', ''),
                'channel': data.get('payment_method', 'CASH'),
                'timestamp': data.get('payment_date', data.get('synced_at', '')),
                'is_synced': True,
                'source': 'Google Firebase Firestore (Live Cloud)'
            })
        if not results:
            return get_local_fallback()
        return results
    except Exception as e:
        logger.warning(f"Firestore query fallback to local database: {e}")
        return get_local_fallback()

