import os
import sys
import django

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from apps.academics.models import AcademicYear, Classroom, Subject, ClassSubject, GradeLevelRule
from apps.teachers.models import Teacher
from apps.academics.views import teacher_assignments_auto_assign

User = get_user_model()

def run_tests():
    print("==========================================================================")
    print("🚀 TEST: STRICT TEACHER HOURS QUOTA ENFORCEMENT IN AUTO-ASSIGN")
    print("==========================================================================")

    admin_user = User.objects.filter(role='ADMIN').first()
    if not admin_user:
        admin_user = User.objects.create_superuser('admin_quota_test', 'admin@quota.com', 'pass123')

    # 1. Setup Academic Year
    ay, _ = AcademicYear.objects.get_or_create(
        name="2026-2027 Quota Test Year",
        defaults={'start_date': '2026-09-01', 'end_date': '2027-07-15', 'is_current': True}
    )
    AcademicYear.objects.filter(id=ay.id).update(is_current=True)
    AcademicYear.objects.exclude(id=ay.id).update(is_current=False)

    # 2. Setup Subjects
    sub_math, _ = Subject.objects.get_or_create(code='M', defaults={'name_kh': 'គណិតវិទ្យា', 'name_en': 'Math', 'order': 1})
    sub_physics, _ = Subject.objects.get_or_create(code='P', defaults={'name_kh': 'រូបវិទ្យា', 'name_en': 'Physics', 'order': 2})
    sub_khmer, _ = Subject.objects.get_or_create(code='K', defaults={'name_kh': 'ភាសាខ្មែរ', 'name_en': 'Khmer', 'order': 3})

    # 3. Setup Teachers with explicit max_weekly_hours
    Teacher.objects.filter(teacher_id__startswith="TCH-QTEST-").delete()
    
    t_math_hs = Teacher.objects.create(
        teacher_id="TCH-QTEST-M1",
        khmer_name="លោកគ្រូ គណិត ទុតិយភូមិ",
        latin_name="MATH HIGH SCHOOL",
        specialization="គណិតវិទ្យា",
        training_level="គ្រូទុតិយភូមិ",
        max_weekly_hours=16,
        status='ACTIVE'
    )
    t_math_ms = Teacher.objects.create(
        teacher_id="TCH-QTEST-M2",
        khmer_name="លោកគ្រូ គណិត បឋមភូមិ",
        latin_name="MATH MIDDLE SCHOOL",
        specialization="គណិត-រូប",
        training_level="គ្រូបឋមភូមិ",
        max_weekly_hours=18,
        status='ACTIVE'
    )
    t_physics = Teacher.objects.create(
        teacher_id="TCH-QTEST-P1",
        khmer_name="អ្នកគ្រូ រូបវិទ្យា",
        latin_name="PHYSICS TEACHER",
        specialization="រូបវិទ្យា",
        training_level="គ្រូទុតិយភូមិ",
        max_weekly_hours=14, # Custom max hours
        status='ACTIVE'
    )
    t_khmer = Teacher.objects.create(
        teacher_id="TCH-QTEST-K1",
        khmer_name="អ្នកគ្រូ ភាសាខ្មែរ",
        latin_name="KHMER TEACHER",
        specialization="អក្សរសាស្ត្រខ្មែរ",
        training_level="គ្រូបឋមភូមិ",
        max_weekly_hours=18,
        status='ACTIVE'
    )

    # 4. Setup 6 Classrooms to generate heavy teaching load (e.g. 6 classes * 5h Math = 30h Math needed)
    Classroom.objects.filter(code__startswith="QTEST-").delete()
    classes = []
    for g in [12, 11, 10, 9, 8, 7]:
        cls = Classroom.objects.create(
            code=f"QTEST-{g}A",
            name=f"ថ្នាក់ទី {g}A",
            grade_level=g,
            track='GENERAL',
            academic_year=ay
        )
        classes.append(cls)
        # Grade rules: Math=5h, Physics=3h, Khmer=6h
        GradeLevelRule.objects.update_or_create(grade_level=g, track='GENERAL', subject=sub_math, defaults={'weekly_hours': 5})
        GradeLevelRule.objects.update_or_create(grade_level=g, track='GENERAL', subject=sub_physics, defaults={'weekly_hours': 3})
        GradeLevelRule.objects.update_or_create(grade_level=g, track='GENERAL', subject=sub_khmer, defaults={'weekly_hours': 6})

    # Clear existing assignments for test classes
    ClassSubject.objects.filter(classroom__in=classes).delete()

    # 5. Run Auto-Assignment
    rf = RequestFactory()
    req = rf.get(f'/academics/teacher-assignments/auto-assign/?year={ay.id}')
    req.user = admin_user
    req.session = {}
    setattr(req, '_messages', FallbackStorage(req))
    
    res = teacher_assignments_auto_assign(req)
    assert res.status_code == 302, f"Expected redirect 302, got {res.status_code}"

    # 6. Verify NO TEACHER in the entire database EXCEEDED THEIR MAX HOURS QUOTA
    rules_dict = {(r.subject_id, r.grade_level, r.track): r.weekly_hours for r in GradeLevelRule.objects.all()}

    all_active_teachers = list(Teacher.objects.filter(status='ACTIVE'))
    over_quota_violations = []
    total_assigned_slots = 0

    for t in all_active_teachers:
        assigned_cs = ClassSubject.objects.filter(teacher=t, classroom__academic_year=ay)
        total_hours = sum(
            rules_dict.get((cs.subject_id, cs.classroom.grade_level, cs.classroom.track or 'GENERAL'), cs.weekly_hours or 0)
            for cs in assigned_cs
        )
        total_assigned_slots += assigned_cs.count()

        if total_hours > t.max_weekly_hours:
            over_quota_violations.append((t.khmer_name, total_hours, t.max_weekly_hours))
        
        if total_hours > 0:
            print(f"👩‍🏫 Teacher {t.khmer_name} ({t.training_level}): Assigned = {total_hours}h / Max Quota = {t.max_weekly_hours}h [{assigned_cs.count()} classes]")

    print(f"\n📊 Total Class-Subject Assignments made: {total_assigned_slots}")
    print(f"⚠️ Over-Quota Violations: {len(over_quota_violations)}")

    # STRICT ASSERTION: ZERO TEACHERS MAY EXCEED MAX HOURS
    assert len(over_quota_violations) == 0, f"Found {len(over_quota_violations)} teachers exceeding max quota: {over_quota_violations}"
    print("✅ PASSED: 100% នៃគ្រូទាំងអស់គឺមិនលើសម៉ោងកំណត់ឡើយ (0 teachers over quota)!")

    print("\n==========================================================================")
    print("🎉 ALL STRICT TEACHER HOURS QUOTA ASSERTIONS PASSED WITH 100% SUCCESS!")
    print("==========================================================================")

    # Clean up test data
    ClassSubject.objects.filter(classroom__in=classes).delete()
    Classroom.objects.filter(code__startswith="QTEST-").delete()
    Teacher.objects.filter(teacher_id__startswith="TCH-QTEST-").delete()

if __name__ == '__main__':
    run_tests()
