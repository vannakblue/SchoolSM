import io
import json
import logging
import requests
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from django.core.files.base import ContentFile
from apps.academics.models import AcademicYear, Classroom
from apps.students.models import Student
from apps.finance.models import (
    MonthlyFeeConfig,
    MonthlyFeeRate,
    StudentMonthlyPayment,
    StudentMonthlyCategory,
    Invoice,
    PaymentTransaction,
    SchoolPaymentMethod,
    PaymentSlipSubmission,
    FirestorePaymentAuditLog
)
from apps.accounts.models import TelegramConfig
from apps.accounts.utils import (
    send_telegram_notification,
    send_telegram_photo,
    edit_telegram_message,
    answer_telegram_callback_query
)
from apps.finance.firebase_service import (
    log_fee_inquiry_to_firestore,
    log_qr_dispatch_to_firestore,
    log_payment_slip_to_firestore,
    log_payment_transaction_to_firestore
)
from apps.finance.views import MONTH_NAMES_KM

logger = logging.getLogger(__name__)


def handle_telegram_fees_message(msg):
    """
    Handle incoming text messages from Telegram Bot:
    - Direct Student ID (e.g. '2624001', 'STU001', etc.)
    - /start or /start <student_id>
    - /fees or /fees <student_id_or_class>
    - /pay <student_id>
    - /qr <student_id>
    - /check <student_id>
    """
    chat_id = msg.get('chat', {}).get('id')
    text = (msg.get('text') or '').strip()
    user_info = msg.get('from', {})
    first_name = user_info.get('first_name', '')
    username = user_info.get('username')
    user_disp = f"{first_name} (@{username})" if username else (first_name or f"User_{chat_id}")

    if not chat_id or not text:
        return

    parts = text.split()
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ''

    if cmd == '/start':
        if arg:
            return process_fees_inquiry(chat_id, arg, user_disp=user_disp)
        else:
            return send_welcome_and_help(chat_id)

    elif cmd in ['/fees', '/fee', '/due', '/check']:
        return process_fees_inquiry(chat_id, arg, user_disp=user_disp)

    elif cmd in ['/pay', '/collect']:
        return process_pay_command(chat_id, arg)

    elif cmd in ['/qr', '/aba', '/bakong']:
        if arg:
            student = Student.objects.filter(student_id__iexact=arg).first()
            if student:
                return send_bank_qr_code(chat_id, student, user_disp=user_disp)
        return process_fees_inquiry(chat_id, arg or text, user_disp=user_disp)

    elif cmd in ['/help', 'ជំនួយ']:
        return send_welcome_and_help(chat_id)

    else:
        # User typed raw text (e.g. Student ID '2624001', 'STU2026001')
        cleaned_query = text.replace('#', '').strip()
        student = Student.objects.filter(student_id__iexact=cleaned_query).first()
        if not student:
            student = Student.objects.filter(student_id__icontains=cleaned_query).first()
        if not student:
            # Check if it matches a student by Khmer name or Latin name
            student = Student.objects.filter(khmer_name__iexact=cleaned_query).first() or Student.objects.filter(latin_name__iexact=cleaned_query).first()

        if student:
            return send_combined_student_fee_statement(chat_id, student, user_disp=user_disp)

        # Check if query matches classroom
        active_year = AcademicYear.objects.filter(is_current=True).first()
        classroom = Classroom.objects.filter(name__iexact=cleaned_query, academic_year=active_year).first() if active_year else None
        if classroom:
            config = MonthlyFeeConfig.get_or_create_for_year(active_year)
            return send_classroom_fee_status_telegram(chat_id, classroom, active_year, config)

        # If not recognized
        send_telegram_notification(
            title="🔍 ស្វែងរកព័ត៌មានសិស្ស",
            message=f"❌ រកមិនឃើញសិស្ស ឬថ្នាក់ដែលមានអត្តលេខ/ឈ្មោះ «*{text}*» ឡើយ។\n\n💡 *សូមវាយអត្តលេខសិស្សឱ្យបានត្រឹមត្រូវ* ឧទាហរណ៍៖ `2624001` ឬ `/fees 2624001`",
            custom_chat_id=chat_id
        )


def send_welcome_and_help(chat_id):
    """
    Sends welcome guide to parent/student on how to use Telegram Bot for fee inquiries and payments.
    """
    msg = (
        "👋 *សូមស្វាគមន៍មកកាន់ប្រព័ន្ធទូទាត់ប្រាក់ និងពិនិត្យកម្រៃសិក្សា (SchoolSM Bot)*\n\n"
        "🏫 អាណាព្យាបាល និងសិស្សអាចពិនិត្យ និងបង់ប្រាក់បានយ៉ាងងាយស្រួល៖\n\n"
        "👉 *គ្រាន់តែវាយ ឬផ្ញើ «អត្តលេខសិស្ស»* (ឧទាហរណ៍៖ `2624001`)\n"
        "ប្រព័ន្ធនឹងបង្ហាញព័ត៌មានលម្អិតអំពី៖\n"
        " 1️⃣ **ថវិកាដើមឆ្នាំ & សេវាផ្សេងៗ** (Registration / Tuition / Uniforms)\n"
        " 2️⃣ **ថវិកាទឹកភ្លើងតាមខែនីមួយៗ** (Monthly Water & Electricity Fees)\n"
        " 3️⃣ **ABA QR Code / Bakong KHQR** សម្រាប់ស្កេនបង់ប្រាក់ភ្លាមៗ\n"
        " 4️⃣ **ផ្ញើរូបថតបង្កាន់ដៃ (Receipt Slip)** សម្រាប់ឱ្យ Admin ផ្ទៀងផ្ទាត់\n\n"
        "💡 *ពាក្យបញ្ជាគំរូ៖*\n"
        "• វាយអត្តលេខសិស្សផ្ទាល់ (ឧ. `2624001`)\n"
        "• `/fees 2624001` - ពិនិត្យកម្រៃសិស្ស\n"
        "• `/fees 8A` - ពិនិត្យបញ្ជីជំពាក់តាមថ្នាក់\n"
        "• `/qr 2624001` - បង្ហាញ QR Code សម្រាប់បង់ប្រាក់"
    )
    send_telegram_notification(
        title="សាលារៀន SM - Telegram Bot",
        message=msg,
        custom_chat_id=chat_id
    )


