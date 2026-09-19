import os
import re
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import SchoolProfile


def test_public_website_pure_english_mode():
    client = Client()
    
    # 1. Test Homepage in English
    res_home = client.get('/?lang=en')
    assert res_home.status_code == 200, f"Expected 200, got {res_home.status_code}"
    html_home = res_home.content.decode('utf-8')
    
    # Check Spot 1: Top Navbar Brand Subtitle
    assert "Hun Sen Kampong Kantuot High School" in html_home
    assert '<span class="text-muted small fw-semibold" style="font-size: 0.75rem; letter-spacing: 0.3px;">វិទ្យាល័យ ហ៊ុន សែន កំពង់កន្ទួត</span>' not in html_home
    
    # Check Spot 2: Footer Brand Subtitle
    assert '<small class="text-light-50">វិទ្យាល័យ ហ៊ុន សែន កំពង់កន្ទួត</small>' not in html_home
    
    # Check Spot 3: Footer Education Levels
    assert "អនុវិទ្យាល័យ, វិទ្យាល័យ" not in html_home
    assert "Secondary &amp; High School" in html_home or "Secondary & High School" in html_home
    
    # Check Spot 4: Footer Administration DoE Name
    assert "ការិយាល័យអប់រំ យុវជន និងកីឡា ស្រុកកណ្តាលស្ទឹង" not in html_home
    assert "Kandal Stueng District Office of Education" in html_home
    
    # 2. Test Contact Page in English
    res_contact = client.get('/contact/?lang=en')
    assert res_contact.status_code == 200
    html_contact = res_contact.content.decode('utf-8')
    
    # Exclude language switcher item
    filtered_khmer = [
        m for m in re.findall(r'[\u1780-\u17FF]+', html_contact)
        if m not in ['ភាសាខ្មែរ', 'ខ្មែរ', 'ភាសា']
    ]
    assert len(filtered_khmer) == 0, f"Found unexpected Khmer text in English contact page: {filtered_khmer}"
    
    # Check Contact Page specific English elements
    assert "Contact School" in html_contact
    assert "Contact Information" in html_contact
    assert "Official Address" in html_contact
    assert "Phone Numbers" in html_contact
    assert "Official Email" in html_contact
    assert "Open in Google Maps" in html_contact
    assert "Send an Inquiry" in html_contact
    assert "Full Name *" in html_contact
    assert "Phone Number *" in html_contact
    assert "Submit Message to School" in html_contact
    
    print("=== ALL PUBLIC WEBSITE PURE ENGLISH MODE TESTS PASSED (100%) ===")


if __name__ == '__main__':
    test_public_website_pure_english_mode()
