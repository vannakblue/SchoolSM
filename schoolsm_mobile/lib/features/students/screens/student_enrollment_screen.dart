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

  // Metadata from backend
  List<dynamic> _academicYears = [];
  List<dynamic> _classrooms = [];
  List<dynamic> _scholarshipTypes = [];
  String _suggestedId = '';
  String _schoolName = 'SchoolSM';

  // Form Controllers
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
    final khmerName = _khmerNameController.text.trim();
    if (khmerName.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text("សូមបញ្ចូលឈ្មោះជាភាសាខ្មែរ!"),
          backgroundColor: AppColors.danger,
        ),
      );
      return;
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

    final payload = {
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
      'emergency_phone': _emergencyPhoneController.text.trim(),
    };

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
                      Navigator.pop(ctx); // Close dialog
                      Navigator.pop(context); // Return to previous screen
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
    _motherNameController.clear();
    _motherPhoneController.clear();
    _guardianNameController.clear();
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
                                "បំពេញព័ត៌មានខាងក្រោមដើម្បីចុះឈ្មោះសិស្សថ្មី",
                                style: TextStyle(color: Colors.white.withValues(alpha: 0.85), fontSize: 12),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 18),

                  // -------------------------------------------------------------
                  // SECTION 1: Student Identity
                  // -------------------------------------------------------------
                  _buildSectionHeader("១. ព័ត៌មានអត្តសញ្ញាណសិស្ស (Student Identity)", Icons.person_rounded),
                  const SizedBox(height: 10),
                  _buildCard(
                    children: [
                      // Khmer Name
                      _buildTextField(
                        controller: _khmerNameController,
                        label: "ឈ្មោះជាភាសាខ្មែរ (Khmer Name) *",
                        hint: "ឧ. សុខ ពិសិដ្ឋ",
                        icon: Icons.badge_outlined,
                        onChanged: _onKhmerNameChanged,
                      ),
                      const SizedBox(height: 14),

                      // Latin Name
                      _buildTextField(
                        controller: _latinNameController,
                        label: "ឈ្មោះជាអក្សរឡាតាំង (Latin Name)",
                        hint: "ឧ. SOK PISETH (ស្វ័យប្រវត្តិ)",
                        icon: Icons.language_rounded,
                      ),
                      const SizedBox(height: 14),

                      // Gender Chips
                      Row(
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
                      ),
                      const SizedBox(height: 14),

                      // Date of Birth Picker
                      InkWell(
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
                      ),
                      const SizedBox(height: 14),

                      // Student ID Input with Real-time Check
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
                  ),
                  const SizedBox(height: 20),

                  // -------------------------------------------------------------
                  // SECTION 2: Academic Placement
                  // -------------------------------------------------------------
                  _buildSectionHeader("២. ព័ត៌មានថ្នាក់រៀន និងឆ្នាំសិក្សា", Icons.school_rounded),
                  const SizedBox(height: 10),
                  _buildCard(
                    children: [
                      // Academic Year Dropdown
                      DropdownButtonFormField<int>(
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
                      ),
                      const SizedBox(height: 14),

                      // Classroom Dropdown
                      DropdownButtonFormField<int>(
                        initialValue: _selectedClassroomId,
                        decoration: _inputDecoration("ជ្រើសរើសថ្នាក់រៀន (Classroom)", Icons.meeting_room_rounded),
                        items: _classrooms.map<DropdownMenuItem<int>>((c) {
                          return DropdownMenuItem<int>(
                            value: c['id'],
                            child: Text("${c['name']} (ថ្នាក់ទី ${c['grade_level']})"),
                          );
                        }).toList(),
                        onChanged: (v) => setState(() => _selectedClassroomId = v),
                      ),
                      const SizedBox(height: 14),

                      // Scholarship Type
                      DropdownButtonFormField<String>(
                        initialValue: _selectedScholarship,
                        decoration: _inputDecoration("ប្រភេទថ្លៃសិក្សា / អាហារូបករណ៍", Icons.card_giftcard_rounded),
                        items: _scholarshipTypes.map<DropdownMenuItem<String>>((s) {
                          return DropdownMenuItem<String>(
                            value: s['code'],
                            child: Text(s['label'] ?? s['code']),
                          );
                        }).toList(),
                        onChanged: (v) => setState(() => _selectedScholarship = v ?? 'FULL_PAY'),
                      ),
                    ],
                  ),
                  const SizedBox(height: 20),

                  // -------------------------------------------------------------
                  // SECTION 3: Contact & Address
                  // -------------------------------------------------------------
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

                  // -------------------------------------------------------------
                  // SECTION 4: Parents / Guardian
                  // -------------------------------------------------------------
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
                        label: "ឈ្មោះអាណាព្យាបាល (ប្រសិនបើមិននៅជាមួយឪពុកម្តាយ)",
                        hint: "ឈ្មោះអាណាព្យាបាល",
                        icon: Icons.shield_outlined,
                      ),
                      const SizedBox(height: 14),
                      _buildTextField(
                        controller: _emergencyPhoneController,
                        label: "លេខទូរស័ព្ទទំនាក់ទំនងបន្ទាន់ (Emergency Phone)",
                        hint: "012 xxx xxx",
                        icon: Icons.emergency_outlined,
                        keyboardType: TextInputType.phone,
                      ),
                    ],
                  ),
                  const SizedBox(height: 28),

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
                          : const Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Icon(Icons.check_circle_outline, size: 22),
                                SizedBox(width: 8),
                                Text(
                                  "ចុះឈ្មោះសិស្សឥឡូវនេះ (Submit)",
                                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
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

  Widget _buildSectionHeader(String title, IconData icon) {
    return Row(
      children: [
        Icon(icon, size: 20, color: AppColors.primary),
        const SizedBox(width: 8),
        Text(
          title,
          style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
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