def process_fees_inquiry(chat_id, arg, user_disp="Parent"):
    """
    Inquiry for due fees by student ID or classroom name.
    """
    active_year = AcademicYear.objects.filter(is_current=True).first()
    if not active_year:
        send_telegram_notification(
            title="⚠️ ដំណឹងប្រព័ន្ធ",
            message="មិនទាន់មានឆ្នាំសិក្សាសកម្មក្នុងប្រព័ន្ធឡើយ។ សូមទាក់ទងរដ្ឋបាលសាលា។",
            custom_chat_id=chat_id
        )
        return

    if not arg:
        return send_welcome_and_help(chat_id)

    # Check Student
    student = Student.objects.filter(student_id__iexact=arg).first() or Student.objects.filter(student_id__icontains=arg).first()
    if student:
        return send_combined_student_fee_statement(chat_id, student, user_disp=user_disp)

    # Check Classroom
    config = MonthlyFeeConfig.get_or_create_for_year(active_year)
    classroom = Classroom.objects.filter(name__iexact=arg, academic_year=active_year).first()
    if not classroom:
        classroom = Classroom.objects.filter(name__icontains=arg, academic_year=active_year).first()

    if classroom:
        return send_classroom_fee_status_telegram(chat_id, classroom, active_year, config)

    send_telegram_notification(
        title="🔍 លទ្ធផលស្វែងរក",
        message=f"❌ រកមិនឃើញសិស្ស ឬថ្នាក់ដែលមានកូដ «*{arg}*» ឡើយ។\nសូមវាយអត្តលេខសិស្សឱ្យបានត្រឹមត្រូវ (ឧ. `2624001`)។",
        custom_chat_id=chat_id
    )


