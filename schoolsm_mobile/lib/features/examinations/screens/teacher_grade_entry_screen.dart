import 'package:flutter/material.dart';
import 'package:flutter_spinkit/flutter_spinkit.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/api_constants.dart';
import '../../../core/api/api_client.dart';

class TeacherGradeEntryScreen extends StatefulWidget {
  const TeacherGradeEntryScreen({super.key});

  @override
  State<TeacherGradeEntryScreen> createState() => _TeacherGradeEntryScreenState();
}

class _TeacherGradeEntryScreenState extends State<TeacherGradeEntryScreen> {
  bool _isLoadingMeta = true;
  bool _isLoadingSheet = false;
  bool _isSaving = false;

  List<dynamic> _examTerms = [];
  List<dynamic> _classrooms = [];
  List<dynamic> _subjects = [];
  List<dynamic> _allMetaSubjects = [];

  bool _canSelectTerm = false;
  String _activeTermName = '';

  int? _selectedTermId;
  int? _selectedClassroomId;
  int? _selectedSubjectId;

  List<dynamic> _students = [];
  final Map<int, TextEditingController> _scoreControllers = {};

  @override
  void initState() {
    super.initState();
    _fetchMeta();
  }

  @override
  void dispose() {
    for (final c in _scoreControllers.values) {
      c.dispose();
    }
    super.dispose();
  }

  void _updateSubjectsForClass(int? classroomId) {
    if (classroomId == null) {
      _subjects = [];
      _selectedSubjectId = null;
      return;
    }
    final dynamic cls = _classrooms.firstWhere(
      (c) => c['id'] == classroomId,
      orElse: () => null,
    );
    if (cls != null && cls['subjects'] != null && (cls['subjects'] as List).isNotEmpty) {
      _subjects = (cls['subjects'] as List).toList();
    } else if (_allMetaSubjects.isNotEmpty) {
      _subjects = List.from(_allMetaSubjects);
    } else {
      _subjects = [];
    }

    if (_subjects.isNotEmpty) {
      if (!_subjects.any((s) => s['id'] == _selectedSubjectId)) {
        _selectedSubjectId = _subjects.first['id'] as int?;
      }
    } else {
      _selectedSubjectId = null;
    }
  }

  Future<void> _fetchMeta() async {
    setState(() => _isLoadingMeta = true);
    try {
      final res = await ApiClient().dio.get(ApiConstants.teacherGradeMeta);
      final data = res.data;
      if (data != null && data['status'] == 'success') {
        final terms = (data['exam_terms'] as List?)?.toList() ?? [];
        final classes = (data['classrooms'] as List?)?.toList() ?? [];
        final subs = (data['subjects'] as List?)?.toList() ?? [];
        final bool canSelect = data['can_select_term'] == true;
        final String activeName = data['active_term_name']?.toString() ?? '';
        final int? activeId = data['active_term_id'] as int?;

        setState(() {
          _examTerms = terms;
          _classrooms = classes;
          _allMetaSubjects = subs;
          _canSelectTerm = canSelect;
          _activeTermName = activeName;

          if (activeId != null) {
            _selectedTermId = activeId;
          } else if (_examTerms.isNotEmpty) {
            _selectedTermId = _examTerms.first['id'] as int?;
          }
          if (_classrooms.isNotEmpty) {
            _selectedClassroomId = _classrooms.first['id'] as int?;
            _updateSubjectsForClass(_selectedClassroomId);
          } else {
            _selectedClassroomId = null;
            _subjects = [];
            _selectedSubjectId = null;
          }

          _isLoadingMeta = false;
        });

        if (_selectedTermId != null && _selectedClassroomId != null && _selectedSubjectId != null) {
          _fetchSheet();
        }
      } else {
        setState(() => _isLoadingMeta = false);
      }
    } catch (_) {
      setState(() => _isLoadingMeta = false);
    }
  }

  Future<void> _fetchSheet() async {
    if (_selectedTermId == null || _selectedClassroomId == null || _selectedSubjectId == null) return;

    setState(() => _isLoadingSheet = true);
    try {
      final res = await ApiClient().dio.get(
        ApiConstants.teacherGradeSheet,
        queryParameters: {
          'exam_term_id': _selectedTermId,
          'classroom_id': _selectedClassroomId,
          'subject_id': _selectedSubjectId,
        },
      );
      final data = res.data;
      if (data['status'] == 'success') {
        final list = data['students'] ?? [];
        for (final c in _scoreControllers.values) {
          c.dispose();
        }
        _scoreControllers.clear();

        for (final s in list) {
          final id = s['id'] as int;
          final score = s['score'] != null ? s['score'].toString() : '';
          _scoreControllers[id] = TextEditingController(text: score);
        }

        setState(() {
          _students = list;
          _isLoadingSheet = false;
        });
      } else {
        setState(() => _isLoadingSheet = false);
      }
    } catch (_) {
      setState(() => _isLoadingSheet = false);
    }
  }

