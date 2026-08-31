import 'package:flutter/material.dart';
import 'package:flutter_spinkit/flutter_spinkit.dart';
import 'package:provider/provider.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/api_constants.dart';
import '../../../core/services/auth_service.dart';
import '../../dashboard/screens/main_navigation_screen.dart';

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

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    super.dispose();
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
            const SizedBox(height: 8),
            Wrap(
              spacing: 6,
              children: [
                ActionChip(
                  avatar: const Icon(Icons.cloud_done, size: 14, color: AppColors.primary),
                  label: const Text("Render Cloud", style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold)),
                  onPressed: () => urlController.text = "https://schoolsm.onrender.com",
                ),
                ActionChip(
                  label: const Text("Localhost", style: TextStyle(fontSize: 11)),
                  onPressed: () => urlController.text = "http://127.0.0.1:8000",
                ),
                ActionChip(
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
              Navigator.pop(ctx);
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
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                // Server Config Badge on top right
                Align(
                  alignment: Alignment.topRight,
                  child: InkWell(
                    onTap: _showServerSettingsDialog,
                    borderRadius: BorderRadius.circular(20),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                      decoration: BoxDecoration(
                        color: Colors.white.withOpacity(0.08),
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(color: Colors.white.withOpacity(0.15)),
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
                          const SizedBox(width: 4),
                          const Icon(Icons.edit, size: 12, color: AppColors.textDarkSecondary),
                        ],
                      ),
                    ),
                  ),
                ),

                // Animated App Logo
                Container(
                  width: 90,
                  height: 90,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: AppColors.primaryGradient,
                    boxShadow: [
                      BoxShadow(
                        color: AppColors.primary.withOpacity(0.5),
                        blurRadius: 25,
                        offset: const Offset(0, 10),
                      ),
                    ],
                  ),
                  child: const Center(
                    child: Icon(Icons.school, size: 48, color: Colors.white),
                  ),
                ),
                const SizedBox(height: 20),

                // App Title
                const Text(
                  "SchoolSM Mobile",
                  style: TextStyle(
                    fontSize: 26,
                    fontWeight: FontWeight.bold,
                    color: Colors.white,
                    letterSpacing: 0.5,
                  ),
                ),
                const SizedBox(height: 6),
                const Text(
                  "ប្រព័ន្ធគ្រប់គ្រងសាលារៀនឌីជីថល",
                  style: TextStyle(
                    fontSize: 15,
                    color: AppColors.secondary,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                const SizedBox(height: 32),

                // Login Form Card
                Container(
                  padding: const EdgeInsets.all(24),
                  decoration: BoxDecoration(
                    color: AppColors.bgDarkCard,
                    borderRadius: BorderRadius.circular(24),
                    border: Border.all(color: AppColors.borderDark),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withOpacity(0.3),
                        blurRadius: 20,
                        offset: const Offset(0, 8),
                      ),
                    ],
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        "ចូលប្រើប្រព័ន្ធ",
                        style: TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.bold,
                          color: Colors.white,
                        ),
                      ),
                      const SizedBox(height: 6),
                      const Text(
                        "សូមវាយបញ្ចូលឈ្មោះគណនី និងពាក្យសម្ងាត់របស់អ្នក",
                        style: TextStyle(
                          fontSize: 13,
                          color: AppColors.textDarkSecondary,
                        ),
                      ),
                      const SizedBox(height: 24),

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
                      const SizedBox(height: 16),

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
                      const SizedBox(height: 12),

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
                      const SizedBox(height: 16),

                      // Submit Button
                      SizedBox(
                        width: double.infinity,
                        height: 52,
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

                const SizedBox(height: 24),
                // Helper Info
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.05),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.verified_user_outlined, size: 16, color: AppColors.secondary),
                      SizedBox(width: 8),
                      Text(
                        "គាំទ្រសិទ្ធិ: Admin, គ្រូបង្រៀន, សិស្ស & មាតាបិតា",
                        style: TextStyle(fontSize: 12, color: AppColors.textDarkSecondary),
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
