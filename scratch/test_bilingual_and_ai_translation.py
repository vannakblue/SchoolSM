import os
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import django
# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import RequestFactory
from apps.accounts.models import SchoolProfile
from apps.extras.models import Announcement
from apps.website.models import NewsArticle
from apps.tools.ai_translation_service import AiTranslationService
from apps.accounts.translation_service import set_current_language, get_current_language
from apps.website.views import website_home

def run_tests():
    print("=" * 60)
    print("TEST 1: School Profile Auto-Translation via AI Service")
    print("=" * 60)
    
    profile = SchoolProfile.get_settings()
    profile.name_kh = "វិទ្យាល័យ ហ៊ុន សែន កំពង់កន្ទួត"
    profile.short_name = "វិ. ហ៊ុន សែន កំពង់កន្ទួត"
    profile.school_type = "វិទ្យាល័យ"
    profile.motto = "ចំណេះដឹង វិន័យ សីលធម៌ គុណធម៌"
    profile.street_address = "ផ្លូវលេខ១០៥ ភូមិស្វាយមីង ឃុំបារគូ ស្រុកកណ្តាលស្ទឹង ខេត្តកណ្តាល"
    profile.principal_name = "លោក ថេង រិទ្ធីយ៉ា"
    profile.about_school = "យើងខ្ញុំបណ្តុះបណ្តាលសិស្សឱ្យមានទាំងចំណេះដឹងទូទៅ ជំនាញបច្ចេកវិទ្យា វិន័យ សីលធម៌ល្អ និងស្មារតីទទួលខុសត្រូវខ្ពស់។"
    
    # Clear EN fields to test AI auto-population
    profile.name_en = ""
    profile.short_name_en = ""
    profile.school_type_en = ""
    profile.motto_en = ""
    profile.street_address_en = ""
    profile.principal_name_en = ""
    profile.about_school_en = ""
    
    AiTranslationService.auto_translate_school_profile(profile, overwrite=False)
    profile.save()
    
    print(f"Name (KH): {profile.name_kh}")
    print(f"Name (EN): {profile.name_en}")
    print(f"Short Name (KH): {profile.short_name}")
    print(f"Short Name (EN): {profile.short_name_en}")
    print(f"School Type (EN): {profile.school_type_en}")
    print(f"Motto (EN): {profile.motto_en}")
    print(f"Street Address (EN): {profile.street_address_en}")
    print(f"Principal (EN): {profile.principal_name_en}")
    print(f"About (EN): {profile.about_school_en[:60]}...")
    
    assert profile.name_en, "name_en must be translated"
    assert profile.motto_en, "motto_en must be translated"
    assert profile.principal_name_en, "principal_name_en must be translated"
    print(">>> PASS: School Profile AI translation succeeded!")

    print("\n" + "=" * 60)
    print("TEST 2: Announcement Auto-Translation via AI Service")
    print("=" * 60)
    ann, created = Announcement.objects.get_or_create(
        title="សេចក្តីជូនដំណឹងស្តីពីការឈប់សម្រាកបុណ្យភ្ជុំបិណ្ឌ",
        defaults={
            'content': "សាលារៀនសូមជម្រាបជូនដំណឹងដល់លោកគ្រូ អ្នកគ្រូ និងសិស្សានុសិស្សទាំងអស់ឱ្យបានជ្រាបថា សាលានឹងត្រូវឈប់សម្រាកចំនួន ៣ ថ្ងៃក្នុងឱកាសពិធីបុណ្យភ្ជុំបិណ្ឌខាងមុខនេះ។",
            'category': 'HOLIDAY',
            'target_audience': 'ALL',
            'is_published': True
        }
    )
    ann.title_en = ""
    ann.content_en = ""
    AiTranslationService.auto_translate_announcement(ann, overwrite=False)
    ann.save()
    
    print(f"Announcement Title (KH): {ann.title}")
    print(f"Announcement Title (EN): {ann.title_en}")
    print(f"Announcement Content (EN): {ann.content_en[:70]}...")
    assert ann.title_en, "Announcement title_en must be populated"
    print(">>> PASS: Announcement AI translation succeeded!")

    print("\n" + "=" * 60)
    print("TEST 3: News Article Auto-Translation via AI Service")
    print("=" * 60)
    news, created = NewsArticle.objects.get_or_create(
        title="ពិធីបើកបវេសនកាលឆ្នាំសិក្សាថ្មី ២០២៦-២០២៧",
        defaults={
            'excerpt': "គណៈគ្រប់គ្រងសាលាបានប្រារព្ធពិធីបើកបវេសនកាលឆ្នាំសិក្សាថ្មីយ៉ាងអធិកអធមក្រោមអធិបតីភាពលោកនាយកសាលា។",
            'content': "នៅព្រឹកថ្ងៃទី០១ ខែកញ្ញា ឆ្នាំ២០២៦ សាលារៀនបានរៀបចំពិធីបើកបវេសនកាលឆ្នាំសិក្សាថ្មី ២០២៦-២០២៧ ដោយមានការចូលរួមពីសំណាក់លោកគ្រូ អ្នកគ្រូ និងសិស្សានុសិស្សរាប់ពាន់នាក់។",
            'category': 'ACTIVITY',
            'is_published': True
        }
    )
    news.title_en = ""
    news.excerpt_en = ""
    news.content_en = ""
    AiTranslationService.auto_translate_news(news, overwrite=False)
    news.save()
    
    print(f"News Title (KH): {news.title}")
    print(f"News Title (EN): {news.title_en}")
    print(f"News Excerpt (EN): {news.excerpt_en}")
    assert news.title_en, "News title_en must be populated"
    print(">>> PASS: News Article AI translation succeeded!")

    print("\n" + "=" * 60)
    print("TEST 4: Dual Language View Rendering (?lang=km vs ?lang=en)")
    print("=" * 60)
    rf = RequestFactory()
    
    # Request in Khmer
    req_km = rf.get('/?lang=km')
    # mock session
    req_km.session = {'django_language': 'km'}
    resp_km = website_home(req_km)
    content_km = resp_km.content.decode('utf-8')
    
    # Request in English
    req_en = rf.get('/?lang=en')
    req_en.session = {'django_language': 'en'}
    resp_en = website_home(req_en)
    content_en = resp_en.content.decode('utf-8')
    
    print(f"Khmer Response Status: {resp_km.status_code}")
    print(f"English Response Status: {resp_en.status_code}")
    
    # Check Khmer response contains Khmer text
    assert "វិទ្យាល័យ ហ៊ុន សែន កំពង់កន្ទួត" in content_km or profile.name_kh in content_km, "Khmer page should contain Khmer name"
    print(">>> Khmer homepage renders correct Khmer title!")

    # Check English response contains English text
    assert profile.name_en in content_en, f"English page should contain {profile.name_en}"
    print(f">>> English homepage renders '{profile.name_en}' correctly!")
    
    print("\n" + "=" * 60)
    print("ALL 4 BILINGUAL & AI TRANSLATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == '__main__':
    run_tests()
