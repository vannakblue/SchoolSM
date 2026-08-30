import 'package:flutter_test/flutter_test.dart';
import 'package:schoolsm_mobile/main.dart';

void main() {
  testWidgets('SchoolSM App smoke test', (WidgetTester tester) async {
    await tester.pumpWidget(const SchoolSMApp());
    expect(find.byType(SchoolSMApp), findsOneWidget);
  });
}
