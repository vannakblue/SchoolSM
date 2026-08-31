from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect, render
from django.http import JsonResponse, HttpResponse
import sys, traceback

from apps.accounts.views import telegram_webhook, init_admin_view

def health_check(request):
    return JsonResponse({'status': 'ok', 'service': 'SchoolSM', 'message': 'Server is active and healthy'})

def custom_500(request):
    try:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        if exc_type:
            tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
            tb_str = "".join(tb_lines)
            exc_name = getattr(exc_type, '__name__', str(exc_type))
        else:
            tb_str = "No active traceback available."
            exc_name = "Internal Server Error"
        
        path_str = getattr(request, 'path', 'Unknown Path')
        user_str = str(getattr(request, 'user', 'Anonymous'))
        return HttpResponse(f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Server Error (500) | SchoolSM Diagnostics</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light p-4">
    <div class="container">
        <div class="card border-danger shadow-sm my-4">
            <div class="card-header bg-danger text-white fw-bold">
                ⚠️ 500 Internal Server Error - System Diagnostic Report
            </div>
            <div class="card-body">
                <p class="mb-2"><strong>Path:</strong> <code>{path_str}</code></p>
                <p class="mb-2"><strong>User:</strong> {user_str}</p>
                <p class="mb-3"><strong>Exception:</strong> <span class="text-danger fw-bold">{exc_name}: {exc_value}</span></p>
                <h6 class="fw-bold">Traceback:</h6>
                <pre class="bg-dark text-light p-3 rounded small" style="max-height: 400px; overflow: auto;">{tb_str}</pre>
                <a href="{path_str}" class="btn btn-outline-primary mt-2">Refresh Page</a>
                <a href="/dashboard/admin/" class="btn btn-secondary mt-2 ms-2">Back to Dashboard</a>
            </div>
        </div>
    </div>
</body>
</html>""", status=500)
    except Exception as fallback_err:
        return HttpResponse(f"Internal Server Error (500): {str(fallback_err)}", status=500)

handler500 = 'school_management.urls.custom_500'

urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('ping/', health_check, name='ping_check'),
    path('admin-panel/', admin.site.urls),
    path('', lambda request: redirect('dashboard_redirect'), name='root_redirect'),
    path('maintenance-preview/', lambda request: render(request, 'maintenance.html'), name='maintenance_preview'),
    path('init-admin/', init_admin_view, name='root_init_admin'),
    path('api/telegram/webhook/', telegram_webhook, name='telegram_webhook'),
    
    path('accounts/', include('apps.accounts.urls')),
    path('dashboard/', include('apps.dashboard.urls')),
    path('academics/', include('apps.academics.urls')),
    path('students/', include('apps.students.urls')),
    path('teachers/', include('apps.teachers.urls')),
    path('attendance/', include('apps.attendance.urls')),
    path('examinations/', include('apps.examinations.urls')),
    path('finance/', include('apps.finance.urls')),
    path('extras/', include('apps.extras.urls')),
    path('tools/', include('apps.tools.urls')),
    path('api/v1/', include('apps.mobile_api.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
