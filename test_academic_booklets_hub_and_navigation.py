import os
import sys
import django

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from django.urls import reverse
from apps.accounts.models import User, MenuItem, MenuSection
from apps.accounts.menu_registry import sync_system_menus_to_db, get_menu_catalog
from apps.academics.models import AcademicYear, Classroom
from apps.students.models import Student

def run_tests():
    print("=== Step 1: Testing Menu Sync & Database Registration ===")
    sync_system_menus_to_db()
    menu_item = MenuItem.objects.filter(code='academic_booklets_hub').first()
    assert menu_item is not None, "MenuItem 'academic_booklets_hub' must exist in DB!"
    print(f"[OK] Found MenuItem in DB: {menu_item.name_kh} | URL: {menu_item.url_name}")
    assert menu_item.url_name == 'academic_booklets_hub'
    assert menu_item.section.code == 'sec_examinations'
    print(f"[OK] Menu Item section is: {menu_item.section.name_kh}")

    catalog = get_menu_catalog()
    exam_sec = next((s for s in catalog if s['key'] == 'sec_examinations'), None)
    assert exam_sec is not None, "sec_examinations section must exist in catalog!"
    hub_in_catalog = any(item['key'] == 'academic_booklets_hub' for item in exam_sec.get('items', []))
    assert hub_in_catalog, "academic_booklets_hub must be present in get_menu_catalog()!"
    print("[OK] academic_booklets_hub is active in catalog hierarchy.")

    print("\n=== Step 2: Testing URL Resolution ===")
    hub_url = reverse('academic_booklets_hub')
    print(f"[OK] reverse('academic_booklets_hub') = {hub_url}")
    assert hub_url == '/examinations/academic-booklets/'

    print("\n=== Step 3: Testing HTTP 200 Rendering with Admin ===")
    admin_user = User.objects.filter(role='ADMIN', is_active=True).first()
    if not admin_user:
        admin_user = User.objects.filter(is_superuser=True).first()
    assert admin_user is not None, "Need an admin user to test with!"
    print(f"Testing with user: {admin_user.username} ({admin_user.role})")

    client = Client()
    client.force_login(admin_user)

    # 3.1 Base hub
    resp = client.get(hub_url)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    content = resp.content.decode('utf-8')
    assert "មជ្ឈមណ្ឌលសៀវភៅតាមដាន & សិក្ខាគារិក" in content, "Missing title in content!"
    assert "សៀវភៅតាមដាន (មួយថ្នាក់)" in content
    assert "សៀវភៅសិក្ខាគារិក (មួយថ្នាក់)" in content
    print("[OK] Hub base page rendered 200 OK with proper MoEYS titles.")

    # 3.2 Grade filter
    resp_grade = client.get(f"{hub_url}?grade=7")
    assert resp_grade.status_code == 200
    print("[OK] Hub grade filter rendered 200 OK.")

    # 3.3 Student search
    first_student = Student.objects.filter(status='ACTIVE').first()
    search_q = first_student.khmer_name[:4] if first_student else "វ៉ាន់"
    resp_search = client.get(f"{hub_url}?q={search_q}")
    assert resp_search.status_code == 200
    search_content = resp_search.content.decode('utf-8')
    assert "លទ្ធផលស្វែងរកសិស្ស" in search_content
    print(f"[OK] Hub student search for '{search_q}' rendered 200 OK.")

    # 3.4 Test Admin Dashboard has the link
    resp_dash = client.get(reverse('admin_dashboard'))
    assert resp_dash.status_code == 200
    dash_content = resp_dash.content.decode('utf-8')
    assert hub_url in dash_content, f"admin_dashboard must contain link to {hub_url}!"
    print("[OK] admin_dashboard successfully contains link to academic_booklets_hub.")

    # 3.5 Test Student List has the link
    resp_stu_list = client.get(reverse('student_list'))
    assert resp_stu_list.status_code == 200
    stu_list_content = resp_stu_list.content.decode('utf-8')
    assert hub_url in stu_list_content, f"student_list must contain link to {hub_url}!"
    assert "student_study_tracking_book_view" in stu_list_content or "tracking-book" in stu_list_content
    print("[OK] student_list successfully contains link to academic_booklets_hub and student actions.")

    # 3.6 Test Classroom List has the link
    resp_cls_list = client.get(reverse('classroom_list'))
    assert resp_cls_list.status_code == 200
    cls_list_content = resp_cls_list.content.decode('utf-8')
    assert hub_url in cls_list_content, f"classroom_list must contain link to {hub_url}!"
    print("[OK] classroom_list successfully contains link to academic_booklets_hub.")

    # 3.7 Test Annual Results has the link
    resp_ann = client.get(reverse('annual_results'))
    assert resp_ann.status_code == 200
    ann_content = resp_ann.content.decode('utf-8')
    assert hub_url in ann_content, f"annual_results must contain link to {hub_url}!"
    print("[OK] annual_results successfully contains link to academic_booklets_hub.")

    print("\nALL VERIFICATIONS PASSED SUCCESSFULLY! 100% OK.")

if __name__ == '__main__':
    run_tests()
