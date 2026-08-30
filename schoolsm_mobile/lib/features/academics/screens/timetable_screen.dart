import 'package:flutter/material.dart';
import 'package:flutter_spinkit/flutter_spinkit.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/api_constants.dart';
import '../../../core/api/api_client.dart';

class TimetableScreen extends StatefulWidget {
  const TimetableScreen({super.key});

  @override
  State<TimetableScreen> createState() => _TimetableScreenState();
}

class _TimetableScreenState extends State<TimetableScreen> {
  final List<Map<String, String>> _days = [
    {'key': 'MON', 'label': 'ច័ន្ទ'},
    {'key': 'TUE', 'label': 'អង្គារ'},
    {'key': 'WED', 'label': 'ពុធ'},
    {'key': 'THU', 'label': 'ព្រហ'},
    {'key': 'FRI', 'label': 'សុក្រ'},
    {'key': 'SAT', 'label': 'សៅរ៍'},
  ];

  String _selectedDay = 'MON';
  bool _isLoading = true;
  List<dynamic> _timetable = [];
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _fetchTimetable();
  }

  Future<void> _fetchTimetable() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final res = await ApiClient().dio.get(
        ApiConstants.timetable,
        queryParameters: {'day': _selectedDay},
      );
      setState(() {
        _timetable = res.data['timetable'] ?? [];
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _errorMessage = ApiClient.getErrorMessage(e);
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bgLight,
      appBar: AppBar(
        title: const Text("កាលវិភាគបង្រៀន & រៀន", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
        backgroundColor: Colors.white,
        foregroundColor: AppColors.textPrimary,
        elevation: 0,
      ),
      body: Column(
        children: [
          // Day Selector Tabs
          Container(
            padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 16),
            color: Colors.white,
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: _days.map((d) {
                  final isSelected = _selectedDay == d['key'];
                  return Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: ChoiceChip(
                      label: Text(d['label']!),
                      selected: isSelected,
                      selectedColor: AppColors.primary,
                      backgroundColor: AppColors.bgLight,
                      labelStyle: TextStyle(
                        color: isSelected ? Colors.white : AppColors.textPrimary,
                        fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                      ),
                      onSelected: (selected) {
                        if (selected) {
                          setState(() => _selectedDay = d['key']!);
                          _fetchTimetable();
                        }
                      },
                    ),
                  );
                }).toList(),
              ),
            ),
          ),
          const Divider(height: 1),

          // Timetable List
          Expanded(
            child: _isLoading
                ? const Center(child: SpinKitFadingCircle(color: AppColors.primary, size: 40))
                : _errorMessage != null
                    ? Center(child: Text(_errorMessage!, style: const TextStyle(color: AppColors.textSecondary)))
                    : _timetable.isEmpty
                        ? const Center(
                            child: Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Icon(Icons.event_busy, size: 54, color: AppColors.textSecondary),
                                SizedBox(height: 12),
                                Text("គ្មានកាលវិភាគសម្រាប់ថ្ងៃនេះទេ", style: TextStyle(color: AppColors.textSecondary)),
                              ],
                            ),
                          )
                        : RefreshIndicator(
                            onRefresh: _fetchTimetable,
                            child: ListView.separated(
                              padding: const EdgeInsets.all(16),
                              itemCount: _timetable.length,
                              separatorBuilder: (_, __) => const SizedBox(height: 12),
                              itemBuilder: (ctx, index) {
                                final item = _timetable[index];
                                final subject = item['subject_name'] ?? 'មុខវិជ្ជា';
                                final teacher = item['teacher_name'] ?? '';
                                final classroom = item['classroom_name'] ?? '';
                                final room = item['room'] ?? '';
                                final period = item['period_number'];
                                final start = item['start_time'] ?? '';
                                final end = item['end_time'] ?? '';

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
                                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                                        decoration: BoxDecoration(
                                          color: AppColors.primary.withOpacity(0.1),
                                          borderRadius: BorderRadius.circular(12),
                                        ),
                                        child: Column(
                                          children: [
                                            Text(
                                              period != null ? "ម៉ោង $period" : "ម៉ោង",
                                              style: const TextStyle(color: AppColors.primary, fontWeight: FontWeight.bold, fontSize: 12),
                                            ),
                                            const SizedBox(height: 2),
                                            Text(
                                              "$start\n$end",
                                              textAlign: TextAlign.center,
                                              style: const TextStyle(fontSize: 10, color: AppColors.textSecondary),
                                            ),
                                          ],
                                        ),
                                      ),
                                      const SizedBox(width: 16),
                                      Expanded(
                                        child: Column(
                                          crossAxisAlignment: CrossAxisAlignment.start,
                                          children: [
                                            Text(
                                              subject,
                                              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                                            ),
                                            const SizedBox(height: 4),
                                            if (teacher.isNotEmpty)
                                              Row(
                                                children: [
                                                  const Icon(Icons.person, size: 14, color: AppColors.textSecondary),
                                                  const SizedBox(width: 4),
                                                  Text("គ្រូ: $teacher", style: const TextStyle(fontSize: 12, color: AppColors.textSecondary)),
                                                ],
                                              ),
                                            if (classroom.isNotEmpty)
                                              Row(
                                                children: [
                                                  const Icon(Icons.class_, size: 14, color: AppColors.textSecondary),
                                                  const SizedBox(width: 4),
                                                  Text("ថ្នាក់: $classroom ${room.isNotEmpty ? '• បន្ទប់: $room' : ''}", style: const TextStyle(fontSize: 12, color: AppColors.textSecondary)),
                                                ],
                                              ),
                                          ],
                                        ),
                                      ),
                                    ],
                                  ),
                                );
                              },
                            ),
                          ),
          ),
        ],
      ),
    );
  }
}
