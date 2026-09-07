import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

class ApiConstants {
  // Dynamic Default Backend Base URL
  static String get defaultBaseUrl {
    if (kIsWeb) {
      return "http://127.0.0.1:8000";
    }
    return "https://schoolsm.onrender.com";
  }

  static String baseUrl = defaultBaseUrl;
  static const String prefBaseUrlKey = "custom_base_url";

  static Future<void> loadBaseUrl() async {
    final prefs = await SharedPreferences.getInstance();
    final saved = prefs.getString(prefBaseUrlKey);
    if (saved != null && saved.isNotEmpty) {
      baseUrl = saved;
    } else {
      baseUrl = defaultBaseUrl;
    }
  }

  static Future<void> saveBaseUrl(String newUrl) async {
    final prefs = await SharedPreferences.getInstance();
    baseUrl = newUrl.replaceAll(RegExp(r'/+$'), '');
    await prefs.setString(prefBaseUrlKey, baseUrl);
  }

  // Endpoints
  static String get login => "$baseUrl/api/v1/auth/login/";
  static String get refreshToken => "$baseUrl/api/v1/auth/refresh/";
  static String get changePassword => "$baseUrl/api/v1/auth/change-password/";
  static String get registerFcmToken => "$baseUrl/api/v1/auth/register-fcm-token/";
  static String get profile => "$baseUrl/api/v1/profile/";
  static String get dashboard => "$baseUrl/api/v1/dashboard/";
  static String get qrScan => "$baseUrl/api/v1/attendance/qr-scan/";
  static String get attendanceHistory => "$baseUrl/api/v1/attendance/history/";
  static String get timetable => "$baseUrl/api/v1/timetable/";
  static String get grades => "$baseUrl/api/v1/grades/";
  static String get notifications => "$baseUrl/api/v1/notifications/";

  // Student Admission & Directory
  static String get studentEnroll => "$baseUrl/api/v1/students/enroll/";
  static String get studentCheckId => "$baseUrl/api/v1/students/check-id/";
  static String get studentRomanize => "$baseUrl/api/v1/students/romanize/";
  static String get studentsList => "$baseUrl/api/v1/students/";

  // Student Promotion & Retention Matrix
  static String get studentPromotionMeta => "$baseUrl/api/v1/students/promotion/meta/";
  static String get studentPromotionStudents => "$baseUrl/api/v1/students/promotion/students/";
  static String get studentPromotionSubmit => "$baseUrl/api/v1/students/promotion/submit/";

  // Examination Seating & Teacher Grade Entry
  static String get examSeating => "$baseUrl/api/v1/exams/seating/";
  static String get teacherGradeMeta => "$baseUrl/api/v1/grades/teacher-entry/meta/";
  static String get teacherGradeSheet => "$baseUrl/api/v1/grades/teacher-entry/sheet/";
  static String get teacherGradeSave => "$baseUrl/api/v1/grades/teacher-entry/save/";
  static String get blindScoringValidate => "$baseUrl/api/v1/grades/blind-scoring/validate-code/";
  static String get blindScoringSave => "$baseUrl/api/v1/grades/blind-scoring/save-scores/";

  // Exam Invigilation & Proctor Shifts
  static String get invigilatorStatus => "$baseUrl/api/v1/exam-invigilator/status/";
  static String get invigilatorSlots => "$baseUrl/api/v1/exam-invigilator/slots/";
  static String get invigilatorToggle => "$baseUrl/api/v1/exam-invigilator/toggle/";
  static String get invigilatorFinalize => "$baseUrl/api/v1/exam-invigilator/finalize/";
}
