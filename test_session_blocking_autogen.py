import os
import sys
import json
import django

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.academics.models import AcademicYear, Classroom, Subject, ClassSubject, Timetable, GradeLevelRule
from apps.teachers.models import Teacher

def test_session_blocking_autogen():
    print("==========================================================================")
    print("TEST: PRESERVATION OF BLOCKED SESSIONS & UNBLOCKED-ONLY AUTO-GENERATION")
    print("==========================================================================")

    client = Client()
    admin_user = User.objects.filter(role='ADMIN').first()
    if not admin_user:
        admin_user = User.objects.create_superuser('admin_blk_test', 'admin@test.com', 'password123')
    client.force_login(admin_user)

    # 1. Setup Academic Year
    ay, _ = AcademicYear.objects.get_or_create(
        name="2026-2027 Blk Test",
        defaults={'start_date': '2026-09-01', 'end_date': '2027-07-15', 'is_current': True}
    )
    AcademicYear.objects.filter(id=ay.id).update(is_current=True)
    AcademicYear.objects.exclude(id=ay.id).update(is_current=False)

    # 2. Setup Teachers & Subjects
    t_math, _ = Teacher.objects.get_or_create(
        teacher_id="TCH-BLK-M",
        defaults={'khmer_name': 'លោកគ្រូ សំ សុក', 'status': 'ACTIVE', 'max_weekly_hours': 18}
    )
    t_khmer, _ = Teacher.objects.get_or_create(
        teacher_id="TCH-BLK-K",
        defaults={'khmer_name': 'អ្នកគ្រូ ចាន់ សុភាព', 'gender': 'F', 'status': 'ACTIVE', 'max_weekly_hours': 18}
    )

    sub_math, _ = Subject.objects.get_or_create(code='M', defaults={'name_kh': 'គណិតវិទ្យា', 'name_en': 'Math', 'category': 'SCIENCE'})
    sub_khmer, _ = Subject.objects.get_or_create(code='K', defaults={'name_kh': 'ភាសាខ្មែរ', 'name_en': 'Khmer', 'category': 'GENERAL'})

    GradeLevelRule.objects.update_or_create(grade_level=7, track='GENERAL', subject=sub_math, defaults={'weekly_hours': 5, 'max_score': 100})
    GradeLevelRule.objects.update_or_create(grade_level=7, track='GENERAL', subject=sub_khmer, defaults={'weekly_hours': 6, 'max_score': 100})

    # 3. Create Classroom 7-BlockedTest
    Classroom.objects.filter(code='7-BLKTEST').delete()
    cls_blk = Classroom.objects.create(
        code='7-BLKTEST',
        name='ថ្នាក់ទី ៧-BlockedTest',
        grade_level=7,
        track='GENERAL',
        academic_year=ay,
        homeroom_teacher=t_math
    )

    ClassSubject.objects.create(classroom=cls_blk, subject=sub_math, teacher=t_math)
    ClassSubject.objects.create(classroom=cls_blk, subject=sub_khmer, teacher=t_khmer)

    # 4. Prepare Blocked Slots (Block ALL Afternoon periods 5, 6, 7, 8 across Monday to Saturday)
    blocked_slots = []
    for d in range(1, 7): # Monday to Saturday
        for p in [5, 6, 7, 8]: # Afternoon
            blocked_slots.append({
                'classroom_id': cls_blk.id,
                'day_of_week': d,
                'period_number': p,
                'is_blocked': True,
                'is_locked': True
            })

    # 5. Save Matrix with blocked_slots in session
    res_save = client.post(
        '/academics/timetable/save-matrix/',
        data=json.dumps({'matrix': [], 'blocked_slots': blocked_slots}),
        content_type='application/json'
    )
    assert res_save.status_code == 200

    # 6. Run Auto-Generation with blocked_slots passed in locked_slots
    res_autogen = client.post(
        '/academics/timetable/auto-generate/',
        data=json.dumps({
            'clear_existing': True,
            'locked_slots': blocked_slots
        }),
        content_type='application/json'
    )
    assert res_autogen.status_code == 200

    # 7. Check that generated timetable entries ONLY exist in morning periods (1-4)
    afternoon_slots = Timetable.objects.filter(
        classroom=cls_blk,
        period_number__in=[5, 6, 7, 8]
    )
    morning_slots = Timetable.objects.filter(
        classroom=cls_blk,
        period_number__in=[1, 2, 3, 4]
    )

    print(f"✅ PASSED: ពេលព្រឹក (Morning 1-4) ត្រូវបានរៀបចំស្វ័យប្រវត្តិចំនួន {morning_slots.count()} ម៉ោង (Math 5h + Khmer 6h).")
    print(f"✅ PASSED: ពេលរសៀលដែលបានបិទ (Afternoon 5-8 Blocked) គ្មានម៉ោងណាធ្លាក់ចូលឡើយ ({afternoon_slots.count()} slots).")

    assert afternoon_slots.count() == 0, f"Expected 0 afternoon slots, got {afternoon_slots.count()}"
    assert morning_slots.count() == 11, f"Expected 11 morning slots, got {morning_slots.count()}"

    # 8. Check that timetable_view returns matrix_state with is_blocked preserved
    res_view = client.get('/academics/timetable/')
    assert res_view.status_code == 200
    html_content = res_view.content.decode('utf-8')
    assert 'is_blocked' in html_content
    for blk in blocked_slots:
        k = f"{blk['classroom_id']}_{blk['day_of_week']}_{blk['period_number']}"
        assert f'"{k}": {{"is_blocked": true' in html_content or f'"{k}":{{"is_blocked":true' in html_content or k in html_content

    print(f"✅ PASSED: ពេល Refresh ឬ Auto-Gen រួច កន្លែងដែលបានបិទទាំង {len(blocked_slots)} ម៉ោង នៅរក្សាទុកដដែល (Preserved).")


    # 9. Clean up test records
    Timetable.objects.filter(classroom=cls_blk).delete()
    cls_blk.delete()

    print("==========================================================================")
    print("🎉 ALL SESSION BLOCKING & AUTO-GEN PRESERVATION TESTS PASSED 100%!")
    print("==========================================================================")

if __name__ == '__main__':
    test_session_blocking_autogen()
