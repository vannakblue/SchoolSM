"""
Report Card PDF Generator & Telegram Dispatcher.
Generates official PDF Report Cards and sends them to Telegram groups or individual parents.
"""

import io
from decimal import Decimal
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable
from reportlab.lib.units import inch, cm

from apps.accounts.models import SchoolProfile
from apps.accounts.utils import send_telegram_notification, send_telegram_document
from apps.examinations.models import Grade, ExamTerm
from apps.students.models import Student


def generate_report_card_pdf_bytes(student, term):
    """
    Generates an official PDF Report Card in memory using ReportLab.
    Returns bytes of the PDF document.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm
    )

    school = SchoolProfile.get_settings()
    classroom = student.classroom

    # Collect grades
    grades = Grade.objects.filter(student=student, exam_term=term).select_related('subject')
    total_score = Decimal('0.00')
    total_max = Decimal('0.00')

    for g in grades:
        total_score += g.score
        total_max += g.max_score

    if total_max == 0 and classroom:
        total_max = classroom.get_total_max_score()

    percentage = round((float(total_score) / float(total_max)) * 100, 2) if total_max > 0 else 0.0

    if percentage >= 90:
        overall_grade = 'A (ល្អប្រសើរ / Excellent)'
    elif percentage >= 80:
        overall_grade = 'B (ល្អណាស់ / Very Good)'
    elif percentage >= 70:
        overall_grade = 'C (ល្អ / Good)'
    elif percentage >= 60:
        overall_grade = 'D (ល្អបង្គួរ / Fairly Good)'
    elif percentage >= 50:
        overall_grade = 'E (មធ្យម / Passing)'
    else:
        overall_grade = 'F (ធ្លាក់ / Failed)'

    # Calculate rank in class
    all_class_students = Student.objects.filter(classroom=classroom, status='ACTIVE') if classroom else []
    student_scores = []
    for s in all_class_students:
        s_grades = Grade.objects.filter(student=s, exam_term=term)
        s_tot = sum(g.score for g in s_grades)
        student_scores.append((s.id, s_tot))

    student_scores.sort(key=lambda x: x[1], reverse=True)
    rank = 1
    for idx, (s_id, _) in enumerate(student_scores, 1):
        if s_id == student.id:
            rank = idx
            break

    story = []
    styles = getSampleStyleSheet()

    # Title & Headers
    title_style = ParagraphStyle(
        'HeaderTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        alignment=1, # Center
        textColor=colors.HexColor('#1e3a8a')
    )
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        alignment=1,
        textColor=colors.HexColor('#475569')
    )
    bold_style = ParagraphStyle(
        'BoldText',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#0f172a')
    )
    normal_style = ParagraphStyle(
        'NormalText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#1e293b')
    )

    story.append(Paragraph(f"<b>KINGDOM OF CAMBODIA - NATION RELIGION KING</b>", title_style))
    story.append(Paragraph(f"<b>{school.ministry_name}</b>", subtitle_style))
    story.append(Paragraph(f"<b>{school.name_en or school.name_kh}</b>", title_style))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#1e3a8a'), spaceAfter=15))

    story.append(Paragraph(f"<b>OFFICIAL ACADEMIC REPORT CARD / ព្រឹត្តិបត្រពិន្ទុ</b>", title_style))
    story.append(Paragraph(f"Exam Term: {term.name} | Academic Year: {term.academic_year.name}", subtitle_style))
    story.append(Spacer(1, 12))

    # Student Info Grid
    info_data = [
        [
            Paragraph(f"<b>Student Name:</b> {student.khmer_name} ({student.latin_name})", normal_style),
            Paragraph(f"<b>Student ID:</b> {student.student_id}", normal_style)
        ],
        [
            Paragraph(f"<b>Classroom:</b> {classroom.name if classroom else '-'} ({classroom.get_track_display() if classroom else '-'})", normal_style),
            Paragraph(f"<b>Gender:</b> {student.get_gender_display()}", normal_style)
        ]
    ]
    info_table = Table(info_data, colWidths=[9 * cm, 8.5 * cm])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 14))

    # Grades Table
    grade_table_data = [
        ['No.', 'Subject / មុខវិជ្ជា', 'Max Score', 'Score Obtained', 'Percentage', 'Grade']
    ]

    for idx, g in enumerate(grades, 1):
        g_pct = round((float(g.score) / float(g.max_score)) * 100, 1) if g.max_score > 0 else 0
        grade_table_data.append([
            str(idx),
            g.subject.name_en or g.subject.name_kh,
            f"{g.max_score:.1f}",
            f"{g.score:.1f}",
            f"{g_pct}%",
            g.grade_letter or '-'
        ])

    if not grades:
        grade_table_data.append(['-', 'No grades recorded for this term', '-', '-', '-', '-'])

    grade_table = Table(grade_table_data, colWidths=[1.2 * cm, 6.3 * cm, 2.5 * cm, 2.8 * cm, 2.5 * cm, 2.2 * cm])
    grade_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (1, 1), (1, -1), 'LEFT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#94a3b8')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(grade_table)
    story.append(Spacer(1, 14))

    # Summary & Class Standing Box
    summary_data = [
        ['Total Score Obtained:', f"{total_score:.1f} / {total_max:.0f}", 'Class Rank:', f"Rank #{rank} in Class"],
        ['Percentage Score:', f"{percentage}%", 'Overall Grade:', overall_grade]
    ]
    summary_table = Table(summary_data, colWidths=[4.5 * cm, 4 * cm, 4 * cm, 5 * cm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#eff6ff')),
        ('BOX', (0,0), (-1,-1), 1.5, colors.HexColor('#3b82f6')),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('TEXTCOLOR', (0,0), (-1,-1), colors.HexColor('#1e3a8a')),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 25))

    # Signatures Footer
    sig_data = [
        [
            Paragraph(f"Class Advisor / គ្រូបន្ទុកថ្នាក់<br/><br/><br/>______________________", subtitle_style),
            Paragraph(f"School Principal / នាយកសាលា<br/><br/><br/><b>{school.principal_name}</b>", subtitle_style)
        ]
    ]
    sig_table = Table(sig_data, colWidths=[8.75 * cm, 8.75 * cm])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(sig_table)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def build_report_card_telegram_message(student, term):
    """
    Constructs a beautiful Markdown formatted message summarizing the student's report card.
    """
    school = SchoolProfile.get_settings()
    classroom = student.classroom
    grades = Grade.objects.filter(student=student, exam_term=term).select_related('subject')

    total_score = Decimal('0.00')
    total_max = Decimal('0.00')
    lines = []

    for g in grades:
        total_score += g.score
        total_max += g.max_score
        lines.append(f"• {g.subject.name_kh}: *{g.score:.1f}* /{g.max_score:.0f} (និទ្ទេស {g.grade_letter or '-'})")

    if total_max == 0 and classroom:
        total_max = classroom.get_total_max_score()

    percentage = round((float(total_score) / float(total_max)) * 100, 2) if total_max > 0 else 0.0

    if percentage >= 90:
        overall_grade = 'A (ល្អប្រសើរ)'
    elif percentage >= 80:
        overall_grade = 'B (ល្អណាស់)'
    elif percentage >= 70:
        overall_grade = 'C (ល្អ)'
    elif percentage >= 60:
        overall_grade = 'D (ល្អបង្គួរ)'
    elif percentage >= 50:
        overall_grade = 'E (មធ្យម)'
    else:
        overall_grade = 'F (ធ្លាក់)'

    # Calculate class rank
    all_class_students = Student.objects.filter(classroom=classroom, status='ACTIVE') if classroom else []
    student_scores = []
    for s in all_class_students:
        s_grades = Grade.objects.filter(student=s, exam_term=term)
        s_tot = sum(g.score for g in s_grades)
        student_scores.append((s.id, s_tot))

    student_scores.sort(key=lambda x: x[1], reverse=True)
    rank = 1
    for idx, (s_id, _) in enumerate(student_scores, 1):
        if s_id == student.id:
            rank = idx
            break

    subject_scores_str = "\n".join(lines) if lines else "• មិនទាន់មានទិន្នន័យពិន្ទុ"

    msg = (
        f"📊 *ព្រឹត្តិបត្រពិន្ទុ & លទ្ធផលការសិក្សា (Official Report Card)*\n"
        f"🏫 *{school.name_kh}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 *សិស្ស:* {student.khmer_name} ({student.latin_name})\n"
        f"🆔 *អត្តលេខ:* `{student.student_id}` | 📚 *ថ្នាក់:* {classroom.name if classroom else '-'}\n"
        f"🗓️ *សម័យប្រឡង:* {term.name}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📖 *ពិន្ទុតាមមុខវិជ្ជា:*\n"
        f"{subject_scores_str}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 *ពិន្ទុសរុប:* *{total_score:.1f}* / {total_max:.0f}\n"
        f"📈 *ភាគរយ:* *{percentage}%* | 🎖️ *និទ្ទេសរួម:* *{overall_grade}*\n"
        f"🥇 *ចំណាត់ថ្នាក់ក្នុងថ្នាក់:* *ចំណាត់ថ្នាក់ទី {rank}* (ក្នុងចំណោម {len(all_class_students)} នាក់)\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✨ _សូមអបអរសាទរចំពោះការខិតខំប្រឹងប្រែងរៀនសូត្ររបស់សិស្ស!_"
    )
    return msg


def dispatch_student_report_card_to_telegram(student, term, destination='CLASS_GROUP', send_mode='BOTH', custom_chat_id=None):
    """
    Dispatches the report card (Message, PDF Document, or Both) to Telegram.
    destination: 'CLASS_GROUP', 'PARENT_INDIVIDUAL', 'CUSTOM_CHAT_ID'
    send_mode: 'MESSAGE_ONLY', 'PDF_ONLY', 'BOTH'
    """
    school = SchoolProfile.get_settings()
    
    # Determine target chat ID
    target_chat_id = None
    if destination == 'CUSTOM_CHAT_ID':
        target_chat_id = custom_chat_id
    elif destination == 'PARENT_INDIVIDUAL':
        # Check student/parent emergency contact or telegram ID
        target_chat_id = custom_chat_id or student.emergency_phone or student.phone
    else: # CLASS_GROUP
        target_chat_id = custom_chat_id  # Falls back to default TelegramConfig chat_id if None

    msg_text = build_report_card_telegram_message(student, term)
    pdf_bytes = generate_report_card_pdf_bytes(student, term)
    pdf_filename = f"Report_Card_{student.student_id}_{term.name.replace(' ', '_')}.pdf"

    log_doc = None
    log_msg = None

    if send_mode in ['MESSAGE_ONLY', 'BOTH']:
        log_msg = send_telegram_notification(
            title=f"លទ្ធផលប្រឡង៖ {student.khmer_name} ({term.name})",
            message=msg_text,
            recipient_name=f"{student.khmer_name} (អាណាព្យាបាល)",
            recipient_phone=student.phone or student.emergency_phone,
            custom_chat_id=target_chat_id
        )

    if send_mode in ['PDF_ONLY', 'BOTH']:
        caption = f"📄 *ប័ណ្ណពិន្ទុផ្លូវការ (PDF)*: {student.khmer_name} - {term.name}"
        log_doc = send_telegram_document(
            document_bytes=pdf_bytes,
            filename=pdf_filename,
            caption=caption,
            recipient_name=f"{student.khmer_name} (អាណាព្យាបាល)",
            custom_chat_id=target_chat_id
        )

    return {
        'status': 'success',
        'student': student.khmer_name,
        'student_id': student.student_id,
        'term': term.name,
        'pdf_filename': pdf_filename,
        'destination': destination,
        'send_mode': send_mode
    }
