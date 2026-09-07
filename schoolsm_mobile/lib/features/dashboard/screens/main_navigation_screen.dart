import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:flutter_spinkit/flutter_spinkit.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/api_constants.dart';
import '../../../core/api/api_client.dart';
import '../../../core/services/auth_service.dart';

// Screens
import '../../attendance/screens/qr_scanner_screen.dart';
import '../../attendance/screens/attendance_history_screen.dart';
import '../../academics/screens/timetable_screen.dart';
import '../../examinations/screens/exam_grades_screen.dart';
import '../../examinations/screens/teacher_grade_entry_screen.dart';
import '../../examinations/screens/exam_invigilator_screen.dart';
import '../../students/screens/student_enrollment_screen.dart';
import '../../students/screens/student_list_screen.dart';
import '../../students/screens/student_portal_screen.dart';
import '../../students/screens/student_promotion_screen.dart';
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

    // List of screens & navigation items based on Role
    List<Widget> screens = [];
    List<BottomNavigationBarItem> navItems = [];

    if (auth.isTeacher) {
      screens = [
        const _HomeScreen(),
        const TeacherGradeEntryScreen(),
        const TimetableScreen(),
        const AttendanceHistoryScreen(),
        const ProfileScreen(),
      ];
      navItems = const [
        BottomNavigationBarItem(icon: Icon(Icons.dashboard_rounded), label: "ទំព័រដើម"),
        BottomNavigationBarItem(icon: Icon(Icons.edit_note_rounded), label: "បញ្ចូលពិន្ទុ"),
        BottomNavigationBarItem(icon: Icon(Icons.calendar_month_rounded), label: "កាលវិភាគ"),
        BottomNavigationBarItem(icon: Icon(Icons.fact_check_rounded), label: "វត្តមាន"),
        BottomNavigationBarItem(icon: Icon(Icons.person_rounded), label: "គណនី"),
      ];
    } else if (auth.isStudent) {
      screens = [
        const _HomeScreen(),
        const ExamGradesScreen(),
        const StudentPortalScreen(),
        const TimetableScreen(),
        const ProfileScreen(),
      ];
      navItems = const [
        BottomNavigationBarItem(icon: Icon(Icons.dashboard_rounded), label: "ទំព័រដើម"),
        BottomNavigationBarItem(icon: Icon(Icons.military_tech_rounded), label: "ពិន្ទុ"),
        BottomNavigationBarItem(icon: Icon(Icons.badge_rounded), label: "កាត & ប្រឡង"),
        BottomNavigationBarItem(icon: Icon(Icons.calendar_month_rounded), label: "កាលវិភាគ"),
        BottomNavigationBarItem(icon: Icon(Icons.person_rounded), label: "គណនី"),
      ];
    } else if (auth.isAccountant) {
      screens = [
        const _HomeScreen(),
        const StudentListScreen(),
        const StudentEnrollmentScreen(),
        const ProfileScreen(),
      ];
      navItems = const [
        BottomNavigationBarItem(icon: Icon(Icons.dashboard_rounded), label: "ទំព័រដើម"),
        BottomNavigationBarItem(icon: Icon(Icons.people_alt_rounded), label: "បញ្ជីសិស្ស"),
        BottomNavigationBarItem(icon: Icon(Icons.person_add_alt_1_rounded), label: "ចុះឈ្មោះ"),
        BottomNavigationBarItem(icon: Icon(Icons.person_rounded), label: "គណនី"),
      ];
    } else {
      // Super Admin
      screens = [
        const _HomeScreen(),
        const StudentListScreen(),
        const TimetableScreen(),
        const AttendanceHistoryScreen(),
        const ProfileScreen(),
      ];
      navItems = const [
        BottomNavigationBarItem(icon: Icon(Icons.dashboard_rounded), label: "ទំព័រដើម"),
        BottomNavigationBarItem(icon: Icon(Icons.people_alt_rounded), label: "បញ្ជីសិស្ស"),
        BottomNavigationBarItem(icon: Icon(Icons.calendar_month_rounded), label: "កាលវិភាគ"),
        BottomNavigationBarItem(icon: Icon(Icons.fact_check_rounded), label: "វត្តមាន"),
        BottomNavigationBarItem(icon: Icon(Icons.person_rounded), label: "គណនី"),
      ];
    }

    if (_currentIndex >= screens.length) {
      _currentIndex = 0;
    }

    return Scaffold(
      body: IndexedStack(
        index: _currentIndex,
        children: screens,
      ),
      floatingActionButton: (auth.isTeacher || auth.isAdmin || auth.isAccountant)
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
              color: Colors.black.withValues(alpha: 0.06),
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
          selectedLabelStyle: const TextStyle(fontWeight: FontWeight.bold, fontSize: 11.5),
          unselectedLabelStyle: const TextStyle(fontSize: 10.5),
          items: navItems,
          onTap: (index) => setState(() => _currentIndex = index),
        ),
      ),
    );
  }
}

