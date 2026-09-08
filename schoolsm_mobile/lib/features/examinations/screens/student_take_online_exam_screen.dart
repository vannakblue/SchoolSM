import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_spinkit/flutter_spinkit.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/api_constants.dart';
import '../../../core/api/api_client.dart';
import 'student_online_exam_result_screen.dart';

class StudentTakeOnlineExamScreen extends StatefulWidget {
  final int examId;
  final String? accessCode;

  const StudentTakeOnlineExamScreen({
    super.key,
    required this.examId,
    this.accessCode,
  });

  @override
  State<StudentTakeOnlineExamScreen> createState() => _StudentTakeOnlineExamScreenState();
}

class _StudentTakeOnlineExamScreenState extends State<StudentTakeOnlineExamScreen> {
  bool _isLoading = true;
  bool _isSubmitting = false;
  String? _errorMessage;

  int? _submissionId;
  String _examTitle = "វិញ្ញាសាប្រឡង";
  String _subjectName = "";
  int _remainingSeconds = 0;
  Timer? _countdownTimer;
  DateTime? _examStartTime;

  List<dynamic> _questions = [];
  int _currentIndex = 0;
  final Map<int, int> _answers = {}; // question_id -> option_id

  @override
  void initState() {
    super.initState();
    _examStartTime = DateTime.now();
    _fetchExamSession();
  }

  @override
  void dispose() {
    _countdownTimer?.cancel();
    super.dispose();
  }

  Future<void> _fetchExamSession() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final res = await ApiClient().dio.post(
        ApiConstants.onlineExamTake(widget.examId),
        data: {'access_code': widget.accessCode ?? ''},
      );

      final data = res.data;
      if (data != null && data['status'] == 'success') {
        _submissionId = data['submission_id'];
        _examTitle = data['exam_title'] ?? 'វិញ្ញាសាប្រឡង';
        _subjectName = data['subject_name'] ?? '';
        _remainingSeconds = (data['remaining_seconds'] as num?)?.toInt() ?? 0;
        _questions = data['questions'] ?? [];

        // Load pre-saved answers if student is resuming
        for (var q in _questions) {
          final qId = q['id'];
          final savedOpt = q['saved_option_id'];
          if (savedOpt != null && qId != null) {
            _answers[qId] = savedOpt;
          }
        }

        _startCountdown();

        if (mounted) {
          setState(() {
            _isLoading = false;
          });
        }
      } else {
        if (mounted) {
          setState(() {
            _isLoading = false;
            _errorMessage = data?['message'] ?? 'មិនអាចចាប់ផ្តើមការប្រឡងបានទេ!';
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

  void _startCountdown() {
    _countdownTimer?.cancel();
    _countdownTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (!mounted) {
        timer.cancel();
        return;
      }
      if (_remainingSeconds <= 1) {
        timer.cancel();
        setState(() => _remainingSeconds = 0);
        _handleTimeExpired();
      } else {
        setState(() {
          _remainingSeconds--;
        });
      }
    });
  }

  void _handleTimeExpired() {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text("⏰ អស់ម៉ោងប្រឡងហើយ! ប្រព័ន្ធកំពុងប្រគល់កិច្ចការដោយស្វ័យប្រវត្តិ..."),
        backgroundColor: AppColors.danger,
        duration: Duration(seconds: 3),
      ),
    );
    _submitExam(isAutoSubmit: true);
  }

  String _formatDuration(int seconds) {
    final m = seconds ~/ 60;
    final s = seconds % 60;
    final mStr = m.toString().padLeft(2, '0');
    final sStr = s.toString().padLeft(2, '0');
    return "$mStr:$sStr";
  }

