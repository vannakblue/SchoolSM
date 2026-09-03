import os
import django
import datetime
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from apps.academics.models import AcademicYear
from apps.teachers.models import Teacher
from apps.examinations.models import (
    ExamInvigilatorPlan, TeacherDutyGroup, TeacherDutyQuota,
    ExamShiftSlot, TeacherShiftRegistration
)

User = get_user_model()

class TeacherInvigilatorShiftSystemTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Create Academic Year
        self.academic_year = AcademicYear.objects.create(
            name="2025-2026",
            start_date=datetime.date(2025, 10, 1),
            end_date=datetime.date(2026, 8, 31),
            is_current=True
        )

        # Create Admin User
        self.admin_user = User.objects.create_superuser(
            username="admin_test",
            email="admin@test.com",
            password="adminpassword123",
            role="ADMIN"
        )

        # Create Teacher Users & Profiles
        self.teacher_user_1 = User.objects.create_user(
            username="teacher_regular",
            email="t1@test.com",
            password="teacherpassword123",
            role="TEACHER"
        )
        self.teacher_1 = Teacher.objects.create(
            user=self.teacher_user_1,
            teacher_id="T-001",
            khmer_name="សុក ចាន់ថន",
            latin_name="Sok Chanthon",
            gender="M",
            current_duty="គ្រូបង្រៀនគណិតវិទ្យា",
            status=Teacher.Status.ACTIVE
        )

        self.teacher_user_2 = User.objects.create_user(
            username="teacher_office",
            email="t2@test.com",
            password="teacherpassword123",
            role="TEACHER"
        )
        self.teacher_2 = Teacher.objects.create(
            user=self.teacher_user_2,
            teacher_id="T-002",
            khmer_name="កែវ ពិសិដ្ឋ",
            latin_name="Keo Piseth",
            gender="M",
            current_duty="គ្រូការិយាល័យរដ្ឋបាល",
            status=Teacher.Status.ACTIVE
        )

    def test_01_plan_creation_and_auto_groups(self):
        """Test creating a plan auto-generates groups, quotas, and shift slots."""
        self.client.force_login(self.admin_user)
        url = reverse('exam_invigilator_plan_create')

        response = self.client.post(url, {
            'title': 'សម័យប្រឡងតេស្តស្តង់ដា ឆមាសទី១',
            'academic_year': self.academic_year.id,
            'start_date': '2026-09-10',
            'end_date': '2026-09-12',
            'default_regular_quota': 4,
            'default_office_quota': 5,
            'auto_create_slots': 'on',
            'slots_capacity': 10,
            'is_active': 'on',
            'allow_teacher_registration': 'on',
            'description': 'សូមគ្រូទាំងអស់សុំវេនឱ្យបានគ្រប់'
        })
        self.assertEqual(response.status_code, 302)

        plan = ExamInvigilatorPlan.objects.get(title='សម័យប្រឡងតេស្តស្តង់ដា ឆមាសទី១')
        self.assertTrue(plan.is_active)
        self.assertEqual(plan.default_regular_quota, 4)
        self.assertEqual(plan.default_office_quota, 5)

        # 3 days * 2 slots (Morning + Afternoon) = 6 slots
        self.assertEqual(plan.shift_slots.count(), 6)

        # Duty Groups created
        self.assertTrue(plan.duty_groups.filter(name__icontains='ធម្មតា', required_shifts=4).exists())
        self.assertTrue(plan.duty_groups.filter(name__icontains='ការិយាល័យ', required_shifts=5).exists())

        # Quotas auto-assigned according to duty
        q1 = TeacherDutyQuota.objects.get(plan=plan, teacher=self.teacher_1)
        q2 = TeacherDutyQuota.objects.get(plan=plan, teacher=self.teacher_2)
        self.assertEqual(q1.effective_required_shifts, 4)
        self.assertEqual(q2.effective_required_shifts, 5)

    def test_02_strict_gate_inactive_plan_blocks_and_hides_from_teacher(self):
        """When plan is inactive, teacher portal is locked, direct API fails, and sidebar menu is omitted."""
        plan = ExamInvigilatorPlan.objects.create(
            academic_year=self.academic_year,
            title="សម័យប្រឡងតេស្ត",
            start_date=datetime.date(2026, 9, 10),
            end_date=datetime.date(2026, 9, 11),
            is_active=False, # INACTIVE
            allow_teacher_registration=False
        )
        slot = ExamShiftSlot.objects.create(
            plan=plan,
            date=datetime.date(2026, 9, 10),
            session='MORNING',
            session_name='ព្រឹក ថ្ងៃទី១',
            max_invigilators=5
        )

        # Log in as regular teacher
        self.client.force_login(self.teacher_user_1)

        # 1. Teacher Portal should render inactive message
        res_portal = self.client.get(reverse('exam_invigilator_teacher_portal'))
        self.assertEqual(res_portal.status_code, 200)
        self.assertContains(res_portal, "ការស្នើសុំវេនអនុរក្សមិនទាន់បើកដំណើរការ")

        # 2. Direct AJAX toggle should return 403 Forbidden
        res_ajax = self.client.post(reverse('api_toggle_invigilator_slot'), {'slot_id': slot.id})
        self.assertEqual(res_ajax.status_code, 403)

        # 3. Sidebar context should omit exam_invigilator_request
        from apps.accounts.context_processors import user_role_context
        class DummyRequest:
            user = self.teacher_user_1
            path = '/'
            COOKIES = {}
            META = {}
            resolver_match = None
        ctx = user_role_context(DummyRequest())
        all_visible_keys = [item['key'] for sec in ctx.get('sidebar_catalog', []) for item in sec.get('visible_items', [])]
        self.assertNotIn('exam_invigilator_request', all_visible_keys)

    def test_03_active_plan_allows_slot_toggle_and_quota_tracking(self):
        """When plan is active, teacher can toggle slots and see live quota progress."""
        plan = ExamInvigilatorPlan.objects.create(
            academic_year=self.academic_year,
            title="សម័យប្រឡងសកម្ម",
            start_date=datetime.date(2026, 9, 10),
            end_date=datetime.date(2026, 9, 11),
            is_active=True,
            allow_teacher_registration=True,
            default_regular_quota=4
        )
        slot1 = ExamShiftSlot.objects.create(
            plan=plan,
            date=datetime.date(2026, 9, 10),
            session='MORNING',
            session_name='ព្រឹក ថ្ងៃទី១',
            max_invigilators=2
        )
        slot2 = ExamShiftSlot.objects.create(
            plan=plan,
            date=datetime.date(2026, 9, 10),
            session='AFTERNOON',
            session_name='រសៀល ថ្ងៃទី១',
            max_invigilators=2
        )

        self.client.force_login(self.teacher_user_1)

        # 1. Toggle ON slot 1
        res1 = self.client.post(reverse('api_toggle_invigilator_slot'), {'slot_id': slot1.id})
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertTrue(data1['success'])
        self.assertTrue(data1['is_registered'])
        self.assertEqual(data1['current_count'], 1)
        self.assertEqual(data1['remaining_to_choose'], 3)
        self.assertEqual(slot1.registrations.count(), 1)

        # 2. Toggle OFF slot 1
        res2 = self.client.post(reverse('api_toggle_invigilator_slot'), {'slot_id': slot1.id})
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertFalse(data2['is_registered'])
        self.assertEqual(data2['current_count'], 0)
        self.assertEqual(slot1.registrations.count(), 0)

    def test_04_capacity_limit_prevents_overbooking(self):
        """When slot reaches max_invigilators capacity, next teacher cannot register."""
        plan = ExamInvigilatorPlan.objects.create(
            academic_year=self.academic_year,
            title="សម័យប្រឡងសកម្ម",
            start_date=datetime.date(2026, 9, 10),
            end_date=datetime.date(2026, 9, 10),
            is_active=True,
            allow_teacher_registration=True
        )
        slot = ExamShiftSlot.objects.create(
            plan=plan,
            date=datetime.date(2026, 9, 10),
            session='MORNING',
            session_name='ព្រឹក ថ្ងៃទី១',
            max_invigilators=1 # Capacity 1
        )

        # Teacher 1 registers
        TeacherShiftRegistration.objects.create(slot=slot, teacher=self.teacher_1, status='CONFIRMED')
        self.assertTrue(slot.is_full)

        # Teacher 2 tries to register
        self.client.force_login(self.teacher_user_2)
        res = self.client.post(reverse('api_toggle_invigilator_slot'), {'slot_id': slot.id})
        self.assertEqual(res.status_code, 400)
        data = res.json()
        self.assertFalse(data['success'])
        self.assertIn("ពេញ", data['error'])

    def test_05_admin_auto_assign_fills_empty_spots(self):
        """1-Click Auto-Assign distributes unfulfilled teachers to available slots."""
        plan = ExamInvigilatorPlan.objects.create(
            academic_year=self.academic_year,
            title="សម័យប្រឡង Auto-Assign",
            start_date=datetime.date(2026, 9, 10),
            end_date=datetime.date(2026, 9, 10),
            is_active=True,
            default_regular_quota=2
        )
        slot1 = ExamShiftSlot.objects.create(
            plan=plan, date=datetime.date(2026, 9, 10), session='MORNING', session_name='ព្រឹក', max_invigilators=150
        )
        slot2 = ExamShiftSlot.objects.create(
            plan=plan, date=datetime.date(2026, 9, 10), session='AFTERNOON', session_name='រសៀល', max_invigilators=150
        )

        self.client.force_login(self.admin_user)
        res = self.client.post(reverse('api_invigilator_auto_assign', kwargs={'plan_id': plan.id}))
        self.assertEqual(res.status_code, 302)

        # Both teachers should now have assigned slots
        reg_count_t1 = TeacherShiftRegistration.objects.filter(slot__plan=plan, teacher=self.teacher_1).count()
        reg_count_t2 = TeacherShiftRegistration.objects.filter(slot__plan=plan, teacher=self.teacher_2).count()
        self.assertGreaterEqual(reg_count_t1, 1)
        self.assertGreaterEqual(reg_count_t2, 1)
        self.assertGreaterEqual(TeacherShiftRegistration.objects.filter(slot__plan=plan).count(), 10)

    def test_06_mobile_api_endpoints(self):
        """Mobile API endpoints return JSON status, slots, and allow toggling."""
        plan = ExamInvigilatorPlan.objects.create(
            academic_year=self.academic_year,
            title="សម័យប្រឡង Mobile Test",
            start_date=datetime.date(2026, 9, 10),
            end_date=datetime.date(2026, 9, 10),
            is_active=True,
            default_regular_quota=4
        )
        slot = ExamShiftSlot.objects.create(
            plan=plan, date=datetime.date(2026, 9, 10), session='MORNING', session_name='ព្រឹក', max_invigilators=10
        )

        self.client.force_login(self.teacher_user_1)

        # 1. Status API
        res_status = self.client.get(reverse('mobile_api_invigilator_status'))
        self.assertEqual(res_status.status_code, 200)
        data_status = res_status.json()
        self.assertTrue(data_status['is_active'])
        self.assertEqual(data_status['teacher']['required_shifts'], 4)

        # 2. Slots API
        res_slots = self.client.get(reverse('mobile_api_invigilator_slots'))
        self.assertEqual(res_slots.status_code, 200)
        data_slots = res_slots.json()
        self.assertEqual(len(data_slots['slots']), 1)

        # 3. Toggle API
        res_toggle = self.client.post(
            reverse('mobile_api_invigilator_toggle'),
            {'slot_id': slot.id},
            content_type='application/json'
        )
        self.assertEqual(res_toggle.status_code, 200)
        data_toggle = res_toggle.json()
        self.assertEqual(data_toggle['status'], 'success')
        self.assertTrue(data_toggle['is_registered'])
        self.assertEqual(data_toggle['current_count'], 1)
