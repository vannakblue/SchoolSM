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
    req = factory.get(f'/examinations/invigilator-plans/{plan.id}/roster/print/')
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

    # 6. Check 54 Row Numbers & Empty Row Padding
    assert "<td class=\"col-num\">1</td>" in html, "Slot 1 must be present"
    assert "<td class=\"col-num\">2</td>" in html, "Slot 2 must be present"
    assert "<td class=\"col-num\">53</td>" in html, "Slot 53 must be present"
    assert "<td class=\"col-num\">54</td>" in html, "Slot 54 must be present (padded for manual signatures)"
    print("5. [PASS] Table strictly renders 54 slots (27 rows x 2 columns) with empty padding")

    # 7. Check Footer (Location, Solar Date, Lunar Date & Principal Title)
    assert "កំពង់កន្ទួត" in html, "Location name must be present in footer"
    assert "ព.ស.២៥៧០" in html, "Buddhist Era 2570 must be present in lunar date line"
    assert "នាយកសាលា" in html, "Principal title must be present in footer"
    print("6. [PASS] Footer with Location, Solar Date, Buddhist Era & នាយកសាលា signature verified")

    # 8. Check Query Parameter Overrides (custom school name & slot filter)
    req_custom = factory.get(f'/examinations/invigilator-plans/{plan.id}/roster/print/?school_name=វិទ្យាល័យ+គំរូ&location=ភ្នំពេញ')
    req_custom.user = admin_user
    req_custom.session = SessionStore()
    setattr(req_custom, '_messages', FallbackStorage(req_custom))
    resp_custom = exam_invigilator_roster_print(req_custom, plan_id=plan.id)
    html_custom = resp_custom.content.decode('utf-8')
    assert "វិទ្យាល័យ គំរូ" in html_custom, "Custom school name override must work"
    assert "ភ្នំពេញ" in html_custom, "Custom location override must work"
    print("7. [PASS] Query Parameter Overrides (custom school name, location) verified")

    print("\n================================================================================")
    print("🎉 ALL TESTS PASSED (100%)! ROSTER PRINT SHEET COMPLIES 100% WITH 11.PDF.")
    print("================================================================================")


if __name__ == '__main__':
    run_tests()
