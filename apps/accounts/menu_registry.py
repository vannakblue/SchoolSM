"""
Centralized Registry of All System Menus & Submenus.
Defines catalog hierarchy, descriptions, icons, and default allowed roles.
Provides helpers to retrieve, update, and evaluate role permissions.
"""

from typing import Dict, List, Any, Set
from .models import RoleMenuPermission, User

# Complete Catalog of System Navigation
MENU_SECTIONS_CATALOG = [
    {
        'key': 'sec_dashboard',
        'name_kh': 'ផ្ទាំងគ្រប់គ្រង',
        'name_en': 'Dashboard',
        'icon': 'fa-solid fa-gauge-high',
        'color': 'secondary',
        'default_roles': ['ADMIN', 'TEACHER', 'STUDENT', 'ACCOUNTANT'],
        'items': [
            {
                'key': 'admin_dashboard',
                'name_kh': 'ផ្ទាំងគ្រប់គ្រងទូទៅ',
                'name_en': 'Admin Dashboard',
                'icon': 'fa-solid fa-gauge-high',
                'default_roles': ['ADMIN'],
                'url_name': 'admin_dashboard',
                'is_admin_only': True,
            },
            {
                'key': 'moeys_reports',
                'name_kh': 'ស្ថិតិអប់រំ MoEYS',
                'name_en': 'MoEYS EMIS Statistics',
                'icon': 'fa-solid fa-file-waveform text-info',
                'default_roles': ['ADMIN', 'ACCOUNTANT'],
                'url_name': 'moeys_reports',
            },
            {
                'key': 'finance_dashboard',
                'name_kh': 'ផ្ទាំងគណនេយ្យករ',
                'name_en': 'Accountant Dashboard',
                'icon': 'fa-solid fa-wallet',
                'default_roles': ['ADMIN', 'ACCOUNTANT'],
                'url_name': 'finance_dashboard',
            },
            {
                'key': 'teacher_dashboard',
                'name_kh': 'ផ្ទាំងគ្រូបង្រៀន',
                'name_en': 'Teacher Dashboard',
                'icon': 'fa-solid fa-chalkboard-user',
                'default_roles': ['ADMIN', 'TEACHER'],
                'url_name': 'teacher_dashboard',
            },
            {
                'key': 'student_dashboard',
                'name_kh': 'ផ្ទាំងសិស្ស-អាណាព្យាបាល',
                'name_en': 'Student & Parent Portal',
                'icon': 'fa-solid fa-user-graduate',
                'default_roles': ['ADMIN', 'STUDENT'],
                'url_name': 'student_dashboard',
            },
            {
                'key': 'announcement_list',
                'name_kh': 'សេចក្តីជូនដំណឹង',
                'name_en': 'Announcements & Notices',
                'icon': 'fa-solid fa-bullhorn text-warning',
                'default_roles': ['ADMIN', 'TEACHER', 'STUDENT', 'ACCOUNTANT'],
                'url_name': 'announcement_list',
            },
        ]
    },
    {
        'key': 'sec_students',
        'name_kh': 'គ្រប់គ្រងសិស្ស & ការសិក្សា',
        'name_en': 'Students & Academics',
        'icon': 'fa-solid fa-graduation-cap',
        'color': 'info',
        'default_roles': ['ADMIN', 'TEACHER', 'ACCOUNTANT'],
        'items': [
            {
                'key': 'student_list',
                'name_kh': 'បញ្ជីសិស្ស',
                'name_en': 'Student Directory',
                'icon': 'fa-solid fa-users',
                'default_roles': ['ADMIN', 'TEACHER', 'ACCOUNTANT'],
                'url_name': 'student_list',
            },
            {
                'key': 'student_enroll',
                'name_kh': 'ចុះឈ្មោះសិស្សថ្មី',
                'name_en': 'New Student Enrollment',
                'icon': 'fa-solid fa-user-plus',
                'default_roles': ['ADMIN'],
                'url_name': 'student_enroll',
            },
            {
                'key': 'classroom_list',
                'name_kh': 'ថ្នាក់រៀន',
                'name_en': 'Classrooms Management',
                'icon': 'fa-solid fa-school',
                'default_roles': ['ADMIN'],
                'url_name': 'classroom_list',
            },
            {
                'key': 'subject_list',
                'name_kh': 'មុខវិជ្ជាសិក្សា',
                'name_en': 'Subjects & Curriculum',
                'icon': 'fa-solid fa-book-bookmark',
                'default_roles': ['ADMIN'],
                'url_name': 'subject_list',
            },
            {
                'key': 'academic_year_list',
                'name_kh': 'ឆ្នាំសិក្សា',
                'name_en': 'Academic Years Setup',
                'icon': 'fa-solid fa-calendar-days text-primary',
                'default_roles': ['ADMIN'],
                'url_name': 'academic_year_list',
            },
            {
                'key': 'grade_options_manager',
                'name_kh': 'បែបបទតាមកម្រិតថ្នាក់',
                'name_en': 'Grade Options & Templates',
                'icon': 'fa-solid fa-sliders text-primary',
                'default_roles': ['ADMIN'],
                'url_name': 'grade_options_manager',
            },
            {
                'key': 'student_promotion',
                'name_kh': 'ផ្ទេរ/ឡើងថ្នាក់',
                'name_en': 'Student Promotion & Transfer',
                'icon': 'fa-solid fa-arrow-up-right-dots',
                'default_roles': ['ADMIN'],
                'url_name': 'student_promotion',
            },
            {
                'key': 'student_status_list',
                'name_kh': 'ស្ថានភាពសិក្សា',
                'name_en': 'Student Statuses Config',
                'icon': 'fa-solid fa-tags text-info',
                'default_roles': ['ADMIN'],
                'url_name': 'student_status_list',
            },
        ]
    },
    {
        'key': 'sec_timetable',
        'name_kh': 'កាលវិភាគ & គ្រូបង្រៀន',
        'name_en': 'Timetable & Scheduling',
        'icon': 'fa-solid fa-calendar-alt',
        'color': 'primary',
        'default_roles': ['ADMIN', 'TEACHER', 'STUDENT'],
        'items': [
            {
                'key': 'timetable_view',
                'name_kh': 'កាលវិភាគរួម',
                'name_en': 'Master Timetable Matrix',
                'icon': 'fa-solid fa-calendar-days text-primary',
                'default_roles': ['ADMIN', 'TEACHER'],
                'url_name': 'timetable_view',
            },
            {
                'key': 'timetable_daily_reports_view',
                'name_kh': 'របាយការណ៍ប្រចាំថ្ងៃ',
                'name_en': 'Daily Duty & Teaching Log',
                'icon': 'fa-solid fa-file-signature text-purple',
                'default_roles': ['ADMIN', 'TEACHER'],
                'url_name': 'timetable_daily_reports_view',
            },
            {
                'key': 'student_teacher_timetable_view',
                'name_kh': 'កាលវិភាគសិស្ស-គ្រូ',
                'name_en': 'Student-Teacher Schedule Card',
                'icon': 'fa-solid fa-print text-success',
                'default_roles': ['ADMIN', 'TEACHER', 'STUDENT'],
                'url_name': 'student_teacher_timetable_view',
            },
            {
                'key': 'subject_requirements_manager',
                'name_kh': 'មុខវិជ្ជា & ម៉ោងសិក្សា',
                'name_en': 'Subject Hours Requirements',
                'icon': 'fa-solid fa-sliders text-info',
                'default_roles': ['ADMIN'],
                'url_name': 'subject_requirements_manager',
            },
            {
                'key': 'teacher_assignments_manager',
                'name_kh': 'គ្រប់គ្រងគ្រូ & ចាត់តាំងថ្នាក់',
                'name_en': 'Teacher Class Assignments',
                'icon': 'fa-solid fa-chalkboard-user text-warning',
                'default_roles': ['ADMIN'],
                'url_name': 'teacher_assignments_manager',
            },
            {
                'key': 'teacher_duty_manager',
                'name_kh': 'គ្រប់គ្រងម៉ោងប្រចាំការ',
                'name_en': 'Duty Hours & Staff Roster',
                'icon': 'fa-solid fa-clock text-danger',
                'default_roles': ['ADMIN', 'TEACHER'],
                'url_name': 'teacher_duty_manager',
            },
        ]
    },
    {
        'key': 'sec_attendance',
        'name_kh': 'គ្រប់គ្រងវត្តមាន',
        'name_en': 'Attendance Management',
        'icon': 'fa-solid fa-clipboard-user',
        'color': 'success',
        'default_roles': ['ADMIN', 'TEACHER'],
        'items': [
            {
                'key': 'assembly_attendance',
                'name_kh': 'ស្រង់វត្តមានពេលគោរពទង់ជាតិ',
                'name_en': 'Flag Ceremony & Pre-Class Attendance',
                'icon': 'fa-solid fa-flag text-danger',
                'default_roles': ['ADMIN', 'TEACHER', 'STUDENT'],
                'url_name': 'assembly_attendance',
            },
            {
                'key': 'student_attendance_grid',
                'name_kh': 'ស្រង់វត្តមានសិស្សតាមម៉ោង',
                'name_en': 'Student Hourly Attendance Sheet',
                'icon': 'fa-solid fa-clipboard-check text-primary',
                'default_roles': ['ADMIN', 'TEACHER'],
                'url_name': 'student_attendance_grid',
            },
            {
                'key': 'attendance_report',
                'name_kh': 'របាយការណ៍វត្តមានប្រចាំខែ',
                'name_en': 'Monthly Attendance Report',
                'icon': 'fa-solid fa-chart-column text-info',
                'default_roles': ['ADMIN', 'TEACHER'],
                'url_name': 'attendance_report',
            },
            {
                'key': 'attendance_admin_hub',
                'name_kh': 'គ្រប់គ្រងវត្តមាន & Telegram',
                'name_en': 'Attendance & Telegram Hub',
                'icon': 'fa-solid fa-sliders text-warning',
                'default_roles': ['ADMIN'],
                'url_name': 'attendance_admin_hub',
            },
            {
                'key': 'at_risk_attendance',
                'name_kh': 'សិស្សអវត្តមានច្រើន',
                'name_en': 'At-Risk Chronic Absentees',
                'icon': 'fa-solid fa-triangle-exclamation text-danger',
                'default_roles': ['ADMIN', 'TEACHER'],
                'url_name': 'at_risk_attendance',
            },
        ]
    },
    {
        'key': 'sec_examinations',
        'name_kh': 'ការប្រឡង & ពិន្ទុ',
        'name_en': 'Examinations & Grading',
        'icon': 'fa-solid fa-graduation-cap',
        'color': 'primary',
        'default_roles': ['ADMIN', 'TEACHER'],
        'items': [
            {
                'key': 'grade_entry_matrix',
                'name_kh': 'បញ្ចូលពិន្ទុ',
                'name_en': 'Grade Entry Matrix',
                'icon': 'fa-solid fa-pen-to-square text-primary',
                'default_roles': ['ADMIN', 'TEACHER'],
                'url_name': 'grade_entry_matrix',
            },
            {
                'key': 'grade_summary',
                'name_kh': 'តារាងពិន្ទុ & ចំណាត់ថ្នាក់',
                'name_en': 'Score Summary & Student Ranking',
                'icon': 'fa-solid fa-ranking-star text-warning',
                'default_roles': ['ADMIN', 'TEACHER'],
                'url_name': 'grade_summary',
            },
            {
                'key': 'semester_results',
                'name_kh': 'លទ្ធផលប្រចាំឆមាស',
                'name_en': 'Semester Results & Rankings',
                'icon': 'fa-solid fa-file-signature text-info',
                'default_roles': ['ADMIN', 'TEACHER'],
                'url_name': 'semester_results',
            },
            {
                'key': 'annual_results',
                'name_kh': 'លទ្ធផលប្រចាំឆ្នាំ',
                'name_en': 'Annual Overall Results & Promotion',
                'icon': 'fa-solid fa-award text-success',
                'default_roles': ['ADMIN', 'TEACHER'],
                'url_name': 'annual_results',
            },
            {
                'key': 'standardized_exam_list',
                'name_kh': 'សម័យប្រឡង',
                'name_en': 'Exam Sessions',
                'icon': 'fa-solid fa-certificate text-danger',
                'default_roles': ['ADMIN'],
                'url_name': 'standardized_exam_list',
                'is_admin_only': True,
            },
            {
                'key': 'exam_blind_scoring_portal',
                'name_kh': 'បញ្ចូលពិន្ទុកូដសម្ងាត់',
                'name_en': 'Blind Scoring Portal',
                'icon': 'fa-solid fa-user-secret text-dark',
                'default_roles': ['ADMIN', 'TEACHER'],
                'url_name': 'exam_blind_scoring_portal',
            },
            {
                'key': 'grade_rules_manager',
                'name_kh': 'ច្បាប់ពិន្ទុ & លក្ខខណ្ឌ',
                'name_en': 'Scoring & Assessment Rules',
                'icon': 'fa-solid fa-scale-balanced text-primary',
                'default_roles': ['ADMIN'],
                'url_name': 'grade_rules_manager',
            },
            {
                'key': 'exam_exclusions_manage',
                'name_kh': 'សិស្សលើកលែងមិនឱ្យប្រឡង',
                'name_en': 'Student Exam Exclusions',
                'icon': 'fa-solid fa-user-slash text-danger',
                'default_roles': ['ADMIN', 'TEACHER'],
                'url_name': 'exam_exclusions_manage',
            },
            {
                'key': 'exam_invigilator_admin',
                'name_kh': 'គ្រប់គ្រងវេនអនុរក្សប្រឡង',
                'name_en': 'Exam Invigilator Shifts',
                'icon': 'fa-solid fa-clipboard-user text-warning',
                'default_roles': ['ADMIN'],
                'url_name': 'exam_invigilator_plans_list',
            },
            {
                'key': 'exam_invigilator_request',
                'name_kh': 'ស្នើសុំវេនអនុរក្សប្រឡង',
                'name_en': 'Request Invigilator Shifts',
                'icon': 'fa-solid fa-hand-holding-hand text-success',
                'default_roles': ['ADMIN', 'TEACHER'],
                'url_name': 'exam_invigilator_teacher_portal',
            },
        ]
    },
    {
        'key': 'sec_teachers',
        'name_kh': 'គ្រូបង្រៀន & បុគ្គលិក',
        'name_en': 'Teachers & Staff',
        'icon': 'fa-solid fa-chalkboard-user',
        'color': 'warning',
        'default_roles': ['ADMIN', 'TEACHER'],
        'items': [
            {
                'key': 'teacher_list',
                'name_kh': 'បញ្ជីគ្រូបង្រៀន',
                'name_en': 'Teachers Directory',
                'icon': 'fa-solid fa-chalkboard-user',
                'default_roles': ['ADMIN'],
                'url_name': 'teacher_list',
            },
            {
                'key': 'teacher_attendance',
                'name_kh': 'ស្រង់វត្តមានគ្រូប្រចាំថ្ងៃ',
                'name_en': 'Daily Teacher Attendance',
                'icon': 'fa-solid fa-user-clock',
                'default_roles': ['ADMIN'],
                'url_name': 'teacher_attendance',
            },
            {
                'key': 'teacher_kiosk_view',
                'name_kh': 'Kiosk ស្កេនវត្តមាន',
                'name_en': 'Attendance Kiosk Display',
                'icon': 'fa-solid fa-qrcode text-primary',
                'default_roles': ['ADMIN', 'TEACHER'],
                'url_name': 'teacher_kiosk_view',
            },
            {
                'key': 'teacher_mobile_qr_scan',
                'name_kh': 'ស្កេនវត្តមានលើទូរស័ព្ទ',
                'name_en': 'Teacher Mobile Scan',
                'icon': 'fa-solid fa-mobile-screen text-success',
                'default_roles': ['ADMIN', 'TEACHER'],
                'url_name': 'teacher_mobile_qr_scan',
            },
            {
                'key': 'biometric_hub',
                'name_kh': 'ឧបករណ៍ Biometric & ក្រយៅដៃ',
                'name_en': 'Biometric & Fingerprint Hub',
                'icon': 'fa-solid fa-fingerprint text-warning',
                'default_roles': ['ADMIN'],
                'url_name': 'biometric_hub',
            },
            {
                'key': 'teacher_punch_logs',
                'name_kh': 'កំណត់ត្រាស្កេនវត្តមាន',
                'name_en': 'Teacher Punch Logs',
                'icon': 'fa-solid fa-list-check text-info',
                'default_roles': ['ADMIN', 'TEACHER'],
                'url_name': 'teacher_punch_logs',
            },
            {
                'key': 'teacher_attendance_report',
                'name_kh': 'របាយការណ៍វត្តមានគ្រូ',
                'name_en': 'Teacher Attendance Report',
                'icon': 'fa-solid fa-chart-column text-info',
                'default_roles': ['ADMIN'],
                'url_name': 'teacher_attendance_report',
            },
            {
                'key': 'teacher_attendance_settings',
                'name_kh': 'ការកំណត់វិធីសាស្ត្រវត្តមាន',
                'name_en': 'Attendance Method Settings',
                'icon': 'fa-solid fa-sliders text-secondary',
                'default_roles': ['ADMIN'],
                'url_name': 'teacher_attendance_settings',
            },
            {
                'key': 'teacher_leave_list',
                'name_kh': 'ច្បាប់ឈប់សម្រាកគ្រូ',
                'name_en': 'Teacher Leave Requests',
                'icon': 'fa-solid fa-envelope-open-text text-warning',
                'default_roles': ['ADMIN', 'TEACHER'],
                'url_name': 'teacher_leave_list',
            },
        ]
    },
    {
        'key': 'sec_finance',
        'name_kh': 'ហិរញ្ញវត្ថុ & ទឹកភ្លើង',
        'name_en': 'Finance & Utilities',
        'icon': 'fa-solid fa-coins',
        'color': 'warning',
        'default_roles': ['ADMIN', 'ACCOUNTANT'],
        'items': [
            {
                'key': 'monthly_fees_tracker',
                'name_kh': 'បញ្ជីទឹកភ្លើងប្រចាំខែ',
                'name_en': 'Monthly Utilities & Due Fees',
                'icon': 'fa-solid fa-faucet-drip text-warning',
                'default_roles': ['ADMIN', 'ACCOUNTANT'],
                'url_name': 'monthly_fees_tracker',
            },
            {
                'key': 'invoice_list',
                'name_kh': 'វិក្កយបត្រសិស្ស',
                'name_en': 'Student Invoices',
                'icon': 'fa-solid fa-file-invoice-dollar',
                'default_roles': ['ADMIN', 'ACCOUNTANT'],
                'url_name': 'invoice_list',
            },
            {
                'key': 'expense_list',
                'name_kh': 'ចំណាយសាលា',
                'name_en': 'School Expenses',
                'icon': 'fa-solid fa-money-bill-transfer',
                'default_roles': ['ADMIN', 'ACCOUNTANT'],
                'url_name': 'expense_list',
            },
            {
                'key': 'scholarship_type_list',
                'name_kh': 'ប្រភេទកម្រៃ & អាហារូបករណ៍',
                'name_en': 'Scholarships & Fee Categories',
                'icon': 'fa-solid fa-award text-warning',
                'default_roles': ['ADMIN', 'ACCOUNTANT'],
                'url_name': 'scholarship_type_list',
            },
            {
                'key': 'payroll_list',
                'name_kh': 'ប្រាក់ខែបុគ្គលិក-គ្រូ',
                'name_en': 'Staff & Teacher Payroll',
                'icon': 'fa-solid fa-hand-holding-dollar',
                'default_roles': ['ADMIN', 'ACCOUNTANT'],
                'url_name': 'payroll_list',
            },
            {
                'key': 'payment_logs_dashboard',
                'name_kh': 'កំណត់ត្រាបង់ប្រាក់ & Firestore',
                'name_en': 'Payment Logs & Firestore',
                'icon': 'fa-solid fa-cloud-bolt text-primary',
                'default_roles': ['ADMIN', 'ACCOUNTANT'],
                'url_name': 'payment_logs_dashboard',
            },
        ]
    },
    {
        'key': 'sec_extras',
        'name_kh': 'ប្រតិបត្តិការបន្ថែម',
        'name_en': 'Extras & Library',
        'icon': 'fa-solid fa-layer-group',
        'color': 'info',
        'default_roles': ['ADMIN', 'TEACHER', 'STUDENT', 'ACCOUNTANT'],
        'items': [
            {
                'key': 'book_list',
                'name_kh': 'បណ្ណាល័យសាលា',
                'name_en': 'Library Books & Borrowing',
                'icon': 'fa-solid fa-book-bookmark',
                'default_roles': ['ADMIN', 'TEACHER', 'STUDENT', 'ACCOUNTANT'],
                'url_name': 'book_list',
            },
            {
                'key': 'inventory_list',
                'name_kh': 'ស្តុកសម្ភារៈសាលា',
                'name_en': 'School Inventory & Asset Stock',
                'icon': 'fa-solid fa-boxes-stacked',
                'default_roles': ['ADMIN', 'ACCOUNTANT'],
                'url_name': 'inventory_list',
            },
        ]
    },
    {
        'key': 'sec_tools',
        'name_kh': 'ឧបករណ៍ឌីជីថល',
        'name_en': 'Digital Tools Hub',
        'icon': 'fa-solid fa-wand-magic-sparkles',
        'color': 'warning',
        'default_roles': ['ADMIN', 'TEACHER', 'STUDENT', 'ACCOUNTANT'],
        'items': [
            {
                'key': 'tools_hub',
                'name_kh': 'ផ្ទាំងឧបករណ៍សរុប',
                'name_en': 'Tools Hub Dashboard',
                'icon': 'fa-solid fa-grip text-primary',
                'default_roles': ['ADMIN', 'TEACHER', 'STUDENT', 'ACCOUNTANT'],
                'url_name': 'tools_hub',
            },
            {
                'key': 'tool_pdf_merge',
                'name_kh': 'បញ្ចូលឯកសារ PDF',
                'name_en': 'PDF Merge Tool',
                'icon': 'fa-solid fa-file-pdf text-danger',
                'default_roles': ['ADMIN', 'TEACHER', 'STUDENT', 'ACCOUNTANT'],
                'url_name': 'tool_pdf_merge',
            },
            {
                'key': 'tool_pdf_split',
                'name_kh': 'បំបែកឯកសារ PDF',
                'name_en': 'PDF Split Tool',
                'icon': 'fa-solid fa-file-export text-danger',
                'default_roles': ['ADMIN', 'TEACHER', 'STUDENT', 'ACCOUNTANT'],
                'url_name': 'tool_pdf_split',
            },
            {
                'key': 'tool_images_to_pdf',
                'name_kh': 'រូបភាពទៅជា PDF',
                'name_en': 'Images to PDF Tool',
                'icon': 'fa-solid fa-images text-purple',
                'default_roles': ['ADMIN', 'TEACHER', 'STUDENT', 'ACCOUNTANT'],
                'url_name': 'tool_images_to_pdf',
            },
            {
                'key': 'tool_doc_scanner',
                'name_kh': 'ស្កេនក្រដាស & ឯកសារ',
                'name_en': 'Document Scanner',
                'icon': 'fa-solid fa-file-invoice text-success',
                'default_roles': ['ADMIN', 'TEACHER', 'STUDENT', 'ACCOUNTANT'],
                'url_name': 'tool_doc_scanner',
            },
            {
                'key': 'tool_image_editor',
                'name_kh': 'កែសម្រួលរូបភាព',
                'name_en': 'Image Editor Studio',
                'icon': 'fa-solid fa-crop-simple text-success',
                'default_roles': ['ADMIN', 'TEACHER', 'STUDENT', 'ACCOUNTANT'],
                'url_name': 'tool_image_editor',
            },
            {
                'key': 'tool_id_photo_maker',
                'name_kh': 'កាត់រូបថតកាត (4x6 / 3x4)',
                'name_en': 'ID Photo Passport Maker',
                'icon': 'fa-solid fa-id-card text-info',
                'default_roles': ['ADMIN', 'TEACHER', 'STUDENT', 'ACCOUNTANT'],
                'url_name': 'tool_id_photo_maker',
            },
            {
                'key': 'tool_image_compressor',
                'name_kh': 'បង្រួមទំហំរូបភាព',
                'name_en': 'Image Compressor',
                'icon': 'fa-solid fa-file-zipper text-secondary',
                'default_roles': ['ADMIN', 'TEACHER', 'STUDENT', 'ACCOUNTANT'],
                'url_name': 'tool_image_compressor',
            },
            {
                'key': 'tool_qr_generator',
                'name_kh': 'បង្កើត QR Code',
                'name_en': 'QR Code Generator',
                'icon': 'fa-solid fa-qrcode text-dark',
                'default_roles': ['ADMIN', 'TEACHER', 'STUDENT', 'ACCOUNTANT'],
                'url_name': 'tool_qr_generator',
            },
            {
                'key': 'tool_qr_scanner',
                'name_kh': 'ស្កេន QR & Barcode',
                'name_en': 'QR & Barcode Scanner',
                'icon': 'fa-solid fa-camera text-primary',
                'default_roles': ['ADMIN', 'TEACHER', 'STUDENT', 'ACCOUNTANT'],
                'url_name': 'tool_qr_scanner',
            },
            {
                'key': 'tool_classroom_picker',
                'name_kh': 'ចាប់ឆ្នោតសិស្ស & ចែកក្រុម',
                'name_en': 'Classroom Student Picker & Grouping',
                'icon': 'fa-solid fa-dharmachakra text-warning',
                'default_roles': ['ADMIN', 'TEACHER'],
                'url_name': 'tool_classroom_picker',
            },
            {
                'key': 'tool_khmer_number_converter',
                'name_kh': 'លេខទៅជាអក្សរខ្មែរ',
                'name_en': 'Khmer Number to Words',
                'icon': 'fa-solid fa-money-check-dollar text-success',
                'default_roles': ['ADMIN', 'TEACHER', 'STUDENT', 'ACCOUNTANT'],
                'url_name': 'tool_khmer_number_converter',
            },
            {
                'key': 'tool_text_analyzer',
                'name_kh': 'រាប់ពាក្យ & វិភាគអត្ថបទ',
                'name_en': 'Text Word Count & Analyzer',
                'icon': 'fa-solid fa-spell-check text-info',
                'default_roles': ['ADMIN', 'TEACHER', 'STUDENT', 'ACCOUNTANT'],
                'url_name': 'tool_text_analyzer',
            },
            {
                'key': 'tool_voice_typing',
                'name_kh': 'វាយអត្ថបទតាមសំឡេង',
                'name_en': 'Khmer Voice Typing',
                'icon': 'fa-solid fa-microphone-lines text-danger',
                'default_roles': ['ADMIN', 'TEACHER', 'STUDENT', 'ACCOUNTANT'],
                'url_name': 'tool_voice_typing',
            },
            {
                'key': 'tool_calculator_converter',
                'name_kh': 'ម៉ាស៊ីនគិតលេខ & បំលែងខ្នាត',
                'name_en': 'Calculator & Unit Converter',
                'icon': 'fa-solid fa-calculator text-primary',
                'default_roles': ['ADMIN', 'TEACHER', 'STUDENT', 'ACCOUNTANT'],
                'url_name': 'tool_calculator_converter',
            },
        ]
    },
    {
        'key': 'sec_settings',
        'name_kh': 'ការកំណត់ប្រព័ន្ធ',
        'name_en': 'System Settings',
        'icon': 'fa-solid fa-gear',
        'color': 'secondary',
        'default_roles': ['ADMIN'],
        'items': [
            {
                'key': 'location_manager_view',
                'name_kh': 'តំបន់រដ្ឋបាល (ខេត្ត/ស្រុក/ឃុំ)',
                'name_en': 'Administrative Geography',
                'icon': 'fa-solid fa-map-location-dot text-primary',
                'default_roles': ['ADMIN'],
                'url_name': 'location_manager_view',
            },
            {
                'key': 'school_profile_settings',
                'name_kh': 'ព័ត៌មានសាលារៀន',
                'name_en': 'School Profile & Identity',
                'icon': 'fa-solid fa-school-flag text-warning',
                'default_roles': ['ADMIN'],
                'url_name': 'school_profile_settings',
            },
            {
                'key': 'telegram_settings',
                'name_kh': 'ការជូនដំណឹង Telegram',
                'name_en': 'Telegram Bot Settings',
                'icon': 'fa-brands fa-telegram text-info',
                'default_roles': ['ADMIN'],
                'url_name': 'telegram_settings',
            },
            {
                'key': 'user_management',
                'name_kh': 'គ្រប់គ្រងគណនីប្រើប្រាស់',
                'name_en': 'User Accounts Management',
                'icon': 'fa-solid fa-users-gear text-primary',
                'default_roles': ['ADMIN'],
                'url_name': 'user_management',
            },
            {
                'key': 'menu_permissions',
                'name_kh': 'កំណត់សិទ្ធិមឺនុយ',
                'name_en': 'Menu & Submenu Permissions',
                'icon': 'fa-solid fa-user-shield text-danger',
                'default_roles': ['ADMIN'],
                'url_name': 'menu_permissions',
            },
            {
                'key': 'tool_database_backup',
                'name_kh': 'បម្រុងទុកទិន្នន័យ',
                'name_en': 'Database Backup & Snapshot',
                'icon': 'fa-solid fa-database text-success',
                'default_roles': ['ADMIN'],
                'url_name': 'tool_database_backup',
            },
        ]
    },
]


