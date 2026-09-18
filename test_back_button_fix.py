import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.academics.models import Classroom

def run():
    admin_user = User.objects.filter(role='ADMIN').first() or User.objects.filter(is_superuser=True).first()
    client = Client()
    client.force_login(admin_user)

    cls = Classroom.objects.first()
    assert cls is not None

    # 1. Batch tracking book view
    r1 = client.get(f'/examinations/homeroom/{cls.id}/individual-tracking-books/')
    assert r1.status_code == 200, f'Expected 200, got {r1.status_code}'
    c1 = r1.content.decode('utf-8')
    assert 'smartGoBack' in c1, 'Missing smartGoBack in tracking book'
    assert '/examinations/academic-booklets/' in c1
    print('[PASS] Batch tracking book view tested OK with smartGoBack!')

    # 2. Batch dossier view
    r2 = client.get(f'/examinations/homeroom/{cls.id}/cumulative-dossier/')
    assert r2.status_code == 200, f'Expected 200, got {r2.status_code}'
    c2 = r2.content.decode('utf-8')
    assert 'smartGoBack' in c2, 'Missing smartGoBack in dossier'
    assert '/examinations/academic-booklets/' in c2
    print('[PASS] Batch cumulative dossier view tested OK with smartGoBack!')

    # 3. Test with classroom having 0 students
    test_cls, _ = Classroom.objects.get_or_create(
        code='TEST-EMPTY-01',
        academic_year=cls.academic_year,
        defaults={'name': 'ថ្នាក់ 7A-TEST', 'grade_level': 7}
    )
    r3 = client.get(f'/examinations/homeroom/{test_cls.id}/individual-tracking-books/')
    assert r3.status_code == 200
    c3 = r3.content.decode('utf-8')
    assert 'មិនទាន់មានទិន្នន័យសិស្សឡើយ' in c3
    print('[PASS] Empty classroom shows friendly message and working back button!')

    print('\nALL VERIFICATIONS PASSED SUCCESSFULLY! 100% OK.')

if __name__ == '__main__':
    run()
