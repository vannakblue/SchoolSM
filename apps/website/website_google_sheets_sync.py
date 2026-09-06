"""
Two-Way Google Sheets Synchronization Engine for SchoolSM Website Portal:
- Syncs Announcements, News Articles, School Profile (About/Contact), and Contact Messages
- Bi-directional:
  * Push (Database -> Google Sheets)
  * Pull (Google Sheets -> Database)
  * Real-time Append for Contact Form inquiries
"""
import logging
from datetime import datetime
from django.utils import timezone
from django.conf import settings

from apps.accounts.models import GoogleSheetsConfig, SchoolProfile
from apps.extras.models import Announcement
from apps.website.models import NewsArticle, ContactMessage
from apps.tools.google_sheets_service import GoogleSheetsService

logger = logging.getLogger(__name__)


class WebsiteGoogleSheetsSync(GoogleSheetsService):
    """
    Handles two-way synchronization between SchoolSM Website CMS and Google Sheets.
    """
    REGISTRY_KEY = "website_portal"
    SPREADSHEET_TITLE = "[SchoolSM] គេហទំព័រសាលា - Website Portal Data"

    ANNOUNCEMENT_HEADERS = [
        "ID",
        "កាលបរិច្ឆេទ",
        "ចំណងជើង",
        "ប្រភេទ (Category)",
        "អ្នកទទួលដំណឹង (Audience)",
        "កម្រិតអាទិភាព",
        "ខ្លឹមសារ",
        "ផ្សាយជាសាធារណៈ (TRUE/FALSE)"
    ]

    NEWS_HEADERS = [
        "ID",
        "កាលបរិច្ឆេទ",
        "ចំណងជើង",
        "ប្រភេទ (Category)",
        "ខ្លឹមសារសង្ខេប",
        "ខ្លឹមសារពេញលេញ",
        "Link រូបភាព Cover",
        "អត្ថបទលេចធ្លោ (TRUE/FALSE)",
        "ផ្សាយជាសាធារណៈ (TRUE/FALSE)"
    ]

    PROFILE_HEADERS = [
        "កូដទិន្នន័យ (Field Key)",
        "ឈ្មោះទិន្នន័យ (Field Label)",
        "តម្លៃបច្ចុប្បន្ន (Current Value)",
        "ការពិពណ៌នា (Description)"
    ]

    CONTACT_HEADERS = [
        "ID",
        "កាលបរិច្ឆេទផ្ញើ",
        "ឈ្មោះអ្នកផ្ញើ",
        "លេខទូរស័ព្ទ",
        "អ៊ីមែល",
        "ប្រធានបទ",
        "ខ្លឹមសារសារ",
        "បានអាន (TRUE/FALSE)"
    ]

    def get_or_create_website_spreadsheet(self):
        """
        Retrieves existing website portal spreadsheet or creates a new one in the SchoolSM Drive folder.
        """
        self.authenticate()

        master_folder_id = self.get_or_create_drive_folder(self.config.drive_folder_name or "SchoolSM_Cloud_Sync")
        if self.config.drive_folder_id != master_folder_id:
            self.config.drive_folder_id = master_folder_id
            self.config.save(update_fields=['drive_folder_id'])

        registry = self.config.spreadsheets_registry or {}
        entry = registry.get(self.REGISTRY_KEY)

        if entry and entry.get('spreadsheet_id'):
            try:
                sh = self.client.open_by_key(entry['spreadsheet_id'])
                return sh
            except Exception as e:
                logger.info(f"Website portal spreadsheet not accessible ({e}), creating a fresh one.")

        # Create new spreadsheet
        try:
            if master_folder_id:
                sh = self.client.create(self.SPREADSHEET_TITLE, folder_id=master_folder_id)
            else:
                sh = self.client.create(self.SPREADSHEET_TITLE)
        except Exception as e:
            err_str = str(e)
            if "quota" in err_str.lower() or "403" in err_str:
                client_email = self.config.client_email or "Google Service Account Email"
                raise RuntimeError(
                    f"Google Cloud Service Account គ្មានទំហំផ្ទុក Drive (0 MB Quota Exceeded) ដើម្បីបង្កើត File ដោយស្វ័យប្រវត្តិបានទេ។\n"
                    f"👉 ដំណោះស្រាយងាយៗ៖\n"
                    f"១. បង្កើត Google Sheet មួយក្នុង Google Drive ({self.config.admin_email or 'Gmail'})\n"
                    f"២. ចុច Share ➔ បន្ថែម Email: {client_email} (សិទ្ធិ Editor) ឬកំណត់ 'Anyone with the link can edit'\n"
                    f"៣. Copy Link នៃ Sheet នោះ រួចមកចុចប៊ូតុង '🔗 ភ្ជាប់ Google Sheet' លើផ្ទាំង Website Sync នេះជាការស្រេច!"
                )
            raise e

        # Admin Only sharing
        if self.config.admin_email:
            self.share_with_admin(sh.id)

        # Update registry
        registry[self.REGISTRY_KEY] = {
            'spreadsheet_id': sh.id,
            'spreadsheet_url': sh.url,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'title': self.SPREADSHEET_TITLE
        }
        self.config.spreadsheets_registry = registry
        self.config.save(update_fields=['spreadsheets_registry'])

        return sh

    def link_spreadsheet(self, sheet_url_or_id):
        """Links a pre-existing Google Spreadsheet to Website Portal."""
        self.authenticate()
        sheet_id = self.extract_spreadsheet_id(sheet_url_or_id)
        if not sheet_id:
            raise ValueError("តំណភ្ជាប់ Google Sheet ឬ Spreadsheet ID មិនត្រឹមត្រូវឡើយ។")

        try:
            sh = self.client.open_by_key(sheet_id)
        except Exception as e:
            client_email = self.config.client_email or "Google Service Account Email"
            raise RuntimeError(
                f"មិនអាចបើក Google Sheet នេះបានឡើយ ({str(e)})! "
                f"សូមប្រាកដថាបានចុច Share ទៅកាន់ Email: {client_email} (សិទ្ធិ Editor) ឬបានកំណត់ General access ជា 'Anyone with the link can edit' រួចចុច Done។"
            )

        registry = self.config.spreadsheets_registry or {}
        registry[self.REGISTRY_KEY] = {
            'spreadsheet_id': sh.id,
            'spreadsheet_url': sh.url,
            'title': sh.title,
            'linked_manually': True,
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        self.config.spreadsheets_registry = registry
        self.config.save(update_fields=['spreadsheets_registry'])
        return sh

    def unlink_spreadsheet(self):
        """Unlinks the spreadsheet from Website Portal."""
        registry = self.config.spreadsheets_registry or {}
        if self.REGISTRY_KEY in registry:
            del registry[self.REGISTRY_KEY]
            self.config.spreadsheets_registry = registry
            self.config.save(update_fields=['spreadsheets_registry'])
            return True
        return False

    def get_spreadsheet_info(self):
        """Returns dict containing spreadsheet id, url, last_sync_at, or None."""
        registry = self.config.spreadsheets_registry or {}
        entry = registry.get(self.REGISTRY_KEY)
        return entry

    # =========================================================================
    # 📤 PUSH (Database -> Google Sheets)
    # =========================================================================
    def push_to_sheets(self):
        """
        Exports all website data (Announcements, News, Profile, Contacts) to Google Sheets.
        """
        sh = self.get_or_create_website_spreadsheet()

        # 1. Announcements Sheet
        ws_ann = self._prepare_worksheet(sh, "Announcements", self.ANNOUNCEMENT_HEADERS)
        ann_qs = Announcement.objects.all().order_by('-created_at')
        ann_rows = []
        for a in ann_qs:
            dt_str = a.created_at.strftime('%Y-%m-%d %H:%M') if a.created_at else ''
            ann_rows.append([
                a.id,
                dt_str,
                a.title,
                a.category,
                a.target_audience,
                a.priority,
                a.content,
                "TRUE" if a.is_published else "FALSE"
            ])
        if ann_rows:
            ws_ann.update(ann_rows, f'A2:H{len(ann_rows) + 1}')

        # 2. News Sheet
        ws_news = self._prepare_worksheet(sh, "News", self.NEWS_HEADERS)
        news_qs = NewsArticle.objects.all().order_by('-created_at')
        news_rows = []
        for n in news_qs:
            dt_str = n.created_at.strftime('%Y-%m-%d %H:%M') if n.created_at else ''
            cover_url = n.cover_image.url if n.cover_image and hasattr(n.cover_image, 'url') else ''
            news_rows.append([
                n.id,
                dt_str,
                n.title,
                n.category,
                n.excerpt or '',
                n.content,
                cover_url,
                "TRUE" if n.is_featured else "FALSE",
                "TRUE" if n.is_published else "FALSE"
            ])
        if news_rows:
            ws_news.update(news_rows, f'A2:I{len(news_rows) + 1}')

        # 3. School Profile Sheet
        ws_profile = self._prepare_worksheet(sh, "School_Profile", self.PROFILE_HEADERS)
        p = SchoolProfile.get_settings()
        profile_fields = [
            ("name_kh", "ឈ្មោះសាលា (ខ្មែរ)", getattr(p, "name_kh", "") or "", "ឈ្មោះផ្លូវការជាភាសាខ្មែរ"),
            ("name_en", "ឈ្មោះសាលា (English)", getattr(p, "name_en", "") or "", "ឈ្មោះផ្លូវការជាភាសាអង់គ្លេស"),
            ("short_name", "ឈ្មោះកាត់សាលា", getattr(p, "short_name", "") or "", "ឈ្មោះសម្រាប់បង្ហាញលើ Header"),
            ("school_code", "លេខកូដសាលា (EMIS)", getattr(p, "school_code", "") or "", "លេខកូដសម្គាល់គ្រឹះស្ថានអប់រំ"),
            ("school_type", "កម្រិត/ប្រភេទសាលា", getattr(p, "school_type", "") or "", "ឧទាហរណ៍៖ វិទ្យាល័យ / General High School"),
            ("motto", "បាវចនាសាលា", getattr(p, "motto", "") or "", "បាវចនា ឬពាក្យស្លោករបស់សាលា"),
            ("principal_name", "ឈ្មោះនាយកសាលា", getattr(p, "principal_name", "") or "", "ឈ្មោះថ្នាក់ដឹកនាំសាលា"),
            ("phone", "លេខទូរស័ព្ទផ្លូវការ", getattr(p, "phone", "") or "", "លេខទូរស័ព្ទទំនាក់ទំនងទូទៅ"),
            ("email", "អ៊ីមែលផ្លូវការ", getattr(p, "email", "") or "", "អ៊ីមែលទាក់ទងផ្លូវការ"),
            ("website", "អាសយដ្ឋានគេហទំព័រ", getattr(p, "website", "") or "", "Domain URL"),
            ("facebook_page", "ទំព័រហ្វេសប៊ុក (Facebook)", getattr(p, "facebook_page", "") or "", "Facebook Link"),
            ("telegram_channel", "Telegram Channel", getattr(p, "telegram_channel", "") or "", "Telegram Channel Link"),
            ("street_address", "អាសយដ្ឋានផ្លូវ", getattr(p, "street_address", "") or "", "លេខផ្ទះ/ផ្លូវ"),
            ("village", "ភូមិ", getattr(p, "village", "") or "", "ភូមិ"),
            ("commune", "ឃុំ/សង្កាត់", getattr(p, "commune", "") or "", "ឃុំ ឬសង្កាត់"),
            ("district", "ស្រុក/ខណ្ឌ", getattr(p, "district", "") or "", "ស្រុក ខណ្ឌ ឬក្រុង"),
            ("province", "រាជធានី/ខេត្ត", getattr(p, "province", "") or "", "រាជធានី ឬខេត្ត"),
        ]
        profile_rows = [[k, label, val, desc] for k, label, val, desc in profile_fields]
        ws_profile.update(profile_rows, f'A2:D{len(profile_rows) + 1}')

        # 4. Contact Messages Sheet
        ws_contact = self._prepare_worksheet(sh, "Contact_Messages", self.CONTACT_HEADERS)
        contact_qs = ContactMessage.objects.all().order_by('-created_at')
        contact_rows = []
        for c in contact_qs:
            dt_str = c.created_at.strftime('%Y-%m-%d %H:%M') if c.created_at else ''
            contact_rows.append([
                c.id,
                dt_str,
                c.name,
                c.phone,
                c.email or '',
                c.subject,
                c.message,
                "TRUE" if c.is_read else "FALSE"
            ])
        if contact_rows:
            ws_contact.update(contact_rows, f'A2:H{len(contact_rows) + 1}')

        # Update registry timestamp
        registry = self.config.spreadsheets_registry or {}
        if self.REGISTRY_KEY in registry:
            registry[self.REGISTRY_KEY]['last_sync_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.config.spreadsheets_registry = registry
            self.config.save(update_fields=['spreadsheets_registry'])

        return {
            'status': 'success',
            'announcements_count': len(ann_rows),
            'news_count': len(news_rows),
            'profile_fields_count': len(profile_rows),
            'contact_messages_count': len(contact_rows),
            'spreadsheet_url': sh.url,
            'spreadsheet_title': sh.title,
        }

    # =========================================================================
    # 📥 PULL (Google Sheets -> Database)
    # =========================================================================
    def pull_from_sheets(self):
        """
        Imports changes from Google Sheets into the Django database:
        - If row has an ID: updates the record.
        - If row has NO ID (new row in Sheet): creates a new record and writes the new ID back to the Sheet!
        """
        sh = self.get_or_create_website_spreadsheet()
        summary = {
            'announcements_created': 0,
            'announcements_updated': 0,
            'news_created': 0,
            'news_updated': 0,
            'profile_updated': False,
            'contact_updated': 0,
        }

        # 1. Pull Announcements
        try:
            ws_ann = sh.worksheet("Announcements")
            ann_records = ws_ann.get_all_values()
            if len(ann_records) > 1:
                new_id_updates = []
                for row_idx, row in enumerate(ann_records[1:], start=2):
                    if not row or not any(row):
                        continue
                    row_id = row[0].strip() if len(row) > 0 else ""
                    title = row[2].strip() if len(row) > 2 else ""
                    if not title:
                        continue
                    cat = row[3].strip() if len(row) > 3 and row[3].strip() else "GENERAL"
                    aud = row[4].strip() if len(row) > 4 and row[4].strip() else "ALL"
                    pri = row[5].strip() if len(row) > 5 and row[5].strip() else "NORMAL"
                    content = row[6].strip() if len(row) > 6 else ""
                    pub_str = row[7].strip().upper() if len(row) > 7 else "TRUE"
                    is_published = pub_str in ["TRUE", "1", "YES", "ពិត"]

                    if row_id and row_id.isdigit():
                        # Update existing
                        ann = Announcement.objects.filter(id=int(row_id)).first()
                        if ann:
                            ann.title = title
                            ann.category = cat
                            ann.target_audience = aud
                            ann.priority = pri
                            ann.content = content
                            ann.is_published = is_published
                            ann.save()
                            summary['announcements_updated'] += 1
                            continue

                    # Create new
                    new_ann = Announcement.objects.create(
                        title=title,
                        category=cat,
                        target_audience=aud,
                        priority=pri,
                        content=content,
                        is_published=is_published
                    )
                    summary['announcements_created'] += 1
                    new_id_updates.append((row_idx, new_ann.id))

                # Write newly assigned IDs back to Google Sheets Column A
                for r_idx, new_id in new_id_updates:
                    try:
                        ws_ann.update([[new_id]], f'A{r_idx}')
                    except Exception as e:
                        logger.warning(f"Failed to write back new announcement id: {e}")
        except Exception as e:
            logger.error(f"Error pulling announcements from Google Sheets: {e}")

        # 2. Pull News
        try:
            ws_news = sh.worksheet("News")
            news_records = ws_news.get_all_values()
            if len(news_records) > 1:
                new_id_updates = []
                for row_idx, row in enumerate(news_records[1:], start=2):
                    if not row or not any(row):
                        continue
                    row_id = row[0].strip() if len(row) > 0 else ""
                    title = row[2].strip() if len(row) > 2 else ""
                    if not title:
                        continue
                    cat = row[3].strip() if len(row) > 3 and row[3].strip() else "NEWS"
                    excerpt = row[4].strip() if len(row) > 4 else ""
                    content = row[5].strip() if len(row) > 5 else ""
                    feat_str = row[7].strip().upper() if len(row) > 7 else "FALSE"
                    pub_str = row[8].strip().upper() if len(row) > 8 else "TRUE"
                    is_featured = feat_str in ["TRUE", "1", "YES", "ពិត"]
                    is_published = pub_str in ["TRUE", "1", "YES", "ពិត"]

                    if row_id and row_id.isdigit():
                        art = NewsArticle.objects.filter(id=int(row_id)).first()
                        if art:
                            art.title = title
                            art.category = cat
                            art.excerpt = excerpt
                            art.content = content
                            art.is_featured = is_featured
                            art.is_published = is_published
                            art.save()
                            summary['news_updated'] += 1
                            continue

                    # Create new news article
                    new_art = NewsArticle.objects.create(
                        title=title,
                        category=cat,
                        excerpt=excerpt,
                        content=content,
                        is_featured=is_featured,
                        is_published=is_published
                    )
                    summary['news_created'] += 1
                    new_id_updates.append((row_idx, new_art.id))

                # Write newly assigned IDs back to Google Sheets Column A
                for r_idx, new_id in new_id_updates:
                    try:
                        ws_news.update([[new_id]], f'A{r_idx}')
                    except Exception as e:
                        logger.warning(f"Failed to write back new news id: {e}")
        except Exception as e:
            logger.error(f"Error pulling news from Google Sheets: {e}")

        # 3. Pull School Profile
        try:
            ws_prof = sh.worksheet("School_Profile")
            prof_records = ws_prof.get_all_values()
            if len(prof_records) > 1:
                p = SchoolProfile.get_settings()
                updated_fields = []
                for row in prof_records[1:]:
                    if len(row) < 3:
                        continue
                    key = row[0].strip()
                    val = row[2].strip()
                    if hasattr(p, key) and getattr(p, key) != val:
                        setattr(p, key, val)
                        updated_fields.append(key)
                if updated_fields:
                    p.save(update_fields=updated_fields)
                    summary['profile_updated'] = True
        except Exception as e:
            logger.error(f"Error pulling school profile from Google Sheets: {e}")

        # 4. Pull Contact Messages (read status updates)
        try:
            ws_cont = sh.worksheet("Contact_Messages")
            cont_records = ws_cont.get_all_values()
            if len(cont_records) > 1:
                for row in cont_records[1:]:
                    if len(row) < 8:
                        continue
                    row_id = row[0].strip()
                    read_str = row[7].strip().upper()
                    is_read = read_str in ["TRUE", "1", "YES", "ពិត"]
                    if row_id and row_id.isdigit():
                        c = ContactMessage.objects.filter(id=int(row_id)).first()
                        if c and c.is_read != is_read:
                            c.is_read = is_read
                            c.save(update_fields=['is_read'])
                            summary['contact_updated'] += 1
        except Exception as e:
            logger.error(f"Error pulling contact messages from Google Sheets: {e}")

        # Update registry timestamp
        registry = self.config.spreadsheets_registry or {}
        if self.REGISTRY_KEY in registry:
            registry[self.REGISTRY_KEY]['last_sync_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.config.spreadsheets_registry = registry
            self.config.save(update_fields=['spreadsheets_registry'])

        summary['status'] = 'success'
        summary['spreadsheet_url'] = sh.url
        return summary

    # =========================================================================
    # ⚡ REAL-TIME APPEND (Contact Messages)
    # =========================================================================
    def append_contact_message(self, contact_msg):
        """
        Appends a single contact message to the 'Contact_Messages' worksheet.
        """
        sh = self.get_or_create_website_spreadsheet()
        try:
            ws = sh.worksheet("Contact_Messages")
        except Exception:
            ws = self._prepare_worksheet(sh, "Contact_Messages", self.CONTACT_HEADERS)

        dt_str = contact_msg.created_at.strftime('%Y-%m-%d %H:%M') if contact_msg.created_at else ''
        row = [
            contact_msg.id,
            dt_str,
            contact_msg.name,
            contact_msg.phone,
            contact_msg.email or '',
            contact_msg.subject,
            contact_msg.message,
            "TRUE" if contact_msg.is_read else "FALSE"
        ]
        ws.append_row(row)

    @classmethod
    def append_contact_message_safely(cls, contact_msg):
        """
        Safely attempts to append contact message without interrupting client submission flow.
        """
        try:
            config = GoogleSheetsConfig.get_config()
            if not config.is_configured():
                return
            syncer = cls(config=config)
            syncer.append_contact_message(contact_msg)
        except Exception as e:
            logger.warning(f"Could not auto-append contact message #{contact_msg.id} to Google Sheets: {e}")
