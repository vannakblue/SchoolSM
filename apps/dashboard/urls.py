from django.urls import path
from . import views

urlpatterns = [
    path('admin/', views.admin_dashboard, name='admin_dashboard'),
    path('finance/', views.finance_dashboard, name='finance_dashboard'),
    path('teacher/', views.teacher_dashboard, name='teacher_dashboard'),
    path('student/', views.student_dashboard, name='student_dashboard'),
    path('reports/moeys/', views.moeys_statistics_view, name='moeys_reports'),
    path('reports/moeys/export/', views.export_moeys_excel, name='export_moeys_excel'),
    path('export/students/csv/', views.export_students_csv, name='export_students_csv'),
    path('export/students/excel/', views.export_students_excel, name='export_students_excel'),
    path('export/finance/excel/', views.export_finance_excel, name='export_finance_excel'),
]
