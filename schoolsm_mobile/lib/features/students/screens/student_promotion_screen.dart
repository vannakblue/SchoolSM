import 'package:flutter/material.dart';
import 'package:flutter_spinkit/flutter_spinkit.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/api_constants.dart';
import '../../../core/api/api_client.dart';

class StudentPromotionScreen extends StatefulWidget {
  const StudentPromotionScreen({super.key});

  @override
  State<StudentPromotionScreen> createState() => _StudentPromotionScreenState();
}

class _StudentPromotionScreenState extends State<StudentPromotionScreen> {
  bool _isLoadingMeta = true;
  bool _isLoadingStudents = false;
  bool _isSubmitting = false;

  List<dynamic> _sourceClassrooms = [];
  List<dynamic> _targetYears = [];
  List<dynamic> _targetClassrooms = [];

  int? _selectedSourceClassId;
  int? _selectedTargetYearId;
  int? _selectedGlobalTargetClassId;

  List<dynamic> _students = [];
  final Map<int, String> _actions = {}; // studentId -> 'PROMOTE' or 'RETAIN'

  @override
  void initState() {
    super.initState();
    _fetchMeta();
  }

  Future<void> _fetchMeta() async {
    setState(() => _isLoadingMeta = true);
    try {
      final res = await ApiClient().dio.get(ApiConstants.studentPromotionMeta);
      final data = res.data;
      if (data['status'] == 'success') {
        setState(() {
          _sourceClassrooms = data['source_classrooms'] ?? [];
          _targetYears = data['target_years'] ?? [];
          _targetClassrooms = data['target_classrooms'] ?? [];

          if (_sourceClassrooms.isNotEmpty) _selectedSourceClassId = _sourceClassrooms.first['id'];
          if (_targetYears.isNotEmpty) _selectedTargetYearId = _targetYears.first['id'];
          if (_targetClassrooms.isNotEmpty) _selectedGlobalTargetClassId = _targetClassrooms.first['id'];

          _isLoadingMeta = false;
        });

        if (_selectedSourceClassId != null) {
          _fetchClassStudents();
        }
      } else {
        setState(() => _isLoadingMeta = false);
      }
    } catch (_) {
      setState(() => _isLoadingMeta = false);
    }
  }

  Future<void> _fetchClassStudents() async {
    if (_selectedSourceClassId == null) return;
    setState(() => _isLoadingStudents = true);
    try {
      final res = await ApiClient().dio.get(
        ApiConstants.studentPromotionStudents,
        queryParameters: {'source_class_id': _selectedSourceClassId},
      );
      final data = res.data;
      if (data['status'] == 'success') {
        final list = data['students'] ?? [];
        _actions.clear();
        for (final s in list) {
          _actions[s['id']] = 'PROMOTE';
        }
        setState(() {
          _students = list;
          _isLoadingStudents = false;
        });
      } else {
        setState(() => _isLoadingStudents = false);
      }
    } catch (_) {
      setState(() => _isLoadingStudents = false);
    }
  }

