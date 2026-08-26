import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from datetime import date
from django.test import RequestFactory
from apps.academics.models import AcademicYear, Classroom, GradeLevel, GradeEnrollmentOption
from apps.students.models import Student, ScholarshipType
from apps.students.forms import StudentEnrollmentForm
from apps.students.views import api_get_grade_options, _extract_grade_options

def run_tests():
    print("=== STARTING ENROLLMENT FEATURES TEST SUITE ===")
    
    # 1. Setup Academic Years and Classrooms
    y25, _ = AcademicYear.objects.get_or_create(name='2025-2026', defaults={'start_date': date(2025, 10, 1), 'end_date': date(2026, 7, 31), 'is_current': False})
    y26, _ = AcademicYear.objects.get_or_create(name='2026-2027', defaults={'start_date': date(2026, 10, 1), 'end_date': date(2027, 7, 31), 'is_current': True})
    
    c_25_7a, _ = Classroom.objects.get_or_create(code='7A-25', defaults={'name': 'ថ្នាក់ទី ៧A [2025-2026]', 'grade_level': 7, 'track': 'GENERAL', 'academic_year': y25})
    c_26_7a, _ = Classroom.objects.get_or_create(code='7A-26', defaults={'name': 'ថ្នាក់ទី ៧A [2026-2027]', 'grade_level': 7, 'track': 'GENERAL', 'academic_year': y26})
    c_26_10a, _ = Classroom.objects.get_or_create(code='10A-26', defaults={'name': 'ថ្នាក់ទី ១០A [2026-2027]', 'grade_level': 10, 'track': 'GENERAL', 'academic_year': y26})
    c_26_11sci, _ = Classroom.objects.get_or_create(code='11SCI-26', defaults={'name': 'ថ្នាក់ទី ១១ វិទ្យាសាស្ត្រ [2026-2027]', 'grade_level': 11, 'track': 'SCIENCE', 'academic_year': y26})

    # Test 1: Strict Academic Year Isolation in Form
    form_26 = StudentEnrollmentForm(academic_year=y26)
    c_26_ids = set(form_26.fields['classroom'].queryset.values_list('id', flat=True))
    assert c_26_7a.id in c_26_ids, "Classroom from 2026-2027 should be present"
    assert c_26_10a.id in c_26_ids, "Classroom from 2026-2027 should be present"
    assert c_25_7a.id not in c_26_ids, "Classroom from 2025-2026 MUST NOT be present in 2026-2027 form"
    print("[PASS] 1. Strict Academic Year Isolation: Form strictly shows ONLY active year classrooms!")

    # Test 2: Dynamic Scholarship Types CRUD & Choices
    st_custom, _ = ScholarshipType.objects.get_or_create(
        code='TEST_SAMDECH_TECHO',
        defaults={
            'name': 'អាហារូបករណ៍សម្តេចតេជោ (១០០%)',
            'discount_percentage': 100.0,
            'description': 'សម្រាប់សិស្សឆ្នើម',
            'is_active': True,
            'order': 10
        }
    )
    
    form_sch = StudentEnrollmentForm(academic_year=y26)
    sch_codes = [c[0] for c in form_sch.fields['scholarship_type'].choices]
    assert 'TEST_SAMDECH_TECHO' in sch_codes, "Dynamic scholarship type must appear in form choices"

    # Create student with custom scholarship
    s = Student.objects.create(
        khmer_name='តេស្ត សិស្សអាហារូបករណ៍',
        latin_name='TEST SCHOLARSHIP STUDENT',
        gender=Student.Gender.MALE,
        date_of_birth=date(2010, 5, 15),
        classroom=c_26_11sci,
        academic_year=y26,
        scholarship_type='TEST_SAMDECH_TECHO'
    )
    assert s.scholarship_name == 'អាហារូបករណ៍សម្តេចតេជោ (១០០%)'
    assert s.scholarship_discount_percentage == 100.0
    print("[PASS] 2. Dynamic Admin Scholarship Types: Correctly created, populated in form, and resolved on Student!")

    # Test 3: Grade-Level Specific Options (Custom Fields)
    gl_7, _ = GradeLevel.objects.get_or_create(grade_number=7, track='GENERAL', defaults={'name': 'ថ្នាក់ទី ៧', 'order': 1})
    gl_11, _ = GradeLevel.objects.get_or_create(grade_number=11, track='SCIENCE', defaults={'name': 'ថ្នាក់ទី ១១ វិទ្យាសាស្ត្រ', 'order': 5})

    opt_primary, _ = GradeEnrollmentOption.objects.get_or_create(
        grade_level=gl_7,
        field_name='primary_school',
        defaults={
            'label': 'ឈ្មោះសាលាបឋមសិក្សាដើម',
            'field_type': 'TEXT',
            'is_required': True,
            'order': 1
        }
    )
    opt_lang, _ = GradeEnrollmentOption.objects.get_or_create(
        grade_level=gl_7,
        field_name='foreign_language',
        defaults={
            'label': 'ភាសាបរទេសទី១',
            'field_type': 'SELECT',
            'choices': 'ភាសាអង់គ្លេស, ភាសាបារាំង',
            'is_required': False,
            'order': 2
        }
    )

    opt_diploma, _ = GradeEnrollmentOption.objects.get_or_create(
        grade_level=gl_11,
        field_name='diploma_grade',
        defaults={
            'label': 'និទ្ទេសប្រឡងឌីប្លូម',
            'field_type': 'SELECT',
            'choices': 'និទ្ទេស A, និទ្ទេស B, និទ្ទេស C, និទ្ទេស D, និទ្ទេស E',
            'is_required': True,
            'order': 1
        }
    )

    # Test API for Grade 7 Classroom
    rf = RequestFactory()
    req_7 = rf.get(f'/students/api/grade-options/?classroom_id={c_26_7a.id}')
    resp_7 = api_get_grade_options(req_7)
    import json
    data_7 = json.loads(resp_7.content)
    assert data_7['status'] == 'success'
    field_names_7 = [item['field_name'] for item in data_7['data']]
    assert 'primary_school' in field_names_7
    assert 'foreign_language' in field_names_7
    assert 'diploma_grade' not in field_names_7
    print("[PASS] 3. Grade-Level Options API: Correctly returned Grade 7 custom options!")

    # Test 4: Rich Field Types and Formats (Date, Time, DateTime, Phone, Email, Radio, MultiSelect, Section, etc.)
    opt_date, _ = GradeEnrollmentOption.objects.update_or_create(
        grade_level=gl_7,
        field_name='entry_date',
        defaults={'label': 'កាលបរិច្ឆេទចូលរៀន', 'field_type': 'DATE', 'col_width': 6, 'order': 3}
    )
    opt_time, _ = GradeEnrollmentOption.objects.update_or_create(
        grade_level=gl_7,
        field_name='preferred_time',
        defaults={'label': 'ម៉ោងសិក្សាពេញចិត្ត', 'field_type': 'TIME', 'col_width': 4, 'order': 4}
    )
    opt_radio, _ = GradeEnrollmentOption.objects.update_or_create(
        grade_level=gl_7,
        field_name='study_shift',
        defaults={'label': 'វេនសិក្សា', 'field_type': 'RADIO', 'choices': 'វេនព្រឹក, វេនរសៀល', 'col_width': 6, 'order': 5}
    )
    opt_multi, _ = GradeEnrollmentOption.objects.update_or_create(
        grade_level=gl_7,
        field_name='extracurricular',
        defaults={'label': 'សកម្មភាពក្រៅម៉ោងសិក្សា', 'field_type': 'MULTISELECT', 'choices': 'កីឡាបាល់ទាត់, តន្ត្រី, គំនូរ, កុំព្យូទ័រ', 'col_width': 12, 'order': 6}
    )
    opt_section, _ = GradeEnrollmentOption.objects.update_or_create(
        grade_level=gl_7,
        field_name='health_sec',
        defaults={'label': 'ផ្នែកព័ត៌មានសុខភាពសិស្ស', 'field_type': 'SECTION', 'col_width': 12, 'order': 7}
    )

    # Test API returns all rich types and col_width
    resp_7 = api_get_grade_options(req_7)
    data_7 = json.loads(resp_7.content)
    opts_map = {item['field_name']: item for item in data_7['data']}
    assert opts_map['entry_date']['field_type'] == 'DATE' and opts_map['entry_date']['col_width'] == 6
    assert opts_map['preferred_time']['field_type'] == 'TIME' and opts_map['preferred_time']['col_width'] == 4
    assert opts_map['study_shift']['field_type'] == 'RADIO' and 'វេនព្រឹក' in opts_map['study_shift']['choices']
    assert opts_map['extracurricular']['field_type'] == 'MULTISELECT' and opts_map['extracurricular']['col_width'] == 12
    assert opts_map['health_sec']['field_type'] == 'SECTION'
    print("[PASS] 4. Rich Field Formats: Date, Time, Radio, MultiSelect, Section Header & Widths verified via API!")

    # Test 5: Drag & Drop Reorder API
    from apps.academics.views import grade_options_reorder, grade_option_update_width
    from apps.accounts.models import User

    admin_user = User.objects.filter(role=User.Role.ADMIN).first()
    if not admin_user:
        admin_user = User.objects.create_user(username='test_admin_reorder', password='password', role=User.Role.ADMIN)

    # Reorder IDs in reverse
    new_order_ids = [opt_section.id, opt_multi.id, opt_radio.id, opt_time.id, opt_date.id, opt_lang.id, opt_primary.id]
    reorder_req = rf.post('/academics/grade-options/reorder/', data=json.dumps({'ordered_ids': new_order_ids}), content_type='application/json')
    reorder_req.user = admin_user
    reorder_resp = grade_options_reorder(reorder_req)
    assert reorder_resp.status_code == 200
    opt_section.refresh_from_db()
    opt_primary.refresh_from_db()
    assert opt_section.order == 1, "opt_section should now be order 1"
    assert opt_primary.order == 7, "opt_primary should now be order 7"
    print("[PASS] 5. Drag & Drop Reorder API: Successfully reordered options in database!")

    # Test 6: Column Width Update API
    width_req = rf.post(f'/academics/grade-options/{opt_date.id}/width/', data=json.dumps({'col_width': 12}), content_type='application/json')
    width_req.user = admin_user
    width_resp = grade_option_update_width(width_req, pk=opt_date.id)
    assert width_resp.status_code == 200
    opt_date.refresh_from_db()
    assert opt_date.col_width == 12, "col_width should be updated to 12"
    print("[PASS] 6. Column Width Update API: Successfully updated column width (100% full width)!")

    # Test 7: Multi-Select Extraction & Saving
    from django.http import QueryDict
    qd = QueryDict('', mutable=True)
    qd.setlist('grade_opt_extracurricular', ['កីឡាបាល់ទាត់', 'កុំព្យូទ័រ'])
    qd['grade_opt_entry_date'] = '2026-09-01'
    qd['grade_opt_preferred_time'] = '08:00'
    qd['grade_opt_study_shift'] = 'វេនព្រឹក'

    multi_req = rf.post('/students/enroll/')
    multi_req.POST = qd
    extracted_multi = _extract_grade_options(multi_req, c_26_7a)
    assert 'extracurricular' in extracted_multi
    assert extracted_multi['extracurricular']['value'] == 'កីឡាបាល់ទាត់, កុំព្យូទ័រ'
    assert extracted_multi['entry_date']['value'] == '2026-09-01'
    assert extracted_multi['preferred_time']['value'] == '08:00'
    assert extracted_multi['study_shift']['value'] == 'វេនព្រឹក'
    print("[PASS] 7. Rich Form Data Extraction: Successfully extracted Date, Time, Radio, and MultiSelect values!")

    # Clean up test records
    s.delete()
    st_custom.delete()
    print("\nALL ENROLLMENT & RICH FIELD FORMATS & DRAG-AND-DROP TESTS PASSED 100%!")

if __name__ == '__main__':
    run_tests()
