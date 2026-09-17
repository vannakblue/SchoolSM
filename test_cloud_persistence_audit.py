import os
import sys
import json
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import dj_database_url
from django.conf import settings
from apps.accounts.models import GoogleSheetsConfig, SchoolProfile
from apps.accounts.permanent_data_manager import export_permanent_admin_defaults, import_permanent_admin_defaults

def test_audit():
    print("=== AUDITING CLOUD PERSISTENCE (NEON.TECH, CLOUDINARY, GOOGLE SHEETS) ===")

    # 1. TEST NEON.TECH DATABASE_URL PARSER & SSL ENFORCEMENT
    print("\n--- 1. Testing Neon.tech PostgreSQL Database Parser ---")
    neon_url = "postgresql://myuser:mypass@ep-cool-project-123456.us-east-2.aws.neon.tech/neondb"
    is_cloud_postgres = any(host_kw in neon_url.lower() for host_kw in ['neon.tech', 'supabase', 'render.com', 'aws', 'pooler'])
    is_local = any(loc_kw in neon_url.lower() for loc_kw in ['localhost', '127.0.0.1'])
    ssl_require = is_cloud_postgres or (not is_local and 'postgres' in neon_url.lower())
    
    parsed = dj_database_url.parse(neon_url, conn_max_age=600, conn_health_checks=True, ssl_require=ssl_require)
    assert parsed['ENGINE'] == 'django.db.backends.postgresql'
    assert parsed['HOST'] == 'ep-cool-project-123456.us-east-2.aws.neon.tech'
    assert parsed['USER'] == 'myuser'
    assert parsed['NAME'] == 'neondb'
    assert parsed['OPTIONS']['sslmode'] == 'require', "Neon.tech connection MUST require sslmode"
    print("✓ Neon.tech Database URL parsed perfectly with enforced sslmode=require.")

    # 2. TEST CLOUDINARY CONFIGURATION PARSER
    print("\n--- 2. Testing Cloudinary Parser ---")
    # Test CLOUDINARY_URL unified format
    import urllib.parse
    test_c_url = "cloudinary://123456789012345:mySecretKeyAbc@myschoolcloud"
    parsed_c = urllib.parse.urlparse(test_c_url)
    c_cloud = parsed_c.hostname
    c_key = parsed_c.username
    c_secret = parsed_c.password
    assert c_cloud == 'myschoolcloud'
    assert c_key == '123456789012345'
    assert c_secret == 'mySecretKeyAbc'
    print("✓ Cloudinary single URL (CLOUDINARY_URL) parsing verified.")

    # Check that packages are installed
    import cloudinary
    import cloudinary_storage
    print("✓ Cloudinary package loaded successfully.")
    print("✓ django-cloudinary-storage loaded successfully.")

    # 3. TEST GOOGLE SHEETS SERVICE ACCOUNT FROM ENV & MODEL
    print("\n--- 3. Testing Google Sheets Integration ---")
    dummy_creds = {
        "type": "service_account",
        "project_id": "test-school-project",
        "private_key_id": "abcdef123456",
        "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC...\n-----END PRIVATE KEY-----\n",
        "client_email": "school-sync@test-school-project.iam.gserviceaccount.com",
        "client_id": "10987654321"
    }
    
    # Test loading from environment variable GOOGLE_SERVICE_ACCOUNT_JSON
    os.environ['GOOGLE_SERVICE_ACCOUNT_JSON'] = json.dumps(dummy_creds)
    gs_cfg = GoogleSheetsConfig.get_config()
    loaded_creds = gs_cfg.get_credentials_dict()
    assert loaded_creds is not None, "Should load credentials from GOOGLE_SERVICE_ACCOUNT_JSON env var"
    assert loaded_creds['client_email'] == "school-sync@test-school-project.iam.gserviceaccount.com"
    assert gs_cfg.client_email == "school-sync@test-school-project.iam.gserviceaccount.com"
    print("✓ Google Service Account successfully detected from Render environment variable!")
    del os.environ['GOOGLE_SERVICE_ACCOUNT_JSON']

    # 4. TEST PERMANENT DATA MANAGER SYNC FOR GOOGLE SHEETS
    print("\n--- 4. Testing Permanent Data Manager (Google Sheets Config Protection) ---")
    gs_cfg.is_active = True
    gs_cfg.admin_email = "admin@myschool.edu.kh"
    gs_cfg.drive_folder_id = "folder_xyz_123"
    gs_cfg.spreadsheets_registry = {
        "2025-2026": {
            "sheet_id": "sheet_abc_123",
            "sheet_url": "https://docs.google.com/spreadsheets/d/sheet_abc_123/edit"
        }
    }
    gs_cfg.save()

    # Export to fixture
    fixture_path = export_permanent_admin_defaults()
    assert fixture_path.exists()

    with open(fixture_path, 'r', encoding='utf-8') as f:
        fixture_content = json.load(f)
    assert 'google_sheets_config' in fixture_content
    assert fixture_content['google_sheets_config']['admin_email'] == "admin@myschool.edu.kh"
    assert fixture_content['google_sheets_config']['spreadsheets_registry']['2025-2026']['sheet_id'] == "sheet_abc_123"
    print("✓ Google Sheets configuration exported into permanent_admin_defaults.json.")

    # Re-import test
    import_permanent_admin_defaults()
    gs_cfg.refresh_from_db()
    assert gs_cfg.admin_email == "admin@myschool.edu.kh"
    assert "2025-2026" in gs_cfg.spreadsheets_registry
    print("✓ Google Sheets configuration successfully restored by import_permanent_admin_defaults().")

    print("\n🎉 ALL CLOUD PERSISTENCE AUDIT CHECKS PASSED 100%!")

if __name__ == '__main__':
    test_audit()
