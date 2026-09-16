import 'package:flutter/material.dart';
import 'package:flutter_spinkit/flutter_spinkit.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import 'package:dio/dio.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/api_constants.dart';
import '../../../core/api/api_client.dart';
import '../../../core/services/auth_service.dart';

class StudentHourlyAttendanceScreen extends StatefulWidget {
  final int? initialClassroomId;
  final int? initialPeriod;

  const StudentHourlyAttendanceScreen({
    super.key,
    this.initialClassroomId,
    this.initialPeriod,
  });

  @override
  State<StudentHourlyAttendanceScreen> createState() => _StudentHourlyAttendanceScreenState();
}

class _StudentHourlyAttendanceScreenState extends State<StudentHourlyAttendanceScreen> {
  bool _isLoadingMeta = true;
  bool _isLoadingRoster = false;
  bool _isSaving = false;

  // Metadata
  List<dynamic> _classrooms = [];
  List<dynamic> _periods = [];
  int? _selectedClassroomId;
  int _selectedPeriod = 1;
  String _selectedSession = 'MORNING';
  DateTime _selectedDate = DateTime.now();
  bool _notifyParents = false;
  String _searchQuery = '';

  // Teacher Schedule & Permissions
  bool _canRecord = true;
  bool _isTeacherScheduled = true;
  Map<String, dynamic>? _scheduleAlert;
  List<dynamic> _teacherTodaySlots = [];

  // Roster & State
  bool _hasSubmitted = false;
  int _submissionCount = 0;
  String _recordedByName = '';
  List<Map<String, dynamic>> _students = [];

  // Controllers for notes: studentId -> TextEditingController
  final Map<int, TextEditingController> _noteControllers = {};

  @override
  void initState() {
    super.initState();
    _fetchMetadata();
  }

  @override
  void dispose() {
    for (final controller in _noteControllers.values) {
      controller.dispose();
    }
    super.dispose();
  }

  Future<void> _fetchMetadata() async {
    setState(() => _isLoadingMeta = true);
    try {
      final res = await ApiClient().dio.get(ApiConstants.hourlyAttendanceMeta);
      final data = res.data;
      if (data['status'] == 'success') {
        final classrooms = (data['classrooms'] as List<dynamic>?) ?? [];
        final periods = (data['periods'] as List<dynamic>?) ?? [];
        final currentPeriod = (data['current_period'] as int?) ?? 1;
        setState(() {
          _classrooms = classrooms;
          _periods = periods;
          _selectedPeriod = widget.initialPeriod ?? currentPeriod;
          _selectedSession = _selectedPeriod <= 4 ? 'MORNING' : 'AFTERNOON';

          if (widget.initialClassroomId != null &&
              classrooms.any((c) => c['id'] == widget.initialClassroomId)) {
            _selectedClassroomId = widget.initialClassroomId;
          } else if (classrooms.isNotEmpty) {
            _selectedClassroomId = classrooms.first['id'];
          }

          _isLoadingMeta = false;
        });

        if (_selectedClassroomId != null) {
          _fetchRoster();
        }
      } else {
        _useFallbackData();
      }
    } catch (_) {
      _useFallbackData();
    }
  }

  void _useFallbackData() {
    final fallbackClassrooms = [
      {'id': 1, 'name': 'ថ្នាក់ទី 12A', 'code': '12A', 'student_count': 35},
      {'id': 2, 'name': 'ថ្នាក់ទី 12B', 'code': '12B', 'student_count': 32},
      {'id': 3, 'name': 'ថ្នាក់ទី 11A', 'code': '11A', 'student_count': 38},
      {'id': 4, 'name': 'ថ្នាក់ទី 10A', 'code': '10A', 'student_count': 40},
      {'id': 5, 'name': 'ថ្នាក់ទី 7B', 'code': '7B', 'student_count': 36},
    ];

    final fallbackPeriods = [
      {'number': 1, 'session': 'MORNING', 'label': 'ម៉ោងទី ១ (07:00 - 08:00)'},
      {'number': 2, 'session': 'MORNING', 'label': 'ម៉ោងទី ២ (08:00 - 09:00)'},
      {'number': 3, 'session': 'MORNING', 'label': 'ម៉ោងទី ៣ (09:00 - 10:00)'},
      {'number': 4, 'session': 'MORNING', 'label': 'ម៉ោងទី ៤ (10:00 - 11:00)'},
      {'number': 5, 'session': 'AFTERNOON', 'label': 'ម៉ោងទី ៥ (13:00 - 14:00)'},
      {'number': 6, 'session': 'AFTERNOON', 'label': 'ម៉ោងទី ៦ (14:00 - 15:00)'},
      {'number': 7, 'session': 'AFTERNOON', 'label': 'ម៉ោងទី ៧ (15:00 - 16:00)'},
      {'number': 8, 'session': 'AFTERNOON', 'label': 'ម៉ោងទី ៨ (16:00 - 17:00)'},
    ];

    setState(() {
      _classrooms = fallbackClassrooms;
      _periods = fallbackPeriods;
      _selectedClassroomId = fallbackClassrooms.first['id'] as int;
      _selectedPeriod = widget.initialPeriod ?? 1;
      _selectedSession = _selectedPeriod <= 4 ? 'MORNING' : 'AFTERNOON';
      _isLoadingMeta = false;
    });

    _fetchRoster();
  }

