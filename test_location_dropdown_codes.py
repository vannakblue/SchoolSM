import os
import sys
import django

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from django.urls import reverse
from apps.academics.models import Province, District, Commune, Village


def test_location_dropdown_codes():
    print("=== STARTING LOCATION DROPDOWN CODES VERIFICATION ===")
    client = Client()

    # 1. Test Provinces API
    res_prov = client.get(reverse('api_locations_provinces'))
    assert res_prov.status_code == 200, "Provinces API should return 200"
    data_prov = res_prov.json()
    assert data_prov['status'] == 'success'
    provinces = data_prov['data']
    assert len(provinces) > 0, "Should return provinces"
    
    first_prov = provinces[0]
    assert 'code' in first_prov and 'name_kh' in first_prov, "Province object must have code and name_kh"
    print(f"  [PASS] 1. Provinces API returned {len(provinces)} provinces. Sample: [{first_prov['code']}] {first_prov['name_kh']}")

    # 2. Test Districts API
    p_id = first_prov['id']
    res_dist = client.get(f"{reverse('api_locations_districts')}?province_id={p_id}")
    assert res_dist.status_code == 200
    data_dist = res_dist.json()
    districts = data_dist['data']
    assert len(districts) > 0, "Should return districts for province"
    first_dist = districts[0]
    assert 'code' in first_dist and 'name_kh' in first_dist
    print(f"  [PASS] 2. Districts API returned {len(districts)} districts. Sample: [{first_dist['code']}] {first_dist['name_kh']}")

    # 3. Test Communes API
    d_id = first_dist['id']
    res_comm = client.get(f"{reverse('api_locations_communes')}?district_id={d_id}")
    assert res_comm.status_code == 200
    data_comm = res_comm.json()
    communes = data_comm['data']
    assert len(communes) > 0, "Should return communes for district"
    first_comm = communes[0]
    assert 'code' in first_comm and 'name_kh' in first_comm
    print(f"  [PASS] 3. Communes API returned {len(communes)} communes. Sample: [{first_comm['code']}] {first_comm['name_kh']}")

    # 4. Test Villages API
    c_id = first_comm['id']
    res_vill = client.get(f"{reverse('api_locations_villages')}?commune_id={c_id}")
    assert res_vill.status_code == 200
    data_vill = res_vill.json()
    villages = data_vill['data']
    if villages:
        first_vill = villages[0]
        print(f"  [PASS] 4. Villages API returned {len(villages)} villages. Sample: [{first_vill['code']}] {first_vill['name_kh']}")
    else:
        print(f"  [PASS] 4. Villages API returned 0 villages for commune {first_comm['name_kh']}.")

    print("=== ALL LOCATION DROPDOWN CODES TESTS PASSED 100% ===")


if __name__ == '__main__':
    test_location_dropdown_codes()