  Future<void> _saveGrades() async {
    if (_students.isEmpty) return;

    setState(() => _isSaving = true);
    final gradesPayload = <Map<String, dynamic>>[];

    for (final s in _students) {
      final id = s['id'] as int;
      final text = _scoreControllers[id]?.text.trim() ?? '';
      if (text.isNotEmpty) {
        final val = double.tryParse(text);
        if (val != null) {
          gradesPayload.add({'student_id': id, 'score': val});
        }
      }
    }

    try {
      final res = await ApiClient().dio.post(
        ApiConstants.teacherGradeSave,
        data: {
          'exam_term_id': _selectedTermId,
          'classroom_id': _selectedClassroomId,
          'subject_id': _selectedSubjectId,
          'grades': gradesPayload,
        },
      );

      setState(() => _isSaving = false);
      if (res.data['status'] == 'success') {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text("🎉 បានរក្សាទុកពិន្ទុដោយជោគជ័យ!"),
              backgroundColor: AppColors.success,
            ),
          );
        }
      }
    } catch (e) {
      setState(() => _isSaving = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(ApiClient.getErrorMessage(e)),
            backgroundColor: AppColors.danger,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final int? safeTermId = (_selectedTermId != null && _examTerms.any((t) => t['id'] == _selectedTermId))
        ? _selectedTermId
        : (_examTerms.isNotEmpty ? _examTerms.first['id'] as int? : null);

    final int? safeClassroomId = (_selectedClassroomId != null && _classrooms.any((c) => c['id'] == _selectedClassroomId))
        ? _selectedClassroomId
        : (_classrooms.isNotEmpty ? _classrooms.first['id'] as int? : null);

    final int? safeSubjectId = (_selectedSubjectId != null && _subjects.any((s) => s['id'] == _selectedSubjectId))
        ? _selectedSubjectId
        : (_subjects.isNotEmpty ? _subjects.first['id'] as int? : null);

    final String activeDisplayName = _activeTermName.isNotEmpty
        ? _activeTermName
        : (_examTerms.any((t) => t['id'] == safeTermId)
            ? (_examTerms.firstWhere((t) => t['id'] == safeTermId)['name'] ?? '')
            : (_examTerms.isNotEmpty ? (_examTerms.first['name'] ?? '') : ''));

    return Scaffold(
      backgroundColor: AppColors.bgLight,
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        title: const Text(
          "បញ្ចូលពិន្ទុសិស្ស (Grade Entry)",
          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 17, color: AppColors.textPrimary),
        ),
      ),
      body: _isLoadingMeta
          ? const Center(child: SpinKitFadingCircle(color: AppColors.primary, size: 36))
          : Column(
              children: [
                // Filter Dropdowns
                Container(
                  color: Colors.white,
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: _canSelectTerm
                                ? DropdownButtonFormField<int>(
                                    initialValue: safeTermId,
                                    isExpanded: true,
                                    decoration: _dropDeco("សម័យប្រឡង"),
                                    items: _examTerms.map<DropdownMenuItem<int>>((t) {
                                      return DropdownMenuItem<int>(
                                        value: t['id'] as int,
                                        child: Text(t['name'] ?? '', overflow: TextOverflow.ellipsis),
                                      );
                                    }).toList(),
                                    onChanged: (v) {
                                      setState(() => _selectedTermId = v);
                                      _fetchSheet();
                                    },
                                  )
                                : DropdownButtonFormField<int>(
                                    initialValue: safeTermId,
                                    isExpanded: true,
                                    decoration: _dropDeco("សម័យប្រឡង").copyWith(
                                      filled: true,
                                      fillColor: const Color(0xFFF1F5F9),
                                      prefixIcon: const Icon(Icons.lock_rounded, size: 17, color: AppColors.primary),
                                      helperText: "កំណត់ដោយ Admin (មិនអាចប្តូរបាន)",
                                      helperStyle: const TextStyle(fontSize: 10, color: Colors.black54, fontWeight: FontWeight.w500),
                                    ),
                                    items: [
                                      DropdownMenuItem<int>(
                                        value: safeTermId,
                                        child: Text(
                                          activeDisplayName,
                                          style: const TextStyle(fontWeight: FontWeight.w600, color: AppColors.textPrimary, fontSize: 13),
                                          overflow: TextOverflow.ellipsis,
                                        ),
                                      ),
                                    ],
                                    onChanged: null, // Disabled: teacher can view but cannot change!
                                  ),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: DropdownButtonFormField<int>(
                              value: safeClassroomId,
                              isExpanded: true,
                              decoration: _dropDeco("ថ្នាក់រៀន"),
                              items: _classrooms.map<DropdownMenuItem<int>>((c) {
                                return DropdownMenuItem<int>(
                                  value: c['id'] as int,
                                  child: Text(c['name'] ?? '', overflow: TextOverflow.ellipsis),
                                );
                              }).toList(),
                              onChanged: (v) {
                                setState(() {
                                  _selectedClassroomId = v;
                                  _updateSubjectsForClass(v);
                                });
                                _fetchSheet();
                              },
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 10),
                      DropdownButtonFormField<int>(
                        value: safeSubjectId,
                        isExpanded: true,
                        decoration: _dropDeco("មុខវិជ្ជា (Subject)"),
                        items: _subjects.map<DropdownMenuItem<int>>((s) {
                          final name = s['name_kh'] ?? s['name'] ?? '';
                          final code = s['code'] ?? '';
                          return DropdownMenuItem<int>(
                            value: s['id'] as int,
                            child: Text(code.isNotEmpty ? "$name ($code)" : name, overflow: TextOverflow.ellipsis),
                          );
                        }).toList(),
                        onChanged: (v) {
                          setState(() => _selectedSubjectId = v);
                          _fetchSheet();
                        },
                      ),
                    ],
                  ),
                ),

                // Student Score List
                Expanded(
                  child: _isLoadingSheet
                      ? const Center(child: SpinKitFadingCircle(color: AppColors.primary, size: 36))
                      : _students.isEmpty
                          ? const Center(child: Text("ពុំមានទិន្នន័យសិស្សក្នុងថ្នាក់នេះឡើយ", style: TextStyle(color: AppColors.textSecondary)))
                          : ListView.builder(
                              padding: const EdgeInsets.all(16),
                              itemCount: _students.length,
                              itemBuilder: (ctx, idx) {
                                final s = _students[idx];
                                final id = s['id'] as int;
                                final controller = _scoreControllers[id];

                                return Container(
                                  margin: const EdgeInsets.only(bottom: 10),
                                  padding: const EdgeInsets.all(12),
                                  decoration: BoxDecoration(
                                    color: Colors.white,
                                    borderRadius: BorderRadius.circular(14),
                                    border: Border.all(color: AppColors.borderLight),
                                  ),
                                  child: Row(
                                    children: [
                                      CircleAvatar(
                                        radius: 18,
                                        backgroundColor: AppColors.primary.withValues(alpha: 0.1),
                                        child: Text(
                                          "${idx + 1}",
                                          style: const TextStyle(fontWeight: FontWeight.bold, color: AppColors.primary, fontSize: 13),
                                        ),
                                      ),
                                      const SizedBox(width: 12),
                                      Expanded(
                                        child: Column(
                                          crossAxisAlignment: CrossAxisAlignment.start,
                                          children: [
                                            Text(
                                              s['khmer_name'] ?? '',
                                              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: AppColors.textPrimary),
                                            ),
                                            Text(
                                              s['student_id'] ?? '',
                                              style: const TextStyle(fontSize: 11, color: AppColors.textSecondary),
                                            ),
                                          ],
                                        ),
                                      ),
                                      SizedBox(
                                        width: 80,
                                        height: 44,
                                        child: TextField(
                                          controller: controller,
                                          keyboardType: const TextInputType.numberWithOptions(decimal: true),
                                          textAlign: TextAlign.center,
                                          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: AppColors.primary),
                                          decoration: InputDecoration(
                                            hintText: "ពិន្ទុ",
                                            hintStyle: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
                                            filled: true,
                                            fillColor: AppColors.bgLight,
                                            contentPadding: const EdgeInsets.symmetric(vertical: 8),
                                            border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: AppColors.borderLight)),
                                            focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: AppColors.primary, width: 2)),
                                          ),
                                        ),
                                      ),
                                    ],
                                  ),
                                );
                              },
                            ),
                ),

                // Save Action Bar
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    boxShadow: [
                      BoxShadow(color: Colors.black.withValues(alpha: 0.05), blurRadius: 10, offset: const Offset(0, -3)),
                    ],
                  ),
                  child: SizedBox(
                    width: double.infinity,
                    height: 48,
                    child: ElevatedButton(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.primary,
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                      ),
                      onPressed: _isSaving ? null : _saveGrades,
                      child: _isSaving
                          ? const SpinKitThreeBounce(color: Colors.white, size: 22)
                          : const Text("រក្សាទុកពិន្ទុ (Save Grades)", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
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