from .models import RoleMenuPermission, MenuSection, MenuItem, User


def sync_system_menus_to_db():
    """
    Synchronizes static catalogue into database MenuSection and MenuItem records.
    Safe to run repeatedly; updates existing system records and creates missing ones,
    while preserving custom additions.
    """
    valid_sec_codes = set()
    valid_item_codes = set()

    for sec_idx, sec_data in enumerate(MENU_SECTIONS_CATALOG):
        valid_sec_codes.add(sec_data['key'])
        sec_obj, created = MenuSection.objects.get_or_create(
            code=sec_data['key'],
            defaults={
                'name_kh': sec_data['name_kh'],
                'name_en': sec_data['name_en'],
                'icon': sec_data['icon'],
                'color': sec_data.get('color', 'secondary'),
                'order': sec_idx,
                'is_active': True,
                'is_system': True,
                'default_roles': ','.join(sec_data.get('default_roles', ['ADMIN'])),
            }
        )
        if not created and sec_obj.is_system:
            sec_obj.name_kh = sec_data['name_kh']
            sec_obj.name_en = sec_data['name_en']
            sec_obj.icon = sec_data['icon']
            sec_obj.color = sec_data.get('color', 'secondary')
            sec_obj.order = sec_idx
            sec_obj.default_roles = ','.join(sec_data.get('default_roles', ['ADMIN']))
            sec_obj.save()

        for item_idx, item_data in enumerate(sec_data.get('items', [])):
            valid_item_codes.add(item_data['key'])
            item_obj, item_created = MenuItem.objects.get_or_create(
                code=item_data['key'],
                defaults={
                    'section': sec_obj,
                    'name_kh': item_data['name_kh'],
                    'name_en': item_data['name_en'],
                    'icon': item_data['icon'],
                    'url_name': item_data.get('url_name'),
                    'order': item_idx,
                    'is_active': True,
                    'is_admin_only': item_data.get('is_admin_only', False),
                    'is_system': True,
                    'default_roles': ','.join(item_data.get('default_roles', ['ADMIN'])),
                }
            )
            if not item_created and item_obj.is_system:
                item_obj.section = sec_obj
                item_obj.name_kh = item_data['name_kh']
                item_obj.name_en = item_data['name_en']
                item_obj.icon = item_data['icon']
                item_obj.url_name = item_data.get('url_name')
                item_obj.order = item_idx
                item_obj.is_admin_only = item_data.get('is_admin_only', False)
                item_obj.default_roles = ','.join(item_data.get('default_roles', ['ADMIN']))
                item_obj.save()

    # Clean up obsolete system menus
    MenuItem.objects.filter(is_system=True).exclude(code__in=valid_item_codes).delete()
    MenuSection.objects.filter(is_system=True).exclude(code__in=valid_sec_codes).delete()


