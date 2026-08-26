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
