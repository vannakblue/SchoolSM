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
}
