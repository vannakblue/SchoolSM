import sys
import django
import os

sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.teachers.models import Teacher
from apps.academics.models import ClassSubject, Timetable, Classroom, Subject

def run_verify():
    print("=" * 80)
    print("VERIFY TEACHER ASSIGNMENTS MATRIX IN WEB BROWSER")
    print("=" * 80)

    u = User.objects.filter(role=User.Role.ADMIN).first()
    client = Client()
    client.force_login(u)

    res = client.get('/academics/teacher-assignments/')
    print(f"Status Code: {res.status_code}")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"

    ctx = res.context
    teachers = ctx['teachers']
    teacher_stats = ctx['teacher_stats']
    print(f"Total Active Teachers listed: {len(teachers)}")
    print(f"Total Teacher Stats calculated: {len(teacher_stats)}")

    # Check some sample teachers:
    sample_names = ['កាន ដាវី', 'ផល ឌីណា', 'យូ ម៉ាលីស', 'ឆេង សុជាតា', 'ឡុច សាវិន', 'សាន់ កឿន']
    for t_name in sample_names:
        stat = next((s for s in teacher_stats if s['teacher'].khmer_name == t_name), None)
        if stat:
            tch = stat['teacher']
            cnt = stat['assigned_count']
            hrs = stat['assigned_hours']
            quota = stat['max_weekly_hours']
            print(f"  ✓ {tch.khmer_name:<16} (ID: {tch.id}) | Classes: {cnt:2d} | Weekly Hours: {hrs:2d}h | Quota: {quota}h")

    # Verify when selecting a specific teacher
    kan_davy = Teacher.objects.filter(khmer_name='កាន ដាវី').first()
    res_davy = client.get(f'/academics/teacher-assignments/?teacher={kan_davy.id}')
    assert res_davy.status_code == 200
    ctx_davy = res_davy.context
    grid = ctx_davy['matrix_grid']
    print(f"\nMatrix grid rows for {kan_davy.khmer_name}: {len(grid)} classrooms")
    # Kan Davy is assigned to 7A, 7B, 7C, 7D Math
    checked_cells = []
    for row in grid:
        cls_name = row['classroom'].name
        for cell in row['cells']:
            if cell['is_checked']:
                checked_cells.append(f"{cls_name} - {cell['subject'].name_kh}")
    print(f"Checked cells in matrix for {kan_davy.khmer_name}: {checked_cells}")
    assert len(checked_cells) == 4, f"Expected 4 checked cells for Kan Davy (7A, 7B, 7C, 7D Math), got {len(checked_cells)}"

    # Check Timetable entries count
    tt_count = Timetable.objects.count()
    print(f"\nTotal Timetable slots in database: {tt_count}")
    assert tt_count > 1000, f"Expected > 1000 timetable slots, got {tt_count}"

    print("\n" + "=" * 80)
    print("ALL VERIFICATIONS PASSED 100%! TEACHER ASSIGNMENTS MATRIX FULLY FUNCTIONAL!")
    print("=" * 80)

if __name__ == '__main__':
    run_verify()
