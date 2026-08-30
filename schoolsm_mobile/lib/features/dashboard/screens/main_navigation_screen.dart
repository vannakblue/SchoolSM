import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:flutter_spinkit/flutter_spinkit.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/api_constants.dart';
import '../../../core/api/api_client.dart';
import '../../../core/services/auth_service.dart';
import '../../attendance/screens/qr_scanner_screen.dart';
import '../../attendance/screens/attendance_history_screen.dart';
import '../../academics/screens/timetable_screen.dart';
import '../../examinations/screens/exam_grades_screen.dart';
import '../../notifications/screens/notifications_screen.dart';
import '../../profile/screens/profile_screen.dart';

class MainNavigationScreen extends StatefulWidget {
  const MainNavigationScreen({super.key});

  @override
  State<MainNavigationScreen> createState() => _MainNavigationScreenState();
}

class _MainNavigationScreenState extends State<MainNavigationScreen> {
  int _currentIndex = 0;

  @override
  Widget build(BuildContext context) {
    final auth = Provider.of<AuthService>(context);

    // List of screens based on Role
    List<Widget> screens = [];
    List<BottomNavigationBarItem> navItems = [];

    if (auth.isTeacher) {
      screens = [
        const _HomeScreen(),
        const TimetableScreen(),
        const AttendanceHistoryScreen(),
        const ProfileScreen(),
      ];
      navItems = const [
        BottomNavigationBarItem(icon: Icon(Icons.dashboard_rounded), label: "ទំព័រដើម"),
        BottomNavigationBarItem(icon: Icon(Icons.calendar_month_rounded), label: "កាលវិភាគ"),
        BottomNavigationBarItem(icon: Icon(Icons.fact_check_rounded), label: "វត្តមាន"),
        BottomNavigationBarItem(icon: Icon(Icons.person_rounded), label: "គណនី"),
      ];
    } else if (auth.isStudent) {
      screens = [
        const _HomeScreen(),
        const ExamGradesScreen(),
        const TimetableScreen(),
        const AttendanceHistoryScreen(),
        const ProfileScreen(),
      ];
      navItems = const [
        BottomNavigationBarItem(icon: Icon(Icons.dashboard_rounded), label: "ទំព័រដើម"),
        BottomNavigationBarItem(icon: Icon(Icons.military_tech_rounded), label: "ពិន្ទុ"),
        BottomNavigationBarItem(icon: Icon(Icons.calendar_month_rounded), label: "កាលវិភាគ"),
        BottomNavigationBarItem(icon: Icon(Icons.fact_check_rounded), label: "វត្តមាន"),
        BottomNavigationBarItem(icon: Icon(Icons.person_rounded), label: "គណនី"),
      ];
    } else {
      // Admin
      screens = [
        const _HomeScreen(),
        const AttendanceHistoryScreen(),
        const TimetableScreen(),
        const ProfileScreen(),
      ];
      navItems = const [
        BottomNavigationBarItem(icon: Icon(Icons.dashboard_rounded), label: "ទំព័រដើម"),
        BottomNavigationBarItem(icon: Icon(Icons.fact_check_rounded), label: "វត្តមាន"),
        BottomNavigationBarItem(icon: Icon(Icons.calendar_month_rounded), label: "កាលវិភាគ"),
        BottomNavigationBarItem(icon: Icon(Icons.person_rounded), label: "គណនី"),
      ];
    }

    return Scaffold(
      body: IndexedStack(
        index: _currentIndex,
        children: screens,
      ),
      floatingActionButton: (auth.isTeacher || auth.isAdmin)
          ? FloatingActionButton(
              backgroundColor: AppColors.primary,
              foregroundColor: Colors.white,
              elevation: 4,
              child: const Icon(Icons.qr_code_scanner_rounded, size: 28),
              onPressed: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => const QRScannerScreen()),
                );
              },
            )
          : null,
      bottomNavigationBar: Container(
        decoration: BoxDecoration(
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.06),
              blurRadius: 16,
              offset: const Offset(0, -4),
            ),
          ],
        ),
        child: BottomNavigationBar(
          currentIndex: _currentIndex,
          type: BottomNavigationBarType.fixed,
          selectedItemColor: AppColors.primary,
          unselectedItemColor: AppColors.textSecondary,
          backgroundColor: Colors.white,
          elevation: 0,
          selectedLabelStyle: const TextStyle(fontWeight: FontWeight.bold, fontSize: 12),
          unselectedLabelStyle: const TextStyle(fontSize: 11),
          items: navItems,
          onTap: (index) => setState(() => _currentIndex = index),
        ),
      ),
    );
  }
}

// -------------------------------------------------------------
// Integrated Modern Home / Dashboard Screen
// -------------------------------------------------------------
class _HomeScreen extends StatefulWidget {
  const _HomeScreen();

