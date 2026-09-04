import os
import sys
sys.path.insert(0, 'e:/SchoolSM')
sys.stdout.reconfigure(encoding='utf-8')
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from apps.examinations.models import StandardizedExam
from apps.examinations.analytics_service import ExamAnalyticsService

exam8 = StandardizedExam.objects.filter(name__icontains='វិច្ឆិកា', grade_level=8).first()
payload = ExamAnalyticsService.get_analytics_payload(exam8, scope='grade', grade_level=8)

print("=== Overall Mentions Matrix ===")
print("Grades:", payload['overall_mentions']['grades'])
print("Total row:", payload['overall_mentions']['total_row'])
print("Female row:", payload['overall_mentions']['female_row'])
print("Male row:", payload['overall_mentions']['male_row'])

print("\n=== Quality Evaluation ===")
print("Total row:", payload['quality_evaluation']['total_row'])
print("Female row:", payload['quality_evaluation']['female_row'])
print("Male row:", payload['quality_evaluation']['male_row'])

print(f"\nSlow learners count: {len(payload['slow_learners_data'])}")
if payload['slow_learners_data']:
    first = payload['slow_learners_data'][0]
    print(f"Sample slow learner: {first['name']} ({first['gender']}) - Failed subjects: {first['failed_count']} - Overall: {first['overall_mention']}")
