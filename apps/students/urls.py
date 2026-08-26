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

    # AJAX API for Grade-Specific Enrollment Options
    path('api/grade-options/', views.api_get_grade_options, name='api_get_grade_options'),

    path('<int:pk>/', views.student_detail, name='student_detail'),
    path('<int:pk>/edit/', views.student_edit, name='student_edit'),
    path('<int:pk>/id-card/', views.student_id_card, name='student_id_card'),
    path('<int:pk>/quick-status/', views.api_quick_set_student_status, name='student_quick_status'),
    path('<int:pk>/exam-status/', views.api_set_student_exam_status, name='student_set_exam_status'),
    path('batch/exam-status/', views.api_batch_set_student_exam_status, name='student_batch_set_exam_status'),
]

