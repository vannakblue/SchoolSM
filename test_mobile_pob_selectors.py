import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from rest_framework.test import APIClient
from apps.academics.models import Province, District, Commune, AcademicYear, Classroom
from apps.students.models import Student

def test_mobile_locations_api():
    client = APIClient()

    # 1. Unauthenticated provinces fetch
    res_prov = client.get('/api/v1/locations/provinces/')
    assert res_prov.status_code == 200, f"Expected 200, got {res_prov.status_code}"
    provinces = res_prov.data.get('data', [])
    assert len(provinces) == 25, f"Expected 25 provinces, got {len(provinces)}"
    print(f"Provinces API check passed: {len(provinces)} provinces returned.")

    target_prov = provinces[0]
    prov_id = target_prov['id']

    # 2. Districts for province
    res_dist = client.get(f'/api/v1/locations/districts/?province_id={prov_id}')
    assert res_dist.status_code == 200
    districts = res_dist.data.get('data', [])
    assert len(districts) > 0, "Expected at least 1 district"
    print(f"Districts API check passed: {len(districts)} districts for prov {prov_id}.")

    target_dist = districts[0]
    dist_id = target_dist['id']

    # 3. Communes for district
    res_comm = client.get(f'/api/v1/locations/communes/?district_id={dist_id}')
    assert res_comm.status_code == 200
    communes = res_comm.data.get('data', [])
    assert len(communes) > 0, "Expected at least 1 commune"
    print(f"Communes API check passed: {len(communes)} communes for dist {dist_id}.")

    # 4. Test Student Enrollment with selected POB fields in MoEYS mode
    current_year = AcademicYear.objects.filter(is_current=True).first() or AcademicYear.objects.first()
    classroom = Classroom.objects.filter(academic_year=current_year).first()

    payload = {
        'enrollment_mode': 'MOEYS_INDIVIDUAL',
        'surname': 'មាស',
        'given_name': 'សុភ័ក្ត្រ',
        'khmer_name': 'មាស សុភ័ក្ត្រ',
        'latin_name': 'MEAS SOPHEAK',
        'gender': 'M',
        'date_of_birth': '2010-05-15',
        'phone': '012998877',
        'pob_province': target_prov['name_kh'],
        'pob_district': target_dist['name_kh'],
        'pob_commune': communes[0]['name_kh'],
        'place_of_birth': f"{communes[0]['name_kh']}, {target_dist['name_kh']}, {target_prov['name_kh']}",
        'current_address': f"{communes[0]['name_kh']}, {target_dist['name_kh']}, {target_prov['name_kh']}",
        'classroom_id': classroom.id if classroom else None,
        'academic_year_id': current_year.id if current_year else None,
        'scholarship_type': 'FULL_PAY',
    }

    res_enroll = client.post('/api/v1/students/enroll/', payload, format='json')
    assert res_enroll.status_code in [200, 201], f"Enrollment failed: {res_enroll.data}"
    stu_id = res_enroll.data['student']['student_id']
    student = Student.objects.get(student_id=stu_id)

    assert student.place_of_birth == payload['place_of_birth'], f"Expected {payload['place_of_birth']}, got {student.place_of_birth}"
    assert student.enrollment_data.get('pob_province') == target_prov['name_kh']
    assert student.enrollment_data.get('pob_district') == target_dist['name_kh']
    assert student.enrollment_data.get('pob_commune') == communes[0]['name_kh']

    safe_pob = student.place_of_birth.encode('ascii', 'backslashreplace').decode('ascii')
    print(f"Enrollment test passed: Student {student.student_id} saved with POB: {safe_pob}")

    # Clean up test student
    student.delete()
    print("All tests passed successfully!")

if __name__ == '__main__':
    test_mobile_locations_api()