def get_menu_catalog() -> List[Dict[str, Any]]:
    """
    Returns the complete structured hierarchy of all sections and submenus sourced from Database.
    Automatically seeds and syncs DB from system catalogue if empty or if new system items were added.
    """
    try:
        system_item_codes = set()
        for s in MENU_SECTIONS_CATALOG:
            for itm in s.get('items', []):
                system_item_codes.add(itm['key'])

        existing_sys_codes = set(MenuItem.objects.filter(is_system=True).values_list('code', flat=True))
        if not MenuSection.objects.exists() or not system_item_codes.issubset(existing_sys_codes):
            sync_system_menus_to_db()

        sections = MenuSection.objects.filter(is_active=True).prefetch_related('items').order_by('order', 'id')
        catalog = []
        for sec in sections:
            active_items = sec.items.filter(is_active=True).order_by('order', 'id')
            item_list = []
            for item in active_items:
                item_list.append({
                    'id': item.id,
                    'key': item.code,
                    'name_kh': item.name_kh,
                    'name_en': item.name_en,
                    'icon': item.icon,
                    'url_name': item.url_name,
                    'custom_url': item.custom_url,
                    'url': item.get_url,
                    'is_admin_only': item.is_admin_only,
                    'is_system': item.is_system,
                    'default_roles': [r.strip() for r in item.default_roles.split(',') if r.strip()],
                })

            catalog.append({
                'id': sec.id,
                'key': sec.code,
                'name_kh': sec.name_kh,
                'name_en': sec.name_en,
                'icon': sec.icon,
                'color': sec.color,
                'is_system': sec.is_system,
                'default_roles': [r.strip() for r in sec.default_roles.split(',') if r.strip()],
                'items': item_list,
            })
        return catalog
    except Exception:
        return MENU_SECTIONS_CATALOG