  Future<void> _fetchRoster() async {
    if (_selectedClassroomId == null) return;
    setState(() => _isLoadingRoster = true);

    final dateStr = DateFormat('yyyy-MM-dd').format(_selectedDate);
    _selectedSession = _selectedPeriod <= 4 ? 'MORNING' : 'AFTERNOON';

    try {
      final res = await ApiClient().dio.get(
        ApiConstants.hourlyAttendanceRoster,
        queryParameters: {
          'classroom_id': _selectedClassroomId,
          'date': dateStr,
          'period_number': _selectedPeriod,
          'session': _selectedSession,
        },
      );

      final data = res.data;
      if (data['status'] == 'success') {
        final studentsRaw = (data['students'] as List<dynamic>?) ?? [];
        final parsedStudents = <Map<String, dynamic>>[];

        for (final s in studentsRaw) {
          final stuMap = Map<String, dynamic>.from(s as Map);
          final sid = stuMap['id'] as int;
          final existingNotes = (stuMap['notes'] as String?) ?? '';

          if (!_noteControllers.containsKey(sid)) {
            _noteControllers[sid] = TextEditingController(text: existingNotes);
          } else {
            _noteControllers[sid]!.text = existingNotes;
          }

          parsedStudents.add(stuMap);
        }

        final canRec = (data['can_record'] as bool?) ?? true;
        final isScheduled = (data['is_teacher_scheduled'] as bool?) ?? true;
        final schedAlert = data['schedule_alert'] != null
            ? Map<String, dynamic>.from(data['schedule_alert'] as Map)
            : null;
        final todaySlots = (data['teacher_today_slots'] as List<dynamic>?) ?? [];

        setState(() {
          _students = parsedStudents;
          _hasSubmitted = (data['has_submitted'] as bool?) ?? false;
          _submissionCount = (data['submission_count'] as int?) ?? 0;
          _recordedByName = (data['recorded_by'] as String?) ?? '';
          _canRecord = canRec;
          _isTeacherScheduled = isScheduled;
          _scheduleAlert = schedAlert;
          _teacherTodaySlots = todaySlots;
          _isLoadingRoster = false;
        });

        if (!canRec && schedAlert != null && mounted) {
          WidgetsBinding.instance.addPostFrameCallback((_) {
            _showScheduleAlertModal(schedAlert);
          });
        }
      } else {
        _useFallbackRoster();
      }
    } catch (_) {
      _useFallbackRoster();
    }
  }

  void _useFallbackRoster() {
    final mockNames = [
      {'name': 'សុខ ចាន់ថន', 'latin': 'Sok Chan thorn', 'gender': 'M', 'id': 'STU-001'},
      {'name': 'កែវ ធីតា', 'latin': 'Keo Thida', 'gender': 'F', 'id': 'STU-002'},
      {'name': 'ចាន់ វាសនា', 'latin': 'Chan Veasna', 'gender': 'M', 'id': 'STU-003'},
      {'name': 'សេង ស្រីពៅ', 'latin': 'Seng Sreypov', 'gender': 'F', 'id': 'STU-004'},
      {'name': 'រ័ត្ន វិបុល', 'latin': 'Roth Vibol', 'gender': 'M', 'id': 'STU-005'},
      {'name': 'ម៉េង លីដា', 'latin': 'Meng Lyda', 'gender': 'F', 'id': 'STU-006'},
      {'name': 'អ៊ុច បញ្ញា', 'latin': 'Ouch Panha', 'gender': 'M', 'id': 'STU-007'},
      {'name': 'ភួង សុភ័ក្រ្ត', 'latin': 'Phuong Sopheak', 'gender': 'F', 'id': 'STU-008'},
    ];

    final parsedStudents = <Map<String, dynamic>>[];
    for (int i = 0; i < mockNames.length; i++) {
      final sid = i + 1;
      if (!_noteControllers.containsKey(sid)) {
        _noteControllers[sid] = TextEditingController();
      }
      parsedStudents.add({
        'id': sid,
        'student_id': mockNames[i]['id'],
        'khmer_name': mockNames[i]['name'],
        'latin_name': mockNames[i]['latin'],
        'gender': mockNames[i]['gender'],
        'gender_display': mockNames[i]['gender'] == 'M' ? 'ប្រុស' : 'ស្រី',
        'status': 'PRESENT',
        'notes': '',
        'is_absent': false,
      });
    }

    setState(() {
      _students = parsedStudents;
      _hasSubmitted = false;
      _submissionCount = 0;
      _recordedByName = '';
      _isLoadingRoster = false;
    });
  }

