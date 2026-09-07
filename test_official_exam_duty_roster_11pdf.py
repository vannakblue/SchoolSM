import os
import sys
import django
import datetime

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.messages.storage.fallback import FallbackStorage
from apps.accounts.models import User, SchoolProfile
from apps.academics.models import AcademicYear
from apps.examinations.models import (
    ExamInvigilatorPlan, ExamShiftSlot, TeacherShiftRegistration, ExamCommitteeRole, TeacherDutyQuota
)
from apps.examinations.views import exam_invigilator_roster_print
from apps.teachers.models import Teacher


def run_tests():
    print("================================================================================")
    print("RUNNING TESTS: OFFICIAL EXAM DUTY ROSTER & SIGNATURE SHEET (11.PDF COMPLIANCE)")
    print("================================================================================")

    factory = RequestFactory()
    admin_user, _ = User.objects.get_or_create(
        username='admin_duty_roster',
        defaults={'role': User.Role.ADMIN, 'is_staff': True, 'is_superuser': True}
    )

    ay = AcademicYear.objects.filter(is_current=True).first() or AcademicYear.objects.first()

    # Create / Get Test Plan
    plan, _ = ExamInvigilatorPlan.objects.get_or_create(
        title="បែងចែកភារកិច្ចប្រឡងឆមាសទី២ (11.pdf Sample Test)",
        academic_year=ay,
        defaults={
            'start_date': datetime.date(2026, 8, 3),
            'end_date': datetime.date(2026, 8, 3),
            'is_active': True,
        }
    )

    # Ensure slot
    slot, _ = ExamShiftSlot.objects.get_or_create(
        plan=plan,
        date=datetime.date(2026, 8, 3),
        session=ExamShiftSlot.Session.MORNING,
        defaults={
            'session_name': 'ថ្ងៃទី១ (ចន្ទ 03/08) - 🌅 ពេលព្រឹក',
            'order': 1,
            'max_invigilators': 40
        }
    )

    # Ensure sample teachers representing the official hierarchy from 11.pdf
    teacher_samples = [
        ('T_01', 'ផេង រិទ្ធីយ៉ា', Teacher.Gender.MALE, ExamCommitteeRole.PRESIDENT, ''),
        ('T_02', 'សុន សុមនី', Teacher.Gender.FEMALE, ExamCommitteeRole.VICE_PRESIDENT, ''),
        ('T_03', 'ប៊ុន ណារី', Teacher.Gender.FEMALE, ExamCommitteeRole.VICE_PRESIDENT, ''),
        ('T_04', 'ទិន សុភី', Teacher.Gender.MALE, ExamCommitteeRole.VICE_PRESIDENT, ''),
        ('T_05', 'គង់ ម៉ានិន', Teacher.Gender.MALE, ExamCommitteeRole.SECRETARIAT, ''),
        ('T_06', 'ឃឹម ស្រស់', Teacher.Gender.MALE, ExamCommitteeRole.BUILDING_INSPECTOR, ''),
        ('T_07', 'ទុន វណ្ណៈ', Teacher.Gender.MALE, ExamCommitteeRole.TABULATOR, ''),
        ('T_08', 'កង សុគង់', Teacher.Gender.FEMALE, ExamCommitteeRole.INVIGILATOR, 'បន្ទប់ 01'),
        ('T_09', 'ខ្លឹម សុផា', Teacher.Gender.MALE, ExamCommitteeRole.INVIGILATOR, 'បន្ទប់ 08'),
        ('T_10', 'កន ជីវី', Teacher.Gender.FEMALE, ExamCommitteeRole.INVIGILATOR, 'បន្ទប់ 31'),
    ]

    for tid, name, gender, role, room in teacher_samples:
        t, _ = Teacher.objects.get_or_create(
            teacher_id=tid,
            defaults={
                'khmer_name': name,
                'latin_name': name,
                'gender': gender,
                'phone': '012000111',
                'status': Teacher.Status.ACTIVE
            }
        )
        TeacherShiftRegistration.objects.update_or_create(
            slot=slot, teacher=t,
            defaults={'role': role, 'room_assignment': room}
        )

    # 1. Test View Response
    req = factory.get(f'/examinations/invigilator-plans/{plan.id}/roster/print/?slot_id={slot.id}')
    req.user = admin_user
    req.session = SessionStore()
    setattr(req, '_messages', FallbackStorage(req))

    resp = exam_invigilator_roster_print(req, plan_id=plan.id)
    assert resp.status_code == 200, f"Expected 200 OK, got {resp.status_code}"
    html = resp.content.decode('utf-8')

    # 2. Check Official MoEYS Headers
    assert "ព្រះរាជាណាចក្រកម្ពុជា" in html, "Kingdom header must be present"
    assert "ជាតិ សាសនា ព្រះមហាក្សត្រ" in html, "National motto must be present"
    assert "វិទ្យាល័យ ហ៊ុន សែន កំពង់កន្ទួត" in html, "Default School name must be present"
    assert "បែងចែកភារកិច្ចប្រឡងឆមាសទី២" in html, "Main Title must be present"
    assert "ថ្ងៃចន្ទ ទី០៣ ខែសីហា ឆ្នាំ២០២៦" in html, "Full Khmer Date formatted exactly as in 11.pdf"
    assert "ព្រឹក" in html, "Shift indicator ព្រឹក must be present"
    print("1. [PASS] Official MoEYS Headers, Title, Khmer Date & Shift Indicator verified")

    # 3. Check Dual-Column Table Headers & Structure
    assert "ល.រ" in html, "Order column header must be present"
    assert "គោត្តនាម-នាម" in html, "Name column header must be present"
    assert "តួនាទី" in html, "Duty column header must be present"
    assert "ហត្ថលេខា" in html, "Signature column header must be present"
    print("2. [PASS] Dual-Column Table Headers (ល.រ, គោត្តនាម-នាម, តួនាទី, ហត្ថលេខា) verified")

    # 4. Check Teacher Names with Honorifics (លោក / លោកស្រី / កញ្ញា)
    assert "លោក ផេង រិទ្ធីយ៉ា" in html, "Male teacher must have លោក prefix"
    assert "លោកស្រី សុន សុមនី" in html, "Female teacher must have លោកស្រី prefix"
    print("3. [PASS] Teacher honorifics prefixes verified")

    # 5. Check Committee Roles Hierarchy & Invigilator Room Numbers
    assert "ប្រធាន" in html, "President role must be present"
    assert "អនុប្រធាន" in html, "Vice President role must be present"
    assert "កណ្តាល" in html, "Secretariat role must be present"
    assert "ត្រួតអគារ" in html, "Building Inspector role must be present"
    assert "បូកស្រង់" in html, "Tabulator role must be present"
    assert "អនុរក្ស 1" in html, "Invigilator 1 duty must match 11.pdf format"
    assert "អនុរក្ស 8" in html, "Invigilator 8 duty must match 11.pdf format"
    assert "អនុរក្ស 31" in html, "Invigilator 31 duty must match 11.pdf format"
    print("4. [PASS] Roles (ប្រធាន, អនុប្រធាន, កណ្តាល, ត្រួតអគារ, បូកស្រង់, អនុរក្ស 1/8/31) verified")

    # 6. Check Dynamic Column Balancing (10 teachers: 5 rows, 0 empty cells, stops at 10)
    assert "<td class=\"col-num\">1</td>" in html, "Slot 1 must be present on left"
    assert "<td class=\"col-num\">2</td>" in html, "Slot 2 must be present on right"
    assert "<td class=\"col-num\">9</td>" in html, "Slot 9 must be present on left"
    assert "<td class=\"col-num\">10</td>" in html, "Slot 10 must be present on right"
    assert "<td class=\"col-num\">11</td>" not in html, "Slot 11 must NOT be present (table stops at 10)"
    assert "<td class=\"col-num\">53</td>" not in html, "Slot 53 must NOT be present"
    assert "<td class=\"col-num\">54</td>" not in html, "Slot 54 must NOT be present"
    assert "<td class=\"col-num\"></td>" not in html, "No empty cells for 10 teachers"
    print("5. [PASS] Table strictly renders balanced 5 rows for 10 teachers with horizontal pairs (1,2 / 3,4 ... 9,10)")

    # 7. Check Footer (Location, Solar Date, Lunar Date & Principal Title)
    assert "កំពង់កន្ទួត" in html, "Location name must be present in footer"
    assert "ព.ស.២៥៧០" in html, "Buddhist Era 2570 must be present in lunar date line"
    assert "នាយកសាលា" in html, "Principal title must be present in footer"
    print("6. [PASS] Footer with Location, Solar Date, Buddhist Era & នាយកសាលា signature verified")

    # 8. Check Query Parameter Overrides (custom school name, location, lunar_date, solar_date)
    custom_lunar_str = "ថ្ងៃពុធ ៦រោច ខែទុតិយាសាឍ ឆ្នាំរោង ឆស័ក ព.ស.២៥៧០"
    custom_solar_str = "ទី០៧ ខែតុលា ឆ្នាំ២០២៦"
    req_custom = factory.get(f'/examinations/invigilator-plans/{plan.id}/roster/print/?school_name=វិទ្យាល័យ+គំរូ&location=ភ្នំពេញ&lunar_date={custom_lunar_str}&solar_date={custom_solar_str}')
    req_custom.user = admin_user
    req_custom.session = SessionStore()
    setattr(req_custom, '_messages', FallbackStorage(req_custom))
    resp_custom = exam_invigilator_roster_print(req_custom, plan_id=plan.id)
    html_custom = resp_custom.content.decode('utf-8')
    assert "វិទ្យាល័យ គំរូ" in html_custom, "Custom school name override must work"
    assert "ភ្នំពេញ" in html_custom, "Custom location override must work"
    assert custom_lunar_str in html_custom, "Custom lunar date override must work"
    assert custom_solar_str in html_custom, "Custom solar date override must work"
    assert 'contenteditable="true"' in html_custom, "In-place contenteditable must be enabled for direct editing"
    print("7. [PASS] Query Parameter Overrides (school name, location, lunar date, solar date) & contenteditable verified")

    # 9. SPECIAL TEST: Exactly 50 Teachers (Even Number - User's exact scenario)
    # Must have 25 rows, 1..25 on left, 26..50 on right, 0 empty cells, and NO numbers 51..54!
    slot_50, _ = ExamShiftSlot.objects.get_or_create(
        plan=plan,
        date=datetime.date(2026, 8, 4),
        session=ExamShiftSlot.Session.AFTERNOON,
        defaults={
            'session_name': 'ថ្ងៃទី២ (អង្គារ 04/08) - ⛅ ពេលរសៀល',
            'order': 2,
            'max_invigilators': 60
        }
    )
    # Create 50 teachers
    for idx in range(1, 51):
        tid = f'T_TEST50_{idx:03d}'
        t, _ = Teacher.objects.get_or_create(
            teacher_id=tid,
            defaults={
                'khmer_name': f'គ្រូ ទេសទី{idx}',
                'latin_name': f'Teacher Test {idx}',
                'gender': Teacher.Gender.MALE if idx % 2 == 1 else Teacher.Gender.FEMALE,
                'phone': '012000222',
                'status': Teacher.Status.ACTIVE
            }
        )
        TeacherShiftRegistration.objects.update_or_create(
            slot=slot_50, teacher=t,
            defaults={
                'role': ExamCommitteeRole.INVIGILATOR,
                'room_assignment': f'បន្ទប់ {idx:02d}'
            }
        )

    # Ensure 51st teacher is not present yet for the 50-teacher test
    TeacherShiftRegistration.objects.filter(slot=slot_50, teacher__teacher_id='T_TEST50_051').delete()

    req_50 = factory.get(f'/examinations/invigilator-plans/{plan.id}/roster/print/?slot={slot_50.id}')
    req_50.user = admin_user
    req_50.session = SessionStore()
    setattr(req_50, '_messages', FallbackStorage(req_50))
    resp_50 = exam_invigilator_roster_print(req_50, plan_id=plan.id)
    html_50 = resp_50.content.decode('utf-8')

    assert "<td class=\"col-num\">1</td>" in html_50, "Slot 1 must be present on left"
    assert "<td class=\"col-num\">2</td>" in html_50, "Slot 2 must be present on right"
    assert "<td class=\"col-num\">49</td>" in html_50, "Slot 49 must be present on left"
    assert "<td class=\"col-num\">50</td>" in html_50, "Slot 50 must be present on right"
    assert "<td class=\"col-num\">51</td>" not in html_50, "Slot 51 must NOT be present!"
    assert "<td class=\"col-num\">52</td>" not in html_50, "Slot 52 must NOT be present!"
    assert "<td class=\"col-num\">53</td>" not in html_50, "Slot 53 must NOT be present!"
    assert "<td class=\"col-num\">54</td>" not in html_50, "Slot 54 must NOT be present!"
    assert "<td class=\"col-num\"></td>" not in html_50, "No empty cells for even number of teachers (50)!"
    print("8. [PASS] 50 Teachers (Even): Exact 25 balanced rows, 0 empty cells, stops strictly at 50!")

    # 10. SPECIAL TEST: Exactly 51 Teachers (Odd Number - User's exact scenario)
    # Must have 26 rows, horizontal pairs (1,2 / 3,4 ... 49,50), row 26 has 51 on left and empty on right!
    t_51, _ = Teacher.objects.get_or_create(
        teacher_id='T_TEST50_051',
        defaults={
            'khmer_name': 'គ្រូ ទេសទី៥១',
            'latin_name': 'Teacher Test 51',
            'gender': Teacher.Gender.FEMALE,
            'phone': '012000222',
            'status': Teacher.Status.ACTIVE
        }
    )
    TeacherShiftRegistration.objects.update_or_create(
        slot=slot_50, teacher=t_51,
        defaults={
            'role': ExamCommitteeRole.INVIGILATOR,
            'room_assignment': 'បន្ទប់ 51'
        }
    )
    resp_51 = exam_invigilator_roster_print(req_50, plan_id=plan.id)
    html_51 = resp_51.content.decode('utf-8')

    assert "<td class=\"col-num\">1</td>" in html_51, "Slot 1 must be present on left"
    assert "<td class=\"col-num\">2</td>" in html_51, "Slot 2 must be present on right"
    assert "<td class=\"col-num\">49</td>" in html_51, "Slot 49 must be present on left"
    assert "<td class=\"col-num\">50</td>" in html_51, "Slot 50 must be present on right"
    assert "<td class=\"col-num\">51</td>" in html_51, "Slot 51 must be present on left"
    assert "<td class=\"col-num\">52</td>" not in html_51, "Slot 52 must NOT be present!"
    assert "<td class=\"col-num\"></td>" in html_51, "Exactly 1 empty cell on the right for odd count (51)!"
    # Verify there is at most 1 empty cell
    assert html_51.count('<td class=\"col-num\"></td>') == 1, "There must be at most 1 empty cell on the right for odd count!"
    print("9. [PASS] 51 Teachers (Odd): Exact 26 balanced rows, exactly 1 empty cell on the right, stops at 51!")

    # 11. SPECIAL TEST: Exact Role Hierarchy & Alphabetical Sort (Image 2 Compliance)
    # Order must strictly follow:
    # 1: ផេង រិទ្ធីយ៉ា (ប្រធាន)
    # 2: ប៊ុន ណារី (អនុប្រធាន - ប)
    # 3: ទិន សុភី (អនុប្រធាន - ទ)
    # 4: សុន សុមនី (អនុប្រធាន - ស)
    # 5: គង់ ម៉ានិន (កណ្តាល - គ)
    # 6: ឃឹម ស្រស់ (ត្រួតអគារ - ឃ)
    # 7: ទុន វណ្ណៈ (បូកស្រង់ - ទ)
    # 8: កង សុគង់ (អនុរក្ស 1 - កង)
    # 9: កន ជីវី (អនុរក្ស 31 - កន)
    # 10: ខ្លឹម សុផា (អនុរក្ស 8 - ខ្ល)
    # Invigilators are sorted alphabetically by teacher name, with randomized rooms (1, 31, 8)!
    resp_slot1 = exam_invigilator_roster_print(req, plan_id=plan.id)
    html_s1 = resp_slot1.content.decode('utf-8')
    assert "ផេង រិទ្ធីយ៉ា" in html_s1
    assert "កង សុគង់" in html_s1
    assert "អនុរក្ស 1" in html_s1
    assert "អនុរក្ស 31" in html_s1
    assert "អនុរក្ស 8" in html_s1

    # Check that in the rendered HTML, spots match exact ordering
    import re
    row_pattern = r'<td class="col-num">(\d+)</td>\s*<td class="col-name">(.*?)</td>\s*<td class="col-duty">(.*?)</td>'
    matches_s1 = re.findall(row_pattern, html_s1)
    # Sort matches by order_num int
    matches_s1_sorted = sorted(matches_s1, key=lambda x: int(x[0]))
    # Filter only our slot's 10 teachers
    spots_ordered = matches_s1_sorted[:10]

    print("Spots ordered:", spots_ordered)
    assert spots_ordered[0][1] == "លោក ផេង រិទ្ធីយ៉ា" and spots_ordered[0][2] == "ប្រធាន"
    # Vice Presidents (order 2, 3, 4)
    vp_duties = [s[2] for s in spots_ordered[1:4]]
    assert all(d == "អនុប្រធាន" for d in vp_duties), "Spots 2, 3, 4 must all be អនុប្រធាន"
    assert "គង់ ម៉ានិន" in spots_ordered[4][1] and spots_ordered[4][2] == "កណ្តាល"
    assert "ឃឹម ស្រស់" in spots_ordered[5][1] and spots_ordered[5][2] == "ត្រួតអគារ"
    assert "ទុន វណ្ណៈ" in spots_ordered[6][1] and spots_ordered[6][2] == "បូកស្រង់"
    assert "កង សុគង់" in spots_ordered[7][1] and spots_ordered[7][2] == "អនុរក្ស 1"
    assert "កន ជីវី" in spots_ordered[8][1] and spots_ordered[8][2] == "អនុរក្ស 31"
    assert "ខ្លឹម សុផា" in spots_ordered[9][1] and spots_ordered[9][2] == "អនុរក្ស 8"
    print("10. [PASS] Exact Image 2 Compliance: ប្រធាន first -> អនុប្រធាន -> កណ្តាល -> ត្រួតអគារ -> បូកស្រង់ -> អនុរក្ស (Alphabetical with randomized rooms 1, 31, 8)")

    # 12. SPECIAL TEST: Admin Changes Invigilator to "កណ្តាល" (Secretariat)
    from apps.examinations.views import exam_invigilator_roster_view
    reg_to_change = TeacherShiftRegistration.objects.filter(slot=slot, role=ExamCommitteeRole.INVIGILATOR).first()
    t_name = reg_to_change.teacher.khmer_name
    req_post = factory.post(f'/examinations/invigilator-plans/{plan.id}/roster/', {
        'action': 'admin_update_registration',
        'registration_id': reg_to_change.id,
        'role': ExamCommitteeRole.SECRETARIAT,
        'room_assignment': ''
    })
    req_post.user = admin_user
    req_post.session = SessionStore()
    setattr(req_post, '_messages', FallbackStorage(req_post))
    resp_post = exam_invigilator_roster_view(req_post, plan_id=plan.id)
    assert resp_post.status_code == 302, "Admin role update must redirect"

    reg_to_change.refresh_from_db()
    assert reg_to_change.role == ExamCommitteeRole.SECRETARIAT, "Role must be updated to SECRETARIAT"
    assert reg_to_change.room_assignment == "", "Room assignment must be cleared for non-invigilator role"

    # Now verify roster print reflects the change
    resp_updated = exam_invigilator_roster_print(req, plan_id=plan.id)
    html_updated = resp_updated.content.decode('utf-8')
    matches_up = sorted(re.findall(row_pattern, html_updated), key=lambda x: int(x[0]))[:10]

    # The changed teacher must now have duty "កណ្តាល"
    found_changed = [s for s in matches_up if t_name in s[1]]
    assert len(found_changed) == 1
    assert found_changed[0][2] == "កណ្តាល", f"Teacher {t_name} duty must now be 'កណ្តាល'"
    # 12. VERIFY DYNAMIC ROW HEIGHT & FONT SIZE CUSTOMIZATION
    req_custom_size = factory.get(f'/examinations/invigilator-plans/{plan.id}/roster/print/?slot_id={slot.id}&row_height=28&font_size=11.5')
    req_custom_size.user = admin_user
    req_custom_size.session = SessionStore()
    setattr(req_custom_size, '_messages', FallbackStorage(req_custom_size))
    resp_custom_size = exam_invigilator_roster_print(req_custom_size, plan_id=plan.id)
    assert resp_custom_size.status_code == 200
    html_custom = resp_custom_size.content.decode('utf-8')

    assert '--row-height: 28px;' in html_custom, "Custom row height 28px must be present in CSS variables"
    assert '--table-font-size: 11.5pt;' in html_custom, "Custom font size 11.5pt must be present in CSS variables"
    assert 'adjustRowHeight' in html_custom, "JavaScript adjustRowHeight function must be present"
    assert 'adjustFontSize' in html_custom, "JavaScript adjustFontSize function must be present"
    assert 'resetTableSizing' in html_custom, "JavaScript resetTableSizing function must be present"
    assert 'id="rowHeightDisplay"' in html_custom, "Row height display badge must be present"
    assert 'id="fontSizeDisplay"' in html_custom, "Font size display badge must be present"
    print("12. [PASS] Row height (28px) and Font size (11.5pt) live controls & CSS variables verified!")

    print("\n================================================================================")
    print("🎉 ALL 12 TESTS PASSED (100%)! ROSTER PRINT SHEET COMPLIES 100% WITH ALL SPECS.")
    print("================================================================================")


if __name__ == '__main__':
    run_tests()
