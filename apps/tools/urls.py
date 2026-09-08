from django.urls import path
from . import views

urlpatterns = [
    # Main Hub
    path('', views.tools_hub, name='tools_hub'),

    # PDF Tools
    path('pdf-merge/', views.pdf_merge_view, name='tool_pdf_merge'),
    path('pdf-split/', views.pdf_split_view, name='tool_pdf_split'),
    path('pdf-to-word-excel/', views.pdf_to_word_excel_view, name='tool_pdf_to_word_excel'),
    path('images-to-pdf/', views.images_to_pdf_view, name='tool_images_to_pdf'),
    path('doc-scanner/', views.doc_scanner_view, name='tool_doc_scanner'),

    # Image & ID Photo Tools
    path('image-editor/', views.image_editor_view, name='tool_image_editor'),
    path('id-photo-maker/', views.id_photo_maker_view, name='tool_id_photo_maker'),
    path('image-compressor/', views.image_compressor_view, name='tool_image_compressor'),

    # QR Code Suite
    path('qr-generator/', views.qr_generator_view, name='tool_qr_generator'),
    path('qr-scanner/', views.qr_scanner_view, name='tool_qr_scanner'),

    # Classroom & Academic Utilities
    path('khmer-number-converter/', views.khmer_number_converter_view, name='tool_khmer_number_converter'),
    path('text-analyzer/', views.text_analyzer_view, name='tool_text_analyzer'),
    path('voice-typing/', views.voice_typing_view, name='tool_voice_typing'),
    path('classroom-picker/', views.classroom_picker_view, name='tool_classroom_picker'),
    path('calculator-converter/', views.calculator_converter_view, name='tool_calculator_converter'),

    # Database Backup & Snapshot Suite
    path('database-backup/', views.database_backup_view, name='tool_database_backup'),
    path('database-backup/create/', views.api_create_database_backup, name='tool_database_backup_create'),
    path('database-backup/download/<str:filename>/', views.download_database_backup, name='tool_database_backup_download'),
    path('database-backup/download/', views.download_database_backup, {'filename': 'current'}, name='tool_database_download_live'),
    path('database-backup/send-telegram/', views.api_send_backup_to_telegram, name='tool_database_backup_send_telegram'),
    path('database-backup/save-schedule/', views.api_save_backup_schedule, name='tool_database_backup_save_schedule'),
    path('database-backup/trigger-schedule/', views.api_trigger_schedule_check, name='tool_database_backup_trigger_schedule'),
    path('database-backup/restore/', views.api_restore_database_backup, name='tool_database_backup_restore'),
    path('database-backup/upload-restore/', views.api_upload_restore_database, name='tool_database_backup_upload_restore'),
    path('database-backup/delete/<str:filename>/', views.api_delete_database_backup, name='tool_database_backup_delete'),
    path('academic-year-backup/<int:year_id>/export/', views.tool_academic_year_backup_export, name='tool_academic_year_backup_export'),
    path('academic-year-backup/restore/', views.tool_academic_year_backup_restore, name='tool_academic_year_backup_restore'),

    # Google Sheets & Google Drive Suite
    path('google-sheets/', views.google_sheets_dashboard_view, name='tool_google_sheets'),
    path('google-sheets/save-config/', views.api_save_google_sheets_config, name='tool_google_sheets_save_config'),
    path('google-sheets/link/', views.api_link_google_sheet, name='tool_google_sheets_link'),
    path('google-sheets/unlink/', views.api_unlink_google_sheet, name='tool_google_sheets_unlink'),
    path('google-sheets/sync/', views.api_sync_google_sheets, name='tool_google_sheets_sync'),
    path('google-sheets/restore/', views.api_restore_google_sheets, name='tool_google_sheets_restore'),

    # Backend API Endpoints
    path('api/ai-assist/', views.api_tool_ai_assist, name='api_tool_ai_assist'),
    path('api/classroom/<int:classroom_id>/students/', views.api_classroom_students, name='api_tool_classroom_students'),
    path('api/pdf-merge/', views.api_pdf_merge, name='api_tool_pdf_merge'),
    path('api/pdf-to-docx/', views.api_pdf_to_docx, name='api_tool_pdf_to_docx'),
    path('api/pdf-to-excel/', views.api_pdf_to_excel, name='api_tool_pdf_to_excel'),
    path('api/images-to-pdf/', views.api_images_to_pdf, name='api_tool_images_to_pdf'),

    # 📱 Mobile App & APK Builder Suite
    path('mobile-app/', views.tool_mobile_app_manager, name='tool_mobile_app_manager'),
    path('mobile-app/build/', views.api_build_mobile_apk, name='api_build_mobile_apk'),
    path('mobile-app/upload/', views.api_upload_mobile_apk, name='api_upload_mobile_apk'),
    path('mobile-app/status/', views.api_mobile_build_status, name='api_mobile_build_status'),
    path('mobile-app/download/', views.tool_public_mobile_download, name='tool_public_mobile_download'),
    path('mobile-app/download-apk/', views.tool_download_mobile_apk, name='tool_download_mobile_apk'),
    path('mobile-app/download-ipa/', views.tool_download_mobile_ipa, name='tool_download_mobile_ipa'),
    path('mobile-app/qr-code/', views.tool_mobile_apk_qr, name='tool_mobile_apk_qr'),
    path('mobile-app/export-ios/', views.tool_export_ios_project, name='tool_export_ios_project'),
    path('mobile-app/save-cloud-config/', views.api_save_mobile_cloud_config, name='api_save_mobile_cloud_config'),
]