  @override
  State<_HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<_HomeScreen> {
  bool _isLoading = true;
  Map<String, dynamic>? _dashboardData;

  @override
  void initState() {
    super.initState();
    _fetchDashboard();
  }

  Future<void> _fetchDashboard() async {
    setState(() => _isLoading = true);
    try {
      final res = await ApiClient().dio.get(ApiConstants.dashboard);
      setState(() {
        _dashboardData = res.data['dashboard'];
        _isLoading = false;
      });
    } catch (e) {
      setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = Provider.of<AuthService>(context);
    final stats = _dashboardData?['stats'] ?? {};

    return Scaffold(
      backgroundColor: AppColors.bgLight,
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        title: Row(
          children: [
            Container(
              width: 36,
              height: 36,
              decoration: const BoxDecoration(
                shape: BoxShape.circle,
                gradient: AppColors.primaryGradient,
              ),
              child: const Center(
                child: Icon(Icons.school, size: 20, color: Colors.white),
              ),
            ),
            const SizedBox(width: 10),
            const Text(
              "SchoolSM",
              style: TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.bold, fontSize: 18),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.notifications_outlined, color: AppColors.textPrimary),
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const NotificationsScreen()),
              );
            },
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _fetchDashboard,
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Welcome Banner
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  gradient: AppColors.primaryGradient,
                  borderRadius: BorderRadius.circular(24),
                  boxShadow: [
                    BoxShadow(
                      color: AppColors.primary.withOpacity(0.3),
                      blurRadius: 15,
                      offset: const Offset(0, 6),
                    ),
                  ],
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          "សួស្តី, ${auth.displayName}",
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                          decoration: BoxDecoration(
                            color: Colors.white.withOpacity(0.2),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Text(
                            auth.user?['role_display'] ?? auth.role,
                            style: const TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.bold),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Text(
                      "ថ្ងៃនេះ: ${_dashboardData?['today'] ?? ''}",
                      style: TextStyle(color: Colors.white.withOpacity(0.85), fontSize: 13),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 24),

              // Quick Actions Grid
              const Text(
                "មុខងាររហ័ស (Quick Actions)",
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  if (auth.isTeacher || auth.isAdmin)
                    Expanded(
                      child: _buildActionCard(
                        icon: Icons.qr_code_scanner_rounded,
                        label: "ស្កេន QR វត្តមាន",
                        color: AppColors.primary,
                        onTap: () {
                          Navigator.push(
                            context,
                            MaterialPageRoute(builder: (_) => const QRScannerScreen()),
                          );
                        },
                      ),
                    ),
                  if (auth.isTeacher || auth.isAdmin) const SizedBox(width: 12),
                  Expanded(
                    child: _buildActionCard(
                      icon: Icons.calendar_month_rounded,
                      label: "កាលវិភាគ",
                      color: AppColors.secondary,
                      onTap: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(builder: (_) => const TimetableScreen()),
                        );
                      },
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _buildActionCard(
                      icon: auth.isStudent ? Icons.military_tech_rounded : Icons.fact_check_rounded,
                      label: auth.isStudent ? "មើលពិន្ទុ" : "ប្រវត្តិវត្តមាន",
                      color: AppColors.accent,
                      onTap: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) => auth.isStudent ? const ExamGradesScreen() : const AttendanceHistoryScreen(),
                          ),
                        );
                      },
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 24),

              // Overview Stats Cards
              const Text(
                "ស្ថានភាពទូទៅ (Overview)",
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
              ),
              const SizedBox(height: 12),

              _isLoading
                  ? const Center(child: Padding(padding: EdgeInsets.all(20), child: SpinKitFadingCircle(color: AppColors.primary, size: 36)))
                  : _buildStatsWidgets(auth, stats),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildActionCard({
    required IconData icon,
    required String label,
    required Color color,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(16),
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 8),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppColors.borderLight),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.02),
              blurRadius: 8,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Column(
          children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: color.withOpacity(0.12),
                shape: BoxShape.circle,
              ),
              child: Icon(icon, color: color, size: 24),
            ),
            const SizedBox(height: 8),
            Text(
              label,
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStatsWidgets(AuthService auth, Map<String, dynamic> stats) {
    if (auth.isTeacher) {
      return Row(
        children: [
          Expanded(
            child: _buildMetricCard(
              title: "វត្តមានថ្ងៃនេះ",
              value: stats['check_in_time'] != null ? "បាន Check-In\n${stats['check_in_time']}" : "មិនទាន់ស្កេន",
              color: stats['check_in_time'] != null ? AppColors.success : AppColors.warning,
              icon: Icons.access_time_filled,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: _buildMetricCard(
              title: "ម៉ោងបង្រៀនថ្ងៃនេះ",
              value: "${stats['today_classes'] ?? 0} ម៉ោង",
              color: AppColors.primary,
              icon: Icons.menu_book_rounded,
            ),
          ),
        ],
      );
    } else if (auth.isStudent) {
      return Row(
        children: [
          Expanded(
            child: _buildMetricCard(
              title: "ថ្នាក់រៀន",
              value: stats['classroom'] ?? '-',
              color: AppColors.primary,
              icon: Icons.school,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: _buildMetricCard(
              title: "វត្តមានថ្ងៃនេះ",
              value: stats['today_attendance'] ?? 'មិនទាន់កត់ត្រា',
              color: stats['attendance_status_code'] == 'PRESENT' ? AppColors.success : AppColors.info,
              icon: Icons.check_circle,
            ),
          ),
        ],
      );
    } else {
      // Admin
      return Column(
        children: [
          Row(
            children: [
              Expanded(
                child: _buildMetricCard(
                  title: "សិស្សសរុប",
                  value: "${stats['total_students'] ?? 0} នាក់",
                  color: AppColors.primary,
                  icon: Icons.groups,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildMetricCard(
                  title: "គ្រូបង្រៀន",
                  value: "${stats['total_teachers'] ?? 0} នាក់",
                  color: AppColors.secondary,
                  icon: Icons.badge,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          _buildMetricCard(
            title: "គ្រូមានវត្តមានថ្ងៃនេះ",
            value: "${stats['today_teacher_attendance'] ?? 0} នាក់",
            color: AppColors.success,
            icon: Icons.how_to_reg,
          ),
        ],
      );
    }
  }

  Widget _buildMetricCard({
    required String title,
    required String value,
    required Color color,
    required IconData icon,
  }) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: AppColors.borderLight),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: color.withOpacity(0.12),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(icon, color: color, size: 24),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: const TextStyle(fontSize: 12, color: AppColors.textSecondary)),
                const SizedBox(height: 4),
                Text(
                  value,
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: color),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
