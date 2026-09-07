import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:dio/dio.dart';
import 'package:schoolsm_mobile/core/api/api_client.dart';
import 'package:schoolsm_mobile/core/services/auth_service.dart';
import 'package:schoolsm_mobile/features/dashboard/screens/main_navigation_screen.dart';

class TestTeacherAuthService extends ChangeNotifier implements AuthService {
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

class TestStudentAuthService extends ChangeNotifier implements AuthService {
  @override
  bool get isLoading => false;
  @override
  bool get isAuthenticated => true;
  @override
  Map<String, dynamic>? get user => {
        'username': 'student1',
        'role': 'STUDENT',
        'role_display': 'សិស្ស (Student)',
        'display_name': 'សុខ សាន',
      };
  @override
  Map<String, dynamic>? get roleProfile => null;
  @override
  Map<String, dynamic>? get schoolInfo => null;
  @override
  String get role => 'STUDENT';
  @override
  String get displayName => 'សុខ សាន';
  @override
  String get username => 'student1';
  @override
  String? get avatarUrl => null;
  @override
  bool get isTeacher => false;
  @override
  bool get isStudent => true;
  @override
  bool get isAdmin => false;
  @override
  bool get isAccountant => false;
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class SuccessMockInterceptor extends Interceptor {
  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    if (options.path.contains('/dashboard/')) {
      return handler.resolve(Response(
        requestOptions: options,
        data: {
          'status': 'success',
          'dashboard': {
            'role': 'TEACHER',
            'user_display_name': 'លោកគ្រូ តេស្ត',
            'today': '07-09-2026',
            'stats': {
              'check_in_status': 'NOT_YET',
              'check_in_time': null,
              'total_classes': 2,
              'today_classes': 1,
            }
          }
        },
        statusCode: 200,
      ));
    }
    if (options.path.contains('/grades/teacher-entry/meta/')) {
      return handler.resolve(Response(
        requestOptions: options,
        data: {
          'status': 'success',
          'exam_terms': [{'id': 1, 'name': 'ឆមាសទី១'}],
          'classrooms': [{'id': 10, 'name': 'ថ្នាក់ទី 10A'}],
          'subjects': [{'id': 100, 'name': 'គណិតវិទ្យា', 'code': 'MATH'}],
        },
        statusCode: 200,
      ));
    }
    if (options.path.contains('/grades/teacher-entry/sheet/')) {
      return handler.resolve(Response(
        requestOptions: options,
        data: {
          'status': 'success',
          'students': [
            {'id': 1, 'student_id': 'STU001', 'name': 'សុខ សាន', 'gender': 'M', 'score': 85.0}
          ],
        },
        statusCode: 200,
      ));
    }
    if (options.path.contains('/timetable/')) {
      return handler.resolve(Response(
        requestOptions: options,
        data: {
          'status': 'success',
          'timetable': [],
        },
        statusCode: 200,
      ));
    }
    if (options.path.contains('/attendance/history/')) {
      return handler.resolve(Response(
        requestOptions: options,
        data: {
          'status': 'success',
          'records': [],
        },
        statusCode: 200,
      ));
    }

    return handler.resolve(Response(
      requestOptions: options,
      data: {'status': 'success'},
      statusCode: 200,
    ));
  }
}

class FailureMockInterceptor extends Interceptor {
  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    handler.reject(DioException(
      requestOptions: options,
      error: 'Connection timed out',
      type: DioExceptionType.connectionTimeout,
    ));
  }
}

void main() {
  testWidgets('Test MainNavigationScreen Teacher with successful API and tab switching', (WidgetTester tester) async {
    ApiClient().dio.interceptors.clear();
    ApiClient().dio.interceptors.add(SuccessMockInterceptor());

    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 2.75;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final mockAuth = TestTeacherAuthService();

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

    await tester.pumpAndSettle();

    // Verify Tab 0 (Home)
    expect(find.byType(MainNavigationScreen), findsOneWidget);
    expect(find.text("SchoolSM"), findsOneWidget);
    expect(find.byType(ErrorWidget), findsNothing);

    // Switch to Tab 1 (Grade Entry)
    await tester.tap(find.text("បញ្ចូលពិន្ទុ"));
    await tester.pumpAndSettle();
    expect(find.byType(ErrorWidget), findsNothing);

    // Switch to Tab 2 (Timetable)
    await tester.tap(find.text("កាលវិភាគ"));
    await tester.pumpAndSettle();
    expect(find.byType(ErrorWidget), findsNothing);

    // Switch to Tab 3 (Attendance)
    await tester.tap(find.text("វត្តមាន"));
    await tester.pumpAndSettle();
    expect(find.byType(ErrorWidget), findsNothing);

    // Switch to Tab 4 (Account)
    await tester.tap(find.text("គណនី"));
    await tester.pumpAndSettle();
    expect(find.byType(ErrorWidget), findsNothing);
  });

  testWidgets('Test MainNavigationScreen with Network Failure fallback (Cold Start)', (WidgetTester tester) async {
    ApiClient().dio.interceptors.clear();
    ApiClient().dio.interceptors.add(FailureMockInterceptor());

    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 2.75;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final mockAuth = TestTeacherAuthService();

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

    await tester.pumpAndSettle();

    // Verify Home renders cleanly with fallback banner and NO crash
    expect(find.byType(MainNavigationScreen), findsOneWidget);
    expect(find.text("SchoolSM"), findsOneWidget);
    expect(find.byType(ErrorWidget), findsNothing);
  });

  testWidgets('Test MainNavigationScreen Student mode', (WidgetTester tester) async {
    ApiClient().dio.interceptors.clear();
    ApiClient().dio.interceptors.add(SuccessMockInterceptor());

    final mockAuth = TestStudentAuthService();

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

    await tester.pumpAndSettle();

    expect(find.byType(MainNavigationScreen), findsOneWidget);
    expect(find.text("SchoolSM"), findsOneWidget);
    expect(find.byType(ErrorWidget), findsNothing);
  });
}
