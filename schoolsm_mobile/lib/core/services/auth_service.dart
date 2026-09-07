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
  bool _isDemoSession = false;
  Map<String, dynamic>? _user;
  Map<String, dynamic>? _roleProfile;
  Map<String, dynamic>? _schoolInfo;

  bool get isLoading => _isLoading;
  bool get isAuthenticated => _isAuthenticated;
  bool get isDemoSession => _isDemoSession;
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
  bool get isAccountant => role == 'ACCOUNTANT' || role == 'FINANCE';

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
        _isDemoSession = token.startsWith('demo_token_');

        // Fetch fresh profile in background only for real server sessions
        if (!_isDemoSession) {
          fetchFreshProfile();
        }
      }
    } catch (e) {
      debugPrint("Auto-login error: $e");
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  bool _isDemoCredentials(String username, String password) {
    final u = username.trim().toLowerCase();
    final p = password.trim();
    final demoUsers = [
      'student',
      'student1',
      'students',
      'accountant',
      'finance',
      'teacher',
      'teacher1',
      'teachers',
      'admin',
      'superadmin'
    ];
    return demoUsers.contains(u) &&
        (p == 'admin123' || p == 'p123456' || p == 'demo123' || p.isEmpty);
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
        _isDemoSession = false;

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
        if (_isDemoCredentials(username, password)) {
          return await _loginAsDemoFallback(username);
        }
        _isLoading = false;
        notifyListeners();
        return {'success': false, 'message': data['message'] ?? 'Login failed'};
      }
    } catch (e) {
      if (_isDemoCredentials(username, password)) {
        return await _loginAsDemoFallback(username);
      }
      _isLoading = false;
      notifyListeners();
      return {'success': false, 'message': ApiClient.getErrorMessage(e)};
    }
  }

  Future<Map<String, dynamic>> _loginAsDemoFallback(String username) async {
    final u = username.trim().toLowerCase();
    Map<String, dynamic> demoUser;
    Map<String, dynamic>? demoRoleProfile;

    if (u == 'student' || u == 'student1' || u == 'students') {
      demoUser = {
        'id': 9991,
        'username': 'student1',
        'display_name': 'សុខ ចាន់ថន',
        'first_name': 'ចាន់ថន',
        'last_name': 'សុខ',
        'khmer_name': 'សុខ ចាន់ថន',
        'latin_name': 'Sok Chan thorn',
        'role': 'STUDENT',
        'role_display': 'សិស្សានុសិស្ស',
        'email': 'student1@school.edu.kh',
        'phone': '012 345 678',
        'avatar_url': null,
      };
      demoRoleProfile = {
        'student_id': 'STU-2026-0001',
        'khmer_name': 'សុខ ចាន់ថន',
        'latin_name': 'Sok Chan thorn',
        'gender': 'M',
        'gender_display': 'ប្រុស / Male',
        'classroom': 'ថ្នាក់ទី 12A',
        'academic_year': '2025-2026',
        'status': 'កំពុងសិក្សា',
        'phone': '012 345 678',
        'parent_name': 'សុខ គង់',
        'parent_phone': '098 765 432',
      };
    } else if (u == 'accountant' || u == 'finance') {
      demoUser = {
        'id': 9992,
        'username': 'accountant',
        'display_name': 'មន្ត្រីគណនេយ្យ & បេឡា',
        'first_name': 'គណនេយ្យ',
        'last_name': 'មន្ត្រី',
        'khmer_name': 'មន្ត្រី គណនេយ្យ',
        'latin_name': 'Accountant Officer',
        'role': 'ACCOUNTANT',
        'role_display': 'គណនេយ្យករ (Finance)',
        'email': 'accountant@school.edu.kh',
        'phone': '012 999 888',
        'avatar_url': null,
      };
      demoRoleProfile = {
        'position': 'ប្រធានគណនេយ្យ',
        'department': 'ការិយាល័យហិរញ្ញវត្ថុ & ចុះឈ្មោះ',
      };
    } else if (u == 'teacher' || u == 'teacher1' || u == 'teachers') {
      demoUser = {
        'id': 9993,
        'username': 'teacher',
        'display_name': 'លោកគ្រូ សុវណ្ណ លី',
        'first_name': 'សុវណ្ណ',
        'last_name': 'លី',
        'khmer_name': 'លី សុវណ្ណ',
        'latin_name': 'Ly Sovann',
        'role': 'TEACHER',
        'role_display': 'លោកគ្រូ-អ្នកគ្រូ',
        'email': 'teacher@school.edu.kh',
        'phone': '012 777 666',
        'avatar_url': null,
      };
      demoRoleProfile = {
        'teacher_id': 'TEA-001',
        'khmer_name': 'លី សុវណ្ណ',
        'latin_name': 'Ly Sovann',
        'specialization': 'គណិតវិទ្យា & វិទ្យាសាស្ត្រ',
        'phone': '012 777 666',
      };
    } else {
      // admin
      demoUser = {
        'id': 9994,
        'username': 'admin',
        'display_name': 'អ្នកគ្រប់គ្រងទូទៅ (Admin)',
        'first_name': 'Admin',
        'last_name': 'System',
        'khmer_name': 'រដ្ឋបាលសាលា',
        'latin_name': 'School Administrator',
        'role': 'ADMIN',
        'role_display': 'អ្នកគ្រប់គ្រងទូទៅ',
        'email': 'admin@school.edu.kh',
        'phone': '012 000 111',
        'avatar_url': null,
      };
      demoRoleProfile = {
        'title': 'ប្រធានរដ្ឋបាល និងប្រព័ន្ធបច្ចេកវិទ្យា',
      };
    }

    final demoSchool = {
      'name': 'សាលារៀន ស្មាតស្គូល (Smart School)',
      'code': 'SCH-001',
      'logo_url': null,
      'phone': '023 888 999',
      'email': 'info@schoolsm.edu.kh',
      'address': 'រាជធានីភ្នំពេញ',
    };

    final demoToken = 'demo_token_${u}_${DateTime.now().millisecondsSinceEpoch}';
    await _storage.write(key: 'access_token', value: demoToken);
    await _storage.write(key: 'refresh_token', value: 'demo_refresh_token');

    _user = demoUser;
    _roleProfile = demoRoleProfile;
    _schoolInfo = demoSchool;
    _isAuthenticated = true;
    _isDemoSession = true;

    await _storage.write(key: 'cached_user', value: jsonEncode(_user));
    if (_roleProfile != null) {
      await _storage.write(key: 'cached_role_profile', value: jsonEncode(_roleProfile));
    }
    if (_schoolInfo != null) {
      await _storage.write(key: 'cached_school_info', value: jsonEncode(_schoolInfo));
    }

    _isLoading = false;
    notifyListeners();
    return {
      'success': true,
      'message': 'ចូលប្រើប្រព័ន្ធសាកល្បង Demo (${demoUser['role_display']}) ជោគជ័យ!',
      'is_demo': true,
    };
  }

  Future<void> fetchFreshProfile() async {
    if (_isDemoSession) return;
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
    _isDemoSession = false;
    _user = null;
    _roleProfile = null;
    _schoolInfo = null;
    notifyListeners();
  }
}
