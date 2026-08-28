from django.urls import path
from . import views
from . import biometric_views

urlpatterns = [
    path('', views.teacher_list, name='teacher_list'),
    path('create/', views.teacher_create, name='teacher_create'),
    path('export/excel/', views.teacher_export_excel, name='teacher_export_excel'),
    path('import/', views.teacher_import, name='teacher_import'),
    path('import/template/excel/', views.teacher_import_template_excel, name='teacher_import_template_excel'),
    path('import/template/csv/', views.teacher_import_template_csv, name='teacher_import_template_csv'),
    path('attendance/', views.teacher_attendance_view, name='teacher_attendance'),
    path('attendance/report/', views.teacher_attendance_report, name='teacher_attendance_report'),
    
    # --- Multi-Method Attendance Suite ---
    # 1. Dynamic QR Kiosk & Mobile Scan
    path('attendance/kiosk/', biometric_views.teacher_kiosk_view, name='teacher_kiosk_view'),
    path('attendance/kiosk/api/token/', biometric_views.api_kiosk_qr_token, name='api_kiosk_qr_token'),
    path('attendance/scan/', biometric_views.mobile_qr_scan_view, name='teacher_mobile_qr_scan'),
    path('attendance/scan/api/process/', biometric_views.api_process_qr_checkin, name='api_process_qr_checkin'),

    # 2. Webcam Face Recognition AI
    path('attendance/face-ai/', biometric_views.face_ai_kiosk_view, name='teacher_face_ai_kiosk'),
    path('attendance/face-ai/api/enrolled/', biometric_views.api_get_enrolled_faces, name='api_get_enrolled_faces'),
    path('attendance/face-ai/api/checkin/', biometric_views.api_face_checkin, name='api_face_checkin'),
    path('attendance/face-enroll/<int:pk>/', biometric_views.face_enroll_view, name='face_enroll'),

    # 3. Biometric Hub (ZKTeco / Hikvision / USB / File Import)
    path('attendance/biometric/', biometric_views.biometric_hub_view, name='biometric_hub'),
    path('attendance/biometric/api/push/', biometric_views.api_biometric_push_webhook, name='api_biometric_push_webhook'),
    path('attendance/biometric/api/sync/', biometric_views.api_sync_biometric_device, name='api_sync_biometric_device'),
    path('attendance/biometric/import/', biometric_views.biometric_file_import_view, name='biometric_file_import'),
    path('attendance/biometric/api/usb-punch/', biometric_views.api_usb_fingerprint_punch, name='api_usb_fingerprint_punch'),

    # 4. Admin Method Settings & Punch Logs Audit
    path('attendance/settings/', biometric_views.teacher_attendance_settings_view, name='teacher_attendance_settings'),
    path('attendance/logs/', biometric_views.teacher_punch_logs_view, name='teacher_punch_logs'),
    path('my-attendance/', biometric_views.teacher_my_attendance_history_view, name='teacher_my_attendance_history'),

    # Teacher Information Re-Submission Campaign & Self-Update Portal
    path('campaign/settings/', views.teacher_update_campaign_view, name='teacher_update_campaign'),
    path('portal/update/', views.teacher_self_update_portal, name='teacher_self_update_portal'),

    # Leaves & Profile
    path('leave/', views.teacher_leave_list, name='teacher_leave_list'),
    path('leave/apply/', views.teacher_leave_create, name='teacher_leave_create'),
    path('leave/<int:pk>/print/', views.teacher_leave_print_letter, name='teacher_leave_print_letter'),
    path('delete-all/', views.teacher_delete_all, name='teacher_delete_all'),
    path('<int:pk>/', views.teacher_detail, name='teacher_detail'),
    path('<int:pk>/edit/', views.teacher_edit, name='teacher_edit'),
    path('<int:pk>/delete/', views.teacher_delete, name='teacher_delete'),
]



