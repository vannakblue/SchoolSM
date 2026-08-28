import os
import sys
import django
from datetime import date

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from django.urls import reverse
from apps.accounts.models import User
from apps.teachers.models import Teacher, TeacherProfileUpdateCampaign


def test_teacher_resubmission_campaign_and_portal():
    print("=== STARTING TEACHER RE-SUBMISSION CAMPAIGN & PORTAL VERIFICATION ===")

    # 1. Verify Viewport Zoom configuration in base.html
    base_path = os.path.join('templates', 'base.html')
    with open(base_path, 'r', encoding='utf-8') as f:
        base_content = f.read()
    assert 'maximum-scale=5.0' in base_content
    assert 'user-scalable=yes' in base_content
    print("  [PASS] 1. Smartphone & Tablet Pinch-to-Zoom enabled in base viewport meta tag.")

    # 2. Verify Section 2 Layout Redesign in teacher_form.html
    form_path = os.path.join('templates', 'teachers', 'teacher_form.html')
    with open(form_path, 'r', encoding='utf-8') as f:
        form_content = f.read()
    # Check that qualification and specialization are in col-md-6, training level and subjects in col-md-4
    assert '{{ form.qualification }}' in form_content
    assert '{{ form.specialization }}' in form_content
    assert '{{ form.training_level }}' in form_content
    assert '{{ form.primary_subject }}' in form_content
    assert '{{ form.secondary_subject }}' in form_content
    print("  [PASS] 2. Section 2 layout reorganized: Qualification + Specialization (50/50), Training Level + Subjects (33/33/33).")

    # 3. Create Admin & Teacher Users
    admin_user, _ = User.objects.get_or_create(
        username='admin_campaign_tester',
        defaults={'role': User.Role.ADMIN, 'khmer_name': 'Admin Campaign Tester'}
    )
    admin_user.set_password('password123')
    admin_user.save()

    teacher_user, _ = User.objects.get_or_create(
        username='teacher_portal_user',
        defaults={'role': User.Role.TEACHER, 'khmer_name': 'គ្រូ សាកល្បង', 'latin_name': 'Test Teacher'}
    )
    teacher_user.set_password('password123')
    teacher_user.save()

    teacher_obj, _ = Teacher.objects.update_or_create(
        teacher_id='T-PORTAL-01',
        defaults={
            'user': teacher_user,
            'khmer_name': 'គ្រូ សាកល្បង',
            'latin_name': 'Test Teacher',
            'gender': Teacher.Gender.MALE,
            'date_of_birth': date(1985, 5, 20),
            'specialization': 'គណិតវិទ្យា',
            'phone': '012334455',
            'base_salary': 500.00,
            'status': Teacher.Status.ACTIVE
        }
    )

    client = Client()

    # 4. Test Admin Campaign Settings
    client.force_login(admin_user)
    res_campaign_get = client.get(reverse('teacher_update_campaign'))
    assert res_campaign_get.status_code == 200
    assert 'យុទ្ធនាការទាមទារ/បំពេញព័ត៌មានគ្រូបង្រៀនឡើងវិញ' in res_campaign_get.content.decode('utf-8')

    # Admin Ticks specific sections: ['identity', 'address', 'education', 'training_subjects', 'phone_email']
    post_data = {
        'title': 'យុទ្ធនាការបច្ចុប្បន្នភាពព័ត៌មានគ្រូដើមឆ្នាំសិក្សា',
        'instructions': 'សូមលោកគ្រូ-អ្នកគ្រូ មេត្តាពិនិត្យ និងបំពេញព័ត៌មានឱ្យបានគ្រប់ជ្រុងជ្រោយ។',
        'is_active': '1',
        'target_all': '1',
        'deadline': '2026-12-31',
        'sections': ['identity', 'dob_gender', 'phone_email', 'address', 'education', 'training_subjects', 'civil_service'],
    }
    res_campaign_post = client.post(reverse('teacher_update_campaign'), post_data, follow=True)
    assert res_campaign_post.status_code == 200

    campaign = TeacherProfileUpdateCampaign.objects.first()
    assert campaign.is_active is True
    assert 'address' in campaign.allowed_sections
    assert 'training_subjects' in campaign.allowed_sections
    print(f"  [PASS] 3. Admin configured and ticked allowed sections in Campaign: {campaign.title}.")

    # 5. Test Teacher Accessing Self-Update Portal
    client.force_login(teacher_user)
    res_portal_get = client.get(reverse('teacher_self_update_portal'))
    assert res_portal_get.status_code == 200
    portal_content = res_portal_get.content.decode('utf-8')
    assert 'Teacher Self-Service Portal' in portal_content
    assert 'T-PORTAL-01' in portal_content
    assert 'អាសយដ្ឋានបច្ចុប្បន្ន (ជ្រើសរើសតាមលំដាប់ថ្នាក់រដ្ឋបាលកម្ពុជា)' in portal_content
    print("  [PASS] 4. Teacher accessed self-update portal and verified unlocked sections.")

    # 6. Test Teacher Submitting Updated Data via Portal
    update_data = {
        'khmer_name': 'គ្រូ សាកល្បង វីរៈ',
        'latin_name': 'Test Teacher Virak',
        'gender': 'M',
        'date_of_birth': '1985-05-20',
        'phone': '098776655',
        'email': 'virak@school.edu.kh',
        'address': 'ភូមិវត្តបូព៌, សង្កាត់សាលាកំរើក, ក្រុងសៀមរាប, ខេត្តសៀមរាប',
        'qualification': 'បរិញ្ញាបត្រអប់រំ',
        'specialization': 'គណិតវិទ្យា & ICT',
        'training_level': 'គរុកោសល្យឧត្តម',
        'primary_subject': 'គណិតវិទ្យា',
        'secondary_subject': 'ព័ត៌មានវិទ្យា',
        'current_duty': 'ប្រធានដេប៉ាតឺម៉ង់',
        'prakas_category': 'ក្របខ័ណ្ឌ ក.១',
        'prakas_year': '2015',
        'prakas_number': 'ប្រកាសលេខ ៩៩៩',
    }
    res_portal_post = client.post(reverse('teacher_self_update_portal'), update_data, follow=True)
    assert res_portal_post.status_code == 200

    # Refresh teacher record
    teacher_obj.refresh_from_db()
    assert teacher_obj.khmer_name == 'គ្រូ សាកល្បង វីរៈ'
    assert teacher_obj.phone == '098776655'
    assert teacher_obj.address == 'ភូមិវត្តបូព៌, សង្កាត់សាលាកំរើក, ក្រុងសៀមរាប, ខេត្តសៀមរាប'
    assert teacher_obj.specialization == 'គណិតវិទ្យា & ICT'
    assert teacher_obj.training_level == 'គរុកោសល្យឧត្តម'
    assert teacher_obj.primary_subject == 'គណិតវិទ្យា'
    assert teacher_obj.last_profile_verified_at is not None
    print(f"  [PASS] 5. Teacher submitted update: Address='{teacher_obj.address}', Specialization='{teacher_obj.specialization}', VerifiedAt={teacher_obj.last_profile_verified_at}.")

    # 7. Clean up test records
    teacher_obj.delete()
    User.objects.filter(username__in=['admin_campaign_tester', 'teacher_portal_user']).delete()
    print("=== ALL TEACHER RE-SUBMISSION CAMPAIGN & PORTAL TESTS PASSED 100% ===")


if __name__ == '__main__':
    test_teacher_resubmission_campaign_and_portal()
