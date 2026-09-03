import os, sys, django
if sys.stdout and sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from apps.academics.models import AcademicYear, Classroom, ClassSubject

ay = AcademicYear.objects.filter(name='2026-2027').first()
print(f"=== SAMPLE TEACHER ASSIGNMENTS IN YEAR: '{ay.name}' ===")

sample_classes = ['7A', '8A', '9A', '10A', '11A', '12A']
for ccode in sample_classes:
    cls_obj = Classroom.objects.filter(academic_year=ay, code=ccode).first()
    if not cls_obj:
        continue
    cs_list = ClassSubject.objects.filter(classroom=cls_obj).select_related('subject', 'teacher').order_by('subject__order')
    print(f"\n--- {cls_obj.name} ({cls_obj.code}) | Total Subjects Assigned: {cs_list.count()} ---")
    for cs in cs_list:
        tch_name = cs.teacher.khmer_name if cs.teacher else 'N/A'
        tch_duty = cs.teacher.current_duty if cs.teacher else ''
        print(f"    - {cs.subject.name_kh:20s} ({cs.subject.code:3s}): គ្រូបង្រៀន = {tch_name:22s} [និម្មិតសញ្ញា: {tch_duty}]")
