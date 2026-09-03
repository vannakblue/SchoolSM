import os
import django
import datetime
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from apps.academics.models import AcademicYear
from apps.examinations.models import StandardizedExam

User = get_user_model()

class HierarchicalExamSessionsViewTests(TestCase):
    def setUp(self):
        self.client = Client()

        self.academic_year = AcademicYear.objects.create(
            name="2025-2026",
            start_date=datetime.date(2025, 10, 1),
            end_date=datetime.date(2026, 8, 31),
            is_current=True
        )

        self.admin_user = User.objects.create_superuser(
            username="admin_hierarchical_test",
            email="admin_h@test.com",
            password="adminpassword123",
            role="ADMIN"
        )

        # Create Standardized Exams for Exam Session 1 (Semester 1 Exam: Grades 7, 8, 9, 10 Morning, 11, 12 Afternoon)
        for g in [7, 8, 9, 10]:
            StandardizedExam.objects.create(
                academic_year=self.academic_year,
                name=f"សម័យប្រឡងតេស្តស្តង់ដា ឆមាសទី១ (ថ្នាក់ទី {g})",
                grade_level=g,
                track="ALL",
                session="MORNING",
                exam_date=datetime.date(2026, 9, 15),
                candidates_per_room=25
            )

        for g in [11, 12]:
            StandardizedExam.objects.create(
                academic_year=self.academic_year,
                name=f"សម័យប្រឡងតេស្តស្តង់ដា ឆមាសទី១ (ថ្នាក់ទី {g})",
                grade_level=g,
                track="SCIENCE",
                session="AFTERNOON",
                exam_date=datetime.date(2026, 9, 15),
                candidates_per_room=25
            )

        # Create Standardized Exam for Exam Session 2 (Monthly Exam: Grade 9)
        StandardizedExam.objects.create(
            academic_year=self.academic_year,
            name="សម័យប្រឡងប្រចាំខែវិច្ឆិកា (ថ្នាក់ទី ៩)",
            grade_level=9,
            track="ALL",
            session="MORNING",
            exam_date=datetime.date(2026, 11, 20),
            candidates_per_room=25
        )

    def test_01_hierarchical_grouping_by_exam_sessions(self):
        """Standardized exam list groups exams into Exam Sessions first, then reveals grade levels."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('standardized_exam_list'))
        self.assertEqual(response.status_code, 200)

        # Verify context has exam_sessions grouped
        exam_sessions = response.context['exam_sessions']
        self.assertEqual(len(exam_sessions), 2) # Session 1 (Semester 1) and Session 2 (Monthly Nov)

        # Verify Session 1 has 6 grades (7, 8, 9, 10, 11, 12)
        sess1 = next(s for s in exam_sessions if 'ឆមាសទី១' in s['title'])
        self.assertEqual(sess1['title'], 'សម័យប្រឡងតេស្តស្តង់ដា ឆមាសទី១')
        self.assertEqual(len(sess1['exams_data']), 6)
        self.assertEqual(sess1['morning_grades'], [7, 8, 9, 10])
        self.assertEqual(sess1['afternoon_grades'], [11, 12])

        # Verify Session 2 has 1 grade (9)
        sess2 = next(s for s in exam_sessions if 'វិច្ឆិកា' in s['title'])
        self.assertEqual(sess2['title'], 'សម័យប្រឡងប្រចាំខែវិច្ឆិកា')
        self.assertEqual(len(sess2['exams_data']), 1)

        # Check rendered HTML
        self.assertContains(response, 'សម័យប្រឡងតេស្តស្តង់ដា ឆមាសទី១')
        self.assertContains(response, 'សម័យប្រឡងប្រចាំខែវិច្ឆិកា')
        self.assertContains(response, 'មាន 6 កម្រិតថ្នាក់')
        self.assertContains(response, '🌅 វេនព្រឹក៖ <strong>ថ្នាក់ទី 7, 8, 9, 10</strong>')
        self.assertContains(response, '⛅ វេនរសៀល៖ <strong>ថ្នាក់ទី 11, 12</strong>')
