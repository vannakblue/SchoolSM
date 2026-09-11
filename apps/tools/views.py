import os
import io
import json
import re
from django.conf import settings
from django.utils import timezone
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse, FileResponse, Http404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from apps.accounts.decorators import role_required
from apps.tools.backup_utils import (
    get_db_statistics, create_database_backup, list_backups,
    restore_database_backup, delete_backup, get_backup_dir, get_db_path,
    is_sqlite_database, create_json_backup
)

from apps.academics.models import Classroom, AcademicYear
from apps.students.models import Student
from apps.accounts.khmer_lunar import calculate_khmer_lunar_details, get_khmer_lunar_date
from apps.tools.lunar_excel_service import (
    generate_dynamic_lunar_converter_excel,
    export_lunar_calendar_excel,
    batch_convert_uploaded_excel
)

import pypdf
from docx import Document
from openpyxl import Workbook


@login_required
def tools_hub(request):
    """
    Central Online Tools Hub displaying all categories and utilities.
    """
    total_classrooms = Classroom.objects.count()
    return render(request, 'tools/hub.html', {
        'page_title': 'មជ្ឈមណ្ឌលឧបករណ៍អនឡាញ (Online Tools Hub)',
        'total_classrooms': total_classrooms,
    })


@login_required
def pdf_merge_view(request):
    """
    PDF Merge & Organizer Tool: Merge multiple PDF documents, re-order, preview.
    """
    return render(request, 'tools/pdf_merge.html', {
        'page_title': 'បញ្ចូលឯកសារ PDF ចូលគ្នា (PDF Merge)',
    })


@login_required
def pdf_split_view(request):
    """
    PDF Split & Page Extractor: Extract specific pages or split PDF into pieces.
    """
    return render(request, 'tools/pdf_split.html', {
        'page_title': 'បំបែក & ទាញយកទំព័រ PDF (PDF Split & Extract)',
    })


@login_required
def pdf_to_word_excel_view(request):
    """
    PDF to Word (.docx) & PDF to Excel (.xlsx) / CSV Table Extractor.
    """
    return render(request, 'tools/pdf_to_word_excel.html', {
        'page_title': 'បំលែង PDF ទៅជា Word & Excel (PDF to Word & Excel Converter)',
    })


@login_required
def images_to_pdf_view(request):
    """
    Images to PDF Converter: Convert exam photos, homework, documents to single PDF.
    """
    return render(request, 'tools/images_to_pdf.html', {
        'page_title': 'បំលែងរូបភាពជាឯកសារ PDF (Images to PDF)',
    })


@login_required
def doc_scanner_view(request):
    """
    Smart Document & Paper Scanner (CamScanner-Style) with live camera capture & paper filters.
    """
    return render(request, 'tools/doc_scanner.html', {
        'page_title': 'ម៉ាស៊ីនស្កេនក្រដាស & ឯកសារ (Smart Document Scanner)',
    })


@login_required
def image_editor_view(request):
    """
    Studio Image Editor: Crop, Rotate, Filter, Draw, Annotate, Add School Watermark.
    """
    return render(request, 'tools/image_editor.html', {
        'page_title': 'កម្មវិធីកែសម្រួលរូបភាព (Studio Image Editor)',
    })


@login_required
def id_photo_maker_view(request):
    """
    Student & Teacher ID Photo Maker (4x6 & 3x4 cm) with background replacer & multi-photo sheet.
    """
    return render(request, 'tools/id_photo_maker.html', {
        'page_title': 'បង្កើតរូបថតកាតសិស្ស-គ្រូ 4x6 & 3x4 (ID Photo Maker)',
    })


@login_required
def image_compressor_view(request):
    """
    Batch Image Compressor & Format Converter (PNG, JPG, WEBP).
    """
    return render(request, 'tools/image_compressor.html', {
        'page_title': 'បង្រួម & បំលែងប្រភេទរូបភាព (Image Compressor & Converter)',
    })


@login_required
def qr_generator_view(request):
    """
    Advanced QR Code Generator for Links, WiFi, vCards, Telegram with school logo.
    """
    return render(request, 'tools/qr_generator.html', {
        'page_title': 'បង្កើត QR Code គ្រប់ប្រភេទ (Advanced QR Generator)',
    })


@login_required
def qr_scanner_view(request):
    """
    QR Code & Barcode Scanner via device camera or file upload.
    """
    return render(request, 'tools/qr_scanner.html', {
        'page_title': 'ស្កេន QR Code & Barcode (QR & Barcode Scanner)',
    })


@login_required
def khmer_number_converter_view(request):
    """
    Khmer Number to Words & Currency Spellout Converter.
    """
    return render(request, 'tools/khmer_number_converter.html', {
        'page_title': 'បំលែងលេខទៅជាអក្សរខ្មែរ (Khmer Number to Words)',
    })


@login_required
def khmer_lunar_converter_view(request):
    """
    Solar to Khmer Lunar Date Converter (Chhankitek) with real-time conversion,
    monthly calendar view, MoEYS formal signature lines, and holy days detection.
    """
    import datetime
    today = datetime.date.today()
    initial_details = calculate_khmer_lunar_details(today)
    return render(request, 'tools/khmer_lunar_converter.html', {
        'page_title': 'បម្លែងថ្ងៃខែចន្ទគតិ (Khmer Lunar Calendar Converter)',
        'today_str': today.strftime('%Y-%m-%d'),
        'today_details': initial_details,
    })


