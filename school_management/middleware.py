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
        att_settings = None
        is_maintenance = self.flag_path.exists() or os.environ.get('MAINTENANCE_MODE') == '1'

        if not is_maintenance:
            try:
                from apps.attendance.models import AttendanceSetting
                att_settings = AttendanceSetting.get_settings()
                if att_settings and att_settings.is_maintenance_mode:
                    is_maintenance = True
            except Exception:
                pass

        if is_maintenance:
            # Exempt static and media files
            path = request.path_info
            if path.startswith(settings.STATIC_URL) or (settings.MEDIA_URL and path.startswith(settings.MEDIA_URL)):
                return self.get_response(request)

            # Exempt superusers / staff / admin role to allow live debugging & system management
            if hasattr(request, 'user') and request.user.is_authenticated:
                if request.user.is_superuser or request.user.is_staff or getattr(request.user, 'role', '') == 'ADMIN':
                    return self.get_response(request)

            # Exempt admin URLs and auth login/logout so admins can sign in
            exempt_prefixes = [
                '/admin-panel/',
                '/admin/',
                '/accounts/login/',
                '/accounts/logout/',
                '/accounts/demo-login/ADMIN/',
                '/attendance/admin-hub/',
                '/maintenance-preview/',
            ]
            if any(path.startswith(prefix) for prefix in exempt_prefixes):
                return self.get_response(request)

            # Render 503 Maintenance page for regular users / students / teachers
            custom_msg = att_settings.maintenance_message if att_settings and att_settings.maintenance_message else None
            return render(request, 'maintenance.html', {'maintenance_message': custom_msg}, status=503)

        return self.get_response(request)
