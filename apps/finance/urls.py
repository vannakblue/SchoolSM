from django.urls import path
from . import views

urlpatterns = [
    # Monthly Utility & Fee Tracker (បញ្ជីទឹកភ្លើងប្រចាំខែ)
    path('monthly-fees/', views.monthly_fees_tracker, name='monthly_fees_tracker'),
    path('monthly-fees/export-excel/', views.export_monthly_fees_excel, name='export_monthly_fees_excel'),
    path('monthly-fees/export-csv/', views.export_monthly_fees_csv, name='export_monthly_fees_csv'),
    path('monthly-fees/save-scope/', views.save_monthly_fee_scope, name='save_monthly_fee_scope'),
    path('monthly-fees/save-range/', views.save_monthly_fee_range, name='save_monthly_fee_range'),
    path('monthly-fees/record-payment/', views.record_student_monthly_payment, name='record_student_monthly_payment'),
    path('monthly-fees/update-fee-start-month/', views.update_student_fee_start_month, name='update_student_fee_start_month'),
    path('monthly-fees/bulk-assign-category/', views.bulk_assign_student_category, name='bulk_assign_student_category'),
    path('monthly-fees/classroom-students/', views.get_classroom_students_ajax, name='get_classroom_students_ajax'),
    path('monthly-fees/configure-rates/', views.configure_monthly_rates_matrix, name='configure_monthly_rates_matrix'),
    path('monthly-fees/manage-collectors/', views.manage_fee_collectors, name='manage_fee_collectors'),
    path('monthly-fees/categories/', views.manage_student_categories, name='manage_student_categories'),
    path('monthly-fees/categories/<int:pk>/delete/', views.delete_student_category, name='delete_student_category'),
    path('monthly-fees/send-reminder/', views.send_monthly_fee_reminder, name='send_monthly_fee_reminder'),
    path('monthly-fees/send-classroom-summary/', views.send_classroom_fee_summary_telegram, name='send_classroom_fee_summary_telegram'),

    # Tri-Channel Mobile Fee Collector Portal & Passes
    path('monthly-fees/collector-portal/', views.mobile_fee_collector_portal, name='mobile_fee_collector_portal'),
    path('monthly-fees/collector-passes/', views.get_teacher_collector_passes, name='get_teacher_collector_passes'),
    path('monthly-fees/api/search-student-qr/', views.api_search_student_qr, name='api_search_student_qr'),

    # Legacy Due Fees URL (Redirects to monthly-fees)
    path('due-fees/', views.due_fees_list, name='due_fees_list'),

    # Standard Invoicing & Receipts
    path('fees/', views.fee_category_list, name='fee_category_list'),
    path('invoices/', views.invoice_list, name='invoice_list'),
    path('invoices/create/', views.invoice_create, name='invoice_create'),
    path('invoices/batch-create/', views.invoice_batch_create, name='invoice_batch_create'),
    path('invoices/<int:pk>/', views.invoice_detail, name='invoice_detail'),
    path('invoices/<int:pk>/pay/', views.record_payment, name='record_payment'),
    path('receipts/<int:pk>/', views.official_receipt, name='official_receipt'),
    
    # Expenses & Payroll
    path('expenses/', views.expense_list, name='expense_list'),
    path('payroll/', views.payroll_list, name='payroll_list'),
    path('payroll/generate/', views.payroll_generate, name='payroll_generate'),
    path('payroll/<int:pk>/mark-paid/', views.payroll_mark_paid, name='payroll_mark_paid'),

    # Payment Audit Logs, Firestore Cloud Sync & Any-Time Backup Suite
    path('payment-logs/', views.payment_logs_dashboard, name='payment_logs_dashboard'),
    path('payment-logs/methods/', views.api_manage_payment_methods, name='api_manage_payment_methods'),
    path('payment-logs/slips/<int:pk>/review/', views.api_review_payment_slip, name='api_review_payment_slip'),
    path('payment-logs/export-excel/', views.export_payment_logs_excel, name='export_payment_logs_excel'),
    path('payment-logs/export-json/', views.export_payment_logs_json, name='export_payment_logs_json'),
    path('payment-logs/sync-firestore/', views.api_sync_firestore, name='api_sync_firestore'),
    path('payment-logs/send-telegram/', views.api_send_payment_backup_telegram, name='api_send_payment_backup_telegram'),
]

