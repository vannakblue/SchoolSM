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
        is_maintenance = self.flag_path.exists() or os.environ.get('MAINTENANCE_MODE') == '1'

        if is_maintenance:
            # Exempt static and media files
            path = request.path_info
            if path.startswith(settings.STATIC_URL) or (settings.MEDIA_URL and path.startswith(settings.MEDIA_URL)):
                return self.get_response(request)

            # Exempt superusers / staff to allow live debugging
            if hasattr(request, 'user') and request.user.is_authenticated and (request.user.is_superuser or request.user.is_staff):
                return self.get_response(request)

            # Exempt admin URLs and auth login/logout so admins can sign in
            exempt_prefixes = [
                '/admin-panel/',
                '/admin/',
                '/accounts/login/',
                '/accounts/logout/',
            ]
            if any(path.startswith(prefix) for prefix in exempt_prefixes):
                return self.get_response(request)

            # Render 503 Maintenance page for regular users / students / teachers
            return render(request, 'maintenance.html', status=503)

        return self.get_response(request)
