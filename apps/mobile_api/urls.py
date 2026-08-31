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

    # 3. QR Attendance Scanning, Assembly & History
    path('attendance/qr-scan/', views.QRAttendanceScanView.as_view(), name='mobile_api_qr_scan'),
    path('attendance/assembly/', views.AssemblyAttendanceAPIView.as_view(), name='mobile_api_assembly_attendance'),
    path('attendance/history/', views.AttendanceHistoryView.as_view(), name='mobile_api_attendance_history'),

    # 4. Timetable & Schedule
    path('timetable/', views.TimetableView.as_view(), name='mobile_api_timetable'),

    # 5. Examination Grades & Mobile Grade Entry
    path('grades/', views.ExamGradesView.as_view(), name='mobile_api_grades'),
    path('grades/teacher-entry/meta/', views.TeacherGradeEntryMetaAPIView.as_view(), name='mobile_api_teacher_entry_meta'),
    path('grades/teacher-entry/sheet/', views.TeacherGradeEntrySheetAPIView.as_view(), name='mobile_api_teacher_entry_sheet'),
    path('grades/teacher-entry/save/', views.TeacherGradeEntrySaveAPIView.as_view(), name='mobile_api_teacher_entry_save'),
    path('grades/blind-scoring/validate-code/', views.MobileBlindScoringValidateAPIView.as_view(), name='mobile_api_blind_scoring_validate'),
    path('grades/blind-scoring/save-scores/', views.MobileBlindScoringSaveAPIView.as_view(), name='mobile_api_blind_scoring_save'),

    # 6. In-App Notifications
    path('notifications/', views.MobileNotificationListView.as_view(), name='mobile_api_notifications'),
]
