import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_spinkit/flutter_spinkit.dart';
import 'package:intl/intl.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/api_constants.dart';
import '../../../core/api/api_client.dart';

class StudentEnrollmentScreen extends StatefulWidget {
  const StudentEnrollmentScreen({super.key});

  @override
  State<StudentEnrollmentScreen> createState() => _StudentEnrollmentScreenState();
}

class _StudentEnrollmentScreenState extends State<StudentEnrollmentScreen> {
  bool _isLoadingMeta = true;
  bool _isSubmitting = false;

  // Metadata & Modes from backend
  String _registrationMode = 'BOTH'; // 'ADMIN_CUSTOM', 'MOEYS_INDIVIDUAL', 'BOTH'
  String _activeEnrollmentMode = 'ADMIN_CUSTOM'; // Active selected mode
  List<dynamic> _academicYears = [];
  List<dynamic> _classrooms = [];
  List<dynamic> _scholarshipTypes = [];
  String _suggestedId = '';
  String _schoolName = 'SchoolSM';

  // Dynamic Grade Options
  List<dynamic> _gradeOptions = [];
  final Map<String, dynamic> _gradeOptionValues = {};
  bool _isLoadingGradeOptions = false;

  // General & Shared Form Controllers
  final _khmerNameController = TextEditingController();
  final _latinNameController = TextEditingController();
  final _customIdController = TextEditingController();
  final _phoneController = TextEditingController();
  final _pobController = TextEditingController();
  final _addressController = TextEditingController();

  final _fatherNameController = TextEditingController();
  final _fatherPhoneController = TextEditingController();
  final _fatherJobController = TextEditingController();

  final _motherNameController = TextEditingController();
  final _motherPhoneController = TextEditingController();
  final _motherJobController = TextEditingController();

  final _guardianNameController = TextEditingController();
  final _emergencyPhoneController = TextEditingController();

  // MoEYS Individual 35-Column Specific Controllers & State
  final _surnameController = TextEditingController();
  final _givenNameController = TextEditingController();
  final _pobCommuneController = TextEditingController();
  final _pobDistrictController = TextEditingController();
  final _pobProvinceController = TextEditingController();
  final _primarySchoolController = TextEditingController();
  final _secondarySchoolController = TextEditingController();
  final _guardianJobController = TextEditingController();

  String _orphanStatus = 'មិនមែន';
  String _ethnicMinority = 'មិនមែន';
  String _disabilityPhysical = 'មិនមាន';
  String _disabilitySight = 'មិនមាន';
  String _disabilityHearing = 'មិនមាន';
  String _equityCard1 = 'មិនមាន';
  String _equityCard2 = 'មិនមាន';
  String _riskCard = 'មិនមាន';
  String _moeysScholarship = 'មិនមាន';
  String _moeysTrack = 'ទូទៅ';
  bool _isRepeatingGrade = false;

  // Academic & Shared Choices
  String _gender = 'M';
  DateTime _dateOfBirth = DateTime(DateTime.now().year - 14, 1, 1);
  int? _selectedYearId;
  int? _selectedClassroomId;
  String _selectedScholarship = 'FULL_PAY';

  // Uniqueness check state
  Timer? _debounceRomanize;
  Timer? _debounceCheckId;
  bool _isCheckingId = false;
  bool? _isIdAvailable;
  String _idCheckMessage = '';

  @override
  void initState() {
    super.initState();
    _fetchEnrollmentMeta();
  }

  @override
  void dispose() {
    _debounceRomanize?.cancel();
    _debounceCheckId?.cancel();
    _khmerNameController.dispose();
    _latinNameController.dispose();
    _customIdController.dispose();
    _phoneController.dispose();
    _pobController.dispose();
    _addressController.dispose();
    _fatherNameController.dispose();
    _fatherPhoneController.dispose();
    _fatherJobController.dispose();
    _motherNameController.dispose();
    _motherPhoneController.dispose();
    _motherJobController.dispose();
    _guardianNameController.dispose();
    _emergencyPhoneController.dispose();

    _surnameController.dispose();
    _givenNameController.dispose();
    _pobCommuneController.dispose();
    _pobDistrictController.dispose();
    _pobProvinceController.dispose();
    _primarySchoolController.dispose();
    _secondarySchoolController.dispose();
    _guardianJobController.dispose();
    super.dispose();
  }

