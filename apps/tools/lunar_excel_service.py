"""
Khmer Lunar Excel Service (សេវាបម្លែង និងទាញយកប្រតិទិនចន្ទគតិជា Excel)
Provides:
1. Dynamic Interactive Excel Converter Tool (.xlsx) with pre-configured lookup formulas
2. Monthly & Yearly Khmer Lunar Calendar Export (.xlsx)
3. Batch Excel Converter: Upload any Excel spreadsheet with dates -> appends lunar dates
"""

import io
import datetime
from typing import Optional, Union, List, Tuple
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from apps.accounts.khmer_lunar import calculate_khmer_lunar_details, get_khmer_lunar_date


# Color Palette Constants
COLOR_NAVY_DARK = "0F172A"       # Header background / Primary brand
COLOR_NAVY_LIGHT = "1E3A8A"      # Subheader / Accents
COLOR_GOLD = "F59E0B"            # Highlights / Badges
COLOR_GOLD_LIGHT = "FEFCE8"      # Holy day row fill
COLOR_GOLD_TEXT = "B45309"       # Holy day text
COLOR_WHITE = "FFFFFF"
COLOR_GRAY_LIGHT = "F8FAFC"      # Zebra striping
COLOR_BORDER = "E2E8F0"          # Thin borders
COLOR_INPUT_BG = "FEF9C3"        # Light yellow input cell
COLOR_RESULT_BG = "0F172A"       # Dark celestial card background
COLOR_RESULT_TEXT = "FEF08A"     # Glowing gold result text


def _get_styles():
    """Generates standard styles for openpyxl cells."""
    thin_border = Border(
        left=Side(style='thin', color='E2E8F0'),
        right=Side(style='thin', color='E2E8F0'),
        top=Side(style='thin', color='E2E8F0'),
        bottom=Side(style='thin', color='E2E8F0')
    )
    thick_bottom = Border(
        left=Side(style='thin', color='E2E8F0'),
        right=Side(style='thin', color='E2E8F0'),
        top=Side(style='thin', color='E2E8F0'),
        bottom=Side(style='medium', color='1E3A8A')
    )
    gold_border = Border(
        left=Side(style='thin', color='F59E0B'),
        right=Side(style='thin', color='F59E0B'),
        top=Side(style='thin', color='F59E0B'),
        bottom=Side(style='thin', color='F59E0B')
    )
    box_border = Border(
        left=Side(style='medium', color='CBD5E1'),
        right=Side(style='medium', color='CBD5E1'),
        top=Side(style='medium', color='CBD5E1'),
        bottom=Side(style='medium', color='CBD5E1')
    )

    return {
        'thin_border': thin_border,
        'thick_bottom': thick_bottom,
        'gold_border': gold_border,
        'box_border': box_border,
        'font_title': Font(name='Khmer OS Siemreap', size=16, bold=True, color='1E3A8A'),
        'font_subtitle': Font(name='Khmer OS Siemreap', size=10, italic=True, color='64748B'),
        'font_sec_head': Font(name='Khmer OS Siemreap', size=11, bold=True, color='FFFFFF'),
        'font_tbl_head': Font(name='Khmer OS Siemreap', size=10, bold=True, color='FFFFFF'),
        'font_data': Font(name='Khmer OS Siemreap', size=9.5, color='1E293B'),
        'font_data_bold': Font(name='Khmer OS Siemreap', size=9.5, bold=True, color='1E293B'),
        'font_holy': Font(name='Khmer OS Siemreap', size=9.5, bold=True, color='B45309'),
        'fill_navy_dark': PatternFill(start_color='0F172A', end_color='0F172A', fill_type='solid'),
        'fill_navy': PatternFill(start_color='1E3A8A', end_color='1E3A8A', fill_type='solid'),
        'fill_header_tbl': PatternFill(start_color='1E40AF', end_color='1E40AF', fill_type='solid'),
        'fill_gray': PatternFill(start_color='F8FAFC', end_color='F8FAFC', fill_type='solid'),
        'fill_holy': PatternFill(start_color='FEFCE8', end_color='FEFCE8', fill_type='solid'),
        'fill_input': PatternFill(start_color='FEF9C3', end_color='FEF9C3', fill_type='solid'),
        'fill_result': PatternFill(start_color='0F172A', end_color='0F172A', fill_type='solid'),
        'fill_validity': PatternFill(start_color='ECFDF5', end_color='ECFDF5', fill_type='solid'),
        'font_validity': Font(name='Khmer OS Siemreap', size=9.5, bold=True, color='047857'),
        'validity_border': Border(
            left=Side(style='thin', color='10B981'),
            right=Side(style='thin', color='10B981'),
            top=Side(style='thin', color='10B981'),
            bottom=Side(style='thin', color='10B981')
        ),
        'font_result': Font(name='Khmer OS Siemreap', size=14, bold=True, color='FEF08A'),
        'font_input': Font(name='Calibri', size=14, bold=True, color='1E3A8A'),
    }


