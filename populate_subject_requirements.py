import os
import sys
import django

sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from apps.academics.models import Subject, GradeLevel, GradeLevelRule, SavedDefaultConfig

# 1. Ensure all official MoEYS and requested subjects exist
subjects_to_ensure = [
    ('R', 'តែងសេចក្តី', 'Composition / Essay', '#4f46e5', 1),
    ('D', 'សរសេរតាមអាន', 'Dictation', '#6366f1', 2),
    ('K', 'ភាសាខ្មែរ', 'Khmer Language', '#0ea5e9', 3),
    ('I', 'សីលធម៌', 'Civics & Moral / Ethics', '#06b6d4', 4),
    ('G', 'ភូមិវិទ្យា', 'Geography', '#d97706', 5),
    ('H', 'ប្រវត្តិវិទ្យា', 'History', '#f59e0b', 6),
    ('M', 'គណិតវិទ្យា', 'Mathematics', '#dc2626', 7),
    ('Es', 'ផែនដីវិទ្យា', 'Earth Science', '#84cc16', 8),
    ('P', 'រូបវិទ្យា', 'Physics', '#8b5cf6', 9),
    ('C', 'គីមីវិទ្យា', 'Chemistry', '#10b981', 10),
    ('B', 'ជីវវិទ្យា', 'Biology', '#14b8a6', 11),
    ('He', 'គេហវិទ្យា', 'Home Economics', '#ec4899', 12),
    ('Ec', 'សេដ្ឋកិច្ច', 'Economics', '#f97316', 13),
    ('E', 'អង់គ្លេស', 'English Language', '#3b82f6', 14),
    ('Ed', 'កីឡា', 'Physical Education', '#059669', 15),
    ('Ag', 'កសិកម្ម', 'Agriculture', '#16a34a', 16),
    ('IT', 'ព័ត៌មានវិទ្យា', 'Information Technology', '#6366f1', 17),
]

for code, name_kh, name_en, color, ord_idx in subjects_to_ensure:
    sub, created = Subject.objects.get_or_create(
        code=code,
        defaults={
            'name_kh': name_kh,
            'name_en': name_en,
            'color_code': color,
            'order': ord_idx,
            'category': Subject.SubjectCategory.GENERAL,
        }
    )
    if not created:
        sub.name_kh = name_kh
        sub.name_en = name_en
        sub.color_code = color
        sub.order = ord_idx
        sub.save()
    print(f"Subject ensured: [{sub.code}] {sub.name_kh}")

# 2. Standard MoEYS Weekly Teaching Hours Matrix (តាមកម្រិតថ្នាក់ត្រឹមត្រូវ)
MOEYS_HOURS_MATRIX = {
    # ថ្នាក់ទី ៧ (Grade 7 - Junior High)
    (7, 'GENERAL'): {
        'K': 5, 'M': 5, 'P': 2, 'C': 1, 'B': 2, 'Es': 1,
        'I': 2, 'G': 2, 'H': 2, 'He': 2, 'Ec': 0, 'E': 2, 'Ed': 2, 'Ag': 2, 'IT': 2,
    },
    # ថ្នាក់ទី ៨ (Grade 8 - Junior High)
    (8, 'GENERAL'): {
        'K': 5, 'M': 5, 'P': 2, 'C': 2, 'B': 2, 'Es': 1,
        'I': 2, 'G': 2, 'H': 2, 'He': 2, 'Ec': 0, 'E': 2, 'Ed': 2, 'Ag': 2, 'IT': 2,
    },
    # ថ្នាក់ទី ៩ (Grade 9 - Junior High Diploma)
    (9, 'GENERAL'): {
        'K': 5, 'M': 5, 'P': 2, 'C': 2, 'B': 2, 'Es': 1,
        'I': 2, 'G': 2, 'H': 2, 'He': 2, 'Ec': 0, 'E': 2, 'Ed': 2, 'Ag': 2, 'IT': 2,
    },
    # ថ្នាក់ទី ១០ (Grade 10 - High School Foundation)
    (10, 'GENERAL'): {
        'K': 5, 'M': 5, 'P': 3, 'C': 3, 'B': 3, 'Es': 2,
        'I': 2, 'G': 2, 'H': 2, 'He': 2, 'Ec': 2, 'E': 3, 'Ed': 2, 'Ag': 0, 'IT': 2,
    },
    # ថ្នាក់ទី ១១ វិទ្យាសាស្ត្រ (Grade 11 - Science Stream)
    (11, 'SCIENCE'): {
        'K': 4, 'M': 6, 'P': 4, 'C': 4, 'B': 4, 'Es': 2,
        'I': 2, 'G': 2, 'H': 2, 'He': 0, 'Ec': 2, 'E': 2, 'Ed': 2, 'Ag': 0, 'IT': 2,
    },
    # ថ្នាក់ទី ១១ វិទ្យាសាស្ត្រសង្គម (Grade 11 - Social Science Stream)
    (11, 'SOCIAL'): {
        'K': 6, 'M': 4, 'P': 2, 'C': 1, 'B': 2, 'Es': 2,
        'I': 4, 'G': 4, 'H': 4, 'He': 0, 'Ec': 3, 'E': 2, 'Ed': 2, 'Ag': 0, 'IT': 2,
    },
    # ថ្នាក់ទី ១២ វិទ្យាសាស្ត្រ (Grade 12 - Science Stream BacII)
    (12, 'SCIENCE'): {
        'K': 4, 'M': 6, 'P': 4, 'C': 4, 'B': 4, 'Es': 2,
        'I': 2, 'G': 2, 'H': 2, 'He': 0, 'Ec': 2, 'E': 2, 'Ed': 2, 'Ag': 0, 'IT': 2,
    },
    # ថ្នាក់ទី ១២ វិទ្យាសាស្ត្រសង្គម (Grade 12 - Social Science Stream BacII)
    (12, 'SOCIAL'): {
        'K': 6, 'M': 4, 'P': 2, 'C': 1, 'B': 2, 'Es': 2,
        'I': 4, 'G': 4, 'H': 4, 'He': 0, 'Ec': 3, 'E': 2, 'Ed': 2, 'Ag': 0, 'IT': 2,
    },
}

# Apply to GradeLevelRule
updated_count = 0
for (g_num, trk), sub_map in MOEYS_HOURS_MATRIX.items():
    for sub_code, hrs in sub_map.items():
        sub = Subject.objects.filter(code=sub_code).first()
        if sub:
            rule, _ = GradeLevelRule.objects.get_or_create(
                grade_level=g_num,
                track=trk,
                subject=sub,
                defaults={'weekly_hours': hrs}
            )
            if rule.weekly_hours != hrs:
                rule.weekly_hours = hrs
                rule.save(update_fields=['weekly_hours'])
            updated_count += 1

print(f"\nSuccessfully populated {updated_count} GradeLevelRule records into Database!")

# Save as default in SavedDefaultConfig
saved_dict = {}
for (g_num, trk), sub_map in MOEYS_HOURS_MATRIX.items():
    for sub_code, hrs in sub_map.items():
        sub = Subject.objects.filter(code=sub_code).first()
        if sub:
            saved_dict[f"{g_num}_{trk}_{sub.id}"] = hrs

SavedDefaultConfig.objects.update_or_create(
    key='moeys_subject_requirements',
    defaults={'data': saved_dict}
)
SavedDefaultConfig.objects.update_or_create(
    key='custom_subject_requirements',
    defaults={'data': saved_dict}
)

print("SavedDefaultConfig updated with MoEYS standard defaults!")