@login_required
def tool_lunar_download_excel_tool(request):
    """
    Downloads the interactive dynamic Excel file (.xlsx) which has built-in formulas
    that automatically convert Solar Dates to Khmer Lunar Dates inside Microsoft Excel / WPS / Google Sheets.
    Supports customizable start_year and end_year.
    """
    try:
        start_year = int(request.GET.get('start_year', 2000))
        end_year = int(request.GET.get('end_year', 2035))
    except (ValueError, TypeError):
        start_year, end_year = 2000, 2035

    if start_year > end_year:
        start_year, end_year = end_year, start_year

    # Clamp to reasonable bounds (1950 to 2060)
    start_year = max(1950, min(2060, start_year))
    end_year = max(start_year, min(2060, end_year))

    sample_date = request.GET.get('date', '').strip() or None
    buf = generate_dynamic_lunar_converter_excel(start_year=start_year, end_year=end_year, sample_date=sample_date)

    filename = f"SchoolSM_Khmer_Lunar_Converter_{start_year}_{end_year}.xlsx"
    response = HttpResponse(
        buf.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def tool_lunar_export_calendar_excel(request):
    """
    Exports a clean, official MoEYS-formatted Khmer Lunar Calendar for a specific month or an entire year.
    """
    import datetime
    today = datetime.date.today()
    try:
        year = int(request.GET.get('year', today.year))
    except (ValueError, TypeError):
        year = today.year

    month_param = request.GET.get('month', '').strip()
    month = None
    if month_param:
        try:
            m = int(month_param)
            if 1 <= m <= 12:
                month = m
        except (ValueError, TypeError):
            pass

    buf = export_lunar_calendar_excel(year=year, month=month)
    suffix = f"Month_{month}" if month else "Full_Year"
    filename = f"Khmer_Lunar_Calendar_{year}_{suffix}.xlsx"

    response = HttpResponse(
        buf.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@require_POST
def tool_lunar_batch_convert_excel(request):
    """
    Uploads an existing Excel file with solar dates and returns the updated file
    with Khmer lunar dates, zodiac, sak, and holy days appended.
    """
    excel_file = request.FILES.get('excel_file')
    if not excel_file:
        messages.error(request, "សូមជ្រើសរើសឯកសារ Excel ដើម្បីបម្លែង។")
        return redirect('tool_khmer_lunar_converter')

    try:
        buf = batch_convert_uploaded_excel(excel_file.read())
        orig_name = excel_file.name.rsplit('.', 1)[0]
        filename = f"{orig_name}_Khmer_Lunar_Converted.xlsx"
        response = HttpResponse(
            buf.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        messages.error(request, f"មានបញ្ហាក្នុងការបម្លែងឯកសារ Excel៖ {e}")
        return redirect('tool_khmer_lunar_converter')


@login_required
def text_analyzer_view(request):
    """
    Word Counter, Character Counter, Khmer Text Analyzer & Reading Time Estimator.
    """
    return render(request, 'tools/text_analyzer.html', {
        'page_title': 'រាប់ពាក្យ & វិភាគអត្ថបទ (Word Counter & Text Analyzer)',
    })


@login_required
def voice_typing_view(request):
    """
    Voice Typing & Speech-to-Text Dictation supporting Khmer and English.
    """
    return render(request, 'tools/voice_typing.html', {
        'page_title': 'វាយអត្ថបទតាមសំឡេង (Voice Typing & Speech to Text)',
    })


@login_required
def classroom_picker_view(request):
    """
    Interactive Classroom Lucky Draw Wheel, Random Name Picker, Team Splitter & Stopwatch.
    """
    active_year = AcademicYear.objects.filter(is_current=True).first()
    if active_year:
        classrooms = Classroom.objects.filter(academic_year=active_year).order_by('grade_level', 'name')
    else:
        classrooms = Classroom.objects.all().order_by('grade_level', 'name')
    return render(request, 'tools/classroom_picker.html', {
        'page_title': 'ចាប់ឆ្នោតសិស្ស & ចែកក្រុមរៀន (Classroom Lucky Draw & Team Builder)',
        'classrooms': classrooms,
        'active_year': active_year,
    })


@login_required
def calculator_converter_view(request):
    """
    Scientific Calculator & Universal Educational Unit Converter.
    """
    return render(request, 'tools/calculator_converter.html', {
        'page_title': 'ម៉ាស៊ីនគិតលេខ & បំលែងខ្នាត (Scientific Calculator & Unit Converter)',
    })


# --------------------------------------------------------------------------
# API Endpoints
# --------------------------------------------------------------------------

@login_required
@require_GET
def api_solar_to_lunar(request):
    """
    API endpoint that accepts a Gregorian/solar date string (e.g. YYYY-MM-DD or DD/MM/YYYY)
    and returns rich Khmer lunar date details, holy day status, moon phases, and copyable text.
    """
    date_str = request.GET.get('date', '').strip()
    try:
        details = calculate_khmer_lunar_details(date_str if date_str else None)
        return JsonResponse({
            'success': True,
            'data': details,
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=400)

@login_required
@require_GET
def api_classroom_students(request, classroom_id):
    """
    API returning student names and information for classroom lucky draw & team builder.
    """
    try:
        classroom = get_object_or_404(Classroom, id=classroom_id)
        students = Student.objects.filter(
            classroom=classroom,
            status=Student.Status.ACTIVE
        ).order_by('khmer_name')

        data = [{
            'id': s.id,
            'student_id': s.student_id or f"S-{s.id}",
            'khmer_name': s.khmer_name,
            'latin_name': s.latin_name or '',
            'gender': s.get_gender_display(),
            'gender_code': s.gender,
        } for s in students]

        return JsonResponse({
            'success': True,
            'classroom': {
                'id': classroom.id,
                'name': classroom.name,
                'total_students': len(data),
            },
            'students': data,
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@require_POST
def api_pdf_merge(request):
    """
    Server-side fallback endpoint to merge uploaded PDF files.
    """
    try:
        files = request.FILES.getlist('pdf_files')
        if not files:
            return JsonResponse({'success': False, 'error': 'មិនមានឯកសារ PDF ត្រូវបានជ្រើសរើសឡើយ'}, status=400)

        writer = pypdf.PdfWriter()
        for f in files:
            reader = pypdf.PdfReader(f)
            for page in reader.pages:
                writer.add_page(page)

        output_stream = io.BytesIO()
        writer.write(output_stream)
        output_stream.seek(0)

        response = HttpResponse(output_stream.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="Merged_SchoolSM_Document.pdf"'
        return response
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'បរាជ័យក្នុងការបញ្ចូល PDF: {str(e)}'}, status=500)


@login_required
def normalize_khmer_text(text):
    """
    Cleans up broken spacing between Khmer syllables and corrects misplaced pre-vowels.
    """
    if not text:
        return ""
    # Reorder pre-vowels (េ, ែ, ៃ) placed before consonants
    text = re.sub(r'([\u17C1\u17C2\u17C3])([\u1780-\u17B3])', r'\2\1', text)
    # Remove spaces between base consonants and coeng markers
    text = re.sub(r'\s+(\u17D2[\u1780-\u17B3])', r'\1', text)
    # Remove spaces between base consonants and dependent vowels
    text = re.sub(r'([\u1780-\u17B3])\s+([\u17B6-\u17C5])', r'\1\2', text)
    return text


@login_required
@require_POST
def api_pdf_to_docx(request):
    """
    Extract text and structured tables from uploaded PDF into Microsoft Word (.docx).
    Automatically detects table structures and builds real Word tables with borders and columns.
    """
    try:
        pdf_file = request.FILES.get('pdf_file')
        if not pdf_file:
            return JsonResponse({'success': False, 'error': 'សូមជ្រើសរើសឯកសារ PDF'}, status=400)

        reader = pypdf.PdfReader(pdf_file)
        doc = Document()

        # Set default font to Kantumruy Pro / Khmer OS Battambang
        for style in doc.styles:
            if hasattr(style, 'font'):
                style.font.name = 'Kantumruy Pro'

        original_name = pdf_file.name.rsplit('.', 1)[0] if '.' in pdf_file.name else 'Document'
        doc.add_heading(f'ឯកសារស្រង់ចេញ៖ {original_name}', level=1)

        total_pages = len(reader.pages)
        for idx, page in enumerate(reader.pages, start=1):
            text = page.extract_text()
            if not text:
                continue

            if total_pages > 1:
                doc.add_heading(f'--- ទំព័រទី {idx} ---', level=2)

            lines = [normalize_khmer_text(l.strip()) for l in text.split('\n') if l.strip()]
            
            # Group lines into paragraphs and table blocks
            current_table_rows = []

            for line in lines:
                # Detect if line is a table row (contains multiple spaces, tabs, or pipe symbols)
                parts = [p.strip() for p in re.split(r'\s{2,}|\t|\|', line) if p.strip()]

                if len(parts) >= 2:
                    current_table_rows.append(parts)
                else:
                    # If we had a table block accumulated, write it to docx as a real Table
                    if current_table_rows:
                        if len(current_table_rows) >= 2 or any(len(r) >= 3 for r in current_table_rows):
                            # Real Table detected
                            max_cols = max(len(r) for r in current_table_rows)
                            table = doc.add_table(rows=len(current_table_rows), cols=max_cols)
                            table.style = 'Table Grid'
                            for r_idx, row_data in enumerate(current_table_rows):
                                for c_idx, cell_value in enumerate(row_data):
                                    cell = table.cell(r_idx, c_idx)
                                    cell.text = cell_value
                        else:
                            for r in current_table_rows:
                                doc.add_paragraph("    ".join(r))
                        current_table_rows = []

                    # Add regular paragraph
                    doc.add_paragraph(line)

            # Flush any remaining table block
            if current_table_rows:
                if len(current_table_rows) >= 2 or any(len(r) >= 3 for r in current_table_rows):
                    max_cols = max(len(r) for r in current_table_rows)
                    table = doc.add_table(rows=len(current_table_rows), cols=max_cols)
                    table.style = 'Table Grid'
                    for r_idx, row_data in enumerate(current_table_rows):
                        for c_idx, cell_value in enumerate(row_data):
                            cell = table.cell(r_idx, c_idx)
                            cell.text = cell_value
                else:
                    for r in current_table_rows:
                        doc.add_paragraph("    ".join(r))

        output_stream = io.BytesIO()
        doc.save(output_stream)
        output_stream.seek(0)

        response = HttpResponse(
            output_stream.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        response['Content-Disposition'] = f'attachment; filename="{original_name}_converted.docx"'
        return response
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'បរាជ័យក្នុងការបំលែងជា Word: {str(e)}'}, status=500)


@login_required
@require_POST
def api_pdf_to_excel(request):
    """
    Extract text/tables from uploaded PDF into Microsoft Excel (.xlsx) with structured columns.
    """
    try:
        pdf_file = request.FILES.get('pdf_file')
        if not pdf_file:
            return JsonResponse({'success': False, 'error': 'សូមជ្រើសរើសឯកសារ PDF'}, status=400)

        reader = pypdf.PdfReader(pdf_file)
        wb = Workbook()
        ws = wb.active
        ws.title = "Extracted Data"

        row_num = 1
        ws.cell(row=row_num, column=1, value=f"ទិន្នន័យស្រង់ចេញពី PDF៖ {pdf_file.name}")
        row_num += 2

        for idx, page in enumerate(reader.pages, start=1):
            text = page.extract_text()
            if text:
                if len(reader.pages) > 1:
                    ws.cell(row=row_num, column=1, value=f"--- ទំព័រទី {idx} ---")
                    row_num += 1

                lines = text.split('\n')
                for line in lines:
                    line_str = line.strip()
                    if not line_str:
                        continue
                    parts = [p.strip() for p in re.split(r'\s{2,}|\t|\|', line_str) if p.strip()]
                    if parts:
                        for col_idx, part in enumerate(parts, start=1):
                            ws.cell(row=row_num, column=col_idx, value=part)
                        row_num += 1
                row_num += 1

        output_stream = io.BytesIO()
        wb.save(output_stream)
        output_stream.seek(0)

        original_name = pdf_file.name.rsplit('.', 1)[0] if '.' in pdf_file.name else 'Data'
        response = HttpResponse(
            output_stream.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{original_name}_extracted.xlsx"'
        return response
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'បរាជ័យក្នុងការបំលែងជា Excel: {str(e)}'}, status=500)


@login_required
@require_POST
def api_images_to_pdf(request):
    """
    Compile multiple uploaded images into a clean, high-quality PDF document.
    """
    try:
        images_files = request.FILES.getlist('images')
        if not images_files:
            return JsonResponse({'success': False, 'error': 'សូមជ្រើសរើសរូបភាពយ៉ាងហោចណាស់មួយសន្លឹក'}, status=400)

        from PIL import Image, ImageOps

        orientation = request.POST.get('orientation', 'portrait')
        page_size_choice = request.POST.get('pageSize', 'a4')
        margin_choice = request.POST.get('margin', 'small')
        doc_title = request.POST.get('docTitle', 'SchoolSM_Images_Document').strip() or 'SchoolSM_Images_Document'

        # Page dimensions (A4: 595 x 842 pt, scale x2 for sharp print)
        page_w, page_h = 595, 842
        if page_size_choice == 'letter':
            page_w, page_h = 612, 792

        if orientation == 'landscape':
            page_w, page_h = page_h, page_w

        margin_px = 0
        if margin_choice == 'small':
            margin_px = 25
        elif margin_choice == 'big':
            margin_px = 50

        pdf_pages = []
        for f in images_files:
            img = Image.open(f).convert('RGB')
            img = ImageOps.exif_transpose(img)  # Mobile photo auto-rotation fix

            if page_size_choice == 'fit':
                pdf_pages.append(img)
            else:
                canvas_img = Image.new('RGB', (page_w * 2, page_h * 2), color=(255, 255, 255))
                avail_w = (page_w - (margin_px * 2)) * 2
                avail_h = (page_h - (margin_px * 2)) * 2

                img_ratio = img.width / img.height
                avail_ratio = avail_w / avail_h

                if img_ratio > avail_ratio:
                    new_w = avail_w
                    new_h = int(avail_w / img_ratio)
                else:
                    new_h = avail_h
                    new_w = int(avail_h * img_ratio)

                resized_img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                pos_x = (margin_px * 2) + (avail_w - new_w) // 2
                pos_y = (margin_px * 2) + (avail_h - new_h) // 2
                canvas_img.paste(resized_img, (pos_x, pos_y))
                pdf_pages.append(canvas_img)

        if not pdf_pages:
            return JsonResponse({'success': False, 'error': 'មិនមានទិន្នន័យរូបភាព'}, status=400)

        output_stream = io.BytesIO()
        pdf_pages[0].save(
            output_stream,
            format='PDF',
            save_all=True,
            append_images=pdf_pages[1:],
            resolution=150.0
        )
        output_stream.seek(0)

        response = HttpResponse(output_stream.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{doc_title}.pdf"'
        return response
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'បរាជ័យក្នុងការបង្កើត PDF: {str(e)}'}, status=500)


# ==========================================
# DATABASE BACKUP, SNAPSHOT & RESTORE SUITE
# ==========================================

@login_required
@role_required(['ADMIN'])
def database_backup_view(request):
    """
    Main Database Backup & Snapshot Manager dashboard.
    """
    from apps.accounts.models import TelegramConfig
    from apps.academics.models import AcademicYear
    from apps.tools.backup_utils import list_academic_year_backups
    stats = get_db_statistics()
    backups = list_backups()
    year_backups = list_academic_year_backups()
    academic_years = AcademicYear.objects.all().order_by('-start_date')
    telegram_config = TelegramConfig.get_config()
    return render(request, 'tools/db_backup.html', {
        'page_title': 'ការគ្រប់គ្រង Database Backup & Snapshot',
        'stats': stats,
        'backups': backups,
        'total_backups': len(backups),
        'year_backups': year_backups,
        'academic_years': academic_years,
        'telegram_config': telegram_config,
    })


@login_required
@role_required(['ADMIN'])
@require_POST
def api_create_database_backup(request):
    """
    Creates an instant snapshot backup of the current database.
    """
    label = request.POST.get('label', '').strip() or 'Snapshot តាម Web'
    user_info = f"{request.user.get_full_name() or request.user.username} ({request.user.role})"
    try:
        result = create_database_backup(label=label, user_info=user_info)
        messages.success(request, f"បានបង្កើត Backup Snapshot '{result['filename']}' ដោយជោគជ័យ!")
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('format') == 'json':
            return JsonResponse({'success': True, 'result': result})
        return redirect('tool_database_backup')
    except Exception as e:
        messages.error(request, f"បរាជ័យក្នុងការបង្កើត Backup: {str(e)}")
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('format') == 'json':
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
        return redirect('tool_database_backup')


@login_required
@login_required
@role_required(['ADMIN'])
def download_database_backup(request, filename=None):
    """
    Downloads either a specific backup snapshot (.sqlite3 or .json) or the live database dump.
    """
    from datetime import datetime
    now_str = datetime.now().strftime('%Y%m%d_%H%M%S')

    if filename == 'json' or request.GET.get('format') == 'json' or (filename == 'current' and not is_sqlite_database()):
        from django.core.management import call_command
        output_stream = io.StringIO()
        call_command(
            'dumpdata',
            '--exclude=contenttypes',
            '--exclude=auth.permission',
            '--exclude=sessions',
            '--indent=2',
            stdout=output_stream
        )
        data_bytes = output_stream.getvalue().encode('utf-8')
        response = HttpResponse(data_bytes, content_type='application/json; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="school_db_backup_{now_str}.json"'
        return response

    if filename == 'current' or not filename:
        if is_sqlite_database():
            db_path = get_db_path()
            if not db_path.exists():
                raise Http404("Database file not found")
            response = FileResponse(open(db_path, 'rb'), content_type='application/x-sqlite3')
            response['Content-Disposition'] = f'attachment; filename="school_db_live_{now_str}.sqlite3"'
            return response
        else:
            return redirect('/tools/database-backup/download/?format=json')
    else:
        # Sanitize filename
        safe_filename = os.path.basename(filename)
        backup_file = get_backup_dir() / safe_filename
        if not backup_file.exists():
            from apps.tools.backup_utils import get_academic_year_backup_dir
            alt_file = get_academic_year_backup_dir() / safe_filename
            if alt_file.exists():
                backup_file = alt_file
            else:
                raise Http404("Backup snapshot not found")

        content_type = 'application/json' if safe_filename.endswith('.json') else 'application/x-sqlite3'
        response = FileResponse(open(backup_file, 'rb'), content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{safe_filename}"'
        return response


@login_required
@role_required(['ADMIN'])
@require_POST
def api_restore_database_backup(request):
    """
    Restores the database from a specified snapshot file (.sqlite3 or .json).
    """
    filename = request.POST.get('filename', '').strip()
    if not filename:
        messages.error(request, "សូមជ្រើសរើសឯកសារ Backup ដែលចង់ Restore!")
        return redirect('tool_database_backup')

    safe_filename = os.path.basename(filename)
    user_info = f"{request.user.get_full_name() or request.user.username}"
    try:
        result = restore_database_backup(safe_filename, user_info=user_info)
        messages.success(request, f"{result['message']} (ទិន្នន័យមុន Restore ត្រូវបាន Save ទុកក្នុង Safety Backup រួចរាល់)")
        return redirect('tool_database_backup')
    except Exception as e:
        messages.error(request, f"បរាជ័យក្នុងការ Restore Database: {str(e)}")
        return redirect('tool_database_backup')


@login_required
@role_required(['ADMIN'])
@require_POST
def api_upload_restore_database(request):
    """
    Upload an external backup file (.json or .sqlite3) and restore it into the database.
    """
    if 'db_file' not in request.FILES:
        messages.error(request, "សូមជ្រើសរើសឯកសារ Backup (.json ឬ .sqlite3) ដើម្បី Upload!")
        return redirect('tool_database_backup')

    uploaded_file = request.FILES['db_file']
    fname_lower = uploaded_file.name.lower()
    if not fname_lower.endswith(('.json', '.sqlite3', '.db', '.sqlite')):
        messages.error(request, "ឯកសារត្រូវតែជាប្រភេទ JSON Backup (.json) ឬ SQLite (.sqlite3 / .db)!")
        return redirect('tool_database_backup')

    # Save uploaded file to backups directory first
    from datetime import datetime
    backup_dir = get_backup_dir()
    now_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    clean_orig_name = "".join(c for c in uploaded_file.name if c.isalnum() or c in ('.', '_', '-'))
    
    if fname_lower.endswith('.json'):
        saved_filename = f"db_dump_{now_str}_uploaded_{clean_orig_name}"
    else:
        saved_filename = f"db_backup_{now_str}_uploaded_{clean_orig_name}"
        
    target_path = backup_dir / saved_filename

    with open(target_path, 'wb+') as dest:
        for chunk in uploaded_file.chunks():
            dest.write(chunk)

    # Now restore from this saved file
    user_info = f"{request.user.get_full_name() or request.user.username} (Web Upload)"
    try:
        result = restore_database_backup(saved_filename, user_info=user_info)
        messages.success(request, f"🎉 បាន Upload និង Restore Database ពី {uploaded_file.name} ដោយជោគជ័យ!")
    except Exception as e:
        messages.error(request, f"⚠️ បរាជ័យក្នុងការ Restore ពី Uploaded File: {str(e)}")

    return redirect('tool_database_backup')


@login_required
@role_required(['ADMIN'])
@require_POST
def api_delete_database_backup(request, filename):
    """
    Deletes a specified backup snapshot file.
    """
    safe_filename = os.path.basename(filename)
    try:
        delete_backup(safe_filename)
        messages.success(request, f"បានលុប Snapshot '{safe_filename}' ដោយជោគជ័យ!")
    except Exception as e:
        messages.error(request, f"បរាជ័យក្នុងការលុប Snapshot: {str(e)}")
    return redirect('tool_database_backup')


@login_required
@role_required(['ADMIN'])
@require_POST
def api_send_backup_to_telegram(request):
    """
    1-Click Pipeline: Creates and delivers live database backup directly to Telegram.
    """
    from apps.tools.backup_utils import send_database_backup_to_telegram
    format_type = request.POST.get('format', 'json')
    custom_chat_id = request.POST.get('chat_id', '').strip() or None
    user_info = f"{request.user.get_full_name() or request.user.username} (Admin Web UI)"

    try:
        result = send_database_backup_to_telegram(
            custom_chat_id=custom_chat_id,
            format_type=format_type,
            sender_user=user_info
        )
        if result['success']:
            messages.success(request, result['message'])
        else:
            messages.warning(request, result['message'])
    except Exception as e:
        messages.error(request, f"បរាជ័យក្នុងការបញ្ជូន Backup ទៅកាន់ Telegram: {str(e)}")

    return redirect('tool_database_backup')


@login_required
@role_required(['ADMIN'])
@require_POST
def api_save_backup_schedule(request):
    """
    Saves the Automated Database Backup Schedule configured by Admin directly from Web Browser.
    """
    from apps.accounts.models import TelegramConfig
    config = TelegramConfig.get_config()

    config.auto_backup_enabled = (request.POST.get('auto_backup_enabled') == 'on' or request.POST.get('auto_backup_enabled') == 'true')
    config.backup_frequency = request.POST.get('backup_frequency', 'DAILY')
    
    backup_time_str = request.POST.get('backup_time', '00:00')
    if backup_time_str:
        try:
            from datetime import time
            h, m = map(int, backup_time_str.split(':'))
            config.backup_time = time(h, m)
        except Exception:
            pass

    day_of_week = request.POST.get('backup_day_of_week')
    if day_of_week is not None and str(day_of_week).isdigit():
        config.backup_day_of_week = int(day_of_week)

    config.backup_format = request.POST.get('backup_format', 'json')
    config.backup_chat_id = request.POST.get('backup_chat_id', '').strip()
    
    # Optional update of general bot token & default chat id if provided
    bot_token = request.POST.get('bot_token', '').strip()
    if bot_token:
        config.bot_token = bot_token
    default_chat_id = request.POST.get('default_chat_id', '').strip()
    if default_chat_id:
        config.chat_id = default_chat_id

    config.save()

    status_txt = "បានបើក (Enabled)" if config.auto_backup_enabled else "បានបិទ (Disabled)"
    messages.success(request, f"🎉 បានរក្សាទុកការកំណត់ Auto-Backup Schedule រួចរាល់! ស្ថានភាព៖ {status_txt} ({config.get_backup_frequency_display()} វេលាម៉ោង {config.backup_time.strftime('%H:%M')})")
    return redirect('tool_database_backup')


@login_required
@role_required(['ADMIN'])
@require_POST
def api_trigger_schedule_check(request):
    """
    Tests or triggers the Automated Database Backup Schedule check immediately.
    """
    from apps.tools.backup_utils import check_and_run_scheduled_backup
    force = (request.POST.get('force') == 'true' or request.POST.get('force') == '1')
    try:
        res = check_and_run_scheduled_backup(force=force)
        if res.get('executed'):
            messages.success(request, res.get('message', 'បានដំណើរការ Auto-Backup ដោយជោគជ័យ!'))
        else:
            messages.info(request, f"ℹ️ {res.get('message', 'ពុំទាន់ដល់លក្ខខណ្ឌត្រូវ Backup ឡើយ។')}")
    except Exception as e:
        messages.error(request, f"បរាជ័យក្នុងការតេស្ត Auto-Backup: {str(e)}")

    return redirect('tool_database_backup')


# =====================================================================
# ACADEMIC YEAR SPECIFIC DATA BACKUP & RESTORE VIEWS
# =====================================================================

@login_required
@role_required(['ADMIN'])
def tool_academic_year_backup_export(request, year_id):
    """
    Creates and downloads a complete portable JSON backup package for a specific Academic Year.
    """
    from apps.academics.models import AcademicYear
    from apps.tools.backup_utils import create_academic_year_backup
    ay = get_object_or_404(AcademicYear, id=year_id)
    user_info = f"{request.user.get_full_name() or request.user.username} (Admin)"

    try:
        res = create_academic_year_backup(ay, user_info=user_info)
        filepath = res['filepath']
        filename = res['filename']

        if request.GET.get('action') == 'save_only':
            messages.success(request, f"🎉 បានបង្កើត និងរក្សាទុកកញ្ចប់ Backup ឆ្នាំសិក្សា «{ay.name}» ដោយជោគជ័យ! ({filename})")
            return redirect('tool_database_backup')

        # Download file directly
        response = FileResponse(open(filepath, 'rb'), content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        messages.error(request, f"បរាជ័យក្នុងការ Backup ឆ្នាំសិក្សា {ay.name}: {str(e)}")
        return redirect('tool_database_backup')


@login_required
@role_required(['ADMIN'])
@require_POST
def tool_academic_year_backup_restore(request):
    """
    Restores an Academic Year Backup Package from an uploaded JSON file or saved file.
    """
    from apps.tools.backup_utils import restore_academic_year_backup, get_academic_year_backup_dir
    user_info = f"{request.user.get_full_name() or request.user.username}"

    # Case 1: Uploaded JSON File
    if 'year_backup_file' in request.FILES:
        uploaded_file = request.FILES['year_backup_file']
        if not uploaded_file.name.lower().endswith('.json'):
            messages.error(request, "ឯកសារ Backup ឆ្នាំសិក្សាត្រូវតែជាប្រភេទ JSON (.json)!")
            return redirect('tool_database_backup')
        try:
            content = uploaded_file.read().decode('utf-8')
            res = restore_academic_year_backup(content, user_info=user_info)
            messages.success(request, res['message'])
        except Exception as e:
            messages.error(request, f"បរាជ័យក្នុងការ Restore ឆ្នាំសិក្សាពី {uploaded_file.name}: {str(e)}")
        return redirect('tool_database_backup')

    # Case 2: Selected from existing backups list
    filename = request.POST.get('filename', '').strip()
    if filename:
        safe_name = os.path.basename(filename)
        target_path = get_academic_year_backup_dir() / safe_name
        if not target_path.exists():
            messages.error(request, f"រកមិនឃើញឯកសារ {safe_name} ឡើយ!")
            return redirect('tool_database_backup')
        try:
            res = restore_academic_year_backup(target_path, user_info=user_info)
            messages.success(request, res['message'])
        except Exception as e:
            messages.error(request, f"បរាជ័យក្នុងការ Restore ឆ្នាំសិក្សាពី {safe_name}: {str(e)}")
        return redirect('tool_database_backup')

    messages.error(request, "សូមជ្រើសរើសឯកសារ JSON ឬ Upload ឯកសារដើម្បី Restore!")
    return redirect('tool_database_backup')


# ==========================================
# GOOGLE SHEETS & DRIVE SYNC SUITE
# ==========================================

@login_required
@role_required(['ADMIN'])
def google_sheets_dashboard_view(request):
    """
    Main Google Sheets Sync, Backup & Restore Dashboard.
    """
    from apps.accounts.models import GoogleSheetsConfig
    from apps.academics.models import AcademicYear
    from apps.tools.google_sheets_service import GoogleSheetsService

    config = GoogleSheetsConfig.get_config()
    academic_years = AcademicYear.objects.all().order_by('-start_date')
    current_year = AcademicYear.objects.filter(is_current=True).first() or academic_years.first()
    spreadsheets_registry = config.spreadsheets_registry or {}

    years_data = []
    for ay in academic_years:
        reg = spreadsheets_registry.get(ay.name)
        years_data.append({
            'ay': ay,
            'reg': reg,
            'is_linked': bool(reg and reg.get('spreadsheet_id')),
            'spreadsheet_url': reg.get('spreadsheet_url') if reg else None,
            'spreadsheet_id': reg.get('spreadsheet_id') if reg else None,
            'updated_at': reg.get('updated_at') or reg.get('created_at') if reg else None,
        })

    return render(request, 'tools/google_sheets_dashboard.html', {
        'page_title': 'សមកាលកម្ម Google Sheets & Drive (Academic Sync & Backup)',
        'config': config,
        'client_email': config.client_email,
        'is_configured': config.is_configured(),
        'academic_years': academic_years,
        'years_data': years_data,
        'current_year': current_year,
        'spreadsheets_registry': spreadsheets_registry,
    })


@login_required
@role_required(['ADMIN'])
@require_POST
def api_save_google_sheets_config(request):
    """
    Saves Google Sheets credentials, admin email, and configuration.
    """
    from apps.accounts.models import GoogleSheetsConfig
    config = GoogleSheetsConfig.get_config()

    config.admin_email = request.POST.get('admin_email', '').strip()
    config.drive_folder_name = request.POST.get('drive_folder_name', 'SchoolSM_Cloud_Sync').strip()
    config.sync_students_with_photos = (request.POST.get('sync_students_with_photos') == 'on' or request.POST.get('sync_students_with_photos') == 'true')
    config.is_active = (request.POST.get('is_active') == 'on' or request.POST.get('is_active') == 'true')

    # Upload JSON file or paste JSON content
    credentials_file = request.FILES.get('credentials_file')
    if credentials_file:
        try:
            content = credentials_file.read().decode('utf-8')
            json.loads(content)
            config.service_account_json_content = content
        except Exception as e:
            messages.error(request, f"ឯកសារ Credentials JSON មិនត្រឹមត្រូវ: {e}")
            return redirect('tool_google_sheets')
    else:
        raw_json = request.POST.get('service_account_json_content', '').strip()
        if raw_json:
            try:
                json.loads(raw_json)
                config.service_account_json_content = raw_json
            except Exception as e:
                messages.error(request, f"ទម្រង់ JSON មិនត្រឹមត្រូវ: {e}")
                return redirect('tool_google_sheets')

    config.save()
    messages.success(request, "បានរក្សាទុកការកំណត់ Google Sheets ដោយជោគជ័យ!")
    return redirect('tool_google_sheets')


@login_required
@role_required(['ADMIN'])
@require_POST
def api_sync_google_sheets(request):
    """
    Triggers immediate synchronization to Google Sheets for selected Academic Year.
    """
    from apps.accounts.models import GoogleSheetsConfig
    from apps.academics.models import AcademicYear
    from apps.tools.google_sheets_service import GoogleSheetsService

    config = GoogleSheetsConfig.get_config()
    if not config.is_configured():
        msg = "សូមកំណត់ Google Service Account Credentials ជាមុនសិន។"
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': msg}, status=400)
        messages.error(request, msg)
        return redirect('tool_google_sheets')

    year_id = request.POST.get('academic_year_id')
    ay = None
    if year_id:
        ay = AcademicYear.objects.filter(id=year_id).first() or AcademicYear.objects.filter(name=year_id).first()
    if not ay:
        ay = AcademicYear.objects.filter(is_current=True).first() or AcademicYear.objects.order_by('-start_date').first()

    if not ay:
        msg = "រកមិនឃើញឆ្នាំសិក្សាដែលត្រូវ Sync ទេ។"
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': msg}, status=400)
        messages.error(request, msg)
        return redirect('tool_google_sheets')

    try:
        service = GoogleSheetsService(config=config)
        stats = service.sync_academic_year(ay)
        msg = (
            f"✅ បាន Sync ទៅ Google Sheets ឆ្នាំសិក្សា {ay.name} ដោយជោគជ័យ! "
            f"(សិស្ស {stats['students_synced']} នាក់, រូបថត {stats['photos_uploaded']}, "
            f"វត្តមាន {stats['attendance_synced']}, ចំណូល {stats['incomes_synced']}, ចំណាយ {stats['expenses_synced']})"
        )
        messages.success(request, msg)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'stats': stats, 'message': msg})
    except Exception as e:
        msg = f"បរាជ័យក្នុងការ Sync Google Sheets: {str(e)}"
        messages.error(request, msg)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': msg}, status=500)

    return redirect('tool_google_sheets')


@login_required
@role_required(['ADMIN'])
@require_POST
def api_restore_google_sheets(request):
    """
    Restores / re-imports data from Google Sheets back into system database.
    """
    from apps.accounts.models import GoogleSheetsConfig
    from apps.academics.models import AcademicYear
    from apps.tools.google_sheets_service import GoogleSheetsService

    config = GoogleSheetsConfig.get_config()
    year_id = request.POST.get('academic_year_id')
    ay = AcademicYear.objects.filter(id=year_id).first() or AcademicYear.objects.filter(name=year_id).first()
    if not ay:
        messages.error(request, "សូមជ្រើសរើសឆ្នាំសិក្សាដែលត្រូវ Restore។")
        return redirect('tool_google_sheets')

    try:
        service = GoogleSheetsService(config=config)
        results = service.restore_from_academic_spreadsheet(ay)
        msg = (
            f"🎉 បានទាញយក និងស្តារទិន្នន័យពី Google Sheets ឆ្នាំ {ay.name} រួចរាល់! "
            f"(សិស្សថ្មី {results['students_created']} នាក់, សិស្សចាស់ Update {results['students_restored']} នាក់, "
            f"ចំណាយ {results['expenses_restored']})"
        )
        messages.success(request, msg)
    except Exception as e:
        messages.error(request, f"បរាជ័យក្នុងការ Restore ពី Google Sheets: {str(e)}")

    return redirect('tool_google_sheets')


@login_required
@role_required(['ADMIN'])
@require_POST
def api_link_google_sheet(request):
    """
    Links a pre-created Google Spreadsheet (URL or ID) to a specific Academic Year.
    """
    from apps.accounts.models import GoogleSheetsConfig
    from apps.academics.models import AcademicYear
    from apps.tools.google_sheets_service import GoogleSheetsService

    config = GoogleSheetsConfig.get_config()
    if not config.is_configured():
        messages.error(request, "សូមកំណត់ Google Service Account Credentials ជាមុនសិន។")
        return redirect('tool_google_sheets')

    year_id = request.POST.get('academic_year_id')
    sheet_url = request.POST.get('sheet_url', '').strip()

    ay = AcademicYear.objects.filter(id=year_id).first() or AcademicYear.objects.filter(name=year_id).first()
    if not ay:
        messages.error(request, "រកមិនឃើញឆ្នាំសិក្សាដែលបានជ្រើសរើសឡើយ។")
        return redirect('tool_google_sheets')

    if not sheet_url:
        messages.error(request, "សូមបញ្ចូលតំណភ្ជាប់ (URL) ឬ ID របស់ Google Sheet។")
        return redirect('tool_google_sheets')

    try:
        service = GoogleSheetsService(config=config)
        sh = service.link_academic_spreadsheet(ay, sheet_url)
        messages.success(request, f"🎉 បានភ្ជាប់ Google Sheet «{sh.title}» ជាមួយឆ្នាំសិក្សា {ay.name} ដោយជោគជ័យ! លោកអ្នកអាចចុច Sync បានឥឡូវនេះ។")
    except Exception as e:
        messages.error(request, f"បរាជ័យក្នុងការភ្ជាប់ Google Sheet: {str(e)}")

    return redirect('tool_google_sheets')


@login_required
@role_required(['ADMIN'])
@require_POST
def api_unlink_google_sheet(request):
    """
    Unlinks a Google Spreadsheet from an Academic Year.
    """
    from apps.accounts.models import GoogleSheetsConfig
    from apps.academics.models import AcademicYear
    from apps.tools.google_sheets_service import GoogleSheetsService

    year_id = request.POST.get('academic_year_id')
    ay = AcademicYear.objects.filter(id=year_id).first() or AcademicYear.objects.filter(name=year_id).first()
    if ay:
        config = GoogleSheetsConfig.get_config()
        service = GoogleSheetsService(config=config)
        service.unlink_academic_spreadsheet(ay)
        messages.success(request, f"បានផ្តាច់ Google Sheet ចេញពីឆ្នាំសិក្សា {ay.name} រួចរាល់។")
    return redirect('tool_google_sheets')


# =====================================================================
# 📱 Mobile App & APK Builder Suite (SchoolSM Cross-Platform App)
# =====================================================================

import subprocess
import threading
import time
import zipfile
import shutil
import socket
from datetime import datetime
from django.urls import reverse

# Global state for asynchronous mobile app compilation
BUILD_STATE = {
    'status': 'idle',  # 'idle', 'building', 'success', 'error'
    'started_at': None,
    'finished_at': None,
    'logs': [],
    'error_message': None,
    'duration_seconds': 0,
}
_BUILD_LOCK = threading.Lock()


def _get_lan_ip():
    """Returns local LAN IP for local WiFi device access."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def find_flutter_executable():
    """Finds flutter.bat or flutter executable on Windows/Linux."""
    which_path = shutil.which('flutter')
    if which_path:
        return which_path
    common_paths = [
        r"C:\src\flutter\bin\flutter.bat",
        r"C:\src\flutter\bin\flutter",
        r"C:\flutter\bin\flutter.bat",
        r"C:\flutter\bin\flutter",
        r"e:\flutter\bin\flutter.bat",
        r"e:\flutter\bin\flutter",
        r"d:\flutter\bin\flutter.bat",
        r"d:\flutter\bin\flutter",
        os.path.expandvars(r"%LOCALAPPDATA%\flutter\bin\flutter.bat"),
    ]
    for p in common_paths:
        if os.path.exists(p):
            return p
    return None


def normalize_direct_download_url(url: str) -> str:
    """
    Converts Google Drive and Dropbox preview links to direct download links.
    - Google Drive:
        https://drive.google.com/file/d/<ID>/view?usp=sharing -> https://drive.google.com/uc?export=download&id=<ID>
        https://drive.google.com/open?id=<ID> -> https://drive.google.com/uc?export=download&id=<ID>
    - Dropbox:
        https://www.dropbox.com/s/.../app.apk?dl=0 -> ...?dl=1
    """
    if not url:
        return ""
    url = url.strip()

    # Google Drive file/d/ID or open?id=ID
    gd_match = re.search(r'drive\.google\.com/file/d/([a-zA-Z0-9_-]+)', url)
    if gd_match:
        file_id = gd_match.group(1)
        return f"https://drive.google.com/uc?export=download&id={file_id}"

    gd_open_match = re.search(r'drive\.google\.com/open\?id=([a-zA-Z0-9_-]+)', url)
    if gd_open_match:
        file_id = gd_open_match.group(1)
        return f"https://drive.google.com/uc?export=download&id={file_id}"

    # Dropbox ?dl=0 -> ?dl=1
    if 'dropbox.com' in url:
        if 'dl=0' in url:
            return url.replace('dl=0', 'dl=1')
        elif '?dl=1' not in url and '&dl=1' not in url:
            sep = '&' if '?' in url else '?'
            return f"{url}{sep}dl=1"

    return url


def _run_apk_build_thread():
    """Background worker compiling Flutter release APK on Local PC."""
    global BUILD_STATE
    with _BUILD_LOCK:
        BUILD_STATE['status'] = 'building'
        BUILD_STATE['started_at'] = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        BUILD_STATE['finished_at'] = None
        BUILD_STATE['error_message'] = None
        BUILD_STATE['logs'] = ["[*] Initializing Flutter Release APK compilation..."]
        start_time = time.time()

    env = os.environ.copy()
    
    # Configure JDK 17 if available
    jdk_path = r"C:\Program Files\Microsoft\jdk-17.0.20.101-hotspot"
    if os.path.exists(jdk_path):
        env['JAVA_HOME'] = jdk_path
        env['PATH'] = f"{jdk_path}\\bin;{env.get('PATH', '')}"

    # Configure Android SDK if available
    android_sdk = r"e:\AndroidSdk"
    if not os.path.exists(android_sdk):
        local_sdk = os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk")
        if os.path.exists(local_sdk):
            android_sdk = local_sdk

    if os.path.exists(android_sdk):
        env['ANDROID_HOME'] = android_sdk
        env['ANDROID_SDK_ROOT'] = android_sdk
        env['PATH'] = f"{android_sdk}\\platform-tools;{android_sdk}\\cmdline-tools\\latest\\bin;{env.get('PATH', '')}"

    # Configure Flutter in PATH
    flutter_bin = find_flutter_executable()
    if flutter_bin:
        flutter_dir = os.path.dirname(flutter_bin)
        env['PATH'] = f"{flutter_dir};{env.get('PATH', '')}"
    flutter_cmd = flutter_bin if flutter_bin else "flutter"

    mobile_dir = os.path.join(settings.BASE_DIR, 'schoolsm_mobile')
    pubspec = os.path.join(mobile_dir, 'pubspec.yaml')
    if not os.path.exists(pubspec):
        with _BUILD_LOCK:
            BUILD_STATE['status'] = 'error'
            BUILD_STATE['error_message'] = 'pubspec.yaml not found in schoolsm_mobile'
            BUILD_STATE['logs'].append(f"[ERROR] pubspec.yaml not found at {pubspec}")
        return

    try:
        with _BUILD_LOCK:
            BUILD_STATE['logs'].append("[*] Resolving Flutter packages (flutter pub get)...")

        proc_pub = subprocess.run(
            [flutter_cmd, "pub", "get"],
            cwd=mobile_dir,
            env=env,
            capture_output=True,
            text=True,
            shell=True
        )
        if proc_pub.returncode != 0:
            with _BUILD_LOCK:
                BUILD_STATE['status'] = 'error'
                BUILD_STATE['error_message'] = 'flutter pub get failed'
                BUILD_STATE['logs'].append(f"[ERROR] flutter pub get failed:\n{proc_pub.stderr}")
            return

        with _BUILD_LOCK:
            BUILD_STATE['logs'].append("[OK] Dependencies resolved successfully.")
            BUILD_STATE['logs'].append("[*] Compiling Release APK (flutter build apk --release)...")

        cmd = [
            flutter_cmd, "build", "apk", "--release",
            "--no-tree-shake-icons",
            "--android-skip-build-dependency-validation"
        ]
        proc_build = subprocess.Popen(
            cmd,
            cwd=mobile_dir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            shell=True
        )

        for line in proc_build.stdout:
            cleaned = line.strip()
            if cleaned:
                with _BUILD_LOCK:
                    BUILD_STATE['logs'].append(cleaned)
                    if len(BUILD_STATE['logs']) > 300:
                        BUILD_STATE['logs'] = BUILD_STATE['logs'][-300:]

        proc_build.wait()

        if proc_build.returncode == 0:
            output_apk = os.path.join(mobile_dir, 'build', 'app', 'outputs', 'flutter-apk', 'app-release.apk')
            dest_apk = os.path.join(settings.BASE_DIR, 'SchoolSM-Mobile.apk')
            if os.path.exists(output_apk):
                shutil.copy2(output_apk, dest_apk)
                with _BUILD_LOCK:
                    BUILD_STATE['logs'].append(f"[SUCCESS] APK copied to {dest_apk}")

            with _BUILD_LOCK:
                BUILD_STATE['status'] = 'success'
                BUILD_STATE['finished_at'] = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
                BUILD_STATE['duration_seconds'] = int(time.time() - start_time)
                BUILD_STATE['logs'].append(f"[DONE] Release APK built successfully in {BUILD_STATE['duration_seconds']}s!")
        else:
            with _BUILD_LOCK:
                BUILD_STATE['status'] = 'error'
                BUILD_STATE['finished_at'] = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
                BUILD_STATE['duration_seconds'] = int(time.time() - start_time)
                BUILD_STATE['error_message'] = f"Build failed with exit code {proc_build.returncode}"
                BUILD_STATE['logs'].append(f"[ERROR] Build process failed with code {proc_build.returncode}")
    except Exception as e:
        with _BUILD_LOCK:
            BUILD_STATE['status'] = 'error'
            BUILD_STATE['finished_at'] = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
            BUILD_STATE['duration_seconds'] = int(time.time() - start_time)
            BUILD_STATE['error_message'] = str(e)
            BUILD_STATE['logs'].append(f"[EXCEPTION] {str(e)}")


GITHUB_APK_URL = "https://github.com/vannakblue/SchoolSM/releases/download/latest/SchoolSM-Mobile.apk"
GITHUB_IPA_URL = "https://github.com/vannakblue/SchoolSM/releases/download/latest/SchoolSM-iOS.ipa"
GITHUB_ACTIONS_URL = "https://github.com/vannakblue/SchoolSM/actions/workflows/build_mobile_apps.yml"


@login_required
@role_required(['ADMIN'])
def tool_mobile_app_manager(request):
    """
    Web Dashboard for Mobile App & APK Builder:
    Trigger builds (Local 100%), manage Custom Cloud Storage, download APK, and share QR code.
    """
    apk_path = os.path.join(settings.BASE_DIR, 'SchoolSM-Mobile.apk')
    apk_exists = os.path.exists(apk_path)
    apk_size_mb = round(os.path.getsize(apk_path) / (1024 * 1024), 2) if apk_exists else 0
    apk_mtime = datetime.fromtimestamp(os.path.getmtime(apk_path)) if apk_exists else None

    # Calculate LAN download URL for phones on local Wi-Fi
    lan_ip = _get_lan_ip()
    host = request.get_host()
    port = host.split(':')[1] if ':' in host else '8000'
    lan_download_url = f"http://{lan_ip}:{port}{reverse('tool_download_mobile_apk')}"
    web_download_url = request.build_absolute_uri(reverse('tool_download_mobile_apk'))

    # Read Custom Cloud Storage Config
    cloud_config = get_mobile_download_config()
    custom_apk_url = cloud_config.get('custom_apk_url', '').strip()
    is_cloud_active = bool(custom_apk_url)

    # Effective download URL for user / QR display
    if is_cloud_active:
        effective_download_url = custom_apk_url
    else:
        effective_download_url = lan_download_url

    # Check Flutter availability on current server / local PC
    flutter_bin = find_flutter_executable()
    flutter_installed = bool(flutter_bin)
    flutter_version = "Flutter (ម៉ាស៊ីន Local ត្រៀមរួចរាល់ 100%)" if flutter_installed else "មិនទាន់ដំឡើង (Cloud Server)"
    
    with _BUILD_LOCK:
        current_build = dict(BUILD_STATE)

    return render(request, 'tools/mobile_app_manager.html', {
        'page_title': 'គ្រប់គ្រងកម្មវិធីទូរស័ព្ទ (SchoolSM Mobile App & APK Builder)',
        'apk_exists': apk_exists,
        'apk_size_mb': apk_size_mb,
        'apk_mtime': apk_mtime,
        'effective_download_url': effective_download_url,
        'lan_download_url': lan_download_url,
        'web_download_url': web_download_url,
        'is_cloud_active': is_cloud_active,
        'lan_ip': lan_ip,
        'flutter_version': flutter_version,
        'flutter_installed': flutter_installed,
        'github_apk_url': GITHUB_APK_URL,
        'github_ipa_url': GITHUB_IPA_URL,
        'github_actions_url': GITHUB_ACTIONS_URL,
        'build_state': current_build,
        'cloud_config': cloud_config,
    })


@login_required
@role_required(['ADMIN'])
@require_POST
def api_build_mobile_apk(request):
    """
    Triggers background compilation of Release APK on Local PC (100%).
    """
    if not find_flutter_executable():
        return JsonResponse({
            'status': 'error',
            'message': 'Cloud Server (ដូចជា Render.com) មិនមានដំឡើង Flutter SDK & Android SDK ឡើយ។ សូមចុចប្រើប្រាស់ Cloud Build តាម GitHub Actions ឬ Build លើ Local PC រួច Upload ឯកសារ APK មកវិញ។'
        }, status=400)

    global BUILD_STATE
    with _BUILD_LOCK:
        if BUILD_STATE['status'] == 'building':
            return JsonResponse({'status': 'already_running', 'message': 'ដំណើរការ Build កំពុងដំណើរការរួចហើយ។'}, status=400)

    t = threading.Thread(target=_run_apk_build_thread, daemon=True)
    t.start()
    return JsonResponse({'status': 'started', 'message': 'បានចាប់ផ្តើមដំណើរការ Build APK នៅ Background ដោយជោគជ័យ!'})


@login_required
@role_required(['ADMIN'])
@require_POST
def api_upload_mobile_apk(request):
    """
    Allows Admin to upload pre-built SchoolSM-Mobile.apk from local PC to Cloud Server.
    """
    if 'apk_file' not in request.FILES:
        messages.error(request, "សូមជ្រើសរើសឯកសារ .apk ជាមុនសិន។")
        return redirect('tool_mobile_app_manager')

    apk_file = request.FILES['apk_file']
    if not apk_file.name.lower().endswith('.apk'):
        messages.error(request, "ឯកសារដែលបានជ្រើសរើសមិនមែនជាប្រភេទ Android APK (.apk) ឡើយ។")
        return redirect('tool_mobile_app_manager')

    dest_path = os.path.join(settings.BASE_DIR, 'SchoolSM-Mobile.apk')
    with open(dest_path, 'wb+') as destination:
        for chunk in apk_file.chunks():
            destination.write(chunk)

    size_mb = round(os.path.getsize(dest_path) / (1024 * 1024), 2)
    messages.success(request, f"🎉 បាន Upload ឯកសារ SchoolSM-Mobile.apk ({size_mb} MB) ឡើងទៅកាន់ Server ដោយជោគជ័យ! អ្នកប្រើប្រាស់អាចទាញយក និងស្កេន QR Code បានឥឡូវនេះ។")
    return redirect('tool_mobile_app_manager')


@login_required
@role_required(['ADMIN'])
def api_mobile_build_status(request):
    """
    Returns real-time status and logs of APK compilation.
    """
    global BUILD_STATE
    with _BUILD_LOCK:
        data = dict(BUILD_STATE)

    apk_path = os.path.join(settings.BASE_DIR, 'SchoolSM-Mobile.apk')
    apk_exists = os.path.exists(apk_path)
    apk_size_mb = round(os.path.getsize(apk_path) / (1024 * 1024), 2) if apk_exists else 0
    apk_mtime_str = datetime.fromtimestamp(os.path.getmtime(apk_path)).strftime('%d/%m/%Y %I:%M %p') if apk_exists else None

    data['apk_exists'] = apk_exists
    data['apk_size_mb'] = apk_size_mb
    data['apk_mtime_str'] = apk_mtime_str
    return JsonResponse(data)


MOBILE_CONFIG_PATH = os.path.join(settings.BASE_DIR, 'mobile_download_config.json')


def get_mobile_download_config():
    """Reads custom cloud storage download links for APK & IPA."""
    if os.path.exists(MOBILE_CONFIG_PATH):
        try:
            with open(MOBILE_CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        'custom_apk_url': '',
        'custom_ipa_url': '',
    }


def save_mobile_download_config(data):
    """Writes custom cloud storage download links for APK & IPA."""
    with open(MOBILE_CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def tool_download_mobile_apk(request):
    """
    Direct download endpoint for SchoolSM-Mobile.apk.
    1. If Admin configured custom Cloud Storage URL (Google Drive, Dropbox, R2), redirect to it.
    2. If local file exists, serve it.
    3. Else fallback to GitHub Releases CDN.
    """
    cfg = get_mobile_download_config()
    if cfg.get('custom_apk_url'):
        return redirect(cfg['custom_apk_url'])

    apk_path = os.path.join(settings.BASE_DIR, 'SchoolSM-Mobile.apk')
    if os.path.exists(apk_path):
        response = FileResponse(open(apk_path, 'rb'), content_type='application/vnd.android.package-archive')
        response['Content-Disposition'] = 'attachment; filename="SchoolSM-Mobile.apk"'
        response['Content-Length'] = os.path.getsize(apk_path)
        return response

    fallback = os.path.join(settings.BASE_DIR, 'schoolsm_mobile', 'build', 'app', 'outputs', 'flutter-apk', 'app-release.apk')
    if os.path.exists(fallback):
        response = FileResponse(open(fallback, 'rb'), content_type='application/vnd.android.package-archive')
        response['Content-Disposition'] = 'attachment; filename="SchoolSM-Mobile.apk"'
        response['Content-Length'] = os.path.getsize(fallback)
        return response

    # If file not present on cloud server, redirect to GitHub Release CDN download
    return redirect(GITHUB_APK_URL)


def tool_download_mobile_ipa(request):
    """
    Direct download endpoint for SchoolSM-iOS.ipa.
    1. If Admin configured custom Cloud Storage URL, redirect to it.
    2. If local file exists, serve it.
    3. Else fallback to GitHub Releases CDN.
    """
    cfg = get_mobile_download_config()
    if cfg.get('custom_ipa_url'):
        return redirect(cfg['custom_ipa_url'])

    ipa_path = os.path.join(settings.BASE_DIR, 'SchoolSM-iOS.ipa')
    if os.path.exists(ipa_path):
        response = FileResponse(open(ipa_path, 'rb'), content_type='application/octet-stream')
        response['Content-Disposition'] = 'attachment; filename="SchoolSM-iOS.ipa"'
        return response

    fallback = os.path.join(settings.BASE_DIR, 'schoolsm_mobile', 'dist', 'SchoolSM-iOS.ipa')
    if os.path.exists(fallback):
        response = FileResponse(open(fallback, 'rb'), content_type='application/octet-stream')
        response['Content-Disposition'] = 'attachment; filename="SchoolSM-iOS.ipa"'
        return response

    return redirect(GITHUB_IPA_URL)


@login_required
@role_required(['ADMIN'])
@require_POST
def api_save_mobile_cloud_config(request):
    """
    Saves custom cloud download links (Google Drive, Dropbox, Cloudflare R2, AWS S3, etc.)
    Automatically normalizes share URLs to direct download URLs.
    """
    raw_apk_url = request.POST.get('custom_apk_url', '').strip()
    raw_ipa_url = request.POST.get('custom_ipa_url', '').strip()

    custom_apk_url = normalize_direct_download_url(raw_apk_url)
    custom_ipa_url = normalize_direct_download_url(raw_ipa_url)

    data = {
        'custom_apk_url': custom_apk_url,
        'custom_ipa_url': custom_ipa_url,
        'updated_at': timezone.now().strftime('%d/%m/%Y %I:%M %p'),
    }
    save_mobile_download_config(data)
    messages.success(request, "🎉 បានរក្សាទុកការកំណត់ Cloud Storage (Custom URLs) ដោយជោគជ័យ! អ្នកប្រើប្រាស់អាចស្កេន QR Code ឬចុចទាញយកបានភ្លាមៗ។")
    return redirect('tool_mobile_app_manager')


def tool_public_mobile_download(request):
    """
    Public download portal allowing any user (students, parents, teachers)
    to choose between Android (APK) and Apple iOS (IPA / PWA) download.
    """
    from apps.accounts.models import SchoolProfile
    school_profile = SchoolProfile.objects.first()
    cfg = get_mobile_download_config()

    lan_ip = _get_lan_ip()
    host = request.get_host()
    port = host.split(':')[1] if ':' in host else '8000'

    if '127.0.0.1' in host or 'localhost' in host:
        apk_download_url = f"http://{lan_ip}:{port}{reverse('tool_download_mobile_apk')}"
        ipa_download_url = f"http://{lan_ip}:{port}{reverse('tool_download_mobile_ipa')}"
    else:
        apk_download_url = request.build_absolute_uri(reverse('tool_download_mobile_apk'))
        ipa_download_url = request.build_absolute_uri(reverse('tool_download_mobile_ipa'))

    apk_path = os.path.join(settings.BASE_DIR, 'SchoolSM-Mobile.apk')
    apk_exists = os.path.exists(apk_path)
    apk_size_mb = round(os.path.getsize(apk_path) / (1024 * 1024), 2) if apk_exists else 67.6

    return render(request, 'tools/public_download.html', {
        'page_title': 'ទាញយកកម្មវិធីទូរស័ព្ទ (SchoolSM Mobile App - Android & iOS)',
        'school_profile': school_profile,
        'apk_download_url': apk_download_url,
        'ipa_download_url': ipa_download_url,
        'github_apk_url': GITHUB_APK_URL,
        'github_ipa_url': GITHUB_IPA_URL,
        'custom_apk_url': cfg.get('custom_apk_url', ''),
        'custom_ipa_url': cfg.get('custom_ipa_url', ''),
        'apk_size_mb': apk_size_mb,
    })


def tool_mobile_apk_qr(request):
    """
    Generates dynamic high-res QR code pointing to APK download.
    If Admin configured custom Cloud Storage (Google Drive, Dropbox, etc.),
    the QR code points directly to custom_apk_url so that ANY phone scanning it
    can download immediately from any network in the world!
    """
    import qrcode

    cfg = get_mobile_download_config()
    custom_apk_url = cfg.get('custom_apk_url', '').strip()

    if custom_apk_url:
        download_url = custom_apk_url
    else:
        lan_ip = _get_lan_ip()
        host = request.get_host()
        port = host.split(':')[1] if ':' in host else '8000'
        
        # If host is localhost, replace with LAN IP so phone can reach it
        if '127.0.0.1' in host or 'localhost' in host:
            download_url = f"http://{lan_ip}:{port}{reverse('tool_download_mobile_apk')}"
        else:
            download_url = request.build_absolute_uri(reverse('tool_download_mobile_apk'))

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=3,
    )
    qr.add_data(download_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")

    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return HttpResponse(buffer.getvalue(), content_type="image/png")


@login_required
@role_required(['ADMIN'])
def tool_export_ios_project(request):
    """
    Exports the Flutter iOS project source files as a ZIP archive for opening in Xcode.
    """
    mobile_dir = os.path.join(settings.BASE_DIR, 'schoolsm_mobile')
    if not os.path.exists(mobile_dir):
        raise Http404("រកមិនឃើញ Folder schoolsm_mobile ឡើយ។")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(mobile_dir):
            dirs[:] = [d for d in dirs if d not in ['.dart_tool', 'build', '.git', '.idea', 'android']]
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, settings.BASE_DIR)
                zf.write(file_path, arcname)

    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename="SchoolSM-Mobile-iOS-Xcode.zip"'
    return response


@login_required
@require_POST
def api_tool_ai_assist(request):
    """
    Unified AI Agent endpoint for all tools in SchoolSM Digital Tools Hub.
    Powered by Google Gemini 3.8 Flash with Dynamic Thinking Levels.
    """
    from .ai_service import ToolAiService

    try:
        data = json.loads(request.body)
    except Exception:
        data = request.POST

    tool_name = str(data.get('tool', '')).strip().lower()
    action = str(data.get('action', '')).strip().lower()
    content = str(data.get('content', '')).strip()
    options = data.get('options', {})
    if isinstance(options, str):
        try:
            options = json.loads(options)
        except Exception:
            options = {}

    thinking_level = str(data.get('thinking_level', '')).strip().lower()

    if not content and action not in ['quiz_wheel']:
        return JsonResponse({'status': 'error', 'message': 'សូមបញ្ចូល ឬជ្រើសរើសខ្លឹមសារជាមុនសិន!'}, status=400)

    res = ToolAiService.process_tool_ai(
        tool_name=tool_name,
        action=action,
        content=content,
        options=options,
        thinking_level=thinking_level,
        user=request.user
    )

    return JsonResponse(res)