  Future<void> _submitPromotion() async {
    if (_students.isEmpty || _selectedTargetYearId == null) return;

    setState(() => _isSubmitting = true);
    final listPayload = <Map<String, dynamic>>[];

    for (final s in _students) {
      final id = s['id'] as int;
      final action = _actions[id] ?? 'PROMOTE';
      listPayload.add({
        'student_id': id,
        'action': action,
        'target_class_id': action == 'PROMOTE' ? _selectedGlobalTargetClassId : _selectedSourceClassId,
        'standard_reason': action == 'PROMOTE' ? 'PASSED_YEAR' : 'FAILED_YEAR',
        'custom_notes': action == 'PROMOTE' ? 'ឡើងថ្នាក់' : 'ត្រួតថ្នាក់',
      });
    }

    try {
      final res = await ApiClient().dio.post(
        ApiConstants.studentPromotionSubmit,
        data: {
          'source_class_id': _selectedSourceClassId,
          'target_year_id': _selectedTargetYearId,
          'students': listPayload,
        },
      );

      setState(() => _isSubmitting = false);
      if (res.data['status'] == 'success') {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(res.data['message'] ?? 'ជោគជ័យ!'),
              backgroundColor: AppColors.success,
            ),
          );
        }
        _fetchClassStudents();
      }
    } catch (e) {
      setState(() => _isSubmitting = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(ApiClient.getErrorMessage(e)), backgroundColor: AppColors.danger),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bgLight,
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        title: const Text(
          "ឡើងថ្នាក់ & ត្រួតថ្នាក់ (Promotion)",
          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 17, color: AppColors.textPrimary),
        ),
      ),
      body: _isLoadingMeta
          ? const Center(child: SpinKitFadingCircle(color: AppColors.primary, size: 36))
          : Column(
              children: [
                // Config Filters
                Container(
                  color: Colors.white,
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: DropdownButtonFormField<int>(
                              initialValue: _selectedSourceClassId,
                              isExpanded: true,
                              decoration: _dropDeco("ថ្នាក់ដើម (Source Class)"),
                              items: _sourceClassrooms.map<DropdownMenuItem<int>>((c) {
                                return DropdownMenuItem<int>(
                                  value: c['id'],
                                  child: Text(c['name'] ?? '', overflow: TextOverflow.ellipsis),
                                );
                              }).toList(),
                              onChanged: (v) {
                                setState(() => _selectedSourceClassId = v);
                                _fetchClassStudents();
                              },
                            ),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: DropdownButtonFormField<int>(
                              initialValue: _selectedTargetYearId,
                              isExpanded: true,
                              decoration: _dropDeco("ឆ្នាំទៅមុខ (Target Year)"),
                              items: _targetYears.map<DropdownMenuItem<int>>((y) {
                                return DropdownMenuItem<int>(
                                  value: y['id'],
                                  child: Text(y['name'] ?? '', overflow: TextOverflow.ellipsis),
                                );
                              }).toList(),
                              onChanged: (v) => setState(() => _selectedTargetYearId = v),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 10),
                      DropdownButtonFormField<int>(
                        initialValue: _selectedGlobalTargetClassId,
                        isExpanded: true,
                        decoration: _dropDeco("ថ្នាក់គោលដៅសម្រាប់សិស្សឡើងថ្នាក់"),
                        items: _targetClassrooms.map<DropdownMenuItem<int>>((c) {
                          return DropdownMenuItem<int>(
                            value: c['id'],
                            child: Text(c['name'] ?? '', overflow: TextOverflow.ellipsis),
                          );
                        }).toList(),
                        onChanged: (v) => setState(() => _selectedGlobalTargetClassId = v),
                      ),
                    ],
                  ),
                ),

                // Student List
                Expanded(
                  child: _isLoadingStudents
                      ? const Center(child: SpinKitFadingCircle(color: AppColors.primary, size: 36))
                      : _students.isEmpty
                          ? const Center(child: Text("ពុំមានទិន្នន័យសិស្សឡើយ", style: TextStyle(color: AppColors.textSecondary)))
                          : ListView.builder(
                              padding: const EdgeInsets.all(16),
                              itemCount: _students.length,
                              itemBuilder: (ctx, idx) {
                                final s = _students[idx];
                                final id = s['id'] as int;
                                final action = _actions[id] ?? 'PROMOTE';
                                final isPromote = action == 'PROMOTE';

                                return Container(
                                  margin: const EdgeInsets.only(bottom: 10),
                                  padding: const EdgeInsets.all(12),
                                  decoration: BoxDecoration(
                                    color: Colors.white,
                                    borderRadius: BorderRadius.circular(14),
                                    border: Border.all(color: isPromote ? AppColors.success : AppColors.warning, width: 1.2),
                                  ),
                                  child: Row(
                                    children: [
                                      Expanded(
                                        child: Column(
                                          crossAxisAlignment: CrossAxisAlignment.start,
                                          children: [
                                            Text(s['khmer_name'] ?? '', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
                                            Text("ID: ${s['student_id']}", style: const TextStyle(fontSize: 11, color: AppColors.textSecondary)),
                                          ],
                                        ),
                                      ),
                                      Row(
                                        children: [
                                          ChoiceChip(
                                            label: const Text("ឡើងថ្នាក់", style: TextStyle(fontSize: 11)),
                                            selected: isPromote,
                                            selectedColor: AppColors.success.withValues(alpha: 0.2),
                                            onSelected: (_) => setState(() => _actions[id] = 'PROMOTE'),
                                          ),
                                          const SizedBox(width: 6),
                                          ChoiceChip(
                                            label: const Text("ត្រួតថ្នាក់", style: TextStyle(fontSize: 11)),
                                            selected: !isPromote,
                                            selectedColor: AppColors.warning.withValues(alpha: 0.2),
                                            onSelected: (_) => setState(() => _actions[id] = 'RETAIN'),
                                          ),
                                        ],
                                      ),
                                    ],
                                  ),
                                );
                              },
                            ),
                ),

                // Submit Button
                Container(
                  padding: const EdgeInsets.all(16),
                  color: Colors.white,
                  child: SizedBox(
                    width: double.infinity,
                    height: 48,
                    child: ElevatedButton(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.primary,
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                      ),
                      onPressed: _isSubmitting ? null : _submitPromotion,
                      child: _isSubmitting
                          ? const SpinKitThreeBounce(color: Colors.white, size: 22)
                          : const Text("អនុវត្តការឡើងថ្នាក់/ត្រួតថ្នាក់", style: TextStyle(fontWeight: FontWeight.bold)),
                    ),
                  ),
                ),
              ],
            ),
    );
  }

  InputDecoration _dropDeco(String label) {
    return InputDecoration(
      labelText: label,
      labelStyle: const TextStyle(fontSize: 12),
      contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      filled: true,
      fillColor: AppColors.bgLight,
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: AppColors.borderLight)),
    );
  }
}
