import os
import django
import datetime
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from apps.academics.models import AcademicYear, GradeLevelRule, Subject
from apps.examinations.models import StandardizedExam, ExamSubject

User = get_user_model()

class ExamSubjectCoefficientAutoCalculationTests(TestCase):
    def setUp(self):
        self.client = Client()

        self.academic_year = AcademicYear.objects.create(
            name="2025-2026",
            start_date=datetime.date(2025, 10, 1),
            end_date=datetime.date(2026, 8, 31),
            is_current=True
        )

        self.admin_user = User.objects.create_superuser(
            username="admin_coef_test",
            email="admin_coef@test.com",
            password="adminpassword123",
            role="ADMIN"
        )

        # Create Subjects
        self.sub_math = Subject.objects.create(name_kh="គណិតវិទ្យា", name_en="Mathematics", code="MATH", order=1)
        self.sub_khmer = Subject.objects.create(name_kh="ភាសាខ្មែរ", name_en="Khmer", code="KHM", order=2)
        self.sub_physics = Subject.objects.create(name_kh="រូបវិទ្យា", name_en="Physics", code="PHYS", order=3)
        self.sub_history = Subject.objects.create(name_kh="ប្រវត្តិវិទ្យា", name_en="History", code="HIST", order=4)

        # Create GradeLevelRules with different max scores
        # Math: 100 -> Coef 2.0 (100 / 50)
        GradeLevelRule.objects.update_or_create(
            grade_level=12, track='SCIENCE', subject=self.sub_math,
            defaults={'max_score': Decimal('100.00'), 'order': 1}
        )
        # Khmer: 50 -> Coef 1.0 (50 / 50)
        GradeLevelRule.objects.update_or_create(
            grade_level=12, track='SCIENCE', subject=self.sub_khmer,
            defaults={'max_score': Decimal('50.00'), 'order': 2}
        )
        # Physics: 75 -> Coef 1.5 (75 / 50)
        GradeLevelRule.objects.update_or_create(
            grade_level=12, track='SCIENCE', subject=self.sub_physics,
            defaults={'max_score': Decimal('75.00'), 'order': 3}
        )
        # History: 25 -> Coef 0.5 (25 / 50)
        GradeLevelRule.objects.update_or_create(
            grade_level=12, track='SCIENCE', subject=self.sub_history,
            defaults={'max_score': Decimal('25.00'), 'order': 4}
        )

    def test_01_auto_calculation_on_exam_creation(self):
        """Coefficients are automatically calculated as max_score / 50 upon exam creation."""
        self.client.force_login(self.admin_user)
        
        url = reverse('standardized_exam_create')
        response = self.client.post(url, {
            'academic_year': self.academic_year.id,
            'name': 'សម័យប្រឡងតេស្តប្រចាំឆមាស',
            'grades_selected': ['12'],
            'grade_name_12': 'សម័យប្រឡងតេស្តប្រចាំឆមាស (ថ្នាក់ទី ១២)',
            'grade_track_12': 'SCIENCE',
            'grade_custom_session_12': 'MORNING',
            'grade_date_12': '2026-09-15',
            'grade_cpr_12': 25,
            'is_published': 'on'
        })
        self.assertEqual(response.status_code, 302)

        exam = StandardizedExam.objects.get(grade_level=12)
        es_math = ExamSubject.objects.get(exam=exam, subject=self.sub_math)
        es_khmer = ExamSubject.objects.get(exam=exam, subject=self.sub_khmer)
        es_phys = ExamSubject.objects.get(exam=exam, subject=self.sub_physics)
        es_hist = ExamSubject.objects.get(exam=exam, subject=self.sub_history)

        # Verify Math: 100 -> Coef 2.0
        self.assertEqual(es_math.max_score, Decimal('100.00'))
        self.assertEqual(es_math.coefficient, Decimal('2.00'))

        # Verify Khmer: 50 -> Coef 1.0
        self.assertEqual(es_khmer.max_score, Decimal('50.00'))
        self.assertEqual(es_khmer.coefficient, Decimal('1.00'))

        # Verify Physics: 75 -> Coef 1.5
        self.assertEqual(es_phys.max_score, Decimal('75.00'))
        self.assertEqual(es_phys.coefficient, Decimal('1.50'))

        # Verify History: 25 -> Coef 0.5
        self.assertEqual(es_hist.max_score, Decimal('25.00'))
        self.assertEqual(es_hist.coefficient, Decimal('0.50'))

    def test_02_manual_override_preserved_on_edit(self):
        """Admin can manually override coefficient to any custom value on exam edit."""
        exam = StandardizedExam.objects.create(
            academic_year=self.academic_year,
            name="សម័យប្រឡងតេស្ត",
            grade_level=12,
            track="SCIENCE",
            exam_date=datetime.date(2026, 9, 15),
            session="MORNING"
        )
        es_math = ExamSubject.objects.create(
            exam=exam, subject=self.sub_math, max_score=Decimal('100.00'), coefficient=Decimal('2.00')
        )

        self.client.force_login(self.admin_user)
        edit_url = reverse('standardized_exam_edit', kwargs={'exam_id': exam.id})

        # Admin overrides Math coefficient manually to 3.5
        response = self.client.post(edit_url, {
            'academic_year': self.academic_year.id,
            'name': 'សម័យប្រឡងតេស្ត (កែប្រែ)',
            'grade_level': 12,
            'track': 'SCIENCE',
            'exam_date': '2026-09-15',
            'session': 'MORNING',
            'candidates_per_room': 25,
            f'max_score_{es_math.id}': '100',
            f'coefficient_{es_math.id}': '3.5', # Manual override
            f'session_{es_math.id}': 'MORNING',
            f'exam_date_{es_math.id}': '2026-09-15'
        })
        self.assertEqual(response.status_code, 302)

        es_math.refresh_from_db()
        self.assertEqual(es_math.coefficient, Decimal('3.50'))
