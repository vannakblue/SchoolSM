import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:dio/dio.dart';
import 'package:schoolsm_mobile/core/api/api_client.dart';
import 'package:schoolsm_mobile/core/services/auth_service.dart';
import 'package:schoolsm_mobile/features/dashboard/screens/main_navigation_screen.dart';

class MockTeacherAuthService extends ChangeNotifier implements AuthService {
  @override
  bool get isLoading => false;

  @override
  bool get isAuthenticated => true;

  @override
  Map<String, dynamic>? get user => {
        'username': 'teacher1',
        'role': 'TEACHER',
        'role_display': 'គ្រូបង្រៀន (Teacher)',
        'display_name': 'លោកគ្រូ តេស្ត',
      };

  @override
  Map<String, dynamic>? get roleProfile => null;

  @override
  Map<String, dynamic>? get schoolInfo => null;

  @override
  String get role => 'TEACHER';

  @override
  String get displayName => 'លោកគ្រូ តេស្ត';

  @override
  String get username => 'teacher1';

  @override
  String? get avatarUrl => null;

  @override
  bool get isTeacher => true;

  @override
  bool get isStudent => false;

  @override
  bool get isAdmin => false;

  @override
  bool get isAccountant => false;

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class FastMockInterceptor extends Interceptor {
  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    return handler.resolve(Response(
      requestOptions: options,
      data: {'status': 'success'},
      statusCode: 200,
    ));
  }
}

void main() {
  testWidgets('Test MainNavigationScreen for Teacher', (WidgetTester tester) async {
    ApiClient().dio.interceptors.clear();
    ApiClient().dio.interceptors.add(FastMockInterceptor());

    final mockAuth = MockTeacherAuthService();

    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider<AuthService>.value(value: mockAuth),
        ],
        child: const MaterialApp(
          home: MainNavigationScreen(),
        ),
      ),
    );

    // Initial pump & settle
    await tester.pumpAndSettle();

    // Verify MainNavigationScreen renders without crashing
    expect(find.byType(MainNavigationScreen), findsOneWidget);
    expect(find.byType(BottomNavigationBar), findsOneWidget);

    // Check if error widget was rendered
    expect(find.byType(ErrorWidget), findsNothing);
  });
}