def send_combined_student_fee_statement(chat_id, student, user_disp="Parent"):
    """
    Generates and sends full fee statement to parent covering:
    1. Early Year Invoices & Miscellaneous Fees (ថវិកាដើមឆ្នាំ & ផ្សេងៗ)
    2. Monthly Utility Fees (ថ្លៃទឹកភ្លើងតាមខែនីមួយៗ)
    3. Grand Total Due
    4. Action buttons: [ Scan ABA QR ], [ Monthly Details ], [ Submit Slip ], [ Refresh ]
    """
    active_year = student.academic_year or AcademicYear.objects.filter(is_current=True).first()
    config = MonthlyFeeConfig.get_or_create_for_year(active_year) if active_year else None

    # 1. Early-Year & Standard Invoices
    invoices = Invoice.objects.filter(student=student).select_related('fee_category', 'academic_year')
    inv_total_expected = Decimal('0.00')
    inv_total_paid = Decimal('0.00')
    inv_due_items = []

    for inv in invoices:
        inv_total_expected += inv.final_amount
        inv_total_paid += inv.paid_amount
        if inv.remaining_balance > 0:
            inv_due_items.append(inv)

    inv_debt = max(Decimal('0.00'), inv_total_expected - inv_total_paid)

    # 2. Monthly Utilities Calculation
    month_seq = config.get_month_sequence() if config else []
    ticked_set = set(config.ticked_months or []) if config else set()
    payments = {p.month: p for p in StudentMonthlyPayment.objects.filter(student=student, academic_year=active_year)}
    monthly_cats = {mc.month: mc.category for mc in StudentMonthlyCategory.objects.filter(student=student, academic_year=active_year)}
    rates = {(r.category_id, r.month): r.amount for r in MonthlyFeeRate.objects.filter(config=config)} if config else {}

    fee_start_idx = month_seq.index(student.fee_start_month) if student.fee_start_month in month_seq else 0
    fee_end_idx = month_seq.index(student.fee_end_month) if student.fee_end_month in month_seq else len(month_seq) - 1

    utility_total_expected = Decimal('0.00')
    utility_total_paid = Decimal('0.00')
    unpaid_months_badges = []
    month_detail_rows = []

    for idx, m in enumerate(month_seq):
        is_attending = (fee_start_idx <= idx <= fee_end_idx)
        is_ticked = (m in ticked_set) and is_attending
        m_cat = monthly_cats.get(m, student.category)
        m_cat_id = m_cat.id if m_cat else None

        expected = Decimal('0.00')
        if m_cat_id and is_attending:
            expected = rates.get((m_cat_id, m))
            if expected is None:
                if m_cat and ('FREE' in m_cat.code or '100' in m_cat.name):
                    expected = Decimal('0.00')
                elif m_cat and ('SCHOLAR' in m_cat.code or '50' in m_cat.name or 'TEACHER' in m_cat.code):
                    expected = Decimal('10000.00')
                else:
                    expected = Decimal('20000.00')

        p = payments.get(m)
        paid = p.paid_amount if p else Decimal('0.00')
        utility_total_paid += paid

        if is_ticked:
            utility_total_expected += expected
            m_name = MONTH_NAMES_KM.get(m, f'ខែ {m}')
            if paid >= expected and expected > 0:
                unpaid_months_badges.append(f"🟢 {m_name}")
            elif paid > 0:
                unpaid_months_badges.append(f"🟡 {m_name} ({expected - paid:,.0f}៛)")
            else:
                unpaid_months_badges.append(f"🔴 {m_name} ({expected:,.0f}៛)")

            month_detail_rows.append({
                'month': m,
                'name': m_name,
                'expected': expected,
                'paid': paid,
                'balance': max(Decimal('0.00'), expected - paid)
            })

    utility_debt = max(Decimal('0.00'), utility_total_expected - utility_total_paid)
    grand_total_debt = utility_debt + (inv_debt * Decimal('4100.00')) # In KHR equivalent if invoice is USD

    # Build Beautiful Telegram Message
    class_name = student.classroom.name if student.classroom else 'គ្មានថ្នាក់'
    cat_name = student.category.name if student.category else 'ទូទៅ'

    msg = f"👤 *ព័ត៌មានកម្រៃសិក្សា & ថ្លៃទឹកភ្លើង*\n"
    msg += f"━━━━━━━━━━━━━━━━━━\n"
    msg += f"• សិស្ស៖ *{student.khmer_name}* ({student.student_id})\n"
    msg += f"• ថ្នាក់រៀន៖ *{class_name}* | ប្រភេទ៖ {cat_name}\n"
    msg += f"• ឆ្នាំសិក្សា៖ {active_year.name if active_year else 'បច្ចុប្បន្ន'}\n"
    msg += f"━━━━━━━━━━━━━━━━━━\n\n"

    # Section 1: ថវិកាដើមឆ្នាំ & វិក្កយបត្រ (Early Year & Invoices)
    msg += f"📋 *១. ថវិកាដើមឆ្នាំ & សេវាផ្សេងៗ (Invoices)*\n"
    if invoices.exists():
        for inv in invoices[:4]:
            status_icon = "🟢" if inv.status == Invoice.Status.PAID else ("🟡" if inv.status == Invoice.Status.PARTIAL else "🔴")
            msg += f"• {status_icon} {inv.fee_category.name}: *${inv.final_amount:,.2f}* (បានបង់: ${inv.paid_amount:,.2f}"
            if inv.remaining_balance > 0:
                msg += f" | ជំពាក់: *${inv.remaining_balance:,.2f}*)"
            else:
                msg += f" | រួចរាល់)"
            msg += "\n"
        if inv_debt > 0:
            msg += f"👉 *សរុបជំពាក់ថវិកាដើមឆ្នាំ៖ ${inv_debt:,.2f}* (~{inv_debt * Decimal('4100'):,.0f} ៛)\n\n"
        else:
            msg += f"👉 *ស្ថានភាព៖ បានបង់គ្រប់ចំនួនរួចរាល់* ✅\n\n"
    else:
        msg += f"• មិនមានវិក្កយបត្រជំពាក់នៅដើមឆ្នាំឡើយ ✅\n\n"

    # Section 2: ថ្លៃទឹកភ្លើងតាមខែនីមួយៗ (Monthly Utilities)
    msg += f"⚡💧 *២. ថ្លៃទឹកភ្លើងតាមខែនីមួយៗ (Utilities)*\n"
    if unpaid_months_badges:
        msg += f"• ស្ថានភាពខែ៖ {' | '.join(unpaid_months_badges[:6])}\n"
        if len(unpaid_months_badges) > 6:
            msg += f"  {' | '.join(unpaid_months_badges[6:])}\n"
        msg += f"• សរុបបានបង់៖ {utility_total_paid:,.0f} ៛\n"
        if utility_debt > 0:
            msg += f"👉 *សរុបជំពាក់ថ្លៃទឹកភ្លើង៖ {utility_debt:,.0f} ៛* 🔴\n\n"
        else:
            msg += f"👉 *ស្ថានភាព៖ បានបង់គ្រប់ខែទាំងអស់* 🟢\n\n"
    else:
        msg += f"• មិនទាន់មានការកំណត់ថ្លៃទឹកភ្លើងសម្រាប់ឆ្នាំនេះឡើយ\n\n"

    # Grand Total
    msg += f"━━━━━━━━━━━━━━━━━━\n"
    if grand_total_debt > 0:
        msg += f"💰 *សរុបទឹកប្រាក់ត្រូវបង់ទាំងអស់៖ {utility_debt:,.0f} ៛"
        if inv_debt > 0:
            msg += f" + ${inv_debt:,.2f}*"
        else:
            msg += "*"
        msg += f"\n\n👉 *សូមចុចប៊ូតុងខាងក្រោមដើម្បីស្កេន ABA QR Code ឬផ្ញើបង្កាន់ដៃបង់ប្រាក់៖*"
    else:
        msg += f"🎉 *សិស្សបានបង់ប្រាក់រួចរាល់គ្រប់ចំនួនទាំងអស់! គ្មានប្រាក់ជំពាក់ឡើយ!* 🟢"

    # Inline Keyboard
    inline_keyboard = []
    if grand_total_debt > 0:
        inline_keyboard.append([
            {'text': "💳 បង្ហាញ QR Code បង់ប្រាក់ (ABA / Bakong)", 'callback_data': f"feeqr:{student.id}"}
        ])
        inline_keyboard.append([
            {'text': "📤 ផ្ញើបង្កាន់ដៃបង់ប្រាក់ (Submit Slip)", 'callback_data': f"feeslip:{student.id}"},
            {'text': "📋 មើលលម្អិតតាមខែ", 'callback_data': f"feedetail:{student.id}"}
        ])
    else:
        inline_keyboard.append([
            {'text': "📋 មើលលម្អិតប្រវត្តិបង់ប្រាក់", 'callback_data': f"feedetail:{student.id}"},
            {'text': "🔄 ពិនិត្យឡើងវិញ", 'callback_data': f"feerefresh:{student.id}"}
        ])

    reply_markup = {'inline_keyboard': inline_keyboard}

    # Log to Firestore
    log_fee_inquiry_to_firestore(
        student=student,
        chat_id=chat_id,
        total_due=grand_total_debt,
        details={
            'utility_debt': float(utility_debt),
            'invoice_debt_usd': float(inv_debt),
            'months_status': unpaid_months_badges
        },
        user_disp=user_disp
    )

    # Dispatch via Telegram Bot
    tconfig = TelegramConfig.objects.filter(is_active=True).first()
    if tconfig and tconfig.bot_token:
        try:
            requests.post(
                f"https://api.telegram.org/bot{tconfig.bot_token}/sendMessage",
                json={
                    'chat_id': chat_id,
                    'text': msg,
                    'parse_mode': 'Markdown',
                    'reply_markup': reply_markup
                },
                timeout=8
            )
        except Exception as e:
            logger.error(f"Error sending fee statement to Telegram: {e}")
    else:
        send_telegram_notification(
            title="ព័ត៌មានកម្រៃសិក្សា & ទឹកភ្លើង",
            message=msg,
            custom_chat_id=chat_id,
            reply_markup=reply_markup
        )


