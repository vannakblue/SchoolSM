"""
Global Omnisearch Engine for SchoolSM.
Provides high-speed synonym-aware keyword search across all system menus,
features, students, classrooms, and administrative tools.
"""

from django.urls import reverse, NoReverseMatch
from apps.accounts.models import MenuSection, MenuItem, User
from apps.students.models import Student
from apps.academics.models import Classroom

# Pre-indexed keywords and synonyms mapped to destinations
STATIC_KEYWORDS_INDEX = [
    {
        'title_kh': 'សៀវភៅតាមដានការសិក្សា & ប្រវត្តិរូបសិស្ស',
        'title_en': 'Student Tracking Book & Directory',
        'category': 'សិស្ស & ការសិក្សា (Students)',
        'icon': 'fa-solid fa-address-book text-primary',
        'url_name': 'student_list',
        'custom_url': None,
        'keywords': ['សៀវភៅតាមដាន', 'តាមដានការសិក្សា', 'ប្រវត្តិរូបសិស្ស', 'បញ្ជីសិស្ស', 'student directory', 'tracking book', 'កាតសិស្ស', 'កូដសិស្ស']
    },
    {
        'title_kh': 'ប័ណ្ណពិន្ទុប្រចាំខែ & តារាងចំណាត់ថ្នាក់សិស្ស',
        'title_en': 'Monthly Report Cards & Grade Summary',
        'category': 'ការប្រឡង & ពិន្ទុ (Exams)',
        'icon': 'fa-solid fa-ranking-star text-warning',
        'url_name': 'grade_summary',
        'custom_url': None,
        'keywords': ['ប័ណ្ណពិន្ទុ', 'ប័ណ្ណពិន្ទុប្រចាំខែ', 'ព្រឹត្តិបត្រពិន្ទុ', 'ចំណាត់ថ្នាក់', 'និទ្ទេស', 'report card', 'transcript', 'rankings', 'លទ្ធផលប្រឡង']
    },
    {
        'title_kh': 'បញ្ចូលពិន្ទុសិស្សតាមថ្នាក់រៀន (Grade Entry Matrix)',
        'title_en': 'Classroom Grade Entry Matrix',
        'category': 'ការប្រឡង & ពិន្ទុ (Exams)',
        'icon': 'fa-solid fa-pen-to-square text-success',
        'url_name': 'grade_entry_matrix',
        'custom_url': None,
        'keywords': ['បញ្ចូលពិន្ទុ', 'បញ្ចូលពិន្ទុតាមថ្នាក់', 'ពិន្ទុ', 'grade entry', 'គ្រូបញ្ចូលពិន្ទុ', 'ពិន្ទុប្រចាំខែ']
    },
    {
        'title_kh': 'ការបង់ថ្លៃសិក្សា វិក្កយបត្រ & ការចំណាយ (ទឹកភ្លើង)',
        'title_en': 'Student Fee Invoices & Utility Billing',
        'category': 'ហិរញ្ញវត្ថុ & គណនេយ្យ (Finance)',
        'icon': 'fa-solid fa-file-invoice-dollar text-success',
        'url_name': 'invoice_list',
        'custom_url': None,
        'keywords': ['ការបង់ទឹកភ្លើង', 'ទឹកភ្លើង', 'វិក្កយបត្រ', 'បង់ប្រាក់', 'ថ្លៃសិក្សា', 'invoices', 'billing', 'utilities', 'ចំណាយ', 'ចំណូល']
    },
    {
        'title_kh': 'ប្រភេទកម្រៃសិក្សា & ប្រភេទទឹកភ្លើង/សេវា',
        'title_en': 'Fee & Service Categories',
        'category': 'ហិរញ្ញវត្ថុ & គណនេយ្យ (Finance)',
        'icon': 'fa-solid fa-tags text-info',
        'url_name': 'fee_category_list',
        'custom_url': None,
        'keywords': ['ប្រភេទកម្រៃ', 'ថ្លៃទឹកភ្លើង', 'កម្រៃសិក្សា', 'fee categories', 'សេវាកម្ម']
    },
    {
        'title_kh': 'តេស្តស្តង់ដា & បញ្ចូលពិន្ទុតាមបន្ទប់ (១-២៥ នាក់)',
        'title_en': 'Standardized Room-Based Exams',
        'category': 'ការប្រឡង & ពិន្ទុ (Exams)',
        'icon': 'fa-solid fa-door-open text-primary',
        'url_name': 'standardized_exam_list',
        'custom_url': None,
        'keywords': ['តេស្តស្តង់ដា', 'ប្រឡងតាមបន្ទប់', 'បន្ទប់ប្រឡង', 'standardized exam', 'mock exam', 'បាក់ឌុប', 'ឌុប្លូម', 'លេខតុ', 'លេខកូដសម្ងាត់']
    },
    {
        'title_kh': 'ស្រង់វត្តមានសិស្សប្រចាំថ្ងៃ',
        'title_en': 'Daily Student Attendance',
        'category': 'វត្តមាន (Attendance)',
        'icon': 'fa-solid fa-clipboard-user text-danger',
        'url_name': 'student_attendance_grid',
        'custom_url': None,
        'keywords': ['វត្តមាន', 'ស្រង់វត្តមាន', 'អវត្តមាន', 'attendance', 'ច្បាប់', 'ឥតច្បាប់']
    },
    {
        'title_kh': 'កាលវិភាគបង្រៀន & ម៉ោងសិក្សា (Master Timetable)',
        'title_en': 'Master Timetable Matrix',
        'category': 'កាលវិភាគ (Timetable)',
        'icon': 'fa-solid fa-calendar-days text-info',
        'url_name': 'timetable_view',
        'custom_url': None,
        'keywords': ['កាលវិភាគ', 'កាលវិភាគបង្រៀន', 'ម៉ោងបង្រៀន', 'timetable', 'schedule', 'កាលវិភាគថ្នាក់', 'នាំចេញកាលវិភាគ', 'នាំចូលកាលវិភាគ']
    },
    {
        'title_kh': 'គ្រប់គ្រងគ្រូ & ចាត់តាំងថ្នាក់បង្រៀន (Teacher Assignments)',
        'title_en': 'Teacher Class & Subject Assignments',
        'category': 'កាលវិភាគ & គ្រូបង្រៀន (Timetable & Teachers)',
        'icon': 'fa-solid fa-chalkboard-user text-primary',
        'url_name': 'teacher_assignments_manager',
        'custom_url': None,
        'keywords': ['ចាត់តាំងគ្រូ', 'ចាត់ថ្នាក់', 'គ្រូបង្រៀន', 'teacher assignment', 'ម៉ោងគ្រូ', 'បង្រៀនមុខវិជ្ជា']
    },
    {
        'title_kh': 'បញ្ចូល & នាំចេញគ្រូបង្រៀនពី Excel (Teacher Import/Export)',
        'title_en': 'Bulk Teacher Import & Excel Export',
        'category': 'គ្រូបង្រៀន (Teachers)',
        'icon': 'fa-solid fa-file-excel text-success',
        'url_name': 'teacher_import',
        'custom_url': None,
        'keywords': ['នាំចូលគ្រូ', 'នាំចេញគ្រូ', 'បញ្ចូលគ្រូ', 'import teacher', 'export teacher', 'បញ្ជីគ្រូ excel', 'ទម្រង់គំរូគ្រូ']
    },
    {
        'title_kh': 'បញ្ជីគ្រូបង្រៀនទាំងអស់ & វត្តមាន (Teacher Directory)',
        'title_en': 'All Teachers Directory',
        'category': 'គ្រូបង្រៀន (Teachers)',
        'icon': 'fa-solid fa-users text-primary',
        'url_name': 'teacher_list',
        'custom_url': None,
        'keywords': ['បញ្ជីគ្រូ', 'គ្រូបង្រៀន', 'teacher list', 'teachers', 'ប្រវត្តិរូបគ្រូ', 'ប្រាក់ខែគ្រូ']
    },
    {
        'title_kh': 'ច្បាប់ពិន្ទុ & ជំនាញសិក្សាតាមកម្រិតថ្នាក់ (Scoring Rules & Tracks)',
        'title_en': 'MoEYS Scoring Rules Matrix & Academic Tracks',
        'category': 'ការកំណត់ប្រព័ន្ធ (Settings)',
        'icon': 'fa-solid fa-scale-balanced text-primary',
        'url_name': 'grade_rules_manager',
        'custom_url': None,
        'keywords': ['ច្បាប់ពិន្ទុ', 'ពិន្ទុពេញ', 'មេគុណ', 'scoring rules', 'moeys rules', 'រូបមន្តពិន្ទុ', 'ជំនាញសិក្សា', 'ប្រភេទកម្រិតថ្នាក់', 'កម្មវិធីសិក្សា', 'tracks', 'academic tracks', 'វិទ្យាសាស្ត្រ', 'សង្គម', 'បច្ចេកទេស', 'ទូទៅ']
    },
    {
        'title_kh': 'ព័ត៌មានសាលារៀន ផែនទី Google Maps ឡូហ្គោ & ត្រា',
        'title_en': 'School Profile, Google Maps & Identity',
        'category': 'ការកំណត់ប្រព័ន្ធ (Settings)',
        'icon': 'fa-solid fa-school-flag text-warning',
        'url_name': 'school_profile_settings',
        'custom_url': None,
        'keywords': ['ព័ត៌មានសាលា', 'ផែនទី', 'google maps', 'gps', 'ត្រាសាលា', 'ឡូហ្គោ', 'school profile', 'emis']
    },
    {
        'title_kh': 'គ្រប់គ្រងគណនីអ្នកប្រើប្រាស់ (User Management)',
        'title_en': 'User Accounts Management & Password Reset',
        'category': 'ការកំណត់ប្រព័ន្ធ (Settings)',
        'icon': 'fa-solid fa-users-gear text-primary',
        'url_name': 'user_management',
        'custom_url': None,
        'keywords': ['គ្រប់គ្រងគណនី', 'user management', 'users', 'គណនី', 'reset password', 'ប្តូរ password', 'បង្កើត user', 'username', 'accounts', 'ចាក់សោគណនី']
    },
    {
        'title_kh': 'កំណត់សិទ្ធិ Menu & Submenu តាមតួនាទី',
        'title_en': 'Role Menu & Submenu Permissions',
        'category': 'ការកំណត់ប្រព័ន្ធ (Settings)',
        'icon': 'fa-solid fa-shield-halved text-danger',
        'url_name': 'menu_permissions',
        'custom_url': None,
        'keywords': ['កំណត់សិទ្ធិ', 'សិទ្ធិ', 'menu permissions', 'role permissions', 'សិទ្ធិគ្រូ', 'សិទ្ធិសិស្ស']
    },
    {
        'title_kh': 'ការកំណត់ Telegram Notifications & Bot',
        'title_en': 'Telegram Bot Notification Settings',
        'category': 'ការកំណត់ប្រព័ន្ធ (Settings)',
        'icon': 'fa-brands fa-telegram text-info',
        'url_name': 'telegram_settings',
        'custom_url': None,
        'keywords': ['telegram', 'telegram bot', 'ការជូនដំណឹង', 'bot token', 'chat id', 'notify']
    },
    {
        'title_kh': 'របាយការណ៍ស្ថិតិអប់រំ MoEYS EMIS',
        'title_en': 'MoEYS Official Education Reports',
        'category': 'របាយការណ៍ (Reports)',
        'icon': 'fa-solid fa-file-waveform text-success',
        'url_name': 'moeys_reports',
        'custom_url': None,
        'keywords': ['របាយការណ៍', 'moeys', 'ស្ថិតិ', 'emis', 'របាយការណ៍ក្រសួង']
    },
    {
        'title_kh': 'បណ្ណាល័យសាលា & ការខ្ចី-សងសៀវភៅ',
        'title_en': 'School Library & Book Borrowing',
        'category': 'បណ្ណាល័យ (Library)',
        'icon': 'fa-solid fa-book-bookmark text-primary',
        'url_name': 'book_list',
        'custom_url': None,
        'keywords': ['បណ្ណាល័យ', 'សៀវភៅ', 'ខ្ចីសៀវភៅ', 'library', 'books', 'book_list']
    }
]