// -------------------------------------------------------------
// Integrated Modern Home / Dashboard Screen with Feature Hub
// -------------------------------------------------------------
class _HomeScreen extends StatefulWidget {
  const _HomeScreen();

  @override
  State<_HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<_HomeScreen> {
  bool _isLoading = true;
  String? _errorMessage;
  Map<String, dynamic>? _dashboardData;

  @override
  void initState() {
    super.initState();
    _fetchDashboard();
  }

  Future<void> _fetchDashboard() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });
    try {
      final res = await ApiClient().dio.get(ApiConstants.dashboard);
      if (res.data != null && res.data['dashboard'] != null) {
        setState(() {
          _dashboardData = Map<String, dynamic>.from(res.data['dashboard']);
          _isLoading = false;
        });
      } else {
        setState(() => _isLoading = false);
      }
    } catch (e) {
      setState(() {
        _errorMessage = ApiClient.getErrorMessage(e);
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = Provider.of<AuthService>(context);
    final Map<String, dynamic> stats = _dashboardData?['stats'] != null
        ? Map<String, dynamic>.from(_dashboardData!['stats'])
        : <String, dynamic>{};

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
            const Expanded(
              child: Text(
                "SchoolSM",
                style: TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.bold, fontSize: 18),
                overflow: TextOverflow.ellipsis,
              ),
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
                  borderRadius: BorderRadius.circular(22),
                  boxShadow: [
                    BoxShadow(
                      color: AppColors.primary.withValues(alpha: 0.3),
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
                        Expanded(
                          child: Text(
                            "សួស្តី, ${auth.displayName}",
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 18,
                              fontWeight: FontWeight.bold,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                          decoration: BoxDecoration(
                            color: Colors.white.withValues(alpha: 0.2),
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
                      style: TextStyle(color: Colors.white.withValues(alpha: 0.85), fontSize: 13),
                    ),
                  ],
                ),
              ),
              if (_errorMessage != null) ...[
                const SizedBox(height: 12),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                  decoration: BoxDecoration(
                    color: Colors.amber.shade50,
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: Colors.amber.shade300),
                  ),
                  child: Row(
                    children: [
                      Icon(Icons.wifi_off_rounded, color: Colors.amber.shade800, size: 20),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          _errorMessage!,
                          style: TextStyle(fontSize: 12, color: Colors.amber.shade900),
                        ),
                      ),
                      IconButton(
                        icon: const Icon(Icons.refresh_rounded, size: 20),
                        color: Colors.amber.shade900,
                        onPressed: _fetchDashboard,
                        tooltip: "ព្យាយាមម្តងទៀត",
                      ),
                    ],
                  ),
                ),
              ],
              const SizedBox(height: 20),

              // Overview Stats Cards
              const Text(
                "ស្ថានភាពទូទៅ (Overview)",
                style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
              ),
              const SizedBox(height: 10),

              _isLoading
                  ? const Center(child: Padding(padding: EdgeInsets.all(16), child: SpinKitFadingCircle(color: AppColors.primary, size: 32)))
                  : _buildStatsWidgets(auth, stats),

              const SizedBox(height: 24),

              // -------------------------------------------------------------
              // 🌟 ALL FEATURES HUB (មជ្ឈមណ្ឌលមុខងារទាំងអស់)
              // -------------------------------------------------------------
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Expanded(
                    child: Text(
                      "មុខងារទាំងអស់ (All Features)",
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(
                      color: AppColors.primary.withValues(alpha: 0.08),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      auth.role,
                      style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: AppColors.primary),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),

              _buildAllFeaturesGrid(context, auth),
              const SizedBox(height: 20),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildAllFeaturesGrid(BuildContext context, AuthService auth) {
    List<Map<String, dynamic>> features = [];

    if (auth.isAdmin) {
      features = [
        {
          'title': 'ចុះឈ្មោះសិស្សថ្មី',
          'subtitle': 'Student Admission',
          'icon': Icons.person_add_alt_1_rounded,
          'color': const Color(0xFF10B981),
          'onTap': () => Navigator.push(context, MaterialPageRoute(builder: (_) => const StudentEnrollmentScreen())),
        },
        {
          'title': 'បញ្ជី និងគ្រប់គ្រងសិស្ស',
          'subtitle': 'Student Directory',
          'icon': Icons.people_alt_rounded,
          'color': const Color(0xFF4F46E5),
          'onTap': () => Navigator.push(context, MaterialPageRoute(builder: (_) => const StudentListScreen())),
        },
        {
          'title': 'ឡើងថ្នាក់ & ត្រួតថ្នាក់',
          'subtitle': 'Promotion Matrix',
          'icon': Icons.swap_vert_circle_rounded,
          'color': const Color(0xFFF59E0B),
          'onTap': () => Navigator.push(context, MaterialPageRoute(builder: (_) => const StudentPromotionScreen())),
        },
        {
          'title': 'ស្កេន QR វត្តមាន',
          'subtitle': 'QR Attendance Scan',
          'icon': Icons.qr_code_scanner_rounded,
          'color': const Color(0xFF06B6D4),
          'onTap': () => Navigator.push(context, MaterialPageRoute(builder: (_) => const QRScannerScreen())),
        },
        {
          'title': 'កាលវិភាគទូទៅ',
          'subtitle': 'Timetables',
          'icon': Icons.calendar_month_rounded,
          'color': const Color(0xFF8B5CF6),
          'onTap': () => Navigator.push(context, MaterialPageRoute(builder: (_) => const TimetableScreen())),
        },
        {
          'title': 'ប្រវត្តិកំណត់ត្រាវត្តមាន',
          'subtitle': 'Attendance Logs',
          'icon': Icons.fact_check_rounded,
          'color': const Color(0xFF3B82F6),
          'onTap': () => Navigator.push(context, MaterialPageRoute(builder: (_) => const AttendanceHistoryScreen())),
        },
        {
          'title': 'លទ្ធផល និងពិន្ទុប្រឡង',
          'subtitle': 'Exams & Grades',
          'icon': Icons.military_tech_rounded,
          'color': const Color(0xFFEC4899),
          'onTap': () => Navigator.push(context, MaterialPageRoute(builder: (_) => const ExamGradesScreen())),
        },
        {
          'title': 'ការជូនដំណឹង',
          'subtitle': 'Notifications',
          'icon': Icons.notifications_active_rounded,
          'color': const Color(0xFF64748B),
          'onTap': () => Navigator.push(context, MaterialPageRoute(builder: (_) => const NotificationsScreen())),
        },
      ];
    } else if (auth.isTeacher) {
      features = [
        {
          'title': 'ស្កេន QR វត្តមាន',
          'subtitle': 'Check-In & Students',
          'icon': Icons.qr_code_scanner_rounded,
          'color': const Color(0xFF4F46E5),
          'onTap': () => Navigator.push(context, MaterialPageRoute(builder: (_) => const QRScannerScreen())),
        },
        {
          'title': 'បញ្ចូលពិន្ទុសិស្ស',
          'subtitle': 'Grade Entry',
          'icon': Icons.edit_note_rounded,
          'color': const Color(0xFF10B981),
          'onTap': () => Navigator.push(context, MaterialPageRoute(builder: (_) => const TeacherGradeEntryScreen())),
        },
        {
          'title': 'វេនអនុរក្សប្រឡង',
          'subtitle': 'Invigilator Shifts',
          'icon': Icons.security_rounded,
          'color': const Color(0xFF06B6D4),
          'onTap': () => Navigator.push(context, MaterialPageRoute(builder: (_) => const ExamInvigilatorScreen())),
        },
        {
          'title': 'ចុះឈ្មោះសិស្សថ្មី',
          'subtitle': 'Student Admission',
          'icon': Icons.person_add_alt_1_rounded,
          'color': const Color(0xFFF59E0B),
          'onTap': () => Navigator.push(context, MaterialPageRoute(builder: (_) => const StudentEnrollmentScreen())),
        },
        {
          'title': 'បញ្ជីសិស្សតាមថ្នាក់',
          'subtitle': 'Class Students',
          'icon': Icons.people_alt_rounded,
          'color': const Color(0xFF8B5CF6),
          'onTap': () => Navigator.push(context, MaterialPageRoute(builder: (_) => const StudentListScreen())),
        },
        {
          'title': 'ឡើងថ្នាក់ & ត្រួតថ្នាក់',
          'subtitle': 'Student Promotion',
          'icon': Icons.swap_vert_circle_rounded,
          'color': const Color(0xFFEC4899),
          'onTap': () => Navigator.push(context, MaterialPageRoute(builder: (_) => const StudentPromotionScreen())),
        },
        {
          'title': 'កាលវិភាគបង្រៀន',
          'subtitle': 'My Schedule',
          'icon': Icons.calendar_month_rounded,
          'color': const Color(0xFF3B82F6),
          'onTap': () => Navigator.push(context, MaterialPageRoute(builder: (_) => const TimetableScreen())),
        },
        {
          'title': 'ប្រវត្តិវត្តមានរបស់ខ្ញុំ',
          'subtitle': 'My Attendance',
          'icon': Icons.fact_check_rounded,
          'color': const Color(0xFF64748B),
          'onTap': () => Navigator.push(context, MaterialPageRoute(builder: (_) => const AttendanceHistoryScreen())),
        },
      ];
    } else if (auth.isStudent) {
      features = [
        {
          'title': 'កាតសិស្ស & កន្លែងប្រឡង',
          'subtitle': 'ID Card & Desk No',
          'icon': Icons.badge_rounded,
          'color': const Color(0xFF4F46E5),
          'onTap': () => Navigator.push(context, MaterialPageRoute(builder: (_) => const StudentPortalScreen())),
        },
        {
          'title': 'លទ្ធផលប្រឡង & ពិន្ទុ',
          'subtitle': 'Grades & Ranking',
          'icon': Icons.military_tech_rounded,
          'color': const Color(0xFFF59E0B),
          'onTap': () => Navigator.push(context, MaterialPageRoute(builder: (_) => const ExamGradesScreen())),
        },
        {
          'title': 'កាលវិភាគសិក្សា',
          'subtitle': 'Class Timetable',
          'icon': Icons.calendar_month_rounded,
          'color': const Color(0xFF06B6D4),
          'onTap': () => Navigator.push(context, MaterialPageRoute(builder: (_) => const TimetableScreen())),
        },
        {
          'title': 'ប្រវត្តិកំណត់ត្រាវត្តមាន',
          'subtitle': 'Attendance Record',
          'icon': Icons.fact_check_rounded,
          'color': const Color(0xFF10B981),
          'onTap': () => Navigator.push(context, MaterialPageRoute(builder: (_) => const AttendanceHistoryScreen())),
        },
        {
          'title': 'ដំណឹងសាលា',
          'subtitle': 'Announcements',
          'icon': Icons.notifications_active_rounded,
          'color': const Color(0xFF3B82F6),
          'onTap': () => Navigator.push(context, MaterialPageRoute(builder: (_) => const NotificationsScreen())),
        },
        {
          'title': 'គណនីផ្ទាល់ខ្លួន',
          'subtitle': 'Student Profile',
          'icon': Icons.person_rounded,
          'color': const Color(0xFF8B5CF6),
          'onTap': () => Navigator.push(context, MaterialPageRoute(builder: (_) => const ProfileScreen())),
        },
      ];
    } else {
      // Accountant
      features = [
        {
          'title': 'បញ្ជីសិស្ស & ថ្លៃសិក្សា',
          'subtitle': 'Student Tuition',
          'icon': Icons.people_alt_rounded,
          'color': const Color(0xFF4F46E5),
          'onTap': () => Navigator.push(context, MaterialPageRoute(builder: (_) => const StudentListScreen())),
        },
        {
          'title': 'ចុះឈ្មោះសិស្សថ្មី',
          'subtitle': 'Student Admission',
          'icon': Icons.person_add_alt_1_rounded,
          'color': const Color(0xFF10B981),
          'onTap': () => Navigator.push(context, MaterialPageRoute(builder: (_) => const StudentEnrollmentScreen())),
        },
        {
          'title': 'ស្កេនផ្ទៀងផ្ទាត់កាតសិស្ស',
          'subtitle': 'Verify Student ID',
          'icon': Icons.qr_code_scanner_rounded,
          'color': const Color(0xFF06B6D4),
          'onTap': () => Navigator.push(context, MaterialPageRoute(builder: (_) => const QRScannerScreen())),
        },
        {
          'title': 'ការជូនដំណឹង',
          'subtitle': 'Notifications',
          'icon': Icons.notifications_active_rounded,
          'color': const Color(0xFF64748B),
          'onTap': () => Navigator.push(context, MaterialPageRoute(builder: (_) => const NotificationsScreen())),
        },
      ];
    }

    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: features.length,
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        crossAxisSpacing: 12,
        mainAxisSpacing: 12,
        childAspectRatio: 1.45,
      ),
      itemBuilder: (ctx, idx) {
        final f = features[idx];
        final Color c = f['color'] as Color;

        return InkWell(
          onTap: f['onTap'] as VoidCallback,
          borderRadius: BorderRadius.circular(18),
          child: Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: AppColors.borderLight),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.02),
                  blurRadius: 8,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: c.withValues(alpha: 0.12),
                    shape: BoxShape.circle,
                  ),
                  child: Icon(f['icon'] as IconData, color: c, size: 22),
                ),
                const Spacer(),
                Text(
                  f['title'] as String,
                  style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                Text(
                  f['subtitle'] as String,
                  style: const TextStyle(fontSize: 10.5, color: AppColors.textSecondary),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
        );
      },
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
    } else if (auth.isAccountant) {
      return Row(
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
              title: "វត្តមានសិស្សថ្ងៃនេះ",
              value: "${stats['today_student_attendance'] ?? 0} នាក់",
              color: AppColors.success,
              icon: Icons.how_to_reg,
            ),
          ),
        ],
      );
    } else {
      // Super Admin
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
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: _buildMetricCard(
                  title: "គ្រូមានវត្តមានថ្ងៃនេះ",
                  value: "${stats['today_teacher_attendance'] ?? 0} នាក់",
                  color: AppColors.success,
                  icon: Icons.how_to_reg,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildMetricCard(
                  title: "សិស្សមានវត្តមានថ្ងៃនេះ",
                  value: "${stats['today_student_attendance'] ?? 0} នាក់",
                  color: AppColors.info,
                  icon: Icons.how_to_reg,
                ),
              ),
            ],
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
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.borderLight),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(icon, color: color, size: 22),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: const TextStyle(fontSize: 11.5, color: AppColors.textSecondary)),
                const SizedBox(height: 2),
                Text(
                  value,
                  style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: color),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