def get_default_permissions_for_role(role: str) -> Dict[str, bool]:
    """
    Computes default permission map {menu_key: bool} for a given role based on Database catalog.
    """
    catalog = get_menu_catalog()
    defaults = {}
    for section in catalog:
        sec_key = section['key']
        defaults[sec_key] = (role in section.get('default_roles', [])) or (role == 'ADMIN')
        for item in section.get('items', []):
            item_key = item['key']
            defaults[item_key] = (role in item.get('default_roles', [])) or (role == 'ADMIN')
    return defaults


def get_role_permissions_map(role: str) -> Dict[str, bool]:
    """
    Retrieves full permission map for a role.
    Applies custom database overrides on top of default configuration.
    """
    perms = get_default_permissions_for_role(role)
    if role == 'ADMIN':
        # Super admin always has access to everything
        return {k: True for k in perms}

    try:
        # Fetch custom overrides from database
        db_overrides = RoleMenuPermission.objects.filter(role=role).values('menu_key', 'is_allowed')
        for override in db_overrides:
            perms[override['menu_key']] = override['is_allowed']
    except Exception:
        pass

    # Also compute Section visibility: Section is visible if sec_key is allowed AND at least one child is allowed
    catalog = get_menu_catalog()
    for section in catalog:
        sec_key = section['key']
        has_allowed_child = any(perms.get(item['key'], False) for item in section.get('items', []))
        if not perms.get(sec_key, True) or not has_allowed_child:
            perms[sec_key] = False
        else:
            perms[sec_key] = True

    return perms


