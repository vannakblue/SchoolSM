import logging
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from apps.academics.models import AcademicYear, Classroom
from apps.students.models import Student
from apps.finance.models import MonthlyFeeConfig, MonthlyFeeRate, StudentMonthlyPayment, StudentMonthlyCategory
from apps.accounts.utils import send_telegram_notification, edit_telegram_message, answer_telegram_callback_query
from apps.finance.views import get_monthly_fees_data, MONTH_NAMES_KM

logger = logging.getLogger(__name__)

def handle_telegram_fees_message(msg):
    """
    Handle incoming text commands related to fees:
    - /fees
    - /fees <classroom_name> (e.g. /fees 8A)
    - /fees <student_id> (e.g. /fees 2624001)
    - /pay <student_id> (e.g. /pay 2624001)
    """
    chat_id = msg.get('chat', {}).get('id')
    text = (msg.get('text') or '').strip()
    if not chat_id or not text:
        return

    parts = text.split()
    cmd = parts[0].lower()

    if cmd in ['/fees', '/fee', '/due']:
        arg = parts[1] if len(parts) > 1 else ''
        return process_fees_inquiry(chat_id, arg)
    elif cmd in ['/pay', '/collect']:
        arg = parts[1] if len(parts) > 1 else ''
        return process_pay_command(chat_id, arg)


def process_fees_inquiry(chat_id, arg):
    """
    Inquiry for due fees by classroom or student ID
    """
    active_year = AcademicYear.objects.filter(is_current=True).first()
    if not active_year:
        send_telegram_notification(chat_id=chat_id, message="⚠️ មិនទាន់មានឆ្នាំសិក្សាសកម្មក្នុងប្រព័ន្ធឡើយ។")
        return

    config = MonthlyFeeConfig.get_or_create_for_year(active_year)
    ticked_months = config.ticked_months or []

    if not arg:
        # Overview summary
        classrooms = Classroom.objects.filter(academic_year=active_year).order_by('grade_level', 'name')
        msg = f"📊 *សង្ខេបការប្រមូលថ្លៃទឹកភ្លើង ({active_year.name})*\n"
        msg += f"📅 ខែដែលត្រូវប្រមូល (Active): {len(ticked_months)} ខែ\n\n"
        msg += "*សូមជ្រើសរើស ឬវាយពាក្យបញ្ជាដូចខាងក្រោម៖*\n"
        for c in classrooms[:10]:
            msg += f"• `/fees {c.name}` - ពិនិត្យថ្នាក់ {c.name}\n"
        msg += "\n💡 ឬវាយ `/fees [ID_សិស្ស]` ដើម្បីពិនិត្យសិស្សម្នាក់ៗ"
        send_telegram_notification(custom_chat_id=chat_id, message=msg)
        return

    # Check if arg is student ID
    student = Student.objects.filter(student_id__iexact=arg).first()
    if student:
        return send_student_fee_status_telegram(chat_id, student, active_year, config)

    # Check if arg is classroom name
    classroom = Classroom.objects.filter(name__iexact=arg, academic_year=active_year).first()
    if not classroom:
        classroom = Classroom.objects.filter(name__icontains=arg).first()

    if classroom:
        return send_classroom_fee_status_telegram(chat_id, classroom, active_year, config)

    send_telegram_notification(
        custom_chat_id=chat_id,
        message=f"❌ រកមិនឃើញថ្នាក់ ឬសិស្សដែលមានកូដ/ឈ្មោះ «{arg}» ឡើយ។\nសូមវាយ `/fees 8A` ឬ `/fees 2624001`"
    )