  Future<void> _fetchEnrollmentMeta() async {
    setState(() => _isLoadingMeta = true);
    try {
      final res = await ApiClient().dio.get(ApiConstants.studentEnroll);
      final data = res.data;
      if (data['status'] == 'success') {
        setState(() {
          _suggestedId = data['suggested_id'] ?? '';
          _customIdController.text = _suggestedId;
          _academicYears = data['academic_years'] ?? [];
          _classrooms = data['classrooms'] ?? [];
          _scholarshipTypes = data['scholarship_types'] ?? [];
          _schoolName = data['school_name'] ?? 'SchoolSM';

          _registrationMode = data['registration_mode'] ?? 'BOTH';
          if (_registrationMode == 'MOEYS_INDIVIDUAL') {
            _activeEnrollmentMode = 'MOEYS_INDIVIDUAL';
          } else {
            _activeEnrollmentMode = 'ADMIN_CUSTOM';
          }

          if (data['current_academic_year'] != null) {
            _selectedYearId = data['current_academic_year']['id'];
          } else if (_academicYears.isNotEmpty) {
            _selectedYearId = _academicYears.first['id'];
          }

          if (_classrooms.isNotEmpty) {
            _selectedClassroomId = _classrooms.first['id'];
          }

          _isLoadingMeta = false;
          _isIdAvailable = true;
          _idCheckMessage = "អត្តលេខស្វ័យប្រវត្តិតាមឆ្នាំសិក្សា";
        });

        // Load grade-specific options if classroom selected
        if (_selectedClassroomId != null) {
          _fetchGradeOptions();
        }
      }
    } catch (e) {
      setState(() => _isLoadingMeta = false);
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

  Future<void> _fetchGradeOptions() async {
    if (_selectedClassroomId == null) {
      setState(() => _gradeOptions = []);
      return;
    }

    setState(() => _isLoadingGradeOptions = true);
    try {
      final res = await ApiClient().dio.get(
        ApiConstants.studentGradeOptions,
        queryParameters: {
          'classroom_id': _selectedClassroomId,
          'form_category': _activeEnrollmentMode,
        },
      );
      final data = res.data;
      if (data['status'] == 'success') {
        setState(() {
          _gradeOptions = data['options'] ?? [];
          _isLoadingGradeOptions = false;
        });
      } else {
        setState(() => _isLoadingGradeOptions = false);
      }
    } catch (_) {
      setState(() => _isLoadingGradeOptions = false);
    }
  }

  void _switchEnrollmentMode(String mode) {
    if (_activeEnrollmentMode == mode) return;
    setState(() {
      _activeEnrollmentMode = mode;
      _gradeOptions = [];
      _gradeOptionValues.clear();
    });
    _fetchGradeOptions();
  }

  void _onMoEYSNameChanged() {
    final s = _surnameController.text.trim();
    final g = _givenNameController.text.trim();
    final full = "$s $g".trim();
    _khmerNameController.text = full;
    _onKhmerNameChanged(full);
  }

  void _onKhmerNameChanged(String val) {
    _debounceRomanize?.cancel();
    if (val.trim().isEmpty) return;

    _debounceRomanize = Timer(const Duration(milliseconds: 600), () async {
      try {
        final res = await ApiClient().dio.get(
          ApiConstants.studentRomanize,
          queryParameters: {'name': val.trim()},
        );
        if (res.data != null && res.data['latin_name'] != null) {
          final latin = res.data['latin_name'].toString();
          if (latin.isNotEmpty && _latinNameController.text.isEmpty) {
            setState(() {
              _latinNameController.text = latin;
            });
          }
        }
      } catch (_) {}
    });
  }

  void _onCustomIdChanged(String val) {
    _debounceCheckId?.cancel();
    final trimmed = val.trim();
    if (trimmed.isEmpty) {
      setState(() {
        _isIdAvailable = true;
        _idCheckMessage = "នឹងបង្កើតស្វ័យប្រវត្តិតាមឆ្នាំសិក្សា (ឧ. $_suggestedId)";
        _isCheckingId = false;
      });
      return;
    }

    setState(() => _isCheckingId = true);
    _debounceCheckId = Timer(const Duration(milliseconds: 500), () async {
      try {
        final res = await ApiClient().dio.get(
          ApiConstants.studentCheckId,
          queryParameters: {
            'student_id': trimmed,
            if (_selectedYearId != null) 'academic_year_id': _selectedYearId,
          },
        );
        final data = res.data;
        if (mounted) {
          setState(() {
            _isCheckingId = false;
            _isIdAvailable = data['is_available'] ?? false;
            _idCheckMessage = data['message'] ?? '';
          });
        }
      } catch (e) {
        if (mounted) {
          setState(() {
            _isCheckingId = false;
            _isIdAvailable = null;
          });
        }
      }
    });
  }

  Future<void> _submitEnrollment() async {
    String khmerName = _khmerNameController.text.trim();
    if (_activeEnrollmentMode == 'MOEYS_INDIVIDUAL') {
      final s = _surnameController.text.trim();
      final g = _givenNameController.text.trim();
      if (s.isEmpty || g.isEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text("សូមបញ្ចូលនាមត្រកូល និងនាមខ្លួនជាភាសាខ្មែរ!"),
            backgroundColor: AppColors.danger,
          ),
        );
        return;
      }
      khmerName = "$s $g".trim();
    } else {
      if (khmerName.isEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text("សូមបញ្ចូលឈ្មោះជាភាសាខ្មែរ!"),
            backgroundColor: AppColors.danger,
          ),
        );
        return;
      }
    }

    if (_isIdAvailable == false) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text("អត្តលេខជាន់គ្នា! សូមជ្រើសរើសអត្តលេខផ្សេង ឬទុកទទេ"),
          backgroundColor: AppColors.danger,
        ),
      );
      return;
    }

    setState(() => _isSubmitting = true);

    final payload = <String, dynamic>{
      'enrollment_mode': _activeEnrollmentMode,
      'student_id': _customIdController.text.trim(),
      'khmer_name': khmerName,
      'latin_name': _latinNameController.text.trim(),
      'gender': _gender,
      'date_of_birth': DateFormat('yyyy-MM-dd').format(_dateOfBirth),
      'phone': _phoneController.text.trim(),
      'place_of_birth': _pobController.text.trim(),
      'current_address': _addressController.text.trim(),
      'classroom_id': _selectedClassroomId,
      'academic_year_id': _selectedYearId,
      'scholarship_type': _selectedScholarship,
      'father_name': _fatherNameController.text.trim(),
      'father_phone': _fatherPhoneController.text.trim(),
      'father_job': _fatherJobController.text.trim(),
      'mother_name': _motherNameController.text.trim(),
      'mother_phone': _motherPhoneController.text.trim(),
      'mother_job': _motherJobController.text.trim(),
      'guardian_name': _guardianNameController.text.trim(),
      'guardian_job': _guardianJobController.text.trim(),
      'emergency_phone': _emergencyPhoneController.text.trim(),
      'grade_options': _gradeOptionValues,
    };

    if (_activeEnrollmentMode == 'MOEYS_INDIVIDUAL') {
      payload.addAll({
        'surname': _surnameController.text.trim(),
        'given_name': _givenNameController.text.trim(),
        'pob_commune': _pobCommuneController.text.trim(),
        'pob_district': _pobDistrictController.text.trim(),
        'pob_province': _pobProvinceController.text.trim(),
        'primary_school': _primarySchoolController.text.trim(),
        'secondary_school': _secondarySchoolController.text.trim(),
        'orphan_status': _orphanStatus,
        'ethnic_minority': _ethnicMinority,
        'disability_physical': _disabilityPhysical,
        'disability_sight': _disabilitySight,
        'disability_hearing': _disabilityHearing,
        'equity_card_1': _equityCard1,
        'equity_card_2': _equityCard2,
        'risk_card': _riskCard,
        'scholarship': _moeysScholarship,
        'track': _moeysTrack,
        'is_repeating_grade': _isRepeatingGrade,
      });
    }

    try {
      final res = await ApiClient().dio.post(
        ApiConstants.studentEnroll,
        data: payload,
      );

      setState(() => _isSubmitting = false);

      final data = res.data;
      if (data['status'] == 'success') {
        final student = data['student'] ?? {};
        final sid = student['student_id'] ?? '';
        final sName = student['khmer_name'] ?? khmerName;
        final cName = student['classroom_name'] ?? '';

        if (!mounted) return;

        showDialog(
          context: context,
          barrierDismissible: false,
          builder: (ctx) => AlertDialog(
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
            contentPadding: const EdgeInsets.all(24),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 70,
                  height: 70,
                  decoration: const BoxDecoration(
                    color: Color(0xFFDCFCE7),
                    shape: BoxShape.circle,
                  ),
                  child: const Center(
                    child: Icon(Icons.check_circle_rounded, color: AppColors.success, size: 44),
                  ),
                ),
                const SizedBox(height: 16),
                const Text(
                  "ចុះឈ្មោះបានជោគជ័យ!",
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
                ),
                const SizedBox(height: 8),
                Text(
                  "សិស្ស $sName ត្រូវបានបញ្ចូលទៅក្នុងថ្នាក់ $cName ដោយជោគជ័យ។",
                  textAlign: TextAlign.center,
                  style: const TextStyle(fontSize: 13, color: AppColors.textSecondary),
                ),
                const SizedBox(height: 16),
                Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: AppColors.bgLight,
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: AppColors.borderLight),
                  ),
                  child: Column(
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          const Text("អត្តលេខសិស្ស (ID):", style: TextStyle(fontSize: 12, color: AppColors.textSecondary)),
                          Text(sid, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: AppColors.primary)),
                        ],
                      ),
                      const Divider(height: 16),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          const Text("បែបបទចុះឈ្មោះ:", style: TextStyle(fontSize: 12, color: AppColors.textSecondary)),
                          Text(
                            _activeEnrollmentMode == 'MOEYS_INDIVIDUAL' ? "សម្រង់ព័ត៌មាន MoEYS" : "បែបបទ Admin កំណត់",
                            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
                          ),
                        ],
                      ),
                      const Divider(height: 16),
                      const Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text("ពាក្យសម្ងាត់ Login:", style: TextStyle(fontSize: 12, color: AppColors.textSecondary)),
                          Text("p123456", style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: AppColors.success)),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 20),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.primary,
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      padding: const EdgeInsets.symmetric(vertical: 12),
                    ),
                    onPressed: () {
                      Navigator.pop(ctx);
                      Navigator.pop(context);
                    },
                    child: const Text("រួចរាល់ / ត្រឡប់ក្រោយ", style: TextStyle(fontWeight: FontWeight.bold)),
                  ),
                ),
                const SizedBox(height: 8),
                TextButton(
                  onPressed: () {
                    Navigator.pop(ctx);
                    _resetForm();
                  },
                  child: const Text("ចុះឈ្មោះសិស្សម្នាក់ទៀត", style: TextStyle(color: AppColors.primaryLight)),
                ),
              ],
            ),
          ),
        );
      }
    } catch (e) {
      setState(() => _isSubmitting = false);
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

  void _resetForm() {
    _khmerNameController.clear();
    _latinNameController.clear();
    _phoneController.clear();
    _pobController.clear();
    _addressController.clear();
    _fatherNameController.clear();
    _fatherPhoneController.clear();
    _fatherJobController.clear();
    _motherNameController.clear();
    _motherPhoneController.clear();
    _motherJobController.clear();
    _guardianNameController.clear();
    _emergencyPhoneController.clear();

    _surnameController.clear();
    _givenNameController.clear();
    _pobCommuneController.clear();
    _pobDistrictController.clear();
    _pobProvinceController.clear();
    _primarySchoolController.clear();
    _secondarySchoolController.clear();
    _guardianJobController.clear();

    _orphanStatus = 'មិនមែន';
    _ethnicMinority = 'មិនមែន';
    _disabilityPhysical = 'មិនមាន';
    _disabilitySight = 'មិនមាន';
    _disabilityHearing = 'មិនមាន';
    _equityCard1 = 'មិនមាន';
    _equityCard2 = 'មិនមាន';
    _riskCard = 'មិនមាន';
    _moeysScholarship = 'មិនមាន';
    _moeysTrack = 'ទូទៅ';
    _isRepeatingGrade = false;

    _gradeOptionValues.clear();
    _fetchEnrollmentMeta();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bgLight,
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new, size: 20, color: AppColors.textPrimary),
          onPressed: () => Navigator.pop(context),
        ),
        title: const Text(
          "ចុះឈ្មោះចូលរៀនថ្មី (Admission)",
          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 17, color: AppColors.textPrimary),
        ),
      ),
      body: _isLoadingMeta
          ? const Center(child: SpinKitFadingCircle(color: AppColors.primary, size: 40))
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // School Info Banner
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      gradient: AppColors.primaryGradient,
                      borderRadius: BorderRadius.circular(18),
                      boxShadow: [
                        BoxShadow(
                          color: AppColors.primary.withValues(alpha: 0.25),
                          blurRadius: 12,
                          offset: const Offset(0, 4),
                        ),
                      ],
                    ),
                    child: Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.all(10),
                          decoration: BoxDecoration(
                            color: Colors.white.withValues(alpha: 0.2),
                            shape: BoxShape.circle,
                          ),
                          child: const Icon(Icons.app_registration_rounded, color: Colors.white, size: 26),
                        ),
                        const SizedBox(width: 14),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                _schoolName,
                                style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 15),
                              ),
                              const SizedBox(height: 2),
                              Text(
                                _activeEnrollmentMode == 'MOEYS_INDIVIDUAL'
                                    ? "សម្រង់ព័ត៌មានសិស្សម្នាក់ៗ MoEYS (ជំរឿន ៣៥ ជួរឈរ)"
                                    : "បំពេញបែបបទចុះឈ្មោះតាមការកំណត់របស់ Admin",
                                style: TextStyle(color: Colors.white.withValues(alpha: 0.85), fontSize: 12),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),

                  // Mode Switcher Tabs (Rendered if Admin allowed BOTH)
                  if (_registrationMode == 'BOTH') ...[
                    _buildModeSwitcher(),
                    const SizedBox(height: 18),
                  ],

                  // Render Form based on Active Mode
                  if (_activeEnrollmentMode == 'MOEYS_INDIVIDUAL')
                    ..._buildMoEYSFormSections()
                  else
                    ..._buildGeneralFormSections(),

                  // Dynamic Grade-Level Options (Filtered strictly by category)
                  _buildDynamicGradeOptionsSection(),
                  const SizedBox(height: 24),

                  // Submit Button
                  SizedBox(
                    width: double.infinity,
                    height: 52,
                    child: ElevatedButton(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.primary,
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                        elevation: 3,
                      ),
                      onPressed: _isSubmitting ? null : _submitEnrollment,
                      child: _isSubmitting
                          ? const SpinKitThreeBounce(color: Colors.white, size: 24)
                          : Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                const Icon(Icons.check_circle_outline, size: 22),
                                const SizedBox(width: 8),
                                Text(
                                  _activeEnrollmentMode == 'MOEYS_INDIVIDUAL'
                                      ? "រក្សាទុកសម្រង់ព័ត៌មានសិស្ស MoEYS"
                                      : "ចុះឈ្មោះសិស្សឥឡូវនេះ (Submit)",
                                  style: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
                                ),
                              ],
                            ),
                    ),
                  ),
                  const SizedBox(height: 24),
                ],
              ),
            ),
    );
  }

  // ---------------------------------------------------------------------------
  // DUAL MODE SWITCHER WIDGET
  // ---------------------------------------------------------------------------
  Widget _buildModeSwitcher() {
    final isGeneral = _activeEnrollmentMode == 'ADMIN_CUSTOM';
    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.borderLight),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.03),
            blurRadius: 6,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Row(
        children: [
          // Tab 1: General
          Expanded(
            child: InkWell(
              onTap: () => _switchEnrollmentMode('ADMIN_CUSTOM'),
              borderRadius: BorderRadius.circular(10),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                padding: const EdgeInsets.symmetric(vertical: 10),
                decoration: BoxDecoration(
                  color: isGeneral ? AppColors.primary : Colors.transparent,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(
                      Icons.tune_rounded,
                      size: 17,
                      color: isGeneral ? Colors.white : AppColors.textSecondary,
                    ),
                    const SizedBox(width: 6),
                    Text(
                      "បែបបទ Admin កំណត់",
                      style: TextStyle(
                        fontSize: 12.5,
                        fontWeight: isGeneral ? FontWeight.bold : FontWeight.w500,
                        color: isGeneral ? Colors.white : AppColors.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
          // Tab 2: MoEYS 35 Columns
          Expanded(
            child: InkWell(
              onTap: () => _switchEnrollmentMode('MOEYS_INDIVIDUAL'),
              borderRadius: BorderRadius.circular(10),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                padding: const EdgeInsets.symmetric(vertical: 10),
                decoration: BoxDecoration(
                  color: !isGeneral ? const Color(0xFF0284C7) : Colors.transparent,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(
                      Icons.table_chart_rounded,
                      size: 17,
                      color: !isGeneral ? Colors.white : AppColors.textSecondary,
                    ),
                    const SizedBox(width: 6),
                    Text(
                      "សម្រង់ព័ត៌មាន MoEYS",
                      style: TextStyle(
                        fontSize: 12.5,
                        fontWeight: !isGeneral ? FontWeight.bold : FontWeight.w500,
                        color: !isGeneral ? Colors.white : AppColors.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // OPTION 1: GENERAL ADMIN FORM SECTIONS
  // ---------------------------------------------------------------------------
  List<Widget> _buildGeneralFormSections() {
    return [
      _buildSectionHeader("១. ព័ត៌មានអត្តសញ្ញាណសិស្ស (Identity)", Icons.person_rounded),
      const SizedBox(height: 10),
      _buildCard(
        children: [
          _buildTextField(
            controller: _khmerNameController,
            label: "ឈ្មោះជាភាសាខ្មែរ (Khmer Name) *",
            hint: "ឧ. សុខ ពិសិដ្ឋ",
            icon: Icons.badge_outlined,
            onChanged: _onKhmerNameChanged,
          ),
          const SizedBox(height: 14),
          _buildTextField(
            controller: _latinNameController,
            label: "ឈ្មោះជាអក្សរឡាតាំង (Latin Name)",
            hint: "ឧ. SOK PISETH (ស្វ័យប្រវត្តិ)",
            icon: Icons.language_rounded,
          ),
          const SizedBox(height: 14),
          _buildGenderSelector(),
          const SizedBox(height: 14),
          _buildDobPicker(),
          const SizedBox(height: 14),
          _buildStudentIdField(),
        ],
      ),
      const SizedBox(height: 20),
      _buildSectionHeader("២. ព័ត៌មានថ្នាក់រៀន និងឆ្នាំសិក្សា", Icons.school_rounded),
      const SizedBox(height: 10),
      _buildCard(
        children: [
          _buildYearDropdown(),
          const SizedBox(height: 14),
          _buildClassroomDropdown(),
          const SizedBox(height: 14),
          _buildScholarshipDropdown(),
        ],
      ),
      const SizedBox(height: 20),
      _buildSectionHeader("៣. ទំនាក់ទំនង និងទីលំនៅ", Icons.location_on_rounded),
      const SizedBox(height: 10),
      _buildCard(
        children: [
          _buildTextField(
            controller: _phoneController,
            label: "លេខទូរស័ព្ទផ្ទាល់ខ្លួនសិស្ស (Phone)",
            hint: "ឧ. 012 345 678",
            icon: Icons.phone_android_rounded,
            keyboardType: TextInputType.phone,
          ),
          const SizedBox(height: 14),
          _buildTextField(
            controller: _pobController,
            label: "ទីកន្លែងកំណើត (Place of Birth)",
            hint: "ភូមិ, ឃុំ/សង្កាត់, ស្រុក/ខណ្ឌ, ខេត្ត/រាជធានី",
            icon: Icons.home_rounded,
          ),
          const SizedBox(height: 14),
          _buildTextField(
            controller: _addressController,
            label: "ទីលំនៅបច្ចុប្បន្ន (Current Address)",
            hint: "ផ្ទះលេខ, ផ្លូវ, ភូមិ, សង្កាត់, ខណ្ឌ",
            icon: Icons.pin_drop_rounded,
          ),
        ],
      ),
      const SizedBox(height: 20),
      _buildSectionHeader("៤. ព័ត៌មានឪពុកម្តាយ / អាណាព្យាបាល", Icons.family_restroom_rounded),
      const SizedBox(height: 10),
      _buildCard(
        children: [
          Row(
            children: [
              Expanded(
                child: _buildTextField(
                  controller: _fatherNameController,
                  label: "ឈ្មោះឪពុក",
                  hint: "ឈ្មោះឪពុក",
                  icon: Icons.person_outline,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _buildTextField(
                  controller: _fatherPhoneController,
                  label: "លេខទូរស័ព្ទឪពុក",
                  hint: "012 xxx xxx",
                  icon: Icons.phone_outlined,
                  keyboardType: TextInputType.phone,
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: _buildTextField(
                  controller: _motherNameController,
                  label: "ឈ្មោះម្តាយ",
                  hint: "ឈ្មោះម្តាយ",
                  icon: Icons.person_outline,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _buildTextField(
                  controller: _motherPhoneController,
                  label: "លេខទូរស័ព្ទម្តាយ",
                  hint: "012 xxx xxx",
                  icon: Icons.phone_outlined,
                  keyboardType: TextInputType.phone,
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          _buildTextField(
            controller: _guardianNameController,
            label: "ឈ្មោះអាណាព្យាបាល (ប្រសិនបើមាន)",
            hint: "ឈ្មោះអាណាព្យាបាល",
            icon: Icons.shield_outlined,
          ),
          const SizedBox(height: 14),
          _buildTextField(
            controller: _emergencyPhoneController,
            label: "លេខទូរស័ព្ទទំនាក់ទំនងបន្ទាន់",
            hint: "012 xxx xxx",
            icon: Icons.emergency_outlined,
            keyboardType: TextInputType.phone,
          ),
        ],
      ),
      const SizedBox(height: 20),
    ];
  }

  // ---------------------------------------------------------------------------
  // OPTION 2: MOEYS INDIVIDUAL 35-COLUMN CENSUS FORM SECTIONS
  // ---------------------------------------------------------------------------
  List<Widget> _buildMoEYSFormSections() {
    return [
      _buildSectionHeader("១. អត្តសញ្ញាណសិស្ស MoEYS (នាមត្រកូល & នាមខ្លួន)", Icons.badge_rounded),
      const SizedBox(height: 10),
      _buildCard(
        children: [
          Row(
            children: [
              Expanded(
                child: _buildTextField(
                  controller: _surnameController,
                  label: "នាមត្រកូល (Surname) *",
                  hint: "ឧ. សុខ",
                  icon: Icons.person_pin_rounded,
                  onChanged: (_) => _onMoEYSNameChanged(),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _buildTextField(
                  controller: _givenNameController,
                  label: "នាមខ្លួន (Given Name) *",
                  hint: "ឧ. ចិន្តា",
                  icon: Icons.person_outline,
                  onChanged: (_) => _onMoEYSNameChanged(),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          _buildTextField(
            controller: _latinNameController,
            label: "ឈ្មោះជាអក្សរឡាតាំង (Latin Name) *",
            hint: "e.g. SOK CHINDA",
            icon: Icons.language_rounded,
          ),
          const SizedBox(height: 14),
          _buildGenderSelector(),
          const SizedBox(height: 14),
          _buildDobPicker(),
          const SizedBox(height: 14),
          const Text(
            "ទីកន្លែងកំណើត (៣ ជួរឈរ MoEYS):",
            style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600, color: AppColors.textPrimary),
          ),
          const SizedBox(height: 8),
          _buildTextField(
            controller: _pobCommuneController,
            label: "ឃុំ/សង្កាត់កំណើត (POB Commune)",
            hint: "ឧ. សង្កាត់វត្តភ្នំ",
            icon: Icons.location_city_rounded,
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: _buildTextField(
                  controller: _pobDistrictController,
                  label: "ក្រុង/ស្រុក/ខណ្ឌកំណើត",
                  hint: "ឧ. ខណ្ឌដូនពេញ",
                  icon: Icons.map_outlined,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _buildTextField(
                  controller: _pobProvinceController,
                  label: "រាជធានី/ខេត្តកំណើត",
                  hint: "ឧ. រាជធានីភ្នំពេញ",
                  icon: Icons.terrain_rounded,
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          _buildStudentIdField(),
        ],
      ),
      const SizedBox(height: 20),

      _buildSectionHeader("២. ថ្នាក់រៀន គន្លងអប់រំ និងការត្រួតថ្នាក់", Icons.school_rounded),
      const SizedBox(height: 10),
      _buildCard(
        children: [
          _buildYearDropdown(),
          const SizedBox(height: 14),
          _buildClassroomDropdown(),
          const SizedBox(height: 14),
          DropdownButtonFormField<String>(
            initialValue: _moeysTrack,
            decoration: _inputDecoration("ជំនាញ / គន្លងអប់រំ (Track)", Icons.alt_route_rounded),
            items: [
              'ទូទៅ',
              'វិទ្យាសាស្ត្រ',
              'វិទ្យាសាស្ត្រសង្គម',
              'វិជ្ជាជីវៈ',
            ].map((t) => DropdownMenuItem(value: t, child: Text(t))).toList(),
            onChanged: (v) => setState(() => _moeysTrack = v ?? 'ទូទៅ'),
          ),
          const SizedBox(height: 14),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: AppColors.bgLight,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppColors.borderLight),
            ),
            child: Row(
              children: [
                Checkbox(
                  value: _isRepeatingGrade,
                  activeColor: AppColors.primary,
                  onChanged: (v) => setState(() => _isRepeatingGrade = v ?? false),
                ),
                const SizedBox(width: 6),
                const Expanded(
                  child: Text(
                    "ជាសិស្សត្រួតថ្នាក់ (Repeating Grade)",
                    style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.textPrimary),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),
          _buildScholarshipDropdown(),
        ],
      ),
      const SizedBox(height: 20),

      _buildSectionHeader("៣. ប្រវត្តិការសិក្សាពីមុន (Prior Education)", Icons.history_edu_rounded),
      const SizedBox(height: 10),
      _buildCard(
        children: [
          _buildTextField(
            controller: _primarySchoolController,
            label: "សាលាបឋមសិក្សាពីមុន (Primary School)",
            hint: "ឧ. បឋមសិក្សា ហ៊ុន សែន...",
            icon: Icons.school_outlined,
            onChanged: (v) {
              if (v.trim().isNotEmpty && _secondarySchoolController.text.isNotEmpty) {
                setState(() => _secondarySchoolController.clear());
              }
            },
          ),
          const SizedBox(height: 14),
          _buildTextField(
            controller: _secondarySchoolController,
            label: "គ្រឹះស្ថានមធ្យមសិក្សាពីមុន (Secondary School)",
            hint: "ឧ. អនុវិទ្យាល័យ / វិទ្យាល័យ...",
            icon: Icons.account_balance_outlined,
            onChanged: (v) {
              if (v.trim().isNotEmpty && _primarySchoolController.text.isNotEmpty) {
                setState(() => _primarySchoolController.clear());
              }
            },
          ),
        ],
      ),
      const SizedBox(height: 20),

      _buildSectionHeader("៤. ស្ថានភាពងាយរងគ្រោះ សមធម៌ និងពិការភាព (Census)", Icons.volunteer_activism_rounded),
      const SizedBox(height: 10),
      _buildCard(
        children: [
          DropdownButtonFormField<String>(
            initialValue: _orphanStatus,
            decoration: _inputDecoration("ស្ថានភាពកុមារកំព្រា (Orphan Status)", Icons.family_restroom_outlined),
            items: ['មិនមែន', 'កំព្រាឪពុក', 'កំព្រាម្តាយ', 'កំព្រាទាំងពីរ']
                .map((o) => DropdownMenuItem(value: o, child: Text(o)))
                .toList(),
            onChanged: (v) => setState(() => _orphanStatus = v ?? 'មិនមែន'),
          ),
          const SizedBox(height: 14),
          DropdownButtonFormField<String>(
            initialValue: _ethnicMinority,
            decoration: _inputDecoration("ជនជាតិដើមភាគតិច (Ethnic Minority)", Icons.groups_outlined),
            items: ['មិនមែន', 'ជនជាតិដើមភាគតិច', 'ផ្សេងៗ']
                .map((m) => DropdownMenuItem(value: m, child: Text(m)))
                .toList(),
            onChanged: (v) => setState(() => _ethnicMinority = v ?? 'មិនមែន'),
          ),
          const SizedBox(height: 14),
          DropdownButtonFormField<String>(
            initialValue: _disabilityPhysical,
            decoration: _inputDecoration("ពិការភាពកាយសម្បទា (Physical)", Icons.accessible_forward_rounded),
            items: ['មិនមាន', 'ពិការដៃ', 'ពិការជើង', 'ពិការរាងកាយ', 'ផ្សេងៗ']
                .map((d) => DropdownMenuItem(value: d, child: Text(d)))
                .toList(),
            onChanged: (v) => setState(() => _disabilityPhysical = v ?? 'មិនមាន'),
          ),
          const SizedBox(height: 14),
          DropdownButtonFormField<String>(
            initialValue: _disabilitySight,
            decoration: _inputDecoration("ពិការភាពគំហើញ (Sight)", Icons.visibility_off_outlined),
            items: ['មិនមាន', 'ពិការភ្នែកទាំងសងខាង', 'ពិការភ្នែកម្ខាង', 'មើលមិនសូវច្បាស់']
                .map((d) => DropdownMenuItem(value: d, child: Text(d)))
                .toList(),
            onChanged: (v) => setState(() => _disabilitySight = v ?? 'មិនមាន'),
          ),
          const SizedBox(height: 14),
          DropdownButtonFormField<String>(
            initialValue: _disabilityHearing,
            decoration: _inputDecoration("ពិការភាពការស្តាប់ (Hearing)", Icons.hearing_disabled_rounded),
            items: ['មិនមាន', 'ថ្លង់ទាំងសងខាង', 'ថ្លង់ម្ខាង', 'គរ', 'ស្តាប់មិនសូវឮ']
                .map((d) => DropdownMenuItem(value: d, child: Text(d)))
                .toList(),
            onChanged: (v) => setState(() => _disabilityHearing = v ?? 'មិនមាន'),
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: DropdownButtonFormField<String>(
                  value: _equityCard1,
                  decoration: _inputDecoration("ប័ណ្ណសមធម៌ក្រ១", Icons.credit_card_rounded),
                  items: ['មិនមាន', 'មាន'].map((e) => DropdownMenuItem(value: e, child: Text(e))).toList(),
                  onChanged: (v) => setState(() {
                    _equityCard1 = v ?? 'មិនមាន';
                    if (_equityCard1 != 'មិនមាន') {
                      _equityCard2 = 'មិនមាន';
                    }
                  }),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: DropdownButtonFormField<String>(
                  value: _equityCard2,
                  decoration: _inputDecoration("ប័ណ្ណសមធម៌ក្រ២", Icons.credit_card_rounded),
                  items: ['មិនមាន', 'មាន'].map((e) => DropdownMenuItem(value: e, child: Text(e))).toList(),
                  onChanged: (v) => setState(() {
                    _equityCard2 = v ?? 'មិនមាន';
                    if (_equityCard2 != 'មិនមាន') {
                      _equityCard1 = 'មិនមាន';
                    }
                  }),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: DropdownButtonFormField<String>(
                  initialValue: _riskCard,
                  decoration: _inputDecoration("ប័ណ្ណហានិភ័យ", Icons.warning_amber_rounded),
                  items: ['មិនមាន', 'មាន'].map((r) => DropdownMenuItem(value: r, child: Text(r))).toList(),
                  onChanged: (v) => setState(() => _riskCard = v ?? 'មិនមាន'),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: DropdownButtonFormField<String>(
                  initialValue: _moeysScholarship,
                  decoration: _inputDecoration("អាហារូបករណ៍រដ្ឋ/អង្គការ", Icons.card_giftcard_rounded),
                  items: ['មិនមាន', 'អាហារូបករណ៍រដ្ឋ', 'អាហារូបករណ៍អង្គការ', 'អាហារូបករណ៍សាលា', 'ផ្សេងៗ']
                      .map((s) => DropdownMenuItem(value: s, child: Text(s)))
                      .toList(),
                  onChanged: (v) => setState(() => _moeysScholarship = v ?? 'មិនមាន'),
                ),
              ),
            ],
          ),
        ],
      ),
      const SizedBox(height: 20),

      _buildSectionHeader("៥. ព័ត៌មានឪពុកម្តាយ និងមុខរបរ", Icons.people_alt_rounded),
      const SizedBox(height: 10),
      _buildCard(
        children: [
          Row(
            children: [
              Expanded(
                child: _buildTextField(
                  controller: _fatherNameController,
                  label: "ឈ្មោះឪពុក",
                  hint: "ឈ្មោះឪពុក",
                  icon: Icons.person_outline,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _buildTextField(
                  controller: _fatherJobController,
                  label: "មុខរបរឪពុក",
                  hint: "មុខរបរឪពុក",
                  icon: Icons.work_outline,
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          _buildTextField(
            controller: _fatherPhoneController,
            label: "លេខទូរស័ព្ទឪពុក",
            hint: "012 xxx xxx",
            icon: Icons.phone_outlined,
            keyboardType: TextInputType.phone,
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: _buildTextField(
                  controller: _motherNameController,
                  label: "ឈ្មោះម្តាយ",
                  hint: "ឈ្មោះម្តាយ",
                  icon: Icons.person_outline,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _buildTextField(
                  controller: _motherJobController,
                  label: "មុខរបរម្តាយ",
                  hint: "មុខរបរម្តាយ",
                  icon: Icons.work_outline,
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          _buildTextField(
            controller: _motherPhoneController,
            label: "លេខទូរស័ព្ទម្តាយ",
            hint: "012 xxx xxx",
            icon: Icons.phone_outlined,
            keyboardType: TextInputType.phone,
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: _buildTextField(
                  controller: _guardianNameController,
                  label: "ឈ្មោះអាណាព្យាបាលជំនួស",
                  hint: "ឈ្មោះអាណាព្យាបាល",
                  icon: Icons.shield_outlined,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _buildTextField(
                  controller: _guardianJobController,
                  label: "មុខរបរអាណាព្យាបាល",
                  hint: "មុខរបរ",
                  icon: Icons.work_outline,
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          _buildTextField(
            controller: _phoneController,
            label: "លេខទូរស័ព្ទសិស្ស/ទំនាក់ទំនងបន្ទាន់",
            hint: "012 xxx xxx",
            icon: Icons.phone_android_rounded,
            keyboardType: TextInputType.phone,
          ),
        ],
      ),
      const SizedBox(height: 20),
    ];
  }

  // ---------------------------------------------------------------------------
  // DYNAMIC GRADE OPTIONS WIDGET (SEPARATED BY CATEGORY)
  // ---------------------------------------------------------------------------
  Widget _buildDynamicGradeOptionsSection() {
    if (_isLoadingGradeOptions) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 16),
        child: Center(child: SpinKitThreeBounce(color: AppColors.primary, size: 20)),
      );
    }

    if (_gradeOptions.isEmpty) {
      return const SizedBox.shrink();
    }

    final headerTitle = _activeEnrollmentMode == 'MOEYS_INDIVIDUAL'
        ? "ជម្រើសបន្ថែមតាមកម្រិតថ្នាក់ (សម្រង់ព័ត៌មាន MoEYS)"
        : "ជម្រើសបន្ថែមតាមកម្រិតថ្នាក់ (Admin កំណត់)";

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildSectionHeader(headerTitle, Icons.dynamic_form_rounded),
        const SizedBox(height: 10),
        _buildCard(
          children: _gradeOptions.map<Widget>((opt) {
            final fieldName = opt['field_name']?.toString() ?? '';
            final label = opt['label']?.toString() ?? '';
            final fieldType = opt['field_type']?.toString() ?? 'TEXT';
            final isRequired = opt['is_required'] == true;
            final choices = (opt['choices'] as List<dynamic>?) ?? [];
            final placeholder = opt['placeholder']?.toString() ?? '';

            final displayLabel = "$label${isRequired ? ' *' : ''}";

            if (fieldType == 'CHECKBOX') {
              final currentVal = _gradeOptionValues[fieldName] == true;
              return Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  decoration: BoxDecoration(
                    color: AppColors.bgLight,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppColors.borderLight),
                  ),
                  child: Row(
                    children: [
                      Checkbox(
                        value: currentVal,
                        activeColor: AppColors.primary,
                        onChanged: (v) {
                          setState(() {
                            _gradeOptionValues[fieldName] = v ?? false;
                          });
                        },
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          displayLabel,
                          style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.textPrimary),
                        ),
                      ),
                    ],
                  ),
                ),
              );
            }

            if (fieldType == 'SELECT' || fieldType == 'RADIO') {
              final currentVal = _gradeOptionValues[fieldName]?.toString();
              return Padding(
                padding: const EdgeInsets.only(bottom: 14),
                child: DropdownButtonFormField<String>(
                  initialValue: choices.contains(currentVal) ? currentVal : null,
                  decoration: _inputDecoration(displayLabel, Icons.arrow_drop_down_circle_outlined),
                  hint: Text(placeholder.isNotEmpty ? placeholder : "-- ជ្រើសរើស --"),
                  items: choices.map<DropdownMenuItem<String>>((c) {
                    return DropdownMenuItem<String>(
                      value: c.toString(),
                      child: Text(c.toString()),
                    );
                  }).toList(),
                  onChanged: (v) {
                    setState(() {
                      _gradeOptionValues[fieldName] = v;
                    });
                  },
                ),
              );
            }

            // Default Text/Number/Date input
            return Padding(
              padding: const EdgeInsets.only(bottom: 14),
              child: TextField(
                keyboardType: fieldType == 'NUMBER'
                    ? TextInputType.number
                    : (fieldType == 'PHONE' ? TextInputType.phone : TextInputType.text),
                maxLines: fieldType == 'TEXTAREA' ? 3 : 1,
                onChanged: (v) => _gradeOptionValues[fieldName] = v.trim(),
                decoration: InputDecoration(
                  labelText: displayLabel,
                  hintText: placeholder.isNotEmpty ? placeholder : label,
                  prefixIcon: const Icon(Icons.edit_note_rounded, color: AppColors.primary, size: 20),
                  filled: true,
                  fillColor: AppColors.bgLight,
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: AppColors.borderLight)),
                  enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: AppColors.borderLight)),
                  focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: AppColors.primary, width: 1.8)),
                ),
              ),
            );
          }).toList(),
        ),
      ],
    );
  }

  // ---------------------------------------------------------------------------
  // REUSABLE SUB-WIDGETS & INPUT FIELDS
  // ---------------------------------------------------------------------------
  Widget _buildGenderSelector() {
    return Row(
      children: [
        const Text("ភេទ (Gender):", style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.textPrimary)),
        const SizedBox(width: 16),
        ChoiceChip(
          label: const Text("ប្រុស (M)"),
          selected: _gender == 'M',
          selectedColor: AppColors.primaryLight.withValues(alpha: 0.3),
          onSelected: (val) => setState(() => _gender = 'M'),
        ),
        const SizedBox(width: 10),
        ChoiceChip(
          label: const Text("ស្រី (F)"),
          selected: _gender == 'F',
          selectedColor: const Color(0xFFF472B6).withValues(alpha: 0.3),
          onSelected: (val) => setState(() => _gender = 'F'),
        ),
      ],
    );
  }

  Widget _buildDobPicker() {
    return InkWell(
      onTap: () async {
        final picked = await showDatePicker(
          context: context,
          initialDate: _dateOfBirth,
          firstDate: DateTime(1990),
          lastDate: DateTime.now(),
        );
        if (picked != null) setState(() => _dateOfBirth = picked);
      },
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        decoration: BoxDecoration(
          border: Border.all(color: AppColors.borderLight),
          borderRadius: BorderRadius.circular(12),
          color: Colors.white,
        ),
        child: Row(
          children: [
            const Icon(Icons.calendar_today_rounded, size: 20, color: AppColors.primary),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text("ថ្ងៃខែឆ្នាំកំណើត (DOB)", style: TextStyle(fontSize: 11, color: AppColors.textSecondary)),
                  Text(DateFormat('dd/MM/yyyy').format(_dateOfBirth), style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
                ],
              ),
            ),
            const Icon(Icons.arrow_drop_down, color: AppColors.textSecondary),
          ],
        ),
      ),
    );
  }

  Widget _buildStudentIdField() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildTextField(
          controller: _customIdController,
          label: "លេខសម្គាល់សិស្ស (Student ID)",
          hint: "ទុកទទេដើម្បីបង្កើតស្វ័យប្រវត្តិ ($_suggestedId)",
          icon: Icons.confirmation_number_outlined,
          onChanged: _onCustomIdChanged,
          suffix: _isCheckingId
              ? const Padding(padding: EdgeInsets.all(12), child: SpinKitFadingCircle(color: AppColors.primary, size: 18))
              : (_isIdAvailable != null
                  ? Icon(
                      _isIdAvailable! ? Icons.check_circle : Icons.cancel,
                      color: _isIdAvailable! ? AppColors.success : AppColors.danger,
                      size: 20,
                    )
                  : null),
        ),
        if (_idCheckMessage.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 6, left: 4),
            child: Text(
              _idCheckMessage,
              style: TextStyle(
                fontSize: 11.5,
                color: _isIdAvailable == true ? AppColors.success : AppColors.danger,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
      ],
    );
  }

  Widget _buildYearDropdown() {
    return DropdownButtonFormField<int>(
      initialValue: _selectedYearId,
      decoration: _inputDecoration("ឆ្នាំសិក្សា (Academic Year)", Icons.event_note_rounded),
      items: _academicYears.map<DropdownMenuItem<int>>((y) {
        return DropdownMenuItem<int>(
          value: y['id'],
          child: Text("${y['name']} ${y['is_current'] == true ? '(ឆ្នាំបច្ចុប្បន្ន)' : ''}"),
        );
      }).toList(),
      onChanged: (v) {
        setState(() => _selectedYearId = v);
        if (_customIdController.text.isNotEmpty) {
          _onCustomIdChanged(_customIdController.text);
        }
      },
    );
  }

  Widget _buildClassroomDropdown() {
    return DropdownButtonFormField<int>(
      initialValue: _selectedClassroomId,
      decoration: _inputDecoration("ជ្រើសរើសថ្នាក់រៀន (Classroom)", Icons.meeting_room_rounded),
      items: _classrooms.map<DropdownMenuItem<int>>((c) {
        return DropdownMenuItem<int>(
          value: c['id'],
          child: Text("${c['name']} (ថ្នាក់ទី ${c['grade_level']})"),
        );
      }).toList(),
      onChanged: (v) {
        setState(() => _selectedClassroomId = v);
        _fetchGradeOptions();
      },
    );
  }

  Widget _buildScholarshipDropdown() {
    return DropdownButtonFormField<String>(
      initialValue: _selectedScholarship,
      decoration: _inputDecoration("ប្រភេទថ្លៃសិក្សា / អាហារូបករណ៍", Icons.card_giftcard_rounded),
      items: _scholarshipTypes.map<DropdownMenuItem<String>>((s) {
        return DropdownMenuItem<String>(
          value: s['code'],
          child: Text(s['label'] ?? s['code']),
        );
      }).toList(),
      onChanged: (v) => setState(() => _selectedScholarship = v ?? 'FULL_PAY'),
    );
  }

  Widget _buildSectionHeader(String title, IconData icon) {
    return Row(
      children: [
        Icon(icon, size: 20, color: AppColors.primary),
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            title,
            style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
          ),
        ),
      ],
    );
  }

  Widget _buildCard({required List<Widget> children}) {
    return Container(
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
        children: children,
      ),
    );
  }

  Widget _buildTextField({
    required TextEditingController controller,
    required String label,
    required String hint,
    required IconData icon,
    TextInputType keyboardType = TextInputType.text,
    ValueChanged<String>? onChanged,
    Widget? suffix,
  }) {
    return TextField(
      controller: controller,
      keyboardType: keyboardType,
      onChanged: onChanged,
      decoration: InputDecoration(
        labelText: label,
        hintText: hint,
        prefixIcon: Icon(icon, color: AppColors.primary, size: 20),
        suffixIcon: suffix,
        filled: true,
        fillColor: AppColors.bgLight,
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: AppColors.borderLight)),
        enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: AppColors.borderLight)),
        focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: AppColors.primary, width: 1.8)),
      ),
    );
  }

  InputDecoration _inputDecoration(String label, IconData icon) {
    return InputDecoration(
      labelText: label,
      prefixIcon: Icon(icon, color: AppColors.primary, size: 20),
      filled: true,
      fillColor: AppColors.bgLight,
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: AppColors.borderLight)),
      enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: AppColors.borderLight)),
      focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: AppColors.primary, width: 1.8)),
    );
  }
}
