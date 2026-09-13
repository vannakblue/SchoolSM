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

    # 3. Database is_current=True
    ay = AcademicYear.objects.filter(is_current=True).first()
    if ay:
        return ay

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

