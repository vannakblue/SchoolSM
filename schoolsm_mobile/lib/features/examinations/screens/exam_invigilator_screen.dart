import 'package:flutter/material.dart';
import 'package:flutter_spinkit/flutter_spinkit.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/api_constants.dart';
import '../../../core/api/api_client.dart';

class ExamInvigilatorScreen extends StatefulWidget {
  const ExamInvigilatorScreen({super.key});

  @override
  State<ExamInvigilatorScreen> createState() => _ExamInvigilatorScreenState();
}

class _ExamInvigilatorScreenState extends State<ExamInvigilatorScreen> {
  bool _isLoading = true;
  bool _isToggling = false;

  Map<String, dynamic>? _plan;
  Map<String, dynamic>? _teacherData;
  List<dynamic> _slots = [];

  @override
  void initState() {
    super.initState();
    _fetchInvigilatorData();
  }

  Future<void> _fetchInvigilatorData() async {
    setState(() => _isLoading = true);
    try {
      final statusRes = await ApiClient().dio.get(ApiConstants.invigilatorStatus);
      final slotsRes = await ApiClient().dio.get(ApiConstants.invigilatorSlots);

      if (statusRes.data['is_active'] == true) {
        setState(() {
          _plan = statusRes.data['plan'];
          _teacherData = statusRes.data['teacher'];
          _slots = slotsRes.data['slots'] ?? [];
          _isLoading = false;
        });
      } else {
        setState(() => _isLoading = false);
      }
    } catch (_) {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _toggleSlot(int slotId) async {
    if (_isToggling) return;
    if (_teacherData?['is_finalized'] == true) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text("លោកគ្រូ-អ្នកគ្រូបានបញ្ជាក់ការជ្រើសរើសរួចហើយ មិនអាចកែប្រែបានទេ!"),
          backgroundColor: AppColors.warning,
        ),
      );
      return;
    }

