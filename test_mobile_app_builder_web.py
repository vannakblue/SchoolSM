import os
import django
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

User = get_user_model()

class MobileAppBuilderWebTest(TestCase):
    def setUp(self):
        self.client = Client()
        # Create an admin user
        self.admin_user = User.objects.create_superuser(
            username='test_admin',
            email='admin@schoolsm.test',
            password='password123',
            role='ADMIN'
        )
        # Create a teacher user
        self.teacher_user = User.objects.create_user(
            username='test_teacher',
            email='teacher@schoolsm.test',
            password='password123',
            role='TEACHER'
        )

    def test_mobile_app_manager_view_admin(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('tool_mobile_app_manager'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'SchoolSM Mobile App & APK')
        self.assertContains(response, 'Build Release APK')
        self.assertContains(response, 'Apple iOS')

    def test_mobile_app_manager_access_restricted_for_teacher(self):
        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse('tool_mobile_app_manager'))
        # Should redirect or deny
        self.assertIn(response.status_code, [302, 403])

    def test_api_build_status(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('api_mobile_build_status'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('status', data)
        self.assertIn('apk_exists', data)
        self.assertIn('apk_size_mb', data)

    def test_tool_download_mobile_apk(self):
        response = self.client.get(reverse('tool_download_mobile_apk'))
        # If SchoolSM-Mobile.apk exists on disk, it should return 200 with APK MIME type
        if os.path.exists('SchoolSM-Mobile.apk'):
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'application/vnd.android.package-archive')
            self.assertIn('SchoolSM-Mobile.apk', response['Content-Disposition'])

    def test_tool_mobile_apk_qr(self):
        response = self.client.get(reverse('tool_mobile_apk_qr'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertTrue(len(response.content) > 100)

    def test_tool_download_mobile_ipa(self):
        response = self.client.get(reverse('tool_download_mobile_ipa'))
        # If local IPA not present, redirects to GitHub Releases CDN
        self.assertIn(response.status_code, [200, 302])

    def test_tool_public_mobile_download(self):
        # Publicly accessible without login
        response = self.client.get(reverse('tool_public_mobile_download'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Android')
        self.assertContains(response, 'Apple iOS')
        self.assertContains(response, 'APK')

if __name__ == '__main__':
    import unittest
    suite = unittest.TestLoader().loadTestsFromTestCase(MobileAppBuilderWebTest)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        exit(1)
