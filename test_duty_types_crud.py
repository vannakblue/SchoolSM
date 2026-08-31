import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.academics.models import TeacherDutyType, TeacherDutySchedule, AcademicYear
from apps.teachers.models import Teacher

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

def run_duty_types_test():
    print("=======================================================")
    print("[*] TESTING DYNAMIC DUTY TYPES CRUD & INTEGRATION")
    print("=======================================================")

    # 1. Ensure Admin User
    admin_user, _ = User.objects.get_or_create(
        username='admin',
        defaults={'role': User.Role.ADMIN, 'is_staff': True, 'is_superuser': True}
    )
    admin_user.set_password('1627')
    admin_user.role = User.Role.ADMIN
    admin_user.is_staff = True
    admin_user.save()

    client = Client()
    client.force_login(admin_user)

    # 2. Test Duty Types List API
    res = client.get('/academics/duty-schedule/types/')
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    data = res.json()
    assert data['status'] == 'success'
    initial_count = len(data['duty_types'])
    print(f"✅ 1. Initial Duty Types listed: {initial_count} types found.")

    # 3. Test Create New Duty Type
    new_type_data = {
        'name': 'ប្រចាំការខ្លោងទ្វារ និងសន្តិសុខ',
        'icon': 'fa-shield-halved',
        'color': '#ef4444'
    }
    res_create = client.post(
        '/academics/duty-schedule/types/create/',
        data=new_type_data,
        content_type='application/json'
    )
    assert res_create.status_code == 200, f"Create failed: {res_create.content}"
    create_data = res_create.json()
    assert create_data['status'] == 'success'
    created_id = create_data['duty_type']['id']
    created_code = create_data['duty_type']['code']
    print(f"✅ 2. Created New Duty Type: ID={created_id}, Name='{create_data['duty_type']['name']}', Code='{created_code}'")

    # 4. Test Edit Duty Type
    edit_data = {
        'name': 'ប្រចាំការខ្លោងទ្វារធំ និងសណ្តាប់ធ្នាប់',
        'icon': 'fa-door-open',
        'color': '#ec4899'
    }
    res_edit = client.post(
        f'/academics/duty-schedule/types/{created_id}/edit/',
        data=edit_data,
        content_type='application/json'
    )
    assert res_edit.status_code == 200
    edit_res = res_edit.json()
    assert edit_res['status'] == 'success'
    assert edit_res['duty_type']['name'] == 'ប្រចាំការខ្លោងទ្វារធំ និងសណ្តាប់ធ្នាប់'
    assert edit_res['duty_type']['icon'] == 'fa-door-open'
    print(f"✅ 3. Edited Duty Type successfully: Updated Name='{edit_res['duty_type']['name']}'")

    # 5. Test Teacher Duty Manager Page renders properly with new types
    res_page = client.get('/academics/duty-schedule/')
    assert res_page.status_code == 200
    assert 'dutyTypeManagerModal' in res_page.content.decode('utf-8')
    assert 'ប្រចាំការខ្លោងទ្វារធំ និងសណ្តាប់ធ្នាប់' in res_page.content.decode('utf-8')
    print("✅ 4. Teacher Duty Manager HTML page contains Duty Type Manager Modal and updated types.")

    # 6. Test Delete Duty Type
    res_del = client.post(f'/academics/duty-schedule/types/{created_id}/delete/')
    assert res_del.status_code == 200
    del_data = res_del.json()
    assert del_data['status'] == 'success'
    assert not TeacherDutyType.objects.filter(id=created_id).exists()
    print(f"✅ 5. Deleted Duty Type successfully: {del_data['message']}")

    print("\n🎉 ALL DYNAMIC DUTY TYPE CRUD TESTS PASSED 100%!")

if __name__ == '__main__':
    run_duty_types_test()
