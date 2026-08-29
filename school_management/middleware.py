import os
from pathlib import Path
from django.conf import settings
from django.shortcuts import render

class MaintenanceModeMiddleware:
    """
    Middleware that checks for the existence of 'maintenance.flag' or 'MAINTENANCE_MODE' env.
    If active, it intercepts non-admin requests and renders the maintenance page (HTTP 503).
    Superusers and Admin panel remain accessible for verification.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.flag_path = Path(settings.BASE_DIR) / 'maintenance.flag'

    def __call__(self, request):
        path = request.path_info

        # 1. Exempt static and media files first (Zero DB overhead)
        if path.startswith(settings.STATIC_URL) or (settings.MEDIA_URL and path.startswith(settings.MEDIA_URL)):
            return self.get_response(request)

        # 2. Check maintenance state
        is_maintenance = self.flag_path.exists() or os.environ.get('MAINTENANCE_MODE') == '1'
        custom_msg = None

        if not is_maintenance:
            try:
                from apps.attendance.models import AttendanceSetting
                setting_row = AttendanceSetting.objects.values_list('is_maintenance_mode', 'maintenance_message').first()
                if setting_row and setting_row[0]:
                    is_maintenance = True
                    custom_msg = setting_row[1]
            except Exception:
                pass

        if is_maintenance:
            # Exempt superusers / staff / admin role
            if hasattr(request, 'user') and request.user.is_authenticated:
                if request.user.is_superuser or request.user.is_staff or getattr(request.user, 'role', '') == 'ADMIN':
                    return self.get_response(request)

            # Exempt admin URLs and authentication pages so admin can log in and manage system
            exempt_prefixes = [
                '/admin-panel/',
                '/admin/',
                '/accounts/login/',
                '/accounts/logout/',
                '/accounts/demo-login/ADMIN/',
                '/attendance/admin-hub/',
                '/attendance/admin_hub/',
                '/dashboard/admin/',
                '/maintenance-preview/',
            ]
            if any(path.startswith(prefix) for prefix in exempt_prefixes):
                return self.get_response(request)

            # Render 503 Maintenance page for regular users / students / teachers
            return render(request, 'maintenance.html', {'maintenance_message': custom_msg}, status=503)

        return self.get_response(request)