def is_menu_allowed(user, menu_key: str) -> bool:
    """
    Checks if a given user has permission to view or access a menu/submenu.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or getattr(user, 'role', '') == 'ADMIN':
        return True
    
    role = getattr(user, 'role', 'STUDENT')
    perms = get_role_permissions_map(role)
    return perms.get(menu_key, False)


def set_role_permission(role: str, menu_key: str, is_allowed: bool) -> RoleMenuPermission:
    """
    Updates or creates custom permission override for a role and menu key.
    """
    obj, _ = RoleMenuPermission.objects.update_or_create(
        role=role,
        menu_key=menu_key,
        defaults={'is_allowed': is_allowed}
    )
    return obj


def reset_role_permissions(role: str = None):
    """
    Resets custom permissions back to system defaults.
    If role is None, resets for all non-admin roles.
    """
    if role:
        RoleMenuPermission.objects.filter(role=role).delete()
    else:
        RoleMenuPermission.objects.all().delete()


def create_menu_item(section_id: int, code: str, name_kh: str, name_en: str, icon: str,
                     url_name: str = None, custom_url: str = None, default_roles: List[str] = None,
                     is_admin_only: bool = False) -> MenuItem:
    """
    Admin helper to dynamically create a new submenu item in database.
    """
    section = MenuSection.objects.get(id=section_id)
    roles_str = ','.join(default_roles) if default_roles else 'ADMIN,TEACHER,STUDENT,ACCOUNTANT'
    item = MenuItem.objects.create(
        section=section,
        code=code.strip(),
        name_kh=name_kh.strip(),
        name_en=name_en.strip(),
        icon=icon.strip(),
        url_name=url_name.strip() if url_name else None,
        custom_url=custom_url.strip() if custom_url else None,
        default_roles=roles_str,
        is_admin_only=is_admin_only,
        is_system=False,
        is_active=True
    )
    return item


def update_menu_item(item_id: int, name_kh: str, name_en: str, icon: str,
                     url_name: str = None, custom_url: str = None, is_admin_only: bool = False) -> MenuItem:
    """
    Admin helper to edit an existing submenu item in database.
    """
    item = MenuItem.objects.get(id=item_id)
    item.name_kh = name_kh.strip()
    item.name_en = name_en.strip()
    item.icon = icon.strip()
    item.url_name = url_name.strip() if url_name else None
    item.custom_url = custom_url.strip() if custom_url else None
    item.is_admin_only = is_admin_only
    item.save()
    return item


def delete_menu_item(item_id: int):
    """
    Admin helper to delete a submenu item from database.
    """
    item = MenuItem.objects.get(id=item_id)
    # Remove associated permissions
    RoleMenuPermission.objects.filter(menu_key=item.code).delete()
    item.delete()