def generate_dynamic_lunar_converter_excel(start_year: int = 1990, end_year: int = 2035,
                                          sample_date: Optional[str] = None) -> io.BytesIO:
    """
    Generates a high-end dynamic Excel workbook (.xlsx).
    Sheet 1: Interactive Converter (Formula-driven, instant auto-calculation on edit) + Batch Table.
             Prominently displays the configured validity range (start_year to end_year).
    Sheet 2: Comprehensive Lookup DB (Hidden from tabs per MoEYS standard user experience).
    """
    wb = openpyxl.Workbook()
    styles = _get_styles()

    # -------------------------------------------------------------
    # SHEET 1: Interactive Converter & Batch Table
    # -------------------------------------------------------------
    ws1 = wb.active
    ws1.title = "បម្លែងថ្ងៃខែចន្ទគតិ"
    ws1.views.sheetView[0].showGridLines = True

    # Column widths
    widths = {
        'A': 3, 'B': 6, 'C': 26, 'D': 42, 'E': 14,
        'F': 14, 'G': 15, 'H': 16, 'I': 14, 'J': 20, 'K': 18
    }
    for col, w in widths.items():
        ws1.column_dimensions[col].width = w

    # Title Banner (Row 2 & Row 3)
    ws1.merge_cells('B2:J2')
    ws1['B2'] = f"កម្មវិធីបម្លែងកាលបរិច្ឆេទសុរិយគតិ ទៅជាចន្ទគតិខ្មែរ (ឆ្នាំ {start_year} - {end_year})"
    ws1['B2'].font = styles['font_title']
    ws1['B2'].alignment = Alignment(horizontal='left', vertical='center')

    ws1.merge_cells('B3:J3')
    ws1['B3'] = "SchoolSM Digital Tools • វាយបញ្ចូលថ្ងៃខែឆ្នាំសុរិយគតិ រូបមន្តនឹងគណនាចេញថ្ងៃខែឆ្នាំចន្ទគតិដោយស្វ័យប្រវត្តិ"
    ws1['B3'].font = styles['font_subtitle']
    ws1['B3'].alignment = Alignment(horizontal='left', vertical='center')

    # Prominent Validity Range Banner (Row 4)
    total_years = end_year - start_year + 1
    ws1.merge_cells('B4:J4')
    ws1['B4'] = (
        f" 📅 សុពលភាពទិន្នន័យគាំទ្រ៖ ចាប់ពីឆ្នាំ {start_year} ដល់ឆ្នាំ {end_year} "
        f"(សរុប {total_years} ឆ្នាំ) • គាំទ្ររាល់កាលបរិច្ឆេទទាំងអស់ក្នុងចន្លោះឆ្នាំនេះ • គណនាស្វ័យប្រវត្ត ១០០%"
    )
    ws1['B4'].font = styles['font_validity']
    ws1['B4'].fill = styles['fill_validity']
    ws1['B4'].alignment = Alignment(horizontal='left', vertical='center')
    ws1['B4'].border = styles['validity_border']
    ws1.row_dimensions[4].height = 24

    # SECTION 1: Single Quick Converter
    ws1.merge_cells('B5:J5')
    ws1['B5'] = f" 🔍 ១. ប្រអប់បម្លែងកាលបរិច្ឆេទរហ័ស (សុពលភាព៖ ឆ្នាំ {start_year} ដល់ {end_year})"
    ws1['B5'].font = styles['font_sec_head']
    ws1['B5'].fill = styles['fill_navy']
    ws1['B5'].alignment = Alignment(horizontal='left', vertical='center')
    ws1.row_dimensions[5].height = 24

    # Date Input Label & Cell
    ws1['B6'] = "វាយបញ្ចូលថ្ងៃខែសុរិយគតិ៖"
    ws1['B6'].font = styles['font_data_bold']
    ws1['B6'].alignment = Alignment(horizontal='right', vertical='center')

    # Determine safe default sample date within valid range
    today = datetime.date.today()
    if not sample_date:
        if start_year <= today.year <= end_year:
            sample_date = today.strftime('%Y-%m-%d')
        else:
            sample_date = f"{start_year}-04-14"
    else:
        try:
            parsed_y = int(sample_date.split('-')[0])
            if not (start_year <= parsed_y <= end_year):
                sample_date = f"{start_year}-04-14"
        except (ValueError, IndexError):
            sample_date = f"{start_year}-04-14"

    ws1['C6'] = sample_date
    ws1['C6'].font = styles['font_input']
    ws1['C6'].fill = styles['fill_input']
    ws1['C6'].alignment = Alignment(horizontal='center', vertical='center')
    ws1['C6'].border = styles['box_border']
    ws1.row_dimensions[6].height = 28

    ws1['D6'] = f"← វាយកាលបរិច្ឆេទក្នុងចន្លោះឆ្នាំ {start_year} ដល់ {end_year} (ឧ. {sample_date} ឬ 11/09/2026)"
    ws1['D6'].font = Font(name='Khmer OS Siemreap', size=9.5, italic=True, color='64748B')
    ws1['D6'].alignment = Alignment(horizontal='left', vertical='center')

    # Main Hero Lunar Output Box (Merged C8:J9)
    ws1.merge_cells('B8:B9')
    ws1['B8'] = "លទ្ធផលចន្ទគតិ៖"
    ws1['B8'].font = styles['font_data_bold']
    ws1['B8'].alignment = Alignment(horizontal='right', vertical='center')

    ws1.merge_cells('C8:J9')
    # Formula links to Sheet 2
    ws1['C8'] = (
        '=IF(ISBLANK(C6),"",'
        'IFERROR(INDEX(ទិន្នន័យចន្ទគតិ_DB!E:E, MATCH(C6, ទិន្នន័យចន្ទគតិ_DB!A:A, 0)),'
        'IFERROR(INDEX(ទិន្នន័យចន្ទគតិ_DB!E:E, MATCH(TEXT(C6,"yyyy-mm-dd"), ទិន្នន័យចន្ទគតិ_DB!B:B, 0)),'
        'IFERROR(INDEX(ទិន្នន័យចន្ទគតិ_DB!E:E, MATCH(DATEVALUE(C6), ទិន្នន័យចន្ទគតិ_DB!A:A, 0)),'
        'IFERROR(INDEX(ទិន្នន័យចន្ទគតិ_DB!E:E, MATCH(TEXT(C6,"dd/mm/yyyy"), ទិន្នន័យចន្ទគតិ_DB!C:C, 0)),'
        f'"កាលបរិច្ឆេទក្រៅសុពលភាព (ត្រូវនៅចន្លោះឆ្នាំ {start_year} ដល់ {end_year})")))))'
    )
    ws1['C8'].font = styles['font_result']
    ws1['C8'].fill = styles['fill_result']
    ws1['C8'].alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    ws1['C8'].border = styles['box_border']
    ws1.row_dimensions[8].height = 22
    ws1.row_dimensions[9].height = 22

    # Sub-details
    ws1['B11'] = "ត្រូវនឹងកាលបរិច្ឆេទ៖"
    ws1['B11'].font = styles['font_data_bold']
    ws1['B11'].alignment = Alignment(horizontal='right', vertical='center')

    ws1.merge_cells('C11:F11')
    ws1['C11'] = (
        '=IF(ISBLANK(C6),"",'
        'IFERROR(INDEX(ទិន្នន័យចន្ទគតិ_DB!D:D, MATCH(C6, ទិន្នន័យចន្ទគតិ_DB!A:A, 0)),'
        'IFERROR(INDEX(ទិន្នន័យចន្ទគតិ_DB!D:D, MATCH(TEXT(C6,"yyyy-mm-dd"), ទិន្នន័យចន្ទគតិ_DB!B:B, 0)),'
        'IFERROR(INDEX(ទិន្នន័យចន្ទគតិ_DB!D:D, MATCH(DATEVALUE(C6), ទិន្នន័យចន្ទគតិ_DB!A:A, 0)),""))))'
    )
    ws1['C11'].font = styles['font_data_bold']
    ws1['C11'].alignment = Alignment(horizontal='left', vertical='center')

    ws1['G11'] = "ស្ថានភាពថ្ងៃសីល៖"
    ws1['G11'].font = styles['font_data_bold']
    ws1['G11'].alignment = Alignment(horizontal='right', vertical='center')

    ws1.merge_cells('H11:J11')
    ws1['H11'] = (
        '=IF(ISBLANK(C6),"",'
        'IFERROR(INDEX(ទិន្នន័យចន្ទគតិ_DB!L:L, MATCH(C6, ទិន្នន័យចន្ទគតិ_DB!A:A, 0)),'
        'IFERROR(INDEX(ទិន្នន័យចន្ទគតិ_DB!L:L, MATCH(TEXT(C6,"yyyy-mm-dd"), ទិន្នន័យចន្ទគតិ_DB!B:B, 0)),'
        'IFERROR(INDEX(ទិន្នន័យចន្ទគតិ_DB!L:L, MATCH(DATEVALUE(C6), ទិន្នន័យចន្ទគតិ_DB!A:A, 0)),""))))'
    )
    ws1['H11'].font = styles['font_holy']
    ws1['H11'].alignment = Alignment(horizontal='left', vertical='center')

    # Deconstructed Metric Badges Header
    ws1['C13'] = "ថ្ងៃនៃសប្តាហ៍"
    ws1['D13'] = "ដំណាក់កាលព្រះច័ន្ទ"
    ws1['E13'] = "ខែចន្ទគតិ"
    ws1['F13'] = "ឆ្នាំសត្វ"
    ws1['G13'] = "ស័ក"
    ws1['H13'] = "ពុទ្ធសករាជ"
    for col_l in ['C', 'D', 'E', 'F', 'G', 'H']:
        cell = ws1[f'{col_l}13']
        cell.font = Font(name='Khmer OS Siemreap', size=8.5, bold=True, color='475569')
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.fill = styles['fill_gray']
        cell.border = styles['thin_border']

    # Deconstructed Metric Formulas
    ws1['C14'] = '=IF(ISBLANK(C6),"",IFERROR(INDEX(ទិន្នន័យចន្ទគតិ_DB!F:F, MATCH(C6, ទិន្នន័យចន្ទគតិ_DB!A:A, 0)), IFERROR(INDEX(ទិន្នន័យចន្ទគតិ_DB!F:F, MATCH(TEXT(C6,"yyyy-mm-dd"), ទិន្នន័យចន្ទគតិ_DB!B:B, 0)), "")))'
    ws1['D14'] = '=IF(ISBLANK(C6),"",IFERROR(INDEX(ទិន្នន័យចន្ទគតិ_DB!G:G, MATCH(C6, ទិន្នន័យចន្ទគតិ_DB!A:A, 0)), IFERROR(INDEX(ទិន្នន័យចន្ទគតិ_DB!G:G, MATCH(TEXT(C6,"yyyy-mm-dd"), ទិន្នន័យចន្ទគតិ_DB!B:B, 0)), "")))'
    ws1['E14'] = '=IF(ISBLANK(C6),"",IFERROR(INDEX(ទិន្នន័យចន្ទគតិ_DB!H:H, MATCH(C6, ទិន្នន័យចន្ទគតិ_DB!A:A, 0)), IFERROR(INDEX(ទិន្នន័យចន្ទគតិ_DB!H:H, MATCH(TEXT(C6,"yyyy-mm-dd"), ទិន្នន័យចន្ទគតិ_DB!B:B, 0)), "")))'
    ws1['F14'] = '=IF(ISBLANK(C6),"",IFERROR(INDEX(ទិន្នន័យចន្ទគតិ_DB!I:I, MATCH(C6, ទិន្នន័យចន្ទគតិ_DB!A:A, 0)), IFERROR(INDEX(ទិន្នន័យចន្ទគតិ_DB!I:I, MATCH(TEXT(C6,"yyyy-mm-dd"), ទិន្នន័យចន្ទគតិ_DB!B:B, 0)), "")))'
    ws1['G14'] = '=IF(ISBLANK(C6),"",IFERROR(INDEX(ទិន្នន័យចន្ទគតិ_DB!J:J, MATCH(C6, ទិន្នន័យចន្ទគតិ_DB!A:A, 0)), IFERROR(INDEX(ទិន្នន័យចន្ទគតិ_DB!J:J, MATCH(TEXT(C6,"yyyy-mm-dd"), ទិន្នន័យចន្ទគតិ_DB!B:B, 0)), "")))'
    ws1['H14'] = '=IF(ISBLANK(C6),"",IFERROR(INDEX(ទិន្នន័យចន្ទគតិ_DB!K:K, MATCH(C6, ទិន្នន័យចន្ទគតិ_DB!A:A, 0)), IFERROR(INDEX(ទិន្នន័យចន្ទគតិ_DB!K:K, MATCH(TEXT(C6,"yyyy-mm-dd"), ទិន្នន័យចន្ទគតិ_DB!B:B, 0)), "")))'

    for col_l in ['C', 'D', 'E', 'F', 'G', 'H']:
        cell = ws1[f'{col_l}14']
        cell.font = styles['font_data_bold']
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = styles['thin_border']
    ws1.row_dimensions[14].height = 22

    # SECTION 2: Batch Table (Copy-paste multiple student/staff dates)
    ws1.merge_cells('B17:J17')
    ws1['B17'] = f" 📋 ២. តារាងបម្លែងកាលបរិច្ឆេទជាក្រុម (សុពលភាព៖ ឆ្នាំ {start_year} ដល់ {end_year})"
    ws1['B17'].font = styles['font_sec_head']
    ws1['B17'].fill = styles['fill_navy']
    ws1['B17'].alignment = Alignment(horizontal='left', vertical='center')
    ws1.row_dimensions[17].height = 24

    ws1.merge_cells('B18:J18')
    ws1['B18'] = f"💡 របៀបប្រើ៖ គ្រាន់តែ Copy & Paste បញ្ជីថ្ងៃខែឆ្នាំសុរិយគតិ (ចន្លោះឆ្នាំ {start_year} ដល់ {end_year}) ចូលក្នុងជួរឈរ C នោះព័ត៌មានចន្ទគតិទាំងអស់នឹងចេញស្វ័យប្រវត្តិ!"
    ws1['B18'].font = Font(name='Khmer OS Siemreap', size=9, italic=True, color='1E40AF')
    ws1['B18'].fill = PatternFill(start_color='EFF6FF', end_color='EFF6FF', fill_type='solid')
    ws1['B18'].alignment = Alignment(horizontal='left', vertical='center')

    # Batch Table Column Headers
    batch_headers = [
        ('B', 'ល.រ', 6),
        ('C', f'ថ្ងៃខែសុរិយគតិ ({start_year}-{end_year})', 26),
        ('D', 'កាលបរិច្ឆេទចន្ទគតិពេញលេញ (Full MoEYS)', 42),
        ('E', 'ថ្ងៃសីល (Holy Day)', 16),
        ('F', 'ថ្ងៃសប្តាហ៍', 13),
        ('G', 'ដំណាក់កាល', 13),
        ('H', 'ខែចន្ទគតិ', 14),
        ('I', 'ឆ្នាំសត្វ & ស័ក', 16),
        ('J', 'ពុទ្ធសករាជ', 14),
    ]

    for col_letter, h_text, w in batch_headers:
        c = ws1[f'{col_letter}20']
        c.value = h_text
        c.font = styles['font_tbl_head']
        c.fill = styles['fill_header_tbl']
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        c.border = styles['thick_bottom']

    ws1.row_dimensions[20].height = 26

    # Sample rows + Pre-configured formulas for 150 rows
    sample_candidates = [
        sample_date,
        f"{min(max(start_year, 2024), end_year)}-10-02", # Pchum Ben
        f"{min(max(start_year, 2026), end_year)}-04-14", # Khmer New Year
        f"{min(max(start_year, 2026), end_year)}-11-23", # Water Festival
        f"{min(max(start_year, 2025), end_year)}-05-11", # Visak Bochea
    ]
    sample_preset_dates = []
    for s_dt in sample_candidates:
        if s_dt not in sample_preset_dates:
            try:
                y = int(s_dt.split('-')[0])
                if start_year <= y <= end_year:
                    sample_preset_dates.append(s_dt)
            except Exception:
                pass

    for r_idx in range(21, 151):
        ws1[f'B{r_idx}'] = r_idx - 20
        ws1[f'B{r_idx}'].alignment = Alignment(horizontal='center', vertical='center')
        ws1[f'B{r_idx}'].font = styles['font_data']
        ws1[f'B{r_idx}'].border = styles['thin_border']

        # Pre-fill sample dates in first few rows
        if r_idx - 21 < len(sample_preset_dates):
            ws1[f'C{r_idx}'] = sample_preset_dates[r_idx - 21]
        else:
            ws1[f'C{r_idx}'] = None

        ws1[f'C{r_idx}'].font = Font(name='Calibri', size=10.5, bold=True, color='1E3A8A')
        ws1[f'C{r_idx}'].alignment = Alignment(horizontal='center', vertical='center')
        ws1[f'C{r_idx}'].border = styles['thin_border']
        ws1[f'C{r_idx}'].fill = styles['fill_input'] if r_idx - 20 <= 5 else PatternFill(fill_type=None)

        # Formulas for columns D through J
        ws1[f'D{r_idx}'] = (
            f'=IF(ISBLANK(C{r_idx}),"",'
            f'IFERROR(INDEX(ទិន្នន័យចន្ទគតិ_DB!E:E, MATCH(C{r_idx}, ទិន្នន័យចន្ទគតិ_DB!A:A, 0)),'
            f'IFERROR(INDEX(ទិន្នន័យចន្ទគតិ_DB!E:E, MATCH(TEXT(C{r_idx},"yyyy-mm-dd"), ទិន្នន័យចន្ទគតិ_DB!B:B, 0)),'
            f'IFERROR(INDEX(ទិន្នន័យចន្ទគតិ_DB!E:E, MATCH(DATEVALUE(C{r_idx}), ទិន្នន័យចន្ទគតិ_DB!A:A, 0)),""))))'
        )
        ws1[f'D{r_idx}'].font = styles['font_data_bold']
        ws1[f'D{r_idx}'].alignment = Alignment(horizontal='left', vertical='center')
        ws1[f'D{r_idx}'].border = styles['thin_border']

        ws1[f'E{r_idx}'] = (
            f'=IF(ISBLANK(C{r_idx}),"",'
            f'IFERROR(INDEX(ទិន្នន័យចន្ទគតិ_DB!L:L, MATCH(C{r_idx}, ទិន្នន័យចន្ទគតិ_DB!A:A, 0)),'
            f'IFERROR(INDEX(ទិន្នន័យចន្ទគតិ_DB!L:L, MATCH(TEXT(C{r_idx},"yyyy-mm-dd"), ទិន្នន័យចន្ទគតិ_DB!B:B, 0)),"")))'
        )
        ws1[f'E{r_idx}'].font = styles['font_holy']
        ws1[f'E{r_idx}'].alignment = Alignment(horizontal='center', vertical='center')
        ws1[f'E{r_idx}'].border = styles['thin_border']

        ws1[f'F{r_idx}'] = f'=IF(ISBLANK(C{r_idx}),"",IFERROR(INDEX(ទិន្នន័យចន្ទគតិ_DB!F:F, MATCH(C{r_idx}, ទិន្នន័យចន្ទគតិ_DB!A:A, 0)), IFERROR(INDEX(ទិន្នន័យចន្ទគតិ_DB!F:F, MATCH(TEXT(C{r_idx},"yyyy-mm-dd"), ទិន្នន័យចន្ទគតិ_DB!B:B, 0)), "")))'
        ws1[f'F{r_idx}'].font = styles['font_data']
        ws1[f'F{r_idx}'].alignment = Alignment(horizontal='center', vertical='center')
        ws1[f'F{r_idx}'].border = styles['thin_border']

        ws1[f'G{r_idx}'] = f'=IF(ISBLANK(C{r_idx}),"",IFERROR(INDEX(ទិន្នន័យចន្ទគតិ_DB!G:G, MATCH(C{r_idx}, ទិន្នន័យចន្ទគតិ_DB!A:A, 0)), IFERROR(INDEX(ទិន្នន័យចន្ទគតិ_DB!G:G, MATCH(TEXT(C{r_idx},"yyyy-mm-dd"), ទិន្នន័យចន្ទគតិ_DB!B:B, 0)), "")))'
        ws1[f'G{r_idx}'].font = styles['font_data']
        ws1[f'G{r_idx}'].alignment = Alignment(horizontal='center', vertical='center')
        ws1[f'G{r_idx}'].border = styles['thin_border']

        ws1[f'H{r_idx}'] = f'=IF(ISBLANK(C{r_idx}),"",IFERROR(INDEX(ទិន្នន័យចន្ទគតិ_DB!H:H, MATCH(C{r_idx}, ទិន្នន័យចន្ទគតិ_DB!A:A, 0)), IFERROR(INDEX(ទិន្នន័យចន្ទគតិ_DB!H:H, MATCH(TEXT(C{r_idx},"yyyy-mm-dd"), ទិន្នន័យចន្ទគតិ_DB!B:B, 0)), "")))'
        ws1[f'H{r_idx}'].font = styles['font_data']
        ws1[f'H{r_idx}'].alignment = Alignment(horizontal='center', vertical='center')
        ws1[f'H{r_idx}'].border = styles['thin_border']

        ws1[f'I{r_idx}'] = f'=IF(ISBLANK(C{r_idx}),"",IFERROR(INDEX(ទិន្នន័យចន្ទគតិ_DB!I:I, MATCH(C{r_idx}, ទិន្នន័យចន្ទគតិ_DB!A:A, 0)), IFERROR(INDEX(ទិន្នន័យចន្ទគតិ_DB!I:I, MATCH(TEXT(C{r_idx},"yyyy-mm-dd"), ទិន្នន័យចន្ទគតិ_DB!B:B, 0)), "")))'
        ws1[f'I{r_idx}'].font = styles['font_data']
        ws1[f'I{r_idx}'].alignment = Alignment(horizontal='center', vertical='center')
        ws1[f'I{r_idx}'].border = styles['thin_border']

        ws1[f'J{r_idx}'] = f'=IF(ISBLANK(C{r_idx}),"",IFERROR(INDEX(ទិន្នន័យចន្ទគតិ_DB!K:K, MATCH(C{r_idx}, ទិន្នន័យចន្ទគតិ_DB!A:A, 0)), IFERROR(INDEX(ទិន្នន័យចន្ទគតិ_DB!K:K, MATCH(TEXT(C{r_idx},"yyyy-mm-dd"), ទិន្នន័យចន្ទគតិ_DB!B:B, 0)), "")))'
        ws1[f'J{r_idx}'].font = styles['font_data']
        ws1[f'J{r_idx}'].alignment = Alignment(horizontal='center', vertical='center')
        ws1[f'J{r_idx}'].border = styles['thin_border']

        ws1.row_dimensions[r_idx].height = 20

    # -------------------------------------------------------------
    # SHEET 2: Pre-computed Lookup Database
    # -------------------------------------------------------------
    ws2 = wb.create_sheet(title="ទិន្នន័យចន្ទគតិ_DB")
    ws2.sheet_properties.tabColor = "64748B"
    ws2.sheet_state = 'hidden'  # Sheet hidden per user requirement

    db_headers = [
        "DateSerial", "DateISO", "DateDMY", "SolarFullKhmer",
        "LunarFullString", "DayOfWeek", "LunarDay", "LunarMonth",
        "ZodiacYear", "StemSak", "BuddhistEra", "HolyDayStatus", "DualDateString"
    ]
    ws2.append(db_headers)
    for col_num in range(1, len(db_headers) + 1):
        cell = ws2.cell(row=1, column=col_num)
        cell.font = Font(name='Calibri', size=9, bold=True, color='FFFFFF')
        cell.fill = PatternFill(start_color='334155', end_color='334155', fill_type='solid')

    start_d = datetime.date(start_year, 1, 1)
    end_d = datetime.date(end_year, 12, 31)
    delta_days = (end_d - start_d).days + 1

    # Batch append pre-computed rows
    batch_rows = []
    for i in range(delta_days):
        cur = start_d + datetime.timedelta(days=i)
        details = calculate_khmer_lunar_details(cur)

        batch_rows.append([
            cur, # A: Date serial (Excel Date)
            cur.strftime('%Y-%m-%d'), # B: ISO string
            cur.strftime('%d/%m/%Y'), # C: DMY string
            details['solar_full_kh'], # D
            details['full_string'], # E
            details['day_of_week'], # F
            details['lunar_day'], # G
            details['lunar_month'], # H
            f"{details['zodiac_full']} {details.get('zodiac_emoji', '')}", # I
            details['stem'], # J
            f"ព.ស. {details['buddhist_era_kh']}", # K
            details['holy_day_label'] if details['is_holy_day'] else 'ថ្ងៃធម្មតា', # L
            details.get('dual_date_string', '') # M
        ])

        # Write in chunks of 2000 for efficiency
        if len(batch_rows) >= 2000:
            for r in batch_rows:
                ws2.append(r)
            batch_rows = []

    if batch_rows:
        for r in batch_rows:
            ws2.append(r)

    # Format Date column A as Excel Date
    for row in range(2, ws2.max_row + 1):
        ws2[f'A{row}'].number_format = 'yyyy-mm-dd'

    # Auto-fit sheet 2 columns lightly
    for col in ws2.columns:
        col_letter = get_column_letter(col[0].column)
        ws2.column_dimensions[col_letter].width = 15

    # Return Excel binary
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def export_lunar_calendar_excel(year: int, month: Optional[int] = None) -> io.BytesIO:
    """
    Exports clean, printable, MoEYS-formatted Khmer Lunar Calendar (.xlsx)
    for an entire year or a specific month.
    """
    wb = openpyxl.Workbook()
    styles = _get_styles()

    months_kh = [
        'មករា (January)', 'កុម្ភៈ (February)', 'មីនា (March)', 'មេសា (April)',
        'ឧសភា (May)', 'មិថុនា (June)', 'កក្កដា (July)', 'សីហា (August)',
        'កញ្ញា (September)', 'តុលា (October)', 'វិច្ឆិកា (November)', 'ធ្នូ (December)'
    ]

    target_months = [month] if month else list(range(1, 13))

    for idx, m in enumerate(target_months):
        ws = wb.active if idx == 0 else wb.create_sheet()
        m_name_kh = months_kh[m - 1]
        ws.title = f"ខែ{m_name_kh.split()[0]} {year}"
        ws.views.sheetView[0].showGridLines = True

        # Header Title
        ws.merge_cells('A2:I2')
        ws['A2'] = f"ប្រតិទិនចន្ទគតិខ្មែរ - ខែ{m_name_kh} ឆ្នាំ{year}"
        ws['A2'].font = styles['font_title']
        ws['A2'].alignment = Alignment(horizontal='center', vertical='center')

        ws.merge_cells('A3:I3')
        ws['A3'] = f"ក្រសួងអប់រំ យុវជន និងកីឡា • ប្រព័ន្ធគ្រប់គ្រងសាលារៀន SchoolSM"
        ws['A3'].font = styles['font_subtitle']
        ws['A3'].alignment = Alignment(horizontal='center', vertical='center')

        # Headers
        cal_headers = [
            ('A', 'ល.រ', 6),
            ('B', 'កាលបរិច្ឆេទ (Solar)', 14),
            ('C', 'ថ្ងៃសប្តាហ៍', 13),
            ('D', 'កាលបរិច្ឆេទចន្ទគតិពេញលេញ (Khmer Lunar Date)', 42),
            ('E', 'ថ្ងៃកើត-រោច', 12),
            ('F', 'ខែចន្ទគតិ', 14),
            ('G', 'ឆ្នាំសត្វ & ស័ក', 16),
            ('H', 'ពុទ្ធសករាជ', 14),
            ('I', 'ថ្ងៃសីល & បុណ្យជាតិ', 24),
        ]

        for col_l, text, w in cal_headers:
            ws.column_dimensions[col_l].width = w
            cell = ws[f'{col_l}5']
            cell.value = text
            cell.font = styles['font_tbl_head']
            cell.fill = styles['fill_header_tbl']
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = styles['thick_bottom']

        ws.row_dimensions[5].height = 26

        # Days of Month
        first_d = datetime.date(year, m, 1)
        next_month_first = datetime.date(year + 1, 1, 1) if m == 12 else datetime.date(year, m + 1, 1)
        num_days = (next_month_first - first_d).days

        for day in range(1, num_days + 1):
            cur_date = datetime.date(year, m, day)
            details = calculate_khmer_lunar_details(cur_date)
            r = 5 + day

            is_holy = details['is_holy_day']
            row_fill = styles['fill_holy'] if is_holy else (styles['fill_gray'] if day % 2 == 0 else PatternFill(fill_type=None))

            ws[f'A{r}'] = day
            ws[f'A{r}'].alignment = Alignment(horizontal='center', vertical='center')

            ws[f'B{r}'] = cur_date.strftime('%Y-%m-%d')
            ws[f'B{r}'].alignment = Alignment(horizontal='center', vertical='center')

            ws[f'C{r}'] = details['day_of_week']
            ws[f'C{r}'].alignment = Alignment(horizontal='center', vertical='center')

            ws[f'D{r}'] = details['full_string']
            ws[f'D{r}'].alignment = Alignment(horizontal='left', vertical='center')

            ws[f'E{r}'] = details['lunar_day']
            ws[f'E{r}'].alignment = Alignment(horizontal='center', vertical='center')

            ws[f'F{r}'] = f"ខែ{details['lunar_month']}"
            ws[f'F{r}'].alignment = Alignment(horizontal='center', vertical='center')

            ws[f'G{r}'] = f"{details['zodiac_full']} {details['stem']}"
            ws[f'G{r}'].alignment = Alignment(horizontal='center', vertical='center')

            ws[f'H{r}'] = f"ព.ស. {details['buddhist_era_kh']}"
            ws[f'H{r}'].alignment = Alignment(horizontal='center', vertical='center')

            # Holy day indicator
            holy_str = details['holy_day_label'] if is_holy else ""
            ws[f'I{r}'] = f"☸️ {holy_str}" if is_holy else ""
            ws[f'I{r}'].alignment = Alignment(horizontal='center', vertical='center')

            for col_l, _, _ in cal_headers:
                c = ws[f'{col_l}{r}']
                c.border = styles['thin_border']
                c.fill = row_fill
                c.font = styles['font_holy'] if is_holy and col_l in ['D', 'E', 'I'] else styles['font_data']

            ws.row_dimensions[r].height = 20

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def batch_convert_uploaded_excel(file_bytes: bytes, date_col_idx: Optional[int] = None) -> io.BytesIO:
    """
    Takes an uploaded Excel spreadsheet, detects solar date column,
    inserts corresponding Khmer Lunar columns, and returns the modified workbook.
    """
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes))
    ws = wb.active
    styles = _get_styles()

    # Find the date column if not specified
    if date_col_idx is None:
        header_row = [str(cell.value or '').strip().lower() for cell in ws[1]]
        for idx, h in enumerate(header_row):
            if any(k in h for k in ['date', 'dob', 'ថ្ងៃខែ', 'កាលបរិច្ឆេទ', 'កំណើត']):
                date_col_idx = idx + 1
                break

    if date_col_idx is None:
        # Fallback to column 1 or first column with date-like values
        date_col_idx = 1
        for row in range(2, min(ws.max_row + 1, 10)):
            val = ws.cell(row=row, column=date_col_idx).value
            if isinstance(val, (datetime.date, datetime.datetime)):
                break

    # Insert 4 new columns after date_col_idx:
    # 1. កាលបរិច្ឆេទចន្ទគតិពេញលេញ
    # 2. ឆ្នាំសត្វ & ស័ក
    # 3. ពុទ្ធសករាជ
    # 4. ថ្ងៃសីល
    insert_at = date_col_idx + 1
    ws.insert_cols(insert_at, 4)

    # Headers for new columns
    new_headers = [
        "កាលបរិច្ឆេទចន្ទគតិ (Full Lunar)",
        "ឆ្នាំសត្វ & ស័ក",
        "ពុទ្ធសករាជ",
        "ថ្ងៃសីល"
    ]
    for i, h_text in enumerate(new_headers):
        cell = ws.cell(row=1, column=insert_at + i)
        cell.value = h_text
        cell.font = Font(name='Khmer OS Siemreap', size=10, bold=True, color='FFFFFF')
        cell.fill = styles['fill_header_tbl']
        cell.alignment = Alignment(horizontal='center', vertical='center')

    # Convert each row
    for row in range(2, ws.max_row + 1):
        date_val = ws.cell(row=row, column=date_col_idx).value
        if not date_val:
            continue

        try:
            details = calculate_khmer_lunar_details(date_val)
            ws.cell(row=row, column=insert_at, value=details['full_string'])
            ws.cell(row=row, column=insert_at + 1, value=f"{details['zodiac_full']} {details['stem']}")
            ws.cell(row=row, column=insert_at + 2, value=f"ព.ស. {details['buddhist_era_kh']}")
            ws.cell(row=row, column=insert_at + 3, value=details['holy_day_label'] if details['is_holy_day'] else '')

            for i in range(4):
                c = ws.cell(row=row, column=insert_at + i)
                c.font = styles['font_data']
                c.border = styles['thin_border']
        except Exception:
            pass

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output
