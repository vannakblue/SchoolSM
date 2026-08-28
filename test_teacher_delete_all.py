import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import TestCase, Client
from apps.accounts.models import User
from apps.teachers.models import Teacher, TeacherAttendance, TeacherLeaveRequest, TeacherPunchLog, TeacherBiometricProfile
from apps.academics.models import AcademicYear, Classroom, Subject, ClassSubject
from datetime import date, time, datetime
from decimal import Decimal

def run_tests():
    print("======================================================================")
    print("[TEST] RUNNING TESTS FOR TEACHER DELETE ALL & SINGLE DELETE")
    print("======================================================================")

    # 1. Setup Admin, Teacher User, and Dummy Teachers
    admin_user, _ = User.objects.get_or_create(
        username='test_admin_delete',
        defaults={'role': User.Role.ADMIN, 'khmer_name': 'Admin Delete Test'}
    )
    admin_user.set_password('pass123')
    admin_user.save()

    regular_user, _ = User.objects.get_or_create(
        username='test_staff_delete',
        defaults={'role': User.Role.TEACHER, 'khmer_name': 'Staff Test'}
    )
    regular_user.set_password('pass123')
    regular_user.save()

    # Create dummy teachers
    t1_user, _ = User.objects.get_or_create(
        username='tch_del_1',
        defaults={'role': User.Role.TEACHER, 'khmer_name': 'គ្រូ តេស្ត ១', 'latin_name': 'Teacher 1'}
    )
    t1_user.set_password('pass123')
    t1_user.save()

    t1, _ = Teacher.objects.get_or_create(
        teacher_id='TCH-DEL-01',
        defaults={
            'user': t1_user,
            'khmer_name': 'គ្រូ តេស្ត ១',
            'latin_name': 'Teacher 1',
            'specialization': 'គណិតវិទ្យា',
            'phone': '012345671',
            'base_salary': Decimal('450.00'),
            'status': Teacher.Status.ACTIVE
        }
    )

    t2_user, _ = User.objects.get_or_create(
        username='tch_del_2',
        defaults={'role': User.Role.TEACHER, 'khmer_name': 'គ្រូ តេស្ត ២', 'latin_name': 'Teacher 2'}
    )
    t2_user.set_password('pass123')
    t2_user.save()

    t2, _ = Teacher.objects.get_or_create(
        teacher_id='TCH-DEL-02',
        defaults={
            'user': t2_user,
            'khmer_name': 'គ្រូ តេស្ត ២',
            'latin_name': 'Teacher 2',
            'specialization': 'រូបវិទ្យា',
            'phone': '012345672',
            'base_salary': Decimal('500.00'),
            'status': Teacher.Status.ACTIVE
        }
    )

    # Attach related items
    TeacherAttendance.objects.create(
        teacher=t1,
        date=date.today(),
        status=TeacherAttendance.Status.PRESENT
    )
    TeacherPunchLog.objects.create(
        teacher=t1,
        date=date.today(),
        punch_time=datetime.now(),
        method=TeacherPunchLog.Method.QR_SCAN
    )
    TeacherBiometricProfile.objects.create(
        teacher=t1,
        is_enrolled_face=True
    )

    print(f"Initial Teacher count: {Teacher.objects.count()}")

    client = Client()

    # 2. Test Non-Admin cannot delete
    client.login(username='test_staff_delete', password='pass123')
    res = client.post('/teachers/delete-all/')
    print(f"[TEST 1] Non-admin POST /teachers/delete-all/ -> Status code: {res.status_code}")
    assert res.status_code == 302 or res.status_code == 403, f"Expected 302 or 403, got {res.status_code}"

    # 3. Test Single Delete with Admin
    client.login(username='test_admin_delete', password='pass123')
    del_res = client.post(f'/teachers/{t2.id}/delete/')
    print(f"[TEST 2] Admin POST /teachers/{t2.id}/delete/ -> Status code: {del_res.status_code}")
    assert del_res.status_code == 302
    assert not Teacher.objects.filter(id=t2.id).exists(), "Teacher 2 should be deleted"
    assert not User.objects.filter(id=t2_user.id).exists(), "Teacher 2 user account should be deleted"
    print("  -> Single delete verified successfully!")

    # 4. Test Delete All Teachers with Admin
    all_res = client.post('/teachers/delete-all/')
    print(f"[TEST 3] Admin POST /teachers/delete-all/ -> Status code: {all_res.status_code}")
    assert all_res.status_code == 302
    assert Teacher.objects.count() == 0, f"Expected 0 teachers, found {Teacher.objects.count()}"
    assert not User.objects.filter(id=t1_user.id).exists(), "Teacher 1 user account should be deleted"
    assert not TeacherAttendance.objects.filter(teacher_id=t1.id).exists(), "Teacher 1 attendances should be cascade deleted"
    assert not TeacherPunchLog.objects.filter(teacher_id=t1.id).exists(), "Teacher 1 punch logs should be cascade deleted"
    print("  -> Delete all teachers verified successfully!")

    # 5. Test Delete All when already empty
    empty_res = client.post('/teachers/delete-all/')
    print(f"[TEST 4] Admin POST /teachers/delete-all/ on empty DB -> Status code: {empty_res.status_code}")
    assert empty_res.status_code == 302
    print("  -> Empty delete all handled gracefully!")

    # Cleanup test users
    admin_user.delete()
    regular_user.delete()

    # Restore standard demo teachers for system integrity
    teachers_info = [
        ('TCH-001', 'teacher1', 'លី វណ្ណារ៉ា', 'LY VANNARA', 'M', 'គណិតវិទ្យា & រូបវិទ្យា', 'បរិញ្ញាបត្រគរុកោសល្យ', Decimal('650.00'), '012 111 222'),
        ('TCH-002', 'teacher2', 'ចាន់ សុភាព', 'CHAN SOPHEAP', 'F', 'ភាសាខ្មែរ & តែងសេចក្តី', 'បរិញ្ញាបត្រអក្សរសាស្ត្រ', Decimal('600.00'), '012 222 333'),
        ('TCH-003', 'teacher3', 'កែវ វិបុល', 'KEO VIBOL', 'M', 'គីមីវិទ្យា & ជីវវិទ្យា', 'អនុបណ្ឌិតគីមីវិទ្យា', Decimal('620.00'), '012 333 444'),
        ('TCH-004', 'teacher4', 'ស៊ិន ស្រីនាង', 'SIN SREINEANG', 'F', 'អង់គ្លេស & គេហវិទ្យា', 'បរិញ្ញាបត្រភាសាអង់គ្លេស (TEFL)', Decimal('580.00'), '012 444 555'),
        ('TCH-005', 'teacher5', 'សេង ពិសិដ្ឋ', 'SENG PISETH', 'M', 'ប្រវត្តិវិទ្យា, ភូមិវិទ្យា & សីលធម៌', 'បរិញ្ញាបត្រប្រវត្តិវិទ្យា', Decimal('550.00'), '012 555 666'),
        ('TCH-006', 'teacher6', 'ម៉ែន សុផាត', 'MEN SOPHAT', 'M', 'ផែនដីវិទ្យា & សេដ្ឋកិច្ច', 'បរិញ្ញាបត្រវិទ្យាសាស្ត្រសេដ្ឋកិច្ច', Decimal('600.00'), '012 666 777'),
    ]
    created_teachers = []
    for tid, uname, kh_name, en_name, gender, spec, qual, salary, phone in teachers_info:
        u, _ = User.objects.get_or_create(
            username=uname,
            defaults={'role': User.Role.TEACHER, 'khmer_name': kh_name, 'latin_name': en_name, 'phone': phone}
        )
        u.set_password('password123')
        u.save()
        tch, _ = Teacher.objects.get_or_create(
            teacher_id=tid,
            defaults={
                'user': u,
                'khmer_name': kh_name,
                'latin_name': en_name,
                'gender': gender,
                'specialization': spec,
                'qualification': qual,
                'base_salary': salary,
                'phone': phone,
                'hire_date': date(2023, 10, 1),
                'status': Teacher.Status.ACTIVE
            }
        )
        created_teachers.append(tch)

    # Re-link classrooms and class subjects
    from apps.academics.models import GradeLevelRule, ClassSubject
    for cls in Classroom.objects.all():
        sub_ids = list(GradeLevelRule.objects.filter(grade_level=cls.grade_level, track=cls.track).values_list('subject_id', flat=True))
        if sub_ids:
            cls.sync_assigned_subjects(sub_ids)
        for idx, cs in enumerate(ClassSubject.objects.filter(classroom=cls)):
            cs.teacher = created_teachers[idx % len(created_teachers)]
            cs.save(update_fields=['teacher'])

    print("======================================================================")
    print("[SUCCESS] ALL TESTS PASSED SUCCESSFULLY & DEMO DATA RESTORED!")
    print("======================================================================")

if __name__ == '__main__':
    run_tests()
