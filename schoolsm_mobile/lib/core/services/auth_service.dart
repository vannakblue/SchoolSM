import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../api/api_client.dart';
import '../constants/api_constants.dart';

class AuthService extends ChangeNotifier {
  final FlutterSecureStorage _storage = const FlutterSecureStorage();
  final ApiClient _api = ApiClient();

  bool _isLoading = false;
  bool _isAuthenticated = false;
  Map<String, dynamic>? _user;
  Map<String, dynamic>? _roleProfile;
  Map<String, dynamic>? _schoolInfo;

  bool get isLoading => _isLoading;
  bool get isAuthenticated => _isAuthenticated;
  Map<String, dynamic>? get user => _user;
  Map<String, dynamic>? get roleProfile => _roleProfile;
  Map<String, dynamic>? get schoolInfo => _schoolInfo;

  String get role => _user?['role'] ?? 'STUDENT';
  String get displayName => _user?['display_name'] ?? _user?['username'] ?? 'User';
  String get username => _user?['username'] ?? '';
  String? get avatarUrl => _user?['avatar_url'];

  bool get isTeacher => role == 'TEACHER';
  bool get isStudent => role == 'STUDENT';
  bool get isAdmin => role == 'ADMIN' || role == 'SUPERADMIN' || role == 'PRINCIPAL';

  AuthService() {
    _tryAutoLogin();
  }

  Future<void> _tryAutoLogin() async {
    _isLoading = true;
    notifyListeners();

    try {
      final token = await _storage.read(key: 'access_token');
      final userJson = await _storage.read(key: 'cached_user');
      final roleJson = await _storage.read(key: 'cached_role_profile');
      final schoolJson = await _storage.read(key: 'cached_school_info');

      if (token != null && userJson != null) {
        _user = jsonDecode(userJson);
        if (roleJson != null) _roleProfile = jsonDecode(roleJson);
        if (schoolJson != null) _schoolInfo = jsonDecode(schoolJson);
        _isAuthenticated = true;

        // Fetch fresh profile in background
        fetchFreshProfile();
      }
    } catch (e) {
      debugPrint("Auto-login error: $e");
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<Map<String, dynamic>> login(String username, String password, {String? deviceToken}) async {
    _isLoading = true;
    notifyListeners();

    try {
      final response = await _api.dio.post(
        ApiConstants.login,
        data: {
          'username': username.trim(),
          'password': password.trim(),
          'device_token': deviceToken ?? '',
          'device_type': 'android',
          'app_version': '1.0.0',
        },
      );

      final data = response.data;
      if (data['status'] == 'success') {
        final tokens = data['tokens'];
        await _storage.write(key: 'access_token', value: tokens['access']);
        await _storage.write(key: 'refresh_token', value: tokens['refresh']);

        _user = data['user'];
        _roleProfile = data['role_profile'];
        _schoolInfo = data['school_info'];
        _isAuthenticated = true;

        await _storage.write(key: 'cached_user', value: jsonEncode(_user));
        if (_roleProfile != null) {
          await _storage.write(key: 'cached_role_profile', value: jsonEncode(_roleProfile));
        }
        if (_schoolInfo != null) {
          await _storage.write(key: 'cached_school_info', value: jsonEncode(_schoolInfo));
        }

        _isLoading = false;
        notifyListeners();
        return {'success': true, 'message': data['message']};
      } else {
        _isLoading = false;
        notifyListeners();
        return {'success': false, 'message': data['message'] ?? 'Login failed'};
      }
    } catch (e) {
      _isLoading = false;
      notifyListeners();
      return {'success': false, 'message': ApiClient.getErrorMessage(e)};
    }
  }

  Future<void> fetchFreshProfile() async {
    try {
      final res = await _api.dio.get(ApiConstants.profile);
      if (res.data['status'] == 'success') {
        _user = res.data['user'];
        _roleProfile = res.data['role_profile'];
        await _storage.write(key: 'cached_user', value: jsonEncode(_user));
        if (_roleProfile != null) {
          await _storage.write(key: 'cached_role_profile', value: jsonEncode(_roleProfile));
        }
        notifyListeners();
      }
    } catch (e) {
      debugPrint("Fresh profile fetch error: $e");
    }
  }

  Future<Map<String, dynamic>> changePassword(String currentPassword, String newPassword) async {
    try {
      final res = await _api.dio.post(
        ApiConstants.changePassword,
        data: {
          'current_password': currentPassword,
          'new_password': newPassword,
        },
      );
      return {'success': true, 'message': res.data['message'] ?? 'Password changed successfully'};
    } catch (e) {
      return {'success': false, 'message': ApiClient.getErrorMessage(e)};
    }
  }

  Future<void> logout() async {
    await _storage.deleteAll();
    _isAuthenticated = false;
    _user = null;
    _roleProfile = null;
    notifyListeners();
  }
}
