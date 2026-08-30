import 'package:flutter/material.dart';
import 'package:flutter_spinkit/flutter_spinkit.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/api_constants.dart';
import '../../../core/api/api_client.dart';

class ExamGradesScreen extends StatefulWidget {
  const ExamGradesScreen({super.key});

  @override
  State<ExamGradesScreen> createState() => _ExamGradesScreenState();
}

class _ExamGradesScreenState extends State<ExamGradesScreen> {
  bool _isLoading = true;
  List<dynamic> _scores = [];
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _fetchGrades();
  }

  Future<void> _fetchGrades() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final res = await ApiClient().dio.get(ApiConstants.grades);
      setState(() {
        _scores = res.data['scores'] ?? [];
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _errorMessage = ApiClient.getErrorMessage(e);
        _isLoading = false;
      });
    }
  }

  Color _getGradeColor(String? letter) {
    switch (letter?.toUpperCase()) {
      case 'A':
        return const Color(0xFF10B981);
      case 'B':
        return const Color(0xFF06B6D4);
      case 'C':
        return const Color(0xFF3B82F6);
      case 'D':
        return const Color(0xFFF59E0B);
      case 'E':
        return const Color(0xFFF97316);
      case 'F':
        return const Color(0xFFEF4444);
      default:
        return AppColors.primary;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bgLight,
      appBar: AppBar(
        title: const Text("លទ្ធផលប្រឡង & ពិន្ទុ", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
        backgroundColor: Colors.white,
        foregroundColor: AppColors.textPrimary,
        elevation: 0,
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _fetchGrades),
        ],
      ),
      body: _isLoading
          ? const Center(child: SpinKitFadingCircle(color: AppColors.primary, size: 40))
          : _errorMessage != null
              ? Center(child: Text(_errorMessage!, style: const TextStyle(color: AppColors.textSecondary)))
              : _scores.isEmpty
                  ? const Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.assessment_outlined, size: 64, color: AppColors.textSecondary),
                          SizedBox(height: 12),
                          Text("មិនទាន់មានកំណត់ត្រាពិន្ទុប្រឡងនៅឡើយទេ", style: TextStyle(color: AppColors.textSecondary)),
                        ],
                      ),
                    )
                  : RefreshIndicator(
                      onRefresh: _fetchGrades,
                      child: ListView.separated(
                        padding: const EdgeInsets.all(16),
                        itemCount: _scores.length,
                        separatorBuilder: (_, __) => const SizedBox(height: 12),
                        itemBuilder: (ctx, index) {
                          final item = _scores[index];
                          final examTitle = item['exam_title'] ?? 'សម័យប្រឡង';
                          final subject = item['subject_name'] ?? 'មុខវិជ្ជា';
                          final score = item['score'] ?? 0;
                          final maxScore = item['max_score'] ?? 100;
                          final letter = item['grade_letter'] ?? '';
                          final color = _getGradeColor(letter);

                          return Container(
                            padding: const EdgeInsets.all(16),
                            decoration: BoxDecoration(
                              color: Colors.white,
                              borderRadius: BorderRadius.circular(16),
                              border: Border.all(color: AppColors.borderLight),
                            ),
                            child: Row(
                              children: [
                                Container(
                                  width: 52,
                                  height: 52,
                                  decoration: BoxDecoration(
                                    color: color.withOpacity(0.12),
                                    borderRadius: BorderRadius.circular(14),
                                    border: Border.all(color: color.withOpacity(0.3)),
                                  ),
                                  child: Center(
                                    child: Text(
                                      letter.isNotEmpty ? letter : "$score",
                                      style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 20),
                                    ),
                                  ),
                                ),
                                const SizedBox(width: 16),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(subject, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                                      const SizedBox(height: 4),
                                      Text(examTitle, style: const TextStyle(fontSize: 12, color: AppColors.textSecondary)),
                                    ],
                                  ),
                                ),
                                Column(
                                  crossAxisAlignment: CrossAxisAlignment.end,
                                  children: [
                                    Text(
                                      "$score",
                                      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18, color: AppColors.textPrimary),
                                    ),
                                    Text(
                                      "/ $maxScore",
                                      style: const TextStyle(fontSize: 11, color: AppColors.textSecondary),
                                    ),
                                  ],
                                ),
                              ],
                            ),
                          );
                        },
                      ),
                    ),
    );
  }
}