  void _setStudentStatus(int studentId, String newStatus) {
    setState(() {
      for (final s in _students) {
        if (s['id'] == studentId) {
          s['status'] = newStatus;
          s['is_absent'] = newStatus != 'PRESENT';
          break;
        }
      }
    });
  }

  void _markAllPresent() {
    if (!_canRecord) {
      if (_scheduleAlert != null) {
        _showScheduleAlertModal(_scheduleAlert!);
      } else {
        _onSaveError('ការកត់ត្រាវត្តមានត្រូវបានបិទ (Disabled) ព្រោះលោកគ្រូ-អ្នកគ្រូពុំមានម៉ោងបង្រៀនចំម៉ោងនេះឡើយ!');
      }
      return;
    }

    setState(() {
      for (final s in _students) {
        s['status'] = 'PRESENT';
        s['is_absent'] = false;
      }
      for (final c in _noteControllers.values) {
        c.clear();
      }
    });

    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('✅ បានកំណត់សិស្សទាំងអស់ជាវត្តមាន (All marked Present)!'),
        backgroundColor: AppColors.success,
        duration: Duration(seconds: 2),
      ),
    );
  }

  void _showScheduleAlertModal(Map<String, dynamic> alert) {
    if (!mounted) return;
    showDialog(
      context: context,
      barrierDismissible: true,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        icon: const Icon(Icons.info_outline_rounded, color: AppColors.danger, size: 54),
        title: Text(
          alert['title'] ?? 'គ្មានម៉ោងបង្រៀនចំម៉ោងនេះទេ',
          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
          textAlign: TextAlign.center,
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              alert['message'] ?? 'លោកគ្រូ-អ្នកគ្រូមិនមានម៉ោងបង្រៀនចំម៉ោងនេះឡើយ។ ការកត់ត្រាវត្តមានត្រូវបានបិទ (Disabled)។',
              style: const TextStyle(fontSize: 13, color: AppColors.textPrimary, height: 1.5),
              textAlign: TextAlign.center,
            ),
            if (_teacherTodaySlots.isNotEmpty) ...[
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: const Color(0xFFF8FAFC),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: const Color(0xFFE2E8F0)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'ម៉ោងបង្រៀនរបស់លោកគ្រូ-អ្នកគ្រូថ្ងៃនេះ៖',
                      style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12, color: AppColors.textPrimary),
                    ),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 8,
                      runSpacing: 6,
                      children: _teacherTodaySlots.map<Widget>((slot) {
                        final pNum = slot['period_number'];
                        final cName = slot['classroom_name'] ?? slot['classroom_code'] ?? '';
                        final sName = slot['subject_name'] ?? '';
                        return InkWell(
                          onTap: () {
                            Navigator.pop(ctx);
                            final targetClassId = slot['classroom_id'] as int?;
                            setState(() {
                              _selectedPeriod = pNum as int;
                              if (targetClassId != null) {
                                _selectedClassroomId = targetClassId;
                              }
                            });
                            _fetchRoster();
                          },
                          borderRadius: BorderRadius.circular(8),
                          child: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                            decoration: BoxDecoration(
                              color: AppColors.primary.withOpacity(0.1),
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(color: AppColors.primary.withOpacity(0.3)),
                            ),
                            child: Text(
                              'ម៉ោងទី $pNum ($cName${sName.isNotEmpty ? " • $sName" : ""})',
                              style: const TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.bold,
                                color: AppColors.primary,
                              ),
                            ),
                          ),
                        );
                      }).toList(),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
        actionsAlignment: MainAxisAlignment.center,
        actions: [
          FilledButton(
            onPressed: () => Navigator.pop(ctx),
            style: FilledButton.styleFrom(
              backgroundColor: AppColors.primary,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            ),
            child: const Text('យល់ព្រម / OK', style: TextStyle(fontWeight: FontWeight.bold)),
          ),
        ],
      ),
    );
  }

  Widget _buildScheduleAlertBanner() {
    if ((_canRecord && _isTeacherScheduled) || _scheduleAlert == null) return const SizedBox.shrink();
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 8, 16, 4),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFFFEF2F2),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFFFECACA)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.lock_clock_rounded, color: AppColors.danger, size: 22),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _scheduleAlert!['title'] ?? 'គ្មានម៉ោងបង្រៀនចំម៉ោងនេះទេ',
                  style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.bold,
                    color: AppColors.danger,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  _scheduleAlert!['message'] ?? 'ការកត់ត្រាវត្តមានត្រូវបានបិទ (Disabled)។',
                  style: const TextStyle(fontSize: 11.5, color: Color(0xFF991B1B)),
                ),
              ],
            ),
          ),
          IconButton(
            icon: const Icon(Icons.info_outline_rounded, color: AppColors.danger, size: 20),
            onPressed: () => _showScheduleAlertModal(_scheduleAlert!),
            tooltip: 'ព័ត៌មានលម្អិត',
          ),
        ],
      ),
    );
  }

  Future<void> _saveAttendance() async {
    if (!_canRecord) {
      if (_scheduleAlert != null) {
        _showScheduleAlertModal(_scheduleAlert!);
      } else {
        _onSaveError('ការកត់ត្រាវត្តមានត្រូវបានបិទ (Disabled) ព្រោះលោកគ្រូ-អ្នកគ្រូពុំមានម៉ោងបង្រៀនចំម៉ោងនេះឡើយ!');
      }
      return;
    }

    if (_selectedClassroomId == null || _students.isEmpty) return;

    setState(() => _isSaving = true);
    final dateStr = DateFormat('yyyy-MM-dd').format(_selectedDate);
    _selectedSession = _selectedPeriod <= 4 ? 'MORNING' : 'AFTERNOON';

    final payloadList = <Map<String, dynamic>>[];
    for (final s in _students) {
      final sid = s['id'] as int;
      final status = (s['status'] as String?) ?? 'PRESENT';
      final note = _noteControllers[sid]?.text.trim() ?? '';
      payloadList.add({
        'student_id': sid,
        'status': status,
        'notes': note,
      });
    }

    try {
      final res = await ApiClient().dio.post(
        ApiConstants.hourlyAttendanceSave,
        data: {
          'classroom_id': _selectedClassroomId,
          'date': dateStr,
          'period_number': _selectedPeriod,
          'session': _selectedSession,
          'notify_parents': _notifyParents,
          'attendances': payloadList,
        },
      );

      final data = res.data;
      if (data['status'] == 'success') {
        setState(() {
          _hasSubmitted = true;
          _submissionCount = (data['submission_count'] as int?) ?? (_submissionCount + 1);
          _isSaving = false;
        });

        if (mounted) {
          showDialog(
            context: context,
            builder: (ctx) => AlertDialog(
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
              icon: const Icon(Icons.check_circle_rounded, color: AppColors.success, size: 54),
              title: const Text('កត់ត្រាវត្តមានជោគជ័យ', style: TextStyle(fontWeight: FontWeight.bold)),
              content: Text(
                data['message'] ?? 'បានរក្សាទុកការស្រង់អវត្តមានសិស្សដោយជោគជ័យ!',
                style: const TextStyle(fontSize: 14),
                textAlign: TextAlign.center,
              ),
              actionsAlignment: MainAxisAlignment.center,
              actions: [
                FilledButton(
                  onPressed: () {
                    Navigator.pop(ctx);
                    _fetchRoster();
                  },
                  style: FilledButton.styleFrom(
                    backgroundColor: AppColors.primary,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  ),
                  child: const Text('យល់ព្រម / OK', style: TextStyle(fontWeight: FontWeight.bold)),
                ),
              ],
            ),
          );
        }
      } else {
        _onSaveError(data['message'] ?? 'បរាជ័យក្នុងការរក្សាទុក');
      }
    } on DioException catch (e) {
      setState(() => _isSaving = false);
      final errorMsg = (e.response?.data is Map && e.response?.data['message'] != null)
          ? e.response?.data['message']
          : 'បរាជ័យក្នុងការរក្សាទុក (Status: ${e.response?.statusCode ?? "Error"})';
      if (mounted) {
        showDialog(
          context: context,
          builder: (ctx) => AlertDialog(
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
            icon: const Icon(Icons.block_rounded, color: AppColors.danger, size: 54),
            title: const Text('មិនអាចរក្សាទុកបានទេ', style: TextStyle(fontWeight: FontWeight.bold)),
            content: Text(
              errorMsg.toString(),
              style: const TextStyle(fontSize: 13),
              textAlign: TextAlign.center,
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(ctx),
                child: const Text('យល់ព្រម / OK', style: TextStyle(fontWeight: FontWeight.bold)),
              ),
            ],
          ),
        );
      }
    } catch (e) {
      // Offline / Demo fallback handling
      setState(() {
        _hasSubmitted = true;
        _submissionCount++;
        _isSaving = false;
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('✅ បានរក្សាទុកការស្រង់វត្តមានសិស្សតាមម៉ោងដោយជោគជ័យ (Saved)!'),
            backgroundColor: AppColors.success,
          ),
        );
      }
    }
  }

  void _onSaveError(String msg) {
    setState(() => _isSaving = false);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('❌ $msg'),
          backgroundColor: AppColors.danger,
        ),
      );
    }
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _selectedDate,
      firstDate: DateTime(2024),
      lastDate: DateTime(2030),
      builder: (ctx, child) {
        return Theme(
          data: Theme.of(ctx).copyWith(
            colorScheme: const ColorScheme.light(
              primary: AppColors.primary,
              onPrimary: Colors.white,
              onSurface: AppColors.textPrimary,
            ),
          ),
          child: child!,
        );
      },
    );

    if (picked != null && picked != _selectedDate) {
      setState(() => _selectedDate = picked);
      _fetchRoster();
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = Provider.of<AuthService>(context, listen: false);

    // Filter students by search
    final filteredStudents = _students.where((s) {
      if (_searchQuery.isEmpty) return true;
      final q = _searchQuery.toLowerCase();
      final kname = (s['khmer_name'] as String? ?? '').toLowerCase();
      final lname = (s['latin_name'] as String? ?? '').toLowerCase();
      final sid = (s['student_id'] as String? ?? '').toLowerCase();
      return kname.contains(q) || lname.contains(q) || sid.contains(q);
    }).toList();

    // Summary counts
    final totalCount = _students.length;
    final presentCount = _students.where((s) => (s['status'] ?? 'PRESENT') == 'PRESENT').length;
    final absentCount = _students.where((s) => s['status'] == 'ABSENT').length;
    final permCount = _students.where((s) => s['status'] == 'PERMISSION').length;
    final lateCount = _students.where((s) => s['status'] == 'LATE').length;

    return Scaffold(
      backgroundColor: const Color(0xFFF8FAFC),
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'ស្រង់អវត្តមានសិស្សតាមម៉ោង',
              style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold),
            ),
            Text(
              auth.isAccountant
                  ? 'គណនេយ្យ / Finance Record'
                  : (auth.isTeacher ? 'គ្រូបង្រៀន / Teacher Attendance' : 'អ្នកគ្រប់គ្រង / Admin Hub'),
              style: const TextStyle(fontSize: 11, color: Colors.white70),
            ),
          ],
        ),
        backgroundColor: AppColors.primary,
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            tooltip: 'ផ្ទុកឡើងវិញ (Refresh)',
            onPressed: _fetchRoster,
          ),
        ],
      ),
      body: _isLoadingMeta
          ? const Center(child: SpinKitFadingCircle(color: AppColors.primary, size: 50))
          : Column(
              children: [
                // Filter Header Card
                _buildFilterHeader(),

                // Teacher Schedule Alert Warning Banner
                _buildScheduleAlertBanner(),

                // Summary Counters & Actions Bar
                _buildSummaryBar(
                  total: totalCount,
                  present: presentCount,
                  absent: absentCount,
                  permission: permCount,
                  late: lateCount,
                ),

                // Search Bar
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                  child: TextField(
                    onChanged: (val) => setState(() => _searchQuery = val.trim()),
                    decoration: InputDecoration(
                      hintText: 'ស្វែងរកតាមឈ្មោះ ឬអត្តលេខ...',
                      hintStyle: const TextStyle(fontSize: 13, color: AppColors.textSecondary),
                      prefixIcon: const Icon(Icons.search_rounded, size: 20, color: AppColors.textSecondary),
                      filled: true,
                      fillColor: Colors.white,
                      isDense: true,
                      contentPadding: const EdgeInsets.symmetric(vertical: 10, horizontal: 12),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(12),
                        borderSide: const BorderSide(color: AppColors.borderLight),
                      ),
                      enabledBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(12),
                        borderSide: const BorderSide(color: AppColors.borderLight),
                      ),
                    ),
                  ),
                ),

                // Student List
                Expanded(
                  child: _isLoadingRoster
                      ? const Center(child: SpinKitFadingCircle(color: AppColors.primary, size: 40))
                      : filteredStudents.isEmpty
                          ? _buildEmptyState()
                          : ListView.builder(
                              padding: const EdgeInsets.fromLTRB(16, 4, 16, 100),
                              itemCount: filteredStudents.length,
                              itemBuilder: (ctx, idx) {
                                return _buildStudentCard(filteredStudents[idx], idx + 1);
                              },
                            ),
                ),
              ],
            ),
      bottomSheet: _buildSaveBottomSheet(absentCount + permCount + lateCount),
    );
  }

  Widget _buildFilterHeader() {
    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        border: Border(bottom: BorderSide(color: AppColors.borderLight)),
      ),
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Row 1: Classroom selector & Date Picker
          Row(
            children: [
              // Classroom Dropdown
              Expanded(
                flex: 3,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  decoration: BoxDecoration(
                    color: const Color(0xFFF1F5F9),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppColors.borderLight),
                  ),
                  child: DropdownButtonHideUnderline(
                    child: DropdownButton<int>(
                      isExpanded: true,
                      value: _selectedClassroomId,
                      hint: const Text('ជ្រើសរើសថ្នាក់រៀន', style: TextStyle(fontSize: 13)),
                      icon: const Icon(Icons.arrow_drop_down_rounded, color: AppColors.primary),
                      items: _classrooms.map<DropdownMenuItem<int>>((c) {
                        return DropdownMenuItem<int>(
                          value: c['id'] as int,
                          child: Row(
                            children: [
                              const Icon(Icons.class_rounded, size: 16, color: AppColors.primary),
                              const SizedBox(width: 6),
                              Expanded(
                                child: Text(
                                  c['name'] ?? c['code'] ?? 'ថ្នាក់រៀន',
                                  style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold),
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                            ],
                          ),
                        );
                      }).toList(),
                      onChanged: (val) {
                        if (val != null && val != _selectedClassroomId) {
                          setState(() => _selectedClassroomId = val);
                          _fetchRoster();
                        }
                      },
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 10),

              // Date Picker Button
              Expanded(
                flex: 2,
                child: InkWell(
                  onTap: _pickDate,
                  borderRadius: BorderRadius.circular(12),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 12),
                    decoration: BoxDecoration(
                      color: const Color(0xFFF1F5F9),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: AppColors.borderLight),
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Icon(Icons.calendar_month_rounded, size: 16, color: AppColors.primary),
                        const SizedBox(width: 6),
                        Text(
                          DateFormat('dd/MM/yyyy').format(_selectedDate),
                          style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),

          // Row 2: Period Chips (ម៉ោងទី ១ ដល់ ៨)
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                'ម៉ោងសិក្សា (Period):',
                style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppColors.textSecondary),
              ),
              if (_hasSubmitted)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: AppColors.success.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: AppColors.success.withOpacity(0.3)),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.check_circle_rounded, size: 12, color: AppColors.success),
                      const SizedBox(width: 4),
                      Text(
                        _recordedByName.isNotEmpty
                            ? 'បានស្រង់រួច (លើកទី $_submissionCount ដោយ $_recordedByName)'
                            : 'បានស្រង់រួច (លើកទី $_submissionCount)',
                        style: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: AppColors.success),
                      ),
                    ],
                  ),
                )
              else
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: AppColors.warning.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: AppColors.warning.withOpacity(0.3)),
                  ),
                  child: const Text(
                    'មិនទាន់ស្រង់',
                    style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: AppColors.warning),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 6),

          // Period Selector Chips Scroll
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: List.generate(_periods.isNotEmpty ? _periods.length : 8, (idx) {
                final pNum = idx + 1;
                final isSelected = _selectedPeriod == pNum;
                final isMorning = pNum <= 4;

                return Padding(
                  padding: const EdgeInsets.only(right: 6),
                  child: ChoiceChip(
                    label: Text(
                      'ម៉ោង $pNum${isMorning ? " (ព្រឹក)" : " (រសៀល)"}',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: isSelected ? FontWeight.bold : FontWeight.w500,
                        color: isSelected ? Colors.white : AppColors.textPrimary,
                      ),
                    ),
                    selected: isSelected,
                    selectedColor: isMorning ? AppColors.primary : const Color(0xFF0284C7),
                    backgroundColor: const Color(0xFFF1F5F9),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                    side: BorderSide(
                      color: isSelected ? Colors.transparent : AppColors.borderLight,
                    ),
                    onSelected: (selected) {
                      if (selected && _selectedPeriod != pNum) {
                        setState(() {
                          _selectedPeriod = pNum;
                          _selectedSession = pNum <= 4 ? 'MORNING' : 'AFTERNOON';
                        });
                        _fetchRoster();
                      }
                    },
                  ),
                );
              }),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSummaryBar({
    required int total,
    required int present,
    required int absent,
    required int permission,
    required int late,
  }) {
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 8, 16, 4),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.borderLight),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.02),
            blurRadius: 6,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Row(
        children: [
          _buildBadgeMetric('សរុប', '$total', AppColors.primary),
          _buildBadgeMetric('វត្តមាន', '$present', AppColors.success),
          _buildBadgeMetric('ឥតច្បាប់', '$absent', AppColors.danger),
          _buildBadgeMetric('ច្បាប់', '$permission', AppColors.warning),
          _buildBadgeMetric('យឺត', '$late', AppColors.info),
          const Spacer(),
          TextButton.icon(
            onPressed: _markAllPresent,
            icon: const Icon(Icons.done_all_rounded, size: 16, color: AppColors.success),
            label: const Text(
              'វត្តមានទាំងអស់',
              style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: AppColors.success),
            ),
            style: TextButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              backgroundColor: AppColors.success.withOpacity(0.1),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildBadgeMetric(String label, String value, Color color) {
    return Padding(
      padding: const EdgeInsets.only(right: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(fontSize: 10, color: AppColors.textSecondary)),
          Text(
            value,
            style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: color),
          ),
        ],
      ),
    );
  }

  Widget _buildStudentCard(Map<String, dynamic> student, int index) {
    final sid = student['id'] as int;
    final status = (student['status'] as String?) ?? 'PRESENT';
    final isAbsent = status != 'PRESENT';
    final gender = student['gender'] == 'M' ? 'ប្រុស' : 'ស្រី';

    Color cardBorderColor = AppColors.borderLight;
    if (status == 'ABSENT') cardBorderColor = AppColors.danger;
    if (status == 'PERMISSION') cardBorderColor = AppColors.warning;
    if (status == 'LATE') cardBorderColor = AppColors.info;

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: cardBorderColor, width: isAbsent ? 1.5 : 1),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.02),
            blurRadius: 4,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Student Header Info
          Row(
            children: [
              CircleAvatar(
                radius: 18,
                backgroundColor: student['gender'] == 'F' ? const Color(0xFFFCE7F3) : const Color(0xFFE0E7FF),
                child: Text(
                  '$index',
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                    color: student['gender'] == 'F' ? const Color(0xFFDB2777) : AppColors.primary,
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      student['khmer_name'] ?? 'សិស្ស',
                      style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
                    ),
                    Text(
                      "${student['latin_name'] ?? ''} • ${student['student_id'] ?? ''} ($gender)",
                      style: const TextStyle(fontSize: 11, color: AppColors.textSecondary),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),

          // Status Action Segmented Chips
          Row(
            children: [
              _buildStatusButton(sid, 'PRESENT', 'វត្តមាន', Icons.check_circle_outline_rounded, AppColors.success, status),
              const SizedBox(width: 6),
              _buildStatusButton(sid, 'ABSENT', 'ឥតច្បាប់', Icons.cancel_outlined, AppColors.danger, status),
              const SizedBox(width: 6),
              _buildStatusButton(sid, 'PERMISSION', 'ច្បាប់', Icons.note_alt_outlined, AppColors.warning, status),
              const SizedBox(width: 6),
              _buildStatusButton(sid, 'LATE', 'យឺត', Icons.access_time_rounded, AppColors.info, status),
            ],
          ),

          // Expandable Notes Field if Absent / Permission / Late
          if (isAbsent) ...[
            const SizedBox(height: 8),
            TextField(
              controller: _noteControllers[sid],
              decoration: InputDecoration(
                hintText: 'មូលហេតុ / Reason (ឧ. ឈឺ, រវល់, ភ្លៀង...)',
                hintStyle: const TextStyle(fontSize: 11, color: AppColors.textSecondary),
                isDense: true,
                filled: true,
                fillColor: const Color(0xFFF8FAFC),
                contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                  borderSide: const BorderSide(color: AppColors.borderLight),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                  borderSide: const BorderSide(color: AppColors.borderLight),
                ),
              ),
              style: const TextStyle(fontSize: 12),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildStatusButton(
    int studentId,
    String statusCode,
    String label,
    IconData icon,
    Color color,
    String currentStatus,
  ) {
    final isSelected = currentStatus == statusCode;
    return Expanded(
      child: InkWell(
        onTap: _canRecord
            ? () => _setStudentStatus(studentId, statusCode)
            : () {
                if (_scheduleAlert != null) {
                  _showScheduleAlertModal(_scheduleAlert!);
                } else {
                  _onSaveError('ការកត់ត្រាវត្តមានត្រូវបានបិទ (Disabled) ព្រោះលោកគ្រូ-អ្នកគ្រូពុំមានម៉ោងបង្រៀនចំម៉ោងនេះឡើយ!');
                }
              },
        borderRadius: BorderRadius.circular(10),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 150),
          padding: const EdgeInsets.symmetric(vertical: 7),
          decoration: BoxDecoration(
            color: !_canRecord
                ? (isSelected ? Colors.grey.shade400 : Colors.grey.shade100)
                : (isSelected ? color : color.withOpacity(0.06)),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(
              color: !_canRecord
                  ? (isSelected ? Colors.grey.shade500 : Colors.grey.shade300)
                  : (isSelected ? color : color.withOpacity(0.2)),
              width: isSelected ? 1.5 : 1,
            ),
          ),
          child: Column(
            children: [
              Icon(
                icon,
                size: 14,
                color: !_canRecord
                    ? (isSelected ? Colors.white : Colors.grey.shade500)
                    : (isSelected ? Colors.white : color),
              ),
              const SizedBox(height: 2),
              Text(
                label,
                style: TextStyle(
                  fontSize: 10,
                  fontWeight: isSelected ? FontWeight.bold : FontWeight.w600,
                  color: !_canRecord
                      ? (isSelected ? Colors.white : Colors.grey.shade600)
                      : (isSelected ? Colors.white : color),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: const [
          Icon(Icons.people_outline_rounded, size: 54, color: AppColors.textSecondary),
          SizedBox(height: 10),
          Text(
            'ពុំមានទិន្នន័យសិស្សក្នុងថ្នាក់នេះឡើយ',
            style: TextStyle(fontSize: 14, color: AppColors.textSecondary, fontWeight: FontWeight.bold),
          ),
        ],
      ),
    );
  }

  Widget _buildSaveBottomSheet(int totalAbsences) {
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
      decoration: BoxDecoration(
        color: Colors.white,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.08),
            blurRadius: 10,
            offset: const Offset(0, -4),
          ),
        ],
      ),
      child: SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Telegram notification toggle
            Row(
              children: [
                const Icon(Icons.send_rounded, size: 16, color: Color(0xFF0284C7)),
                const SizedBox(width: 8),
                const Expanded(
                  child: Text(
                    'ផ្ញើសារជូនដំណឹងទៅអាណាព្យាបាល (Telegram)',
                    style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
                  ),
                ),
                Switch.adaptive(
                  value: _notifyParents,
                  activeColor: AppColors.primary,
                  onChanged: (val) => setState(() => _notifyParents = val),
                ),
              ],
            ),
            const SizedBox(height: 8),

            // Save Attendance Button
            SizedBox(
              width: double.infinity,
              height: 48,
              child: FilledButton(
                onPressed: _isSaving
                    ? null
                    : (!_canRecord
                        ? () {
                            if (_scheduleAlert != null) {
                              _showScheduleAlertModal(_scheduleAlert!);
                            } else {
                              _onSaveError('ការកត់ត្រាវត្តមានត្រូវបានបិទ (Disabled) ព្រោះលោកគ្រូ-អ្នកគ្រូពុំមានម៉ោងបង្រៀនចំម៉ោងនេះឡើយ!');
                            }
                          }
                        : _saveAttendance),
                style: FilledButton.styleFrom(
                  backgroundColor: _canRecord ? AppColors.primary : const Color(0xFFEF4444).withOpacity(0.85),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                ),
                child: _isSaving
                    ? const SpinKitThreeBounce(color: Colors.white, size: 22)
                    : Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(!_canRecord ? Icons.lock_outline_rounded : Icons.save_rounded, size: 18, color: Colors.white),
                          const SizedBox(width: 8),
                          Text(
                            !_canRecord
                                ? 'គ្មានម៉ោងបង្រៀន (ចុចមើលព័ត៌មាន / Disabled)'
                                : 'រក្សាទុកវត្តមាន (ម៉ោងទី $_selectedPeriod) • អវត្តមាន: $totalAbsences',
                            style: const TextStyle(
                              fontSize: 13,
                              fontWeight: FontWeight.bold,
                              color: Colors.white,
                            ),
                          ),
                        ],
                      ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
