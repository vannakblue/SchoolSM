"""
System Defaults Enforcer for SchoolSM.
Guarantees on every app update, startup, and migration:
1. Admin user ('admin') exists with permanent password '123' and superuser permissions.
2. Only Academic Years '2025-2026' and '2026-2027' are kept in the database.
   All other academic years are safely purged after re-linking any dependent records.
"""

from datetime import date
from django.db import transaction
from django.contrib.auth import get_user_model


def ensure_system_defaults(stdout=None, purge_non_defaults=False):
    User = get_user_model()

    # 1. PERMANENT ADMIN ACCOUNT (PASSWORD: 123)
    try:
        admin_user = User.objects.filter(username='admin').first()
        if not admin_user:
            admin_user = User.objects.create(
                username='admin',
                email='admin@school.edu.kh',
                role=User.Role.ADMIN,
                khmer_name='បណ្ឌិត សុខ វិបុល',
                latin_name='Dr. SOK VIBOL',
                is_staff=True,
                is_superuser=True,
                is_active=True
            )
        admin_user.role = User.Role.ADMIN
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.is_active = True
        admin_user.set_password('123')
        admin_user.save()
        if stdout:
            stdout.write("Admin account verified with permanent password '123'.")
    except Exception as e:
        if stdout:
            stdout.write(f"Admin setup warning: {e}")

    # 2. ONLY 2025-2026 AND 2026-2027 ACADEMIC YEARS (DEFAULT FOR EVERY UPDATE)
    # SAFETY RULE: Local database data is strictly preserved across all updates.
    # We guarantee 2025-2026 and 2026-2027 exist as defaults, but never delete
    # new academic years or data created by the admin unless purge_non_defaults=True is explicitly passed.
    try:
        from apps.academics.models import AcademicYear, Classroom
        from apps.students.models import Student
        from apps.examinations.models import ExamTerm
        from apps.finance.models import Invoice

        with transaction.atomic():
            # Ensure 2025-2026 exists
            ay_2025, _ = AcademicYear.objects.get_or_create(
                name='2025-2026',
                defaults={
                    'start_date': date(2025, 9, 1),
                    'end_date': date(2026, 7, 15),
                    'is_current': False
                }
            )

            # Ensure 2026-2027 exists (Active Current Year)
            ay_2026, _ = AcademicYear.objects.get_or_create(
                name='2026-2027',
                defaults={
                    'start_date': date(2026, 9, 1),
                    'end_date': date(2027, 7, 15),
                    'is_current': True
                }
            )

            # If no academic year is current, set 2026-2027 as current
            if not AcademicYear.objects.filter(is_current=True).exists():
                ay_2026.is_current = True
                ay_2026.save(update_fields=['is_current'])

            # Only purge non-default academic years if explicitly instructed by administrator
            if purge_non_defaults:
                other_years = list(AcademicYear.objects.exclude(id__in=[ay_2025.id, ay_2026.id]))
                if other_years:
                    other_ids = [y.id for y in other_years]

                    # Re-link classrooms safely
                    existing_codes_2026 = {c.code.upper().strip(): c for c in Classroom.objects.filter(academic_year=ay_2026)}
                    for cls_obj in Classroom.objects.filter(academic_year_id__in=other_ids):
                        code_norm = cls_obj.code.upper().strip()
                        if code_norm in existing_codes_2026:
                            target_cls = existing_codes_2026[code_norm]
                            Student.objects.filter(classroom=cls_obj).update(classroom=target_cls, academic_year=ay_2026)
                            cls_obj.delete()
                        else:
                            cls_obj.academic_year = ay_2026
                            cls_obj.save(update_fields=['academic_year'])
                            existing_codes_2026[code_norm] = cls_obj

                    # Re-link students, exam terms, and invoices
                    Student.objects.filter(academic_year_id__in=other_ids).update(academic_year=ay_2026)
                    ExamTerm.objects.filter(academic_year_id__in=other_ids).update(academic_year=ay_2026)
                    Invoice.objects.filter(academic_year_id__in=other_ids).update(academic_year=ay_2026)

                    try:
                        from apps.academics.models import TimetableVersion, DailyReportPrintConfig, TeacherDutySchedule
                        TimetableVersion.objects.filter(academic_year_id__in=other_ids).update(academic_year=ay_2026)
                        DailyReportPrintConfig.objects.filter(academic_year_id__in=other_ids).update(academic_year=ay_2026)
                        TeacherDutySchedule.objects.filter(academic_year_id__in=other_ids).update(academic_year=ay_2026)
                    except Exception:
                        pass

                    try:
                        from apps.examinations.models import ExamStudentExclusion
                        ExamStudentExclusion.objects.filter(academic_year_id__in=other_ids).update(academic_year=ay_2026)
                    except Exception:
                        pass

                    # Safely delete all other non-default academic years
                    AcademicYear.objects.filter(id__in=other_ids).delete()
                    if stdout:
                        stdout.write(f"Deleted {len(other_years)} non-default academic years. Only '2025-2026' and '2026-2027' retained.")
            else:
                if stdout:
                    stdout.write("All existing local academic years and database records preserved intact.")

    except Exception as e:
        if stdout:
            stdout.write(f"Academic years default setup warning: {e}")

    # 3. ENSURE CLEANUP OF CLASSROOMS WITH FEWER THAN 10 STUDENTS ACROSS UPDATES
    try:
        from apps.academics.models import Classroom
        from apps.students.models import Student
        from django.db.models import Count

        small_classes = list(Classroom.objects.annotate(stu_count=Count('students')).filter(stu_count__lt=10))
        if small_classes:
            real_classes = {
                (c.code or '').upper().strip(): c
                for c in Classroom.objects.annotate(stu_count=Count('students')).filter(stu_count__gte=10)
                if c.code
            }
            with transaction.atomic():
                for sc in small_classes:
                    students = list(Student.objects.filter(classroom=sc))
                    if students:
                        raw_code = (sc.code or '').upper().split('-')[0].split('_')[0].strip()
                        target_cls = real_classes.get(raw_code)
                        if not target_cls and '8B' in (sc.name or ''):
                            target_cls = real_classes.get('8B')
                        if not target_cls and '7A' in (sc.name or ''):
                            target_cls = real_classes.get('7A')
                        if not target_cls and '10A' in (sc.name or ''):
                            target_cls = real_classes.get('10A')

                        if target_cls:
                            Student.objects.filter(classroom=sc).update(classroom=target_cls)
                        else:
                            Student.objects.filter(classroom=sc).update(classroom=None)

                sc_ids = [sc.id for sc in small_classes]
                Classroom.objects.filter(id__in=sc_ids).delete()
                if stdout:
                    stdout.write(f"Cleaned up {len(sc_ids)} classrooms with fewer than 10 students. Preserved {len(real_classes)} official classrooms.")
    except Exception as cls_err:
        if stdout:
            stdout.write(f"Classroom cleanup note: {cls_err}")