def send_bank_qr_code(chat_id, student, user_disp="Parent"):
    """
    Sends the official School Bank QR Code (ABA / Bakong KHQR) image or details to parent with exact amount.
    """
    bank_method = SchoolPaymentMethod.get_default_or_first()
    active_year = student.academic_year or AcademicYear.objects.filter(is_current=True).first()
    config = MonthlyFeeConfig.get_or_create_for_year(active_year) if active_year else None

    # Calculate current due amount
    month_seq = config.get_month_sequence() if config else []
    ticked_set = set(config.ticked_months or []) if config else set()
    payments = {p.month: p.paid_amount for p in StudentMonthlyPayment.objects.filter(student=student, academic_year=active_year)}
    monthly_cats = {mc.month: mc.category for mc in StudentMonthlyCategory.objects.filter(student=student, academic_year=active_year)}
    rates = {(r.category_id, r.month): r.amount for r in MonthlyFeeRate.objects.filter(config=config)} if config else {}

    fee_start_idx = month_seq.index(student.fee_start_month) if student.fee_start_month in month_seq else 0
    fee_end_idx = month_seq.index(student.fee_end_month) if student.fee_end_month in month_seq else len(month_seq) - 1

    utility_debt = Decimal('0.00')
    unpaid_months = []
    for idx, m in enumerate(month_seq):
        is_attending = (fee_start_idx <= idx <= fee_end_idx)
        if (m in ticked_set) and is_attending:
            m_cat = monthly_cats.get(m, student.category)
            m_cat_id = m_cat.id if m_cat else None
            expected = rates.get((m_cat_id, m), Decimal('20000.00')) if m_cat_id else Decimal('20000.00')
            paid = payments.get(m, Decimal('0.00'))
            if paid < expected:
                utility_debt += (expected - paid)
                unpaid_months.append(MONTH_NAMES_KM.get(m, f"ខែ {m}"))

    invoices = Invoice.objects.filter(student=student, status__in=[Invoice.Status.UNPAID, Invoice.Status.PARTIAL, Invoice.Status.OVERDUE])
    inv_debt = sum(inv.remaining_balance for inv in invoices)

    payable_amount_khr = utility_debt
    memo_text = f"STU-{student.student_id}"

    # Build Bank QR Message
    bank_name = bank_method.bank_name if bank_method else "ABA Bank"
    account_name = bank_method.account_name if bank_method else "SCHOOL MANAGEMENT"
    account_num = bank_method.account_number if bank_method else "000 123 456"
    instructions = bank_method.instructions if bank_method else "សូមស្កេន QR Code ដើម្បីបង់ប្រាក់"

    caption = (
        f"💳 *ABA / BAKONG QR CODE សម្រាប់បង់ប្រាក់*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"• ធនាគារ៖ *{bank_name}*\n"
        f"• ឈ្មោះគណនី៖ *{account_name}*\n"
        f"• លេខគណនី៖ `{account_num}`\n"
        f"• សិស្ស៖ *{student.khmer_name}* ({student.student_id})\n"
        f"• ចំនួនទឹកប្រាក់ត្រូវបង់៖ *{payable_amount_khr:,.0f} ៛*"
    )
    if inv_debt > 0:
        caption += f" (ឬ *${inv_debt:,.2f}* សម្រាប់ដើមឆ្នាំ)"
    caption += (
        f"\n• កំណត់សម្គាល់ (Memo)៖ `{memo_text}`\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📝 *ការណែនាំ៖*\n"
        f"1. បើកកម្មវិធី ABA Mobile / Bakong ឬធនាគារណាក៏បានដើម្បីស្កេន QR\n"
        f"2. បញ្ចូល Memo: `{memo_text}`\n"
        f"3. បន្ទាប់ពីផ្ទេររួច សូមចុចប៊ូតុង «ផ្ញើបង្កាន់ដៃបង់ប្រាក់» ខាងក្រោម ឬផ្ញើរូបភាព Receipt មកទីនេះភ្លាមៗ!"
    )

    inline_keyboard = [
        [
            {'text': "📤 ផ្ញើបង្កាន់ដៃបង់ប្រាក់ (Submit Slip)", 'callback_data': f"feeslip:{student.id}"},
            {'text': "🔄 ពិនិត្យស្ថានភាពឡើងវិញ", 'callback_data': f"feerefresh:{student.id}"}
        ]
    ]
    reply_markup = {'inline_keyboard': inline_keyboard}

    # If Bank QR Code image file exists, send as Photo
    has_sent_photo = False
    if bank_method and bank_method.qr_image:
        try:
            with bank_method.qr_image.open('rb') as f:
                photo_bytes = f.read()
            send_telegram_photo(
                photo_bytes=photo_bytes,
                filename="bank_qr.png",
                caption=caption,
                custom_chat_id=chat_id,
                reply_markup=reply_markup
            )
            has_sent_photo = True
        except Exception as e:
            logger.warning(f"Failed to open bank qr image: {e}")

    if not has_sent_photo:
        tconfig = TelegramConfig.objects.filter(is_active=True).first()
        if tconfig and tconfig.bot_token:
            requests.post(
                f"https://api.telegram.org/bot{tconfig.bot_token}/sendMessage",
                json={
                    'chat_id': chat_id,
                    'text': caption,
                    'parse_mode': 'Markdown',
                    'reply_markup': reply_markup
                },
                timeout=8
            )

    # Log to Firestore
    log_qr_dispatch_to_firestore(
        student=student,
        bank_method=bank_method,
        amount=payable_amount_khr,
        currency="៛",
        memo=memo_text,
        chat_id=chat_id,
        user_disp=user_disp
    )


