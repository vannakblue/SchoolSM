import 'package:flutter/material.dart';
import 'package:flutter_spinkit/flutter_spinkit.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/api_constants.dart';
import '../../../core/api/api_client.dart';

class TeacherScanControlScreen extends StatefulWidget {
  const TeacherScanControlScreen({super.key});

  @override
  State<TeacherScanControlScreen> createState() => _TeacherScanControlScreenState();
}

class _TeacherScanControlScreenState extends State<TeacherScanControlScreen> {
  bool _isLoading = true;
  bool _isSaving = false;
  String? _errorMessage;

  // Configuration values
  bool _enableQrCheckin = true;
  bool _enableFaceAiCheckin = true;
  bool _enableBiometricDevice = true;
  String _activeDailyMode = 'ALL';

  List<dynamic> _dailyModeChoices = [];

  @override
  void initState() {
    super.initState();
    _fetchConfig();
  }

  Future<void> _fetchConfig() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final res = await ApiClient().dio.get(ApiConstants.teacherAttendanceConfig);
      final data = res.data;
      if (data['status'] == 'success') {
        final config = data['config'] ?? {};
        setState(() {
          _enableQrCheckin = config['enable_qr_checkin'] ?? true;
          _enableFaceAiCheckin = config['enable_face_ai_checkin'] ?? true;
          _enableBiometricDevice = config['enable_biometric_device'] ?? true;
          _activeDailyMode = config['active_daily_mode'] ?? 'ALL';
          _dailyModeChoices = data['daily_mode_choices'] ?? [];
          _isLoading = false;
        });
      } else {
        setState(() {
          _errorMessage = data['message'] ?? 'មិនអាចទាញទិន្នន័យបាន';
          _isLoading = false;
        });
      }
    } catch (e) {
      setState(() {
        _errorMessage = ApiClient.getErrorMessage(e);
        _isLoading = false;
      });
    }
  }

  Future<void> _saveConfig() async {
    setState(() => _isSaving = true);
    try {
      final res = await ApiClient().dio.post(
        ApiConstants.teacherAttendanceConfig,
        data: {
          'enable_qr_checkin': _enableQrCheckin,
          'active_daily_mode': _activeDailyMode,
          'enable_face_ai_checkin': _enableFaceAiCheckin,
          'enable_biometric_device': _enableBiometricDevice,
        },
      );

      final data = res.data;
      if (!mounted) return;

      setState(() => _isSaving = false);

      if (data['status'] == 'success') {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            backgroundColor: AppColors.success,
            behavior: SnackBarBehavior.floating,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            content: Row(
              children: [
                const Icon(Icons.check_circle_rounded, color: Colors.white),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    data['message'] ?? 'បានរក្សាទុកការកំណត់ដោយជោគជ័យ!',
                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                  ),
                ),
              ],
            ),
          ),
        );
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            backgroundColor: AppColors.danger,
            behavior: SnackBarBehavior.floating,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            content: Text(data['message'] ?? 'ការរក្សាទុកបានបរាជ័យ'),
          ),
        );
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _isSaving = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          backgroundColor: AppColors.danger,
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          content: Text("កំហុស៖ ${ApiClient.getErrorMessage(e)}"),
        ),
      );
    }
  }

  IconData _getModeIcon(String value) {
    switch (value) {
      case 'OPTION_1_QR':
        return Icons.qr_code_rounded;
      case 'OPTION_2_FACE':
        return Icons.face_retouching_natural_rounded;
      case 'OPTION_3_BIOMETRIC':
        return Icons.fingerprint_rounded;
      case 'ALL':
      default:
        return Icons.all_inclusive_rounded;
    }
  }

  Color _getModeColor(String value) {
    switch (value) {
      case 'OPTION_1_QR':
        return const Color(0xFF0284C7); // Cyan / Sky
      case 'OPTION_2_FACE':
        return const Color(0xFF8B5CF6); // Purple
      case 'OPTION_3_BIOMETRIC':
        return const Color(0xFFF59E0B); // Amber
      case 'ALL':
      default:
        return const Color(0xFF10B981); // Emerald
    }
  }

  String _getModeDescription(String value) {
    switch (value) {
      case 'OPTION_1_QR':
        return 'អនុញ្ញាតឱ្យគ្រូស្កេន Dynamic QR Code លើអេក្រង់ Kiosk ឬទូរស័ព្ទប៉ុណ្ណោះ';
      case 'OPTION_2_FACE':
        return 'អនុញ្ញាតឱ្យគ្រូស្កេនផ្ទៃមុខ Webcam Face AI មុខសាលាប៉ុណ្ណោះ (បិទ QR និង Fingerprint)';
      case 'OPTION_3_BIOMETRIC':
        return 'អនុញ្ញាតឱ្យប្រើតែម៉ាស៊ីនស្កេនមេដៃ / ឧបករណ៍ Biometric Hardware ប៉ុណ្ណោះ';
      case 'ALL':
      default:
        return 'អនុញ្ញាតឱ្យគ្រូប្រើប្រាស់គ្រប់ជម្រើសស្កេន (QR, Face AI, Biometric Hardware)';
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bgLight,
      appBar: AppBar(
        title: const Text(
          "គ្រប់គ្រងការស្កេនវត្តមានគ្រូ",
          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: _fetchConfig,
            tooltip: "ទាញយកទិន្នន័យឡើងវិញ",
          ),
        ],
      ),
      body: _isLoading
          ? const Center(
              child: SpinKitFadingCircle(color: AppColors.primary, size: 36),
            )
          : _errorMessage != null
              ? _buildErrorView()
              : RefreshIndicator(
                  onRefresh: _fetchConfig,
                  child: SingleChildScrollView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _buildStatusHeaderCard(),
                        const SizedBox(height: 18),
                        _buildDailyEnforcedModeSection(),
                        const SizedBox(height: 18),
                        _buildMethodTogglesSection(),
                        const SizedBox(height: 24),
                        _buildSaveButton(),
                        const SizedBox(height: 20),
                      ],
                    ),
                  ),
                ),
    );
  }

  Widget _buildErrorView() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.error_outline_rounded, size: 48, color: AppColors.danger),
            const SizedBox(height: 12),
            Text(
              _errorMessage ?? 'មានបញ្ហាក្នុងការទាញទិន្នន័យ',
              textAlign: TextAlign.center,
              style: const TextStyle(color: AppColors.textSecondary, fontSize: 14),
            ),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: _fetchConfig,
              icon: const Icon(Icons.refresh_rounded),
              label: const Text("ព្យាយាមម្តងទៀត"),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.primary,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStatusHeaderCard() {
    final bool isQrActive = _enableQrCheckin && (_activeDailyMode == 'ALL' || _activeDailyMode == 'OPTION_1_QR');
    final modeColor = _getModeColor(_activeDailyMode);

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            isQrActive ? const Color(0xFF0F172A) : const Color(0xFF7F1D1D),
            isQrActive ? const Color(0xFF1E293B) : const Color(0xFF991B1B),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: (isQrActive ? Colors.black : Colors.red).withValues(alpha: 0.15),
            blurRadius: 16,
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
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      isQrActive ? Icons.check_circle_rounded : Icons.block_rounded,
                      color: isQrActive ? const Color(0xFF4ADE80) : const Color(0xFFFCA5A5),
                      size: 14,
                    ),
                    const SizedBox(width: 6),
                    Text(
                      isQrActive ? "QR SCANNING ACTIVE" : "QR SCAN DISABLED",
                      style: TextStyle(
                        color: isQrActive ? const Color(0xFF4ADE80) : const Color(0xFFFCA5A5),
                        fontWeight: FontWeight.bold,
                        fontSize: 11,
                        letterSpacing: 0.5,
                      ),
                    ),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: modeColor.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: modeColor.withValues(alpha: 0.4)),
                ),
                child: Text(
                  _activeDailyMode,
                  style: TextStyle(
                    color: modeColor,
                    fontWeight: FontWeight.bold,
                    fontSize: 11,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          const Text(
            "សិទ្ធិគ្រប់គ្រងវត្តមានគ្រូ (Admin Authority)",
            style: TextStyle(color: Colors.white, fontSize: 17, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 4),
          Text(
            isQrActive
                ? "គ្រូបង្រៀនអាចស្កេន Dynamic QR Code លើ Kiosk ឬទូរស័ព្ទបានធម្មតា។"
                : "ការស្កេន Dynamic QR Code ត្រូវបានបិទ ឬកំណត់ឱ្យប្រើវិធីសាស្ត្រផ្សេង។",
            style: TextStyle(color: Colors.white.withValues(alpha: 0.85), fontSize: 12),
          ),
        ],
      ),
    );
  }

  Widget _buildDailyEnforcedModeSection() {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.04),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: AppColors.primary.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.tune_rounded, color: AppColors.primary, size: 20),
              ),
              const SizedBox(width: 10),
              const Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      "វិធីសាស្ត្រស្កេនប្រចាំថ្ងៃ (Daily Enforced Mode)",
                      style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
                    ),
                    Text(
                      "កំណត់វិធីសាស្ត្រតែមួយគត់ ឬអនុញ្ញាតគ្រប់ជម្រើសសម្រាប់គ្រូ",
                      style: TextStyle(fontSize: 11, color: AppColors.textSecondary),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          // Choices List
          ..._dailyModeChoices.map((choice) {
            final val = choice['value'] as String? ?? '';
            final label = choice['label'] as String? ?? '';
            final isSelected = _activeDailyMode == val;
            final itemColor = _getModeColor(val);
            final itemIcon = _getModeIcon(val);
            final itemDesc = _getModeDescription(val);

            return InkWell(
              onTap: () {
                setState(() {
                  _activeDailyMode = val;
                  // If admin explicitly selected QR only, ensure QR checkin is turned on
                  if (val == 'OPTION_1_QR') {
                    _enableQrCheckin = true;
                  }
                });
              },
              borderRadius: BorderRadius.circular(14),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                margin: const EdgeInsets.only(bottom: 10),
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: isSelected ? itemColor.withValues(alpha: 0.08) : Colors.grey.shade50,
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(
                    color: isSelected ? itemColor : Colors.grey.shade200,
                    width: isSelected ? 2 : 1,
                  ),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: isSelected ? itemColor : Colors.grey.shade200,
                        shape: BoxShape.circle,
                      ),
                      child: Icon(
                        itemIcon,
                        size: 18,
                        color: isSelected ? Colors.white : Colors.grey.shade700,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Expanded(
                                child: Text(
                                  label,
                                  style: TextStyle(
                                    fontSize: 13,
                                    fontWeight: isSelected ? FontWeight.bold : FontWeight.w600,
                                    color: isSelected ? itemColor : AppColors.textPrimary,
                                  ),
                                ),
                              ),
                              if (isSelected)
                                Icon(Icons.check_circle_rounded, color: itemColor, size: 18),
                            ],
                          ),
                          const SizedBox(height: 4),
                          Text(
                            itemDesc,
                            style: TextStyle(
                              fontSize: 11,
                              color: isSelected ? Colors.black87 : AppColors.textSecondary,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            );
          }),
        ],
      ),
    );
  }

  Widget _buildMethodTogglesSection() {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.04),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: const Color(0xFF06B6D4).withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.toggle_on_rounded, color: Color(0xFF06B6D4), size: 20),
              ),
              const SizedBox(width: 10),
              const Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      "បើក / បិទ វិធីសាស្ត្រស្កេននីមួយៗ (Method Toggles)",
                      style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
                    ),
                    Text(
                      "ជ្រើសរើសបើកដំណើរការ ឬបិទការស្កេនវិធីសាស្ត្រណាមួយ",
                      style: TextStyle(fontSize: 11, color: AppColors.textSecondary),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          // QR Switch
          _buildToggleTile(
            title: "Dynamic QR Code (Kiosk & Mobile)",
            subtitle: "គ្រូអាចស្កេន QR Code លើអេក្រង់ Kiosk ឬទូរស័ព្ទដៃ",
            icon: Icons.qr_code_2_rounded,
            iconColor: const Color(0xFF0284C7),
            value: _enableQrCheckin,
            onChanged: (val) {
              setState(() => _enableQrCheckin = val);
            },
          ),
          const Divider(height: 16),
          // Face AI Switch
          _buildToggleTile(
            title: "Webcam Face Recognition AI",
            subtitle: "ស្កេនផ្ទៃមុខតាមកាមេរ៉ា Tablet/Laptop នៅមុខសាលា",
            icon: Icons.camera_front_rounded,
            iconColor: const Color(0xFF8B5CF6),
            value: _enableFaceAiCheckin,
            onChanged: (val) {
              setState(() => _enableFaceAiCheckin = val);
            },
          ),
          const Divider(height: 16),
          // Biometric Switch
          _buildToggleTile(
            title: "ម៉ាស៊ីន Biometric Hardware (ZKTeco)",
            subtitle: "ទទួលទិន្នន័យពីម៉ាស៊ីនស្កេនមេដៃ/ផ្ទៃមុខប្រចាំសាលា",
            icon: Icons.fingerprint_rounded,
            iconColor: const Color(0xFFF59E0B),
            value: _enableBiometricDevice,
            onChanged: (val) {
              setState(() => _enableBiometricDevice = val);
            },
          ),
        ],
      ),
    );
  }

  Widget _buildToggleTile({
    required String title,
    required String subtitle,
    required IconData icon,
    required Color iconColor,
    required bool value,
    required ValueChanged<bool> onChanged,
  }) {
    return Row(
      children: [
        Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: iconColor.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Icon(icon, color: iconColor, size: 20),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
              ),
              Text(
                subtitle,
                style: const TextStyle(fontSize: 11, color: AppColors.textSecondary),
              ),
            ],
          ),
        ),
        Switch(
          value: value,
          activeColor: AppColors.primary,
          onChanged: onChanged,
        ),
      ],
    );
  }

  Widget _buildSaveButton() {
    return SizedBox(
      width: double.infinity,
      height: 52,
      child: ElevatedButton(
        onPressed: _isSaving ? null : _saveConfig,
        style: ElevatedButton.styleFrom(
          backgroundColor: AppColors.primary,
          foregroundColor: Colors.white,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          elevation: 2,
        ),
        child: _isSaving
            ? const SpinKitThreeBounce(color: Colors.white, size: 20)
            : const Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.save_rounded, size: 20),
                  SizedBox(width: 8),
                  Text(
                    "រក្សាទុកការកំណត់ (Save Configuration)",
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                  ),
                ],
              ),
      ),
    );
  }
}
