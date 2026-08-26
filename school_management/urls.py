from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

from apps.accounts.views import telegram_webhook, init_admin_view

urlpatterns = [
    path('admin-panel/', admin.site.urls),
    path('', lambda request: redirect('dashboard_redirect'), name='root_redirect'),
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
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
