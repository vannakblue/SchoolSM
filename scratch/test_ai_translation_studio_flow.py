import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

import json
from django.test import RequestFactory
from apps.accounts.models import User
from apps.accounts.views import api_ai_translate_text
from apps.website.models import NewsArticle
from apps.website.forms import NewsArticleForm
from apps.extras.models import Announcement
from apps.extras.forms import AnnouncementForm
from apps.tools.ai_translation_service import AiTranslationService

def run_tests():
    print("=" * 60)
    print("TEST 1: Verify /accounts/api/ai-translate/ Endpoint")
    print("=" * 60)
    
    rf = RequestFactory()
    user = User.objects.filter(is_superuser=True).first()
    if not user:
        user = User.objects.create_superuser('testadmin', 'test@example.com', 'pass1234')

    # Test JSON POST
    req = rf.post(
        '/accounts/api/ai-translate/',
        data=json.dumps({'text': 'ពិធីចែកសញ្ញាបត្រដល់សិស្សពូកែ', 'context': 'News Headline'}),
        content_type='application/json'
    )
    req.user = user
    resp = api_ai_translate_text(req)
    data = json.loads(resp.content.decode('utf-8'))
    
    print("Endpoint response status:", data.get('status'))
    print("Original text:", repr(data.get('original')))
    print("Translated text:", repr(data.get('translated_text')))
    print("Has 'translated' key:", 'translated' in data)
    print("Has 'translated_text' key:", 'translated_text' in data)
    
    assert data['status'] == 'success', f"Expected success status, got {data}"
    assert data.get('translated_text'), "translated_text must not be empty"
    assert data.get('translated') == data.get('translated_text'), "Both keys should match"

    print("\n" + "=" * 60)
    print("TEST 2: Admin Custom English Edit Preservation on Save")
    print("=" * 60)

    category = NewsArticle.Category.NEWS

    admin_custom_title_en = "Admin Customized Headline: Outstanding Students Certificate Ceremony 2026"
    admin_custom_excerpt_en = "Custom excerpt curated by administrator directly."
    admin_custom_content_en = "This is full content manually revised and styled by the school admin."

    post_data = {
        'title': 'ពិធីចែកសញ្ញាបត្រដល់សិស្សពូកែ',
        'title_en': admin_custom_title_en,
        'category': category,
        'excerpt': 'សេចក្តីសង្ខេបអំពីពិធីប្រគល់សញ្ញាបត្រ',
        'excerpt_en': admin_custom_excerpt_en,
        'content': 'ខ្លឹមសារពិស្តារនៃពិធីចែកសញ្ញាបត្រឆ្នាំ២០២៦',
        'content_en': admin_custom_content_en,
        'is_featured': True,
        'is_published': True,
    }

    form = NewsArticleForm(data=post_data)
    assert form.is_valid(), f"NewsArticleForm validation failed: {form.errors}"
    article = form.save()

    print("Saved Article Title (KH):", article.title)
    print("Saved Article Title (EN):", article.title_en)
    print("Saved Article Excerpt (EN):", article.excerpt_en)
    print("Saved Article Content (EN):", article.content_en)

    assert article.title_en == admin_custom_title_en, "Admin custom title_en must be preserved!"
    assert article.excerpt_en == admin_custom_excerpt_en, "Admin custom excerpt_en must be preserved!"
    assert article.content_en == admin_custom_content_en, "Admin custom content_en must be preserved!"

    # Clean up test article
    article.delete()

    print("\n" + "=" * 60)
    print("TEST 3: Announcement Admin Custom Edit Preservation on Save")
    print("=" * 60)

    ann_title_en = "Admin Custom Notice: First Semester Parent-Teacher Conference"
    ann_content_en = "All respected parents and guardians are cordially invited to attend."

    ann_data = {
        'title': 'សេចក្តីជូនដំណឹងស្តីពីការប្រជុំមាតាបិតាសិស្សឆមាសទី១',
        'title_en': ann_title_en,
        'category': 'GENERAL',
        'target_audience': 'ALL',
        'priority': 'NORMAL',
        'content': 'សូមគោរពអញ្ជើញមាតាបិតា ឬអាណាព្យាបាលសិស្សទាំងអស់ចូលរួម',
        'content_en': ann_content_en,
        'is_published': True,
        'broadcast_telegram': False,
    }

    ann_form = AnnouncementForm(data=ann_data)
    assert ann_form.is_valid(), f"AnnouncementForm validation failed: {ann_form.errors}"
    ann = ann_form.save()

    print("Saved Announcement Title (KH):", ann.title)
    print("Saved Announcement Title (EN):", ann.title_en)
    print("Saved Announcement Content (EN):", ann.content_en)

    assert ann.title_en == ann_title_en, "Admin custom announcement title_en must be preserved!"
    assert ann.content_en == ann_content_en, "Admin custom announcement content_en must be preserved!"

    # Clean up test announcement
    ann.delete()

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == '__main__':
    run_tests()