def send_student_fee_status_telegram(chat_id, student, active_year, config):
    month_seq = config.get_month_sequence()
    ticked_set = set(config.ticked_months or [])
    payments = {p.month: p for p in StudentMonthlyPayment.objects.filter(student=student, academic_year=active_year)}
    monthly_cats = {mc.month: mc.category for mc in StudentMonthlyCategory.objects.filter(student=student, academic_year=active_year)}
    rates = {(r.category_id, r.month): r.amount for r in MonthlyFeeRate.objects.filter(config=config)}

    fee_start_idx = month_seq.index(student.fee_start_month) if student.fee_start_month in month_seq else 0
    fee_end_idx = month_seq.index(student.fee_end_month) if student.fee_end_month in month_seq else len(month_seq) - 1

    total_expected = Decimal('0.00')
    total_paid = Decimal('0.00')
    unpaid_months = []

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
        total_paid += paid

        if is_ticked:
            total_expected += expected
            if paid < expected:
                m_name = MONTH_NAMES_KM.get(m, f'ខែ {m}')
                unpaid_months.append((m, m_name, expected - paid))

    debt = max(Decimal('0.00'), total_expected - total_paid)

    msg = f"👤 *ព័ត៌មានកម្រៃសិក្សា / ទឹកភ្លើង*\n"
    msg += f"• សិស្ស៖ *{student.khmer_name}* ({student.student_id})\n"
    msg += f"• ថ្នាក់៖ {student.classroom.name if student.classroom else 'គ្មានថ្នាក់'}\n"
    msg += f"• ប្រភេទ៖ {student.category.name if student.category else 'ទូទៅ'}\n"
    msg += f"• សរុបបានបង់៖ {total_paid:,.0f} ៛\n"

    if debt > 0:
        msg += f"• 🔴 *ប្រាក់ជំពាក់៖ {debt:,.0f} ៛*\n"
        msg += f"• ខែជំពាក់៖ {', '.join([m[1] for m in unpaid_months])}\n\n"
        msg += f"👉 វាយ `/pay {student.student_id}` ដើម្បីកត់ត្រាបង់ប្រាក់"
    else:
        msg += f"• 🟢 *ស្ថានភាព៖ បង់រួចរាល់គ្រប់ចំនួន*\n"

    send_telegram_notification(custom_chat_id=chat_id, message=msg)


def send_classroom_fee_status_telegram(chat_id, classroom, active_year, config):
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
            msg += f"{i}. {st.khmer_name} ({st.student_id}): *{debt:,.0f} ៛* -> `/pay {st.student_id}`\n"
    else:
        msg += "🎉 សិស្សទាំងអស់ក្នុងថ្នាក់នេះបានបង់គ្រប់ចំនួនរួចរាល់!"

    send_telegram_notification(custom_chat_id=chat_id, message=msg)


