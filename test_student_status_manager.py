import os
import sys
import datetime
import django

sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.academics.models import AcademicYear, Classroom
from apps.students.models import Student, StudentStatusConfig

print("=== TESTING STUDENT STATUS MANAGEMENT (CRUD & QUICK CHANGER) ===")

# 1. Ensure default statuses exist
StudentStatusConfig.ensure_default_statuses()
assert StudentStatusConfig.objects.filter(code='ACTIVE').exists()
assert StudentStatusConfig.objects.filter(code='SUSPENDED').exists()
assert StudentStatusConfig.objects.filter(code='DROPPED').exists()
assert StudentStatusConfig.objects.filter(code='TRANSFERRED').exists()
assert StudentStatusConfig.objects.filter(code='GRADUATED').exists()
print("[PASS] 1. MoEYS Standard 5 Default Statuses verified!")

# 2. Setup Admin and Student
admin_user, _ = User.objects.get_or_create(username="admin_status_tester", defaults={'role': User.Role.ADMIN, 'is_superuser': True})
year, _ = AcademicYear.objects.get_or_create(name="2026-2027 Status Test", defaults={'start_date': datetime.date(2026, 1, 1), 'end_date': datetime.date(2026, 12, 31), 'is_current': True})
classroom, _ = Classroom.objects.get_or_create(code="10A_STATUS_TEST", academic_year=year, defaults={'name': "10A (Status Test)", 'grade_level': 10})

student, _ = Student.objects.get_or_create(
    student_id="STU_STAT_01",
    defaults={
        'khmer_name': "លី ម៉េងឡុង (Status Test)",
        'latin_name': "LY MENGLONG",
        'gender': 'M',
        'date_of_birth': datetime.date(2009, 1, 1),
        'classroom': classroom,
        'academic_year': year,
        'status': 'ACTIVE'
    }
)

client = Client()
client.force_login(admin_user)

# 3. Test View: GET /students/statuses/
res_list = client.get('/students/statuses/')
assert res_list.status_code == 200
html_list = res_list.content.decode('utf-8')
assert 'ការកំណត់ស្ថានភាពសិក្សា' in html_list
assert 'កំពុងរៀន' in html_list
print("[PASS] 2. GET /students/statuses/ rendered status list and stats cards!")

# 4. Test Create Custom Status: POST /students/statuses/save/
StudentStatusConfig.objects.filter(code='MEDICAL_LEAVE').delete()
res_create = client.post('/students/statuses/save/', {
    'name': "ព្យួរការសិក្សាដោយជំងឺ",
    'name_en': "Medical Leave",
    'code': "MEDICAL_LEAVE",
    'badge_color': "warning",
    'category_type': "SUSPENDED",
    'description': "សិស្សសុំច្បាប់ព្យួរការសិក្សាព្យាបាលជំងឺ",
    'order': 6,
    'is_active': True,
}, follow=True)
assert res_create.status_code == 200
med_stat = StudentStatusConfig.objects.filter(code='MEDICAL_LEAVE').first()
assert med_stat is not None
assert med_stat.name == "ព្យួរការសិក្សាដោយជំងឺ"
assert med_stat.badge_color == "warning"
print("[PASS] 3. POST /students/statuses/save/ created custom status 'ព្យួរការសិក្សាដោយជំងឺ'!")

# 5. Test Quick Status Update: POST /students/<id>/quick-status/
res_quick = client.post(f'/students/{student.id}/quick-status/', {
    'status': 'MEDICAL_LEAVE',
    'fee_end_month': '3'
}, follow=True)
assert res_quick.status_code == 200
student.refresh_from_db()
assert student.status == 'MEDICAL_LEAVE'
assert student.fee_end_month == 3
assert student.get_status_display() == "ព្យួរការសិក្សាដោយជំងឺ"
assert student.status_badge_color == "warning"
print("[PASS] 4. POST /students/<id>/quick-status/ updated student status to 'MEDICAL_LEAVE' with fee_end_month=3!")

# 6. Test System Default Protection: Cannot delete system default status
active_stat = StudentStatusConfig.objects.get(code='ACTIVE')
res_del_default = client.post(f'/students/statuses/{active_stat.id}/delete/', follow=True)
assert res_del_default.status_code == 200
assert StudentStatusConfig.objects.filter(code='ACTIVE').exists()
print("[PASS] 5. System Default status protection verified (cannot delete ACTIVE)!")

# 7. Test In-Use Protection: Cannot delete custom status while assigned to students
res_del_used = client.post(f'/students/statuses/{med_stat.id}/delete/', follow=True)
assert res_del_used.status_code == 200
assert StudentStatusConfig.objects.filter(code='MEDICAL_LEAVE').exists()
print("[PASS] 6. In-use protection verified (cannot delete MEDICAL_LEAVE while student is assigned)!")

# 8. Reset student status and delete custom status
student.status = 'ACTIVE'
student.fee_end_month = None
student.save()

res_del_free = client.post(f'/students/statuses/{med_stat.id}/delete/', follow=True)
assert res_del_free.status_code == 200
assert not StudentStatusConfig.objects.filter(code='MEDICAL_LEAVE').exists()
print("[PASS] 7. POST /students/statuses/<id>/delete/ successfully deleted unused custom status!")

# 9. Verify Student List View renders with dynamic status dropdown and badges
res_stu_list = client.get('/students/')
assert res_stu_list.status_code == 200
html_stu = res_stu_list.content.decode('utf-8')
assert 'ស្ថានភាពសិក្សា' in html_stu
assert 'quickStatusModal' in html_stu
print("[PASS] 8. GET /students/ rendered dynamic status filter and quick status modal!")

# Cleanup
Student.objects.filter(student_id="STU_STAT_01").delete()
print("\n=== ALL STUDENT STATUS MANAGEMENT TESTS PASSED 100%! ===")
