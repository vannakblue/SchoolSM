from django.db.models import Q
from .models import AcademicYear

def get_active_academic_year(request=None):
    """
    Determines the currently active AcademicYear for the user's request.
    Resolution order:
      1. Query param: ?year=<id_or_name> or ?academic_year=<id_or_name> (sets session)
      2. Session param: request.session['active_academic_year_id']
      3. Current active year in database: AcademicYear.objects.filter(is_current=True).first()
      4. Most recent year in database: AcademicYear.objects.order_by('-start_date').first()
    """
    if request is None:
        return AcademicYear.objects.filter(is_current=True).first() or AcademicYear.objects.order_by('-start_date').first()

    # 1. URL Query parameter override
    year_param = request.GET.get('academic_year') or request.GET.get('year')
    if year_param:
        ay = None
        if str(year_param).isdigit():
            ay = AcademicYear.objects.filter(id=int(year_param)).first()
        if not ay:
            ay = AcademicYear.objects.filter(name=str(year_param).strip()).first()
        if not ay:
            raw_param = str(year_param).strip()
            mapping = {'០': '0', '១': '1', '២': '2', '៣': '3', '៤': '4', '៥': '5', '៦': '6', '៧': '7', '៨': '8', '៩': '9'}
            norm_param = raw_param
            for kh, ar in mapping.items():
                norm_param = norm_param.replace(kh, ar)
            for y in AcademicYear.objects.all():
                norm_y = str(y.name).strip()
                for kh, ar in mapping.items():
                    norm_y = norm_y.replace(kh, ar)
                if norm_y == norm_param:
                    ay = y
                    break
        if ay:
            try:
                request.session['active_academic_year_id'] = ay.id
            except Exception:
                pass
            return ay

    # 2. Session override
    try:
        session_year_id = request.session.get('active_academic_year_id')
        if session_year_id:
            ay = AcademicYear.objects.filter(id=session_year_id).first()
            if ay:
                return ay
    except Exception:
        pass

    # 3. Database is_current=True (prefer operational year with classrooms if multiple)
    current_years = AcademicYear.objects.filter(is_current=True)
    if current_years.count() > 1:
        for cy in current_years:
            if cy.classrooms.exists():
                return cy
        return current_years.first()
    elif current_years.exists():
        return current_years.first()

    # 4. Fallback to latest
    return AcademicYear.objects.order_by('-start_date').first()


def get_teacher_subject_duty_code_map(academic_year=None, subjects=None, teachers=None, class_subjects=None):
    """
    Returns a tuple of (teacher_subject_code_map, teacher_direct_code_map)
    containing the official teaching duty codes (e.g. M1, M2, P1, C1, K1, ED1, AG1...)
    permanently stored in the database.
    """
    import re
    from .models import SavedDefaultConfig, ClassSubject, Subject
    from apps.teachers.models import Teacher

    cfg = SavedDefaultConfig.objects.filter(key='teacher_subject_duty_codes').first()
    saved_data = cfg.data if (cfg and isinstance(cfg.data, dict)) else {}

    code_map = {}
    teacher_direct_code = {}

    # 1. Map from Teacher.subject_code or SavedDefaultConfig
    all_teachers = teachers if teachers is not None else list(Teacher.objects.all())
    for t in all_teachers:
        c = getattr(t, 'subject_code', None) or saved_data.get(str(t.id))
        if c:
            teacher_direct_code[t.id] = c

    # 2. Map from ClassSubject.teacher_code
    cs_qs = class_subjects
    if cs_qs is None:
        cs_query = ClassSubject.objects.filter(teacher__isnull=False)
        if academic_year:
            cs_query = cs_query.filter(classroom__academic_year=academic_year)
        cs_qs = list(cs_query.select_related('subject', 'teacher'))

    for cs in cs_qs:
        if cs.subject_id and cs.teacher_id:
            c = getattr(cs, 'teacher_code', None) or saved_data.get(f"{cs.subject_id}_{cs.teacher_id}") or teacher_direct_code.get(cs.teacher_id)
            if c:
                code_map[(cs.subject_id, cs.teacher_id)] = c

    # 3. For any teacher who has a direct subject_code, also map for their assigned subjects
    for cs in cs_qs:
        if cs.subject_id and cs.teacher_id and (cs.subject_id, cs.teacher_id) not in code_map:
            t_code = teacher_direct_code.get(cs.teacher_id)
            if t_code:
                code_map[(cs.subject_id, cs.teacher_id)] = t_code

    # 4. Fallback for unmapped pairs
    all_subjects = subjects if subjects is not None else list(Subject.objects.all())
    sub_by_id = {s.id: s for s in all_subjects}
    subject_teacher_counters = {}

    for (s_id, t_id), code in code_map.items():
        sub = sub_by_id.get(s_id)
        if sub and sub.code:
            m = re.search(r'\d+', str(code))
            if m:
                num = int(m.group(0))
                subject_teacher_counters[s_id] = max(subject_teacher_counters.get(s_id, 0), num)

    for cs in cs_qs:
        if cs.subject_id and cs.teacher_id and (cs.subject_id, cs.teacher_id) not in code_map:
            s_id = cs.subject_id
            t_id = cs.teacher_id
            sub = sub_by_id.get(s_id)
            sub_code = sub.code if (sub and sub.code) else 'S'
            next_num = subject_teacher_counters.get(s_id, 0) + 1
            subject_teacher_counters[s_id] = next_num
            code_map[(s_id, t_id)] = f"{sub_code}{next_num}"

    return code_map, teacher_direct_code


def get_teacher_allowed_classroom_ids(user):
    """
    Returns a set of Classroom IDs that a teacher is assigned to teach via Timetable,
    or as homeroom teacher, or via ClassSubject.
    Returns an empty set if user is not a teacher, has no profile, or has no assigned classrooms.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return set()

    teacher_profile = getattr(user, 'teacher_profile', None)
    if not teacher_profile:
        from apps.teachers.models import Teacher
        teacher_profile = Teacher.objects.filter(user=user).first()

    if not teacher_profile:
        return set()

    from .models import Timetable, Classroom, ClassSubject
    timetable_cls_ids = set(Timetable.objects.filter(teacher=teacher_profile).values_list('classroom_id', flat=True))
    homeroom_cls_ids = set(Classroom.objects.filter(homeroom_teacher=teacher_profile).values_list('id', flat=True))
    class_subject_cls_ids = set(ClassSubject.objects.filter(teacher=teacher_profile).values_list('classroom_id', flat=True))

    return timetable_cls_ids | homeroom_cls_ids | class_subject_cls_ids
