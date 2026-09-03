from django.urls import path
from . import views

urlpatterns = [
    # Monthly/Semester Terms & Classroom Grades
    path('terms/', views.exam_term_list, name='exam_term_list'),
    path('terms/create/', views.exam_term_create, name='exam_term_create'),
    path('terms/<int:term_id>/edit/', views.exam_term_edit, name='exam_term_edit'),
    path('terms/<int:term_id>/delete/', views.exam_term_delete, name='exam_term_delete'),
    path('matrix/', views.grade_entry_matrix, name='grade_entry_matrix'),

    path('summary/', views.grade_summary_view, name='grade_summary'),
    path('results/semester/', views.semester_results_view, name='semester_results'),
    path('results/semester/export-excel/', views.export_semester_results_excel, name='export_semester_results_excel'),
    path('results/annual/', views.annual_results_view, name='annual_results'),
    path('results/annual/export-excel/', views.export_annual_results_excel, name='export_annual_results_excel'),
    path('api/transfer-grade/save/', views.api_save_transfer_grade, name='api_save_transfer_grade'),
    path('api/transfer-grade/<int:student_id>/', views.api_get_transfer_grade, name='api_get_transfer_grade'),
    path('report-card/<int:student_id>/<int:term_id>/', views.report_card_view, name='report_card'),
    path('api/report-card/send-telegram/', views.api_send_report_card_telegram, name='api_send_report_card_telegram'),
    path('api/report-card/send-class-telegram/', views.api_send_class_report_cards_telegram, name='api_send_class_report_cards_telegram'),

    # High School Standardized Examination System (តេស្តស្តង់ដា)
    path('standardized/', views.standardized_exam_list, name='standardized_exam_list'),
    path('standardized/create/', views.standardized_exam_create, name='standardized_exam_create'),
    path('standardized/<int:exam_id>/manage/', views.standardized_exam_manage, name='standardized_exam_manage'),
    path('standardized/<int:exam_id>/edit/', views.standardized_exam_edit, name='standardized_exam_edit'),
    path('standardized/<int:exam_id>/delete/', views.standardized_exam_delete, name='standardized_exam_delete'),

    # Candidates Roster & Excel
    path('standardized/<int:exam_id>/pull-candidates/', views.exam_pull_candidates, name='exam_pull_candidates'),
    path('standardized/<int:exam_id>/export-candidates/', views.exam_export_candidates_excel, name='exam_export_candidates_excel'),
    path('standardized/<int:exam_id>/import-candidates/', views.exam_import_candidates_excel, name='exam_import_candidates_excel'),

    # 25-Candidate Rooms Auto-Partitioning & Postings
    path('standardized/batch-generate-rooms/', views.exam_batch_generate_rooms, name='exam_batch_generate_rooms'),
    path('standardized/<int:exam_id>/generate-rooms/', views.exam_generate_rooms, name='exam_generate_rooms'),
    path('standardized/<int:exam_id>/room-postings/', views.exam_room_postings_view, name='exam_room_postings_view'),

    # Subject Attendance & Signature Sheets
    path('standardized/<int:exam_id>/attendance-sheets/', views.exam_subject_attendance_view, name='exam_subject_attendance_view'),

    # Room Scores Entry & Grade Computation
    path('standardized/<int:exam_id>/scores-entry/', views.exam_room_scores_entry, name='exam_room_scores_entry'),

    # Provisional Results Board & Excel
    path('standardized/<int:exam_id>/provisional-results/', views.exam_provisional_results_view, name='exam_provisional_results_view'),
    path('standardized/<int:exam_id>/export-provisional-excel/', views.exam_export_provisional_excel, name='exam_export_provisional_excel'),

    # Blind / Secret-Coded Exam Scoring System (៤ ជំហាន៖ កម្រិតថ្នាក់ -> មុខវិជ្ជា -> លេខកូដសម្ងាត់ -> ពិន្ទុ ០១ ដល់ ២៥)
    path('standardized/blind-scoring/', views.exam_blind_scoring_portal, name='exam_blind_scoring_portal'),
    path('standardized/api/get-subjects/<int:exam_id>/', views.api_exam_get_subjects, name='api_exam_get_subjects'),
    path('standardized/api/validate-secret-code/', views.api_exam_validate_secret_code, name='api_exam_validate_secret_code'),
    path('standardized/api/save-blind-scores/', views.api_exam_save_blind_scores, name='api_exam_save_blind_scores'),
    path('standardized/<int:exam_id>/toggle-grading-lock/', views.api_toggle_exam_grading_lock, name='api_toggle_exam_grading_lock'),
    path('standardized/<int:exam_id>/set-grading-window/', views.api_update_exam_grading_window, name='api_update_exam_grading_window'),

    # Admin Secret Codes Directory & Regenerate
    path('standardized/<int:exam_id>/secret-codes/', views.exam_secret_codes_directory, name='exam_secret_codes_directory'),
    path('standardized/<int:exam_id>/regenerate-secret-codes/', views.exam_regenerate_secret_codes, name='exam_regenerate_secret_codes'),

    # Disciplinary Hold & Contract Blocking APIs
    path('api/candidate/toggle-disciplinary-hold/', views.api_toggle_candidate_disciplinary_hold, name='api_toggle_candidate_disciplinary_hold'),
    path('api/candidate/batch-disciplinary-hold/', views.api_batch_toggle_disciplinary_hold, name='api_batch_toggle_disciplinary_hold'),

    # Monthly Student Exam Exclusions Management & APIs
    path('exclusions/', views.exam_exclusions_manage, name='exam_exclusions_manage'),
    path('api/exclusion/toggle/', views.api_toggle_exam_exclusion, name='api_toggle_exam_exclusion'),
    path('api/classroom/<int:classroom_id>/students/', views.api_get_students_by_classroom, name='api_get_students_by_classroom'),

    # Teacher Exam Invigilator / Proctor Shift Request System (ប្រព័ន្ធសុំវេនអនុរក្ស)
    path('invigilator-plans/', views.exam_invigilator_plans_list, name='exam_invigilator_plans_list'),
    path('invigilator-plans/create/', views.exam_invigilator_plan_create, name='exam_invigilator_plan_create'),
    path('invigilator-plans/<int:plan_id>/edit/', views.exam_invigilator_plan_edit, name='exam_invigilator_plan_edit'),
    path('invigilator-plans/<int:plan_id>/toggle-active/', views.exam_invigilator_plan_toggle_active, name='exam_invigilator_plan_toggle_active'),
    path('invigilator-plans/<int:plan_id>/delete/', views.exam_invigilator_plan_delete, name='exam_invigilator_plan_delete'),
    path('invigilator-plans/<int:plan_id>/quotas/', views.exam_invigilator_quotas_manage, name='exam_invigilator_quotas_manage'),
    path('invigilator-plans/<int:plan_id>/roster/', views.exam_invigilator_roster_view, name='exam_invigilator_roster_view'),
    path('invigilator-plans/<int:plan_id>/roster/print/', views.exam_invigilator_roster_print, name='exam_invigilator_roster_print'),
    path('invigilator-plans/<int:plan_id>/auto-assign/', views.api_invigilator_auto_assign, name='api_invigilator_auto_assign'),

    # Teacher Self-Service Portal & AJAX API
    path('invigilator-request/', views.exam_invigilator_teacher_portal, name='exam_invigilator_teacher_portal'),
    path('api/invigilator-slot/toggle/', views.api_toggle_invigilator_slot, name='api_toggle_invigilator_slot'),
]



