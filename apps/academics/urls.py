from django.urls import path
from . import views

urlpatterns = [
    # Master Restore
    path('master-restore/', views.master_restore_defaults, name='master_restore_defaults'),

    # Location AJAX APIs (Dropdowns Cascading)
    path('api/locations/provinces/', views.api_locations_provinces, name='api_locations_provinces'),
    path('api/locations/districts/', views.api_locations_districts, name='api_locations_districts'),
    path('api/locations/communes/', views.api_locations_communes, name='api_locations_communes'),
    path('api/locations/villages/', views.api_locations_villages, name='api_locations_villages'),

    # Location Manager (Admin Only)
    path('locations/', views.location_manager_view, name='location_manager_view'),
    path('locations/create/', views.location_item_create, name='location_item_create'),
    path('locations/edit/', views.location_item_edit, name='location_item_edit'),
    path('locations/delete/', views.location_item_delete, name='location_item_delete'),
    path('locations/sync-excel/', views.location_sync_excel, name='location_sync_excel'),
    path('locations/export-excel/', views.location_export_excel, name='location_export_excel'),
    path('locations/export-csv/', views.location_export_csv, name='location_export_csv'),

    # Academic Years (ឆ្នាំសិក្សា CRUD & Set Current & Switch)
    path('academic-years/', views.academic_year_list, name='academic_year_list'),
    path('academic-years/create/', views.academic_year_create, name='academic_year_create'),
    path('academic-years/<int:pk>/edit/', views.academic_year_edit, name='academic_year_edit'),
    path('academic-years/<int:pk>/delete/', views.academic_year_delete, name='academic_year_delete'),
    path('academic-years/<int:pk>/set-current/', views.academic_year_set_current, name='academic_year_set_current'),
    path('academic-years/<int:pk>/switch/', views.academic_year_switch, name='academic_year_switch'),

    # Grade Levels (កម្រិតថ្នាក់ CRUD)
    path('grade-levels/', views.grade_level_list, name='grade_level_list'),
    path('grade-levels/create/', views.grade_level_create, name='grade_level_create'),
    path('grade-levels/<int:pk>/edit/', views.grade_level_edit, name='grade_level_edit'),
    path('grade-levels/<int:pk>/delete/', views.grade_level_delete, name='grade_level_delete'),

    # Academic Tracks (ជំនាញ/កម្មវិធីសិក្សា CRUD)
    path('tracks/', views.academic_track_list, name='academic_track_list'),
    path('tracks/create/', views.academic_track_create, name='academic_track_create'),
    path('tracks/<int:pk>/edit/', views.academic_track_edit, name='academic_track_edit'),
    path('tracks/<int:pk>/delete/', views.academic_track_delete, name='academic_track_delete'),
    path('api/tracks/', views.api_academic_tracks, name='api_academic_tracks'),

    # Grade Level Enrollment Options (បែបបទបំពេញតាមកម្រិតថ្នាក់)
    path('grade-options/', views.grade_options_manager, name='grade_options_manager'),
    path('grade-options/save/', views.grade_option_save, name='grade_option_create'),
    path('grade-options/<int:pk>/save/', views.grade_option_save, name='grade_option_edit'),
    path('grade-options/<int:pk>/delete/', views.grade_option_delete, name='grade_option_delete'),
    path('grade-options/reorder/', views.grade_options_reorder, name='grade_options_reorder'),
    path('grade-options/<int:pk>/width/', views.grade_option_update_width, name='grade_option_update_width'),

    # Classrooms
    path('classrooms/', views.classroom_list, name='classroom_list'),
    path('classrooms/create/', views.classroom_create, name='classroom_create'),
    path('classrooms/<int:pk>/edit/', views.classroom_edit, name='classroom_edit'),
    path('classrooms/<int:pk>/delete/', views.classroom_delete, name='classroom_delete'),
    path('classrooms/<int:pk>/subjects/', views.classroom_manage_subjects, name='classroom_manage_subjects'),
    path('classrooms/bulk-delete/', views.classroom_bulk_delete, name='classroom_bulk_delete'),
    path('classrooms/delete-all/', views.classroom_delete_all, name='classroom_delete_all'),
    path('classrooms/restore-default/', views.classroom_restore_default, name='classroom_restore_default'),

    # Subjects
    path('subjects/', views.subject_list, name='subject_list'),
    path('subjects/create/', views.subject_create, name='subject_create'),
    path('subjects/<int:pk>/edit/', views.subject_edit, name='subject_edit'),
    path('subjects/<int:pk>/delete/', views.subject_delete, name='subject_delete'),
    path('subjects/restore-default/', views.subject_restore_default, name='subject_restore_default'),

    # Scoring Rules Manager
    path('scoring-rules/', views.grade_rules_manager, name='grade_rules_manager'),
    path('scoring-rules/reset/', views.reset_grade_rules_to_moeys, name='reset_grade_rules_to_moeys'),
    path('scoring-rules/save-default/', views.save_current_as_default, name='save_current_as_default'),
    path('scoring-rules/restore-custom/', views.restore_saved_custom_default, name='restore_saved_custom_default'),
    path('scoring-rules/delete-all/', views.grade_rules_delete_all, name='grade_rules_delete_all'),

    # Timetable & Master Matrix
    path('timetable/', views.timetable_view, name='timetable_view'),
    path('timetable/daily-reports/', views.timetable_daily_reports_view, name='timetable_daily_reports_view'),
    path('timetable/daily-reports/export-excel/', views.timetable_daily_reports_export_excel, name='timetable_daily_reports_export_excel'),
    path('timetable/student-teacher/', views.student_teacher_timetable_view, name='student_teacher_timetable_view'),
    path('timetable/save-matrix/', views.timetable_save_matrix, name='timetable_save_matrix'),
    path('timetable/auto-generate/', views.timetable_auto_generate, name='timetable_auto_generate'),
    path('timetable/export-excel/', views.timetable_export_excel, name='timetable_export_excel'),
    path('timetable/clear-all/', views.timetable_clear_all, name='timetable_clear_all'),
    path('timetable/create/', views.timetable_create, name='timetable_create'),
    path('timetable/<int:pk>/edit/', views.timetable_edit, name='timetable_edit'),
    path('timetable/<int:pk>/delete/', views.timetable_delete, name='timetable_delete'),
    path('timetable/clear/<int:class_id>/', views.timetable_clear_class, name='timetable_clear_class'),

    # Subject Requirements & Weekly Hours
    path('subject-requirements/', views.subject_requirements_manager, name='subject_requirements_manager'),
    path('subject-requirements/reset/', views.subject_requirements_reset, name='subject_requirements_reset'),
    path('subject-requirements/restore-moeys/', views.subject_requirements_restore_moeys, name='subject_requirements_restore_moeys'),
    path('subject-requirements/save-default/', views.subject_requirements_save_custom_default, name='subject_requirements_save_custom_default'),
    path('subject-requirements/restore-custom/', views.subject_requirements_restore_custom_default, name='subject_requirements_restore_custom_default'),
    path('subject-requirements/<int:subject_id>/delete/', views.subject_requirement_row_delete, name='subject_requirement_row_delete'),

    # Teacher Class & Subject Assignments
    path('teacher-assignments/', views.teacher_assignments_manager, name='teacher_assignments_manager'),

    # Student Promotion / Academic Year Transfer
    path('promotion/', views.student_promotion_view, name='student_promotion'),
]