def handle_telegram_photo_message(msg):
    """
    Handles payment receipt slip photo uploads sent by parents.
    Saves slip image, notifies Admin Telegram channel with Approve/Reject buttons, and logs to Firebase Firestore.
    """
    chat_id = msg.get('chat', {}).get('id')
    photos = msg.get('photo', [])
    caption = (msg.get('caption') or '').strip()
    user_info = msg.get('from', {})
    first_name = user_info.get('first_name', '')
    username = user_info.get('username')
    user_id = str(user_info.get('id', ''))
    user_disp = f"{first_name} (@{username})" if username else (first_name or f"User_{chat_id}")

    if not chat_id or not photos:
        return

    # Largest photo is the last item
    photo_obj = photos[-1]
    file_id = photo_obj.get('file_id')

    # Try to identify the student:
    # 1. From caption (e.g. '2624001', 'STU2624001')
    student = None
    if caption:
        import re
        tokens = re.findall(r'[a-zA-Z0-9_\-]+', caption)
        for tok in tokens:
            st = Student.objects.filter(student_id__iexact=tok).first()
            if st:
                student = st
                break

    # 2. From recent inquiry log for this chat_id
    if not student:
        last_log = FirestorePaymentAuditLog.objects.filter(
            event_type__in=[FirestorePaymentAuditLog.EventType.INQUIRY, FirestorePaymentAuditLog.EventType.QR_DISPATCH],
            telegram_user_info__icontains=str(chat_id)
        ).order_by('-created_at').first()
        if last_log and last_log.student:
            student = last_log.student

    # 3. From Student telegram_chat_id
    if not student:
        student = Student.objects.filter(telegram_chat_id=str(chat_id)).first()

    active_year = AcademicYear.objects.filter(is_current=True).first()

    if not student:
        # Ask parent to provide Student ID with the slip
        send_telegram_notification(
            title="📸 បានទទួលរូបភាពបង្កាន់ដៃ",
            message=(
                "⚠️ ប្រព័ន្ធបានទទួលរូបភាពបង្កាន់ដៃបង់ប្រាក់ ប៉ុន្តែមិនទាន់ស្គាល់អត្តលេខសិស្សឡើយ。\n\n"
                "👉 *សូមផ្ញើអត្តលេខសិស្ស (ឧ. `2624001`)* មកក្នុង Chat នេះ ដើម្បីភ្ជាប់ជាមួយបង្កាន់ដៃនេះ។"
            ),
            custom_chat_id=chat_id
        )
        return

    # Download photo from Telegram API
    tconfig = TelegramConfig.objects.filter(is_active=True).first()
    image_content = None
    if tconfig and tconfig.bot_token and file_id:
        try:
            get_file_url = f"https://api.telegram.org/bot{tconfig.bot_token}/getFile?file_id={file_id}"
            f_resp = requests.get(get_file_url, timeout=10)
            if f_resp.status_code == 200:
                file_path = f_resp.json().get('result', {}).get('file_path')
                if file_path:
                    download_url = f"https://api.telegram.org/file/bot{tconfig.bot_token}/{file_path}"
                    img_resp = requests.get(download_url, timeout=15)
                    if img_resp.status_code == 200:
                        image_content = img_resp.content
        except Exception as e:
            logger.error(f"Error downloading photo from Telegram: {e}")

    # Create PaymentSlipSubmission record
    slip = PaymentSlipSubmission.objects.create(
        student=student,
        academic_year=active_year or student.academic_year,
        fee_type=PaymentSlipSubmission.FeeType.MONTHLY_UTILITY,
        claimed_amount=Decimal('0.00'),
        currency='៛',
        telegram_file_id=file_id,
        telegram_user_id=user_id,
        telegram_username=username,
        telegram_chat_id=str(chat_id),
        status=PaymentSlipSubmission.Status.PENDING,
        notes=caption or f"ផ្ញើតាម Telegram ដោយ {user_disp}"
    )

    if image_content:
        filename = f"slip_{student.student_id}_{slip.id}.jpg"
        slip.slip_image.save(filename, ContentFile(image_content), save=True)

    # Log slip to Firebase Firestore
    log_payment_slip_to_firestore(slip)

    # Send confirmation to Parent
    parent_confirm_msg = (
        f"🙏 *អរគុណ! ប្រព័ន្ធបានទទួលបង្កាន់ដៃបង់ប្រាក់រួចរាល់ហើយ!*\n\n"
        f"• សិស្ស៖ *{student.khmer_name}* ({student.student_id})\n"
        f"• ថ្នាក់រៀន៖ {student.classroom.name if student.classroom else 'គ្មានថ្នាក់'}\n"
        f"• លេខកូដបង្កាន់ដៃ៖ `#SLIP-{slip.id:04d}`\n"
        f"• ពេលវេលា៖ {timezone.now().strftime('%d/%m/%Y %H:%M')}\n\n"
        f"⏳ _គណៈគ្រប់គ្រងសាលា និងគណនេយ្យករ នឹងពិនិត្យផ្ទៀងផ្ទាត់ និងបញ្ជាក់ជូនក្នុងពេលឆាប់ៗនេះ។_"
    )
    send_telegram_notification(
        title="✅ បង្កាន់ដៃបង់ប្រាក់បានទទួល",
        message=parent_confirm_msg,
        custom_chat_id=chat_id
    )

    # Forward Slip & Action Buttons to Admin Management Chat
    admin_caption = (
        f"🔔 *មានបង្កាន់ដៃបង់ប្រាក់ថ្មីរង់ចាំការផ្ទៀងផ្ទាត់!*\n\n"
        f"• សិស្ស៖ *{student.khmer_name}* (`{student.student_id}`)\n"
        f"• ថ្នាក់៖ {student.classroom.name if student.classroom else 'គ្មាន'}\n"
        f"• ផ្ញើដោយ៖ {user_disp}\n"
        f"• លេខកូដបង្កាន់ដៃ៖ `#SLIP-{slip.id:04d}`\n"
        f"• កំណត់សម្គាល់៖ {caption or 'គ្មាន'}\n\n"
        f"👉 *សូមចុចលើប៊ូតុងខាងក្រោមដើម្បីអនុម័ត ឬបដិសេធ៖*"
    )
    admin_keyboard = {
        'inline_keyboard': [
            [
                {'text': "✅ យល់ព្រម (Approve)", 'callback_data': f"feereceipt:approve:{slip.id}"},
                {'text': "❌ បដិសេធ (Reject)", 'callback_data': f"feereceipt:reject:{slip.id}"}
            ]
        ]
    }

    if image_content and tconfig and tconfig.chat_id:
        send_telegram_photo(
            photo_bytes=image_content,
            filename="slip_review.jpg",
            caption=admin_caption,
            custom_chat_id=tconfig.chat_id,
            reply_markup=admin_keyboard
        )


