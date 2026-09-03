import os, sys, django
if sys.stdout and sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

import openpyxl
from datetime import datetime, date
from apps.teachers.models import Teacher
from apps.students.khmer_romanizer import romanize_khmer_name

wb_moeys = openpyxl.load_workbook('moeys_teachers_2026.xlsx', data_only=True)
ws_moeys = wb_moeys['2026']

moeys_teachers = []
for idx, r in enumerate(list(ws_moeys.iter_rows(values_only=True))[7:], start=8):
    if not r or not any(r):
        continue
    t_no = r[0]
    t_id = str(r[1]).strip() if r[1] is not None else ''
    t_name = str(r[2]).strip().replace('\u200b', ' ').replace('\xa0', ' ') if r[2] is not None else ''
    if not t_id or not t_name:
        continue
    
    t_gender = 'F' if str(r[3]).strip() in ['ស', 'ស្រី', 'F'] else 'M'
    t_dob = r[4]
    if isinstance(t_dob, datetime):
        t_dob = t_dob.date()
    t_qual = str(r[5]).strip() if r[5] is not None else ''
    t_spec = str(r[6]).strip() if r[6] is not None else ''
    t_training = str(r[7]).strip() if r[7] is not None else ''
    
    moeys_teachers.append({
        'teacher_id': t_id,
        'khmer_name': t_name,
        'gender': t_gender,
        'dob': t_dob,
        'qualification': t_qual,
        'specialization': t_spec,
        'training_level': t_training
    })

print(f"Total valid teachers in moeys_teachers_2026.xlsx: {len(moeys_teachers)}")

# Ensure all MoEYS teachers exist in DB
created = 0
updated = 0
for mt in moeys_teachers:
    t_obj = Teacher.objects.filter(teacher_id=mt['teacher_id']).first()
    if not t_obj:
        t_obj = Teacher.objects.filter(khmer_name=mt['khmer_name']).first()
    
    latin = romanize_khmer_name(mt['khmer_name'])
    
    if t_obj:
        t_obj.teacher_id = mt['teacher_id']
        t_obj.khmer_name = mt['khmer_name']
        t_obj.latin_name = latin
        t_obj.gender = mt['gender']
        if mt['dob']:
            t_obj.date_of_birth = mt['dob']
        if mt['specialization']:
            t_obj.specialization = mt['specialization']
        t_obj.save()
        updated += 1
    else:
        Teacher.objects.create(
            teacher_id=mt['teacher_id'],
            khmer_name=mt['khmer_name'],
            latin_name=latin,
            gender=mt['gender'],
            date_of_birth=mt['dob'],
            qualification=mt['qualification'],
            specialization=mt['specialization'] or 'ទូទៅ',
            training_level=mt['training_level'],
            status='ACTIVE'
        )
        created += 1

print(f"DB Teacher Sync from MoEYS: {created} Created, {updated} Updated. Total DB Teachers now = {Teacher.objects.count()}")
