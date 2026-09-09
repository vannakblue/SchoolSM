from django.urls import path
from . import views

urlpatterns = [
    path('', views.student_list, name='student_list'),
    path('enroll/', views.student_enroll, name='student_enroll'),
    path('enroll/online/', views.public_student_enroll, name='public_student_enroll'),
    path('enroll/success/<int:pk>/', views.public_enroll_success, name='public_enroll_success'),
    path('enroll/qr/', views.enrollment_qr_code, name='enrollment_qr_code'),
    path('import/', views.student_import, name='student_import'),
    path('import/template/excel/', views.download_student_template_excel, name='download_student_template_excel'),
    path('import/template/csv/', views.download_student_template_csv, name='download_student_template_csv'),
    
    # Scholarship / Fee Types CRUD
    path('scholarships/', views.scholarship_type_list, name='scholarship_type_list'),
    path('scholarships/save/', views.scholarship_type_save, name='scholarship_type_create'),
    path('scholarships/<int:pk>/save/', views.scholarship_type_save, name='scholarship_type_edit'),
    path('scholarships/<int:pk>/delete/', views.scholarship_type_delete, name='scholarship_type_delete'),

    # Student Academic Statuses CRUD
    path('statuses/', views.student_status_list, name='student_status_list'),
    path('statuses/save/', views.student_status_save, name='student_status_create'),
    path('statuses/<int:pk>/save/', views.student_status_save, name='student_status_edit'),
    path('statuses/<int:pk>/delete/', views.student_status_delete, name='student_status_delete'),

    # AJAX API for Grade-Specific Enrollment Options & Student ID Validation
    path('api/grade-options/', views.api_get_grade_options, name='api_get_grade_options'),
    path('api/check-student-id/', views.api_check_student_id, name='api_check_student_id'),
    path('api/check-duplicate/', views.api_check_duplicate_student, name='api_check_duplicate_student'),
    path('api/generate-student-id/', views.api_generate_student_id, name='api_generate_student_id'),
    path('api/preview-student-id/', views.api_preview_student_id_pattern, name='api_preview_student_id_pattern'),

    # MoEYS Student Age & Grade Level Statistics Matrix
    path('statistics/age-grade/', views.student_age_grade_statistics, name='student_age_grade_statistics'),
    path('statistics/age-grade/export-excel/', views.export_student_age_grade_excel, name='export_student_age_grade_excel'),
    path('api/age-grade-drilldown/', views.api_student_age_grade_drilldown, name='api_student_age_grade_drilldown'),
    path('api/set-repeater-status/<int:student_id>/', views.api_set_student_repeater_status, name='api_set_student_repeater_status'),
    path('api/batch-set-repeater-status/', views.api_batch_set_student_repeater_status, name='api_batch_set_student_repeater_status'),
    path('api/classroom-repeater-list/', views.api_classroom_repeater_list, name='api_classroom_repeater_list'),

    # MoEYS Customizable Student Age Roster Reports (Format A & B)
    path('reports/age-roster/', views.student_age_custom_roster, name='student_age_custom_roster'),
    path('reports/age-roster/export-excel/', views.student_age_custom_roster_export_excel, name='student_age_custom_roster_export_excel'),
    path('reports/age-roster/print/', views.student_age_custom_roster_print, name='student_age_custom_roster_print'),

    # MoEYS Official Individual Student Information Extract (សម្រង់ព័ត៌មានសិស្សម្នាក់ៗ - 35 Columns)
    path('reports/moeys-individual-roster/', views.moeys_individual_student_roster, name='moeys_individual_student_roster'),
    path('reports/moeys-individual-roster/upload/', views.moeys_individual_student_roster_upload, name='moeys_individual_student_roster_upload'),
    path('reports/moeys-individual-roster/export-excel/', views.moeys_individual_student_roster_export_excel, name='moeys_individual_student_roster_export_excel'),
    path('reports/moeys-individual-roster/print/', views.moeys_individual_student_roster_print, name='moeys_individual_student_roster_print'),

    path('<int:pk>/', views.student_detail, name='student_detail'),
    path('<int:pk>/edit/', views.student_edit, name='student_edit'),
    path('<int:pk>/id-card/', views.student_id_card, name='student_id_card'),
    path('id-cards/', views.batch_student_id_cards, name='batch_student_id_cards'),
    path('<int:pk>/quick-status/', views.api_quick_set_student_status, name='student_quick_status'),
    path('<int:pk>/exam-status/', views.api_set_student_exam_status, name='student_set_exam_status'),
    path('batch/exam-status/', views.api_batch_set_student_exam_status, name='student_batch_set_exam_status'),
    path('batch-romanize/', views.batch_romanize_latin_names, name='batch_romanize_latin_names'),
    path('api/romanize/', views.api_romanize_khmer_name, name='api_romanize_khmer_name'),

    # Academic Year Student Archive & Safe Purge URLs
    path('archives/', views.student_archives_list, name='student_archives_list'),
    path('archives/<int:pk>/download/', views.download_student_archive_excel, name='download_student_archive_excel'),
    path('archives/<int:pk>/json/', views.api_get_archive_json_snapshot, name='api_get_archive_json_snapshot'),
    path('archives/<int:pk>/restore/', views.api_restore_student_archive, name='api_restore_student_archive'),
    path('api/academic-year-purge-preview/', views.api_get_academic_year_purge_preview, name='api_get_academic_year_purge_preview'),
    path('api/academic-year-purge-execute/', views.api_execute_academic_year_purge, name='api_execute_academic_year_purge'),
]