def process_pay_command(chat_id, arg):
    """
    Process /pay command with interactive inline buttons
    """
    if not arg:
        send_telegram_notification(
            custom_chat_id=chat_id,
            message="⚠️ សូមបញ្ជាក់កូដសិស្ស ឧទាហរណ៍៖ `/pay 2624001`"
        )
        return

    student = Student.objects.filter(student_id__iexact=arg).first()
    if not student:
        send_telegram_notification(
            custom_chat_id=chat_id,
            message=f"❌ រកមិនឃើញសិស្សដែលមានកូដ «{arg}» ឡើយ។"
        )
        return

    active_year = AcademicYear.objects.filter(is_current=True).first()
    config = MonthlyFeeConfig.get_or_create_for_year(active_year) if active_year else None
    if not active_year or not config:
        send_telegram_notification(custom_chat_id=chat_id, message="⚠️ មិនមានការកំណត់ឆ្នាំសិក្សាសកម្មឡើយ។")
        return

    month_seq = config.get_month_sequence()
    ticked_set = set(config.ticked_months or [])
    payments = {p.month: p for p in StudentMonthlyPayment.objects.filter(student=student, academic_year=active_year)}
    monthly_cats = {mc.month: mc.category for mc in StudentMonthlyCategory.objects.filter(student=student, academic_year=active_year)}
    rates = {(r.category_id, r.month): r.amount for r in MonthlyFeeRate.objects.filter(config=config)}

    fee_start_idx = month_seq.index(student.fee_start_month) if student.fee_start_month in month_seq else 0
    fee_end_idx = month_seq.index(student.fee_end_month) if student.fee_end_month in month_seq else len(month_seq) - 1

    inline_keyboard = []
    unpaid_total = Decimal('0.00')

    for idx, m in enumerate(month_seq):
        is_attending = (fee_start_idx <= idx <= fee_end_idx)
        if not ((m in ticked_set) and is_attending):
            continue

        m_cat = monthly_cats.get(m, student.category)
        m_cat_id = m_cat.id if m_cat else None
        expected = Decimal('20000.00')
        if m_cat_id:
            expected = rates.get((m_cat_id, m), Decimal('20000.00'))

        p = payments.get(m)
        paid = p.paid_amount if p else Decimal('0.00')

        if paid < expected:
            rem = expected - paid
            unpaid_total += rem
            m_name = MONTH_NAMES_KM.get(m, f'ខែ {m}')
            inline_keyboard.append([{
                'text': f"💵 បង់ {m_name} ({rem:,.0f} ៛)",
                'callback_data': f"feepay:{student.id}:{m}"
            }])

    if unpaid_total > 0 and len(inline_keyboard) > 1:
        inline_keyboard.append([{
            'text': f"✅ បង់គ្រប់ខែទាំងអស់ ({unpaid_total:,.0f} ៛)",
            'callback_data': f"feepay:{student.id}:ALL"
        }])

    if not inline_keyboard:
        send_telegram_notification(
            custom_chat_id=chat_id,
            message=f"🎉 សិស្ស *{student.khmer_name}* ({student.student_id}) គ្មានប្រាក់ជំពាក់ក្នុងខែ Active ឡើយ!"
        )
        return

    msg = f"💳 *កត់ត្រាបង់ប្រាក់ថ្លៃទឹកភ្លើង*\n"
    msg += f"• សិស្ស៖ *{student.khmer_name}* ({student.student_id})\n"
    msg += f"• ថ្នាក់៖ {student.classroom.name if student.classroom else 'គ្មានថ្នាក់'}\n"
    msg += f"• ប្រាក់ជំពាក់សរុប៖ *{unpaid_total:,.0f} ៛*\n\n"
    msg += "សូមចុចលើប៊ូតុងខាងក្រោមដើម្បីកត់ត្រាបង់ប្រាក់៖"

    import json
    reply_markup = {'inline_keyboard': inline_keyboard}

    from apps.accounts.models import TelegramConfig
    import requests
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
                timeout=5
            )
        except Exception as e:
            logger.error(f"Error sending interactive pay message: {e}")


def process_telegram_fee_callback(callback_data, user_disp, chat_id, message_id):
    """
    Handles inline button callback:
    feepay:<student_id>:<month_or_ALL>
    """
    parts = callback_data.split(':')
    if len(parts) < 3:
        return {'success': False, 'message': 'Invalid callback data'}

    student_id = parts[1]
    month_target = parts[2]

    student = Student.objects.filter(id=student_id).first()
    if not student:
        return {'success': False, 'message': 'រកមិនឃើញទិន្នន័យសិស្សឡើយ'}

    active_year = AcademicYear.objects.filter(is_current=True).first()
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
            expected = Decimal('20000.00')
            if m_cat_id:
                expected = rates.get((m_cat_id, m), Decimal('20000.00'))

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

    updated_text = f"✅ *បានកត់ត្រាការបង់ប្រាក់ជោគជ័យ!*\n\n"
    updated_text += f"• សិស្ស៖ *{student.khmer_name}* ({student.student_id})\n"
    updated_text += f"• ថ្នាក់៖ {student.classroom.name if student.classroom else 'គ្មានថ្នាក់'}\n"
    updated_text += f"• ខែដែលបានបង់៖ {', '.join(paid_months_list)}\n"
    updated_text += f"• ចំនួនទឹកប្រាក់៖ *{total_recorded:,.0f} ៛*\n"
    updated_text += f"• អ្នកកត់ត្រា៖ {user_disp}\n"
    updated_text += f"• កាលបរិច្ឆេទ៖ {timezone.now().strftime('%d/%m/%Y %H:%M')}"

    return {
        'success': True,
        'message': f"🎉 បានកត់ត្រាបង់ប្រាក់ចំនួន {total_recorded:,.0f} ៛ ជោគជ័យ!",
        'updated_text': updated_text
    }