  Future<void> _submitExam({bool isAutoSubmit = false}) async {
    if (_isSubmitting || _submissionId == null) return;

    setState(() => _isSubmitting = true);
    _countdownTimer?.cancel();

    final timeSpent = _examStartTime != null
        ? DateTime.now().difference(_examStartTime!).inSeconds
        : 0;

    // Convert map keys to string
    final Map<String, dynamic> answersPayload = {};
    _answers.forEach((qId, optId) {
      answersPayload[qId.toString()] = optId;
    });

    try {
      final res = await ApiClient().dio.post(
        ApiConstants.onlineExamSubmit(widget.examId),
        data: {
          'submission_id': _submissionId,
          'answers': answersPayload,
          'time_spent_seconds': timeSpent,
        },
      );

      final data = res.data;
      if (data != null && data['status'] == 'success') {
        if (!mounted) return;
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(
            builder: (_) => StudentOnlineExamResultScreen(
              submissionId: _submissionId!,
              initialResult: data,
            ),
          ),
        );
      } else {
        if (!mounted) return;
        setState(() => _isSubmitting = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(data?['message'] ?? 'មានបញ្ហាក្នុងការប្រគល់កិច្ចការ!'),
            backgroundColor: AppColors.danger,
          ),
        );
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _isSubmitting = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(ApiClient.getErrorMessage(e)),
          backgroundColor: AppColors.danger,
        ),
      );
    }
  }

  void _showSubmitConfirmation() {
    final answeredCount = _answers.length;
    final totalCount = _questions.length;
    final unansweredCount = totalCount - answeredCount;

    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (ctx) {
        return Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: Colors.grey.shade300,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              const SizedBox(height: 18),
              const Icon(Icons.assignment_turned_in_rounded, size: 48, color: AppColors.primary),
              const SizedBox(height: 12),
              const Text(
                "បញ្ជាក់ការប្រគល់កិច្ចការ",
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
              ),
              const SizedBox(height: 8),
              Text(
                "តើអ្នកពិតជាចង់ប្រគល់វិញ្ញាសានេះមែនទេ? លទ្ធផលពិន្ទុនឹងត្រូវបានគណនាភ្លាមៗ។",
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 13, color: Colors.grey.shade600),
              ),
              const SizedBox(height: 16),

              // Status Summary Box
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: AppColors.bgLight,
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(color: AppColors.borderLight),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceAround,
                  children: [
                    Column(
                      children: [
                        const Text("ឆ្លើយរួច", style: TextStyle(fontSize: 12, color: AppColors.textSecondary)),
                        const SizedBox(height: 4),
                        Text(
                          "$answeredCount / $totalCount",
                          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFF10B981)),
                        ),
                      ],
                    ),
                    Container(height: 30, width: 1, color: AppColors.borderLight),
                    Column(
                      children: [
                        const Text("នៅសល់", style: TextStyle(fontSize: 12, color: AppColors.textSecondary)),
                        const SizedBox(height: 4),
                        Text(
                          "$unansweredCount",
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                            color: unansweredCount > 0 ? const Color(0xFFEF4444) : Colors.grey,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              if (unansweredCount > 0) ...[
                const SizedBox(height: 10),
                Text(
                  "⚠️ អ្នកនៅសល់សំណួរចំនួន $unansweredCount មិនទាន់បានឆ្លើយនៅឡើយ!",
                  style: const TextStyle(fontSize: 12, color: Color(0xFFB91C1C), fontWeight: FontWeight.w600),
                ),
              ],
              const SizedBox(height: 20),

              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () => Navigator.pop(ctx),
                      style: OutlinedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      ),
                      child: const Text("ពិនិត្យឡើងវិញ", style: TextStyle(fontWeight: FontWeight.bold)),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: () {
                        Navigator.pop(ctx);
                        _submitExam();
                      },
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.primary,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                        elevation: 0,
                      ),
                      child: const Text("ប្រគល់កិច្ចការ", style: TextStyle(fontWeight: FontWeight.bold)),
                    ),
                  ),
                ],
              ),
            ],
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Scaffold(
        backgroundColor: AppColors.bgLight,
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              SpinKitFadingCircle(color: AppColors.primary, size: 42),
              SizedBox(height: 16),
              Text(
                "កំពុងរៀបចំក្រដាសវិញ្ញាសា...",
                style: TextStyle(fontSize: 14, color: AppColors.textSecondary),
              ),
            ],
          ),
        ),
      );
    }

    if (_errorMessage != null) {
      return Scaffold(
        backgroundColor: AppColors.bgLight,
        appBar: AppBar(backgroundColor: Colors.white, elevation: 0),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.error_outline_rounded, size: 48, color: AppColors.danger),
                const SizedBox(height: 14),
                Text(
                  _errorMessage!,
                  textAlign: TextAlign.center,
                  style: const TextStyle(fontSize: 14.5, color: AppColors.textSecondary),
                ),
                const SizedBox(height: 18),
                ElevatedButton(
                  onPressed: () => Navigator.pop(context),
                  style: ElevatedButton.styleFrom(backgroundColor: AppColors.primary, foregroundColor: Colors.white),
                  child: const Text("ត្រឡប់ក្រោយ"),
                ),
              ],
            ),
          ),
        ),
      );
    }

    if (_questions.isEmpty) {
      return Scaffold(
        appBar: AppBar(title: Text(_examTitle)),
        body: const Center(child: Text("វិញ្ញាសានេះមិនទាន់មានសំណួរនៅឡើយទេ។")),
      );
    }

    final isTimeLow = _remainingSeconds < 300; // < 5 minutes
    final isTimeCritical = _remainingSeconds < 60; // < 1 minute
    final currentQ = _questions[_currentIndex];
    final currentQId = currentQ['id'];
    final options = currentQ['options'] as List<dynamic>? ?? [];
    final selectedOptionId = _answers[currentQId];

    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, result) {
        if (!didPop) {
          _showSubmitConfirmation();
        }
      },
      child: Scaffold(
        backgroundColor: AppColors.bgLight,
        appBar: AppBar(
          backgroundColor: Colors.white,
          elevation: 0.5,
          automaticallyImplyLeading: false,
          title: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      _examTitle,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 14.5, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
                    ),
                    if (_subjectName.isNotEmpty)
                      Text(
                        _subjectName,
                        style: const TextStyle(fontSize: 11.5, color: AppColors.textSecondary),
                      ),
                  ],
                ),
              ),
              const SizedBox(width: 8),

              // Live Timer Pill
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                decoration: BoxDecoration(
                  color: isTimeCritical
                      ? const Color(0xFFEF4444).withValues(alpha: 0.12)
                      : (isTimeLow ? const Color(0xFFF59E0B).withValues(alpha: 0.12) : AppColors.primary.withValues(alpha: 0.08)),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(
                    color: isTimeCritical ? const Color(0xFFEF4444) : (isTimeLow ? const Color(0xFFF59E0B) : AppColors.primary),
                    width: 1.2,
                  ),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      Icons.timer_outlined,
                      size: 16,
                      color: isTimeCritical ? const Color(0xFFEF4444) : (isTimeLow ? const Color(0xFFF59E0B) : AppColors.primary),
                    ),
                    const SizedBox(width: 4),
                    Text(
                      _formatDuration(_remainingSeconds),
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.bold,
                        color: isTimeCritical ? const Color(0xFFEF4444) : (isTimeLow ? const Color(0xFFB45309) : AppColors.primary),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: _isSubmitting ? null : _showSubmitConfirmation,
              child: _isSubmitting
                  ? const SpinKitRing(color: AppColors.primary, size: 18, lineWidth: 2)
                  : const Text(
                      "ប្រគល់",
                      style: TextStyle(fontWeight: FontWeight.bold, color: AppColors.primary, fontSize: 13),
                    ),
            ),
          ],
        ),
        body: Column(
          children: [
            // ---------------------------------------------------------
            // 1. QUESTION PALETTE NAVIGATOR
            // ---------------------------------------------------------
            Container(
              color: Colors.white,
              padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 12),
              child: SizedBox(
                height: 38,
                child: ListView.separated(
                  scrollDirection: Axis.horizontal,
                  itemCount: _questions.length,
                  separatorBuilder: (_, __) => const SizedBox(width: 8),
                  itemBuilder: (context, idx) {
                    final q = _questions[idx];
                    final isCurrent = idx == _currentIndex;
                    final isAnswered = _answers.containsKey(q['id']);

                    Color bg = Colors.grey.shade100;
                    Color textCol = AppColors.textSecondary;
                    Border? border;

                    if (isAnswered) {
                      bg = AppColors.primary.withValues(alpha: 0.15);
                      textCol = AppColors.primary;
                    }
                    if (isCurrent) {
                      border = Border.all(color: AppColors.primary, width: 2);
                      bg = AppColors.primary;
                      textCol = Colors.white;
                    }

                    return InkWell(
                      onTap: () => setState(() => _currentIndex = idx),
                      borderRadius: BorderRadius.circular(19),
                      child: Container(
                        width: 38,
                        height: 38,
                        decoration: BoxDecoration(
                          color: bg,
                          shape: BoxShape.circle,
                          border: border,
                        ),
                        alignment: Alignment.center,
                        child: Text(
                          "${idx + 1}",
                          style: TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.bold,
                            color: textCol,
                          ),
                        ),
                      ),
                    );
                  },
                ),
              ),
            ),
            const Divider(height: 1, thickness: 1, color: AppColors.borderLight),

            // ---------------------------------------------------------
            // 2. QUESTION CARD & OPTIONS BODY
            // ---------------------------------------------------------
            Expanded(
              child: SingleChildScrollView(
                physics: const BouncingScrollPhysics(),
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Question Number and Points Header
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          "សំណួរទី ${_currentIndex + 1} នៃ ${_questions.length}",
                          style: const TextStyle(
                            fontSize: 13.5,
                            fontWeight: FontWeight.bold,
                            color: AppColors.textSecondary,
                          ),
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                          decoration: BoxDecoration(
                            color: AppColors.primary.withValues(alpha: 0.08),
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: Text(
                            "${(currentQ['points'] as num?)?.toDouble() ?? 0} ពិន្ទុ",
                            style: const TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.bold,
                              color: AppColors.primary,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),

                    // Question Text Card
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(18),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(18),
                        border: Border.all(color: AppColors.borderLight),
                        boxShadow: [
                          BoxShadow(
                            color: Colors.black.withValues(alpha: 0.02),
                            blurRadius: 10,
                            offset: const Offset(0, 3),
                          ),
                        ],
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            currentQ['question_text'] ?? '',
                            style: const TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.w600,
                              color: AppColors.textPrimary,
                              height: 1.45,
                            ),
                          ),
                          if (currentQ['image_url'] != null) ...[
                            const SizedBox(height: 12),
                            ClipRRect(
                              borderRadius: BorderRadius.circular(12),
                              child: Image.network(
                                currentQ['image_url'],
                                fit: BoxFit.contain,
                                errorBuilder: (_, __, ___) => const SizedBox.shrink(),
                              ),
                            ),
                          ],
                        ],
                      ),
                    ),
                    const SizedBox(height: 20),

                    // Options Label
                    const Text(
                      "ជម្រើសចម្លើយ (សូមជ្រើសរើសមួយ)៖",
                      style: TextStyle(
                        fontSize: 13.5,
                        fontWeight: FontWeight.bold,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 10),

                    // Options List
                    ...options.asMap().entries.map((entry) {
                      final optIdx = entry.key;
                      final opt = entry.value;
                      final optId = opt['id'];
                      final optText = opt['option_text'] ?? '';
                      final isSelected = (selectedOptionId == optId);
                      final optionLetters = ['A', 'B', 'C', 'D', 'E', 'F'];
                      final letter = optIdx < optionLetters.length ? optionLetters[optIdx] : '${optIdx + 1}';

                      return InkWell(
                        onTap: () {
                          setState(() {
                            _answers[currentQId] = optId;
                          });
                        },
                        borderRadius: BorderRadius.circular(14),
                        child: AnimatedContainer(
                          duration: const Duration(milliseconds: 180),
                          margin: const EdgeInsets.only(bottom: 10),
                          padding: const EdgeInsets.all(14),
                          decoration: BoxDecoration(
                            color: isSelected ? AppColors.primary.withValues(alpha: 0.08) : Colors.white,
                            borderRadius: BorderRadius.circular(14),
                            border: Border.all(
                              color: isSelected ? AppColors.primary : AppColors.borderLight,
                              width: isSelected ? 2 : 1,
                            ),
                          ),
                          child: Row(
                            children: [
                              Container(
                                width: 34,
                                height: 34,
                                decoration: BoxDecoration(
                                  color: isSelected ? AppColors.primary : Colors.grey.shade100,
                                  shape: BoxShape.circle,
                                ),
                                alignment: Alignment.center,
                                child: Text(
                                  letter,
                                  style: TextStyle(
                                    fontSize: 13.5,
                                    fontWeight: FontWeight.bold,
                                    color: isSelected ? Colors.white : AppColors.textPrimary,
                                  ),
                                ),
                              ),
                              const SizedBox(width: 14),
                              Expanded(
                                child: Text(
                                  optText,
                                  style: TextStyle(
                                    fontSize: 14.5,
                                    fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                                    color: isSelected ? AppColors.primary : AppColors.textPrimary,
                                  ),
                                ),
                              ),
                              if (isSelected)
                                const Icon(Icons.check_circle_rounded, color: AppColors.primary, size: 22),
                            ],
                          ),
                        ),
                      );
                    }),
                    const SizedBox(height: 20),
                  ],
                ),
              ),
            ),

            // ---------------------------------------------------------
            // 3. BOTTOM FOOTER NAVIGATION
            // ---------------------------------------------------------
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: BoxDecoration(
                color: Colors.white,
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.05),
                    blurRadius: 10,
                    offset: const Offset(0, -3),
                  ),
                ],
              ),
              child: Row(
                children: [
                  // Previous Button
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: _currentIndex > 0
                          ? () => setState(() => _currentIndex--)
                          : null,
                      icon: const Icon(Icons.arrow_back_ios_rounded, size: 14),
                      label: const Text("សំណួរមុន", style: TextStyle(fontWeight: FontWeight.bold)),
                      style: OutlinedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(vertical: 12),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),

                  // Next or Submit Button
                  Expanded(
                    child: _currentIndex < _questions.length - 1
                        ? ElevatedButton.icon(
                            onPressed: () => setState(() => _currentIndex++),
                            icon: const Icon(Icons.arrow_forward_ios_rounded, size: 14),
                            label: const Text("សំណួរបន្ទាប់", style: TextStyle(fontWeight: FontWeight.bold)),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: AppColors.primary,
                              foregroundColor: Colors.white,
                              padding: const EdgeInsets.symmetric(vertical: 12),
                              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                              elevation: 0,
                            ),
                          )
                        : ElevatedButton.icon(
                            onPressed: _isSubmitting ? null : _showSubmitConfirmation,
                            icon: const Icon(Icons.check_rounded, size: 18),
                            label: const Text("ប្រគល់កិច្ចការ", style: TextStyle(fontWeight: FontWeight.bold)),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: const Color(0xFF10B981),
                              foregroundColor: Colors.white,
                              padding: const EdgeInsets.symmetric(vertical: 12),
                              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                              elevation: 0,
                            ),
                          ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
