import 'package:flutter/material.dart';
import 'package:flutter_spinkit/flutter_spinkit.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/api_constants.dart';
import '../../../core/api/api_client.dart';
import 'student_take_online_exam_screen.dart';
import 'student_online_exam_result_screen.dart';

class StudentOnlineExamListScreen extends StatefulWidget {
  const StudentOnlineExamListScreen({super.key});

  @override
  State<StudentOnlineExamListScreen> createState() => _StudentOnlineExamListScreenState();
}

class _StudentOnlineExamListScreenState extends State<StudentOnlineExamListScreen> {
  bool _isLoading = true;
  String? _errorMessage;
  String _studentName = "";
  String _classroomName = "";
  List<dynamic> _allExams = [];
  int _selectedTabIndex = 0; // 0: All, 1: Available, 2: Completed

  @override
  void initState() {
    super.initState();
    _fetchExams();
  }

  Future<void> _fetchExams() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final res = await ApiClient().dio.get(ApiConstants.onlineExamsList);
      final data = res.data;
      if (data != null && data['status'] == 'success') {
        if (mounted) {
          setState(() {
            _studentName = data['student_name'] ?? '';
            _classroomName = data['classroom_name'] ?? '';
            _allExams = data['exams'] ?? [];
            _isLoading = false;
          });
        }
      } else {
        if (mounted) {
          setState(() {
            _isLoading = false;
            _errorMessage = data?['message'] ?? 'មិនអាចទាញយកបញ្ជីវិញ្ញាសាបានទេ!';
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

  List<dynamic> get _filteredExams {
    if (_selectedTabIndex == 1) {
      // Available / Can take
      return _allExams.where((e) => e['can_take'] == true).toList();
    } else if (_selectedTabIndex == 2) {
      // Completed / Has submitted
      return _allExams.where((e) => e['latest_submission'] != null).toList();
    }
    return _allExams;
  }

  void _handleStartExam(Map<String, dynamic> exam) {
    final requiresPin = exam['requires_access_code'] == true;
    final examId = exam['id'] as int;

    if (requiresPin) {
      _showPinDialog(examId, exam['title'] ?? 'វិញ្ញាសា');
    } else {
      _navigateToExam(examId, null);
    }
  }

  void _showPinDialog(int examId, String title) {
    final pinController = TextEditingController();
    showDialog(
      context: context,
      builder: (ctx) {
        return AlertDialog(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
          title: const Row(
            children: [
              Icon(Icons.lock_rounded, color: AppColors.primary, size: 22),
              SizedBox(width: 8),
              Text(
                "លេខកូដសម្ងាត់ (PIN)",
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
              ),
            ],
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                "វិញ្ញាសានេះទាមទារលេខកូដសម្ងាត់ (PIN) ដើម្បីចាប់ផ្តើមប្រឡង៖",
                style: TextStyle(fontSize: 13, color: Colors.grey.shade700),
              ),
              const SizedBox(height: 14),
              TextField(
                controller: pinController,
                autofocus: true,
                keyboardType: TextInputType.text,
                decoration: InputDecoration(
                  hintText: "បញ្ចូលលេខកូដ PIN...",
                  prefixIcon: const Icon(Icons.key_rounded, size: 20),
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                  contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                ),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text("បោះបង់", style: TextStyle(color: Colors.grey)),
            ),
            ElevatedButton(
              onPressed: () {
                final pin = pinController.text.trim();
                if (pin.isEmpty) return;
                Navigator.pop(ctx);
                _navigateToExam(examId, pin);
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.primary,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
              ),
              child: const Text("ចូលប្រឡង"),
            ),
          ],
        );
      },
    );
  }

  void _navigateToExam(int examId, String? pin) async {
    await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => StudentTakeOnlineExamScreen(
          examId: examId,
          accessCode: pin,
        ),
      ),
    );
    // Refresh after returning from exam
    _fetchExams();
  }

  @override
  Widget build(BuildContext context) {
    final filtered = _filteredExams;

    return Scaffold(
      backgroundColor: AppColors.bgLight,
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0.5,
        title: const Text(
          "វិញ្ញាសា & ប្រឡងអនឡាញ",
          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 17, color: AppColors.textPrimary),
        ),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 20, color: AppColors.textPrimary),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: RefreshIndicator(
        onRefresh: _fetchExams,
        color: AppColors.primary,
        child: Column(
          children: [
            // ---------------------------------------------------------
            // 1. STUDENT INFO BANNER
            // ---------------------------------------------------------
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [Color(0xFF312E81), Color(0xFF4338CA), Color(0xFF4F46E5)],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                boxShadow: [
                  BoxShadow(
                    color: const Color(0xFF312E81).withValues(alpha: 0.25),
                    blurRadius: 10,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: Row(
                children: [
                  Container(
                    width: 44,
                    height: 44,
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.2),
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(Icons.quiz_rounded, color: Colors.white, size: 24),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          _studentName.isNotEmpty ? _studentName : "សិស្ស",
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          _classroomName.isNotEmpty ? "ថ្នាក់រៀន៖ $_classroomName" : "ប្រព័ន្ធប្រឡងតេស្តតាមមុខវិជ្ជា",
                          style: TextStyle(
                            color: Colors.white.withValues(alpha: 0.85),
                            fontSize: 12.5,
                          ),
                        ),
                      ],
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.2),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      "${_allExams.length} វិញ្ញាសា",
                      style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 12),
                    ),
                  ),
                ],
              ),
            ),

            // ---------------------------------------------------------
            // 2. FILTER TABS (All, Available, Completed)
            // ---------------------------------------------------------
            Container(
              color: Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              child: Row(
                children: [
                  _buildTabChip(0, "ទាំងអស់ (${_allExams.length})"),
                  const SizedBox(width: 8),
                  _buildTabChip(1, "កំពុងបើក (${_allExams.where((e) => e['can_take'] == true).length})"),
                  const SizedBox(width: 8),
                  _buildTabChip(2, "បានប្រឡង (${_allExams.where((e) => e['latest_submission'] != null).length})"),
                ],
              ),
            ),
            const Divider(height: 1, thickness: 1, color: AppColors.borderLight),

            // ---------------------------------------------------------
            // 3. EXAMS LIST BODY
            // ---------------------------------------------------------
            Expanded(
              child: _isLoading
                  ? const Center(child: SpinKitFadingCircle(color: AppColors.primary, size: 36))
                  : _errorMessage != null
                      ? Center(
                          child: Padding(
                            padding: const EdgeInsets.all(24),
                            child: Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                const Icon(Icons.wifi_off_rounded, size: 48, color: AppColors.danger),
                                const SizedBox(height: 12),
                                Text(
                                  _errorMessage!,
                                  textAlign: TextAlign.center,
                                  style: const TextStyle(fontSize: 14, color: AppColors.textSecondary),
                                ),
                                const SizedBox(height: 16),
                                ElevatedButton.icon(
                                  onPressed: _fetchExams,
                                  icon: const Icon(Icons.refresh_rounded, size: 18),
                                  label: const Text("ទាញយកឡើងវិញ"),
                                  style: ElevatedButton.styleFrom(
                                    backgroundColor: AppColors.primary,
                                    foregroundColor: Colors.white,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        )
                      : filtered.isEmpty
                          ? Center(
                              child: Column(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Icon(Icons.assignment_turned_in_outlined, size: 54, color: Colors.grey.shade400),
                                  const SizedBox(height: 12),
                                  Text(
                                    _selectedTabIndex == 1
                                        ? "គ្មានវិញ្ញាសាកំពុងបើកប្រឡងទេ!"
                                        : (_selectedTabIndex == 2 ? "មិនទាន់មានប្រវត្តិប្រឡងនៅឡើយទេ!" : "គ្មានវិញ្ញាសាប្រឡង"),
                                    style: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: AppColors.textSecondary),
                                  ),
                                  const SizedBox(height: 4),
                                  const Text(
                                    "សូមរង់ចាំលោកគ្រូ-អ្នកគ្រូបើកវិញ្ញាសាថ្មី",
                                    style: TextStyle(fontSize: 12.5, color: Colors.grey),
                                  ),
                                ],
                              ),
                            )
                          : ListView.separated(
                              padding: const EdgeInsets.all(16),
                              physics: const AlwaysScrollableScrollPhysics(),
                              itemCount: filtered.length,
                              separatorBuilder: (_, __) => const SizedBox(height: 14),
                              itemBuilder: (context, index) {
                                return _buildExamCard(filtered[index]);
                              },
                            ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTabChip(int index, String title) {
    final isSelected = _selectedTabIndex == index;
    return Expanded(
      child: InkWell(
        onTap: () => setState(() => _selectedTabIndex = index),
        borderRadius: BorderRadius.circular(10),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 8),
          decoration: BoxDecoration(
            color: isSelected ? AppColors.primary : Colors.grey.shade100,
            borderRadius: BorderRadius.circular(10),
          ),
          alignment: Alignment.center,
          child: Text(
            title,
            style: TextStyle(
              fontSize: 12,
              fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
              color: isSelected ? Colors.white : AppColors.textSecondary,
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildExamCard(Map<String, dynamic> exam) {
    final title = exam['title'] ?? 'វិញ្ញាសាប្រឡង';
    final subjectName = exam['subject_name'] ?? 'មុខវិជ្ជា';
    final examTermName = exam['exam_term_name'] ?? '';
    final teacherName = exam['teacher_name'] ?? '';
    final durationMins = exam['duration_minutes'] ?? 45;
    final questionsCount = exam['questions_count'] ?? 0;
    final totalScore = (exam['total_score'] as num?)?.toDouble() ?? 100.0;
    final canTake = exam['can_take'] == true;
    final actionLabel = exam['action_label'] ?? 'ចូលប្រឡង';
    final latestSub = exam['latest_submission'] as Map<String, dynamic>?;
    final requiresPin = exam['requires_access_code'] == true;

    // Status Badge Logic
    Color badgeBg = Colors.grey.shade100;
    Color badgeText = AppColors.textSecondary;
    String badgeLabel = exam['status_label'] ?? 'បិទ';

    if (canTake) {
      if (actionLabel == 'បន្តការប្រឡង') {
        badgeBg = const Color(0xFFF59E0B).withValues(alpha: 0.12);
        badgeText = const Color(0xFFB45309);
        badgeLabel = "កំពុងប្រឡង (បន្ត)";
      } else {
        badgeBg = const Color(0xFF10B981).withValues(alpha: 0.12);
        badgeText = const Color(0xFF047857);
        badgeLabel = "កំពុងបើកដំណើរការ";
      }
    } else if (latestSub != null) {
      final isPassed = latestSub['is_passed'] == true;
      final score = (latestSub['score_obtained'] as num?)?.toDouble() ?? 0.0;
      final letter = latestSub['letter_grade'] ?? '';
      badgeBg = isPassed ? const Color(0xFF10B981).withValues(alpha: 0.12) : const Color(0xFFEF4444).withValues(alpha: 0.12);
      badgeText = isPassed ? const Color(0xFF047857) : const Color(0xFFB91C1C);
      badgeLabel = "ពិន្ទុ $score ($letter) - ${isPassed ? 'ជាប់' : 'ធ្លាក់'}";
    }

    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(
          color: canTake ? AppColors.primary.withValues(alpha: 0.4) : AppColors.borderLight,
          width: canTake ? 1.5 : 1,
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.03),
            blurRadius: 10,
            offset: const Offset(0, 3),
          ),
        ],
      ),
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header: Subject Chip & Status Badge
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: AppColors.primary.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  subjectName,
                  style: const TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                    color: AppColors.primary,
                  ),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: badgeBg,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  badgeLabel,
                  style: TextStyle(
                    fontSize: 11.5,
                    fontWeight: FontWeight.bold,
                    color: badgeText,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),

          // Exam Title
          Text(
            title,
            style: const TextStyle(
              fontSize: 15.5,
              fontWeight: FontWeight.bold,
              color: AppColors.textPrimary,
            ),
          ),
          if (examTermName.isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(
              "សម័យប្រឡង៖ $examTermName",
              style: const TextStyle(fontSize: 12.5, color: AppColors.textSecondary),
            ),
          ],
          const SizedBox(height: 12),

          // Chips Row: Duration, Questions count, Points
          Wrap(
            spacing: 8,
            runSpacing: 6,
            children: [
              _buildSmallChip(Icons.timer_outlined, "$durationMins នាទី"),
              _buildSmallChip(Icons.quiz_outlined, "$questionsCount សំណួរ"),
              _buildSmallChip(Icons.grade_outlined, "${totalScore.toStringAsFixed(0)} ពិន្ទុ"),
              if (requiresPin)
                _buildSmallChip(Icons.lock_outline_rounded, "PIN Code", color: const Color(0xFFF59E0B)),
            ],
          ),
          const SizedBox(height: 10),

          // Teacher Info & Action Button Row
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  const Icon(Icons.person_outline_rounded, size: 16, color: AppColors.textSecondary),
                  const SizedBox(width: 4),
                  Text(
                    teacherName.isNotEmpty ? teacherName : "លោកគ្រូ-អ្នកគ្រូ",
                    style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
                  ),
                ],
              ),
              if (canTake)
                ElevatedButton.icon(
                  onPressed: () => _handleStartExam(exam),
                  icon: Icon(
                    actionLabel == 'បន្តការប្រឡង' ? Icons.play_arrow_rounded : Icons.login_rounded,
                    size: 16,
                  ),
                  label: Text(actionLabel, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 12.5)),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: actionLabel == 'បន្តការប្រឡង' ? const Color(0xFFF59E0B) : AppColors.primary,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                    elevation: 1,
                  ),
                )
              else if (latestSub != null)
                OutlinedButton.icon(
                  onPressed: () {
                    final subId = latestSub['id'] as int;
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => StudentOnlineExamResultScreen(submissionId: subId),
                      ),
                    );
                  },
                  icon: const Icon(Icons.visibility_outlined, size: 16),
                  label: const Text("មើលលទ្ធផល", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12.5)),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AppColors.primary,
                    side: const BorderSide(color: AppColors.primary),
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildSmallChip(IconData icon, String label, {Color? color}) {
    final chipColor = color ?? AppColors.textSecondary;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: chipColor.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 13, color: chipColor),
          const SizedBox(width: 4),
          Text(
            label,
            style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: chipColor),
          ),
        ],
      ),
    );
  }
}
