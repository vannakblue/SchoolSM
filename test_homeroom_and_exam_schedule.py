import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import TestCase, Client
from django.urls import reverse
from datetime import date, time, timedelta
from apps.accounts.models import User, SchoolProfile
from apps.academics.models import AcademicYear, Classroom, Subject
from apps.teachers.models import Teacher
from apps.examinations.models import StandardizedExam, ExamSubject

class HomeroomAndExamScheduleTests(TestCase):
    def setUp(self):
        self.client = Client()
        
        # 1. Admin user
        self.admin_user = User.objects.create_superuser(
            username='test_admin',
            email='admin@schoolsm.test',
            password='Password123!',
            role=User.Role.ADMIN,
            khmer_name='អ្នកគ្រប់គ្រង តេស្ត'
        )
        self.client.force_login(self.admin_user)

        # 2. School Profile
        self.school = SchoolProfile.get_settings()
        self.school.name_kh = "វិទ្យាល័យ តេជោសែន កោះកុង"
        self.school.poe_name = "មន្ទីរអប់រំ យុវជន និងកីឡា ខេត្ត កោះកុង"
        self.school.short_name = "វិ.ច.ប.ក.ស"
        self.school.save()

        # 3. Academic Year
        self.year = AcademicYear.objects.create(
            name="២០២៦-២០២៧",
            start_date=date(2026, 10, 1),
            end_date=date(2027, 8, 31),
            is_current=True
        )

        # 4. Teachers
        self.teacher1, _ = Teacher.objects.get_or_create(
            teacher_id="TEST_T001",
            defaults={
                'khmer_name': "ឈិន កុសល",
                'latin_name': "Chhin Kosal",
                'gender': Teacher.Gender.MALE,
                'phone': "012345678",
                'specialization': "គណិតវិទ្យា",
                'status': Teacher.Status.ACTIVE
            }
        )
        self.teacher2, _ = Teacher.objects.get_or_create(
            teacher_id="TEST_T002",
            defaults={
                'khmer_name': "សុខ ណារី",
                'latin_name': "Sok Nary",
                'gender': Teacher.Gender.FEMALE,
                'phone': "098765432",
                'specialization': "ភាសាខ្មែរ",
                'status': Teacher.Status.ACTIVE
            }
        )

        # 5. Classrooms
        self.class12a = Classroom.objects.create(
            name="ថ្នាក់ទី១២ វិទ្យាសាស្ត្រសង្គម A",
            code="12A",
            grade_level=12,
            track=Classroom.Track.SOCIAL,
            academic_year=self.year,
            room_number="បន្ទប់ ១០១",
            homeroom_teacher=None
        )
        self.class12b = Classroom.objects.create(
            name="ថ្នាក់ទី១២ វិទ្យាសាស្ត្រសង្គម B",
            code="12B",
            grade_level=12,
            track=Classroom.Track.SOCIAL,
            academic_year=self.year,
            room_number="បន្ទប់ ១០២",
            homeroom_teacher=None
        )

        # 6. Subjects
        self.sub_math = Subject.objects.filter(name_kh="គណិតវិទ្យា").first() or Subject.objects.create(name_kh="គណិតវិទ្យា", name_en="Mathematics", code="MAT", order=1)
        self.sub_geo = Subject.objects.filter(name_kh="ភូមិវិទ្យា").first() or Subject.objects.create(name_kh="ភូមិវិទ្យា", name_en="Geography", code="GEO", order=2)
        self.sub_khmer = Subject.objects.filter(name_kh="ភាសាខ្មែរ").first() or Subject.objects.create(name_kh="ភាសាខ្មែរ", name_en="Khmer", code="KHM", order=3)

        # 7. Standardized Exam
        self.exam = StandardizedExam.objects.create(
            name="ប្រឡងតេស្តវាស់ស្ទង់ជា ប្រចាំឆមាសទី២",
            academic_year=self.year,
            grade_level=12,
            track=StandardizedExam.Track.SOCIAL,
            session=StandardizedExam.Session.MORNING,
            exam_date=date(2026, 6, 10),
            candidates_per_room=25
        )

    def test_homeroom_teachers_manage_get(self):
        """Test accessing homeroom teachers assignment page."""
        url = reverse('homeroom_teachers_manage') + f"?year={self.year.id}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "12A")
        self.assertContains(response, "12B")
        self.assertContains(response, "ឈិន កុសល")
        self.assertContains(response, "សុខ ណារី")

    def test_homeroom_teachers_manage_bulk_post(self):
        """Test bulk assigning homeroom teachers to classrooms."""
        url = reverse('homeroom_teachers_manage')
        post_data = {
            'year': self.year.id,
            f'teacher_{self.class12a.id}': str(self.teacher1.id),
            f'room_{self.class12a.id}': 'បន្ទប់ ២០១',
            f'teacher_{self.class12b.id}': str(self.teacher2.id),
            f'room_{self.class12b.id}': 'បន្ទប់ ២០២',
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)

        # Verify DB updates
        self.class12a.refresh_from_db()
        self.class12b.refresh_from_db()
        self.assertEqual(self.class12a.homeroom_teacher, self.teacher1)
        self.assertEqual(self.class12a.room_number, 'បន្ទប់ ២០១')
        self.assertEqual(self.class12b.homeroom_teacher, self.teacher2)
        self.assertEqual(self.class12b.room_number, 'បន្ទប់ ២០២')

    def test_homeroom_teachers_update_ajax(self):
        """Test instant AJAX assignment of a homeroom teacher."""
        url = reverse('homeroom_teachers_update_ajax')
        response = self.client.post(url, {
            'classroom_id': self.class12a.id,
            'teacher_id': self.teacher2.id,
            'room_number': 'បន្ទប់ ៩៩'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['teacher_name'], 'សុខ ណារី')

        self.class12a.refresh_from_db()
        self.assertEqual(self.class12a.homeroom_teacher, self.teacher2)
        self.assertEqual(self.class12a.room_number, 'បន្ទប់ ៩៩')

    def test_homeroom_teachers_approval_print(self):
        """Test generating official printable sheet for Principal approval."""
        self.class12a.homeroom_teacher = self.teacher1
        self.class12a.save()

        url = reverse('homeroom_teachers_approval_print') + f"?year={self.year.id}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "បញ្ជីរាយនាមគ្រូទទួលបន្ទុកថ្នាក់")
        self.assertContains(response, "សម្រាប់នាយកសាលាពិនិត្យ និងសម្រេចអនុម័ត")
        self.assertContains(response, "12A")
        self.assertContains(response, "ឈិន កុសល")
        self.assertContains(response, "នាយកសាលា")

    def test_exam_schedule_manage_and_save(self):
        """Test configuring start time, end time, subject, and duration."""
        # Create an ExamSubject
        es = ExamSubject.objects.create(
            exam=self.exam,
            subject=self.sub_math,
            exam_date=self.exam.exam_date,
            session='MORNING',
            start_time=time(7, 30),
            end_time=time(9, 0),
            duration_minutes=90,
            order=1
        )

        url = reverse('standardized_exam_schedule_manage', args=[self.exam.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "តារាងប្រព្រឹត្តទៅនៃវិញ្ញាសា")
        self.assertContains(response, "គណិតវិទ្យា")

        # Edit timetable row via POST
        post_data = {
            'action': 'save_all',
            'row_id': [str(es.id)],
            f'subject_{es.id}': str(self.sub_geo.id),
            f'date_{es.id}': '2026-06-11',
            f'session_{es.id}': 'AFTERNOON',
            f'start_{es.id}': '14:00',
            f'end_{es.id}': '15:30',
            f'duration_{es.id}': '90',
            f'order_{es.id}': '2',
        }
        res_post = self.client.post(url, post_data)
        self.assertEqual(res_post.status_code, 302)

        es.refresh_from_db()
        self.assertEqual(es.subject, self.sub_geo)
        self.assertEqual(es.exam_date, date(2026, 6, 11))
        self.assertEqual(es.session, 'AFTERNOON')
        self.assertEqual(es.start_time, time(14, 0))
        self.assertEqual(es.end_time, time(15, 30))
        self.assertEqual(es.effective_duration_minutes, 90)
        self.assertEqual(es.order, 2)

    def test_exam_schedule_apply_photo_preset(self):
        """Test applying the exact 10-subject 3-day preset matching the photo."""
        url = reverse('standardized_exam_schedule_apply_photo_preset', args=[self.exam.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

        subjects = list(self.exam.exam_subjects.all().order_by('order'))
        self.assertEqual(len(subjects), 10)

        # Day 1 checks (offset 0 -> 2026-06-10)
        s1 = subjects[0]
        self.assertIn("គណិត", s1.subject.name_kh)
        self.assertEqual(s1.exam_date, date(2026, 6, 10))
        self.assertEqual(s1.session, 'MORNING')
        self.assertEqual(s1.start_time, time(7, 30))
        self.assertEqual(s1.end_time, time(9, 0))
        self.assertEqual(s1.effective_duration_minutes, 90)

        # Day 3 Khmer check (offset 2 -> 2026-06-12)
        s9 = subjects[8]
        self.assertTrue("តែងសេចក្តី" in s9.subject.name_kh or "ភាសាខ្មែរ" in s9.subject.name_kh)
        self.assertEqual(s9.exam_date, date(2026, 6, 12))
        self.assertEqual(s9.start_time, time(7, 30))
        self.assertEqual(s9.end_time, time(10, 0))
        self.assertEqual(s9.effective_duration_minutes, 150)

    def test_exam_schedule_print_view(self):
        """Test print view rendering with Khmer numerals matching the reference photo."""
        # First apply preset
        self.client.get(reverse('standardized_exam_schedule_apply_photo_preset', args=[self.exam.id]))

        url = reverse('standardized_exam_schedule_print', args=[self.exam.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Verify national motto
        self.assertContains(response, "ព្រះរាជាណាចក្រកម្ពុជា")
        self.assertContains(response, "ជាតិ សាសនា ព្រះមហាក្សត្រ")

        # Verify title
        self.assertContains(response, "តារាងប្រព្រឹត្តទៅ នៃវិញ្ញាសា")
        self.assertContains(response, "ប្រឡងតេស្តវាស់ស្ទង់ជា ប្រចាំឆមាសទី២")
        self.assertContains(response, "ថ្នាក់ទី ១២")
        self.assertContains(response, "វិទ្យាសាស្ត្រសង្គម")
        self.assertContains(response, "សម័យប្រឡង៖ ១០ មិថុនា ២០២៦")

        # Verify days and shifts
        self.assertContains(response, "ថ្ងៃទី១ ( ថ្ងៃពុធ ទី១០ ខែមិថុនា ឆ្នាំ២០២៦ )")
        self.assertContains(response, "ពេលព្រឹក ៖")
        self.assertContains(response, "ម៉ោង ០៧ : ៣០")
        self.assertContains(response, "ដល់ម៉ោង")
        self.assertContains(response, "០៩ : ០០")
        self.assertContains(response, "( ៩០ នាទី )")
        self.assertContains(response, "ពេលរសៀល ៖")

        # Verify Day 2 & Day 3
        self.assertContains(response, "ថ្ងៃទី២")
        self.assertContains(response, "ថ្ងៃទី៣")
        self.assertContains(response, "( ១៥០ នាទី )")

        # Verify signature
        self.assertContains(response, "នាយក")
        self.assertContains(response, "ឈិន កុសល")

if __name__ == '__main__':
    import unittest
    unittest.main()