    setState(() => _isToggling = true);
    try {
      final res = await ApiClient().dio.post(
        ApiConstants.invigilatorToggle,
        data: {'slot_id': slotId},
      );

      final data = res.data;
      if (data['status'] == 'success') {
        await _fetchInvigilatorData();
      } else {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(data['message'] ?? 'Error'),
              backgroundColor: AppColors.danger,
            ),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(ApiClient.getErrorMessage(e)),
            backgroundColor: AppColors.danger,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _isToggling = false);
    }
  }

  Future<void> _finalizeRegistration() async {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text("បញ្ជាក់ការចុះឈ្មោះ"),
        content: const Text("តើលោកគ្រូ-អ្នកគ្រូពិតជាចង់បញ្ជាក់ការជ្រើសរើសវេនអនុរក្សនេះជាស្ថាពរមែនទេ? បន្ទាប់ពីបញ្ជាក់ហើយ មិនអាចកែប្រែវិញបានឡើយ។"),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text("បោះបង់")),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.success, foregroundColor: Colors.white),
            onPressed: () async {
              Navigator.pop(ctx);
              try {
                final res = await ApiClient().dio.post(ApiConstants.invigilatorFinalize);
                if (res.data['status'] == 'success') {
                  await _fetchInvigilatorData();
                  if (mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text("🎉 បានបញ្ជាក់វេនអនុរក្សជោគជ័យ!"),
                        backgroundColor: AppColors.success,
                      ),
                    );
                  }
                }
              } catch (e) {
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text(ApiClient.getErrorMessage(e)), backgroundColor: AppColors.danger),
                  );
                }
              }
            },
            child: const Text("យល់ព្រម"),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final t = _teacherData;
    final int requiredShifts = t?['required_shifts'] ?? 0;
    final int currentCount = t?['current_count'] ?? 0;
    final bool isFinalized = t?['is_finalized'] ?? false;
    final bool canFinalize = t?['can_finalize'] ?? false;

    return Scaffold(
      backgroundColor: AppColors.bgLight,
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        title: const Text(
          "វេនអនុរក្សប្រឡង (Proctor Shifts)",
          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 17, color: AppColors.textPrimary),
        ),
      ),
      body: _isLoading
          ? const Center(child: SpinKitFadingCircle(color: AppColors.primary, size: 36))
          : _plan == null
              ? const Center(child: Text("មិនទាន់មានការបើកទទួលចុះឈ្មោះវេនអនុរក្សទេ", style: TextStyle(color: AppColors.textSecondary)))
              : SingleChildScrollView(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Plan & Quota Card
                      Container(
                        padding: const EdgeInsets.all(18),
                        decoration: BoxDecoration(
                          gradient: AppColors.primaryGradient,
                          borderRadius: BorderRadius.circular(20),
                          boxShadow: [
                            BoxShadow(color: AppColors.primary.withValues(alpha: 0.25), blurRadius: 14, offset: const Offset(0, 5)),
                          ],
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              _plan?['title'] ?? 'សម័យប្រឡង',
                              style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              "តួនាទី៖ ${t?['assigned_role_display'] ?? 'អនុរក្ស'}",
                              style: TextStyle(color: Colors.white.withValues(alpha: 0.85), fontSize: 13),
                            ),
                            const SizedBox(height: 14),

                            // Progress Bar
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                const Text("កូតាដែលត្រូវបំពេញ:", style: TextStyle(color: Colors.white, fontSize: 12)),
                                Text(
                                  "$currentCount / $requiredShifts វេន",
                                  style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 14),
                                ),
                              ],
                            ),
                            const SizedBox(height: 8),
                            ClipRRect(
                              borderRadius: BorderRadius.circular(8),
                              child: LinearProgressIndicator(
                                value: requiredShifts > 0 ? (currentCount / requiredShifts).clamp(0.0, 1.0) : 1.0,
                                minHeight: 8,
                                backgroundColor: Colors.white.withValues(alpha: 0.3),
                                valueColor: AlwaysStoppedAnimation<Color>(
                                  currentCount == requiredShifts ? const Color(0xFF4ADE80) : Colors.white,
                                ),
                              ),
                            ),
                            const SizedBox(height: 10),
                            if (isFinalized)
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                                decoration: BoxDecoration(
                                  color: Colors.white.withValues(alpha: 0.2),
                                  borderRadius: BorderRadius.circular(10),
                                ),
                                child: const Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    Icon(Icons.lock, color: Colors.white, size: 14),
                                    SizedBox(width: 6),
                                    Text("បានបញ្ជាក់ជាស្ថាពររួចរាល់", style: TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.bold)),
                                  ],
                                ),
                              ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 20),

                      // Shift Slots List
                      const Text(
                        "កាលវិភាគវេនប្រឡង (ជ្រើសរើសវេនខាងក្រោម)៖",
                        style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
                      ),
                      const SizedBox(height: 12),

                      ..._slots.map((slot) {
                        final bool isRegistered = slot['is_registered'] == true;
                        final bool isFull = slot['role_is_full'] == true;
                        final int slotId = slot['id'] as int;

                        return Container(
                          margin: const EdgeInsets.only(bottom: 12),
                          padding: const EdgeInsets.all(14),
                          decoration: BoxDecoration(
                            color: Colors.white,
                            borderRadius: BorderRadius.circular(16),
                            border: Border.all(
                              color: isRegistered ? AppColors.primary : AppColors.borderLight,
                              width: isRegistered ? 1.8 : 1,
                            ),
                            boxShadow: [
                              BoxShadow(color: Colors.black.withValues(alpha: 0.02), blurRadius: 8, offset: const Offset(0, 2)),
                            ],
                          ),
                          child: Row(
                            children: [
                              Container(
                                padding: const EdgeInsets.all(10),
                                decoration: BoxDecoration(
                                  color: (isRegistered ? AppColors.primary : AppColors.secondary).withValues(alpha: 0.12),
                                  shape: BoxShape.circle,
                                ),
                                child: Icon(
                                  isRegistered ? Icons.check_circle_rounded : Icons.calendar_today_rounded,
                                  color: isRegistered ? AppColors.primary : AppColors.secondary,
                                  size: 22,
                                ),
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      "${slot['date']} (${slot['session_name'] ?? slot['session']})",
                                      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: AppColors.textPrimary),
                                    ),
                                    const SizedBox(height: 2),
                                    Text(
                                      "ម៉ោង: ${slot['start_time']} - ${slot['end_time']}",
                                      style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
                                    ),
                                    const SizedBox(height: 4),
                                    Text(
                                      "នៅសល់: ${slot['role_remaining'] ?? slot['remaining_spots'] ?? 0} កន្លែង",
                                      style: TextStyle(
                                        fontSize: 11,
                                        fontWeight: FontWeight.w600,
                                        color: isFull ? AppColors.danger : AppColors.success,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                              ElevatedButton(
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: isRegistered
                                      ? AppColors.danger
                                      : (isFull ? Colors.grey.shade400 : AppColors.primary),
                                  foregroundColor: Colors.white,
                                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                                ),
                                onPressed: (isFull && !isRegistered) || isFinalized
                                    ? null
                                    : () => _toggleSlot(slotId),
                                child: Text(isRegistered ? "ដកចេញ" : "ជ្រើសរើស", style: const TextStyle(fontSize: 12)),
                              ),
                            ],
                          ),
                        );
                      }),

                      const SizedBox(height: 20),
                      if (canFinalize && !isFinalized)
                        SizedBox(
                          width: double.infinity,
                          height: 50,
                          child: ElevatedButton(
                            style: ElevatedButton.styleFrom(
                              backgroundColor: AppColors.success,
                              foregroundColor: Colors.white,
                              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                            ),
                            onPressed: _finalizeRegistration,
                            child: const Text("បញ្ជាក់ការជ្រើសរើសជាស្ថាពរ (Finalize)", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
                          ),
                        ),
                    ],
                  ),
                ),
    );
  }
}
