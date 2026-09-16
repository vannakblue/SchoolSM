import os
import sys
import django

sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User, SchoolProfile

def test_toggle():
    print("=" * 70)
    print("TEST: TOGGLE REGISTRATION PERIOD CLOSE / OPEN & BADGE STATUS")
    print("=" * 70)

    admin_user = User.objects.filter(role='ADMIN').first()
    if not admin_user:
        admin_user = User.objects.create(username='admin_test_toggle', role='ADMIN')
        admin_user.set_password('pass123')
        admin_user.save()

    client = Client()
    client.force_login(admin_user)

    sp = SchoolProfile.get_settings()
    sp.is_registration_open = True
    sp.save()
    print("Initial state: is_registration_open =", sp.is_registration_open)

    # 1. Simulate unchecking the switch and clicking Save (when unchecked, field is omitted or sent as 'false')
    # Case A: Sent with is_registration_open = 'false'
    resp = client.post('/students/enroll/api/registration-period/save/', {
        'is_registration_open': 'false',
        'registration_start_date': '',
        'registration_end_date': '',
        'registration_closed_message': 'ការចុះឈ្មោះត្រូវបានបិទបណ្តោះអាសន្ន។'
    }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    assert data['success'] == True
    assert data['is_registration_open'] == False
    assert data['status_code'] == 'CLOSED_MANUAL'
    print("  ✓ Case A (sent 'false'): Correctly saved as CLOSED_MANUAL (DISABLED).")

    # Case B: Sent with omitted checkbox (standard HTML form when checkbox is unchecked)
    resp = client.post('/students/enroll/api/registration-period/save/', {
        'registration_start_date': '',
        'registration_end_date': '',
        'registration_closed_message': 'ការចុះឈ្មោះត្រូវបានបិទបណ្តោះអាសន្ន។'
    }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    assert resp.status_code == 200
    data = resp.json()
    assert data['is_registration_open'] == False
    assert data['status_code'] == 'CLOSED_MANUAL'
    print("  ✓ Case B (omitted checkbox): Correctly handled as False / CLOSED_MANUAL.")

    # Case C: Turn it back ON
    resp = client.post('/students/enroll/api/registration-period/save/', {
        'is_registration_open': 'true',
        'registration_start_date': '',
        'registration_end_date': '',
        'registration_closed_message': ''
    }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    assert resp.status_code == 200
    data = resp.json()
    assert data['is_registration_open'] == True
    assert data['status_code'] == 'OPEN'
    print("  ✓ Case C (turned ON): Correctly saved as OPEN.")

    # 2. Check HTML rendering
    resp = client.get('/students/enroll/qr/')
    assert resp.status_code == 200
    assert 'កំពុងបើកដំណើរការ (OPEN)' in resp.content.decode('utf-8')
    print("  ✓ HTML rendering displays interactive OPEN button.")

    print("\nALL TEST CASES PASSED SUCCESSFULLY!")

if __name__ == '__main__':
    test_toggle()
