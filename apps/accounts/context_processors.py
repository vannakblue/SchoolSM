import os
from pathlib import Path
from django.conf import settings
from .models import SchoolProfile
from .menu_registry import get_role_permissions_map, get_menu_catalog
from apps.academics.utils import get_active_academic_year
from apps.academics.models import AcademicYear

def user_role_context(request):
    """
    Context processor to pass user role flags, active academic year, global school profile,
    and dynamic database-driven sidebar catalog & permissions to all templates
    """
    is_maintenance_mode = (Path(settings.BASE_DIR) / 'maintenance.flag').exists() or os.environ.get('MAINTENANCE_MODE') == '1'
    if not is_maintenance_mode:
        try:
            from apps.attendance.models import AttendanceSetting
            setting_val = AttendanceSetting.objects.values_list('is_maintenance_mode', flat=True).first()
            if setting_val:
                is_maintenance_mode = True
        except Exception:
            pass
    try:
        school_info = SchoolProfile.get_settings()
    except Exception:
        school_info = None

    try:
        active_academic_year = get_active_academic_year(request)
        all_academic_years = AcademicYear.objects.all().order_by('-start_date')
    except Exception:
        active_academic_year = None
        all_academic_years = []

    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return {
            'is_admin': False,
            'is_accountant': False,
            'is_teacher': False,
            'is_student': False,
            'current_user_role': 'ANONYMOUS',
            'school_info': school_info,
            'active_academic_year': active_academic_year,
            'all_academic_years': all_academic_years,
            'menu_perms': {},
            'sidebar_catalog': [],
            'is_maintenance_mode': is_maintenance_mode,
        }
    
    user = request.user
    role = getattr(user, 'role', 'ADMIN')
    
    is_admin = user.is_superuser or role == 'ADMIN'
    is_accountant = role == 'ACCOUNTANT'
    is_teacher = role == 'TEACHER'
    is_student = role == 'STUDENT'

    # Check fee collection authorization
    is_fee_collector = is_admin or is_accountant
    if is_teacher and hasattr(user, 'teacher_profile') and user.teacher_profile.is_fee_collector:
        is_fee_collector = True

    # Retrieve dynamic menu permissions for the user's role
    menu_perms = get_role_permissions_map(role) if not is_admin else {}

    # Build dynamic sidebar catalog filtered by database permissions
    try:
        raw_catalog = get_menu_catalog()
        sidebar_catalog = []
        current_path = getattr(request, 'path', '').rstrip('/') + '/'
        current_url_name = getattr(getattr(request, 'resolver_match', None), 'url_name', '')

        # 1. Collect all visible items across sections
        all_visible_items = []
        for sec in raw_catalog:
            sec_allowed = is_admin or menu_perms.get(sec['key'], False)
            if not (is_admin or sec_allowed):
                continue
            for item in sec.get('items', []):
                if item.get('is_admin_only') and not is_admin:
                    continue
                if is_admin or menu_perms.get(item['key'], False):
                    all_visible_items.append((sec, item))

        # 2. Find the single best active item (Exact url_name first, then longest matching URL prefix)
        best_active_key = None
        # Check exact url_name match
        if current_url_name:
            for sec, item in all_visible_items:
                if item.get('url_name') and item.get('url_name') == current_url_name:
                    best_active_key = item.get('key')
                    break

        # Fallback to longest URL prefix match if no exact url_name matched
        if not best_active_key and current_path:
            longest_match_len = 0
            for sec, item in all_visible_items:
                item_url = item.get('url', '#')
                if item_url and item_url not in ['#', '/']:
                    normalized_item_url = item_url.rstrip('/') + '/'
                    if current_path.startswith(normalized_item_url):
                        if len(normalized_item_url) > longest_match_len:
                            longest_match_len = len(normalized_item_url)
                            best_active_key = item.get('key')
            # Root path special case
            if not best_active_key and current_path == '/':
                for sec, item in all_visible_items:
                    if item.get('url') == '/':
                        best_active_key = item.get('key')
                        break

        # 3. Build sidebar catalog structure with single active highlight
        for sec in raw_catalog:
            sec_allowed = is_admin or menu_perms.get(sec['key'], False)
            visible_items = []
            for item in sec.get('items', []):
                if item.get('is_admin_only') and not is_admin:
                    continue
                if is_admin or menu_perms.get(item['key'], False):
                    item_dict = dict(item)
                    item_dict['is_current_active'] = (item.get('key') == best_active_key)
                    visible_items.append(item_dict)

            if (is_admin or sec_allowed) and visible_items:
                sec_dict = dict(sec)
                sec_dict['visible_items'] = visible_items
                sec_dict['html_id'] = sec['key'].replace('_', '-')
                sidebar_catalog.append(sec_dict)
    except Exception:
        sidebar_catalog = []

    pending_teacher_leaves_count = 0
    if is_admin:
        try:
            from apps.teachers.models import TeacherLeaveRequest
            pending_teacher_leaves_count = TeacherLeaveRequest.objects.filter(status=TeacherLeaveRequest.Status.PENDING).count()
        except Exception:
            pending_teacher_leaves_count = 0


    return {
        'is_admin': is_admin,
        'is_accountant': is_accountant,
        'is_teacher': is_teacher,
        'is_student': is_student,
        'is_fee_collector': is_fee_collector,
        'current_user_role': role,
        'user_display_name': user.display_name if hasattr(user, 'display_name') else user.username,
        'school_info': school_info,
        'active_academic_year': active_academic_year,
        'all_academic_years': all_academic_years,
        'menu_perms': menu_perms,
        'sidebar_catalog': sidebar_catalog,
        'pending_teacher_leaves_count': pending_teacher_leaves_count,
        'is_maintenance_mode': is_maintenance_mode,
    }



