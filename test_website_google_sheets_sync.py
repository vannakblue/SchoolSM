import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

import unittest
from unittest.mock import MagicMock, patch
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.accounts.models import GoogleSheetsConfig, SchoolProfile
from apps.extras.models import Announcement
from apps.website.models import NewsArticle, ContactMessage
from apps.website.website_google_sheets_sync import WebsiteGoogleSheetsSync

User = get_user_model()


class TestWebsiteGoogleSheetsSync(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username='test_admin_sync', password='password123', role='ADMIN')
        self.client = Client()
        self.client.force_login(self.admin)

        # Config
        self.config = GoogleSheetsConfig.get_config()
        self.config.is_active = True
        self.config.admin_email = "admin@example.com"
        self.config.save()

        # Sample Announcement
        self.ann = Announcement.objects.create(
            title="ដំណឹងប្រឡងឆមាសទី១",
            category="EXAM_SCHEDULE",
            target_audience="STUDENTS_PARENTS",
            priority="IMPORTANT",
            content="ការប្រឡងឆមាសទី១ នឹងចាប់ផ្តើមនៅសប្តាហ៍ក្រោយ។",
            is_published=True
        )

        # Sample News Article
        self.news = NewsArticle.objects.create(
            title="ពិធីសម្ពោធបណ្ណាល័យថ្មី",
            category="EVENT",
            excerpt="បណ្ណាល័យបំពាក់សម្ភារទំនើប",
            content="សាលាបានសម្ពោធបណ្ណាល័យទំនើបសម្រាប់សិស្សានុសិស្ស។",
            is_published=True,
            is_featured=True
        )

        # Sample Contact Message
        self.contact = ContactMessage.objects.create(
            name="សុខ ចាន់",
            phone="012345678",
            email="sokchan@example.com",
            subject="សាកសួរថ្លៃសិក្សា",
            message="សូមសួរអំពីតម្លៃសិក្សាថ្នាក់ទី១០",
            is_read=False
        )

    @patch.object(WebsiteGoogleSheetsSync, 'get_or_create_website_spreadsheet')
    def test_push_to_sheets(self, mock_get_spreadsheet):
        mock_sh = MagicMock()
        mock_ws = MagicMock()
        mock_get_spreadsheet.return_value = mock_sh
        
        syncer = WebsiteGoogleSheetsSync(config=self.config)
        syncer._prepare_worksheet = MagicMock(return_value=mock_ws)

        res = syncer.push_to_sheets()

        self.assertEqual(res['status'], 'success')
        self.assertGreaterEqual(res['announcements_count'], 1)
        self.assertGreaterEqual(res['news_count'], 1)
        self.assertGreaterEqual(res['profile_fields_count'], 10)
        self.assertGreaterEqual(res['contact_messages_count'], 1)
        self.assertEqual(syncer._prepare_worksheet.call_count, 4)

    @patch.object(WebsiteGoogleSheetsSync, 'get_or_create_website_spreadsheet')
    def test_pull_from_sheets_updates_and_creates(self, mock_get_spreadsheet):
        mock_sh = MagicMock()
        mock_get_spreadsheet.return_value = mock_sh

        # 1. Mock Announcement Sheet rows: 1 update, 1 new create
        mock_ws_ann = MagicMock()
        mock_ws_ann.get_all_values.return_value = [
            WebsiteGoogleSheetsSync.ANNOUNCEMENT_HEADERS,
            [str(self.ann.id), "2026-09-01", "ដំណឹងប្រឡងឆមាសទី១ (Updated)", "EXAM_SCHEDULE", "ALL", "URGENT", "កាលវិភាគថ្មី", "TRUE"],
            ["", "2026-09-02", "សេចក្តីជូនដំណឹងថ្មីពី Sheets", "GENERAL", "ALL", "NORMAL", "ខ្លឹមសារបង្កើតពី Sheets", "TRUE"]
        ]

        # 2. Mock News Sheet rows: 1 update, 1 new create
        mock_ws_news = MagicMock()
        mock_ws_news.get_all_values.return_value = [
            WebsiteGoogleSheetsSync.NEWS_HEADERS,
            [str(self.news.id), "2026-09-01", "ពិធីសម្ពោធបណ្ណាល័យថ្មី (Updated)", "EVENT", "សង្ខេបថ្មី", "ខ្លឹមសារថ្មី", "", "TRUE", "TRUE"],
            ["", "2026-09-02", "ព័ត៌មានបង្កើតពី Google Sheets", "SPORTS", "កីឡាសាលា", "ការប្រកួតកីឡាប្រចាំឆ្នាំ", "", "FALSE", "TRUE"]
        ]

        # 3. Mock School Profile Sheet rows
        mock_ws_prof = MagicMock()
        mock_ws_prof.get_all_values.return_value = [
            WebsiteGoogleSheetsSync.PROFILE_HEADERS,
            ["motto", "បាវចនាសាលា", "វិន័យ គុណធម៌ វិជ្ជាជីវៈ (Updated From Sheet)", "Desc"],
            ["phone", "លេខទូរស័ព្ទផ្លូវការ", "023999888", "Desc"],
        ]

        # 4. Mock Contact Messages Sheet rows: update is_read
        mock_ws_cont = MagicMock()
        mock_ws_cont.get_all_values.return_value = [
            WebsiteGoogleSheetsSync.CONTACT_HEADERS,
            [str(self.contact.id), "2026-09-01", "សុខ ចាន់", "012345678", "sokchan@example.com", "សាកសួរ", "សារ", "TRUE"]
        ]

        def get_worksheet_side_effect(name):
            if name == "Announcements": return mock_ws_ann
            if name == "News": return mock_ws_news
            if name == "School_Profile": return mock_ws_prof
            if name == "Contact_Messages": return mock_ws_cont
            return MagicMock()

        mock_sh.worksheet.side_effect = get_worksheet_side_effect

        syncer = WebsiteGoogleSheetsSync(config=self.config)
        summary = syncer.pull_from_sheets()

        self.assertEqual(summary['status'], 'success')
        self.assertEqual(summary['announcements_updated'], 1)
        self.assertEqual(summary['announcements_created'], 1)
        self.assertEqual(summary['news_updated'], 1)
        self.assertEqual(summary['news_created'], 1)
        self.assertTrue(summary['profile_updated'])
        self.assertEqual(summary['contact_updated'], 1)

        # Verify DB changed
        self.ann.refresh_from_db()
        self.assertEqual(self.ann.title, "ដំណឹងប្រឡងឆមាសទី១ (Updated)")
        self.assertEqual(self.ann.priority, "URGENT")

        self.news.refresh_from_db()
        self.assertEqual(self.news.title, "ពិធីសម្ពោធបណ្ណាល័យថ្មី (Updated)")

        profile = SchoolProfile.get_settings()
        self.assertEqual(profile.motto, "វិន័យ គុណធម៌ វិជ្ជាជីវៈ (Updated From Sheet)")
        self.assertEqual(profile.phone, "023999888")

        self.contact.refresh_from_db()
        self.assertTrue(self.contact.is_read)

        # Verify newly created records exist in DB
        new_ann = Announcement.objects.filter(title="សេចក្តីជូនដំណឹងថ្មីពី Sheets").first()
        self.assertIsNotNone(new_ann)

        new_news = NewsArticle.objects.filter(title="ព័ត៌មានបង្កើតពី Google Sheets").first()
        self.assertIsNotNone(new_news)

    def test_dashboard_view_renders(self):
        resp = self.client.get(reverse('website_google_sheets_dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "សមកាលកម្ម Google Sheets")
        self.assertContains(resp, "Announcements")
        self.assertContains(resp, "News")

    @patch.object(WebsiteGoogleSheetsSync, 'push_to_sheets')
    def test_push_view_redirects_and_flashes(self, mock_push):
        mock_push.return_value = {
            'announcements_count': 5,
            'news_count': 3,
            'contact_messages_count': 2
        }
        resp = self.client.post(reverse('website_google_sheets_push'))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(mock_push.called)

    @patch.object(WebsiteGoogleSheetsSync, 'pull_from_sheets')
    def test_pull_view_redirects_and_flashes(self, mock_pull):
        mock_pull.return_value = {
            'announcements_created': 1,
            'announcements_updated': 2,
            'news_created': 0,
            'news_updated': 1,
            'contact_updated': 0
        }
        resp = self.client.post(reverse('website_google_sheets_pull'))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(mock_pull.called)

    @patch.object(WebsiteGoogleSheetsSync, 'append_contact_message')
    def test_contact_submit_auto_appends(self, mock_append):
        with patch.object(GoogleSheetsConfig, 'is_configured', return_value=True):
            resp = self.client.post(reverse('website_contact_submit'), {
                'name': 'មាស វណ្ណា',
                'phone': '098765432',
                'email': 'vanna@example.com',
                'subject': 'ចុះឈ្មោះចូលរៀន',
                'message': 'ខ្ញុំចង់ចុះឈ្មោះកូនចូលរៀនថ្នាក់ទី៧'
            })
            self.assertEqual(resp.status_code, 302)
            created_msg = ContactMessage.objects.filter(name='មាស វណ្ណា').first()
            self.assertIsNotNone(created_msg)
            self.assertTrue(mock_append.called)


if __name__ == '__main__':
    unittest.main()
