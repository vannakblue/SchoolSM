import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:dio/dio.dart';
import 'package:schoolsm_mobile/core/api/api_client.dart';
import 'package:schoolsm_mobile/core/services/auth_service.dart';
import 'package:schoolsm_mobile/features/examinations/screens/student_online_exam_list_screen.dart';
import 'package:schoolsm_mobile/features/examinations/screens/student_take_online_exam_screen.dart';
import 'package:schoolsm_mobile/features/examinations/screens/student_online_exam_result_screen.dart';

class MockAuthService extends ChangeNotifier implements AuthService {
  @override
  bool get isLoading => false;

  @override
  bool get isAuthenticated => true;

  @override
  Map<String, dynamic>? get user => {
        'username': 'student_demo',
        'role': 'STUDENT',
        'role_display': 'សិស្ស (Student)',
        'display_name': 'សុខ ចាន់ថន',
      };

  @override
  Map<String, dynamic>? get roleProfile => null;

  @override
  Map<String, dynamic>? get schoolInfo => null;

  @override
  String get role => 'STUDENT';

  @override
  String get displayName => 'សុខ ចាន់ថន';

  @override
  String get username => 'student_demo';

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

class OnlineExamMockInterceptor extends Interceptor {
  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    final path = options.path;

    // 1. Online exams list
    if (path.contains('/api/v1/online-exams/') && options.method == 'GET' && !path.contains('submissions')) {
      return handler.resolve(Response(
        requestOptions: options,
        data: {
          'status': 'success',
          'student_name': 'សុខ ចាន់ថន',
          'classroom_name': 'ថ្នាក់ទី ៨A',
          'exams': [
            {
              'id': 101,
              'title': 'វិញ្ញាសាតេស្តភាសាខ្មែរប្រចាំខែ',
              'subject_name': 'ភាសាខ្មែរ',
              'exam_term_name': 'សម័យប្រឡងខែវិច្ឆិកា',
              'teacher_name': 'លោកគ្រូ សុវណ្ណ',
              'duration_minutes': 30,
              'total_score': 100.0,
              'pass_score': 50.0,
              'max_attempts': 2,
              'attempts_used': 0,
              'questions_count': 5,
              'requires_access_code': false,
              'status_label': 'កំពុងបើកដំណើរការ',
              'can_take': true,
              'action_label': 'ចូលប្រឡង',
              'latest_submission': null,
            },
            {
              'id': 102,
              'title': 'វិញ្ញាសាតេស្តគណិតវិទ្យា',
              'subject_name': 'គណិតវិទ្យា',
              'exam_term_name': 'សម័យប្រឡងខែវិច្ឆិកា',
              'teacher_name': 'អ្នកគ្រូ ម៉ាលី',
              'duration_minutes': 45,
              'total_score': 100.0,
              'pass_score': 50.0,
              'max_attempts': 1,
              'attempts_used': 1,
              'questions_count': 10,
              'requires_access_code': false,
              'status_label': 'បានបញ្ចប់',
              'can_take': false,
              'action_label': 'បានបញ្ចប់',
              'latest_submission': {
                'id': 202,
                'score_obtained': 85.0,
                'total_possible_score': 100.0,
                'percentage': 85.0,
                'letter_grade': 'B',
                'is_passed': true,
                'formatted_time': '22 នាទី',
              },
            },
          ]
        },
        statusCode: 200,
      ));
    }

