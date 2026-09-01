"""
Comprehensive Bilingual Translation Service for SchoolSM.
Provides clean separation between Khmer (ភាសាខ្មែរ) and English.
"""

from typing import Dict, Any, Optional

DEFAULT_LANGUAGE = 'km'
SUPPORTED_LANGUAGES = {
    'km': {
        'code': 'km',
        'name': 'ភាសាខ្មែរ',
        'english_name': 'Khmer',
        'flag': '🇰🇭',
    },
    'en': {
        'code': 'en',
        'name': 'English',
        'english_name': 'English',
        'flag': '🇬🇧',
    }
}

# Master UI Translation Dictionary
TRANSLATIONS: Dict[str, Dict[str, str]] = {
    # System & Roles
    'school_sm': {'km': 'សាលារៀន SM', 'en': 'SchoolSM'},
    'super_admin': {'km': 'អ្នកគ្រប់គ្រងប្រព័ន្ធ', 'en': 'Super Admin'},
    'accountant': {'km': 'គណនេយ្យករ', 'en': 'Accountant'},
    'teacher': {'km': 'គ្រូបង្រៀន', 'en': 'Teacher'},
    'student': {'km': 'សិស្ស-អាណាព្យាបាល', 'en': 'Student / Parent'},
    'switch_demo_role': {'km': 'ប្តូរ Role សាកល្បង', 'en': 'Switch Demo Role'},
    'system_settings': {'km': 'ការកំណត់ប្រព័ន្ធ', 'en': 'System Settings'},
    'logout': {'km': 'ចាកចេញ', 'en': 'Logout'},
    'my_profile': {'km': 'គណនីរបស់ខ្ញុំ', 'en': 'My Profile'},
    'academic_year': {'km': 'ឆ្នាំសិក្សា', 'en': 'Academic Year'},
    'current_badge': {'km': 'បច្ចុប្បន្ន', 'en': 'Current'},

    # Common Actions & Buttons
    'search': {'km': 'ស្វែងរក...', 'en': 'Search...'},
    'search_placeholder': {'km': 'ស្វែងរក ID, ឈ្មោះ, ថ្នាក់...', 'en': 'Search ID, Name, Class...'},
    'add_new': {'km': 'បន្ថែមថ្មី', 'en': 'Add New'},
    'save': {'km': 'រក្សាទុក', 'en': 'Save'},
    'save_changes': {'km': 'រក្សាទុកការកែប្រែ', 'en': 'Save Changes'},
    'edit': {'km': 'កែប្រែ', 'en': 'Edit'},
    'delete': {'km': 'លុប', 'en': 'Delete'},
    'cancel': {'km': 'បោះបង់', 'en': 'Cancel'},
    'close': {'km': 'បិទ', 'en': 'Close'},
    'back': {'km': 'ថយក្រោយ', 'en': 'Back'},
    'view': {'km': 'មើលព័ត៌មាន', 'en': 'View Details'},
    'view_detail': {'km': 'មើលលម្អិត', 'en': 'View Detail'},
    'export_excel': {'km': 'ទាញយក Excel', 'en': 'Export Excel'},
    'export_csv': {'km': 'ទាញយក CSV', 'en': 'Export CSV'},
    'import_excel': {'km': 'នាំចូល Excel / CSV', 'en': 'Import Excel / CSV'},
    'filter': {'km': 'ចម្រាញ់', 'en': 'Filter'},
    'reset_filter': {'km': 'កំណត់ឡើងវិញ', 'en': 'Reset Filter'},
    'actions': {'km': 'សកម្មភាព', 'en': 'Actions'},
    'status': {'km': 'ស្ថានភាព', 'en': 'Status'},
    'all': {'km': 'ទាំងអស់', 'en': 'All'},
    'total': {'km': 'សរុប', 'en': 'Total'},
    'active': {'km': 'សកម្ម', 'en': 'Active'},
    'inactive': {'km': 'អសកម្ម', 'en': 'Inactive'},
    'pending': {'km': 'រង់ចាំការអនុម័ត', 'en': 'Pending'},
    'approved': {'km': 'បានអនុម័ត', 'en': 'Approved'},
    'rejected': {'km': 'បានបដិសេធ', 'en': 'Rejected'},
    'success': {'km': 'ជោគជ័យ', 'en': 'Success'},
    'error': {'km': 'កំហុស', 'en': 'Error'},
    'warning': {'km': 'ការព្រមាន', 'en': 'Warning'},
    'confirm': {'km': 'បញ្ជាក់', 'en': 'Confirm'},
    'print': {'km': 'បោះពុម្ព', 'en': 'Print'},
    'print_preview': {'km': 'ទិដ្ឋភាពមុនព្រីន', 'en': 'Print Preview'},
    'download': {'km': 'ទាញយក', 'en': 'Download'},
    'upload': {'km': 'ផ្ទុកឡើង', 'en': 'Upload'},
    'no_data': {'km': 'រកមិនឃើញទិន្នន័យឡើយ', 'en': 'No data found'},
    'no_data_desc': {'km': 'មិនមានទិន្នន័យសម្រាប់បង្ហាញក្នុងផ្នែកនេះឡើយ។', 'en': 'There is no data to display in this section.'},

    # Student Module
    'all_students': {'km': 'បញ្ជីសិស្សទាំងអស់', 'en': 'All Students Directory'},
    'student_directory': {'km': 'បញ្ជីសិស្ស', 'en': 'Student Directory'},
    'enroll_student': {'km': 'ចុះឈ្មោះសិស្សថ្មី', 'en': 'Enroll New Student'},
    'online_enroll_qr': {'km': 'QR ចុះឈ្មោះ Online', 'en': 'Online Registration QR'},
    'academic_status': {'km': 'ស្ថានភាពសិក្សា', 'en': 'Academic Status'},
    'student_id': {'km': 'អត្តលេខសិស្ស', 'en': 'Student ID'},
    'student_name': {'km': 'ឈ្មោះសិស្ស', 'en': 'Student Name'},
    'khmer_name': {'km': 'ឈ្មោះជាភាសាខ្មែរ', 'en': 'Khmer Name'},
    'latin_name': {'km': 'ឈ្មោះជាអក្សរឡាតាំង', 'en': 'Latin Name'},
    'gender': {'km': 'ភេទ', 'en': 'Gender'},
    'male': {'km': 'ប្រុស', 'en': 'Male'},
    'female': {'km': 'ស្រី', 'en': 'Female'},
    'date_of_birth': {'km': 'ថ្ងៃខែឆ្នាំកំណើត', 'en': 'Date of Birth'},
    'place_of_birth': {'km': 'ទីកន្លែងកំណើត', 'en': 'Place of Birth'},
    'current_address': {'km': 'អាសយដ្ឋានបច្ចុប្បន្ន', 'en': 'Current Address'},
    'phone_number': {'km': 'លេខទូរស័ព្ទ', 'en': 'Phone Number'},
    'guardian_name': {'km': 'ឈ្មោះអាណាព្យាបាល', 'en': 'Guardian Name'},
    'guardian_phone': {'km': 'ទូរស័ព្ទអាណាព្យាបាល', 'en': 'Guardian Phone'},
    'classroom': {'km': 'ថ្នាក់រៀន', 'en': 'Classroom'},
    'classrooms': {'km': 'ថ្នាក់រៀនទាំងអស់', 'en': 'Classrooms'},
    'grade_level': {'km': 'កម្រិតថ្នាក់', 'en': 'Grade Level'},
    'academic_track': {'km': 'ផ្នែក/Track', 'en': 'Academic Track'},
    'homeroom_teacher': {'km': 'គ្រូបន្ទុកថ្នាក់', 'en': 'Homeroom Teacher'},
    'scholarship_type': {'km': 'ប្រភេទអាហារូបករណ៍', 'en': 'Scholarship Type'},
    'full_pay': {'km': 'បង់ថ្លៃពេញ', 'en': 'Full Pay'},
    'scholarship_50': {'km': 'អាហារូបករណ៍ 50%', 'en': '50% Scholarship'},
    'scholarship_100': {'km': 'អាហារូបករណ៍ 100% (ឥតគិតថ្លៃ)', 'en': '100% Scholarship (Free)'},
    'exam_status': {'km': 'សិទ្ធិប្រឡង', 'en': 'Exam Status'},
    'exam_eligible': {'km': 'មានសិទ្ធិប្រឡង', 'en': 'Eligible for Exam'},
    'exam_suspended': {'km': 'ព្យួរការប្រឡង', 'en': 'Exam Suspended'},
    'total_students_count': {'km': 'សិស្សសរុប៖', 'en': 'Total Students:'},
    'student_promotion': {'km': 'ឡើងថ្នាក់ & ត្រួតថ្នាក់', 'en': 'Student Promotion & Retention'},

    # Subjects & Scoring
    'subjects': {'km': 'មុខវិជ្ជាសិក្សា', 'en': 'Subjects'},
    'subject_name': {'km': 'ឈ្មោះមុខវិជ្ជា', 'en': 'Subject Name'},
    'subject_code': {'km': 'កូដមុខវិជ្ជា', 'en': 'Subject Code'},
    'weekly_hours': {'km': 'ម៉ោងក្នុងមួយសប្តាហ៍', 'en': 'Weekly Hours'},
    'examinations': {'km': 'ការប្រឡង & ពិន្ទុ', 'en': 'Examinations & Scoring'},
    'exam_terms': {'km': 'ឆមាស & លក្ខខណ្ឌប្រឡង', 'en': 'Exam Terms & Sessions'},
    'monthly_scores': {'km': 'បញ្ចូលពិន្ទុប្រចាំខែ', 'en': 'Monthly Score Entry'},
    'semester_scores': {'km': 'ពិន្ទុឆមាស', 'en': 'Semester Scores'},
    'report_cards': {'km': 'ប័ណ្ណពិន្ទុ & ចំណាត់ថ្នាក់', 'en': 'Report Cards & Ranking'},
    'rank': {'km': 'ចំណាត់ថ្នាក់', 'en': 'Rank'},
    'average': {'km': 'មធ្យមភាគ', 'en': 'Average'},

    # Timetable & Duty
    'timetable': {'km': 'កាលវិភាគសិក្សា', 'en': 'Timetable'},
    'master_timetable': {'km': 'កាលវិភាគរួម', 'en': 'Master Timetable'},
    'daily_duty_reports': {'km': 'របាយការណ៍ប្រចាំថ្ងៃ', 'en': 'Daily Duty Reports'},
    'student_teacher_timetable': {'km': 'កាលវិភាគសិស្ស-គ្រូ', 'en': 'Student & Teacher Timetable'},
    'subject_requirements': {'km': 'មុខវិជ្ជា និងម៉ោងសិក្សា', 'en': 'Subject Requirements & Hours'},
    'teacher_assignments': {'km': 'ចាត់តាំងគ្រូបង្រៀនតាមថ្នាក់', 'en': 'Teacher Class Assignments'},
    'teacher_duty_schedule': {'km': 'គ្រប់គ្រងម៉ោងប្រចាំការ', 'en': 'Teacher Duty Schedule'},
    'timetable_versions': {'km': 'កំណែកាលវិភាគប្រចាំឆ្នាំ', 'en': 'Timetable Revision Versions'},
    'print_pages_config': {'km': 'កំណត់ទំព័រព្រីន', 'en': 'Print Pages Config'},

    # Teachers & Staff
    'teachers_and_staff': {'km': 'គ្រូបង្រៀន & បុគ្គលិក', 'en': 'Teachers & Staff'},
    'teacher_directory': {'km': 'បញ្ជីគ្រូបង្រៀន', 'en': 'Teacher Directory'},
    'add_teacher': {'km': 'បញ្ចូលគ្រូថ្មី', 'en': 'Add New Teacher'},
    'teacher_attendance': {'km': 'វត្តមានគ្រូបង្រៀន', 'en': 'Teacher Attendance'},
    'kiosk_attendance': {'km': 'ស្កេនវត្តមាន Kiosk', 'en': 'Kiosk Attendance Scan'},
    'biometric_hub': {'km': 'ប្រព័ន្ធស្កេនមុខ & ម្រាមដៃ', 'en': 'Biometric & Face Hub'},
    'leave_requests': {'km': 'ច្បាប់ឈប់សម្រាក', 'en': 'Leave Requests'},

    # Finance & Utilities
    'finance': {'km': 'ហិរញ្ញវត្ថុ & ប្រាក់ចំណូល', 'en': 'Finance & Invoices'},
    'invoices': {'km': 'វិក្កយបត្រ & ការទូទាត់', 'en': 'Invoices & Payments'},
    'utility_bills': {'km': 'ថ្លៃទឹកភ្លើង & ប្រចាំខែ', 'en': 'Utility & Monthly Bills'},
    'financial_reports': {'km': 'របាយការណ៍ហិរញ្ញវត្ថុ', 'en': 'Financial Reports'},

    # Days of week
    'monday': {'km': 'ច័ន្ទ', 'en': 'Monday'},
    'tuesday': {'km': 'អង្គារ', 'en': 'Tuesday'},
    'wednesday': {'km': 'ពុធ', 'en': 'Wednesday'},
    'thursday': {'km': 'ព្រហស្បតិ៍', 'en': 'Thursday'},
    'friday': {'km': 'សុក្រ', 'en': 'Friday'},
    'saturday': {'km': 'សៅរ៍', 'en': 'Saturday'},
    'sunday': {'km': 'អាទិត្យ', 'en': 'Sunday'},

    # Sessions
    'morning_shift': {'km': 'ពេលព្រឹក', 'en': 'Morning Shift'},
    'afternoon_shift': {'km': 'ពេលរសៀល', 'en': 'Afternoon Shift'},
    'all_sessions': {'km': 'ទាំង២ពេល (ព្រឹក & រសៀល)', 'en': 'Both Shifts (Morning & Afternoon)'},
}


