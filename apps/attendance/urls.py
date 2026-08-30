from django.urls import path
from . import views
from apps.teachers import views as teacher_views

urlpatterns = [
    path('', views.student_attendance_grid, name='student_attendance_grid'),
    path('report/', views.attendance_report, name='attendance_report'),
    path('teacher-report/', teacher_views.teacher_attendance_report, name='teacher_attendance_report_alias'),
    path('at-risk/', views.at_risk_attendance_view, name='at_risk_attendance'),
    path('admin-hub/', views.attendance_admin_hub, name='attendance_admin_hub'),
    path('admin_hub/', views.attendance_admin_hub),
    path('admin-hub/restriction/<int:pk>/delete/', views.delete_calendar_restriction_view, name='delete_calendar_restriction'),
    path('assembly/', views.assembly_attendance_view, name='assembly_attendance'),
    path('telegram/send-class/', views.send_class_attendance_telegram_view, name='send_class_attendance_telegram'),
    path('telegram/send-missing-teachers/', views.send_missing_teachers_telegram_view, name='send_missing_teachers_telegram'),
]


