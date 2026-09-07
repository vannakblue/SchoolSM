"""
Teacher Privilege & Permission Helpers for SchoolSM
Enforces distinction between:
- Administrator (Full access)
- Homeroom Teacher (គ្រូទទួលបន្ទុកថ្នាក់ - manages assigned homeroom classroom)
- Subject Teacher (គ្រូបង្រៀនតាមមុខវិជ្ជា - enters scores and attendance only for assigned subjects & classes)
"""
from typing import Dict, Any, Optional
from django.db.models import Q
from apps.academics.models import Classroom, ClassSubject, Timetable, AcademicYear
from apps.academics.utils import get_active_academic_year
from apps.teachers.models import Teacher


def get_teacher_privileges(user, request=None) -> Dict[str, Any]:
    """
    Computes active privileges for the authenticated user.
    Returns:
        dict with keys:
        - is_admin: bool
        - is_teacher: bool
        - teacher: Teacher object or None
        - homeroom_classrooms: QuerySet of Classrooms where teacher is homeroom teacher
        - primary_homeroom: first homeroom classroom or None
        - is_homeroom_teacher: bool (True if teacher has at least 1 homeroom)
        - teaching_class_ids: set of classroom IDs where teacher teaches
        - teaching_subject_ids: set of subject IDs teacher is assigned to teach
        - teaching_assignments: list of assigned {classroom, subject, weekly_hours}
    """
    is_admin = bool(getattr(user, 'is_superuser', False) or getattr(user, 'role', '') == 'ADMIN')
    teacher = getattr(user, 'teacher_profile', None)
    is_teacher = bool(teacher and (getattr(user, 'role', '') == 'TEACHER' or is_admin))

    active_year = get_active_academic_year(request) if request else AcademicYear.objects.filter(is_current=True).first()

    if not teacher or is_admin:
        all_cls = Classroom.objects.filter(academic_year=active_year) if active_year else Classroom.objects.all()
        return {
            'is_admin': is_admin,
            'is_teacher': is_teacher,
            'teacher': teacher,
            'active_year': active_year,
            'homeroom_classrooms': all_cls,
            'primary_homeroom': all_cls.first(),
            'is_homeroom_teacher': True,
            'teaching_class_ids': set(all_cls.values_list('id', flat=True)),
            'teaching_subject_ids': set(), # All subjects allowed
            'teaching_assignments': [],
            'can_manage_all': is_admin,
        }

    # Homeroom classrooms
    hr_qs = Classroom.objects.filter(homeroom_teacher=teacher)
    if active_year:
        hr_qs_year = hr_qs.filter(academic_year=active_year)
        if hr_qs_year.exists():
            hr_qs = hr_qs_year
    primary_homeroom = hr_qs.first()

    # Teaching assignments from ClassSubject
    cs_qs = ClassSubject.objects.filter(teacher=teacher).select_related('classroom', 'subject', 'classroom__academic_year')
    if active_year:
        cs_qs_year = cs_qs.filter(classroom__academic_year=active_year)
        if cs_qs_year.exists():
            cs_qs = cs_qs_year

    # Also pull from Timetable entries to ensure 100% coverage
    tt_qs = Timetable.objects.filter(teacher=teacher).select_related('classroom', 'subject')
    if active_year:
        tt_qs_year = tt_qs.filter(classroom__academic_year=active_year)
        if tt_qs_year.exists():
            tt_qs = tt_qs_year

    teaching_class_ids = set(cs_qs.values_list('classroom_id', flat=True)) | set(tt_qs.values_list('classroom_id', flat=True))
    teaching_subject_ids = set(cs_qs.values_list('subject_id', flat=True)) | set(tt_qs.values_list('subject_id', flat=True))

    teaching_assignments = []
    seen_pairs = set()
    for cs in cs_qs:
        pair = (cs.classroom_id, cs.subject_id)
        if pair not in seen_pairs:
            seen_pairs.add(pair)
            teaching_assignments.append({
                'classroom': cs.classroom,
                'subject': cs.subject,
                'weekly_hours': cs.weekly_hours,
            })

    for tt in tt_qs:
        pair = (tt.classroom_id, tt.subject_id)
        if pair not in seen_pairs:
            seen_pairs.add(pair)
            teaching_assignments.append({
                'classroom': tt.classroom,
                'subject': tt.subject,
                'weekly_hours': 2,
            })

    return {
        'is_admin': False,
        'is_teacher': True,
        'teacher': teacher,
        'active_year': active_year,
        'homeroom_classrooms': hr_qs,
        'primary_homeroom': primary_homeroom,
        'is_homeroom_teacher': hr_qs.exists(),
        'teaching_class_ids': teaching_class_ids,
        'teaching_subject_ids': teaching_subject_ids,
        'teaching_assignments': teaching_assignments,
        'can_manage_all': False,
    }


def can_teacher_manage_homeroom(user, classroom_id: int) -> bool:
    """
    Returns True if user is Admin, or user is the Homeroom Teacher of classroom_id.
    """
    if getattr(user, 'is_superuser', False) or getattr(user, 'role', '') == 'ADMIN':
        return True
    teacher = getattr(user, 'teacher_profile', None)
    if not teacher:
        return False
    return Classroom.objects.filter(id=classroom_id, homeroom_teacher=teacher).exists()


def can_teacher_grade_subject(user, classroom_id: int, subject_id: int) -> bool:
    """
    Returns True if user is Admin, or Homeroom Teacher of classroom,
    or assigned Subject Teacher for this specific subject in this classroom.
    """
    if getattr(user, 'is_superuser', False) or getattr(user, 'role', '') == 'ADMIN':
        return True
    teacher = getattr(user, 'teacher_profile', None)
    if not teacher:
        return False

    # Homeroom teacher can oversee/grade their homeroom
    if Classroom.objects.filter(id=classroom_id, homeroom_teacher=teacher).exists():
        return True

    # Subject teacher assigned to this classroom and subject
    if ClassSubject.objects.filter(classroom_id=classroom_id, subject_id=subject_id, teacher=teacher).exists():
        return True
    if Timetable.objects.filter(classroom_id=classroom_id, subject_id=subject_id, teacher=teacher).exists():
        return True

    return False
