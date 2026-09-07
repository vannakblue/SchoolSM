"""
Google Sheets & Google Drive Integration Engine for SchoolSM:
- Syncs Students (with embedded photos via Google Drive), Attendance, Incomes, Expenses
- Organizes spreadsheets per Academic Year
- Admin-only privacy sharing
- Full Restore / Re-import capability back into database
"""
import os
import json
import logging
from datetime import datetime
from pathlib import Path
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from apps.accounts.models import GoogleSheetsConfig
from apps.academics.models import AcademicYear, Classroom
from apps.students.models import Student
from apps.attendance.models import StudentAttendance
from apps.finance.models import Invoice, PaymentTransaction, Expense, FeeCategory

logger = logging.getLogger(__name__)

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/drive.file'
]


class GoogleSheetsService:
    def __init__(self, config=None):
        self.config = config or GoogleSheetsConfig.get_config()
        self.client = None
        self.drive_service = None
        self._authenticated = False

    def authenticate(self):
        """Authenticates with Google using Service Account credentials."""
        if self._authenticated and self.client and self.drive_service:
            return True

        creds_dict = self.config.get_credentials_dict()
        if not creds_dict:
            raise ValueError(
                "មិនទាន់មាន Google Service Account Credentials នៅឡើយទេ។ "
                "សូមដាក់ឯកសារ google_service_account.json ឬបិទភ្ជាប់ខ្លឹមសារ JSON ក្នុងទំព័រការកំណត់។"
            )

        try:
            import gspread
            from google.oauth2.service_account import Credentials
            from googleapiclient.discovery import build

            credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
            self.client = gspread.authorize(credentials)
            self.drive_service = build('drive', 'v3', credentials=credentials)
            self._authenticated = True
            return True
        except Exception as e:
            logger.error(f"Google Sheets Authentication failed: {e}")
            raise RuntimeError(f"ការតភ្ជាប់ទៅកាន់ Google Cloud បរាជ័យ: {str(e)}")

    @staticmethod
    def extract_spreadsheet_id(sheet_url_or_id):
        """Extracts Google Spreadsheet ID from full URL or returns raw ID."""
        import re
        if not sheet_url_or_id:
            return None
        s = str(sheet_url_or_id).strip()
        m = re.search(r'/d/([a-zA-Z0-9-_]+)', s)
        if m:
            return m.group(1)
        if re.match(r'^[a-zA-Z0-9-_]{20,80}$', s):
            return s
        return None

    def get_or_create_drive_folder(self, folder_name, parent_id=None):
        """Finds or creates a folder on Google Drive. Gracefully returns None if quota exceeded."""
        self.authenticate()
        try:
            query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
            if parent_id:
                query += f" and '{parent_id}' in parents"

            results = self.drive_service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            files = results.get('files', [])

            if files:
                return files[0]['id']

            # Create folder
            folder_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            if parent_id:
                folder_metadata['parents'] = [parent_id]

            folder = self.drive_service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            folder_id = folder.get('id')

            # Share root folder with admin email if provided
            if not parent_id and self.config.admin_email:
                self.share_with_admin(folder_id)

            return folder_id
        except Exception as e:
            logger.warning(f"Could not get or create drive folder '{folder_name}' (possibly quota exceeded): {e}")
            return None

    def share_with_admin(self, file_or_folder_id):
        """Grants Editor access strictly to Admin Google Email (Admin Only)."""
        if not self.config.admin_email or not self.drive_service:
            return
        try:
            permission = {
                'type': 'user',
                'role': 'writer',
                'emailAddress': self.config.admin_email.strip(),
            }
            self.drive_service.permissions().create(
                fileId=file_or_folder_id,
                body=permission,
                fields='id',
                sendNotificationEmail=False
            ).execute()
        except Exception as e:
            logger.warning(f"Failed to share {file_or_folder_id} with {self.config.admin_email}: {e}")

    def upload_student_photo_to_drive(self, student, photo_folder_id):
        """
        Uploads student photo to Google Drive folder, generates =IMAGE() formula for Sheets,
        and saves Google Drive photo URL into student.photo_drive_url (relieving Web Database from storing image blobs).
        """
        import re

        # If student already has a Google Drive photo URL, reuse it directly
        if getattr(student, 'photo_drive_url', None) and 'id=' in student.photo_drive_url:
            m = re.search(r'id=([a-zA-Z0-9_-]+)', student.photo_drive_url)
            if m:
                file_id = m.group(1)
                thumbnail_url = f"https://drive.google.com/thumbnail?id={file_id}&sz=w400"
                view_url = f"https://drive.google.com/file/d/{file_id}/view"
                formula = f'=HYPERLINK("{view_url}", IMAGE("{thumbnail_url}", 1))'
                return file_id, formula

        if not photo_folder_id or not student.photo:
            return None, ""

        photo_path = student.photo.path if hasattr(student.photo, 'path') else None
        if not photo_path or not os.path.exists(photo_path):
            return None, ""

        self.authenticate()
        filename = f"PHOTO_{student.student_id or student.id}_{os.path.basename(photo_path)}"

        # Check if already exists in folder
        try:
            query = f"'{photo_folder_id}' in parents and name='{filename}' and trashed=false"
            res = self.drive_service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
            existing = res.get('files', [])
            if existing:
                file_id = existing[0]['id']
            else:
                from googleapiclient.http import MediaFileUpload
                file_metadata = {
                    'name': filename,
                    'parents': [photo_folder_id]
                }
                media = MediaFileUpload(photo_path, mimetype='image/jpeg', resumable=True)
                created_file = self.drive_service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id'
                ).execute()
                file_id = created_file.get('id')

                # Grant public reader permission for thumbnail preview in =IMAGE()
                try:
                    self.drive_service.permissions().create(
                        fileId=file_id,
                        body={'type': 'anyone', 'role': 'reader'},
                        fields='id'
                    ).execute()
                except Exception:
                    pass

            thumbnail_url = f"https://drive.google.com/thumbnail?id={file_id}&sz=w400"
            view_url = f"https://drive.google.com/file/d/{file_id}/view"
            formula = f'=HYPERLINK("{view_url}", IMAGE("{thumbnail_url}", 1))'

            # Store the Google Drive URL into student model in Web Database
            try:
                student.photo_drive_url = thumbnail_url
                student.save(update_fields=['photo_drive_url'])
            except Exception as se:
                logger.warning(f"Could not update photo_drive_url on student {student.id}: {se}")

            return file_id, formula
        except Exception as e:
            logger.warning(f"Error uploading photo for student {student.student_id}: {e}")
            return None, ""

    def get_or_create_academic_spreadsheet(self, academic_year):
        """
        Finds or creates a dedicated Google Spreadsheet for the specified Academic Year.
        """
        self.authenticate()
        year_name = academic_year.name if isinstance(academic_year, AcademicYear) else str(academic_year)
        sheet_title = f"[SchoolSM] ឆ្នាំសិក្សា {year_name}"

        master_folder_id = self.get_or_create_drive_folder(self.config.drive_folder_name or "SchoolSM_Cloud_Sync")
        if self.config.drive_folder_id != master_folder_id:
            self.config.drive_folder_id = master_folder_id
            self.config.save(update_fields=['drive_folder_id'])

        registry = self.config.spreadsheets_registry or {}
        year_entry = registry.get(year_name)

        if year_entry and year_entry.get('spreadsheet_id'):
            try:
                sh = self.client.open_by_key(year_entry['spreadsheet_id'])
                return sh, year_entry.get('photo_folder_id')
            except Exception:
                logger.info(f"Spreadsheet {year_entry['spreadsheet_id']} not found or accessible. Creating new.")

        # Create photo folder for this academic year if master folder exists
        photo_folder_id = None
        if master_folder_id:
            photo_folder_name = f"Photos_{year_name.replace(' ', '_').replace('/', '_')}"
            photo_folder_id = self.get_or_create_drive_folder(photo_folder_name, parent_id=master_folder_id)

        # Create new spreadsheet
        try:
            if master_folder_id:
                sh = self.client.create(sheet_title, folder_id=master_folder_id)
            else:
                sh = self.client.create(sheet_title)
        except Exception as e:
            err_str = str(e)
            if "quota" in err_str.lower() or "403" in err_str:
                client_email = self.config.client_email or "Google Service Account Email"
                raise RuntimeError(
                    f"Google Cloud Service Account គ្មានទំហំផ្ទុក Drive (0 MB Quota Exceeded) ដើម្បីបង្កើត File ដោយស្វ័យប្រវត្តិបានទេ។\n"
                    f"👉 វិធីដោះស្រាយងាយៗ៖\n"
                    f"១. បង្កើត Google Sheet មួយក្នុង Google Drive ({self.config.admin_email or 'Gmail'})\n"
                    f"២. ចុច Share ➔ បន្ថែម Email: {client_email} (សិទ្ធិ Editor) ឬកំណត់ 'Anyone with the link can edit'\n"
                    f"៣. Copy Link នៃ Sheet នោះ រួចមកចុចប៊ូតុង '🔗 ភ្ជាប់ Google Sheet' លើផ្ទាំង SchoolSM នេះជាការស្រេច!"
                )
            raise e

        # Admin Only permission
        if self.config.admin_email:
            self.share_with_admin(sh.id)

        # Update registry
        registry[year_name] = {
            'spreadsheet_id': sh.id,
            'spreadsheet_url': sh.url,
            'photo_folder_id': photo_folder_id,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'academic_year': year_name
        }
        self.config.spreadsheets_registry = registry
        self.config.save(update_fields=['spreadsheets_registry'])

        return sh, photo_folder_id

    def link_academic_spreadsheet(self, academic_year, sheet_url_or_id):
        """
        Manually links a pre-created Google Spreadsheet (owned by Admin's personal Google Drive)
        to an Academic Year. Validates access with gspread, records ID and URL in registry.
        """
        self.authenticate()
        sheet_id = self.extract_spreadsheet_id(sheet_url_or_id)
        if not sheet_id:
            raise ValueError("តំណភ្ជាប់ Google Sheet ឬ Spreadsheet ID មិនត្រឹមត្រូវឡើយ។")

        year_name = academic_year.name if isinstance(academic_year, AcademicYear) else str(academic_year)

        try:
            sh = self.client.open_by_key(sheet_id)
        except Exception as e:
            client_email = self.config.client_email or "Google Service Account Email"
            raise RuntimeError(
                f"មិនអាចបើក Google Sheet នេះបានឡើយ ({str(e)})! "
                f"សូមប្រាកដថាបានចុច Share ទៅកាន់ Email: {client_email} (សិទ្ធិ Editor) ឬបានកំណត់ General access ជា 'Anyone with the link can edit' រួចចុច Done។"
            )

        registry = self.config.spreadsheets_registry or {}
        existing_entry = registry.get(year_name, {})
        existing_photo_folder = existing_entry.get('photo_folder_id')

        registry[year_name] = {
            'spreadsheet_id': sh.id,
            'spreadsheet_url': sh.url,
            'title': sh.title,
            'photo_folder_id': existing_photo_folder,
            'linked_manually': True,
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'academic_year': year_name
        }
        self.config.spreadsheets_registry = registry
        self.config.save(update_fields=['spreadsheets_registry'])
        return sh

    def unlink_academic_spreadsheet(self, academic_year):
        """Unlinks the spreadsheet associated with an academic year."""
        year_name = academic_year.name if isinstance(academic_year, AcademicYear) else str(academic_year)
        registry = self.config.spreadsheets_registry or {}
        if year_name in registry:
            del registry[year_name]
            self.config.spreadsheets_registry = registry
            self.config.save(update_fields=['spreadsheets_registry'])
            return True
        return False

    def _prepare_worksheet(self, spreadsheet, title, headers, rows_count=1000):
        """Helper to get or create worksheet, write headers and style them."""
        try:
            ws = spreadsheet.worksheet(title)
            ws.clear()
        except Exception:
            ws = spreadsheet.add_worksheet(title=title, rows=rows_count, cols=len(headers) + 2)

        # Write headers
        ws.update([headers], 'A1')

        # Style header row (Navy blue background, white bold text, freeze header)
        try:
            ws.freeze(rows=1)
            last_col_letter = chr(64 + min(len(headers), 26)) if len(headers) <= 26 else 'Z'
            header_range = f"A1:{last_col_letter}1"
            ws.format(header_range, {
                "backgroundColor": {"red": 0.12, "green": 0.23, "blue": 0.54},
                "textFormat": {"foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}, "bold": True, "fontSize": 10},
                "horizontalAlignment": "CENTER"
            })
        except Exception as e:
            logger.warning(f"Could not style header: {e}")

        return ws

    def sync_academic_year(self, academic_year):
        """
        Synchronizes all data for a specific Academic Year:
        1. Students with Photos
        2. Attendance Logs
        3. Income & Payment Transactions
        4. Expenses
        5. Dashboard KPI Summary
        """
        self.authenticate()

        if isinstance(academic_year, (int, str)):
            ay = AcademicYear.objects.filter(id=academic_year).first() or AcademicYear.objects.filter(name=str(academic_year)).first()
            if not ay:
                raise ValueError(f"រកមិនឃើញឆ្នាំសិក្សា {academic_year} ទេ។")
        else:
            ay = academic_year

        sh, photo_folder_id = self.get_or_create_academic_spreadsheet(ay)

        stats = {
            'students_synced': 0,
            'attendance_synced': 0,
            'incomes_synced': 0,
            'expenses_synced': 0,
            'photos_uploaded': 0,
        }

        # -------------------------------------------------------------
        # 1. STUDENTS TAB
        # -------------------------------------------------------------
        student_headers = [
            "រូបថតសិស្ស (Photo)",
            "អត្តលេខ (Student ID)",
            "ឈ្មោះខ្មែរ (Khmer Name)",
            "ឈ្មោះឡាតាំង (Latin Name)",
            "ភេទ (Gender)",
            "ថ្ងៃខែឆ្នាំកំណើត (DOB)",
            "ថ្នាក់រៀន (Classroom)",
            "ស្ថានភាព (Status)",
            "ប្រភេទកម្រៃ (Fee/Scholarship)",
            "លេខទូរស័ព្ទ (Phone)",
            "ឈ្មោះឪពុក (Father)",
            "លេខទូរស័ព្ទឪពុក",
            "ឈ្មោះម្តាយ (Mother)",
            "លេខទូរស័ព្ទម្តាយ",
            "អាសយដ្ឋាន (Address)",
            "កាលបរិច្ឆេទចុះឈ្មោះ (Enroll Date)"
        ]
        ws_students = self._prepare_worksheet(sh, "📋 បញ្ជីសិស្ស (Students)", student_headers, rows_count=3000)

        # Enrolled students for this academic year
        students_qs = Student.objects.filter(academic_year=ay).select_related('classroom', 'category').order_by('classroom__name', 'student_id')
        student_rows = []

        for st in students_qs:
            photo_formula = ""
            if self.config.sync_students_with_photos and (st.photo or getattr(st, 'photo_drive_url', None)):
                file_id, photo_formula = self.upload_student_photo_to_drive(st, photo_folder_id)
                if file_id:
                    stats['photos_uploaded'] += 1

            gender_display = "ប្រុស" if st.gender == Student.Gender.MALE else "ស្រី"
            dob_str = st.date_of_birth.strftime('%d-%m-%Y') if st.date_of_birth else ""
            enroll_str = st.enrollment_date.strftime('%d-%m-%Y') if st.enrollment_date else ""

            row = [
                photo_formula or "",
                st.student_id or f"STU-{st.id}",
                st.khmer_name or "",
                st.latin_name or "",
                gender_display,
                dob_str,
                st.classroom.name if st.classroom else "មិនទាន់ចាត់ថ្នាក់",
                st.get_status_display(),
                st.scholarship_type or "បង់ពេញ",
                st.phone or "",
                st.father_name or "",
                st.father_phone or "",
                st.mother_name or "",
                st.mother_phone or "",
                st.current_address or "",
                enroll_str
            ]
            student_rows.append(row)

        if student_rows:
            ws_students.update(student_rows, f"A2:P{len(student_rows) + 1}", value_input_option='USER_ENTERED')
            stats['students_synced'] = len(student_rows)

        # -------------------------------------------------------------
        # 2. ATTENDANCE TAB
        # -------------------------------------------------------------
        attendance_headers = [
            "កាលបរិច្ឆេទ (Date)",
            "វេន (Session)",
            "ម៉ោងទី (Period)",
            "អត្តលេខ (Student ID)",
            "ឈ្មោះសិស្ស (Name)",
            "ថ្នាក់រៀន (Class)",
            "ស្ថានភាពវត្តមាន (Status)",
            "មូលហេតុ / កំណត់ចំណាំ (Reason/Notes)",
            "អ្នកកត់ត្រា (Recorded By)"
        ]
        ws_att = self._prepare_worksheet(sh, "📅 វត្តមាន (Attendance)", attendance_headers, rows_count=5000)

        # Attendance within the academic year dates
        att_base_qs = StudentAttendance.objects.filter(
            date__gte=ay.start_date,
            date__lte=ay.end_date
        )
        att_qs = att_base_qs.select_related('student', 'classroom', 'recorded_by').order_by('-date', 'classroom__name', 'student__khmer_name')[:4000]

        att_rows = []
        for att in att_qs:
            att_rows.append([
                att.date.strftime('%d-%m-%Y'),
                att.get_session_display(),
                f"ម៉ោងទី {att.period_number}" if att.period_number else "ពេញមួយវេន",
                att.student.student_id if att.student else "",
                att.student.khmer_name if att.student else "",
                att.classroom.name if att.classroom else "",
                att.get_status_display(),
                att.notes or "",
                att.recorded_by.display_name if (att.recorded_by and hasattr(att.recorded_by, 'display_name')) else (str(att.recorded_by) if att.recorded_by else "")
            ])

        if att_rows:
            ws_att.update(att_rows, f"A2:I{len(att_rows) + 1}", value_input_option='USER_ENTERED')
            stats['attendance_synced'] = len(att_rows)

        # -------------------------------------------------------------
        # 3. INCOME TAB
        # -------------------------------------------------------------
        income_headers = [
            "លេខវិក្កយបត្រ (Invoice No)",
            "លេខបង្កាន់ដៃ (Receipt No)",
            "កាលបរិច្ឆេទ (Payment Date)",
            "អត្តលេខ (Student ID)",
            "ឈ្មោះសិស្ស (Name)",
            "ថ្នាក់រៀន (Class)",
            "ប្រភេទកម្រៃ (Fee Category)",
            "តម្លៃដើម ($)",
            "បញ្ចុះតម្លៃ (%)",
            "ចំនួនប្រាក់បានបង់ ($)",
            "វិធីបង់ប្រាក់ (Payment Method)",
            "ស្ថានភាព (Status)",
            "អ្នកទទួលប្រាក់ (Cashier)"
        ]
        ws_inc = self._prepare_worksheet(sh, "💵 ចំណូល (Incomes)", income_headers, rows_count=3000)

        invoices = Invoice.objects.filter(academic_year=ay).select_related('student', 'fee_category').prefetch_related('payments')
        inc_rows = []
        for inv in invoices:
            payments = list(inv.payments.all())
            rec_numbers = ", ".join(p.receipt_number for p in payments if p.receipt_number) or "-"
            pay_methods = ", ".join(set(p.get_payment_method_display() for p in payments)) or "-"
            pay_date = payments[0].payment_date.strftime('%d-%m-%Y') if payments else inv.created_at.strftime('%d-%m-%Y')
            cashier = payments[0].received_by.display_name if (payments and payments[0].received_by and hasattr(payments[0].received_by, 'display_name')) else "-"

            inc_rows.append([
                inv.invoice_no,
                rec_numbers,
                pay_date,
                inv.student.student_id if inv.student else "",
                inv.student.khmer_name if inv.student else "",
                inv.student.classroom.name if (inv.student and inv.student.classroom) else "",
                inv.fee_category.name if inv.fee_category else "ទូទៅ",
                float(inv.original_amount),
                float(inv.discount_percent),
                float(inv.paid_amount),
                pay_methods,
                inv.get_status_display(),
                cashier
            ])

        if inc_rows:
            ws_inc.update(inc_rows, f"A2:M{len(inc_rows) + 1}", value_input_option='USER_ENTERED')
            stats['incomes_synced'] = len(inc_rows)

        # -------------------------------------------------------------
        # 4. EXPENSES TAB
        # -------------------------------------------------------------
        expense_headers = [
            "កាលបរិច្ឆេទ (Date)",
            "ចំណងជើងចំណាយ (Title)",
            "ប្រភេទចំណាយ (Category)",
            "ចំនួនទឹកប្រាក់ ($)",
            "អ្នកកត់ត្រា (Recorded By)",
            "កំណត់ចំណាំ (Notes)"
        ]
        ws_exp = self._prepare_worksheet(sh, "💸 ចំណាយ (Expenses)", expense_headers, rows_count=3000)

        expenses = Expense.objects.filter(
            date__gte=ay.start_date,
            date__lte=ay.end_date
        ).select_related('recorded_by').order_by('-date')

        exp_rows = []
        for exp in expenses:
            exp_rows.append([
                exp.date.strftime('%d-%m-%Y'),
                exp.title,
                exp.get_category_display(),
                float(exp.amount),
                exp.recorded_by.display_name if (exp.recorded_by and hasattr(exp.recorded_by, 'display_name')) else (str(exp.recorded_by) if exp.recorded_by else ""),
                exp.notes or ""
            ])

        if exp_rows:
            ws_exp.update(exp_rows, f"A2:F{len(exp_rows) + 1}", value_input_option='USER_ENTERED')
            stats['expenses_synced'] = len(exp_rows)

        # -------------------------------------------------------------
        # 5. EXAM SCORES TAB (ពិន្ទុ & លទ្ធផលប្រឡង)
        # -------------------------------------------------------------
        from apps.examinations.models import Grade
        exam_headers = [
            "សម័យប្រឡង (Exam Term)",
            "ថ្នាក់រៀន (Classroom)",
            "អត្តលេខ (Student ID)",
            "ឈ្មោះសិស្ស (Student Name)",
            "មុខវិជ្ជា (Subject)",
            "ពិន្ទុទទួលបាន (Score)",
            "ពិន្ទុពេញ (Max Score)",
            "និទ្ទេស (Grade)",
            "មតិយោបល់ (Remarks)"
        ]
        ws_scores = self._prepare_worksheet(sh, "📊 ពិន្ទុ & លទ្ធផលប្រឡង (Exam Scores)", exam_headers, rows_count=5000)

        grades_qs = Grade.objects.filter(exam_term__academic_year=ay).select_related(
            'student', 'subject', 'exam_term', 'classroom'
        ).order_by('exam_term__name', 'classroom__name', 'student__student_id', 'subject__name_kh')[:4000]

        score_rows = []
        for g in grades_qs:
            score_rows.append([
                g.exam_term.name if g.exam_term else "",
                g.classroom.name if g.classroom else (g.student.classroom.name if g.student and g.student.classroom else ""),
                g.student.student_id if g.student else "",
                g.student.khmer_name if g.student else "",
                g.subject.name_kh if (g.subject and hasattr(g.subject, 'name_kh') and g.subject.name_kh) else (g.subject.name if g.subject else ""),
                float(g.score),
                float(g.max_score),
                g.grade_letter or "",
                g.remarks or ""
            ])

        if score_rows:
            ws_scores.update(score_rows, f"A2:I{len(score_rows) + 1}", value_input_option='USER_ENTERED')
            stats['grades_synced'] = len(score_rows)
        else:
            stats['grades_synced'] = 0

        # -------------------------------------------------------------
        # 6. DASHBOARD SUMMARY TAB
        # -------------------------------------------------------------
        ws_summary = self._prepare_worksheet(sh, "📊 សង្ខេបស្ថិតិ (Summary)", ["សូចនាករគន្លឹះ (KPI Metric)", "តម្លៃ / ចំនួន (Value)", "កំណត់សម្គាល់ (Notes)"])
        
        total_students = students_qs.count()
        boys_count = students_qs.filter(gender=Student.Gender.MALE).count()
        girls_count = students_qs.filter(gender=Student.Gender.FEMALE).count()
        total_incomes = sum(float(inv.paid_amount) for inv in invoices)
        total_expenses = sum(float(exp.amount) for exp in expenses)
        net_balance = total_incomes - total_expenses
        total_attendance = att_base_qs.count()
        present_count = att_base_qs.filter(status=StudentAttendance.Status.PRESENT).count()
        att_rate = round((present_count / total_attendance * 100), 1) if total_attendance > 0 else 100.0

        summary_rows = [
            ["ឆ្នាំសិក្សា (Academic Year)", ay.name, f"{ay.start_date} ដល់ {ay.end_date}"],
            ["កាលបរិច្ឆេទធ្វើបច្ចុប្បន្នភាពចុងក្រោយ", datetime.now().strftime('%d-%m-%Y %H:%M:%S'), "Auto-synced by SchoolSM"],
            ["សរុបសិស្សទាំងអស់ (Total Students)", total_students, f"ប្រុស {boys_count} នាក់ / ស្រី {girls_count} នាក់"],
            ["សរុបពិន្ទុប្រឡង (Total Exam Grades)", stats['grades_synced'], "កំណត់ត្រាពិន្ទុ & លទ្ធផលប្រឡង"],
            ["សរុបចំណូលទទួលបាន (Total Collected)", f"${total_incomes:,.2f}", f"ពីវិក្កយបត្រ {len(invoices)} សន្លឹក"],
            ["សរុបចំណាយទូទៅ (Total Expenses)", f"${total_expenses:,.2f}", f"ពីប្រតិបត្តិការ {len(expenses)} លើក"],
            ["សមតុល្យសាច់ប្រាក់សុទ្ធ (Net Cash Balance)", f"${net_balance:,.2f}", "ចំណូល ដក ចំណាយ"],
            ["អត្រាវត្តមានទូទៅ (Attendance Rate)", f"{att_rate}%", f"ស្រង់បានសរុប {total_attendance} កំណត់ត្រា"],
        ]
        ws_summary.update(summary_rows, f"A2:C{len(summary_rows) + 1}", value_input_option='USER_ENTERED')

        # Remove default 'Sheet1' if it exists and other sheets were added
        try:
            default_sheet = sh.worksheet('Sheet1')
            sh.del_worksheet(default_sheet)
        except Exception:
            pass

        # Update registry timestamp
        registry = self.config.spreadsheets_registry or {}
        if ay.name in registry:
            registry[ay.name]['last_synced_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            registry[ay.name]['stats'] = stats
            self.config.spreadsheets_registry = registry

        self.config.last_sync_at = timezone.now()
        self.config.last_sync_status = "SUCCESS"
        self.config.last_sync_message = (
            f"បាន Sync ទិន្នន័យឆ្នាំសិក្សា {ay.name} ដោយជោគជ័យ៖ "
            f"សិស្ស {stats['students_synced']} នាក់ (រូបថត {stats['photos_uploaded']}), "
            f"ពិន្ទុ {stats['grades_synced']}, វត្តមាន {stats['attendance_synced']}, "
            f"ចំណូល {stats['incomes_synced']}, ចំណាយ {stats['expenses_synced']}."
        )
        self.config.save()

        stats['spreadsheet_url'] = sh.url
        stats['spreadsheet_id'] = sh.id
        return stats

    def restore_from_academic_spreadsheet(self, academic_year):
        """
        Restores / re-imports data from Google Sheets back into the SchoolSM database:
        1. Reads '📋 បញ្ជីសិស្ស (Students)' -> matches or creates Student
        2. Reads '💵 ចំណូល (Incomes)' -> matches or creates Invoices & Payments
        3. Reads '💸 ចំណាយ (Expenses)' -> matches or creates Expenses
        4. Reads '📅 វត្តមាន (Attendance)' -> matches or creates Attendance records
        """
        self.authenticate()

        if isinstance(academic_year, (int, str)):
            ay = AcademicYear.objects.filter(id=academic_year).first() or AcademicYear.objects.filter(name=str(academic_year)).first()
            if not ay:
                raise ValueError(f"រកមិនឃើញឆ្នាំសិក្សា {academic_year} ទេ។")
        else:
            ay = academic_year

        registry = self.config.spreadsheets_registry or {}
        year_entry = registry.get(ay.name)
        if not year_entry or not year_entry.get('spreadsheet_id'):
            raise ValueError(f"មិនទាន់មាន Google Spreadsheet សម្រាប់ឆ្នាំសិក្សា {ay.name} នៅឡើយទេ។")

        sh = self.client.open_by_key(year_entry['spreadsheet_id'])
        restore_stats = {
            'students_restored': 0,
            'students_created': 0,
            'attendance_restored': 0,
            'incomes_restored': 0,
            'expenses_restored': 0,
            'errors': []
        }

        # 1. RESTORE STUDENTS
        try:
            ws_students = sh.worksheet("📋 បញ្ជីសិស្ស (Students)")
            records = ws_students.get_all_values()
            if len(records) > 1:
                headers = records[0]
                rows = records[1:]
                for row in rows:
                    if len(row) < 3 or not row[1].strip():
                        continue
                    student_id = row[1].strip()
                    khmer_name = row[2].strip()
                    latin_name = row[3].strip() if len(row) > 3 else ""
                    gender_str = row[4].strip() if len(row) > 4 else "ប្រុស"
                    gender = Student.Gender.FEMALE if gender_str in ["ស្រី", "Female", "F"] else Student.Gender.MALE
                    dob_raw = row[5].strip() if len(row) > 5 else ""
                    classroom_name = row[6].strip() if len(row) > 6 else ""
                    phone = row[9].strip() if len(row) > 9 else ""
                    father_name = row[10].strip() if len(row) > 10 else ""
                    father_phone = row[11].strip() if len(row) > 11 else ""
                    mother_name = row[12].strip() if len(row) > 12 else ""
                    mother_phone = row[13].strip() if len(row) > 13 else ""
                    address = row[14].strip() if len(row) > 14 else ""

                    # Parse DOB
                    dob = None
                    for fmt in ('%d-%m-%Y', '%Y-%m-%d', '%d/%m/%Y'):
                        try:
                            dob = datetime.strptime(dob_raw, fmt).date()
                            break
                        except Exception:
                            pass
                    if not dob:
                        dob = datetime(2010, 1, 1).date()

                    # Classroom
                    classroom = None
                    if classroom_name and classroom_name != "មិនទាន់ចាត់ថ្នាក់":
                        classroom = Classroom.objects.filter(name__iexact=classroom_name).first()
                        if not classroom:
                            classroom = Classroom.objects.create(name=classroom_name, academic_year=ay)

                    # Extract Google Drive photo link from column 0 (does not download raw file to server disk)
                    photo_cell = row[0].strip() if len(row) > 0 else ""
                    drive_photo_url = ""
                    if photo_cell:
                        import re
                        m = re.search(r'https://drive\.google\.com/thumbnail\?id=[a-zA-Z0-9_-]+(&sz=[a-zA-Z0-9]+)?', photo_cell)
                        if m:
                            drive_photo_url = m.group(0)
                        else:
                            m_id = re.search(r'id=([a-zA-Z0-9_-]+)', photo_cell) or re.search(r'/d/([a-zA-Z0-9_-]+)', photo_cell)
                            if m_id:
                                drive_photo_url = f"https://drive.google.com/thumbnail?id={m_id.group(1)}&sz=w400"

                    student, created = Student.objects.get_or_create(
                        student_id=student_id,
                        defaults={
                            'khmer_name': khmer_name or "សិស្ស",
                            'latin_name': latin_name,
                            'gender': gender,
                            'date_of_birth': dob,
                            'academic_year': ay,
                            'classroom': classroom,
                            'phone': phone,
                            'father_name': father_name,
                            'father_phone': father_phone,
                            'mother_name': mother_name,
                            'mother_phone': mother_phone,
                            'current_address': address,
                            'photo_drive_url': drive_photo_url or None,
                        }
                    )
                    if created:
                        restore_stats['students_created'] += 1
                    else:
                        # Update existing
                        student.khmer_name = khmer_name or student.khmer_name
                        student.latin_name = latin_name or student.latin_name
                        student.classroom = classroom or student.classroom
                        student.academic_year = ay
                        if drive_photo_url and not student.photo_drive_url:
                            student.photo_drive_url = drive_photo_url
                        student.save()
                        restore_stats['students_restored'] += 1

        except Exception as e:
            restore_stats['errors'].append(f"Student restore warning: {e}")

        # 2. RESTORE EXPENSES
        try:
            ws_exp = sh.worksheet("💸 ចំណាយ (Expenses)")
            exp_records = ws_exp.get_all_values()
            if len(exp_records) > 1:
                for row in exp_records[1:]:
                    if len(row) < 4 or not row[1].strip():
                        continue
                    date_raw, title, cat_raw, amount_raw = row[0].strip(), row[1].strip(), row[2].strip(), row[3].strip()
                    exp_date = None
                    for fmt in ('%d-%m-%Y', '%Y-%m-%d', '%d/%m/%Y'):
                        try:
                            exp_date = datetime.strptime(date_raw, fmt).date()
                            break
                        except Exception:
                            pass
                    if not exp_date:
                        exp_date = datetime.now().date()

                    try:
                        clean_amt = amount_raw.replace('$', '').replace(',', '').strip()
                        amount = Decimal(clean_amt)
                    except Exception:
                        amount = Decimal('0.00')

                    if amount > 0:
                        exp_obj, created = Expense.objects.get_or_create(
                            title=title,
                            date=exp_date,
                            amount=amount,
                            defaults={'notes': row[5] if len(row) > 5 else ""}
                        )
                        if created:
                            restore_stats['expenses_restored'] += 1
        except Exception as e:
            restore_stats['errors'].append(f"Expense restore warning: {e}")

        # 3. RESTORE ATTENDANCE
        try:
            ws_att = sh.worksheet("📅 វត្តមាន (Attendance)")
            att_records = ws_att.get_all_values()
            if len(att_records) > 1:
                for row in att_records[1:]:
                    if len(row) < 7 or not row[0].strip() or not row[3].strip():
                        continue
                    date_raw = row[0].strip()
                    session_str = row[1].strip()
                    period_str = row[2].strip()
                    stu_id = row[3].strip()
                    class_name = row[5].strip() if len(row) > 5 else ""
                    status_str = row[6].strip() if len(row) > 6 else "វត្តមាន"
                    notes = row[7].strip() if len(row) > 7 else ""

                    att_date = None
                    for fmt in ('%d-%m-%Y', '%Y-%m-%d', '%d/%m/%Y'):
                        try:
                            att_date = datetime.strptime(date_raw, fmt).date()
                            break
                        except Exception:
                            pass
                    if not att_date:
                        continue

                    student = Student.objects.filter(student_id=stu_id).first()
                    if not student:
                        continue

                    classroom = None
                    if class_name:
                        classroom = Classroom.objects.filter(name__iexact=class_name).first()
                    if not classroom:
                        classroom = student.classroom

                    # Parse status
                    att_status = StudentAttendance.Status.PRESENT
                    if "អវត្តមានគ្មានច្បាប់" in status_str or "UNEXCUSED" in status_str.upper() or "ABSENT" in status_str.upper():
                        att_status = StudentAttendance.Status.ABSENT
                    elif "ច្បាប់" in status_str or "EXCUSED" in status_str.upper() or "PERMISSION" in status_str.upper():
                        att_status = StudentAttendance.Status.PERMISSION
                    elif "យឺត" in status_str or "LATE" in status_str.upper():
                        att_status = StudentAttendance.Status.LATE

                    # Parse session & period
                    session_val = StudentAttendance.Session.MORNING
                    if "រសៀល" in session_str or "AFTERNOON" in session_str.upper():
                        session_val = StudentAttendance.Session.AFTERNOON

                    import re
                    period_num = None
                    p_match = re.search(r'\d+', period_str)
                    if p_match:
                        period_num = int(p_match.group(0))

                    StudentAttendance.objects.update_or_create(
                        student=student,
                        date=att_date,
                        session=session_val,
                        period_number=period_num,
                        defaults={
                            'classroom': classroom,
                            'status': att_status,
                            'notes': notes
                        }
                    )
                    restore_stats['attendance_restored'] += 1
        except Exception as e:
            restore_stats['errors'].append(f"Attendance restore warning: {e}")

        # 4. RESTORE EXAM SCORES (GRADES)
        try:
            ws_scores = sh.worksheet("📊 ពិន្ទុ & លទ្ធផលប្រឡង (Exam Scores)")
            score_records = ws_scores.get_all_values()
            if len(score_records) > 1:
                from apps.examinations.models import ExamTerm, Grade
                from apps.academics.models import Subject
                for row in score_records[1:]:
                    if len(row) < 6 or not row[0].strip() or not row[2].strip() or not row[4].strip():
                        continue
                    term_name = row[0].strip()
                    classroom_name = row[1].strip() if len(row) > 1 else ""
                    student_id = row[2].strip()
                    subject_name = row[4].strip()
                    score_raw = row[5].strip()
                    max_score_raw = row[6].strip() if len(row) > 6 and row[6].strip() else "100"
                    remarks = row[8].strip() if len(row) > 8 else ""

                    try:
                        clean_score = str(score_raw).replace(',', '').strip()
                        clean_max = str(max_score_raw).replace(',', '').strip()
                        score_val = Decimal(clean_score)
                        max_score_val = Decimal(clean_max)
                    except Exception:
                        continue

                    student = Student.objects.filter(student_id=student_id).first()
                    if not student:
                        continue

                    exam_term = ExamTerm.objects.filter(name__iexact=term_name, academic_year=ay).first()
                    if not exam_term:
                        exam_term = ExamTerm.objects.filter(academic_year=ay).first()
                        if not exam_term:
                            continue

                    subject = Subject.objects.filter(name_kh__iexact=subject_name).first() or Subject.objects.filter(name__iexact=subject_name).first()
                    if not subject:
                        continue

                    classroom = None
                    if classroom_name:
                        classroom = Classroom.objects.filter(name__iexact=classroom_name).first()
                    if not classroom:
                        classroom = student.classroom

                    Grade.objects.update_or_create(
                        student=student,
                        subject=subject,
                        exam_term=exam_term,
                        defaults={
                            'classroom': classroom,
                            'score': score_val,
                            'max_score': max_score_val,
                            'remarks': remarks
                        }
                    )
                    restore_stats['grades_restored'] = restore_stats.get('grades_restored', 0) + 1
        except Exception as e:
            restore_stats['errors'].append(f"Exam scores restore warning: {e}")

        return restore_stats
