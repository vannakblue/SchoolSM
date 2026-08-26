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

def test_strict_unassigned_teacher_exclusion():
    print("==========================================================================")
    print("TEST: STRICT EXCLUSION OF UNASSIGNED TEACHERS & SUBJECTS IN AUTO-GEN")
    print("==========================================================================")

    client = Client()
    admin_user = User.objects.filter(role='ADMIN').first()
    if not admin_user:
        admin_user = User.objects.create_superuser('admin_test_auto', 'admin@test.com', 'password123')
    client.force_login(admin_user)

    # 1. Setup Academic Year
    ay, _ = AcademicYear.objects.get_or_create(
        name="2026-2027 Strict Test",
        defaults={'start_date': '2026-09-01', 'end_date': '2027-07-15', 'is_current': True}
    )
    AcademicYear.objects.filter(id=ay.id).update(is_current=True)
    AcademicYear.objects.exclude(id=ay.id).update(is_current=False)

    # 2. Setup Teachers
    t_math, _ = Teacher.objects.get_or_create(
        teacher_id="TCH-STRICT-M",
        defaults={'khmer_name': 'លោកគ្រូ សំ សុក', 'latin_name': 'SAM SOK', 'status': 'ACTIVE', 'max_weekly_hours': 18}
    )
    t_khmer, _ = Teacher.objects.get_or_create(
        teacher_id="TCH-STRICT-K",
        defaults={'khmer_name': 'អ្នកគ្រូ ចាន់ សុភាព', 'latin_name': 'CHAN SOPHEAP', 'gender': 'F', 'status': 'ACTIVE', 'max_weekly_hours': 18}
    )
    t_unassigned, _ = Teacher.objects.get_or_create(
        teacher_id="TCH-STRICT-UN",
        defaults={'khmer_name': 'គ្រូ មិនទាន់ចាត់តាំង', 'latin_name': 'UNASSIGNED TEACHER', 'status': 'ACTIVE', 'max_weekly_hours': 18}
    )

    # 3. Setup Subjects
    sub_math, _ = Subject.objects.get_or_create(code='M', defaults={'name_kh': 'គណិតវិទ្យា', 'name_en': 'Math', 'category': 'SCIENCE'})
    sub_khmer, _ = Subject.objects.get_or_create(code='K', defaults={'name_kh': 'ភាសាខ្មែរ', 'name_en': 'Khmer', 'category': 'GENERAL'})
    sub_physics, _ = Subject.objects.get_or_create(code='P', defaults={'name_kh': 'រូបវិទ្យា', 'name_en': 'Physics', 'category': 'SCIENCE'})
    sub_history, _ = Subject.objects.get_or_create(code='H', defaults={'name_kh': 'ប្រវត្តិវិទ្យា', 'name_en': 'History', 'category': 'SOCIAL'})

    # 4. Setup GradeLevelRules for Grade 7 (Math=5h, Khmer=6h, Physics=2h, History=2h)
    GradeLevelRule.objects.update_or_create(grade_level=7, track='GENERAL', subject=sub_math, defaults={'weekly_hours': 5, 'max_score': 100})
    GradeLevelRule.objects.update_or_create(grade_level=7, track='GENERAL', subject=sub_khmer, defaults={'weekly_hours': 6, 'max_score': 100})
    GradeLevelRule.objects.update_or_create(grade_level=7, track='GENERAL', subject=sub_physics, defaults={'weekly_hours': 2, 'max_score': 50})
    GradeLevelRule.objects.update_or_create(grade_level=7, track='GENERAL', subject=sub_history, defaults={'weekly_hours': 2, 'max_score': 50})

    # 5. Create Class 7-Partial (Only Math & Khmer assigned) and Class 7-Empty (NO teachers assigned)
    Classroom.objects.filter(code__in=['7-PARTIAL', '7-EMPTY']).delete()

    class_partial = Classroom.objects.create(
        code='7-PARTIAL',
        name='ថ្នាក់ទី ៧-Partial',
        grade_level=7,
        track='GENERAL',
        academic_year=ay,
        homeroom_teacher=t_unassigned # Even if homeroom teacher is set, unassigned subjects MUST NOT fall back to homeroom!
    )
    class_empty = Classroom.objects.create(
        code='7-EMPTY',
        name='ថ្នាក់ទី ៧-Empty',
        grade_level=7,
        track='GENERAL',
        academic_year=ay
    )

    # Assign ONLY Math -> t_math, Khmer -> t_khmer in 7-PARTIAL
    # Physics & History are INTENTIONALLY NOT ASSIGNED in 7-PARTIAL
    ClassSubject.objects.create(classroom=class_partial, subject=sub_math, teacher=t_math)
    ClassSubject.objects.create(classroom=class_partial, subject=sub_khmer, teacher=t_khmer)

    # 7-EMPTY has ZERO ClassSubject assignments

    # 6. Run Auto-Generation
    res = client.post(
        '/academics/timetable/auto-generate/',
        data=json.dumps({'clear_existing': True}),
        content_type='application/json'
    )
    assert res.status_code == 200
    res_data = res.json()
    assert res_data.get('status') == 'success'

    # 7. Assertions on generated slots
    # 7-EMPTY must have 0 slots
    empty_slots = Timetable.objects.filter(classroom=class_empty).count()
    assert empty_slots == 0, f"Expected 0 slots for class_empty, got {empty_slots}"
    print(f"✅ PASSED: ថ្នាក់ដែលមិនមានគ្រូចាត់តាំង (7-EMPTY) ទទួលបាន 0 ម៉ោង ({empty_slots} slots).")

    # 7-PARTIAL must have exactly 5 Math + 6 Khmer = 11 slots total
    partial_slots = Timetable.objects.filter(classroom=class_partial)
    math_slots = partial_slots.filter(subject=sub_math, teacher=t_math).count()
    khmer_slots = partial_slots.filter(subject=sub_khmer, teacher=t_khmer).count()
    physics_slots = partial_slots.filter(subject=sub_physics).count()
    history_slots = partial_slots.filter(subject=sub_history).count()
    unassigned_teacher_slots = partial_slots.filter(teacher=t_unassigned).count()

    print(f"✅ PASSED: ថ្នាក់ 7-PARTIAL គណិតវិទ្យា (Math) បាន {math_slots}/5 ម៉ោង ជាមួយគ្រូ {t_math.khmer_name}.")
    print(f"✅ PASSED: ថ្នាក់ 7-PARTIAL ភាសាខ្មែរ (Khmer) បាន {khmer_slots}/6 ម៉ោង ជាមួយគ្រូ {t_khmer.khmer_name}.")
    print(f"✅ PASSED: ថ្នាក់ 7-PARTIAL រូបវិទ្យា (Physics - Unassigned) ទទួលបាន {physics_slots} ម៉ោង (គ្មានការរៀបចំឡើយ).")
    print(f"✅ PASSED: ថ្នាក់ 7-PARTIAL ប្រវត្តិវិទ្យា (History - Unassigned) ទទួលបាន {history_slots} ម៉ោង (គ្មានការរៀបចំឡើយ).")
    print(f"✅ PASSED: គ្រូដែលមិនទាន់ចាត់តាំង ({t_unassigned.khmer_name}) ទទួលបាន {unassigned_teacher_slots} ម៉ោង (100% EXCLUDED).")

    assert math_slots == 5, f"Expected 5 Math slots, got {math_slots}"
    assert khmer_slots == 6, f"Expected 6 Khmer slots, got {khmer_slots}"
    assert physics_slots == 0, f"Expected 0 Physics slots, got {physics_slots}"
    assert history_slots == 0, f"Expected 0 History slots, got {history_slots}"
    assert unassigned_teacher_slots == 0, f"Expected 0 slots for unassigned teacher, got {unassigned_teacher_slots}"

    # Clean up test records
    Timetable.objects.filter(classroom__in=[class_partial, class_empty]).delete()
    class_partial.delete()
    class_empty.delete()

    print("==========================================================================")
    print("🎉 CONFIRMED 100%: UNASSIGNED TEACHERS & SUBJECTS ARE STRICTLY EXCLUDED!")
    print("==========================================================================")

if __name__ == '__main__':
    test_strict_unassigned_teacher_exclusion()
