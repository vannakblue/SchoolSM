import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:schoolsm_mobile/core/services/auth_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  FlutterSecureStorage.setMockInitialValues({});

  group('AuthService Demo Logins', () {
    late AuthService auth;

    setUp(() {
      auth = AuthService();
    });

    test('Demo Student login succeeds with demo fallback and proper role', () async {
      final res = await auth.login('student1', 'admin123');
      expect(res['success'], isTrue);
      expect(auth.isStudent, isTrue);
      expect(auth.role, equals('STUDENT'));
      expect(auth.isAuthenticated, isTrue);
      expect(auth.user?['username'], equals('student1'));
      expect(auth.roleProfile?['student_id'], equals('STU-2026-0001'));
    });

    test('Demo Accountant / Finance login succeeds with demo fallback and proper role', () async {
      final res = await auth.login('accountant', 'admin123');
      expect(res['success'], isTrue);
      expect(auth.isAccountant, isTrue);
      expect(auth.role, equals('ACCOUNTANT'));
      expect(auth.isAuthenticated, isTrue);
      expect(auth.user?['username'], equals('accountant'));
    });

    test('Demo Teacher login succeeds with demo fallback and proper role', () async {
      final res = await auth.login('teacher', 'admin123');
      expect(res['success'], isTrue);
      expect(auth.isTeacher, isTrue);
      expect(auth.role, equals('TEACHER'));
      expect(auth.isAuthenticated, isTrue);
      expect(auth.user?['username'], equals('teacher'));
    });

    test('Demo Admin login succeeds with demo fallback and proper role', () async {
      final res = await auth.login('admin', 'admin123');
      expect(res['success'], isTrue);
      expect(auth.isAdmin, isTrue);
      expect(auth.role, equals('ADMIN'));
      expect(auth.isAuthenticated, isTrue);
      expect(auth.user?['username'], equals('admin'));
    });
  });
}
