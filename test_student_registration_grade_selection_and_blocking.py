import os
import sys
import django
import json

sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from django.test.utils import setup_test_environment
from apps.accounts.models import SchoolProfile, User
from apps.academics.models import AcademicYear, Classroom, GradeLevel
from apps.students.models import Student

setup_test_environment()

def run_tests():
    print("=== STARTING STUDENT REGISTRATION GRADE SELECTION & BLOCKING TESTS ===")
    client = Client()

    profile = SchoolProfile.get_settings()
    profile.is_registration_open = True
    profile.registration_start_date = None
    profile.registration_end_date = None
    profile.save()

    acad_year = AcademicYear.objects.filter(is_current=True).first() or AcademicYear.objects.first()
    if not acad_year:
        acad_year = AcademicYear.objects.create(name='2025-2026', is_current=True)

    # 1. Setup Grade 7 (Allowed/Open) and Grade 8 (Disallowed/Closed)
    gl7, _ = GradeLevel.objects.get_or_create(grade_number=7, track='GENERAL', defaults={'name': 'ថ្នាក់ទី ៧', 'order': 1})
    gl7.is_registration_open = True
    gl7.registration_closed_message = ''
    gl7.save()

    gl8, _ = GradeLevel.objects.get_or_create(grade_number=8, track='GENERAL', defaults={'name': 'ថ្នាក់ទី ៨', 'order': 2})
    gl8.is_registration_open = False
    gl8.registration_closed_message = 'ការចុះឈ្មោះសម្រាប់ថ្នាក់ទី ៨ ត្រូវបានបិទ!'
    gl8.save()

    cls7 = Classroom.objects.filter(grade_level=7, academic_year=acad_year).first()
    if not cls7:
        cls7 = Classroom.objects.create(name='7A', code='7A', grade_level=7, academic_year=acad_year)

    cls8 = Classroom.objects.filter(grade_level=8, academic_year=acad_year).first()
    if not cls8:
        cls8 = Classroom.objects.create(name='8A', code='8A', grade_level=8, academic_year=acad_year)

    print("\n--- 1. Testing Web Portal Grade Level Selection & Visibility ---")
    # Public non-staff user visits /students/enroll/online/
    resp_portal = client.get('/students/enroll/online/')
    assert resp_portal.status_code == 200
    content_str = resp_portal.content.decode('utf-8')

    # Verify Grade Level selector exists in Portal
    assert 'portal_grade_level' in content_str, "Step 1 Grade Level select 'portal_grade_level' must exist"
    assert 'ជំហានទី ១៖ ជ្រើសរើសកម្រិតថ្នាក់' in content_str, "Step 1 label must exist"
    assert 'ជំហានទី ២៖ ជ្រើសរើសបន្ទប់/ថ្នាក់រៀន' in content_str, "Step 2 Classroom label must exist"

    # Verify available_grade_levels in context ONLY includes open grades (Grade 7), NOT Grade 8
    avail_grades = list(resp_portal.context['available_grade_levels'])
    assert gl7 in avail_grades, "Open Grade 7 must be in available_grade_levels"
    assert gl8 not in avail_grades, "Closed Grade 8 must NOT be in available_grade_levels"
    print("  [PASS] Context available_grade_levels includes open Grade 7 and excludes closed Grade 8")

    # In HTML options, Grade 7 should appear in the <select id="portal_grade_level">, Grade 8 must NOT be an option
    # Verify Grade 8 option is not present in the portal grade select
    assert f'value="{gl7.grade_number}"' in content_str
    # Find options within portal_grade_level
    select_snippet = content_str.split('id="portal_grade_level"')[1].split('</select>')[0]
    assert 'ថ្នាក់ទី ៧' in select_snippet, "Grade 7 must be visible in portal_grade_level select"
    assert 'ថ្នាក់ទី ៨' not in select_snippet, "Closed Grade 8 must NOT be visible or selectable in portal_grade_level select"
    print("  [PASS] HTML portal_grade_level dropdown strictly hides closed Grade 8 from student applicants")

    # Verify portalClassroomsData JSON does NOT include Class 8A (from closed Grade 8)
    assert 'portalClassroomsData' in content_str
    json_snippet = content_str.split('id="portalClassroomsData"')[1].split('</script>')[0]
    json_start = json_snippet.find('[')
    json_end = json_snippet.rfind(']') + 1
    classrooms_json = json.loads(json_snippet[json_start:json_end])
    cls_ids = [c['id'] for c in classrooms_json]
    assert cls7.id in cls_ids, "Class 7A must be in portalClassroomsData"
    assert cls8.id not in cls_ids, "Class 8A of closed Grade 8 must NOT be in portalClassroomsData"
    print("  [PASS] portalClassroomsData JSON strictly excludes classrooms belonging to closed Grade 8")

    # ----------------- 2. Test Direct URL & POST Blocking for Closed Grade -----------------
    print("\n--- 2. Testing Direct URL Access & POST Submission Blocking ---")
    resp_direct_closed = client.get('/students/enroll/online/?grade=8')
    assert resp_direct_closed.status_code == 200
    assert any('registration_closed.html' in t.name for t in resp_direct_closed.templates if t.name)
    assert 'ថ្នាក់ទី ៨' in resp_direct_closed.content.decode('utf-8')
    print("  [PASS] Direct URL access ?grade=8 renders registration_closed.html")

    # Attempting to forge POST submission for closed Grade 8 classroom
    post_data_closed = {
        'khmer_name': 'កែវ វិបុល',
        'gender': 'M',
        'date_of_birth': '2010-01-01',
        'classroom': cls8.id,
        'academic_year': acad_year.id,
    }
    resp_post_closed = client.post('/students/enroll/online/', post_data_closed, follow=True)
    assert resp_post_closed.status_code == 200
    # Should redirect back with error or rejection
    assert Student.objects.filter(khmer_name='កែវ វិបុល').count() == 0
    print("  [PASS] Backend rejected POST registration attempt for closed Grade 8")

    # ----------------- 3. Test Mobile API Endpoints -----------------
    print("\n--- 3. Testing Mobile API Endpoints (Grade Selection & Disallowance) ---")
    resp_mobile_enroll = client.get('/api/v1/students/enroll/')
    assert resp_mobile_enroll.status_code == 200
    enroll_json = resp_mobile_enroll.json()

    assert 'grade_levels' in enroll_json, "Mobile enroll metadata must return grade_levels"
    assert 'available_grade_levels' in enroll_json, "Mobile enroll metadata must return available_grade_levels"

    avail_gl_ids = [g['id'] for g in enroll_json['available_grade_levels']]
    assert gl7.id in avail_gl_ids, "Open Grade 7 must be in mobile available_grade_levels"
    assert gl8.id not in avail_gl_ids, "Closed Grade 8 must NOT be in mobile available_grade_levels"
    print("  [PASS] Mobile available_grade_levels strictly filters out closed Grade 8")

    # Mobile POST for closed grade 8 -> 403 GRADE_CLOSED
    post_closed_mobile = {
        'khmer_name': 'សេង ហេង',
        'gender': 'M',
        'date_of_birth': '2010-06-01',
        'classroom_id': cls8.id,
        'grade_level': 8,
        'academic_year_id': acad_year.id,
    }
    resp_m_post_closed = client.post('/api/v1/students/enroll/', post_closed_mobile, content_type='application/json')
    assert resp_m_post_closed.status_code == 403
    assert resp_m_post_closed.json()['status_code'] == 'GRADE_CLOSED'
    print("  [PASS] Mobile POST for closed Grade 8 correctly blocked with 403 GRADE_CLOSED")

    # Mobile POST for open grade 7 -> 201 Created
    post_open_mobile = {
        'khmer_name': 'លឹម គឹមសួរ',
        'gender': 'M',
        'date_of_birth': '2011-04-12',
        'classroom_id': cls7.id,
        'grade_level': 7,
        'academic_year_id': acad_year.id,
    }
    resp_m_post_open = client.post('/api/v1/students/enroll/', post_open_mobile, content_type='application/json')
    assert resp_m_post_open.status_code == 201
    print("  [PASS] Mobile POST for open Grade 7 successfully registered (201 Created)")

    # ----------------- 4. Test Re-opening Grade 8 -----------------
    print("\n--- 4. Testing Admin Re-opening Grade 8 ---")
    gl8.is_registration_open = True
    gl8.save()

    resp_portal_reopened = client.get('/students/enroll/online/')
    reopened_snippet = resp_portal_reopened.content.decode('utf-8').split('id="portal_grade_level"')[1].split('</select>')[0]
    assert 'ថ្នាក់ទី ៨' in reopened_snippet, "Re-opened Grade 8 must now be visible in portal_grade_level"
    print("  [PASS] Portal immediately shows Grade 8 when admin allows it")

    resp_mobile_reopened = client.get('/api/v1/students/enroll/')
    reopened_m_avail_ids = [g['id'] for g in resp_mobile_reopened.json()['available_grade_levels']]
    assert gl8.id in reopened_m_avail_ids, "Re-opened Grade 8 must now be in mobile available_grade_levels"
    print("  [PASS] Mobile API immediately includes Grade 8 when admin allows it")

    # Clean up test student
    Student.objects.filter(khmer_name__in=['លឹម គឹមសួរ', 'កែវ វិបុល', 'សេង ហេង']).delete()

    print("\n=======================================================")
    print(" ALL STUDENT REGISTRATION GRADE SELECTION TESTS PASSED (100%)!")
    print("=======================================================")

if __name__ == '__main__':
    run_tests()