def process_telegram_fee_callback(callback_data, user_disp, chat_id, message_id):
    """
    Handles inline button callback queries:
    - feeqr:<student_id>
    - feedetail:<student_id>
    - feeslip:<student_id>
    - feerefresh:<student_id>
    - feepay:<student_id>:<month_or_ALL>
    - feereceipt:approve:<slip_id>
    - feereceipt:reject:<slip_id>
    """
    parts = callback_data.split(':')
    action_type = parts[0]

    if action_type == 'feeqr':
        student_id = parts[1]
        student = Student.objects.filter(id=student_id).first()
        if student:
            send_bank_qr_code(chat_id, student, user_disp=user_disp)
            return {'success': True, 'message': 'បានបង្ហាញ Bank QR Code រួចរាល់!'}
        return {'success': False, 'message': 'រកមិនឃើញសិស្សឡើយ'}

    elif action_type == 'feedetail':
        student_id = parts[1]
        student = Student.objects.filter(id=student_id).first()
        if student:
            return send_student_detailed_breakdown(chat_id, student)
        return {'success': False, 'message': 'រកមិនឃើញសិស្សឡើយ'}

    elif action_type == 'feeslip':
        student_id = parts[1]
        student = Student.objects.filter(id=student_id).first()
        student_name = student.khmer_name if student else ''
        prompt_msg = (
            f"📸 *របៀបផ្ញើបង្កាន់ដៃបង់ប្រាក់ ({student_name})*\n\n"
            f"1. ថតរូប ឬ Screenshot បង្កាន់ដៃផ្ទេរប្រាក់តាម ABA / Bakong\n"
            f"2. ផ្ញើរូបភាពចូលមកក្នុង Telegram Chat នេះដោយផ្ទាល់\n"
            f"3. ប្រព័ន្ធនឹងកត់ត្រា និងបញ្ជូនទៅកាន់ Admin ស្វ័យប្រវត្តិ!"
        )
        send_telegram_notification(
            title="📤 ផ្ញើបង្កាន់ដៃបង់ប្រាក់",
            message=prompt_msg,
            custom_chat_id=chat_id
        )
        return {'success': True, 'message': 'សូមផ្ញើរូបភាពបង្កាន់ដៃមកកាន់ Chat នេះ'}

    elif action_type == 'feerefresh':
        student_id = parts[1]
        student = Student.objects.filter(id=student_id).first()
        if student:
            send_combined_student_fee_statement(chat_id, student, user_disp=user_disp)
            return {'success': True, 'message': 'បានធ្វើបច្ចុប្បន្នភាពទិន្នន័យរួចរាល់!'}
        return {'success': False, 'message': 'រកមិនឃើញសិស្សឡើយ'}

    elif action_type == 'feepay':
        return process_pay_callback_internal(parts, user_disp, chat_id, message_id)

    elif action_type == 'feereceipt':
        sub_action = parts[1] # 'approve' or 'reject'
        slip_id = parts[2]
        return process_slip_review_callback(sub_action, slip_id, user_disp, chat_id, message_id)

    return {'success': False, 'message': 'Unknown action'}


def send_student_detailed_breakdown(chat_id, student):
    """
    Sends complete month-by-month and invoice-by-invoice detailed table in Telegram.
    """
    active_year = student.academic_year or AcademicYear.objects.filter(is_current=True).first()
    config = MonthlyFeeConfig.get_or_create_for_year(active_year) if active_year else None

    month_seq = config.get_month_sequence() if config else []
    ticked_set = set(config.ticked_months or []) if config else set()
    payments = {p.month: p for p in StudentMonthlyPayment.objects.filter(student=student, academic_year=active_year)}
    monthly_cats = {mc.month: mc.category for mc in StudentMonthlyCategory.objects.filter(student=student, academic_year=active_year)}
    rates = {(r.category_id, r.month): r.amount for r in MonthlyFeeRate.objects.filter(config=config)} if config else {}

    fee_start_idx = month_seq.index(student.fee_start_month) if student.fee_start_month in month_seq else 0
    fee_end_idx = month_seq.index(student.fee_end_month) if student.fee_end_month in month_seq else len(month_seq) - 1

    msg = f"📊 *របាយការណ៍លម្អិតប្រចាំខែ*\n"
    msg += f"• សិស្ស៖ *{student.khmer_name}* ({student.student_id})\n"
    msg += f"• ថ្នាក់៖ {student.classroom.name if student.classroom else 'គ្មាន'}\n\n"
    msg += f"🗓 *បញ្ជីទឹកភ្លើងតាមខែនីមួយៗ៖*\n"

    for idx, m in enumerate(month_seq):
        is_attending = (fee_start_idx <= idx <= fee_end_idx)
        if not is_attending:
            continue

        m_name = MONTH_NAMES_KM.get(m, f'ខែ {m}')
        is_active = (m in ticked_set)
        m_cat = monthly_cats.get(m, student.category)
        m_cat_id = m_cat.id if m_cat else None
        expected = rates.get((m_cat_id, m), Decimal('20000.00')) if m_cat_id else Decimal('20000.00')

        p = payments.get(m)
        paid = p.paid_amount if p else Decimal('0.00')

        if not is_active:
            status_text = "⚪ _មិនទាន់ដល់ខែ_"
        elif paid >= expected and expected > 0:
            status_text = f"🟢 បង់រួច ({paid:,.0f} ៛)"
        elif paid > 0:
            status_text = f"🟡 បង់ខ្លះ ({paid:,.0f}/{expected:,.0f} ៛)"
        else:
            status_text = f"🔴 ជំពាក់ ({expected:,.0f} ៛)"

        msg += f"• {m_name}៖ {status_text}\n"

    send_telegram_notification(
        title="របាយការណ៍លម្អិតកម្រៃ",
        message=msg,
        custom_chat_id=chat_id
    )
    return {'success': True, 'message': 'បានផ្ញើរបាយការណ៍លម្អិតរួចរាល់'}


