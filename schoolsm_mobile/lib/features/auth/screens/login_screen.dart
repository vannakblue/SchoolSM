import 'package:flutter/material.dart';
import 'package:flutter_spinkit/flutter_spinkit.dart';
import 'package:provider/provider.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/api_constants.dart';
import '../../../core/services/auth_service.dart';
import '../../dashboard/screens/main_navigation_screen.dart';

class DemoRoleItem {
  final String key;
  final String title;
  final String roleNameKh;
  final String desc;
  final String username;
  final String password;
  final IconData icon;
  final Color primaryColor;
  final Color badgeColor;

  const DemoRoleItem({
    required this.key,
    required this.title,
    required this.roleNameKh,
    required this.desc,
    required this.username,
    required this.password,
    required this.icon,
    required this.primaryColor,
    required this.badgeColor,
  });
}

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _obscurePassword = true;
  bool _rememberMe = true;
  bool _autoLoginOnSelect = true;
  String? _selectedRoleKey;

  final List<DemoRoleItem> _demoRoles = const [
    DemoRoleItem(
      key: 'ADMIN',
      title: 'Admin',
      roleNameKh: 'អ្នកគ្រប់គ្រងទូទៅ',
      desc: 'គ្រប់គ្រងទូទៅ & របាយការណ៍សាលា',
      username: 'admin',
      password: 'admin123',
      icon: Icons.admin_panel_settings_rounded,
      primaryColor: Color(0xFF6366F1),
      badgeColor: Color(0xFF4F46E5),
    ),
    DemoRoleItem(
      key: 'TEACHER',
      title: 'Teacher',
      roleNameKh: 'លោកគ្រូ-អ្នកគ្រូ',
      desc: 'ស្រង់វត្តមាន, កាលវិភាគ & ដាក់ពិន្ទុ',
      username: 'teacher',
      password: 'admin123',
      icon: Icons.person_pin_rounded,
      primaryColor: Color(0xFF10B981),
      badgeColor: Color(0xFF059669),
    ),
    DemoRoleItem(
      key: 'STUDENT',
      title: 'Student',
      roleNameKh: 'សិស្សានុសិស្ស',
      desc: 'មើលវត្តមាន, កាលវិភាគ & លទ្ធផលប្រឡង',
      username: 'student1',
      password: 'admin123',
      icon: Icons.school_rounded,
      primaryColor: Color(0xFF0EA5E9),
      badgeColor: Color(0xFF0284C7),
    ),
    DemoRoleItem(
      key: 'ACCOUNTANT',
      title: 'Finance',
      roleNameKh: 'គណនេយ្យករ',
      desc: 'គ្រប់គ្រងវិក្កយបត្រ & បង់ថ្លៃសិក្សា',
      username: 'accountant',
      password: 'admin123',
      icon: Icons.account_balance_wallet_rounded,
      primaryColor: Color(0xFFF59E0B),
      badgeColor: Color(0xFFD97706),
    ),
  ];

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  void _selectDemoRole(DemoRoleItem role) {
    setState(() {
      _selectedRoleKey = role.key;
      _usernameController.text = role.username;
      _passwordController.text = role.password;
    });

    ScaffoldMessenger.of(context).hideCurrentSnackBar();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            Icon(role.icon, color: Colors.white, size: 20),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                _autoLoginOnSelect
                    ? "⚡ កំពុង Login ស្វ័យប្រវត្តិក្នងនាម ${role.roleNameKh}..."
                    : "បានបំពេញគណនី ${role.roleNameKh} (${role.username})",
                style: const TextStyle(fontWeight: FontWeight.bold),
              ),
            ),
          ],
        ),
        backgroundColor: role.primaryColor,
        duration: const Duration(seconds: 2),
      ),
    );

    if (_autoLoginOnSelect) {
      _handleLogin();
    }
  }

  void _handleLogin() async {
    final username = _usernameController.text.trim();
    final password = _passwordController.text.trim();

    if (username.isEmpty || password.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text("សូមបញ្ចូលឈ្មោះគណនី និងពាក្យសម្ងាត់!"),
          backgroundColor: AppColors.danger,
        ),
      );
      return;
    }

    final auth = Provider.of<AuthService>(context, listen: false);
    final result = await auth.login(username, password);

    if (!mounted) return;

    if (result['success']) {
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (_) => const MainNavigationScreen()),
      );
    } else {
      showDialog(
        context: context,
        builder: (ctx) => AlertDialog(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          title: const Row(
            children: [
              Icon(Icons.error_outline, color: AppColors.danger),
              SizedBox(width: 8),
              Text("មិនអាចចូលបាន", style: TextStyle(fontWeight: FontWeight.bold)),
            ],
          ),
          content: Text(result['message'] ?? 'Login failed'),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text("យល់ព្រម"),
            ),
          ],
        ),
      );
    }
  }

  void _showServerSettingsDialog() {
    final urlController = TextEditingController(text: ApiConstants.baseUrl);
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: const Row(
          children: [
            Icon(Icons.dns, color: AppColors.primary),
            SizedBox(width: 8),
            Text("កំណត់ Server Backend", style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              "បញ្ចូលអាសយដ្ឋាន Server IP ឬ Domain ដែលកំពុងដំណើរការ Django:",
              style: TextStyle(fontSize: 13, color: AppColors.textSecondary),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: urlController,
              decoration: InputDecoration(
                prefixIcon: const Icon(Icons.link),
                hintText: "http://192.168.1.xxx:8000",
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                filled: true,
                fillColor: AppColors.bgLight,
              ),
            ),
            const SizedBox(height: 12),
            const Text(
              "ជ្រើសរើសរហ័ស (Quick Presets):",
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppColors.textSecondary),
            ),
            const SizedBox(height: 6),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                ActionChip(
                  avatar: const Icon(Icons.cloud_done, size: 14, color: AppColors.primary),
                  label: const Text("Render Cloud", style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold)),
                  onPressed: () => urlController.text = "https://schoolsm.onrender.com",
                ),
                ActionChip(
                  avatar: const Icon(Icons.computer, size: 14, color: AppColors.secondary),
                  label: const Text("Localhost", style: TextStyle(fontSize: 11)),
                  onPressed: () => urlController.text = "http://127.0.0.1:8000",
                ),
                ActionChip(
                  avatar: const Icon(Icons.phone_android, size: 14, color: AppColors.success),
                  label: const Text("Emulator (10.0.2.2)", style: TextStyle(fontSize: 11)),
                  onPressed: () => urlController.text = "http://10.0.2.2:8000",
                ),
              ],
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text("បោះបង់"),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.primary,
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            ),
            onPressed: () async {
              await ApiConstants.saveBaseUrl(urlController.text.trim());
              if (!mounted) return;
              if (ctx.mounted) {
                Navigator.pop(ctx);
              }
              setState(() {});
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                  content: Text("បានរក្សាទុក Server: ${ApiConstants.baseUrl}"),
                  backgroundColor: AppColors.success,
                ),
              );
            },
            child: const Text("រក្សាទុក"),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final auth = Provider.of<AuthService>(context);

    return Scaffold(
      backgroundColor: AppColors.bgDark,
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                // Top Action Bar: Server Connection Badge
                Align(
                  alignment: Alignment.topRight,
                  child: InkWell(
                    onTap: _showServerSettingsDialog,
                    borderRadius: BorderRadius.circular(20),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.08),
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(color: Colors.white.withValues(alpha: 0.18)),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            ApiConstants.baseUrl.startsWith("https") ? Icons.cloud_done : Icons.dns,
                            size: 14,
                            color: AppColors.secondary,
                          ),
                          const SizedBox(width: 6),
                          Text(
                            ApiConstants.baseUrl.replaceAll("https://", "").replaceAll("http://", ""),
                            style: const TextStyle(fontSize: 11, color: AppColors.textDarkSecondary, fontWeight: FontWeight.bold),
                          ),
                          const SizedBox(width: 6),
                          const Icon(Icons.swap_horiz, size: 14, color: AppColors.primaryLight),
                        ],
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 10),

                // Animated App Logo
                Container(
                  width: 80,
                  height: 80,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: AppColors.primaryGradient,
                    boxShadow: [
                      BoxShadow(
                        color: AppColors.primary.withValues(alpha: 0.4),
                        blurRadius: 20,
                        offset: const Offset(0, 8),
                      ),
                    ],
                  ),
                  child: const Center(
                    child: Icon(Icons.school_rounded, size: 44, color: Colors.white),
                  ),
                ),
                const SizedBox(height: 14),

                // App Title
                const Text(
                  "SchoolSM Mobile",
                  style: TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                    color: Colors.white,
                    letterSpacing: 0.5,
                  ),
                ),
                const SizedBox(height: 4),
                const Text(
                  "ប្រព័ន្ធគ្រប់គ្រងសាលារៀនឌីជីថល",
                  style: TextStyle(
                    fontSize: 14,
                    color: AppColors.secondary,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                const SizedBox(height: 24),

                // ----------------------------------------------------
                // 🌟 QUICK DEMO ROLE SWITCHER CARD (NEW)
                // ----------------------------------------------------
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [
                        const Color(0xFF1E293B),
                        const Color(0xFF0F172A).withValues(alpha: 0.95),
                      ],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: AppColors.primary.withValues(alpha: 0.4), width: 1.2),
                    boxShadow: [
                      BoxShadow(
                        color: AppColors.primary.withValues(alpha: 0.15),
                        blurRadius: 16,
                        offset: const Offset(0, 4),
                      ),
                    ],
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          const Row(
                            children: [
                              Icon(Icons.bolt_rounded, color: AppColors.accent, size: 20),
                              SizedBox(width: 6),
                              Text(
                                "សាកល្បង Demo Login",
                                style: TextStyle(
                                  fontSize: 15,
                                  fontWeight: FontWeight.bold,
                                  color: Colors.white,
                                ),
                              ),
                            ],
                          ),
                          // Auto Login Switch
                          InkWell(
                            onTap: () => setState(() => _autoLoginOnSelect = !_autoLoginOnSelect),
                            borderRadius: BorderRadius.circular(12),
                            child: Padding(
                              padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Text(
                                    _autoLoginOnSelect ? "Auto-Login: ON" : "Auto-Login: OFF",
                                    style: TextStyle(
                                      fontSize: 11,
                                      fontWeight: FontWeight.bold,
                                      color: _autoLoginOnSelect ? AppColors.success : AppColors.textDarkSecondary,
                                    ),
                                  ),
                                  const SizedBox(width: 4),
                                  Icon(
                                    _autoLoginOnSelect ? Icons.toggle_on_rounded : Icons.toggle_off_rounded,
                                    size: 24,
                                    color: _autoLoginOnSelect ? AppColors.success : AppColors.textDarkSecondary,
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 4),
                      const Text(
                        "ចុចលើតួនាទីខាងក្រោមដើម្បីបំពេញ និង Login ភ្លាមៗ៖",
                        style: TextStyle(fontSize: 12, color: AppColors.textDarkSecondary),
                      ),
                      const SizedBox(height: 12),

                      // 2x2 Grid of Role Cards
                      GridView.builder(
                        shrinkWrap: true,
                        physics: const NeverScrollableScrollPhysics(),
                        itemCount: _demoRoles.length,
                        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                          crossAxisCount: 2,
                          crossAxisSpacing: 10,
                          mainAxisSpacing: 10,
                          childAspectRatio: 2.1,
                        ),
                        itemBuilder: (ctx, idx) {
                          final r = _demoRoles[idx];
                          final isSelected = _selectedRoleKey == r.key;
                          return InkWell(
                            onTap: auth.isLoading ? null : () => _selectDemoRole(r),
                            borderRadius: BorderRadius.circular(14),
                            child: AnimatedContainer(
                              duration: const Duration(milliseconds: 200),
                              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                              decoration: BoxDecoration(
                                color: isSelected ? r.primaryColor.withValues(alpha: 0.2) : Colors.white.withValues(alpha: 0.04),
                                borderRadius: BorderRadius.circular(14),
                                border: Border.all(
                                  color: isSelected ? r.primaryColor : Colors.white.withValues(alpha: 0.12),
                                  width: isSelected ? 1.8 : 1,
                                ),
                              ),
                              child: Row(
                                children: [
                                  Container(
                                    width: 34,
                                    height: 34,
                                    decoration: BoxDecoration(
                                      color: r.primaryColor.withValues(alpha: 0.2),
                                      shape: BoxShape.circle,
                                    ),
                                    child: Icon(r.icon, size: 18, color: r.primaryColor),
                                  ),
                                  const SizedBox(width: 8),
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      mainAxisAlignment: MainAxisAlignment.center,
                                      children: [
                                        Text(
                                          r.title,
                                          style: const TextStyle(
                                            fontSize: 13,
                                            fontWeight: FontWeight.bold,
                                            color: Colors.white,
                                          ),
                                          maxLines: 1,
                                          overflow: TextOverflow.ellipsis,
                                        ),
                                        Text(
                                          r.roleNameKh,
                                          style: TextStyle(
                                            fontSize: 10,
                                            color: r.primaryColor,
                                            fontWeight: FontWeight.w600,
                                          ),
                                          maxLines: 1,
                                          overflow: TextOverflow.ellipsis,
                                        ),
                                      ],
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          );
                        },
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 20),

                // ----------------------------------------------------
                // Standard Login Form Card
                // ----------------------------------------------------
                Container(
                  padding: const EdgeInsets.all(22),
                  decoration: BoxDecoration(
                    color: AppColors.bgDarkCard,
                    borderRadius: BorderRadius.circular(22),
                    border: Border.all(color: AppColors.borderDark),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withValues(alpha: 0.25),
                        blurRadius: 18,
                        offset: const Offset(0, 6),
                      ),
                    ],
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        "គណនីផ្ទាល់ខ្លួន (Manual Login)",
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                          color: Colors.white,
                        ),
                      ),
                      const SizedBox(height: 16),

                      // Username Input
                      TextField(
                        controller: _usernameController,
                        style: const TextStyle(color: Colors.white),
                        decoration: InputDecoration(
                          labelText: "ឈ្មោះគណនី / Username or ID",
                          labelStyle: const TextStyle(color: AppColors.textDarkSecondary),
                          prefixIcon: const Icon(Icons.person_outline, color: AppColors.primaryLight),
                          filled: true,
                          fillColor: AppColors.bgDark,
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(14),
                            borderSide: const BorderSide(color: AppColors.borderDark),
                          ),
                          enabledBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(14),
                            borderSide: const BorderSide(color: AppColors.borderDark),
                          ),
                          focusedBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(14),
                            borderSide: const BorderSide(color: AppColors.primary, width: 2),
                          ),
                        ),
                      ),
                      const SizedBox(height: 14),

                      // Password Input
                      TextField(
                        controller: _passwordController,
                        obscureText: _obscurePassword,
                        style: const TextStyle(color: Colors.white),
                        decoration: InputDecoration(
                          labelText: "ពាក្យសម្ងាត់ / Password",
                          labelStyle: const TextStyle(color: AppColors.textDarkSecondary),
                          prefixIcon: const Icon(Icons.lock_outline, color: AppColors.primaryLight),
                          suffixIcon: IconButton(
                            icon: Icon(
                              _obscurePassword ? Icons.visibility_off : Icons.visibility,
                              color: AppColors.textDarkSecondary,
                            ),
                            onPressed: () {
                              setState(() => _obscurePassword = !_obscurePassword);
                            },
                          ),
                          filled: true,
                          fillColor: AppColors.bgDark,
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(14),
                            borderSide: const BorderSide(color: AppColors.borderDark),
                          ),
                          enabledBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(14),
                            borderSide: const BorderSide(color: AppColors.borderDark),
                          ),
                          focusedBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(14),
                            borderSide: const BorderSide(color: AppColors.primary, width: 2),
                          ),
                        ),
                      ),
                      const SizedBox(height: 10),

                      // Remember Me
                      Row(
                        children: [
                          Checkbox(
                            value: _rememberMe,
                            activeColor: AppColors.primary,
                            checkColor: Colors.white,
                            onChanged: (v) => setState(() => _rememberMe = v ?? true),
                          ),
                          const Text(
                            "ចងចាំការចូលប្រើ",
                            style: TextStyle(color: AppColors.textDarkSecondary, fontSize: 13),
                          ),
                        ],
                      ),
                      const SizedBox(height: 14),

                      // Submit Button
                      SizedBox(
                        width: double.infinity,
                        height: 50,
                        child: ElevatedButton(
                          style: ElevatedButton.styleFrom(
                            backgroundColor: AppColors.primary,
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(14),
                            ),
                            elevation: 4,
                          ),
                          onPressed: auth.isLoading ? null : _handleLogin,
                          child: auth.isLoading
                              ? const SpinKitThreeBounce(color: Colors.white, size: 24)
                              : const Row(
                                  mainAxisAlignment: MainAxisAlignment.center,
                                  children: [
                                    Text(
                                      "ចូលប្រើប្រព័ន្ធ (Login)",
                                      style: TextStyle(
                                        fontSize: 16,
                                        fontWeight: FontWeight.bold,
                                        color: Colors.white,
                                      ),
                                    ),
                                    SizedBox(width: 8),
                                    Icon(Icons.arrow_forward, color: Colors.white, size: 20),
                                  ],
                                ),
                        ),
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 20),
                // Helper Info
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.04),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.verified_user_outlined, size: 15, color: AppColors.secondary),
                      SizedBox(width: 8),
                      Text(
                        "គាំទ្រសិទ្ធិ: Admin, គ្រូបង្រៀន, សិស្ស & មាតាបិតា",
                        style: TextStyle(fontSize: 11.5, color: AppColors.textDarkSecondary),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
