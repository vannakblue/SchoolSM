import 'package:flutter/material.dart';
import 'package:flutter_spinkit/flutter_spinkit.dart';
import 'package:provider/provider.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/api_constants.dart';
import '../../../core/api/api_client.dart';
import '../../../core/services/auth_service.dart';

class StudentPortalScreen extends StatefulWidget {
  const StudentPortalScreen({super.key});

  @override
  State<StudentPortalScreen> createState() => _StudentPortalScreenState();
}

class _StudentPortalScreenState extends State<StudentPortalScreen> {
  bool _isLoading = true;
  Map<String, dynamic>? _seatingData;
  List<dynamic> _examSeating = [];

  @override
  void initState() {
    super.initState();
    _fetchExamSeating();
  }

  Future<void> _fetchExamSeating() async {
    setState(() => _isLoading = true);
    try {
      final res = await ApiClient().dio.get(ApiConstants.examSeating);
      final data = res.data;
      if (data['status'] == 'success') {
        setState(() {
          _seatingData = data;
          _examSeating = data['exam_seating'] ?? [];
          _isLoading = false;
        });
      } else {
        setState(() => _isLoading = false);
      }
    } catch (_) {
      setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = Provider.of<AuthService>(context);
    final user = auth.user ?? {};
    final studentInfo = _seatingData?['student'] ?? {};

    final khmerName = studentInfo['khmer_name'] ?? user['khmer_name'] ?? auth.displayName;
    final latinName = studentInfo['latin_name'] ?? user['latin_name'] ?? '';
    final studentId = studentInfo['student_id'] ?? user['username'] ?? '';
    final classroom = studentInfo['classroom'] ?? '-';

    return Scaffold(
      backgroundColor: AppColors.bgLight,
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        title: const Text(
          "កាតសិស្ស & កន្លែងប្រឡង",
          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18, color: AppColors.textPrimary),
        ),
      ),
      body: _isLoading
          ? const Center(child: SpinKitFadingCircle(color: AppColors.primary, size: 36))
          : RefreshIndicator(
              onRefresh: _fetchExamSeating,
              child: SingleChildScrollView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // ---------------------------------------------------------
                    // 1. DIGITAL STUDENT ID CARD
                    // ---------------------------------------------------------
                    Container(
                      width: double.infinity,
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(
                          colors: [Color(0xFF1E3A8A), Color(0xFF2563EB), Color(0xFF06B6D4)],
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                        ),
                        borderRadius: BorderRadius.circular(22),
                        boxShadow: [
                          BoxShadow(
                            color: const Color(0xFF1E3A8A).withValues(alpha: 0.35),
                            blurRadius: 18,
                            offset: const Offset(0, 8),
                          ),
                        ],
                      ),
                      padding: const EdgeInsets.all(20),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          // Header: School & MoEYS Logo
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              const Row(
                                children: [
                                  Icon(Icons.school, color: Colors.white, size: 24),
                                  SizedBox(width: 8),
                                  Text(
                                    "SchoolSM International",
                                    style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 14),
                                  ),
                                ],
                              ),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                decoration: BoxDecoration(
                                  color: Colors.white.withValues(alpha: 0.2),
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                child: const Text(
                                  "STUDENT ID",
                                  style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 10),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 18),

                          // Middle: Avatar & Info
                          Row(
                            children: [
                              Container(
                                width: 68,
                                height: 68,
                                decoration: BoxDecoration(
                                  color: Colors.white.withValues(alpha: 0.2),
                                  shape: BoxShape.circle,
                                  border: Border.all(color: Colors.white, width: 2),
                                ),
                                child: Center(
                                  child: Text(
                                    khmerName.isNotEmpty ? khmerName[0] : 'S',
                                    style: const TextStyle(fontSize: 28, fontWeight: FontWeight.bold, color: Colors.white),
                                  ),
                                ),
                              ),
                              const SizedBox(width: 14),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      khmerName,
                                      style: const TextStyle(
                                        color: Colors.white,
                                        fontWeight: FontWeight.bold,
                                        fontSize: 18,
                                      ),
                                    ),
                                    if (latinName.isNotEmpty)
                                      Text(
                                        latinName.toUpperCase(),
                                        style: TextStyle(
                                          color: Colors.white.withValues(alpha: 0.85),
                                          fontSize: 12,
                                          fontWeight: FontWeight.w600,
                                        ),
                                      ),
                                    const SizedBox(height: 6),
                                    Row(
                                      children: [
                                        Container(
                                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                          decoration: BoxDecoration(
                                            color: Colors.black.withValues(alpha: 0.25),
                                            borderRadius: BorderRadius.circular(6),
                                          ),
                                          child: Text(
                                            "ID: $studentId",
                                            style: const TextStyle(
                                              color: Colors.white,
                                              fontSize: 12,
                                              fontWeight: FontWeight.bold,
                                              letterSpacing: 0.5,
                                            ),
                                          ),
                                        ),
                                        const SizedBox(width: 8),
                                        Text(
                                          "ថ្នាក់: $classroom",
                                          style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.bold),
                                        ),
                                      ],
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 20),

                          // Bottom Barcode / QR Simulation
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                            decoration: BoxDecoration(
                              color: Colors.white,
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Row(
                                  children: List.generate(
                                    24,
                                    (index) => Container(
                                      margin: const EdgeInsets.symmetric(horizontal: 1.5),
                                      width: (index % 3 == 0) ? 3 : 1.5,
                                      height: 22,
                                      color: Colors.black,
                                    ),
                                  ),
                                ),
                                const Row(
                                  children: [
                                    Icon(Icons.qr_code_2_rounded, size: 28, color: Colors.black),
                                    SizedBox(width: 4),
                                    Text("VERIFIED", style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: Colors.black)),
                                  ],
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 24),

                    // ---------------------------------------------------------
                    // 2. EXAM SEATING INFORMATION
                    // ---------------------------------------------------------
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Row(
                          children: [
                            Icon(Icons.event_seat_rounded, color: AppColors.primary, size: 22),
                            SizedBox(width: 8),
                            Text(
                              "កន្លែងអង្គុយប្រឡង (Exam Seating)",
                              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
                            ),
                          ],
                        ),
                        if (_examSeating.isNotEmpty)
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                            decoration: BoxDecoration(
                              color: AppColors.success.withValues(alpha: 0.12),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: const Text(
                              "បានរៀបចំបន្ទប់រួច",
                              style: TextStyle(color: AppColors.success, fontWeight: FontWeight.bold, fontSize: 11),
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(height: 12),

                    if (_examSeating.isEmpty)
                      Container(
                        width: double.infinity,
                        padding: const EdgeInsets.all(20),
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(color: AppColors.borderLight),
                        ),
                        child: Column(
                          children: [
                            Icon(Icons.event_busy_rounded, size: 44, color: AppColors.textSecondary.withValues(alpha: 0.5)),
                            const SizedBox(height: 8),
                            const Text(
                              "មិនទាន់មានសម័យប្រឡងសកម្មនៅឡើយទេ",
                              style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
                            ),
                            const SizedBox(height: 4),
                            const Text(
                              "ព័ត៌មានបន្ទប់ និងលេខតុប្រឡងនឹងបង្ហាញនៅទីនេះពេលសាលារៀបចំរួច។",
                              textAlign: TextAlign.center,
                              style: TextStyle(fontSize: 12, color: AppColors.textSecondary),
                            ),
                          ],
                        ),
                      )
                    else
                      ..._examSeating.map((exam) {
                        return Container(
                          margin: const EdgeInsets.only(bottom: 14),
                          padding: const EdgeInsets.all(16),
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
                            children: [
                              Row(
                                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                children: [
                                  Expanded(
                                    child: Text(
                                      exam['exam_name'] ?? 'ការប្រឡង',
                                      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: AppColors.textPrimary),
                                    ),
                                  ),
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                    decoration: BoxDecoration(
                                      color: AppColors.primary.withValues(alpha: 0.1),
                                      borderRadius: BorderRadius.circular(8),
                                    ),
                                    child: Text(
                                      exam['exam_date'] ?? '',
                                      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 12, color: AppColors.primary),
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 14),

                              // Seating Metric Cards
                              Row(
                                children: [
                                  Expanded(
                                    child: _buildSeatTile(
                                      title: "បន្ទប់ប្រឡង",
                                      value: exam['room_name'] ?? exam['room_number'] ?? 'បន្ទប់ -',
                                      icon: Icons.meeting_room_rounded,
                                      color: AppColors.primary,
                                    ),
                                  ),
                                  const SizedBox(width: 10),
                                  Expanded(
                                    child: _buildSeatTile(
                                      title: "លេខតុ (Desk)",
                                      value: exam['desk_number_display'] ?? exam['desk_number']?.toString() ?? '-',
                                      icon: Icons.chair_rounded,
                                      color: AppColors.accent,
                                    ),
                                  ),
                                  const SizedBox(width: 10),
                                  Expanded(
                                    child: _buildSeatTile(
                                      title: "លេខរៀង (Roll)",
                                      value: exam['roll_number']?.toString() ?? '-',
                                      icon: Icons.format_list_numbered_rounded,
                                      color: AppColors.success,
                                    ),
                                  ),
                                ],
                              ),

                              if (exam['building'] != null && exam['building'].isNotEmpty)
                                Padding(
                                  padding: const EdgeInsets.only(top: 10),
                                  child: Row(
                                    children: [
                                      const Icon(Icons.apartment_rounded, size: 16, color: AppColors.textSecondary),
                                      const SizedBox(width: 6),
                                      Text("អគារ៖ ${exam['building']}", style: const TextStyle(fontSize: 12, color: AppColors.textSecondary)),
                                    ],
                                  ),
                                ),
                            ],
                          ),
                        );
                      }),
                  ],
                ),
              ),
            ),
    );
  }

  Widget _buildSeatTile({required String title, required String value, required IconData icon, required Color color}) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 8),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        children: [
          Icon(icon, size: 20, color: color),
          const SizedBox(height: 4),
          Text(title, style: const TextStyle(fontSize: 10.5, color: AppColors.textSecondary)),
          const SizedBox(height: 2),
          Text(
            value,
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: color),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }
}