def process_slip_review_callback(sub_action, slip_id, user_disp, chat_id, message_id):
    """
    Handles Admin approving or rejecting a parent payment slip via Telegram inline button.
    """
    slip = PaymentSlipSubmission.objects.filter(id=slip_id).select_related('student', 'student__classroom', 'academic_year').first()
    if not slip:
        return {'success': False, 'message': 'រកមិនឃើញទិន្នន័យបង្កាន់ដៃឡើយ'}

    if slip.status != PaymentSlipSubmission.Status.PENDING:
        return {'success': False, 'message': f'បង្កាន់ដៃនេះត្រូវបានដំណើរការរួចហើយ ({slip.get_status_display()})'}

    student = slip.student
    active_year = slip.academic_year or AcademicYear.objects.filter(is_current=True).first()

    if sub_action == 'approve':
        config = MonthlyFeeConfig.get_or_create_for_year(active_year)
        month_seq = config.get_month_sequence() if config else []
        ticked_set = set(config.ticked_months or []) if config else set()
        rates = {(r.category_id, r.month): r.amount for r in MonthlyFeeRate.objects.filter(config=config)} if config else {}
        monthly_cats = {mc.month: mc.category for mc in StudentMonthlyCategory.objects.filter(student=student, academic_year=active_year)}

        fee_start_idx = month_seq.index(student.fee_start_month) if student.fee_start_month in month_seq else 0
        fee_end_idx = month_seq.index(student.fee_end_month) if student.fee_end_month in month_seq else len(month_seq) - 1

        approved_months = []
        total_paid_rec = Decimal('0.00')

        with transaction.atomic():
            for idx, m in enumerate(month_seq):
                is_attending = (fee_start_idx <= idx <= fee_end_idx)
                if not ((m in ticked_set) and is_attending):
                    continue

                m_cat = monthly_cats.get(m, student.category)
                m_cat_id = m_cat.id if m_cat else None
                expected = rates.get((m_cat_id, m), Decimal('20000.00')) if m_cat_id else Decimal('20000.00')

                p, _ = StudentMonthlyPayment.objects.get_or_create(
                    student=student,
                    academic_year=active_year,
                    month=m,
                    defaults={'expected_amount': expected, 'paid_amount': Decimal('0.00')}
                )
                if p.paid_amount < expected:
                    p.expected_amount = expected
                    p.paid_amount = expected
                    p.status = StudentMonthlyPayment.Status.PAID
                    p.payment_date = timezone.now()
                    p.payment_method = StudentMonthlyPayment.PaymentMethod.ABA_BANK
                    p.notes = f"អនុម័តបង្កាន់ដៃ Telegram #SLIP-{slip.id} ដោយ {user_disp}"
                    p.save()
                    approved_months.append(MONTH_NAMES_KM.get(m, f"ខែ {m}"))
                    total_paid_rec += expected
                    log_payment_transaction_to_firestore(p, user_disp=user_disp)

            slip.status = PaymentSlipSubmission.Status.APPROVED
            slip.claimed_amount = total_paid_rec
            slip.reviewed_at = timezone.now()
            slip.notes = f"បានអនុម័តដោយ {user_disp} តាម Telegram"
            slip.save()
            log_payment_slip_to_firestore(slip)

        # Notify Parent
        if slip.telegram_chat_id:
            parent_msg = (
                f"🎉 *បង្កាន់ដៃបង់ប្រាក់ត្រូវបានផ្ទៀងផ្ទាត់ និងយល់ព្រមរួចរាល់!*\n\n"
                f"• សិស្ស៖ *{student.khmer_name}* ({student.student_id})\n"
                f"• ខែដែលបានបង់៖ {', '.join(approved_months) if approved_months else 'គ្រប់ខែ'}\n"
                f"• ចំនួនទឹកប្រាក់៖ *{total_paid_rec:,.0f} ៛*\n"
                f"• កាលបរិច្ឆេទ៖ {timezone.now().strftime('%d/%m/%Y %H:%M')}\n\n"
                f"🙏 *សូមអរគុណចំពោះការបង់ប្រាក់ទាន់ពេលវេលា!*"
            )
            send_telegram_notification(
                title="✅ បញ្ជាក់ការបង់ប្រាក់ជោគជ័យ",
                message=parent_msg,
                custom_chat_id=slip.telegram_chat_id
            )

        updated_text = (
            f"✅ *បានយល់ព្រមបង្កាន់ដៃបង់ប្រាក់ #SLIP-{slip.id:04d}*\n\n"
            f"• សិស្ស៖ *{student.khmer_name}* ({student.student_id})\n"
            f"• ចំនួនទឹកប្រាក់៖ *{total_paid_rec:,.0f} ៛*\n"
            f"• អ្នកអនុម័ត៖ {user_disp}\n"
            f"• ពេលវេលា៖ {timezone.now().strftime('%d/%m/%Y %H:%M')}"
        )
        return {
            'success': True,
            'message': f"បានអនុម័តបង់ប្រាក់ {total_paid_rec:,.0f} ៛ ជោគជ័យ!",
            'updated_text': updated_text
        }

    else:
        # Reject
        slip.status = PaymentSlipSubmission.Status.REJECTED
        slip.reviewed_at = timezone.now()
        slip.notes = f"បានបដិសេធដោយ {user_disp} តាម Telegram"
        slip.save()
        log_payment_slip_to_firestore(slip)

        if slip.telegram_chat_id:
            send_telegram_notification(
                title="❌ បង្កាន់ដៃបង់ប្រាក់មិនត្រឹមត្រូវ",
                message=(
                    f"⚠️ បង្កាន់ដៃបង់ប្រាក់របស់សិស្ស *{student.khmer_name}* ({student.student_id}) មិនទាន់ត្រឹមត្រូវឡើយ。\n\n"
                    f"👉 សូមពិនិត្យចំនួនទឹកប្រាក់ ឬផ្ញើរូបថតបង្កាន់ដៃច្បាស់ឡើងវិញ។"
                ),
                custom_chat_id=slip.telegram_chat_id
            )

        updated_text = (
            f"❌ *បានបដិសេធបង្កាន់ដៃបង់ប្រាក់ #SLIP-{slip.id:04d}*\n\n"
            f"• សិស្ស៖ *{student.khmer_name}* ({student.student_id})\n"
            f"• អ្នកបដិសេធ៖ {user_disp}\n"
            f"• ពេលវេលា៖ {timezone.now().strftime('%d/%m/%Y %H:%M')}"
        )
        return {
            'success': True,
            'message': "បានបដិសេធបង្កាន់ដៃរួចរាល់!",
            'updated_text': updated_text
        }


def process_pay_command(chat_id, arg):
    """
    Processes /pay command to record payment or display payment buttons.
    """
    if not arg:
        send_telegram_notification(
            title="⚠️ បញ្ជាក់អត្តលេខសិស្ស",
            message="សូមបញ្ជាក់អត្តលេខសិស្ស ឧទាហរណ៍៖ `/pay 2624001`",
            custom_chat_id=chat_id
        )
        return

    student = Student.objects.filter(student_id__iexact=arg).first()
    if not student:
        send_telegram_notification(
            title="❌ រកមិនឃើញសិស្ស",
            message=f"រកមិនឃើញសិស្សដែលមានអត្តលេខ «*{arg}*» ឡើយ។",
            custom_chat_id=chat_id
        )
        return

    return send_combined_student_fee_statement(chat_id, student)