def get_current_language(request) -> str:
    """
    Resolves the current active language code ('km' or 'en').
    Priority:
      1. Request GET/POST parameter (if setting language)
      2. Session 'django_language'
      3. Cookie 'django_language'
      4. User account language_preference (if authenticated)
      5. Default to 'km'
    """
    if not request:
        return DEFAULT_LANGUAGE

    # 1. Check Session
    if hasattr(request, 'session') and request.session.get('django_language'):
        lang = str(request.session.get('django_language')).lower().strip()
        if lang in SUPPORTED_LANGUAGES:
            return lang

    # 2. Check Cookie
    if hasattr(request, 'COOKIES') and request.COOKIES.get('django_language'):
        lang = str(request.COOKIES.get('django_language')).lower().strip()
        if lang in SUPPORTED_LANGUAGES:
            return lang

    # 3. Check Authenticated User Preference
    user = getattr(request, 'user', None)
    if user and user.is_authenticated:
        user_lang = getattr(user, 'language_preference', None)
        if user_lang and user_lang in SUPPORTED_LANGUAGES:
            return user_lang

    return DEFAULT_LANGUAGE


def set_current_language(request, response, lang_code: str):
    """
    Stores language preference in session, cookie, and user model if authenticated.
    """
    if lang_code not in SUPPORTED_LANGUAGES:
        lang_code = DEFAULT_LANGUAGE

    if hasattr(request, 'session'):
        request.session['django_language'] = lang_code

    if response:
        response.set_cookie('django_language', lang_code, max_age=365*24*3600, httponly=False, samesite='Lax')

    user = getattr(request, 'user', None)
    if user and user.is_authenticated:
        if hasattr(user, 'language_preference') and user.language_preference != lang_code:
            user.language_preference = lang_code
            user.save(update_fields=['language_preference'])


def t(key: str, lang: str = 'km', default: Optional[str] = None) -> str:
    """
    Translates a key into the target language.
    Falls back to default, or the other language, or the key itself.
    """
    lang = lang if lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
    entry = TRANSLATIONS.get(key)
    if entry and lang in entry:
        return entry[lang]

    if default is not None:
        return default

    # Fallback to key
    return key.replace('_', ' ').title()


class TranslationProxy:
    """
    Proxy object allowing dict-like or property-like translation lookup in templates:
    e.g. {{ t.all_students }}, {{ t.enroll_student }}, {{ t.save }}
    """
    def __init__(self, lang: str = 'km'):
        self.lang = lang

    def __getitem__(self, item):
        return t(str(item), self.lang)

    def __getattr__(self, item):
        return t(str(item), self.lang)

    def __call__(self, key, default=None):
        return t(key, self.lang, default)