    // 2. Take / Start exam
    if (path.contains('/take/') && options.method == 'POST') {
      return handler.resolve(Response(
        requestOptions: options,
        data: {
          'status': 'success',
          'submission_id': 301,
          'exam_id': 101,
          'exam_title': 'វិញ្ញាសាតេស្តភាសាខ្មែរប្រចាំខែ',
          'subject_name': 'ភាសាខ្មែរ',
          'duration_minutes': 30,
          'remaining_seconds': 1800,
          'total_score': 100.0,
          'questions_count': 2,
          'questions': [
            {
              'id': 1,
              'question_text': 'តើពាក្យ «កុសល» មានន័យដូចម្តេច?',
              'image_url': null,
              'points': 50.0,
              'order': 1,
              'options': [
                {'id': 11, 'option_text': 'អំពើល្អ ឬបុណ្យ', 'order': 1},
                {'id': 12, 'option_text': 'អំពើអាក្រក់', 'order': 2},
                {'id': 13, 'option_text': 'សេចក្តីទុក្ខ', 'order': 3},
              ],
              'saved_option_id': null,
            },
            {
              'id': 2,
              'question_text': 'តើព្យញ្ជនៈខ្មែរមានចំនួនប៉ុន្មានតួ?',
              'image_url': null,
              'points': 50.0,
              'order': 2,
              'options': [
                {'id': 21, 'option_text': '៣១ តួ', 'order': 1},
                {'id': 22, 'option_text': '៣៣ តួ', 'order': 2},
                {'id': 23, 'option_text': '៣៥ តួ', 'order': 3},
              ],
              'saved_option_id': null,
            }
          ]
        },
        statusCode: 200,
      ));
    }

    // 3. Submit exam
    if (path.contains('/submit/') && options.method == 'POST') {
      return handler.resolve(Response(
        requestOptions: options,
        data: {
          'status': 'success',
          'submission_id': 301,
          'score_obtained': 100.0,
          'total_possible_score': 100.0,
          'percentage': 100.0,
          'letter_grade': 'A',
          'mention_khmer': 'ល្អប្រសើរ (Grade A)',
          'is_passed': true,
          'time_spent_seconds': 120,
          'formatted_time_spent': '2 នាទី',
          'show_result_immediately': true,
          'show_correct_answers': true,
        },
        statusCode: 200,
      ));
    }

    // 4. Result details
    if (path.contains('/result/') && options.method == 'GET') {
      return handler.resolve(Response(
        requestOptions: options,
        data: {
          'status': 'success',
          'submission': {
            'id': 202,
            'exam_id': 102,
            'exam_title': 'វិញ្ញាសាតេស្តគណិតវិទ្យា',
            'subject_name': 'គណិតវិទ្យា',
            'exam_term_name': 'សម័យប្រឡងខែវិច្ឆិកា',
            'student_name': 'សុខ ចាន់ថន',
            'classroom_name': 'ថ្នាក់ទី ៨A',
            'score_obtained': 85.0,
            'total_possible_score': 100.0,
            'percentage': 85.0,
            'letter_grade': 'B',
            'mention_khmer': 'ល្អណាស់ (Grade B)',
            'is_passed': true,
            'status': 'SUBMITTED',
            'submitted_at': '2026-11-10T10:30:00Z',
            'formatted_time_spent': '22 នាទី',
            'time_spent_seconds': 1320,
            'pass_score': 50.0,
            'show_correct_answers': true,
            'questions_review': [
              {
                'question_id': 1,
                'question_text': 'គណនាផលបូក 25 + 75 = ?',
                'image_url': null,
                'points': 50.0,
                'points_awarded': 50.0,
                'is_correct': true,
                'has_answered': true,
                'explanation': '25 + 75 = 100 ត្រឹមត្រូវ។',
                'options': [
                  {'id': 1, 'option_text': '90', 'is_correct': false, 'is_selected': false},
                  {'id': 2, 'option_text': '100', 'is_correct': true, 'is_selected': true},
                  {'id': 3, 'option_text': '110', 'is_correct': false, 'is_selected': false},
                ]
              }
            ]
          }
        },
        statusCode: 200,
      ));
    }

    return handler.next(options);
  }
}

