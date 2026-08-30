from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    # 1. Authentication & Tokens
    path('auth/login/', views.MobileLoginView.as_view(), name='mobile_api_login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='mobile_api_token_refresh'),
    path('auth/change-password/', views.MobileChangePasswordView.as_view(), name='mobile_api_change_password'),
    path('auth/register-fcm-token/', views.RegisterFCMTokenView.as_view(), name='mobile_api_register_fcm_token'),

    # 2. User Profile & Dashboard Summary
    path('profile/', views.UserProfileView.as_view(), name='mobile_api_profile'),
    path('dashboard/', views.MobileDashboardSummaryView.as_view(), name='mobile_api_dashboard'),

    # 3. QR Attendance Scanning & History
    path('attendance/qr-scan/', views.QRAttendanceScanView.as_view(), name='mobile_api_qr_scan'),
    path('attendance/history/', views.AttendanceHistoryView.as_view(), name='mobile_api_attendance_history'),

    # 4. Timetable & Schedule
    path('timetable/', views.TimetableView.as_view(), name='mobile_api_timetable'),

    # 5. Examination Grades
    path('grades/', views.ExamGradesView.as_view(), name='mobile_api_grades'),

    # 6. In-App Notifications
    path('notifications/', views.MobileNotificationListView.as_view(), name='mobile_api_notifications'),
]
