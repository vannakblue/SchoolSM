from django.db import migrations
from datetime import datetime, date
from decimal import Decimal
import json
import os


def seed_119_teachers(apps, schema_editor):
    Teacher = apps.get_model('teachers', 'Teacher')
    User = apps.get_model('accounts', 'User')
    from django.contrib.auth.hashers import make_password

    # Load seed JSON
    curr_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(os.path.dirname(curr_dir), 'moeys_teachers_seed_data.json')
    if not os.path.exists(json_path):
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        teachers_data = json.load(f)

    default_pwd_hash = make_password('password123')

    def parse_dt(d_str):
        if not d_str:
            return None
        try:
            return datetime.strptime(d_str, '%Y-%m-%d').date()
        except Exception:
            return None

    for item in teachers_data:
        t_id = item['teacher_id']
        k_name = item['khmer_name']
        l_name = item['latin_name']
        gender = item['gender']
        dob = parse_dt(item.get('date_of_birth'))
        qual = item.get('qualification', '')
        spec = item.get('specialization', 'ទូទៅ')
        train_level = item.get('training_level', '')
        state_hire = parse_dt(item.get('state_hire_date'))
        perm_date = parse_dt(item.get('permanent_date'))
        subj1 = item.get('primary_subject', '')
        subj2 = item.get('secondary_subject', '')
        duty = item.get('current_duty', 'គ្រូបង្រៀន')
        prakas_cat = item.get('prakas_category', '')
        prakas_yr = item.get('prakas_year', '')
        prakas_num = item.get('prakas_number', '')
        phone = item.get('phone', '')
        is_fee_collector = item.get('is_fee_collector', False)

        teacher, _ = Teacher.objects.update_or_create(
            teacher_id=t_id,
            defaults={
                'khmer_name': k_name,
                'latin_name': l_name,
                'gender': gender,
                'date_of_birth': dob,
                'qualification': qual,
                'specialization': spec,
                'training_level': train_level,
                'state_hire_date': state_hire,
                'permanent_date': perm_date,
                'primary_subject': subj1,
                'secondary_subject': subj2,
                'current_duty': duty,
                'prakas_category': prakas_cat,
                'prakas_year': prakas_yr,
                'prakas_number': prakas_num,
                'phone': phone,
                'base_salary': Decimal('500.00'),
                'max_weekly_hours': 18,
                'is_fee_collector': is_fee_collector,
                'status': 'ACTIVE',
            }
        )

        user, user_created = User.objects.get_or_create(
            username=t_id,
            defaults={
                'password': default_pwd_hash,
                'role': 'TEACHER',
                'khmer_name': k_name,
                'latin_name': l_name,
                'phone': phone,
                'email': f"{t_id}@hunsenkkt.edu.kh",
                'is_active': True,
            }
        )
        if not user_created:
            user.khmer_name = k_name
            user.latin_name = l_name
            user.phone = phone
            user.role = 'TEACHER'
            user.save(update_fields=['khmer_name', 'latin_name', 'phone', 'role'])

        teacher.user = user
        teacher.save(update_fields=['user'])


def reverse_seed(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('teachers', '0011_teacher_last_profile_verified_at_and_more'),
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_119_teachers, reverse_seed),
    ]
