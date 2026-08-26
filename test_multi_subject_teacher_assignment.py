import os
import sys
import django

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from apps.accounts.models import User
from apps.teachers.models import Teacher
from apps.academics.models import AcademicYear, Classroom, Subject, ClassSubject, GradeLevelRule


def test_multi_subject_assignment():
    print("=== STARTING MULTI-SUBJECT TEACHER ASSIGNMENT VERIFICATION ===")

    ay, _ = AcademicYear.objects.get_or_create(
        name='2026-2027',
        defaults={'start_date': '2026-10-01', 'end_date': '2027-07-31', 'is_current': True}
    )

    # 1. Create a Teacher with Multi-Specialization (e.g., គណិតវិទ្យា, រូបវិទ្យា & ព័ត៌មានវិទ្យា)
    teacher, _ = Teacher.objects.update_or_create(
        teacher_id='T-MULTI-01',
        defaults={
            'khmer_name': 'សុខ វិបុល',
            'latin_name': 'Sok Vibol',
            'gender': Teacher.Gender.MALE,
            'specialization': 'គណិតវិទ្យា, រូបវិទ្យា & ICT',
            'max_weekly_hours': 18
        }
    )
    print(f"  [PASS] 1. Teacher «{teacher.khmer_name}» created with multiple specializations: «{teacher.specialization}».")

    # 2. Create Subjects: Math, Physics, ICT, Biology
    sub_math, _ = Subject.objects.get_or_create(code='M_TEST', defaults={'name_kh': 'គណិតវិទ្យា', 'name_en': 'Math', 'order': 1})
    sub_phys, _ = Subject.objects.get_or_create(code='P_TEST', defaults={'name_kh': 'រូបវិទ្យា', 'name_en': 'Physics', 'order': 2})
    sub_ict, _ = Subject.objects.get_or_create(code='ICT_TEST', defaults={'name_kh': 'ព័ត៌មានវិទ្យា & ICT', 'name_en': 'ICT', 'order': 3})
    sub_bio, _ = Subject.objects.get_or_create(code='B_TEST', defaults={'name_kh': 'ជីវវិទ្យា', 'name_en': 'Biology', 'order': 4})

    # 3. Create Classrooms: 7A, 8A, 9A
    cls_7a, _ = Classroom.objects.get_or_create(name='7A_TEST', code='7A_T', academic_year=ay, defaults={'grade_level': 7})
    cls_8a, _ = Classroom.objects.get_or_create(name='8A_TEST', code='8A_T', academic_year=ay, defaults={'grade_level': 8})
    cls_9a, _ = Classroom.objects.get_or_create(name='9A_TEST', code='9A_T', academic_year=ay, defaults={'grade_level': 9})

    # 4. Admin Assigns Teacher to 4 DIFFERENT Subjects across 3 Different Classes:
    # - Class 7A: Math (6 hours)
    # - Class 8A: Physics (4 hours)
    # - Class 9A: ICT (2 hours)
    # - Class 9A: Biology (2 hours)
    cs1, _ = ClassSubject.objects.update_or_create(classroom=cls_7a, subject=sub_math, defaults={'teacher': teacher, 'weekly_hours': 6})
    cs2, _ = ClassSubject.objects.update_or_create(classroom=cls_8a, subject=sub_phys, defaults={'teacher': teacher, 'weekly_hours': 4})
    cs3, _ = ClassSubject.objects.update_or_create(classroom=cls_9a, subject=sub_ict, defaults={'teacher': teacher, 'weekly_hours': 2})
    cs4, _ = ClassSubject.objects.update_or_create(classroom=cls_9a, subject=sub_bio, defaults={'teacher': teacher, 'weekly_hours': 2})

    # 5. Query all assigned subjects for this teacher
    teacher_assignments = ClassSubject.objects.filter(teacher=teacher)
    assigned_subjects = list(set(teacher_assignments.values_list('subject__name_kh', flat=True)))
    total_assigned_hours = sum(a.weekly_hours for a in teacher_assignments)

    assert len(assigned_subjects) == 4, f"Expected 4 distinct subjects assigned, got {len(assigned_subjects)}"
    assert total_assigned_hours == 14, f"Expected total 14 weekly hours, got {total_assigned_hours}"

    print(f"  [PASS] 2. Successfully assigned teacher to {len(assigned_subjects)} distinct subjects: {', '.join(assigned_subjects)}.")
    print(f"  [PASS] 3. Verified Total Weekly Teaching Hours = {total_assigned_hours} hours/week (Quota: {teacher.max_weekly_hours} hours).")

    # Clean up
    ClassSubject.objects.filter(teacher=teacher).delete()
    cls_7a.delete()
    cls_8a.delete()
    cls_9a.delete()
    sub_math.delete()
    sub_phys.delete()
    sub_ict.delete()
    sub_bio.delete()
    teacher.delete()

    print("=== MULTI-SUBJECT TEACHER ASSIGNMENT TEST PASSED 100% ===")


if __name__ == '__main__':
    test_multi_subject_assignment()
