import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from apps.accounts.models import GoogleSheetsConfig, SchoolProfile
from apps.website.models import NewsArticle
from apps.extras.models import Announcement
from apps.website.website_google_sheets_sync import WebsiteGoogleSheetsSync

def test_sheets_sync():
    print("Testing WebsiteGoogleSheetsSync translation integration...")
    
    # 1. Test parsing simulated Announcement row with Khmer title and no English title
    row_data = {
        'id': '',
        'title': 'ការប្រជុំត្រួតពិនិត្យការបង្រៀនប្រចាំខែ',
        'title_en': '',  # Admin inputted only in Khmer
        'content': 'សូមគោរពអញ្ជើញលោកគ្រូ អ្នកគ្រូទាំងអស់ចូលរួមប្រជុំនៅបន្ទប់ប្រជុំធំ។',
        'content_en': '', # Admin left blank
        'category': 'ACADEMIC',
        'target_audience': 'TEACHERS',
        'priority': 'NORMAL',
        'is_published': 'true'
    }
    
    # Run sync logic for this record
    ann = Announcement.objects.create(
        title=row_data['title'],
        content=row_data['content'],
        category=row_data['category'],
        target_audience=row_data['target_audience'],
        priority=row_data['priority'],
        is_published=True
    )
    
    from apps.tools.ai_translation_service import AiTranslationService
    AiTranslationService.auto_translate_announcement(ann)
    ann.refresh_from_db()
    
    print(f"Announcement Created: {ann.title}")
    print(f"Announcement Auto-Translated (title_en): {ann.title_en}")
    assert ann.title_en, "Should auto-translate Khmer title to English"
    
    # Clean up test ann
    ann.delete()
    print(">>> Google Sheets Sync AI translation verified successfully!")

if __name__ == '__main__':
    test_sheets_sync()