def global_omnisearch(query, user=None, limit=10):
    """
    Search across static keywords, dynamic menus, students, and classrooms.
    Returns list of matched results with highlight badges and direct URLs.
    """
    query = (query or '').strip().lower()
    if not query:
        # Return popular quick links if query is empty
        return _get_top_shortcuts(user, limit)

    results = []
    seen_urls = set()

    # 1. Search Static Keywords & Synonyms Index
    for item in STATIC_KEYWORDS_INDEX:
        match = False
        if query in item['title_kh'].lower() or query in item['title_en'].lower() or query in item['category'].lower():
            match = True
        else:
            for kw in item['keywords']:
                if query in kw.lower() or kw.lower() in query:
                    match = True
                    break

        if match:
            url = None
            if item['url_name']:
                try:
                    url = reverse(item['url_name'])
                except NoReverseMatch:
                    url = item['custom_url'] or '#'
            else:
                url = item['custom_url'] or '#'

            if url and url not in seen_urls:
                seen_urls.add(url)
                results.append({
                    'type': 'MENU',
                    'title_kh': item['title_kh'],
                    'title_en': item['title_en'],
                    'category': item['category'],
                    'icon': item['icon'],
                    'url': url
                })

    # 2. Search Database Menu Items
    db_items = MenuItem.objects.filter(is_active=True).select_related('section')
    for mi in db_items:
        if query in mi.name_kh.lower() or query in mi.name_en.lower() or query in mi.code.lower() or query in mi.section.name_kh.lower():
            url = mi.get_url
            if url and url not in seen_urls:
                seen_urls.add(url)
                results.append({
                    'type': 'MENU',
                    'title_kh': mi.name_kh,
                    'title_en': mi.name_en,
                    'category': mi.section.name_kh,
                    'icon': mi.icon or mi.section.icon,
                    'url': url
                })

    # 3. Search Students by Name or ID
    students = Student.objects.filter(
        status='ACTIVE'
    ).filter(
        models_q_student(query)
    ).select_related('classroom')[:4]

    for s in students:
        s_url = reverse('student_detail', kwargs={'pk': s.pk})
        if s_url not in seen_urls:
            seen_urls.add(s_url)
            results.append({
                'type': 'STUDENT',
                'title_kh': f"{s.khmer_name} ({s.student_id})",
                'title_en': f"{s.latin_name} - ថ្នាក់ {s.classroom.name if s.classroom else 'គ្មានថ្នាក់'}",
                'category': 'សិស្ស (Student 360°)',
                'icon': 'fa-solid fa-user-graduate text-success',
                'url': s_url
            })

    # 4. Search Classrooms
    classrooms = Classroom.objects.filter(name__icontains=query)[:3]
    for c in classrooms:
        c_url = f"{reverse('grade_summary')}?classroom={c.id}"
        if c_url not in seen_urls:
            seen_urls.add(c_url)
            results.append({
                'type': 'CLASSROOM',
                'title_kh': f"ថ្នាក់រៀន {c.name} ({c.get_track_display()})",
                'title_en': f"កម្រិតទី {c.grade_level} - ចំនួនសិស្ស: {c.students.count()} នាក់",
                'category': 'ថ្នាក់រៀន (Classroom)',
                'icon': 'fa-solid fa-chalkboard-user text-info',
                'url': c_url
            })

    return results[:limit]


def models_q_student(query):
    from django.db.models import Q
    return (
        Q(khmer_name__icontains=query) |
        Q(latin_name__icontains=query) |
        Q(student_id__icontains=query) |
        Q(phone__icontains=query)
    )


def _get_top_shortcuts(user=None, limit=8):
    shortcuts = []
    for item in STATIC_KEYWORDS_INDEX[:limit]:
        url = None
        if item['url_name']:
            try:
                url = reverse(item['url_name'])
            except NoReverseMatch:
                url = item['custom_url'] or '#'
        else:
            url = item['custom_url'] or '#'

        shortcuts.append({
            'type': 'SHORTCUT',
            'title_kh': item['title_kh'],
            'title_en': item['title_en'],
            'category': item['category'],
            'icon': item['icon'],
            'url': url
        })
    return shortcuts
