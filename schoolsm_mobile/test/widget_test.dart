import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:schoolsm_mobile/core/services/auth_service.dart';
import 'package:schoolsm_mobile/main.dart';

void main() {
  testWidgets('SchoolSM App smoke test', (WidgetTester tester) async {
    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider(create: (_) => AuthService()),
        ],
        child: const SchoolSMApp(),
      ),
    );
    expect(find.byType(SchoolSMApp), findsOneWidget);
  });
}
