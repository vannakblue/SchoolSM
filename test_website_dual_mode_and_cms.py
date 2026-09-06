import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
import django
django.setup()

from django.test import Client
from apps.accounts.models import User, SchoolProfile
from apps.website.models import NewsArticle, GalleryAlbum, GalleryPhoto, ContactMessage
from apps.extras.models import Announcement

def run_tests():
    print("==================================================")
    print("STARTING TEST SUITE: WEBSITE DUAL-MODE & CMS")
    print("==================================================")

    client = Client()

    # ----------------------------------------------------
    # TEST 1: ANONYMOUS PUBLIC ACCESS (NO LOGIN)
    # ----------------------------------------------------
    print("\n[TEST 1] Testing Public Homepage (/) without authentication...")
    res = client.get('/')
    assert res.status_code == 200, f"Expected 200 on /, got {res.status_code}"
    content = res.content.decode('utf-8')
    assert "ចូលប្រព័ន្ធ" in content or "Portal Login" in content, "Portal Login CTA should be present for anonymous visitors"
    assert "វិទ្យាល័យ" in content or "SchoolSM" in content, "School branding should be rendered"
    print(" -> Public Homepage rendered successfully (HTTP 200) with proper CTAs.")

    print("\n[TEST 2] Testing Public News List (/news/)...")
    res = client.get('/news/')
    assert res.status_code == 200, f"Expected 200 on /news/, got {res.status_code}"
    print(" -> News List rendered successfully (HTTP 200).")

    print("\n[TEST 3] Testing Public News Detail (/news/<id>/)...")
    article = NewsArticle.objects.filter(is_published=True).first()
    if article:
        initial_views = article.views_count
        res = client.get(f'/news/{article.id}/')
        assert res.status_code == 200, f"Expected 200 on /news/{article.id}/, got {res.status_code}"
        article.refresh_from_db()
        assert article.views_count == initial_views + 1, f"Expected views {initial_views + 1}, got {article.views_count}"
        print(f" -> News Detail '{article.title[:30]}...' rendered successfully. View count incremented to {article.views_count}.")

    print("\n[TEST 4] Testing Public Announcements (/notices/)...")
    res = client.get('/notices/')
    assert res.status_code == 200, f"Expected 200 on /notices/, got {res.status_code}"
    print(" -> Announcements board rendered successfully (HTTP 200).")

    ann = Announcement.objects.filter(is_published=True).first()
    if ann:
        res = client.get(f'/notices/{ann.id}/')
        assert res.status_code == 200, f"Expected 200 on /notices/{ann.id}/, got {res.status_code}"
        print(f" -> Announcement Detail '{ann.title[:30]}...' rendered successfully (HTTP 200).")

    print("\n[TEST 5] Testing Public Gallery (/gallery/)...")
    res = client.get('/gallery/')
    assert res.status_code == 200, f"Expected 200 on /gallery/, got {res.status_code}"
    print(" -> Gallery list rendered successfully (HTTP 200).")

    album = GalleryAlbum.objects.filter(is_published=True).first()
    if album:
        res = client.get(f'/gallery/{album.id}/')
        assert res.status_code == 200, f"Expected 200 on /gallery/{album.id}/, got {res.status_code}"
        print(f" -> Album Detail '{album.title[:30]}...' rendered successfully (HTTP 200).")

    print("\n[TEST 6] Testing Public Contact Form submission (/contact/)...")
    contact_data = {
        'name': 'លោក ចាន់ សុភាព (អាណាព្យាបាល)',
        'phone': '012 999 888',
        'email': 'sopheap@gmail.com',
        'subject': 'សាកសួរអំពីការចុះឈ្មោះចូលរៀនថ្នាក់ទី៧ ឆ្នាំសិក្សាថ្មី',
        'message': 'ខ្ញុំបាទចង់សាកសួរអំពីតម្លៃសិក្សា និងឯកសារដែលត្រូវយកមកចុះឈ្មោះ។ សូមអរគុណ!'
    }
    res = client.post('/contact/', data=contact_data, follow=True)
    assert res.status_code == 200, f"Expected 200 on /contact/ POST, got {res.status_code}"
    saved_msg = ContactMessage.objects.filter(phone='012 999 888').first()
    assert saved_msg is not None, "Contact message should be saved to database"
    assert saved_msg.is_read is False, "New message should have is_read=False"
    print(f" -> Contact message '{saved_msg.subject[:35]}...' submitted and stored in DB successfully.")

    # ----------------------------------------------------
    # TEST 7: AUTHENTICATED ADMIN ACCESS TO CMS
    # ----------------------------------------------------
    print("\n[TEST 7] Testing Admin Login and Access to Web App Portal...")
    admin_user = User.objects.filter(is_superuser=True).first() or User.objects.filter(role='ADMIN').first()
    if not admin_user:
        admin_user = User.objects.create_superuser('test_admin_cms', 'admin@test.com', 'pass123')
    
    client.force_login(admin_user)

    # Logged-in view of homepage
    res = client.get('/')
    assert res.status_code == 200
    content = res.content.decode('utf-8')
    assert "ផ្ទាំងគ្រប់គ្រង" in content or "Dashboard" in content, "Logged-in user on homepage should see Dashboard CTA"
    print(" -> Logged-in admin visiting / sees 'ផ្ទាំងគ្រប់គ្រង (Dashboard)' button as expected.")

    # Access CMS News Manager
    print("\n[TEST 8] Testing Admin CMS News Manager (/portal/cms/news/)...")
    res = client.get('/portal/cms/news/')
    assert res.status_code == 200, f"Expected 200 on /portal/cms/news/, got {res.status_code}"
    print(" -> Admin CMS News Manager accessible with HTTP 200.")

    # Create News via CMS
    print("\n[TEST 9] Testing News Creation via Admin CMS...")
    new_article_data = {
        'title': 'ការចុះហត្ថលេខាលើអនុស្សរណៈយោគយល់ (MOU) ជាមួយដៃគូអន្តរជាតិ',
        'category': 'ACADEMICS',
        'excerpt': 'សាលារៀនបានពង្រីកកិច្ចសហប្រតិបត្តិការអន្តរជាតិលើការបណ្តុះបណ្តាលជំនាញបច្ចេកវិទ្យា។',
        'content': 'ខ្លឹមសារលម្អិតនៃពិធីចុះហត្ថលេខា និងអត្ថប្រយោជន៍សម្រាប់សិស្សានុសិស្ស...',
        'is_featured': True,
        'is_published': True,
    }
    res = client.post('/portal/cms/news/create/', data=new_article_data, follow=True)
    assert res.status_code == 200, f"Expected 200 on create, got {res.status_code}"
    created_art = NewsArticle.objects.filter(title=new_article_data['title']).first()
    assert created_art is not None, "Article should be saved in DB"
    assert created_art.author == admin_user, "Article author should be set to logged-in admin"
    print(f" -> News '{created_art.title[:35]}...' created successfully via CMS.")

    # Toggle Publish
    res = client.post(f'/portal/cms/news/toggle/{created_art.id}/', follow=True)
    created_art.refresh_from_db()
    assert created_art.is_published is False, "Article should be unpublished"
    print(" -> Toggled publish status to Draft successfully.")

    # Access CMS Gallery Manager
    print("\n[TEST 10] Testing Admin CMS Gallery Manager (/portal/cms/gallery/)...")
    res = client.get('/portal/cms/gallery/')
    assert res.status_code == 200, f"Expected 200 on /portal/cms/gallery/, got {res.status_code}"
    print(" -> Admin CMS Gallery Manager accessible with HTTP 200.")

    # Create Album via CMS
    new_album_data = {
        'title': 'ការប្រកួតកីឡាបាល់ទាត់ និងបាល់ទះប្រចាំឆ្នាំ',
        'description': 'សកម្មភាពកីឡាដើម្បីសុខភាព និងមិត្តភាពរវាងថ្នាក់រៀនទាំងអស់។',
        'is_published': True,
    }
    res = client.post('/portal/cms/gallery/create/', data=new_album_data, follow=True)
    assert res.status_code == 200
    created_alb = GalleryAlbum.objects.filter(title=new_album_data['title']).first()
    assert created_alb is not None, "Album should be created in DB"
    print(f" -> Album '{created_alb.title}' created successfully via CMS.")

    # Access CMS Messages Inbox
    print("\n[TEST 11] Testing Admin CMS Messages Inbox (/portal/cms/messages/)...")
    res = client.get('/portal/cms/messages/')
    assert res.status_code == 200, f"Expected 200 on /portal/cms/messages/, got {res.status_code}"
    content = res.content.decode('utf-8')
    assert "លោក ចាន់ សុភាព" in content, "Visitor message should appear in admin inbox"
    print(" -> Admin CMS Inbox displays visitor inquiries properly.")

    # Toggle Read Status
    res = client.get(f'/portal/cms/messages/toggle/{saved_msg.id}/', follow=True)
    saved_msg.refresh_from_db()
    assert saved_msg.is_read is True, "Message should be marked as read"
    print(" -> Toggled message read status to True successfully.")

    # Sidebar Menu check
    print("\n[TEST 12] Testing Sidebar Catalog for Website CMS section...")
    res = client.get('/dashboard/admin/')
    assert res.status_code == 200
    content = res.content.decode('utf-8')
    assert "sec_website_cms" in content or "គ្រប់គ្រងគេហទំព័រ" in content or "Website" in content, "Website CMS menu section should be in admin sidebar"
    print(" -> Sidebar contains Website CMS menu section.")

    print("\n==================================================")
    print("ALL 12 TESTS PASSED PERFECTLY (100% SUCCESS)!")
    print("==================================================")

if __name__ == '__main__':
    run_tests()
