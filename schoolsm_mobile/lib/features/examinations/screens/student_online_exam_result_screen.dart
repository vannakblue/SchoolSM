import 'package:flutter/material.dart';
import 'package:flutter_spinkit/flutter_spinkit.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/api_constants.dart';
import '../../../core/api/api_client.dart';

class StudentOnlineExamResultScreen extends StatefulWidget {
  final int submissionId;
  final Map<String, dynamic>? initialResult;

  const StudentOnlineExamResultScreen({
    super.key,
    required this.submissionId,
    this.initialResult,
  });

  @override
  State<StudentOnlineExamResultScreen> createState() => _StudentOnlineExamResultScreenState();
}

class _StudentOnlineExamResultScreenState extends State<StudentOnlineExamResultScreen> {
  bool _isLoading = true;
  String? _errorMessage;
  Map<String, dynamic>? _submissionData;

  @override
  void initState() {
    super.initState();
    if (widget.initialResult != null) {
      _submissionData = widget.initialResult;
      _isLoading = false;
      // Fetch full details in background if questions_review is missing
      if (_submissionData?['questions_review'] == null) {
        _fetchFullResult();
      }
    } else {
      _fetchFullResult();
    }
  }

  Future<void> _fetchFullResult() async {
    try {
      final res = await ApiClient().dio.get(ApiConstants.onlineExamResult(widget.submissionId));
      if (res.data != null && res.data['status'] == 'success') {
        if (mounted) {
          setState(() {
            _submissionData = res.data['submission'];
            _isLoading = false;
            _errorMessage = null;
          });
        }
      } else {
        if (mounted) {
          setState(() {
            _isLoading = false;
            _errorMessage = res.data?['message'] ?? 'មិនអាចទាញយកលទ្ធផលបានទេ!';
          });
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isLoading = false;
          _errorMessage = ApiClient.getErrorMessage(e);
        });
      }
    }
  }

  Color _getGradeColor(String grade) {
    switch (grade.toUpperCase()) {
      case 'A':
        return const Color(0xFF10B981);
      case 'B':
        return const Color(0xFF3B82F6);
      case 'C':
        return const Color(0xFF6366F1);
      case 'D':
        return const Color(0xFFF59E0B);
      case 'E':
        return const Color(0xFFF97316);
      default:
        return const Color(0xFFEF4444);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bgLight,
      appBar: AppBar(
        title: const Text(
          "លទ្ធផលប្រឡងអនឡាញ",
          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 17, color: AppColors.textPrimary),
        ),
        backgroundColor: Colors.white,
        elevation: 0.5,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 20, color: AppColors.textPrimary),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: _isLoading
          ? const Center(child: SpinKitFadingCircle(color: AppColors.primary, size: 40))
          : _errorMessage != null
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Icon(Icons.error_outline_rounded, size: 48, color: AppColors.danger),
                        const SizedBox(height: 12),
                        Text(
                          _errorMessage!,
                          textAlign: TextAlign.center,
                          style: const TextStyle(fontSize: 14, color: AppColors.textSecondary),
                        ),
                        const SizedBox(height: 16),
                        ElevatedButton.icon(
                          onPressed: () {
                            setState(() => _isLoading = true);
                            _fetchFullResult();
                          },
                          icon: const Icon(Icons.refresh_rounded, size: 18),
                          label: const Text("ព្យាយាមម្តងទៀត"),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: AppColors.primary,
                            foregroundColor: Colors.white,
                          ),
                        ),
                      ],
                    ),
                  ),
                )
              : _buildResultBody(),
    );
  }

  Widget _buildResultBody() {
    final sub = _submissionData ?? {};
    final examTitle = sub['exam_title'] ?? 'វិញ្ញាសាប្រឡង';
    final subjectName = sub['subject_name'] ?? '';
    final scoreObtained = (sub['score_obtained'] as num?)?.toDouble() ?? 0.0;
    final totalScore = (sub['total_possible_score'] as num?)?.toDouble() ?? 100.0;
    final percentage = (sub['percentage'] as num?)?.toDouble() ?? 0.0;
    final letterGrade = sub['letter_grade'] ?? '-';
    final isPassed = sub['is_passed'] == true;
    final mentionKhmer = sub['mention_khmer'] ?? '';
    final formattedTime = sub['formatted_time_spent'] ?? '';
    final passScore = (sub['pass_score'] as num?)?.toDouble() ?? 50.0;
    final questionsReview = sub['questions_review'] as List<dynamic>? ?? [];

    return SingleChildScrollView(
      physics: const BouncingScrollPhysics(),
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // -------------------------------------------------------------
          // 1. HERO RESULT CARD
          // -------------------------------------------------------------
          Container(
            width: double.infinity,
            decoration: BoxDecoration(
              gradient: isPassed
                  ? const LinearGradient(
                      colors: [Color(0xFF065F46), Color(0xFF059669), Color(0xFF10B981)],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    )
                  : const LinearGradient(
                      colors: [Color(0xFF881337), Color(0xFFBE123C), Color(0xFFE11D48)],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
              borderRadius: BorderRadius.circular(24),
              boxShadow: [
                BoxShadow(
                  color: (isPassed ? const Color(0xFF059669) : const Color(0xFFBE123C)).withValues(alpha: 0.35),
                  blurRadius: 20,
                  offset: const Offset(0, 10),
                ),
              ],
            ),
            padding: const EdgeInsets.all(22),
            child: Column(
              children: [
                // Status Icon & Message
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(
                      isPassed ? Icons.check_circle_rounded : Icons.cancel_rounded,
                      color: Colors.white,
                      size: 28,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      isPassed ? "🎉 អបអរសាទរ! ប្រឡងជាប់" : "⚠️ ប្រឡងមិនទាន់ជាប់",
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                Text(
                  isPassed
                      ? "អ្នកបានបំពេញលក្ខខណ្ឌជាប់ការប្រឡងតេស្តនេះ!"
                      : "ពិន្ទុរបស់អ្នកមិនទាន់គ្រប់តាមពិន្ទុជាប់គោល ($passScore) នៅឡើយទេ។",
                  textAlign: TextAlign.center,
                  style: TextStyle(color: Colors.white.withValues(alpha: 0.9), fontSize: 12.5),
                ),
                const SizedBox(height: 20),

                // Score Gauge Centerpiece
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: Colors.white.withValues(alpha: 0.3)),
                  ),
                  child: Column(
                    children: [
                      Text(
                        "${scoreObtained.toStringAsFixed(scoreObtained.truncateToDouble() == scoreObtained ? 0 : 2)} / ${totalScore.toStringAsFixed(0)}",
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 34,
                          fontWeight: FontWeight.w900,
                          letterSpacing: 1,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                            decoration: BoxDecoration(
                              color: Colors.white,
                              borderRadius: BorderRadius.circular(10),
                            ),
                            child: Text(
                              "និទ្ទេស $letterGrade",
                              style: TextStyle(
                                color: _getGradeColor(letterGrade),
                                fontWeight: FontWeight.bold,
                                fontSize: 13,
                              ),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Text(
                            "${percentage.toStringAsFixed(1)}% ($mentionKhmer)",
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 13,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),

                // Meta Info Pills
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceAround,
                  children: [
                    _buildMetaPill(Icons.timer_outlined, "រយៈពេលចំណាយ", formattedTime.isNotEmpty ? formattedTime : "មិនបានកត់ត្រា"),
                    _buildMetaPill(Icons.menu_book_rounded, "មុខវិជ្ជា", subjectName),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),

          // Exam Info Card
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: AppColors.borderLight),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  "ព័ត៌មានវិញ្ញាសា",
                  style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
                ),
                const SizedBox(height: 8),
                Text(
                  examTitle,
                  style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: AppColors.primary),
                ),
                if (sub['exam_term_name'] != null) ...[
                  const SizedBox(height: 4),
                  Text(
                    "សម័យប្រឡង៖ ${sub['exam_term_name']}",
                    style: const TextStyle(fontSize: 12.5, color: AppColors.textSecondary),
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(height: 24),

          // -------------------------------------------------------------
          // 2. DETAILED QUESTION REVIEW
          // -------------------------------------------------------------
          if (questionsReview.isNotEmpty) ...[
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  "ត្រួតពិនិត្យចម្លើយលម្អិត",
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                  decoration: BoxDecoration(
                    color: AppColors.primary.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    "${questionsReview.length} សំណួរ",
                    style: const TextStyle(color: AppColors.primary, fontWeight: FontWeight.bold, fontSize: 12),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),

            ListView.separated(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: questionsReview.length,
              separatorBuilder: (_, __) => const SizedBox(height: 14),
              itemBuilder: (context, index) {
                return _buildQuestionReviewCard(index + 1, questionsReview[index]);
              },
            ),
            const SizedBox(height: 24),
          ],

          // Return Button
          SizedBox(
            width: double.infinity,
            height: 50,
            child: ElevatedButton.icon(
              onPressed: () => Navigator.pop(context),
              icon: const Icon(Icons.arrow_back_rounded, size: 20),
              label: const Text(
                "ត្រឡប់ទៅបញ្ជីវិញ្ញាសា",
                style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
              ),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.primary,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                elevation: 2,
              ),
            ),
          ),
          const SizedBox(height: 20),
        ],
      ),
    );
  }

  Widget _buildMetaPill(IconData icon, String label, String value) {
    return Column(
      children: [
        Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 14, color: Colors.white.withValues(alpha: 0.8)),
            const SizedBox(width: 4),
            Text(
              label,
              style: TextStyle(fontSize: 11, color: Colors.white.withValues(alpha: 0.8)),
            ),
          ],
        ),
        const SizedBox(height: 2),
        Text(
          value,
          style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.bold, color: Colors.white),
        ),
      ],
    );
  }

  Widget _buildQuestionReviewCard(int questionNum, Map<String, dynamic> q) {
    final questionText = q['question_text'] ?? '';
    final isCorrect = q['is_correct'] == true;
    final hasAnswered = q['has_answered'] == true;
    final pointsAwarded = (q['points_awarded'] as num?)?.toDouble() ?? 0.0;
    final points = (q['points'] as num?)?.toDouble() ?? 0.0;
    final explanation = q['explanation'] ?? '';
    final options = q['options'] as List<dynamic>? ?? [];

    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(
          color: isCorrect ? const Color(0xFF10B981).withValues(alpha: 0.4) : const Color(0xFFEF4444).withValues(alpha: 0.4),
          width: 1.5,
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.03),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header: Question # and Badge
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                "សំណួរទី $questionNum",
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: AppColors.textSecondary),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                decoration: BoxDecoration(
                  color: isCorrect
                      ? const Color(0xFF10B981).withValues(alpha: 0.12)
                      : const Color(0xFFEF4444).withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      isCorrect ? Icons.check_circle_rounded : (hasAnswered ? Icons.cancel_rounded : Icons.help_outline_rounded),
                      color: isCorrect ? const Color(0xFF10B981) : const Color(0xFFEF4444),
                      size: 14,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      isCorrect
                          ? "+$pointsAwarded ពិន្ទុ"
                          : (hasAnswered ? "ខុស (0/$points)" : "មិនបានឆ្លើយ"),
                      style: TextStyle(
                        color: isCorrect ? const Color(0xFF047857) : const Color(0xFFB91C1C),
                        fontWeight: FontWeight.bold,
                        fontSize: 11.5,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),

          // Question Text
          Text(
            questionText,
            style: const TextStyle(
              fontSize: 14.5,
              fontWeight: FontWeight.bold,
              color: AppColors.textPrimary,
              height: 1.4,
            ),
          ),
          const SizedBox(height: 14),

          // Options List
          ...options.map((opt) {
            final optText = opt['option_text'] ?? '';
            final optIsCorrect = opt['is_correct'] == true;
            final optIsSelected = opt['is_selected'] == true;

            Color borderColor = AppColors.borderLight;
            Color bgColor = Colors.white;
            Widget? trailingIcon;

            if (optIsSelected && optIsCorrect) {
              borderColor = const Color(0xFF10B981);
              bgColor = const Color(0xFF10B981).withValues(alpha: 0.08);
              trailingIcon = const Icon(Icons.check_circle_rounded, color: Color(0xFF10B981), size: 18);
            } else if (optIsSelected && !optIsCorrect) {
              borderColor = const Color(0xFFEF4444);
              bgColor = const Color(0xFFEF4444).withValues(alpha: 0.08);
              trailingIcon = const Icon(Icons.cancel_rounded, color: Color(0xFFEF4444), size: 18);
            } else if (optIsCorrect) {
              borderColor = const Color(0xFF10B981);
              bgColor = const Color(0xFF10B981).withValues(alpha: 0.05);
              trailingIcon = Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: const Color(0xFF10B981).withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: const Text(
                  "ចម្លើយត្រូវ",
                  style: TextStyle(color: Color(0xFF047857), fontSize: 10.5, fontWeight: FontWeight.bold),
                ),
              );
            }

            return Container(
              margin: const EdgeInsets.only(bottom: 8),
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: BoxDecoration(
                color: bgColor,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: borderColor, width: optIsSelected || optIsCorrect ? 1.5 : 1),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      optText,
                      style: TextStyle(
                        fontSize: 13.5,
                        fontWeight: optIsSelected || optIsCorrect ? FontWeight.w600 : FontWeight.normal,
                        color: optIsSelected && !optIsCorrect
                            ? const Color(0xFFB91C1C)
                            : (optIsCorrect ? const Color(0xFF047857) : AppColors.textPrimary),
                      ),
                    ),
                  ),
                  if (trailingIcon != null) ...[
                    const SizedBox(width: 8),
                    trailingIcon,
                  ],
                ],
              ),
            );
          }),

          // Teacher Explanation Box
          if (explanation.toString().trim().isNotEmpty) ...[
            const SizedBox(height: 8),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFFEFF6FF),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: const Color(0xFFBFDBFE)),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.lightbulb_outline_rounded, color: Color(0xFF2563EB), size: 18),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          "ការពន្យល់ពីលោកគ្រូ-អ្នកគ្រូ៖",
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.bold,
                            color: Color(0xFF1E40AF),
                          ),
                        ),
                        const SizedBox(height: 3),
                        Text(
                          explanation,
                          style: const TextStyle(fontSize: 12.5, color: Color(0xFF1E3A8A), height: 1.35),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}