void main() {
  setUp(() {
    ApiClient().dio.interceptors.clear();
    ApiClient().dio.interceptors.add(OnlineExamMockInterceptor());
  });

  testWidgets('Test StudentOnlineExamListScreen Renders & Filters', (WidgetTester tester) async {
    final mockAuth = MockAuthService();

    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider<AuthService>.value(value: mockAuth),
        ],
        child: const MaterialApp(
          home: StudentOnlineExamListScreen(),
        ),
      ),
    );

    // Settle async fetch
    await tester.pumpAndSettle();

    // Verify app bar title
    expect(find.text("វិញ្ញាសា & ប្រឡងអនឡាញ"), findsOneWidget);

    // Verify student name and classroom in header
    expect(find.text("សុខ ចាន់ថន"), findsOneWidget);
    expect(find.text("ថ្នាក់រៀន៖ ថ្នាក់ទី ៨A"), findsOneWidget);

    // Verify exams rendered
    expect(find.text("វិញ្ញាសាតេស្តភាសាខ្មែរប្រចាំខែ"), findsOneWidget);
    expect(find.text("វិញ្ញាសាតេស្តគណិតវិទ្យា"), findsOneWidget);

    // Verify action buttons
    expect(find.text("ចូលប្រឡង"), findsOneWidget);
    expect(find.text("មើលលទ្ធផល"), findsOneWidget);

    // Test tab filtering
    await tester.tap(find.text("កំពុងបើក (1)"));
    await tester.pumpAndSettle();
    expect(find.text("វិញ្ញាសាតេស្តភាសាខ្មែរប្រចាំខែ"), findsOneWidget);
    expect(find.text("វិញ្ញាសាតេស្តគណិតវិទ្យា"), findsNothing);

    await tester.tap(find.text("បានប្រឡង (1)"));
    await tester.pumpAndSettle();
    expect(find.text("វិញ្ញាសាតេស្តគណិតវិទ្យា"), findsOneWidget);
    expect(find.text("វិញ្ញាសាតេស្តភាសាខ្មែរប្រចាំខែ"), findsNothing);
  });

  testWidgets('Test StudentTakeOnlineExamScreen Focus Mode & Question Flow', (WidgetTester tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: StudentTakeOnlineExamScreen(examId: 101),
      ),
    );

    await tester.pumpAndSettle();

    // Verify title and subject
    expect(find.text("វិញ្ញាសាតេស្តភាសាខ្មែរប្រចាំខែ"), findsOneWidget);
    expect(find.text("ភាសាខ្មែរ"), findsOneWidget);

    // Verify question palette chips
    expect(find.text("1"), findsWidgets);
    expect(find.text("2"), findsWidgets);

    // Verify Question 1 text & options
    expect(find.text("តើពាក្យ «កុសល» មានន័យដូចម្តេច?"), findsOneWidget);
    expect(find.text("អំពើល្អ ឬបុណ្យ"), findsOneWidget);
    expect(find.text("អំពើអាក្រក់"), findsOneWidget);

    // Tap Option A
    await tester.tap(find.text("អំពើល្អ ឬបុណ្យ"));
    await tester.pumpAndSettle();

    // Verify check icon appeared
    expect(find.byIcon(Icons.check_circle_rounded), findsOneWidget);

    // Navigate to next question
    await tester.tap(find.text("សំណួរបន្ទាប់"));
    await tester.pumpAndSettle();

    // Verify Question 2 text
    expect(find.text("តើព្យញ្ជនៈខ្មែរមានចំនួនប៉ុន្មានតួ?"), findsOneWidget);
    expect(find.text("៣៣ តួ"), findsOneWidget);

    // On last question, button turns to Submit
    expect(find.text("ប្រគល់កិច្ចការ"), findsOneWidget);
  });

  testWidgets('Test StudentOnlineExamResultScreen Score & Review', (WidgetTester tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: StudentOnlineExamResultScreen(submissionId: 202),
      ),
    );

    await tester.pumpAndSettle();

    // Verify app bar
    expect(find.text("លទ្ធផលប្រឡងអនឡាញ"), findsOneWidget);

    // Verify pass banner & grade
    expect(find.text("🎉 អបអរសាទរ! ប្រឡងជាប់"), findsOneWidget);
    expect(find.text("និទ្ទេស B"), findsOneWidget);
    expect(find.text("85 / 100"), findsOneWidget);

    // Verify Question review
    expect(find.text("ត្រួតពិនិត្យចម្លើយលម្អិត"), findsOneWidget);
    expect(find.text("គណនាផលបូក 25 + 75 = ?"), findsOneWidget);
    expect(find.text("25 + 75 = 100 ត្រឹមត្រូវ។"), findsOneWidget);

    // Verify return button
    expect(find.text("ត្រឡប់ទៅបញ្ជីវិញ្ញាសា"), findsOneWidget);
  });
}