def process_pay_callback_internal(parts, user_disp, chat_id, message_id):
    """
    Internal handler for direct feepay:<student_id>:<month_or_ALL> button clicks.
    """
    if len(parts) < 3:
        return {'success': False, 'message': 'Invalid callback data'}

    student_id = parts[1]
    month_target = parts[2]

    student = Student.objects.filter(id=student_id).first()
    if not student:
        return {'success': False, 'message': 'រកមិនឃើញទិន្នន័យសិស្សឡើយ'}

    active_year = student.academic_year or AcademicYear.objects.filter(is_current=True).first()
    config = MonthlyFeeConfig.get_or_create_for_year(active_year) if active_year else None
    if not active_year or not config:
        return {'success': False, 'message': 'គ្មានឆ្នាំសិក្សាសកម្ម'}

    month_seq = config.get_month_sequence()
    ticked_set = set(config.ticked_months or [])
    rates = {(r.category_id, r.month): r.amount for r in MonthlyFeeRate.objects.filter(config=config)}
    monthly_cats = {mc.month: mc.category for mc in StudentMonthlyCategory.objects.filter(student=student, academic_year=active_year)}

    fee_start_idx = month_seq.index(student.fee_start_month) if student.fee_start_month in month_seq else 0
    fee_end_idx = month_seq.index(student.fee_end_month) if student.fee_end_month in month_seq else len(month_seq) - 1

    paid_months_list = []
    total_recorded = Decimal('0.00')

    with transaction.atomic():
        for idx, m in enumerate(month_seq):
            is_attending = (fee_start_idx <= idx <= fee_end_idx)
            if not ((m in ticked_set) and is_attending):
                continue

            if month_target != 'ALL' and str(m) != str(month_target):
                continue

            m_cat = monthly_cats.get(m, student.category)
            m_cat_id = m_cat.id if m_cat else None
            expected = rates.get((m_cat_id, m), Decimal('20000.00')) if m_cat_id else Decimal('20000.00')

            payment, _ = StudentMonthlyPayment.objects.get_or_create(
                student=student,
                academic_year=active_year,
                month=m,
                defaults={'expected_amount': expected, 'paid_amount': Decimal('0.00')}
            )
            payment.expected_amount = expected
            payment.paid_amount = expected
            payment.status = StudentMonthlyPayment.Status.PAID
            payment.payment_date = timezone.now()
            payment.payment_method = StudentMonthlyPayment.PaymentMethod.CASH
            payment.notes = f"កត់ត្រាប្រមូលតាម Telegram Bot ដោយ {user_disp}"
            payment.save()

            paid_months_list.append(MONTH_NAMES_KM.get(m, f'ខែ {m}'))
            total_recorded += expected
            log_payment_transaction_to_firestore(payment, user_disp=user_disp)

    updated_text = (
        f"✅ *បានកត់ត្រាការបង់ប្រាក់ជោគជ័យ!*\n\n"
        f"• សិស្ស៖ *{student.khmer_name}* ({student.student_id})\n"
        f"• ថ្នាក់៖ {student.classroom.name if student.classroom else 'គ្មានថ្នាក់'}\n"
        f"• ខែដែលបានបង់៖ {', '.join(paid_months_list)}\n"
        f"• ចំនួនទឹកប្រាក់៖ *{total_recorded:,.0f} ៛*\n"
        f"• អ្នកកត់ត្រា៖ {user_disp}\n"
        f"• កាលបរិច្ឆេទ៖ {timezone.now().strftime('%d/%m/%Y %H:%M')}"
    )

    return {
        'success': True,
        'message': f"🎉 បានកត់ត្រាបង់ប្រាក់ចំនួន {total_recorded:,.0f} ៛ ជោគជ័យ!",
        'updated_text': updated_text
    }


def send_classroom_fee_status_telegram(chat_id, classroom, active_year, config):
    """
    Sends due fee summary for an entire classroom to Telegram.
    """
    students = Student.objects.filter(classroom=classroom, status='ACTIVE').select_related('category')
    month_seq = config.get_month_sequence()
    ticked_set = set(config.ticked_months or [])
    rates = {(r.category_id, r.month): r.amount for r in MonthlyFeeRate.objects.filter(config=config)}
    payments = {(p.student_id, p.month): p.paid_amount for p in StudentMonthlyPayment.objects.filter(academic_year=active_year, student__classroom=classroom)}
    monthly_cats = {(mc.student_id, mc.month): mc.category for mc in StudentMonthlyCategory.objects.filter(academic_year=active_year, student__classroom=classroom)}

    due_list = []
    total_class_debt = Decimal('0.00')

    for st in students:
        start_idx = month_seq.index(st.fee_start_month) if st.fee_start_month in month_seq else 0
        end_idx = month_seq.index(st.fee_end_month) if st.fee_end_month in month_seq else len(month_seq) - 1

        st_expected = Decimal('0.00')
        st_paid = Decimal('0.00')

        for idx, m in enumerate(month_seq):
            is_attending = (start_idx <= idx <= end_idx)
            is_ticked = (m in ticked_set) and is_attending
            m_cat = monthly_cats.get((st.id, m), st.category)
            m_cat_id = m_cat.id if m_cat else None
            expected = rates.get((m_cat_id, m), Decimal('20000.00')) if m_cat_id else Decimal('20000.00')
            paid = payments.get((st.id, m), Decimal('0.00'))
            st_paid += paid
            if is_ticked:
                st_expected += expected

        st_debt = max(Decimal('0.00'), st_expected - st_paid)
        if st_debt > 0:
            due_list.append((st, st_debt))
            total_class_debt += st_debt

    msg = f"🏫 *របាយការណ៍បង់ថ្លៃទឹកភ្លើង ថ្នាក់ {classroom.name}*\n"
    msg += f"👥 សិស្សសរុប៖ {students.count()} នាក់\n"
    msg += f"🔴 សិស្សនៅជំពាក់៖ {len(due_list)} នាក់\n"
    msg += f"💰 ប្រាក់ជំពាក់សរុប៖ *{total_class_debt:,.0f} ៛*\n\n"

    if due_list:
        msg += "*បញ្ជីសិស្សនៅជំពាក់៖*\n"
        for i, (st, debt) in enumerate(due_list[:20], 1):
            msg += f"{i}. {st.khmer_name} (`{st.student_id}`): *{debt:,.0f} ៛*\n"
    else:
        msg += "🎉 សិស្សទាំងអស់ក្នុងថ្នាក់នេះបានបង់គ្រប់ចំនួនរួចរាល់!"

    send_telegram_notification(
        title=f"របាយការណ៍ថ្នាក់ {classroom.name}",
        message=msg,
        custom_chat_id=chat_id
    )
