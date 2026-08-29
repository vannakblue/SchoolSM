from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.core.exceptions import ValidationError
from django.db.models import Q, Count
from decimal import Decimal
import datetime
import json
import csv
import os
from apps.accounts.decorators import role_required
from .models import AcademicYear, Classroom, Subject, ClassSubject, Timetable, GradeLevelRule, SavedDefaultConfig, GradeLevel, Province, District, Commune, Village, GradeEnrollmentOption, AcademicTrack
from .forms import ClassroomForm, SubjectForm, TimetableForm, GradeLevelForm, AcademicYearForm, GradeEnrollmentOptionForm, AcademicTrackForm
from apps.students.models import Student
from apps.teachers.models import Teacher
from apps.examinations.models import Grade, ExamTerm

# Official 14 MoEYS Subjects in EXACT specified order
DEFAULT_MOEYS_SUBJECTS = [
    ('តែងសេចក្តី', 'Composition / Essay', 'R', 2, '#4f46e5', 1),
    ('សរសេរតាមអាន', 'Dictation', 'D', 2, '#6366f1', 2),
    ('ភាសាខ្មែរ', 'Khmer Language', 'K', 4, '#0ea5e9', 3),
    ('សីលធម៌', 'Civics & Moral / Ethics', 'I', 2, '#06b6d4', 4),
    ('ភូមិវិទ្យា', 'Geography', 'G', 2, '#d97706', 5),
    ('ប្រវត្តិវិទ្យា', 'History', 'H', 2, '#f59e0b', 6),
    ('គណិតវិទ្យា', 'Mathematics', 'M', 4, '#dc2626', 7),
    ('ផែនដីវិទ្យា', 'Earth Science', 'Es', 2, '#84cc16', 8),
    ('រូបវិទ្យា', 'Physics', 'P', 3, '#8b5cf6', 9),
    ('គីមីវិទ្យា', 'Chemistry', 'C', 3, '#10b981', 10),
    ('ជីវវិទ្យា', 'Biology', 'B', 3, '#14b8a6', 11),
    ('គេហវិទ្យា', 'Home Economics', 'He', 2, '#ec4899', 12),
    ('សេដ្ឋកិច្ច', 'Economics', 'Ec', 2, '#f97316', 13),
    ('អង់គ្លេស', 'English Language', 'E', 3, '#3b82f6', 14),
]

OFFICIAL_CODES = [s[2] for s in DEFAULT_MOEYS_SUBJECTS]

DEFAULT_MOEYS_STREAMS = [
    ('ថ្នាក់ទី ៧', 7, 'GENERAL', 1),
    ('ថ្នាក់ទី ៨', 8, 'GENERAL', 2),
    ('ថ្នាក់ទី ៩', 9, 'GENERAL', 3),
    ('ថ្នាក់ទី ១០', 10, 'GENERAL', 4),
    ('ថ្នាក់ទី ១១ វិទ្យាសាស្ត្រសង្គម', 11, 'SOCIAL', 5),
    ('ថ្នាក់ទី ១១ វិទ្យាសាស្ត្រ', 11, 'SCIENCE', 6),
    ('ថ្នាក់ទី ១២ វិទ្យាសាស្ត្រសង្គម', 12, 'SOCIAL', 7),
    ('ថ្នាក់ទី ១២ វិទ្យាសាស្ត្រ', 12, 'SCIENCE', 8),
]

# Official MoEYS Standard Scoring Rules Matrix for the 8 Streams
MOEYS_SCORING_RULES = {
    (7, 'GENERAL'): {
        'តែងសេចក្តី': 60, 'សរសេរតាមអាន': 40, 'សីលធម៌': 50, 'ភូមិវិទ្យា': 50, 'ប្រវត្តិវិទ្យា': 50,
        'គណិតវិទ្យា': 100, 'ផែនដីវិទ្យា': 50, 'រូបវិទ្យា': 50, 'គីមីវិទ្យា': 50, 'ជីវវិទ្យា': 50,
        'គេហវិទ្យា': 50, 'អង់គ្លេស': 50
    },
    (8, 'GENERAL'): {
        'តែងសេចក្តី': 60, 'សរសេរតាមអាន': 40, 'សីលធម៌': 50, 'ភូមិវិទ្យា': 50, 'ប្រវត្តិវិទ្យា': 50,
        'គណិតវិទ្យា': 100, 'ផែនដីវិទ្យា': 50, 'រូបវិទ្យា': 50, 'គីមីវិទ្យា': 50, 'ជីវវិទ្យា': 50,
        'គេហវិទ្យា': 50, 'អង់គ្លេស': 50
    },
    (9, 'GENERAL'): {
        'តែងសេចក្តី': 60, 'សរសេរតាមអាន': 40, 'សីលធម៌': 35, 'ភូមិវិទ្យា': 32, 'ប្រវត្តិវិទ្យា': 33,
        'គណិតវិទ្យា': 100, 'ផែនដីវិទ្យា': 25, 'រូបវិទ្យា': 35, 'គីមីវិទ្យា': 25, 'ជីវវិទ្យា': 35,
        'គេហវិទ្យា': 50, 'អង់គ្លេស': 50
    },
    (10, 'GENERAL'): {
        'ភាសាខ្មែរ': 150, 'សីលធម៌': 38, 'ភូមិវិទ្យា': 38, 'ប្រវត្តិវិទ្យា': 37,
        'គណិតវិទ្យា': 150, 'ផែនដីវិទ្យា': 25, 'រូបវិទ្យា': 50, 'គីមីវិទ្យា': 37,
        'ជីវវិទ្យា': 38, 'គេហវិទ្យា': 37, 'អង់គ្លេស': 100
    },
    (11, 'SOCIAL'): {
        'ភាសាខ្មែរ': 125, 'សីលធម៌': 75, 'ភូមិវិទ្យា': 75, 'ប្រវត្តិវិទ្យា': 75,
        'គណិតវិទ្យា': 75, 'ផែនដីវិទ្យា': 50, 'រូបវិទ្យា': 50, 'គីមីវិទ្យា': 50,
        'ជីវវិទ្យា': 50, 'សេដ្ឋកិច្ច': 50, 'អង់គ្លេស': 50
    },
    (11, 'SCIENCE'): {
        'ភាសាខ្មែរ': 75, 'សីលធម៌': 50, 'ភូមិវិទ្យា': 50, 'ប្រវត្តិវិទ្យា': 50,
        'គណិតវិទ្យា': 125, 'ផែនដីវិទ្យា': 50, 'រូបវិទ្យា': 75, 'គីមីវិទ្យា': 75,
        'ជីវវិទ្យា': 75, 'សេដ្ឋកិច្ច': 50, 'អង់គ្លេស': 50
    },
    (12, 'SOCIAL'): {
        'ភាសាខ្មែរ': 125, 'សីលធម៌': 75, 'ភូមិវិទ្យា': 75, 'ប្រវត្តិវិទ្យា': 75,
        'គណិតវិទ្យា': 75, 'ផែនដីវិទ្យា': 50, 'រូបវិទ្យា': 50, 'គីមីវិទ្យា': 50,
        'ជីវវិទ្យា': 50, 'សេដ្ឋកិច្ច': 50, 'អង់គ្លេស': 50
    },
    (12, 'SCIENCE'): {
        'ភាសាខ្មែរ': 75, 'សីលធម៌': 50, 'ភូមិវិទ្យា': 50, 'ប្រវត្តិវិទ្យា': 50,
        'គណិតវិទ្យា': 125, 'ផែនដីវិទ្យា': 50, 'រូបវិទ្យា': 75, 'គីមីវិទ្យា': 75,
        'ជីវវិទ្យា': 75, 'សេដ្ឋកិច្ច': 50, 'អង់គ្លេស': 50
    },
}

DEFAULT_MOEYS_CLASSROOMS = [
    ('7A', 'ថ្នាក់ទី ៧A', 7, Classroom.Track.GENERAL, 'បន្ទប់ 001'),
    ('8A', 'ថ្នាក់ទី ៨A', 8, Classroom.Track.GENERAL, 'បន្ទប់ 002'),
    ('9A', 'ថ្នាក់ទី ៩A', 9, Classroom.Track.GENERAL, 'បន្ទប់ 003'),
    ('10A', 'ថ្នាក់ទី ១០A', 10, Classroom.Track.GENERAL, 'បន្ទប់ 101'),
    ('11-SOC', 'ថ្នាក់ទី ១១ វិទ្យាសាស្ត្រសង្គម', 11, Classroom.Track.SOCIAL, 'បន្ទប់ 201'),
    ('11-SCI', 'ថ្នាក់ទី ១១ វិទ្យាសាស្ត្រ', 11, Classroom.Track.SCIENCE, 'បន្ទប់ 202'),
    ('12-SOC', 'ថ្នាក់ទី ១២ វិទ្យាសាស្ត្រសង្គម', 12, Classroom.Track.SOCIAL, 'បន្ទប់ 301'),
    ('12-SCI', 'ថ្នាក់ទី ១២ វិទ្យាសាស្ត្រ', 12, Classroom.Track.SCIENCE, 'បន្ទប់ 302'),
]

# ----------------- GRADE LEVELS CRUD (កម្រិតថ្នាក់) -----------------

@login_required
@role_required(['ADMIN'])
def grade_level_list(request):
    """Lists all configurable Grade Levels / Streams"""
    grade_levels = GradeLevel.objects.all().order_by('order', 'grade_number', 'track')
    form = GradeLevelForm()
    return render(request, 'academics/grade_level_list.html', {
        'grade_levels': grade_levels,
        'form': form,
    })


@login_required
@role_required(['ADMIN'])
def grade_level_create(request):
    """Create a new Grade Level (e.g. ថ្នាក់ទី ១០ វិទ្យាសាស្ត្រ, ថ្នាក់ទី ១០ វិទ្យាសាស្ត្រសង្គម)"""
    if request.method == 'POST':
        form = GradeLevelForm(request.POST)
        if form.is_valid():
            gl = form.save()
            # Initialize default rules for all subjects if none exist
            subjects = Subject.objects.all()
            for s in subjects:
                GradeLevelRule.objects.get_or_create(
                    grade_level=gl.grade_number,
                    track=gl.track,
                    subject=s,
                    defaults={'max_score': Decimal('50.00'), 'order': s.order}
                )
            messages.success(request, f"🎉 បានបង្កើតកម្រិតថ្នាក់ថ្មី '{gl.name}' ជោគជ័យ! លោកអ្នកអាចកំណត់ពិន្ទុអតិបរមានៅលើតារាងច្បាប់ពិន្ទុ។")
            return redirect('grade_rules_manager')
        else:
            for field, errs in form.errors.items():
                for err in errs:
                    messages.error(request, f"⚠️ កំហុស [{field}]: {err}")
    return redirect('grade_rules_manager')


@login_required
@role_required(['ADMIN'])
def grade_level_edit(request, pk):
    """Edit Grade Level name or order"""
    gl = get_object_or_404(GradeLevel, pk=pk)
    if request.method == 'POST':
        form = GradeLevelForm(request.POST, instance=gl)
        if form.is_valid():
            form.save()
            messages.success(request, f"បានកែប្រែកម្រិតថ្នាក់ '{gl.name}' ជោគជ័យ!")
            return redirect('grade_rules_manager')
    else:
        form = GradeLevelForm(instance=gl)
    return render(request, 'academics/grade_level_form.html', {'form': form, 'grade_level': gl})


@login_required
@role_required(['ADMIN'])
def grade_level_delete(request, pk):
    """Delete a Grade Level and its scoring rules"""
    gl = get_object_or_404(GradeLevel, pk=pk)
    if request.method == 'POST':
        name = gl.name
        # Delete associated scoring rules
        GradeLevelRule.objects.filter(grade_level=gl.grade_number, track=gl.track).delete()
        gl.delete()
        messages.success(request, f"🗑️ បានលុបកម្រិតថ្នាក់ '{name}' និងច្បាប់ពិន្ទុពាក់ព័ន្ធជោគជ័យ!")
    return redirect('grade_rules_manager')


# ----------------- ACADEMIC TRACKS (PROGRAMS / STREAMS) CRUD -----------------

@login_required
@role_required(['ADMIN'])
def academic_track_list(request):
    """List & manage all academic tracks"""
    tracks = AcademicTrack.objects.all().order_by('order', 'id')
    form = AcademicTrackForm()
    return render(request, 'academics/track_list.html', {'tracks': tracks, 'form': form})


@login_required
@role_required(['ADMIN'])
def academic_track_create(request):
    """Create a new academic track (Supports AJAX or regular form)"""
    if request.method == 'POST':
        form = AcademicTrackForm(request.POST)
        if form.is_valid():
            track = form.save()
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == '1':
                return JsonResponse({
                    'success': True,
                    'id': track.id,
                    'code': track.code,
                    'name_kh': track.name_kh,
                    'name_en': track.name_en or '',
                    'message': f"បានបង្កើតជំនាញ '{track.name_kh}' ជោគជ័យ!"
                })
            messages.success(request, f"🎉 បានបង្កើតជំនាញសិក្សាថ្មី '{track.name_kh}' ជោគជ័យ!")
        else:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == '1':
                return JsonResponse({'success': False, 'errors': form.errors}, status=400)
            for field, errs in form.errors.items():
                for err in errs:
                    messages.error(request, f"⚠️ [{field}]: {err}")
    return redirect('grade_rules_manager')


@login_required
@role_required(['ADMIN'])
def academic_track_edit(request, pk):
    """Edit an academic track"""
    track = get_object_or_404(AcademicTrack, pk=pk)
    if request.method == 'POST':
        form = AcademicTrackForm(request.POST, instance=track)
        if form.is_valid():
            form.save()
            messages.success(request, f"បានកែប្រែជំនាញសិក្សា '{track.name_kh}' ជោគជ័យ!")
            return redirect('grade_rules_manager')
    else:
        form = AcademicTrackForm(instance=track)
    return render(request, 'academics/track_form.html', {'form': form, 'track': track})


@login_required
@role_required(['ADMIN'])
def academic_track_delete(request, pk):
    """Delete an academic track"""
    track = get_object_or_404(AcademicTrack, pk=pk)
    if request.method == 'POST':
        name = track.name_kh
        code = track.code
        # Check if classrooms or grade levels are using this track
        cl_count = Classroom.objects.filter(track=code).count()
        gl_count = GradeLevel.objects.filter(track=code).count()
        if cl_count > 0 or gl_count > 0:
            messages.warning(request, f"⚠️ មិនអាចលុបជំនាញ '{name}' បានទេ ដោយសារមាន {gl_count} កម្រិតថ្នាក់ និង {cl_count} ថ្នាក់រៀនកំពុងប្រើប្រាស់!")
        else:
            track.delete()
            messages.success(request, f"🗑️ បានលុបជំនាញសិក្សា '{name}' ជោគជ័យ!")
    return redirect('grade_rules_manager')


@login_required
def api_academic_tracks(request):
    """API endpoint returning list of active tracks"""
    tracks = AcademicTrack.objects.all().order_by('order', 'id')
    data = [{'id': t.id, 'code': t.code, 'name_kh': t.name_kh, 'name_en': t.name_en or '', 'is_default': t.is_default} for t in tracks]
    return JsonResponse({'success': True, 'tracks': data})


# ----------------- GRADE ENROLLMENT OPTIONS (CUSTOM FIELDS) -----------------

@login_required
@role_required(['ADMIN'])
def grade_options_manager(request):
    """Admin Manager for Grade-Level Specific Enrollment Options"""
    grade_levels = GradeLevel.objects.prefetch_related('enrollment_options').all().order_by('order', 'grade_number', 'track')
    form = GradeEnrollmentOptionForm()
    
    selected_gl_id = request.GET.get('grade_level')
    selected_gl = None
    if selected_gl_id and str(selected_gl_id).isdigit():
        selected_gl = GradeLevel.objects.filter(id=int(selected_gl_id)).first()

    return render(request, 'academics/grade_options_manager.html', {
        'grade_levels': grade_levels,
        'selected_gl': selected_gl,
        'form': form,
    })


@login_required
@role_required(['ADMIN'])
def grade_option_save(request, pk=None):
    opt = get_object_or_404(GradeEnrollmentOption, pk=pk) if pk else None
    if request.method == 'POST':
        form = GradeEnrollmentOptionForm(request.POST, instance=opt)
        if form.is_valid():
            saved_opt = form.save()
            messages.success(request, f"🎉 បានរក្សាទុកជម្រើស '{saved_opt.label}' សម្រាប់ {saved_opt.grade_level.name} ជោគជ័យ!")
        else:
            for f, errs in form.errors.items():
                for e in errs:
                    messages.error(request, f"កំហុស [{f}]: {e}")
    return redirect('grade_options_manager')


@login_required
@role_required(['ADMIN'])
def grade_option_delete(request, pk):
    opt = get_object_or_404(GradeEnrollmentOption, pk=pk)
    if request.method == 'POST':
        label = opt.label
        gl_name = opt.grade_level.name
        opt.delete()
        messages.success(request, f"🗑️ បានលុបជម្រើស '{label}' ពី {gl_name} ជោគជ័យ!")
    return redirect('grade_options_manager')


@login_required
@role_required(['ADMIN'])
def grade_options_reorder(request):
    """AJAX POST to reorder options via drag and drop"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            ordered_ids = data.get('ordered_ids', [])
            for idx, opt_id in enumerate(ordered_ids, start=1):
                GradeEnrollmentOption.objects.filter(id=opt_id).update(order=idx)
            return JsonResponse({'status': 'success', 'message': 'បានតម្រៀបលំដាប់លំដោយជោគជ័យ!'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)


@login_required
@role_required(['ADMIN'])
def grade_option_update_width(request, pk):
    """AJAX POST to update column width (col-12, col-6, col-4, col-3)"""
    opt = get_object_or_404(GradeEnrollmentOption, pk=pk)
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            new_width = int(data.get('col_width', 6))
            if new_width in [12, 6, 4, 3]:
                opt.col_width = new_width
                opt.save(update_fields=['col_width'])
                return JsonResponse({'status': 'success', 'col_width': opt.col_width})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)



# ----------------- CLASSROOM CRUD & BULK ACTIONS -----------------

@login_required
def classroom_list(request):
    from .utils import get_active_academic_year
    active_year = get_active_academic_year(request)
    selected_year = request.GET.get('year') or request.GET.get('academic_year')
    if selected_year:
        if str(selected_year).isdigit():
            found_year = AcademicYear.objects.filter(id=int(selected_year)).first()
        else:
            found_year = AcademicYear.objects.filter(name=str(selected_year).strip()).first()
        if found_year:
            active_year = found_year
            try:
                request.session['active_academic_year_id'] = active_year.id
            except Exception:
                pass

    classrooms = Classroom.objects.select_related('academic_year', 'homeroom_teacher').prefetch_related('assigned_subjects__subject', 'students').all()
    academic_years = AcademicYear.objects.all().order_by('-start_date')
    all_subjects = Subject.objects.all().order_by('order', 'id')
    
    if active_year:
        classrooms = classrooms.filter(academic_year=active_year)

    # Build a lookup of all GradeLevelRule (grade_level, track, subject_id) -> max_score
    rules_dict = {}
    for r in GradeLevelRule.objects.all():
        rules_dict[(r.grade_level, r.track, r.subject_id)] = r.max_score

    classroom_items = []
    for c in classrooms:
        assigned_ids = set(c.assigned_subjects.values_list('subject_id', flat=True))
        
        # If none explicitly assigned yet, fallback to subjects in rules for this grade/track
        if not assigned_ids:
            assigned_ids = {sub.id for sub in all_subjects if (c.grade_level, c.track, sub.id) in rules_dict}

        subjects_with_meta = []
        tot_max = Decimal('0.00')
        active_cnt = 0
        for sub in all_subjects:
            is_active = sub.id in assigned_ids
            sc = rules_dict.get((c.grade_level, c.track, sub.id), Decimal('50.00'))
            if is_active:
                tot_max += sc
                active_cnt += 1
            subjects_with_meta.append({
                'subject': sub,
                'is_active': is_active,
                'max_score': sc,
            })

        classroom_items.append({
            'classroom': c,
            'assigned_ids': assigned_ids,
            'subjects_with_meta': subjects_with_meta,
            'active_subjects_count': active_cnt,
            'total_max_score': tot_max,
        })

    return render(request, 'academics/classroom_list.html', {
        'classroom_items': classroom_items,
        'all_subjects': all_subjects,
        'academic_years': academic_years,
        'selected_year': str(active_year.id) if active_year else '',
        'active_year': active_year,
    })


@login_required
@role_required(['ADMIN'])
def classroom_manage_subjects(request, pk):
    """Admin ticks/unticks subjects for a specific classroom"""
    classroom = get_object_or_404(Classroom, pk=pk)
    if request.method == 'POST':
        subject_ids = request.POST.getlist('subject_ids')
        if not subject_ids:
            messages.warning(request, f"⚠️ សូមជ្រើសរើសមុខវិជ្ជាយ៉ាងហោចណាស់មួយសម្រាប់ថ្នាក់ {classroom.name}!")
            return redirect('classroom_list')
        
        classroom.sync_assigned_subjects(subject_ids)
        count = len(subject_ids)
        tot_max = classroom.get_total_max_score()
        messages.success(request, f"🎉 បានកំណត់មុខវិជ្ជាសម្រាប់ថ្នាក់ '{classroom.name}' ចំនួន {count} មុខវិជ្ជា (ពិន្ទុសរុបពេញ៖ {tot_max:g} ពិន្ទុ) ដោយជោគជ័យ!")
    return redirect('classroom_list')


@login_required
@role_required(['ADMIN'])
def classroom_create(request):
    from .utils import get_active_academic_year
    active_year = get_active_academic_year(request)
    if request.method == 'POST':
        form = ClassroomForm(request.POST, academic_year=active_year)
        if form.is_valid():
            classroom = form.save()
            subject_ids = request.POST.getlist('subject_ids')
            if subject_ids:
                classroom.sync_assigned_subjects(subject_ids)
            else:
                # Default: assign standard subjects from GradeLevelRule for this grade/track
                default_sub_ids = list(GradeLevelRule.objects.filter(
                    grade_level=classroom.grade_level,
                    track=classroom.track
                ).values_list('subject_id', flat=True))
                if default_sub_ids:
                    classroom.sync_assigned_subjects(default_sub_ids)
            messages.success(request, f"បានបង្កើតថ្នាក់ {classroom.name} ជោគជ័យ!")
            return redirect('classroom_list')
    else:
        form = ClassroomForm(initial={'academic_year': active_year}, academic_year=active_year)
    
    all_subjects = Subject.objects.all().order_by('order', 'id')
    return render(request, 'academics/classroom_form.html', {
        'form': form,
        'all_subjects': all_subjects,
        'title': 'បង្កើតថ្នាក់រៀនថ្មី / Create Classroom'
    })


@login_required
@role_required(['ADMIN'])
def classroom_edit(request, pk):
    classroom = get_object_or_404(Classroom, pk=pk)
    if request.method == 'POST':
        form = ClassroomForm(request.POST, instance=classroom, academic_year=classroom.academic_year)
        if form.is_valid():
            form.save()
            subject_ids = request.POST.getlist('subject_ids')
            if subject_ids:
                classroom.sync_assigned_subjects(subject_ids)
            messages.success(request, f"បានកែប្រែថ្នាក់ {classroom.name} ជោគជ័យ!")
            return redirect('classroom_list')
    else:
        form = ClassroomForm(instance=classroom, academic_year=classroom.academic_year)
    
    all_subjects = Subject.objects.all().order_by('order', 'id')
    assigned_subject_ids = classroom.get_assigned_subject_ids()
    if not assigned_subject_ids:
        assigned_subject_ids = list(GradeLevelRule.objects.filter(
            grade_level=classroom.grade_level,
            track=classroom.track
        ).values_list('subject_id', flat=True))

    return render(request, 'academics/classroom_form.html', {
        'form': form,
        'classroom': classroom,
        'all_subjects': all_subjects,
        'assigned_subject_ids': assigned_subject_ids,
        'title': f'កែប្រែថ្នាក់ {classroom.name}'
    })


@login_required
@role_required(['ADMIN'])
def classroom_delete(request, pk):
    classroom = get_object_or_404(Classroom, pk=pk)
    if request.method == 'POST':
        name = classroom.name
        classroom.delete()
        messages.success(request, f"បានលុបថ្នាក់ {name} ដោយជោគជ័យ!")
    return redirect('classroom_list')


@login_required
@role_required(['ADMIN'])
def classroom_bulk_delete(request):
    """Bulk delete selected classrooms"""
    if request.method == 'POST':
        classroom_ids = request.POST.getlist('classroom_ids')
        if classroom_ids:
            deleted_count, _ = Classroom.objects.filter(id__in=classroom_ids).delete()
            messages.success(request, f"🗑️ បានលុបថ្នាក់រៀនដែលបានជ្រើសរើសចំនួន {deleted_count} ថ្នាក់ជោគជ័យ!")
        else:
            messages.warning(request, "សូមជ្រើសរើសថ្នាក់រៀនយ៉ាងតិចមួយដើម្បីលុប!")
    return redirect('classroom_list')


@login_required
@role_required(['ADMIN'])
def classroom_delete_all(request):
    """Delete all classrooms in the active academic year"""
    from .utils import get_active_academic_year
    active_year = get_active_academic_year(request)
    if request.method == 'POST':
        if active_year:
            count = Classroom.objects.filter(academic_year=active_year).count()
            Classroom.objects.filter(academic_year=active_year).delete()
            messages.success(request, f"⚠️ បានលុបថ្នាក់រៀនទាំងអស់ ({count} ថ្នាក់) ក្នុងឆ្នាំសិក្សា {active_year.name} ជោគជ័យ!")
        else:
            count = Classroom.objects.count()
            Classroom.objects.all().delete()
            messages.success(request, f"⚠️ បានលុបថ្នាក់រៀនទាំងអស់ ({count} ថ្នាក់) ចេញពីប្រព័ន្ធជោគជ័យ!")
    return redirect('classroom_list')


@login_required
@role_required(['ADMIN'])
def classroom_restore_default(request):
    """Restore default 8 MoEYS classrooms (Grade 7 to 12) for active academic year"""
    from .utils import get_active_academic_year
    active_year = get_active_academic_year(request)
    if not active_year:
        active_year, _ = AcademicYear.objects.get_or_create(
            name='2025-2026',
            defaults={'start_date': '2025-09-01', 'end_date': '2026-07-15', 'is_current': True}
        )

    teachers = list(Teacher.objects.filter(status='ACTIVE'))
    restored_cnt = 0

    with transaction.atomic():
        for idx, (code, name, grade, track, room) in enumerate(DEFAULT_MOEYS_CLASSROOMS):
            homeroom = teachers[idx % len(teachers)] if teachers else None
            cls_obj, _ = Classroom.objects.update_or_create(
                code=code,
                academic_year=active_year,
                defaults={
                    'name': name,
                    'grade_level': grade,
                    'track': track,
                    'room_number': room,
                    'capacity': 40,
                    'homeroom_teacher': homeroom
                }
            )
            # Assign standard subjects from rules
            sub_ids = list(GradeLevelRule.objects.filter(
                grade_level=cls_obj.grade_level,
                track=cls_obj.track
            ).values_list('subject_id', flat=True))
            if sub_ids:
                cls_obj.sync_assigned_subjects(sub_ids)
            restored_cnt += 1

    messages.success(request, f"🎉 បានស្តារឡើងវិញនូវថ្នាក់រៀនលំនាំដើម MoEYS ទាំង {restored_cnt} ថ្នាក់ (ថ្នាក់ទី៧ ដល់ទី១២) សម្រាប់ឆ្នាំសិក្សា {active_year.name} ដោយជោគជ័យ!")
    return redirect('classroom_list')



# ----------------- SUBJECTS MANAGEMENT & RESTORE -----------------

@login_required
def subject_list(request):
    subjects = Subject.objects.all().order_by('order', 'id')
    return render(request, 'academics/subject_list.html', {'subjects': subjects})


@login_required
@role_required(['ADMIN'])
def subject_create(request):
    if request.method == 'POST':
        form = SubjectForm(request.POST)
        if form.is_valid():
            subject = form.save()
            
            # Automatically initialize GradeLevelRule for the new subject across all existing GradeLevels
            for gl in GradeLevel.objects.all():
                GradeLevelRule.objects.get_or_create(
                    grade_level=gl.grade_number,
                    track=gl.track,
                    subject=subject,
                    defaults={'max_score': Decimal('50.00'), 'order': subject.order}
                )

            messages.success(request, f"🎉 បានបង្កើតមុខវិជ្ជាថ្មី '{subject.name_kh}' ({subject.code}) ជោគជ័យ! និងបានបន្ថែមទៅក្នុងតារាងច្បាប់ពិន្ទុ (Scoring Matrix) គ្រប់កម្រិតថ្នាក់រួចរាល់។")
            return redirect('subject_list')
        else:
            for field, errs in form.errors.items():
                for err in errs:
                    messages.error(request, f"⚠️ កំហុស [{field}]: {err}")
    else:
        form = SubjectForm()
    return render(request, 'academics/subject_form.html', {'form': form, 'title': 'បង្កើតមុខវិជ្ជាថ្មី / Create Subject'})


@login_required
@role_required(['ADMIN'])
def subject_edit(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    if request.method == 'POST':
        form = SubjectForm(request.POST, instance=subject)
        if form.is_valid():
            form.save()
            messages.success(request, f"បានកែប្រែមុខវិជ្ជា {subject.name_kh} ជោគជ័យ!")
            return redirect('subject_list')
        else:
            for field, errs in form.errors.items():
                for err in errs:
                    messages.error(request, f"⚠️ កំហុស [{field}]: {err}")
    else:
        form = SubjectForm(instance=subject)
    return render(request, 'academics/subject_form.html', {'form': form, 'title': f'កែប្រែមុខវិជ្ជា {subject.name_kh}', 'subject': subject})


@login_required
@role_required(['ADMIN'])
def subject_delete(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    if request.method == 'POST':
        name = subject.name_kh
        subject.delete()
        messages.success(request, f"បានលុបមុខវិជ្ជា {name} ដោយជោគជ័យ!")
    return redirect('subject_list')


@login_required
@role_required(['ADMIN'])
def subject_restore_default(request):
    """Restore/Upsert the official 14 MoEYS subjects with exact short codes."""
    with transaction.atomic():
        restored_cnt = 0
        for name_kh, name_en, short_code, credit, color, sort_order in DEFAULT_MOEYS_SUBJECTS:
            sub = Subject.objects.filter(code=short_code).first() or Subject.objects.filter(name_kh=name_kh).first()
            if sub:
                sub.name_kh = name_kh
                sub.name_en = name_en
                sub.code = short_code
                sub.credit = credit
                sub.color_code = color
                sub.order = sort_order
                sub.save()
            else:
                Subject.objects.create(
                    name_kh=name_kh,
                    name_en=name_en,
                    code=short_code,
                    credit=credit,
                    color_code=color,
                    order=sort_order
                )
            restored_cnt += 1

    messages.success(request, f"🎉 បានស្តារឡើងវិញនូវមុខវិជ្ជា និងអក្សរកាត់លំនាំដើម MoEYS ទាំង {restored_cnt} មុខវិជ្ជា ដោយជោគជ័យ!")
    return redirect('subject_list')


# ----------------- SCORING RULES MANAGER & RESTORE -----------------

@login_required
@role_required(['ADMIN'])
def grade_rules_manager(request):
    """
    Admin Scoring Rules Matrix View
    Displays all dynamic Grade Levels across ALL subjects in exact order.
    """
    # Load all subjects in exact ordered sequence
    subjects = Subject.objects.all().order_by('order', 'id')
    if not subjects.exists():
        subject_restore_default(request)
        subjects = Subject.objects.all().order_by('order', 'id')

    # Ensure default streams exist in GradeLevel model if empty
    if not GradeLevel.objects.exists():
        for name, g_num, trk, ord_idx in DEFAULT_MOEYS_STREAMS:
            GradeLevel.objects.create(
                name=name,
                grade_number=g_num,
                track=trk,
                order=ord_idx
            )

    grade_levels = GradeLevel.objects.all().order_by('order', 'grade_number', 'track', 'id')

    if request.method == 'POST' and 'update_rules' in request.POST:
        updated_cnt = 0
        for gl in grade_levels:
            g = gl.grade_number
            t = gl.track
            for sub in subjects:
                input_key = f"score_{g}_{t}_{sub.id}"
                if input_key in request.POST:
                    val_str = request.POST.get(input_key, '').strip()
                    if val_str:
                        try:
                            score_val = Decimal(val_str)
                            if score_val > 0:
                                GradeLevelRule.objects.update_or_create(
                                    grade_level=g,
                                    track=t,
                                    subject=sub,
                                    defaults={'max_score': score_val, 'order': sub.order}
                                )
                                updated_cnt += 1
                            else:
                                GradeLevelRule.objects.filter(grade_level=g, track=t, subject=sub).delete()
                        except Exception:
                            pass
                    else:
                        GradeLevelRule.objects.filter(grade_level=g, track=t, subject=sub).delete()

        messages.success(request, f"✅ បានធ្វើបច្ចុប្បន្នភាពច្បាប់ពិន្ទុអតិបរមា {updated_cnt} មុខវិជ្ជាជោគជ័យ!")
        return redirect('grade_rules_manager')

    # Load matrix data
    rules_dict = {}
    for r in GradeLevelRule.objects.select_related('subject').all():
        rules_dict[(r.grade_level, r.track, r.subject_id)] = r.max_score

    streams_data = []
    for gl in grade_levels:
        g = gl.grade_number
        t = gl.track
        sub_scores = []
        total_max = Decimal('0.00')
        for sub in subjects:
            sc = rules_dict.get((g, t, sub.id))
            if sc:
                total_max += sc
            sub_scores.append({
                'subject': sub,
                'max_score': sc,
            })
        streams_data.append({
            'id': gl.id,
            'grade': g,
            'track': t,
            'name': gl.name,
            'total_max': total_max,
            'sub_scores': sub_scores,
        })

    has_saved_custom = SavedDefaultConfig.objects.filter(key='custom_scoring_rules').exists()
    gl_form = GradeLevelForm()
    all_tracks = AcademicTrack.objects.all().order_by('order', 'id')
    track_form = AcademicTrackForm()

    return render(request, 'academics/grade_rules_manager.html', {
        'subjects': subjects,
        'streams_data': streams_data,
        'has_saved_custom': has_saved_custom,
        'gl_form': gl_form,
        'all_tracks': all_tracks,
        'track_form': track_form,
    })


@login_required
@role_required(['ADMIN'])
def save_current_as_default(request):
    """
    Saves the current scoring rules configuration as the new custom default preset.
    """
    if request.method == 'POST':
        rules_data = []
        for r in GradeLevelRule.objects.select_related('subject').all():
            rules_data.append({
                'grade_level': r.grade_level,
                'track': r.track,
                'subject_code': r.subject.code,
                'subject_name_kh': r.subject.name_kh,
                'max_score': str(r.max_score),
                'order': r.order,
            })
        
        streams_data = []
        for gl in GradeLevel.objects.all():
            streams_data.append({
                'name': gl.name,
                'grade_number': gl.grade_number,
                'track': gl.track,
                'order': gl.order
            })

        SavedDefaultConfig.objects.update_or_create(
            key='custom_scoring_rules',
            defaults={'data': {'rules': rules_data, 'streams': streams_data}}
        )
        messages.success(request, "💾 ជោគជ័យ! បានរក្សាទុកការកំណត់ច្បាប់ពិន្ទុបច្ចុប្បន្នជា Default សម្រាប់ប្រើប្រាស់ឡើងវិញគ្រប់ពេល។")
    return redirect('grade_rules_manager')


@login_required
@role_required(['ADMIN'])
def restore_saved_custom_default(request):
    """
    Restores the custom default preset saved earlier by the Admin.
    """
    cfg = SavedDefaultConfig.objects.filter(key='custom_scoring_rules').first()
    if not cfg or not cfg.data or 'rules' not in cfg.data:
        messages.warning(request, "មិនទាន់មានទិន្នន័យ Custom Default ត្រូវបានរក្សាទុកនៅឡើយទេ។ ប្រព័ន្ធនឹងស្តារតាម MoEYS Default!")
        return redirect('reset_grade_rules_to_moeys')

    with transaction.atomic():
        # Restore custom streams if present
        if 'streams' in cfg.data:
            GradeLevel.objects.all().delete()
            for s in cfg.data['streams']:
                GradeLevel.objects.create(
                    name=s['name'],
                    grade_number=s['grade_number'],
                    track=s['track'],
                    order=s['order']
                )

        GradeLevelRule.objects.all().delete()
        count = 0
        for item in cfg.data['rules']:
            sub = Subject.objects.filter(code=item['subject_code']).first() or Subject.objects.filter(name_kh=item['subject_name_kh']).first()
            if sub:
                GradeLevelRule.objects.create(
                    grade_level=item['grade_level'],
                    track=item['track'],
                    subject=sub,
                    max_score=Decimal(item['max_score']),
                    order=item.get('order', sub.order)
                )
                count += 1

    messages.success(request, f"🎉 បានស្តារឡើងវិញនូវច្បាប់ពិន្ទុលំនាំដើមដែលលោកអ្នកបាន Save ទុក ({count} មុខវិជ្ជា) ដោយជោគជ័យ!")
    return redirect('grade_rules_manager')


@login_required
@role_required(['ADMIN'])
def grade_rules_delete_all(request):
    """Delete all grade scoring rules"""
    if request.method == 'POST':
        count = GradeLevelRule.objects.count()
        GradeLevelRule.objects.all().delete()
        messages.success(request, f"⚠️ បានលុបច្បាប់ពិន្ទុទាំងអស់ ({count} ច្បាប់) ចេញពីប្រព័ន្ធជោគជ័យ!")
    return redirect('grade_rules_manager')


@login_required
@role_required(['ADMIN'])
def reset_grade_rules_to_moeys(request):
    """Resets all GradeLevel and GradeLevelRule records to the standard MoEYS matrix."""
    with transaction.atomic():
        # 1. First ensure only the clean 14 subjects exist
        Subject.objects.exclude(code__in=OFFICIAL_CODES).delete()
        for name_kh, name_en, short_code, credit, color, sort_order in DEFAULT_MOEYS_SUBJECTS:
            sub = Subject.objects.filter(code=short_code).first() or Subject.objects.filter(name_kh=name_kh).first()
            if sub:
                sub.name_kh = name_kh
                sub.name_en = name_en
                sub.code = short_code
                sub.credit = credit
                sub.color_code = color
                sub.order = sort_order
                sub.save()
            else:
                Subject.objects.create(
                    name_kh=name_kh,
                    name_en=name_en,
                    code=short_code,
                    credit=credit,
                    color_code=color,
                    order=sort_order
                )

        # 3. Reset Scoring Rules
        GradeLevelRule.objects.all().delete()
        created_count = 0
        for (g, track), sub_map in MOEYS_SCORING_RULES.items():
            for sub_name, max_sc in sub_map.items():
                sub = Subject.objects.filter(name_kh=sub_name).first()
                if sub:
                    GradeLevelRule.objects.create(
                        grade_level=g,
                        track=track,
                        subject=sub,
                        max_score=Decimal(str(max_sc)),
                        order=sub.order
                    )
                    created_count += 1

    messages.success(request, f"🎉 បានកំណត់ឡើងវិញនូវច្បាប់ពិន្ទុស្តង់ដារ MoEYS ទាំង ៨ កម្រិតថ្នាក់ ({created_count} មុខវិជ្ជា) ដោយជោគជ័យ!")
    return redirect('grade_rules_manager')


@login_required
@role_required(['ADMIN'])
def master_restore_defaults(request):
    """
    Master 1-Click Restore:
    1. Purges obsolete subjects, keeps exactly 14 official subjects (R, D, K, I, G, H, M, Es, P, C, B, He, Ec, E)
    2. Restores standard 8 GradeLevel records & scoring rules matrix
    3. Restores 8 default classrooms for active academic year
    """
    from .utils import get_active_academic_year
    active_year = get_active_academic_year(request)
    if not active_year:
        active_year, _ = AcademicYear.objects.get_or_create(
            name='2025-2026',
            defaults={'start_date': '2025-09-01', 'end_date': '2026-07-15', 'is_current': True}
        )

    with transaction.atomic():
        # 1. Clean Subjects
        Subject.objects.exclude(code__in=OFFICIAL_CODES).delete()
        for name_kh, name_en, short_code, credit, color, sort_order in DEFAULT_MOEYS_SUBJECTS:
            sub = Subject.objects.filter(code=short_code).first() or Subject.objects.filter(name_kh=name_kh).first()
            if sub:
                sub.name_kh = name_kh
                sub.name_en = name_en
                sub.code = short_code
                sub.credit = credit
                sub.color_code = color
                sub.order = sort_order
                sub.save()
            else:
                Subject.objects.create(
                    name_kh=name_kh,
                    name_en=name_en,
                    code=short_code,
                    credit=credit,
                    color_code=color,
                    order=sort_order
                )

        # 2. Grade Levels
        GradeLevel.objects.all().delete()
        for name, g_num, trk, ord_idx in DEFAULT_MOEYS_STREAMS:
            GradeLevel.objects.create(
                name=name,
                grade_number=g_num,
                track=trk,
                order=ord_idx
            )

        # 3. Scoring Rules
        GradeLevelRule.objects.all().delete()
        for (g, track), sub_map in MOEYS_SCORING_RULES.items():
            for sub_name, max_sc in sub_map.items():
                sub = Subject.objects.filter(name_kh=sub_name).first()
                if sub:
                    GradeLevelRule.objects.create(
                        grade_level=g,
                        track=track,
                        subject=sub,
                        max_score=Decimal(str(max_sc)),
                        order=sub.order
                    )

        # 4. Classrooms
        teachers = list(Teacher.objects.filter(status='ACTIVE'))
        for idx, (code, name, grade, track, room) in enumerate(DEFAULT_MOEYS_CLASSROOMS):
            homeroom = teachers[idx % len(teachers)] if teachers else None
            cls_obj, _ = Classroom.objects.update_or_create(
                code=code,
                academic_year=active_year,
                defaults={
                    'name': name,
                    'grade_level': grade,
                    'track': track,
                    'room_number': room,
                    'capacity': 40,
                    'homeroom_teacher': homeroom
                }
            )
            # Assign standard subjects from rules
            sub_ids = list(GradeLevelRule.objects.filter(
                grade_level=cls_obj.grade_level,
                track=cls_obj.track
            ).values_list('subject_id', flat=True))
            if sub_ids:
                cls_obj.sync_assigned_subjects(sub_ids)

    messages.success(request, f"🎉 ជោគជ័យ! បានស្តារប្រព័ន្ធទាំងមូលឡើងវិញទៅតាមស្តង់ដារលំនាំដើម MoEYS សម្រាប់ឆ្នាំសិក្សា {active_year.name}!")
    return redirect('classroom_list')


# ----------------- MASTER TIMETABLE MATRIX & GENERATION -----------------

STANDARD_PERIOD_TIMES = {
    1: (datetime.time(7, 0), datetime.time(7, 50)),
    2: (datetime.time(7, 55), datetime.time(8, 45)),
    3: (datetime.time(9, 5), datetime.time(9, 55)),
    4: (datetime.time(10, 0), datetime.time(10, 50)),
    5: (datetime.time(13, 0), datetime.time(13, 50)),
    6: (datetime.time(13, 55), datetime.time(14, 45)),
    7: (datetime.time(15, 5), datetime.time(15, 55)),
    8: (datetime.time(16, 0), datetime.time(16, 50)),
}

DAYS_OF_WEEK = [
    {'num': 1, 'name_kh': 'ច័ន្ទ', 'name_en': 'Monday'},
    {'num': 2, 'name_kh': 'អង្គារ', 'name_en': 'Tuesday'},
    {'num': 3, 'name_kh': 'ពុធ', 'name_en': 'Wednesday'},
    {'num': 4, 'name_kh': 'ព្រហស្បតិ៍', 'name_en': 'Thursday'},
    {'num': 5, 'name_kh': 'សុក្រ', 'name_en': 'Friday'},
    {'num': 6, 'name_kh': 'សៅរ៍', 'name_en': 'Saturday'},
]

PERIODS_LIST = [1, 2, 3, 4, 5, 6, 7, 8]


@login_required
def timetable_view(request):

    """
    Master Timetable Matrix (កាលវិភាគរួម) View.
    Displays school-wide timetable matrix with rows as classrooms and columns as Day x Periods 1-8.
    Supports Undo/Redo, filtered teacher/subject assignment selection, real-time clash detection,
    and conditional formatting for required vs scheduled weekly hours.
    Strictly isolated per Academic Year!
    """
    from .utils import get_active_academic_year
    active_year = get_active_academic_year(request)
    selected_year = request.GET.get('year') or request.GET.get('academic_year')
    if selected_year:
        if str(selected_year).isdigit():
            found_year = AcademicYear.objects.filter(id=int(selected_year)).first()
        else:
            found_year = AcademicYear.objects.filter(name=str(selected_year).strip()).first()
        if found_year:
            active_year = found_year
            try:
                request.session['active_academic_year_id'] = active_year.id
            except Exception:
                pass

    academic_years = AcademicYear.objects.all().order_by('-start_date')
    classrooms = Classroom.objects.filter(academic_year=active_year).order_by('grade_level', 'code') if active_year else Classroom.objects.all().order_by('grade_level', 'code')
    teachers = Teacher.objects.filter(status='ACTIVE').order_by('khmer_name')
    subjects = Subject.objects.exclude(code__in=['R', 'D']).order_by('order', 'id')
    
    # Existing timetable entries for active academic year
    timetables = Timetable.objects.filter(classroom__academic_year=active_year).select_related('classroom', 'subject', 'teacher') if active_year else Timetable.objects.select_related('classroom', 'subject', 'teacher').all()
    
    # Pre-fetch ClassSubject assignments (Only teachers assigned to this class and subject in this academic year)
    class_subject_assignments = ClassSubject.objects.filter(
        classroom__academic_year=active_year,
        teacher__isnull=False
    ).exclude(
        subject__code__in=['R', 'D']
    ).select_related('classroom', 'subject', 'teacher') if active_year else ClassSubject.objects.filter(
        teacher__isnull=False
    ).exclude(
        subject__code__in=['R', 'D']
    ).select_related('classroom', 'subject', 'teacher')

    # Build unique sequential teacher-subject codes (e.g. K1, K2, M1, M2, P1, P2...)
    distinct_assignments = class_subject_assignments.values(
        'subject_id', 'teacher_id'
    ).distinct().order_by('subject_id', 'teacher_id')

    teacher_subject_code_map = {}
    subject_teacher_counters = {}

    for item in distinct_assignments:
        s_id = item['subject_id']
        t_id = item['teacher_id']
        sub = next((s for s in subjects if s.id == s_id), None)
        sub_code = sub.code if sub else 'S'
        
        if s_id not in subject_teacher_counters:
            subject_teacher_counters[s_id] = 1
        else:
            subject_teacher_counters[s_id] += 1
            
        code = f"{sub_code}{subject_teacher_counters[s_id]}"
        teacher_subject_code_map[(s_id, t_id)] = code

    # Fallback assignment for any active teachers/subjects
    for s in subjects:
        for t in teachers:
            if (s.id, t.id) not in teacher_subject_code_map:
                if s.id not in subject_teacher_counters:
                    subject_teacher_counters[s.id] = 1
                else:
                    subject_teacher_counters[s.id] += 1
                teacher_subject_code_map[(s.id, t.id)] = f"{s.code}{subject_teacher_counters[s.id]}"

    # Build options per classroom with slot_code (e.g. K1, M2...)
    class_options_map = {}
    for cs in class_subject_assignments:
        c_id = cs.classroom_id
        if c_id not in class_options_map:
            class_options_map[c_id] = []
        slot_code = teacher_subject_code_map.get((cs.subject_id, cs.teacher_id), f"{cs.subject.code}1")
        class_options_map[c_id].append({
            'subject_id': cs.subject.id,
            'subject_code': cs.subject.code,
            'slot_code': slot_code,
            'subject_name': cs.subject.name_kh,
            'subject_color': cs.subject.color_code,
            'category': cs.subject.category,
            'teacher_id': cs.teacher.id,
            'teacher_name': cs.teacher.khmer_name,
            'teacher_short': cs.teacher.khmer_name[:6],
        })

    # Pre-fetch required hours from GradeLevelRule
    grade_rules = GradeLevelRule.objects.filter(
        weekly_hours__gt=0
    ).exclude(
        subject__code__in=['R', 'D']
    ).select_related('subject')

    requirements_map = {}
    for r in grade_rules:
        k = (r.grade_level, r.track)
        if k not in requirements_map:
            requirements_map[k] = {}
        requirements_map[k][r.subject_id] = r.weekly_hours

    # Build master grid records for each classroom
    classrooms_data = []
    matrix_state = {}

    for cls in classrooms:
        cls_reqs = requirements_map.get((cls.grade_level, cls.track), {})
        if not cls_reqs:
            cls_reqs = requirements_map.get((cls.grade_level, 'GENERAL'), {})
        
        total_req_hours = sum(cls_reqs.values())
        
        # Classroom slot map: (day_of_week, period_number) -> slot info
        cls_slots = {}
        cls_entries = timetables.filter(classroom=cls)
        
        for entry in cls_entries:
            slot_code = teacher_subject_code_map.get(
                (entry.subject_id, entry.teacher_id), 
                entry.subject.code
            )
            cls_slots[(entry.day_of_week, entry.period_number)] = {
                'id': entry.id,
                'subject_id': entry.subject_id,
                'subject_name': entry.subject.name_kh,
                'subject_code': entry.subject.code,
                'slot_code': slot_code,
                'subject_color': entry.subject.color_code,
                'category': entry.subject.category,
                'teacher_id': entry.teacher_id,
                'teacher_name': entry.teacher.khmer_name,
                'teacher_short': entry.teacher.khmer_name[:6],
            }
            matrix_state[f"{cls.id}_{entry.day_of_week}_{entry.period_number}"] = {
                'subject_id': entry.subject_id,
                'teacher_id': entry.teacher_id,
                'slot_code': slot_code,
            }

        # Build grid cells per day and period
        days_grid = []
        for day in DAYS_OF_WEEK:
            day_periods = []
            for p in PERIODS_LIST:
                slot_info = cls_slots.get((day['num'], p))
                day_periods.append({
                    'period': p,
                    'slot': slot_info,
                    'cell_id': f"cell_{cls.id}_{day['num']}_{p}",
                })
            days_grid.append({
                'day': day,
                'periods': day_periods,
            })

        classrooms_data.append({
            'classroom': cls,
            'total_req_hours': total_req_hours,
            'scheduled_hours': cls_entries.count(),
            'days_grid': days_grid,
        })

    # Merge session-stored blocked slots for active academic year into matrix_state
    session_key = f"blocked_slots_{active_year.id if active_year else 'all'}"
    saved_blocked = request.session.get(session_key, [])
    for blk in saved_blocked:
        c_id = blk.get('classroom_id')
        d_num = blk.get('day_of_week')
        p_num = blk.get('period_number')
        if c_id and d_num and p_num:
            k = f"{c_id}_{d_num}_{p_num}"
            if k not in matrix_state:
                matrix_state[k] = {'is_blocked': True, 'is_locked': True}

    # Pre-calculate classroom requirements mapping for frontend validation

    class_requirements_map = {}
    for cls in classrooms:
        reqs = requirements_map.get((cls.grade_level, cls.track), {})
        if not reqs:
            reqs = requirements_map.get((cls.grade_level, 'GENERAL'), {})
        class_requirements_map[cls.id] = {str(k): v for k, v in reqs.items()}

    # Calculate teacher statistics (Weekly load vs Max hours) within active academic year
    teacher_hours_report = []
    teacher_assigned_hours_map = {}
    teacher_max_hours_map = {}

    for t in teachers:
        assigned_cs = class_subject_assignments.filter(teacher=t)
        total_assigned_h = 0
        for cs in assigned_cs:
            h = requirements_map.get((cs.classroom.grade_level, cs.classroom.track), {}).get(cs.subject_id)
            if h is None:
                h = requirements_map.get((cs.classroom.grade_level, 'GENERAL'), {}).get(cs.subject_id, 0)
            total_assigned_h += h

        scheduled_h = timetables.filter(teacher=t).count()
        t_max = t.max_weekly_hours or 18
        teacher_assigned_hours_map[t.id] = total_assigned_h
        teacher_max_hours_map[t.id] = t_max

        teacher_hours_report.append({
            'teacher': t,
            'assigned_hours': total_assigned_h,
            'scheduled_hours': scheduled_h,
            'max_hours': t_max,
            'diff': scheduled_h - total_assigned_h,
            'is_over': scheduled_h > t_max or (total_assigned_h > 0 and scheduled_h > total_assigned_h),
            'is_complete': scheduled_h == total_assigned_h and total_assigned_h > 0,
        })

    teacher_code_directory = []
    for (s_id, t_id), code in sorted(teacher_subject_code_map.items(), key=lambda x: x[1]):
        sub = next((s for s in subjects if s.id == s_id), None)
        tch = next((t for t in teachers if t.id == t_id), None)
        if sub and tch and class_subject_assignments.filter(subject_id=s_id, teacher_id=t_id).exists():
            teacher_code_directory.append({
                'code': code,
                'subject': sub,
                'teacher': tch,
            })

    subjects_list = [{'id': s.id, 'name_kh': s.name_kh, 'code': s.code, 'category': s.category} for s in subjects]
    classrooms_list = [{'id': c.id, 'name': c.name, 'grade_level': c.grade_level, 'track': c.track} for c in classrooms]

    context = {
        'active_year': active_year,
        'academic_years': academic_years,
        'selected_year': str(active_year.id) if active_year else '',
        'classrooms': classrooms,
        'teachers': teachers,
        'subjects': subjects,
        'days': DAYS_OF_WEEK,
        'periods': PERIODS_LIST,
        'classrooms_data': classrooms_data,
        'class_options_json': json.dumps(class_options_map),
        'matrix_state_json': json.dumps(matrix_state),
        'class_requirements_json': json.dumps(class_requirements_map),
        'teacher_requirements_json': json.dumps(teacher_assigned_hours_map),
        'teacher_max_hours_json': json.dumps(teacher_max_hours_map),
        'teacher_assigned_hours_json': json.dumps(teacher_assigned_hours_map),
        'subjects_json': json.dumps(subjects_list),
        'classrooms_json': json.dumps(classrooms_list),
        'teacher_hours_report': teacher_hours_report,
        'teacher_code_directory': teacher_code_directory,
    }
    return render(request, 'academics/timetable.html', context)


@login_required
@role_required(['ADMIN'])
def timetable_save_matrix(request):
    """
    Saves the entire Master Timetable Matrix via AJAX JSON payload in a single atomic transaction.
    Scoped strictly to the active academic year!
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid HTTP method'}, status=405)

    from .utils import get_active_academic_year
    active_year = get_active_academic_year(request)

    try:
        data = json.loads(request.body.decode('utf-8'))
        matrix_items = data.get('matrix', [])
        blocked_items = data.get('blocked_slots')
        
        session_key = f"blocked_slots_{active_year.id if active_year else 'all'}"
        if blocked_items is not None:
            request.session[session_key] = blocked_items
            request.session.modified = True
        
        with transaction.atomic():
            if active_year:
                Timetable.objects.filter(classroom__academic_year=active_year).delete()
            else:
                Timetable.objects.all().delete()
            
            created_entries = []
            for item in matrix_items:
                cls_id = item.get('classroom_id')
                day_num = int(item.get('day_of_week'))
                p_num = int(item.get('period_number'))
                sub_id = item.get('subject_id')
                tch_id = item.get('teacher_id')
                
                if cls_id and sub_id and tch_id:
                    st_time, et_time = STANDARD_PERIOD_TIMES.get(
                        p_num, 
                        (datetime.time(7, 0), datetime.time(7, 50))
                    )
                    created_entries.append(Timetable(
                        classroom_id=cls_id,
                        subject_id=sub_id,
                        teacher_id=tch_id,
                        day_of_week=day_num,
                        period_number=p_num,
                        start_time=st_time,
                        end_time=et_time,
                    ))
            
            if created_entries:
                Timetable.objects.bulk_create(created_entries)

        return JsonResponse({
            'status': 'success',
            'message': f'បានរក្សាទុកកាលវិភាគរួម ({len(created_entries)} ម៉ោង) សម្រាប់ឆ្នាំសិក្សា {active_year.name if active_year else ""} ដោយជោគជ័យ!',
            'count': len(created_entries),
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
@role_required(['ADMIN'])
def timetable_auto_generate(request):
    """
    Intelligent Timetable Auto-Generator (Constraint-Satisfaction Solver).
    Strict Priorities:
      1. Alternating Days (រំលង ១ ថ្ងៃ ទៅ ១ ថ្ងៃទៀត): Spaced on alternating days (Mon/Wed/Fri or Tue/Thu/Sat) in 2-hour consecutive blocks.
      2. Remainder Placement (បើសិននៅសល់ម៉ោង): Places remaining single hours or overflow into intermediate available days/periods.
      3. Science vs Social Science: Morning priority (Periods 1-4) for Science, balanced complementary placement for Social Science.
      4. Zero teacher conflict, preservation of locked & blocked slots, and exact requirement quota match.
      Scoped strictly to active academic year!
    """
    import random
    from collections import defaultdict
    from .utils import get_active_academic_year
    active_year = get_active_academic_year(request)

    # Parse potential locked / blocked slots from request
    locked_slots_input = []
    if request.body:
        try:
            req_data = json.loads(request.body.decode('utf-8'))
            locked_slots_input = req_data.get('locked_slots', [])
        except Exception:
            pass

    session_key = f"blocked_slots_{active_year.id if active_year else 'all'}"
    blocked_from_input = [ls for ls in locked_slots_input if ls.get('is_blocked')]
    if blocked_from_input:
        request.session[session_key] = blocked_from_input
        request.session.modified = True


    classrooms = list(Classroom.objects.filter(academic_year=active_year).order_by('grade_level', 'code') if active_year else Classroom.objects.all().order_by('grade_level', 'code'))
    subjects = list(Subject.objects.exclude(code__in=['R', 'D']))
    teachers = list(Teacher.objects.filter(status='ACTIVE'))
    teacher_dict = {t.id: t for t in teachers}
    subject_dict = {s.id: s for s in subjects}

    # Pre-fetch assignments for this academic year
    class_subject_assignments = ClassSubject.objects.filter(
        classroom__academic_year=active_year,
        teacher__isnull=False
    ).exclude(
        subject__code__in=['R', 'D']
    ).select_related('classroom', 'subject', 'teacher') if active_year else ClassSubject.objects.filter(
        teacher__isnull=False
    ).exclude(
        subject__code__in=['R', 'D']
    ).select_related('classroom', 'subject', 'teacher')

    class_teacher_map = {}
    for cs in class_subject_assignments:
        class_teacher_map[(cs.classroom_id, cs.subject_id)] = cs.teacher

    # Pre-fetch requirements
    grade_rules = GradeLevelRule.objects.filter(
        weekly_hours__gt=0
    ).exclude(
        subject__code__in=['R', 'D']
    ).select_related('subject')

    requirements_map = {}
    for r in grade_rules:
        k = (r.grade_level, r.track)
        if k not in requirements_map:
            requirements_map[k] = []
        requirements_map[k].append(r)

    # Map pre-locked and blocked slots per classroom: cls_id -> (d, p) -> slot_dict
    locked_by_class = defaultdict(dict)
    for ls in locked_slots_input:
        c_id = int(ls.get('classroom_id', 0))
        d_num = int(ls.get('day_of_week', 0))
        p_num = int(ls.get('period_number', 0))
        if c_id and d_num and p_num:
            locked_by_class[c_id][(d_num, p_num)] = ls

    DAYS = [1, 2, 3, 4, 5, 6]
    ALL_PERIODS = [1, 2, 3, 4, 5, 6, 7, 8]
    PERIOD_PAIRS_MORNING = [(1, 2), (3, 4)]
    PERIOD_PAIRS_AFTERNOON = [(5, 6), (7, 8)]
    SINGLE_PERIODS_MORNING = [1, 2, 3, 4]
    SINGLE_PERIODS_AFTERNOON = [5, 6, 7, 8]

    # Alternating day pairs & triplets (រំលង ១ ថ្ងៃ)
    ALT_DAY_PAIRS = [(1, 3), (2, 4), (3, 5), (4, 6), (1, 5), (2, 6), (1, 4), (3, 6)]
    ALT_DAY_TRIPLETS = [(1, 3, 5), (2, 4, 6), (1, 3, 6), (1, 4, 6), (2, 4, 5)]

    best_solution = None
    best_score = -999999

    # Run multi-pass optimization solver to find the optimal clash-free, alternating-spaced schedule
    for attempt in range(15):
        teacher_occupancy = set()
        class_slots = defaultdict(dict)
        day_sub_hours = defaultdict(lambda: defaultdict(int))
        total_placed = 0
        total_demanded = 0
        alternating_matches = 0

        # Step 0: Register all locked and blocked slots first across all classes
        for cls in classrooms:
            cls_locked_map = locked_by_class.get(cls.id, {})
            for (d, p), ls in cls_locked_map.items():
                is_blocked = ls.get('is_blocked', False)
                sub_id = ls.get('subject_id')
                tch_id = ls.get('teacher_id')

                if is_blocked or not sub_id:
                    class_slots[cls.id][(d, p)] = {'is_blocked': True}
                else:
                    sub = subject_dict.get(int(sub_id))
                    tch = teacher_dict.get(int(tch_id))
                    if sub and tch:
                        class_slots[cls.id][(d, p)] = {'subject': sub, 'teacher': tch, 'is_locked': True}
                        teacher_occupancy.add((tch.id, d, p))
                        day_sub_hours[(cls.id, d)][sub.id] += 1

        cls_list = list(classrooms)
        random.shuffle(cls_list)

        for cls in cls_list:
            rules = requirements_map.get((cls.grade_level, cls.track)) or requirements_map.get((cls.grade_level, 'GENERAL'), [])
            cls_locked_map = locked_by_class.get(cls.id, {})
            locked_sub_counts = defaultdict(int)
            for (d, p), ls in cls_locked_map.items():
                if not ls.get('is_blocked') and ls.get('subject_id'):
                    locked_sub_counts[int(ls.get('subject_id'))] += 1

            has_any_assignments = class_subject_assignments.exists()
            demands = []
            for r in rules:
                tch = class_teacher_map.get((cls.id, r.subject_id))
                if not tch:
                    if has_any_assignments:
                        # STRICT ISOLATION & ASSIGNMENT: If assignments exist for this year, only schedule assigned classes!
                        continue
                    else:
                        sub_teachers = [t for t in teachers if r.subject.name_kh in (t.specialization or '')]
                        tch = sub_teachers[0] if sub_teachers else (teachers[0] if teachers else None)
                
                if not tch:
                    continue
                needed_h = max(0, r.weekly_hours - locked_sub_counts[r.subject_id])
                if needed_h <= 0:
                    continue


                total_demanded += needed_h
                cat = r.subject.category
                # Priority: Science=1, Khmer=2, Social=3, Other=4
                if cat == Subject.SubjectCategory.SCIENCE:
                    prio = 1
                elif r.subject.code == 'K':
                    prio = 2
                elif cat == Subject.SubjectCategory.SOCIAL:
                    prio = 3
                else:
                    prio = 4

                demands.append({
                    'subject': r.subject,
                    'teacher': tch,
                    'hours': needed_h,
                    'priority': prio,
                })

            # Sort demands by priority then hours desc
            demands.sort(key=lambda x: (x['priority'], -x['hours']))

            for dem in demands:
                sub = dem['subject']
                tch = dem['teacher']
                rem_h = dem['hours']

                # Decompose into teaching units: e.g. 4 -> 2+2, 3 -> 2+1, 2 -> 2, 6 -> 2+2+2
                blocks = []
                while rem_h >= 2:
                    blocks.append(2)
                    rem_h -= 2
                if rem_h == 1:
                    blocks.append(1)

                # ==========================================
                # PRIORITY 1: Alternating Days (រំលង ១ ថ្ងៃ ទៅ ១ ថ្ងៃទៀត)
                # ==========================================
                if len(blocks) == 2 and blocks == [2, 2]:
                    pair_options = list(ALT_DAY_PAIRS)
                    random.shuffle(pair_options)
                    pair_placed = False

                    for d1, d2 in pair_options:
                        period_options = (PERIOD_PAIRS_MORNING + PERIOD_PAIRS_AFTERNOON) if dem['priority'] <= 2 else (PERIOD_PAIRS_MORNING + PERIOD_PAIRS_AFTERNOON)
                        
                        found_p1 = None
                        found_p2 = None

                        for p_a, p_b in period_options:
                            if (d1, p_a) not in class_slots[cls.id] and (d1, p_b) not in class_slots[cls.id]:
                                if (tch.id, d1, p_a) not in teacher_occupancy and (tch.id, d1, p_b) not in teacher_occupancy:
                                    if day_sub_hours[(cls.id, d1)][sub.id] + 2 <= 2:
                                        found_p1 = (p_a, p_b)
                                        break

                        if found_p1:
                            for p_a, p_b in period_options:
                                if (d2, p_a) not in class_slots[cls.id] and (d2, p_b) not in class_slots[cls.id]:
                                    if (tch.id, d2, p_a) not in teacher_occupancy and (tch.id, d2, p_b) not in teacher_occupancy:
                                        if day_sub_hours[(cls.id, d2)][sub.id] + 2 <= 2:
                                            found_p2 = (p_a, p_b)
                                            break

                        if found_p1 and found_p2:
                            for p in found_p1:
                                class_slots[cls.id][(d1, p)] = {'subject': sub, 'teacher': tch}
                                teacher_occupancy.add((tch.id, d1, p))
                            day_sub_hours[(cls.id, d1)][sub.id] += 2

                            for p in found_p2:
                                class_slots[cls.id][(d2, p)] = {'subject': sub, 'teacher': tch}
                                teacher_occupancy.add((tch.id, d2, p))
                            day_sub_hours[(cls.id, d2)][sub.id] += 2

                            total_placed += 4
                            alternating_matches += 1
                            pair_placed = True
                            blocks = [] # Successfully placed in alternating days
                            break

                elif len(blocks) == 3 and blocks == [2, 2, 2]:
                    triplet_options = list(ALT_DAY_TRIPLETS)
                    random.shuffle(triplet_options)
                    trip_placed = False

                    for d1, d2, d3 in triplet_options:
                        p_opts = PERIOD_PAIRS_MORNING + PERIOD_PAIRS_AFTERNOON
                        f_p1, f_p2, f_p3 = None, None, None
                        
                        for p_a, p_b in p_opts:
                            if (d1, p_a) not in class_slots[cls.id] and (d1, p_b) not in class_slots[cls.id] and (tch.id, d1, p_a) not in teacher_occupancy and (tch.id, d1, p_b) not in teacher_occupancy and day_sub_hours[(cls.id, d1)][sub.id] + 2 <= 2:
                                f_p1 = (p_a, p_b)
                                break
                        if f_p1:
                            for p_a, p_b in p_opts:
                                if (d2, p_a) not in class_slots[cls.id] and (d2, p_b) not in class_slots[cls.id] and (tch.id, d2, p_a) not in teacher_occupancy and (tch.id, d2, p_b) not in teacher_occupancy and day_sub_hours[(cls.id, d2)][sub.id] + 2 <= 2:
                                    f_p2 = (p_a, p_b)
                                    break
                        if f_p1 and f_p2:
                            for p_a, p_b in p_opts:
                                if (d3, p_a) not in class_slots[cls.id] and (d3, p_b) not in class_slots[cls.id] and (tch.id, d3, p_a) not in teacher_occupancy and (tch.id, d3, p_b) not in teacher_occupancy and day_sub_hours[(cls.id, d3)][sub.id] + 2 <= 2:
                                    f_p3 = (p_a, p_b)
                                    break

                        if f_p1 and f_p2 and f_p3:
                            for d_cur, f_p in [(d1, f_p1), (d2, f_p2), (d3, f_p3)]:
                                for p in f_p:
                                    class_slots[cls.id][(d_cur, p)] = {'subject': sub, 'teacher': tch}
                                    teacher_occupancy.add((tch.id, d_cur, p))
                                day_sub_hours[(cls.id, d_cur)][sub.id] += 2
                            total_placed += 6
                            alternating_matches += 2
                            trip_placed = True
                            blocks = []
                            break

                # ==========================================
                # PRIORITY 2: Remainder Placement (បើសិននៅសល់ម៉ោង គឺត្រូវបន្ថែមចន្លោះពេល ឬថ្ងៃណាមួយ)
                # ==========================================
                for blk in blocks:
                    placed = False
                    avail_days = list(DAYS)
                    # Sort days by least hours of this subject in that day, then least class total periods
                    avail_days.sort(key=lambda d: (
                        day_sub_hours[(cls.id, d)][sub.id],
                        len([p for p in ALL_PERIODS if (d, p) in class_slots[cls.id]])
                    ))

                    if blk == 2:
                        p_opts = PERIOD_PAIRS_MORNING + PERIOD_PAIRS_AFTERNOON
                        for d in avail_days:
                            if day_sub_hours[(cls.id, d)][sub.id] + 2 > 2:
                                continue
                            for p_a, p_b in p_opts:
                                if (d, p_a) not in class_slots[cls.id] and (d, p_b) not in class_slots[cls.id]:
                                    if (tch.id, d, p_a) not in teacher_occupancy and (tch.id, d, p_b) not in teacher_occupancy:
                                        class_slots[cls.id][(d, p_a)] = {'subject': sub, 'teacher': tch}
                                        class_slots[cls.id][(d, p_b)] = {'subject': sub, 'teacher': tch}
                                        teacher_occupancy.add((tch.id, d, p_a))
                                        teacher_occupancy.add((tch.id, d, p_b))
                                        day_sub_hours[(cls.id, d)][sub.id] += 2
                                        total_placed += 2
                                        placed = True
                                        break
                            if placed:
                                break

                    if not placed:
                        # 1h single block or fallback
                        needed_single = blk
                        for d in avail_days:
                            if needed_single == 0:
                                break
                            if day_sub_hours[(cls.id, d)][sub.id] >= 2:
                                continue
                            p_list = (SINGLE_PERIODS_MORNING + SINGLE_PERIODS_AFTERNOON) if dem['priority'] <= 2 else ALL_PERIODS
                            for p in p_list:
                                if (d, p) not in class_slots[cls.id] and (tch.id, d, p) not in teacher_occupancy:
                                    class_slots[cls.id][(d, p)] = {'subject': sub, 'teacher': tch}
                                    teacher_occupancy.add((tch.id, d, p))
                                    day_sub_hours[(cls.id, d)][sub.id] += 1
                                    total_placed += 1
                                    needed_single -= 1
                                    if needed_single == 0:
                                        placed = True
                                        break

        score = (total_placed * 100) + (alternating_matches * 20)
        if score > best_score:
            best_score = score
            best_solution = class_slots
            if total_placed == total_demanded:
                # 100% placed with maximum alternating efficiency!
                break

    # Persist the winning schedule to database
    generated_timetable_entries = []
    if best_solution:
        with transaction.atomic():
            Timetable.objects.all().delete()
            for cls in classrooms:
                cls_slots = best_solution.get(cls.id, {})
                for (d, p), item in cls_slots.items():
                    if item and not item.get('is_blocked') and item.get('subject') and item.get('teacher'):
                        st_time, et_time = STANDARD_PERIOD_TIMES.get(p, (datetime.time(7, 0), datetime.time(7, 50)))
                        generated_timetable_entries.append(Timetable(
                            classroom=cls,
                            subject=item['subject'],
                            teacher=item['teacher'],
                            day_of_week=d,
                            period_number=p,
                            start_time=st_time,
                            end_time=et_time,
                            room=cls.room_number or f"បន្ទប់ {cls.code}"
                        ))

            if generated_timetable_entries:
                Timetable.objects.bulk_create(generated_timetable_entries)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
        return JsonResponse({
            'status': 'success',
            'message': f'បានរៀបចំកាលវិភាគស្វ័យប្រវត្តិចំនួន {len(generated_timetable_entries)} ម៉ោងដោយជោគជ័យ (គោរពតាមគោលការណ៍រំលងថ្ងៃ រៀបចំម៉ោងនៅសល់ និងគ្មានការជាន់ម៉ោងគ្នា)!',
            'count': len(generated_timetable_entries),
        })
    messages.success(request, f"បានរៀបចំកាលវិភាគស្វ័យប្រវត្តិចំនួន {len(generated_timetable_entries)} ម៉ោងដោយជោគជ័យ!")
    return redirect('timetable_view')


@login_required
def student_teacher_timetable_view(request):
    """
    Individual & Batch Printable Timetable View for Students (Classrooms) and Teachers.
    Matches official Ministry of Education, Youth and Sport (MoEYS) timetable layout.
    Strictly isolated per Academic Year!
    """
    from .utils import get_active_academic_year
    active_year = get_active_academic_year(request)
    selected_year = request.GET.get('year') or request.GET.get('academic_year')
    if selected_year:
        if str(selected_year).isdigit():
            found_year = AcademicYear.objects.filter(id=int(selected_year)).first()
        else:
            found_year = AcademicYear.objects.filter(name=str(selected_year).strip()).first()
        if found_year:
            active_year = found_year

    academic_years = AcademicYear.objects.all().order_by('-start_date')
    classrooms = Classroom.objects.filter(academic_year=active_year).order_by('grade_level', 'code') if active_year else Classroom.objects.all().order_by('grade_level', 'code')
    teachers = Teacher.objects.filter(status='ACTIVE').order_by('khmer_name')
    timetables = Timetable.objects.filter(classroom__academic_year=active_year).select_related('classroom', 'subject', 'teacher') if active_year else Timetable.objects.select_related('classroom', 'subject', 'teacher').all()

    # Pre-fetch ClassSubject for teachers' subjects within active academic year
    class_subjects = ClassSubject.objects.filter(classroom__academic_year=active_year, teacher__isnull=False).select_related('subject', 'teacher', 'classroom') if active_year else ClassSubject.objects.filter(teacher__isnull=False).select_related('subject', 'teacher', 'classroom')
    teacher_subjects_map = {}
    for cs in class_subjects:
        t_id = cs.teacher_id
        if t_id not in teacher_subjects_map:
            teacher_subjects_map[t_id] = set()
        teacher_subjects_map[t_id].add(cs.subject.name_kh)

    # 1. Build Classroom Timetables Data
    classrooms_timetables = []
    for cls in classrooms:
        cls_entries = timetables.filter(classroom=cls)
        slots_map = {}
        for entry in cls_entries:
            t_name = entry.teacher.khmer_name if entry.teacher else ""
            t_gender = getattr(entry.teacher, 'gender', 'M') if entry.teacher else 'M'
            title = "អ្នកគ្រូ" if t_gender == 'F' else "លោកគ្រូ"
            if t_name.startswith('លោកគ្រូ') or t_name.startswith('អ្នកគ្រូ'):
                display_teacher = t_name
            else:
                display_teacher = f"{title} {t_name}" if t_name else ""

            slots_map[(entry.day_of_week, entry.period_number)] = {
                'subject_name': entry.subject.name_kh,
                'subject_code': entry.subject.code,
                'teacher_name': t_name,
                'teacher_title': title,
                'teacher_display': display_teacher,
                'teacher_gender': t_gender,
            }

        
        # Build 4 morning periods (1-4) and 4 afternoon periods (5-8)
        morning_rows = []
        for p in [1, 2, 3, 4]:
            p_slots = [slots_map.get((d['num'], p)) for d in DAYS_OF_WEEK]
            morning_rows.append({'period': p, 'slots': p_slots})

        afternoon_rows = []
        for p in [5, 6, 7, 8]:
            p_slots = [slots_map.get((d['num'], p)) for d in DAYS_OF_WEEK]
            afternoon_rows.append({'period': p, 'slots': p_slots})

        classrooms_timetables.append({
            'classroom': cls,
            'homeroom_teacher': cls.homeroom_teacher,
            'academic_year': cls.academic_year.name if cls.academic_year else (active_year.name if active_year else "២០២៥-២០២៦"),
            'morning_rows': morning_rows,
            'afternoon_rows': afternoon_rows,
            'total_hours': len(slots_map),
        })

    # 2. Build Teacher Timetables Data (Only slots taught in active academic year)
    teachers_timetables = []
    for tch in teachers:
        tch_entries = timetables.filter(teacher=tch)
        slots_map = {}
        for entry in tch_entries:
            slots_map[(entry.day_of_week, entry.period_number)] = {
                'subject_name': entry.subject.name_kh,
                'subject_code': entry.subject.code,
                'classroom_name': entry.classroom.name,
                'classroom_code': entry.classroom.code,
            }

        morning_rows = []
        for p in [1, 2, 3, 4]:
            p_slots = [slots_map.get((d['num'], p)) for d in DAYS_OF_WEEK]
            morning_rows.append({'period': p, 'slots': p_slots})

        afternoon_rows = []
        for p in [5, 6, 7, 8]:
            p_slots = [slots_map.get((d['num'], p)) for d in DAYS_OF_WEEK]
            afternoon_rows.append({'period': p, 'slots': p_slots})

        assigned_subs = sorted(list(teacher_subjects_map.get(tch.id, [])))
        subjects_display = ", ".join(assigned_subs) if assigned_subs else (tch.specialization or "-")
        title = "អ្នកគ្រូ" if tch.gender == 'F' else "លោកគ្រូ"

        teachers_timetables.append({
            'teacher': tch,
            'title': title,
            'subjects_display': subjects_display,
            'academic_year': active_year.name if active_year else "២០២៥-២០២៦",
            'morning_rows': morning_rows,
            'afternoon_rows': afternoon_rows,
            'total_hours': len(slots_map),
        })

    # Date formatting in Khmer
    now = datetime.datetime.now()
    khmer_digits = {'0': '០', '1': '១', '2': '២', '3': '៣', '4': '៤', '5': '៥', '6': '៦', '7': '៧', '8': '៨', '9': '៩'}
    def to_khmer_num(n):
        return ''.join(khmer_digits.get(c, c) for c in str(n))

    kh_months = ['', 'មករា', 'កុម្ភៈ', 'មីនា', 'មេសា', 'ឧសភា', 'មិថុនា', 'កក្កដា', 'សីហា', 'កញ្ញា', 'តុលា', 'វិច្ឆិកា', 'ធ្នូ']
    kh_days_name = ['ច័ន្ទ', 'អង្គារ', 'ពុធ', 'ព្រហស្បតិ៍', 'សុក្រ', 'សៅរ៍', 'អាទិត្យ']

    today_kh_day = to_khmer_num(now.day)
    today_kh_month = kh_months[now.month] if 1 <= now.month <= 12 else ''
    today_kh_year = to_khmer_num(now.year)
    today_kh_dow = kh_days_name[now.weekday()]

    context = {
        'classrooms': classrooms,
        'teachers': teachers,
        'classrooms_timetables': classrooms_timetables,
        'teachers_timetables': teachers_timetables,
        'academic_year': active_year,
        'academic_years': academic_years,
        'selected_year': str(active_year.id) if active_year else '',
        'today_kh_day': today_kh_day,
        'today_kh_month': today_kh_month,
        'today_kh_year': today_kh_year,
        'today_kh_dow': today_kh_dow,
        'days': DAYS_OF_WEEK,
    }
    return render(request, 'academics/student_teacher_timetable.html', context)


@login_required
def timetable_daily_reports_view(request):
    """
    Daily Duty Sign-In Sheets Generator & Related Timetable Reports.
    Matches MoEYS standard layout: No, Teacher ID, Name, Period 1-4 / 5-8, Sign In, Sign Out, Remarks.
    Strictly isolated per Academic Year!
    """
    from .utils import get_active_academic_year
    active_year = get_active_academic_year(request)
    selected_year = request.GET.get('year') or request.GET.get('academic_year')
    if selected_year:
        if str(selected_year).isdigit():
            found_year = AcademicYear.objects.filter(id=int(selected_year)).first()
        else:
            found_year = AcademicYear.objects.filter(name=str(selected_year).strip()).first()
        if found_year:
            active_year = found_year

    teachers = Teacher.objects.filter(status='ACTIVE').order_by('teacher_id', 'khmer_name')
    classrooms = Classroom.objects.filter(academic_year=active_year).order_by('grade_level', 'code') if active_year else Classroom.objects.all().order_by('grade_level', 'code')
    subjects = Subject.objects.exclude(code__in=['R', 'D']).order_by('order', 'id')
    timetables = Timetable.objects.filter(classroom__academic_year=active_year).select_related('classroom', 'subject', 'teacher') if active_year else Timetable.objects.select_related('classroom', 'subject', 'teacher').all()

    # Pre-fetch rules & assignments
    grade_rules = GradeLevelRule.objects.filter(weekly_hours__gt=0).exclude(subject__code__in=['R', 'D'])
    requirements_map = {}
    for r in grade_rules:
        k = (r.grade_level, r.track)
        if k not in requirements_map:
            requirements_map[k] = {}
        requirements_map[k][r.subject_id] = r.weekly_hours

    # Teacher subject code map
    distinct_assignments = ClassSubject.objects.filter(
        classroom__academic_year=active_year,
        teacher__isnull=False
    ).exclude(
        subject__code__in=['R', 'D']
    ).values('subject_id', 'teacher_id').distinct().order_by('subject_id', 'teacher_id') if active_year else ClassSubject.objects.filter(
        teacher__isnull=False
    ).exclude(
        subject__code__in=['R', 'D']
    ).values('subject_id', 'teacher_id').distinct().order_by('subject_id', 'teacher_id')

    teacher_subject_code_map = {}
    subject_teacher_counters = {}
    for item in distinct_assignments:
        s_id = item['subject_id']
        t_id = item['teacher_id']
        sub = next((s for s in subjects if s.id == s_id), None)
        sub_code = sub.code if sub else 'S'
        if s_id not in subject_teacher_counters:
            subject_teacher_counters[s_id] = 1
        else:
            subject_teacher_counters[s_id] += 1
        teacher_subject_code_map[(s_id, t_id)] = f"{sub_code}{subject_teacher_counters[s_id]}"

    # Selected filters from request
    selected_day = request.GET.get('day', 'all')
    selected_session = request.GET.get('session', 'all')
    selected_tab = request.GET.get('tab', 'duty_sheets')

    days_to_render = DAYS_OF_WEEK if selected_day == 'all' else [d for d in DAYS_OF_WEEK if str(d['num']) == str(selected_day)]

    # 1. Build Duty Sign-In Sheets
    duty_sheets = []
    for d in days_to_render:
        d_entries = timetables.filter(day_of_week=d['num'])
        day_teacher_slots = {}
        for entry in d_entries:
            if entry.teacher_id:
                if entry.teacher_id not in day_teacher_slots:
                    day_teacher_slots[entry.teacher_id] = {}
                p_num = entry.period_number or 1
                slot_code = teacher_subject_code_map.get((entry.subject_id, entry.teacher_id), entry.subject.code)
                cls_name = entry.classroom.code or entry.classroom.name
                day_teacher_slots[entry.teacher_id][p_num] = f"{cls_name}({slot_code})"

        # Morning session (Periods 1, 2, 3, 4)
        if selected_session in ['all', 'morning']:
            morning_rows = []
            no_idx = 1
            for tch in teachers:
                tch_slots = day_teacher_slots.get(tch.id, {})
                p1 = tch_slots.get(1, '-')
                p2 = tch_slots.get(2, '-')
                p3 = tch_slots.get(3, '-')
                p4 = tch_slots.get(4, '-')
                has_classes = any(p != '-' for p in [p1, p2, p3, p4])
                
                if has_classes:
                    gender_title = "អ្នកគ្រូ" if tch.gender == 'F' else "លោកគ្រូ"
                    morning_rows.append({
                        'no': no_idx,
                        'teacher_id': tch.teacher_id,
                        'teacher_name': f"{gender_title} {tch.khmer_name}",
                        'specialization': tch.specialization,
                        'p1': p1,
                        'p2': p2,
                        'p3': p3,
                        'p4': p4,
                    })
                    no_idx += 1

            duty_sheets.append({
                'day_num': d['num'],
                'day_name': d['name_kh'],
                'session': 'morning',
                'session_name': 'ពេលព្រឹក',
                'session_badge': 'ព្រឹក (ម៉ោង ១-៤)',
                'period_labels': ['ម៉ោងទី១', 'ម៉ោងទី២', 'ម៉ោងទី៣', 'ម៉ោងទី៤'],
                'rows': morning_rows,
                'total_teachers': len(morning_rows),
            })

        # Afternoon session (Periods 5, 6, 7, 8)
        if selected_session in ['all', 'afternoon']:
            afternoon_rows = []
            no_idx = 1
            for tch in teachers:
                tch_slots = day_teacher_slots.get(tch.id, {})
                p5 = tch_slots.get(5, '-')
                p6 = tch_slots.get(6, '-')
                p7 = tch_slots.get(7, '-')
                p8 = tch_slots.get(8, '-')
                has_classes = any(p != '-' for p in [p5, p6, p7, p8])
                
                if has_classes:
                    gender_title = "អ្នកគ្រូ" if tch.gender == 'F' else "លោកគ្រូ"
                    afternoon_rows.append({
                        'no': no_idx,
                        'teacher_id': tch.teacher_id,
                        'teacher_name': f"{gender_title} {tch.khmer_name}",
                        'specialization': tch.specialization,
                        'p1': p5,
                        'p2': p6,
                        'p3': p7,
                        'p4': p8,
                    })
                    no_idx += 1

            duty_sheets.append({
                'day_num': d['num'],
                'day_name': d['name_kh'],
                'session': 'afternoon',
                'session_name': 'ពេលរសៀល',
                'session_badge': 'រសៀល (ម៉ោង ៥-៨)',
                'period_labels': ['ម៉ោងទី៥', 'ម៉ោងទី៦', 'ម៉ោងទី៧', 'ម៉ោងទី៨'],
                'rows': afternoon_rows,
                'total_teachers': len(afternoon_rows),
            })

    # 2. Teacher Teaching Hours Load Report
    teacher_load_report = []
    for t in teachers:
        t_slots_count = timetables.filter(teacher=t).count()
        t_assigned_cs = ClassSubject.objects.filter(classroom__academic_year=active_year, teacher=t).select_related('classroom') if active_year else ClassSubject.objects.filter(teacher=t).select_related('classroom')
        t_assigned_sum = 0
        for cs in t_assigned_cs:
            cls = cs.classroom
            cls_reqs = requirements_map.get((cls.grade_level, cls.track), {})
            if not cls_reqs:
                cls_reqs = requirements_map.get((cls.grade_level, 'GENERAL'), {})
            t_assigned_sum += cls_reqs.get(cs.subject_id, 0)

        t_max = t.max_weekly_hours or 18
        t_codes = [
            code for (s_id, t_id), code in teacher_subject_code_map.items() 
            if t_id == t.id and ClassSubject.objects.filter(subject_id=s_id, teacher_id=t.id, classroom__academic_year=active_year).exists()
        ]

        if t_slots_count > t_assigned_sum and t_assigned_sum > 0:
            status_text = f"លើសម៉ោងចាត់តាំង ({t_slots_count - t_assigned_sum} ម៉ោង)"
            status_badge = "bg-warning text-dark border border-warning"
        elif t_slots_count > t_max:
            status_text = f"លើសម៉ោងកំណត់គោល ({t_slots_count - t_max} ម៉ោង)"
            status_badge = "bg-warning text-dark border border-warning"
        elif t_assigned_sum > t_max and t_slots_count == t_assigned_sum:
            status_text = "គ្រប់ម៉ោងចាត់តាំងបន្ថែម (Overload)"
            status_badge = "bg-purple-subtle text-purple border"
        elif t_slots_count == t_assigned_sum and t_assigned_sum > 0:
            status_text = "គ្រប់ម៉ោងតាមការកំណត់"
            status_badge = "bg-success text-white"
        elif t_slots_count < t_assigned_sum:
            status_text = f"ខ្វះ {t_assigned_sum - t_slots_count} ម៉ោង"
            status_badge = "bg-info text-dark"
        else:
            status_text = "មិនទាន់មានម៉ោង"
            status_badge = "bg-secondary text-white"

        teacher_load_report.append({
            'teacher': t,
            'codes': ", ".join(t_codes) or "-",
            'max_hours': t_max,
            'assigned_hours': t_assigned_sum,
            'scheduled_hours': t_slots_count,
            'diff': t_slots_count - t_assigned_sum,
            'status_text': status_text,
            'status_badge': status_badge,
        })

    # 3. Teacher Subject Code Directory
    teacher_code_directory = []
    for (s_id, t_id), code in sorted(teacher_subject_code_map.items(), key=lambda x: x[1]):
        sub = next((s for s in subjects if s.id == s_id), None)
        tch = next((t for t in teachers if t.id == t_id), None)
        if sub and tch and ClassSubject.objects.filter(subject_id=s_id, teacher_id=t_id, classroom__academic_year=active_year).exists():
            assigned_classes = Classroom.objects.filter(
                academic_year=active_year,
                assigned_subjects__subject_id=s_id,
                assigned_subjects__teacher_id=t_id
            ).distinct()
            cls_names = ", ".join(c.name for c in assigned_classes) or "-"
            teacher_code_directory.append({
                'code': code,
                'subject': sub,
                'teacher': tch,
                'classes': cls_names,
            })

    # 4. Classrooms Summary
    classrooms_summary = []
    for cls in classrooms:
        cls_reqs = requirements_map.get((cls.grade_level, cls.track), {})
        if not cls_reqs:
            cls_reqs = requirements_map.get((cls.grade_level, 'GENERAL'), {})
        req_total = sum(cls_reqs.values())
        sched_total = timetables.filter(classroom=cls).count()
        diff = sched_total - req_total
        classrooms_summary.append({
            'classroom': cls,
            'required_hours': req_total,
            'scheduled_hours': sched_total,
            'diff': diff,
            'status_class': 'success' if diff == 0 else ('warning text-dark' if diff > 0 else 'info text-dark'),
            'status_text': 'ពេញលេញ' if diff == 0 else (f'លើស {diff} ម៉ោង' if diff > 0 else f'ខ្វះ {-diff} ម៉ោង'),
        })

    # Date in Khmer
    now = datetime.datetime.now()
    khmer_digits = {'0': '០', '1': '១', '2': '២', '3': '៣', '4': '៤', '5': '៥', '6': '៦', '7': '៧', '8': '៨', '9': '៩'}
    def to_khmer_num(n):
        return ''.join(khmer_digits.get(c, c) for c in str(n))

    kh_months = ['', 'មករា', 'កុម្ភៈ', 'មីនា', 'មេសា', 'ឧសភា', 'មិថុនា', 'កក្កដា', 'សីហា', 'កញ្ញា', 'តុលា', 'វិច្ឆិកា', 'ធ្នូ']
    kh_days_name = ['ច័ន្ទ', 'អង្គារ', 'ពុធ', 'ព្រហស្បតិ៍', 'សុក្រ', 'សៅរ៍', 'អាទិត្យ']

    today_kh_day = to_khmer_num(now.day)
    today_kh_month = kh_months[now.month] if 1 <= now.month <= 12 else ''
    today_kh_year = to_khmer_num(now.year)
    today_kh_dow = kh_days_name[now.weekday()]

    context = {
        'days': DAYS_OF_WEEK,
        'selected_day': selected_day,
        'selected_session': selected_session,
        'selected_tab': selected_tab,
        'duty_sheets': duty_sheets,
        'teacher_load_report': teacher_load_report,
        'teacher_code_directory': teacher_code_directory,
        'classrooms_summary': classrooms_summary,
        'academic_year': active_year,
        'today_kh_day': today_kh_day,
        'today_kh_month': today_kh_month,
        'today_kh_year': today_kh_year,
        'today_kh_dow': today_kh_dow,
    }
    return render(request, 'academics/daily_reports.html', context)


@login_required
def timetable_daily_reports_export_excel(request):
    """
    Exports formatted Daily Duty Sign-In Sheets to Excel (.xlsx) using openpyxl.
    Strictly for the active academic year!
    """
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter
    from .utils import get_active_academic_year
    academic_year = get_active_academic_year(request)

    teachers = Teacher.objects.filter(status='ACTIVE').order_by('teacher_id', 'khmer_name')
    subjects = Subject.objects.exclude(code__in=['R', 'D']).order_by('order', 'id')
    timetables = Timetable.objects.filter(classroom__academic_year=academic_year).select_related('classroom', 'subject', 'teacher') if academic_year else Timetable.objects.select_related('classroom', 'subject', 'teacher').all()

    # Teacher subject code map
    distinct_assignments = ClassSubject.objects.filter(
        classroom__academic_year=academic_year,
        teacher__isnull=False
    ).exclude(
        subject__code__in=['R', 'D']
    ).values('subject_id', 'teacher_id').distinct().order_by('subject_id', 'teacher_id') if academic_year else ClassSubject.objects.filter(
        teacher__isnull=False
    ).exclude(
        subject__code__in=['R', 'D']
    ).values('subject_id', 'teacher_id').distinct().order_by('subject_id', 'teacher_id')

    teacher_subject_code_map = {}
    subject_teacher_counters = {}
    for item in distinct_assignments:
        s_id = item['subject_id']
        t_id = item['teacher_id']
        sub = next((s for s in subjects if s.id == s_id), None)
        sub_code = sub.code if sub else 'S'
        if s_id not in subject_teacher_counters:
            subject_teacher_counters[s_id] = 1
        else:
            subject_teacher_counters[s_id] += 1
        teacher_subject_code_map[(s_id, t_id)] = f"{sub_code}{subject_teacher_counters[s_id]}"

    selected_day = request.GET.get('day', 'all')
    selected_session = request.GET.get('session', 'all')

    days_to_render = DAYS_OF_WEEK if selected_day == 'all' else [d for d in DAYS_OF_WEEK if str(d['num']) == str(selected_day)]

    wb = openpyxl.Workbook()
    # Remove default sheet
    wb.remove(wb.active)

    thin_border = Border(
        left=Side(style='thin', color='A0AEC0'),
        right=Side(style='thin', color='A0AEC0'),
        top=Side(style='thin', color='A0AEC0'),
        bottom=Side(style='thin', color='A0AEC0')
    )

    header_fill = PatternFill(start_color='F1F5F9', end_color='F1F5F9', fill_type='solid')

    for d in days_to_render:
        d_entries = timetables.filter(day_of_week=d['num'])
        day_teacher_slots = {}
        for entry in d_entries:
            if entry.teacher_id:
                if entry.teacher_id not in day_teacher_slots:
                    day_teacher_slots[entry.teacher_id] = {}
                p_num = entry.period_number or 1
                slot_code = teacher_subject_code_map.get((entry.subject_id, entry.teacher_id), entry.subject.code)
                cls_name = entry.classroom.code or entry.classroom.name
                day_teacher_slots[entry.teacher_id][p_num] = f"{cls_name}({slot_code})"

        sessions = []
        if selected_session in ['all', 'morning']:
            sessions.append(('morning', 'ពេលព្រឹក', [1, 2, 3, 4], ['ម៉ោងទី១', 'ម៉ោងទី២', 'ម៉ោងទី៣', 'ម៉ោងទី៤']))
        if selected_session in ['all', 'afternoon']:
            sessions.append(('afternoon', 'ពេលរសៀល', [5, 6, 7, 8], ['ម៉ោងទី៥', 'ម៉ោងទី៦', 'ម៉ោងទី៧', 'ម៉ោងទី៨']))

        for sess_code, sess_name, p_nums, p_labels in sessions:
            sheet_title = f"{d['name_kh']}_{sess_name}"[:31]
            ws = wb.create_sheet(title=sheet_title)
            ws.views.sheetView[0].showGridLines = True

            # Title
            ws.merge_cells('A1:J1')
            ws['A1'] = "វិទ្យាល័យ ហ៊ុន សែន កំពង់កន្តែត"
            ws['A1'].font = Font(name='Khmer OS Muol Light', size=13, bold=True)
            ws['A1'].alignment = Alignment(horizontal='center', vertical='center')

            ws.merge_cells('A2:J2')
            ws['A2'] = f"បញ្ជីចុះហត្ថលេខាវត្តមានគ្រូបង្រៀនប្រចាំថ្ងៃ {sess_name} - ថ្ងៃ{d['name_kh']}"
            ws['A2'].font = Font(name='Khmer OS Muol Light', size=11, bold=True)
            ws['A2'].alignment = Alignment(horizontal='center', vertical='center')

            ws.merge_cells('A3:J3')
            ws['A3'] = f"ឆ្នាំសិក្សា៖ {academic_year.name if academic_year else '២០២៤-២០២៥'}"
            ws['A3'].font = Font(name='Khmer OS Siemreap', size=10, italic=True)
            ws['A3'].alignment = Alignment(horizontal='center', vertical='center')

            # Table Header Row
            headers = ['ល.រ', 'អត្តលេខ', 'ឈ្មោះគ្រូបង្រៀន'] + p_labels + ['ហត្ថលេខាចូល', 'ហត្ថលេខាចេញ', 'ផ្សេងៗ']
            ws.append([]) # Row 4 empty
            ws.append(headers) # Row 5

            for col_idx in range(1, len(headers) + 1):
                cell = ws.cell(row=5, column=col_idx)
                cell.font = Font(name='Khmer OS Siemreap', size=10, bold=True)
                cell.alignment = Alignment(horizontal='center', vertical='center')
                cell.fill = header_fill
                cell.border = thin_border

            # Data Rows
            current_row = 6
            no_idx = 1
            for tch in teachers:
                tch_slots = day_teacher_slots.get(tch.id, {})
                p_vals = [tch_slots.get(p, '-') for p in p_nums]
                if any(v != '-' for v in p_vals):
                    gender_title = "អ្នកគ្រូ" if tch.gender == 'F' else "លោកគ្រូ"
                    row_data = [no_idx, tch.teacher_id, f"{gender_title} {tch.khmer_name}"] + p_vals + ['', '', '']
                    ws.append(row_data)

                    for col_idx in range(1, len(headers) + 1):
                        cell = ws.cell(row=current_row, column=col_idx)
                        cell.font = Font(name='Khmer OS Siemreap', size=10)
                        cell.border = thin_border
                        if col_idx in [1, 2, 4, 5, 6, 7]:
                            cell.alignment = Alignment(horizontal='center', vertical='center')
                        else:
                            cell.alignment = Alignment(horizontal='left', vertical='center')

                    current_row += 1
                    no_idx += 1

            # Footer Signatures
            current_row += 2
            ws.cell(row=current_row, column=7, value="បានឃើញ និងឯកភាព").font = Font(name='Khmer OS Siemreap', size=10, bold=True)
            ws.cell(row=current_row + 1, column=7, value="នាយកសាលា").font = Font(name='Khmer OS Siemreap', size=10, bold=True)
            ws.cell(row=current_row, column=2, value="អ្នករៀបចំរបាយការណ៍").font = Font(name='Khmer OS Siemreap', size=10, bold=True)

            # Auto Column Widths
            col_widths = {1: 6, 2: 14, 3: 24, 4: 14, 5: 14, 6: 14, 7: 14, 8: 16, 9: 16, 10: 16}
            for col_idx, width in col_widths.items():
                col_letter = get_column_letter(col_idx)
                ws.column_dimensions[col_letter].width = width

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="teacher_daily_duty_sheets.xlsx"'
    wb.save(response)
    return response


@login_required
def timetable_export_excel(request):
    """
    Export Master Timetable Matrix to Excel-compatible CSV format with UTF-8 BOM for Khmer text.
    Strictly for the active academic year!
    """
    import csv
    from .utils import get_active_academic_year
    active_year = get_active_academic_year(request)

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="master_timetable.csv"'
    response.write('\ufeff') # UTF-8 BOM for Microsoft Excel Khmer font rendering

    writer = csv.writer(response)
    
    # Headers
    header_row_1 = ['ថ្នាក់រៀន']
    for d in DAYS_OF_WEEK:
        for p in PERIODS_LIST:
            header_row_1.append(f"{d['name_kh']} - ម៉ោង {p}")
    writer.writerow(header_row_1)

    classrooms = Classroom.objects.filter(academic_year=active_year).order_by('grade_level', 'code') if active_year else Classroom.objects.all().order_by('grade_level', 'code')
    timetables = Timetable.objects.filter(classroom__academic_year=active_year).select_related('classroom', 'subject', 'teacher') if active_year else Timetable.objects.select_related('classroom', 'subject', 'teacher').all()

    for cls in classrooms:
        row = [cls.name]
        cls_entries = {(e.day_of_week, e.period_number): e for e in timetables.filter(classroom=cls)}
        for d in DAYS_OF_WEEK:
            for p in PERIODS_LIST:
                entry = cls_entries.get((d['num'], p))
                if entry:
                    row.append(f"{entry.subject.name_kh} ({entry.teacher.khmer_name})")
                else:
                    row.append("")
        writer.writerow(row)

    return response


@login_required
@role_required(['ADMIN'])
def timetable_clear_all(request):
    """
    Clear all timetable entries for the active academic year.
    """
    from .utils import get_active_academic_year
    active_year = get_active_academic_year(request)
    if active_year:
        count = Timetable.objects.filter(classroom__academic_year=active_year).count()
        Timetable.objects.filter(classroom__academic_year=active_year).delete()
        msg = f"បានលុបទិន្នន័យកាលវិភាគទាំងអស់ ({count} ម៉ោង) នៃឆ្នាំសិក្សា {active_year.name} រួចរាល់!"
    else:
        count = Timetable.objects.count()
        Timetable.objects.all().delete()
        msg = f"បានលុបទិន្នន័យកាលវិភាគទាំងអស់ ({count} ម៉ោង) រួចរាល់!"

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success', 'message': msg})
    messages.success(request, msg)
    return redirect('timetable_view')


@login_required
@role_required(['ADMIN'])
def timetable_create(request):
    if request.method == 'POST':
        form = TimetableForm(request.POST)
        if form.is_valid():
            try:
                timetable = form.save()
                messages.success(request, f"បានបញ្ចូលកាលវិភាគ {timetable.subject.name_kh} ជោគជ័យ!")
                return redirect('timetable_view')
            except ValidationError as e:
                for field, errors in e.message_dict.items():
                    for err in errors:
                        messages.error(request, f"⚠️ បរាជ័យ: {err}")
        else:
            for field, errors in form.errors.items():
                for err in errors:
                    messages.error(request, f"⚠️ បញ្ហាទិន្នន័យ [{field}]: {err}")
    return redirect('timetable_view')


@login_required
@role_required(['ADMIN'])
def timetable_edit(request, pk):
    entry = get_object_or_404(Timetable, pk=pk)
    if request.method == 'POST':
        form = TimetableForm(request.POST, instance=entry)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, f"បានកែប្រែម៉ោងបង្រៀន {entry.subject.name_kh} ជោគជ័យ!")
                return redirect('timetable_view')
            except ValidationError as e:
                for field, errors in e.message_dict.items():
                    for err in errors:
                        messages.error(request, f"⚠️ បរាជ័យ: {err}")
        else:
            for field, errors in form.errors.items():
                for err in errors:
                    messages.error(request, f"⚠️ កំហុស [{field}]: {err}")
    return redirect('timetable_view')


@login_required
@role_required(['ADMIN'])
def timetable_delete(request, pk):
    entry = get_object_or_404(Timetable, pk=pk)
    entry.delete()
    messages.success(request, "បានលុបម៉ោងបង្រៀនចេញពីកាលវិភាគជោគជ័យ!")
    return redirect('timetable_view')


@login_required
@role_required(['ADMIN'])
def timetable_clear_class(request, class_id):
    cls = get_object_or_404(Classroom, pk=class_id)
    count = Timetable.objects.filter(classroom=cls).count()
    Timetable.objects.filter(classroom=cls).delete()
    messages.success(request, f"បានលុបកាលវិភាគទាំងអស់ ({count} ម៉ោង) របស់ថ្នាក់ {cls.name} រួចរាល់!")
    return redirect('timetable_view')



# ----------------- SUBJECT REQUIREMENTS MATRIX -----------------

@login_required
@role_required(['ADMIN'])
def subject_requirements_manager(request):
    """
    Manage Subjects & Weekly Hours Requirements (Matrix matching user's design)
    Columns: Code, Subject Name, 7, 8, 9, 10, 11SC, 11SS, 12SC, 12SS, Actions
    Excludes R (Essay) and D (Dictation) since Khmer language (K) covers all Khmer teaching hours.
    """
    subjects = Subject.objects.exclude(code__in=['R', 'D']).order_by('order', 'id')
    grade_levels = GradeLevel.objects.all().order_by('order', 'grade_number', 'track', 'id')
    
    if not grade_levels.exists():
        default_levels = [
            (7, 'GENERAL', 'ថ្នាក់ទី ៧', 1),
            (8, 'GENERAL', 'ថ្នាក់ទី ៨', 2),
            (9, 'GENERAL', 'ថ្នាក់ទី ៩', 3),
            (10, 'GENERAL', 'ថ្នាក់ទី ១០', 4),
            (11, 'SCIENCE', 'ថ្នាក់ទី ១១ វិទ្យាសាស្ត្រ', 5),
            (11, 'SOCIAL', 'ថ្នាក់ទី ១១ វិទ្យាសាស្ត្រសង្គម', 6),
            (12, 'SCIENCE', 'ថ្នាក់ទី ១២ វិទ្យាសាស្ត្រ', 7),
            (12, 'SOCIAL', 'ថ្នាក់ទី ១២ វិទ្យាសាស្ត្រសង្គម', 8),
        ]
        for g_num, trk, nm, ord_num in default_levels:
            GradeLevel.objects.get_or_create(grade_number=g_num, track=trk, defaults={'name': nm, 'order': ord_num})
        grade_levels = GradeLevel.objects.all().order_by('order', 'grade_number', 'track', 'id')

    streams_meta = []
    for gl in grade_levels:
        if gl.track == 'SCIENCE':
            lbl = f"{gl.grade_number}SC"
        elif gl.track == 'SOCIAL':
            lbl = f"{gl.grade_number}SS"
        else:
            lbl = f"{gl.grade_number}"
        streams_meta.append({
            'gl': gl,
            'label': lbl,
            'grade_number': gl.grade_number,
            'track': gl.track,
        })

    if request.method == 'POST':
        for key, value in request.POST.items():
            if key.startswith('hours_'):
                parts = key.split('_')
                if len(parts) == 4:
                    _, g_num, trk, sub_id = parts
                    try:
                        hours_val = int(value) if value and value.isdigit() else 0
                        hours_val = max(0, hours_val)
                        rule, _ = GradeLevelRule.objects.get_or_create(
                            grade_level=int(g_num),
                            track=trk,
                            subject_id=int(sub_id),
                            defaults={'weekly_hours': hours_val}
                        )
                        if rule.weekly_hours != hours_val:
                            rule.weekly_hours = hours_val
                            rule.save(update_fields=['weekly_hours'])
                    except Exception:
                        pass
        messages.success(request, "បានរក្សាទុក និងធ្វើបច្ចុប្បន្នភាពម៉ោងសិក្សាជោគជ័យ!")
        return redirect('subject_requirements_manager')

    rules_dict = {}
    for r in GradeLevelRule.objects.all():
        rules_dict[(r.subject_id, r.grade_level, r.track)] = r.weekly_hours

    matrix_rows = []
    stream_totals = [0] * len(streams_meta)
    
    for sub in subjects:
        cells = []
        total_hours_for_sub = 0
        for idx, sm in enumerate(streams_meta):
            hrs = rules_dict.get((sub.id, sm['grade_number'], sm['track']), 0)
            total_hours_for_sub += hrs
            stream_totals[idx] += hrs
            cells.append({
                'grade_number': sm['grade_number'],
                'track': sm['track'],
                'hours': hrs,
                'input_name': f"hours_{sm['grade_number']}_{sm['track']}_{sub.id}",
            })
        matrix_rows.append({
            'subject': sub,
            'cells': cells,
            'total_hours': total_hours_for_sub,
        })

    has_custom_default = SavedDefaultConfig.objects.filter(key='custom_subject_requirements').exists()

    return render(request, 'academics/subject_requirements.html', {
        'streams_meta': streams_meta,
        'matrix_rows': matrix_rows,
        'stream_totals': stream_totals,
        'subjects_count': subjects.count(),
        'has_custom_default': has_custom_default,
    })


@login_required
@role_required(['ADMIN'])
def subject_requirements_reset(request):
    """Reset all weekly teaching hours to 0."""
    GradeLevelRule.objects.all().update(weekly_hours=0)
    messages.success(request, "បានសម្អាតទិន្នន័យម៉ោងសិក្សាទាំងអស់ទៅជា 0 ជោគជ័យ!")
    return redirect('subject_requirements_manager')


@login_required
@role_required(['ADMIN'])
def subject_requirements_restore_moeys(request):
    """
    Restore official Ministry of Education (MoEYS) standard weekly teaching hours per grade level.
    """
    moeys_hours_matrix = {
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

    count = 0
    with transaction.atomic():
        for (g_num, trk), sub_map in moeys_hours_matrix.items():
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
                    count += 1

    messages.success(request, f"បានទាញយក និងកំណត់ម៉ោងសិក្សាតាមស្តង់ដារផ្លូវការក្រសួងអប់រំ (MoEYS) ជោគជ័យ!")
    return redirect('subject_requirements_manager')


@login_required
@role_required(['ADMIN'])
def subject_requirements_save_custom_default(request):
    """
    Save the current weekly hours configuration as the institution's custom default preset.
    """
    rules = GradeLevelRule.objects.filter(weekly_hours__gt=0).select_related('subject')
    saved_dict = {}
    for r in rules:
        saved_dict[f"{r.grade_level}_{r.track}_{r.subject.code}"] = r.weekly_hours

    SavedDefaultConfig.objects.update_or_create(
        key='custom_subject_requirements',
        defaults={'data': saved_dict}
    )
    messages.success(request, "បានរក្សាទុកទម្រង់ម៉ោងសិក្សាបច្ចុប្បន្នជា «លំនាំដើមផ្ទាល់ខ្លួន» របស់សាលាជោគជ័យ!")
    return redirect('subject_requirements_manager')


@login_required
@role_required(['ADMIN'])
def subject_requirements_restore_custom_default(request):
    """
    Restore the institution's custom default preset.
    """
    preset = SavedDefaultConfig.objects.filter(key='custom_subject_requirements').first()
    if not preset or not preset.data:
        messages.warning(request, "មិនទាន់មានទម្រង់លំនាំដើមផ្ទាល់ខ្លួនដែលបានរក្សាទុកនៅឡើយទេ!")
        return redirect('subject_requirements_manager')

    with transaction.atomic():
        GradeLevelRule.objects.all().update(weekly_hours=0)
        for k, hrs in preset.data.items():
            parts = k.split('_')
            if len(parts) == 3:
                g_num, trk, sub_code = parts
                sub = Subject.objects.filter(code=sub_code).first()
                if sub:
                    rule, _ = GradeLevelRule.objects.get_or_create(
                        grade_level=int(g_num),
                        track=trk,
                        subject=sub,
                        defaults={'weekly_hours': int(hrs)}
                    )
                    if rule.weekly_hours != int(hrs):
                        rule.weekly_hours = int(hrs)
                        rule.save(update_fields=['weekly_hours'])

    messages.success(request, "បានទាញយកទម្រង់ម៉ោងសិក្សាលំនាំដើមផ្ទាល់ខ្លួនរបស់សាលាជោគជ័យ!")
    return redirect('subject_requirements_manager')


@login_required
@role_required(['ADMIN'])
def subject_requirement_row_delete(request, subject_id):
    sub = get_object_or_404(Subject, pk=subject_id)
    GradeLevelRule.objects.filter(subject=sub).update(weekly_hours=0)
    messages.success(request, f"បានលុបម៉ោងសិក្សាសម្រាប់មុខវិជ្ជា {sub.name_kh} ជោគជ័យ!")
    return redirect('subject_requirements_manager')


# ----------------- TEACHER CLASS & SUBJECT ASSIGNMENTS -----------------

DEFAULT_TRAINING_LEVEL_QUOTAS = {
    'គ្រូទុតិយភូមិ': 16,
    'គ្រូបឋមភូមិ': 18,
    'គ្រូកម្រិតបឋម': 18,
    'default': 18,
}

def get_training_level_quotas():
    config = SavedDefaultConfig.objects.filter(key='training_level_quotas').first()
    if config and config.data:
        res = dict(DEFAULT_TRAINING_LEVEL_QUOTAS)
        res.update(config.data)
        return res
    return dict(DEFAULT_TRAINING_LEVEL_QUOTAS)


@login_required
@role_required(['ADMIN'])
def teacher_assignments_manager(request):
    """
    Teacher Class & Subject Assignments Manager.
    Admin can select any teacher and tick multiple classrooms and multiple subjects assigned to that teacher.
    Strictly isolated per Academic Year!
    """
    from .utils import get_active_academic_year
    active_year = get_active_academic_year(request)
    selected_year = request.GET.get('year') or request.GET.get('academic_year')
    if selected_year:
        if str(selected_year).isdigit():
            found_year = AcademicYear.objects.filter(id=int(selected_year)).first()
        else:
            found_year = AcademicYear.objects.filter(name=str(selected_year).strip()).first()
        if found_year:
            active_year = found_year

    teachers = Teacher.objects.filter(status='ACTIVE').order_by('khmer_name')
    classrooms = Classroom.objects.filter(academic_year=active_year).order_by('grade_level', 'code') if active_year else Classroom.objects.all().order_by('grade_level', 'code')
    subjects = Subject.objects.exclude(code__in=['R', 'D']).order_by('order', 'id')

    selected_teacher_id = request.GET.get('teacher')
    selected_teacher = None
    if selected_teacher_id:
        selected_teacher = Teacher.objects.filter(id=selected_teacher_id).first()
    if not selected_teacher and teachers.exists():
        selected_teacher = teachers.first()

    if request.method == 'POST' and selected_teacher:
        # Handle Max Hours update
        max_h_str = request.POST.get('max_weekly_hours', '').strip()
        apply_all = request.POST.get('apply_to_all_teachers') in ['true', 'on', '1']
        if max_h_str and max_h_str.isdigit():
            val = int(max_h_str)
            if apply_all:
                Teacher.objects.all().update(max_weekly_hours=val)
                selected_teacher.max_weekly_hours = val
            else:
                selected_teacher.max_weekly_hours = val
                selected_teacher.save(update_fields=['max_weekly_hours'])

        checked_pairs = set()
        for key in request.POST.keys():
            if key.startswith('assign_'):
                parts = key.split('_')
                if len(parts) == 3:
                    cls_id, sub_id = int(parts[1]), int(parts[2])
                    checked_pairs.add((cls_id, sub_id))

        # 1. Unassign unchecked pairs previously belonging to this teacher in this academic year
        existing_assigned = ClassSubject.objects.filter(teacher=selected_teacher, classroom__academic_year=active_year) if active_year else ClassSubject.objects.filter(teacher=selected_teacher)
        for cs in existing_assigned:
            if (cs.classroom_id, cs.subject_id) not in checked_pairs:
                cs.teacher = None
                cs.save(update_fields=['teacher'])

        # 2. Assign checked pairs to this teacher
        assigned_count = 0
        for cls_id, sub_id in checked_pairs:
            cs, _ = ClassSubject.objects.get_or_create(
                classroom_id=cls_id,
                subject_id=sub_id,
            )
            cs.teacher = selected_teacher
            cs.save(update_fields=['teacher'])
            assigned_count += 1

        messages.success(request, f"បានរក្សាទុកការចាត់តាំងមុខវិជ្ជា និងថ្នាក់បង្រៀន ({assigned_count} ថ្នាក់-មុខវិជ្ជា) សម្រាប់គ្រូ {selected_teacher.khmer_name} ជោគជ័យ!")
        return redirect(f"/academics/teacher-assignments/?teacher={selected_teacher.id}{f'&year={active_year.id}' if active_year else ''}")

    # Build matrix for display
    selected_teacher_pairs = set()
    if selected_teacher:
        selected_teacher_pairs = set(
            ClassSubject.objects.filter(teacher=selected_teacher, classroom__academic_year=active_year).values_list('classroom_id', 'subject_id') if active_year else ClassSubject.objects.filter(teacher=selected_teacher).values_list('classroom_id', 'subject_id')
        )

    all_assignments = {}
    cs_query = ClassSubject.objects.filter(classroom__academic_year=active_year, teacher__isnull=False).select_related('teacher') if active_year else ClassSubject.objects.filter(teacher__isnull=False).select_related('teacher')
    for cs in cs_query:
        all_assignments[(cs.classroom_id, cs.subject_id)] = cs.teacher

    rules_dict = {}
    for r in GradeLevelRule.objects.all():
        rules_dict[(r.subject_id, r.grade_level, r.track)] = r.weekly_hours

    teacher_stats = []
    for t in teachers:
        assigned_cs = ClassSubject.objects.filter(classroom__academic_year=active_year, teacher=t).select_related('classroom') if active_year else ClassSubject.objects.filter(teacher=t).select_related('classroom')
        t_hours = 0
        for cs in assigned_cs:
            h = rules_dict.get((cs.subject_id, cs.classroom.grade_level, cs.classroom.track))
            if h is None:
                h = rules_dict.get((cs.subject_id, cs.classroom.grade_level, 'GENERAL'), 0)
            t_hours += h

        t_max = t.max_weekly_hours or 18
        teacher_stats.append({
            'teacher': t,
            'assigned_count': assigned_cs.count(),
            'assigned_hours': t_hours,
            'max_weekly_hours': t_max,
            'is_selected': selected_teacher and t.id == selected_teacher.id,
            'is_over': t_hours > t_max,
        })

    matrix_grid = []
    selected_subject_hours = {sub.id: 0 for sub in subjects}
    selected_total_assigned_hours = 0

    for cls in classrooms:
        cells = []
        cls_assigned_subs = set(cls.assigned_subjects.values_list('subject_id', flat=True))
        if not cls_assigned_subs:
            cls_assigned_subs = set(GradeLevelRule.objects.filter(
                grade_level=cls.grade_level,
                track=cls.track,
                weekly_hours__gt=0
            ).values_list('subject_id', flat=True))

        for sub in subjects:
            is_checked = (cls.id, sub.id) in selected_teacher_pairs
            other_teacher = all_assignments.get((cls.id, sub.id))
            is_valid_for_class = sub.id in cls_assigned_subs

            h_req = rules_dict.get((sub.id, cls.grade_level, cls.track))
            if h_req is None:
                h_req = rules_dict.get((sub.id, cls.grade_level, 'GENERAL'), 0)

            if is_checked:
                selected_subject_hours[sub.id] += h_req
                selected_total_assigned_hours += h_req

            cells.append({
                'subject': sub,
                'classroom': cls,
                'input_name': f"assign_{cls.id}_{sub.id}",
                'is_checked': is_checked,
                'hours_required': h_req,
                'other_teacher': other_teacher if (other_teacher and other_teacher != selected_teacher) else None,
                'is_valid_for_class': is_valid_for_class,
            })
        matrix_grid.append({
            'classroom': cls,
            'cells': cells,
        })

    # Build teacher-subject code mapping (e.g. K1, K2, M1...)
    distinct_assignments = ClassSubject.objects.filter(
        classroom__academic_year=active_year,
        teacher__isnull=False
    ).exclude(
        subject__code__in=['R', 'D']
    ).values('subject_id', 'teacher_id').distinct().order_by('subject_id', 'teacher_id') if active_year else ClassSubject.objects.filter(
        teacher__isnull=False
    ).exclude(
        subject__code__in=['R', 'D']
    ).values('subject_id', 'teacher_id').distinct().order_by('subject_id', 'teacher_id')

    teacher_subject_code_map = {}
    subject_teacher_counters = {}
    for item in distinct_assignments:
        s_id = item['subject_id']
        t_id = item['teacher_id']
        sub = next((s for s in subjects if s.id == s_id), None)
        sub_code = sub.code if sub else 'S'
        if s_id not in subject_teacher_counters:
            subject_teacher_counters[s_id] = 1
        else:
            subject_teacher_counters[s_id] += 1
        teacher_subject_code_map[(s_id, t_id)] = f"{sub_code}{subject_teacher_counters[s_id]}"

    selected_teacher_codes = []
    if selected_teacher:
        for s in subjects:
            if (s.id, selected_teacher.id) in teacher_subject_code_map:
                selected_teacher_codes.append(teacher_subject_code_map[(s.id, selected_teacher.id)])

    # Retrieve dynamic training level quotas for modal customization
    training_quotas = get_training_level_quotas()
    raw_levels = list(Teacher.objects.filter(status='ACTIVE').values_list('training_level', flat=True).distinct())
    distinct_levels = sorted(list(set([lvl.strip() for lvl in raw_levels if lvl and lvl.strip()])))
    if 'គ្រូទុតិយភូមិ' not in distinct_levels:
        distinct_levels.insert(0, 'គ្រូទុតិយភូមិ')
    if 'គ្រូបឋមភូមិ' not in distinct_levels:
        distinct_levels.append('គ្រូបឋមភូមិ')

    training_level_settings = []
    for lvl in distinct_levels:
        training_level_settings.append({
            'name': lvl,
            'hours': training_quotas.get(lvl, 16 if 'ទុតិយភូមិ' in lvl else 18),
            'count': Teacher.objects.filter(status='ACTIVE', training_level=lvl).count(),
        })

    return render(request, 'academics/teacher_assignments.html', {
        'teachers': teachers,
        'teacher_stats': teacher_stats,
        'selected_teacher': selected_teacher,
        'selected_teacher_codes': ", ".join(selected_teacher_codes) or None,
        'classrooms': classrooms,
        'subjects': subjects,
        'matrix_grid': matrix_grid,
        'selected_assigned_count': len(selected_teacher_pairs),
        'selected_assigned_hours': selected_total_assigned_hours,
        'selected_subject_hours': selected_subject_hours,
        'selected_max_hours': selected_teacher.max_weekly_hours if selected_teacher else 18,
        'training_level_settings': training_level_settings,
        'training_quotas': training_quotas,
    })


@login_required
@role_required(['ADMIN'])
def teacher_assignments_training_quotas_save(request):
    """
    Save custom training level teaching hour quotas (e.g. គ្រូទុតិយភូមិ=16h, គ្រូបឋមភូមិ=18h)
    and sync/apply them to all active teachers in the database.
    """
    if request.method == 'POST':
        quotas = get_training_level_quotas()
        for key in request.POST.keys():
            if key.startswith('quota_'):
                level_name = key[6:].strip()
                val_str = request.POST.get(key, '').strip()
                if val_str.isdigit():
                    quotas[level_name] = max(1, min(60, int(val_str)))

        # Handle adding new training level dynamically
        new_name = request.POST.get('new_level_name', '').strip()
        new_hours_str = request.POST.get('new_level_hours', '').strip()
        if new_name and new_hours_str.isdigit():
            quotas[new_name] = max(1, min(60, int(new_hours_str)))

        SavedDefaultConfig.objects.update_or_create(
            key='training_level_quotas',
            defaults={'data': quotas}
        )

        # Apply to all teachers
        updated_count = 0
        teachers = Teacher.objects.all()
        for t in teachers:
            t_level = (t.training_level or '').strip()
            if t_level in quotas:
                new_max = quotas[t_level]
            elif 'ទុតិយភូមិ' in t_level:
                new_max = quotas.get('គ្រូទុតិយភូមិ', 16)
            elif 'បឋមភូមិ' in t_level:
                new_max = quotas.get('គ្រូបឋមភូមិ', 18)
            else:
                new_max = quotas.get('default', 18)

            if t.max_weekly_hours != new_max:
                t.max_weekly_hours = new_max
                t.save(update_fields=['max_weekly_hours'])
                updated_count += 1

        messages.success(request, f"បានរក្សាទុក និងកំណត់កូតាម៉ោងបង្រៀន (គ្រូទុតិយភូមិ = {quotas.get('គ្រូទុតិយភូមិ', 16)} ម៉ោង, ផ្សេងៗ = {quotas.get('default', 18)} ម៉ោង) ទៅគ្រូទាំងអស់ជោគជ័យ!")
    
    return redirect('teacher_assignments_manager')


@login_required
@role_required(['ADMIN'])
def teacher_assignments_reset_teacher(request, teacher_id):
    """Reset/Clear assignments for a single teacher."""
    from .utils import get_active_academic_year
    active_year = get_active_academic_year(request)
    teacher = get_object_or_404(Teacher, pk=teacher_id)
    
    cs_query = ClassSubject.objects.filter(teacher=teacher)
    if active_year:
        cs_query = cs_query.filter(classroom__academic_year=active_year)
    
    count = cs_query.count()
    cs_query.update(teacher=None)
    messages.success(request, f"បានសម្អាតការចាត់តាំងថ្នាក់ ({count} ថ្នាក់-មុខវិជ្ជា) សម្រាប់គ្រូ {teacher.khmer_name} ជោគជ័យ!")
    return redirect(f"/academics/teacher-assignments/?teacher={teacher.id}{f'&year={active_year.id}' if active_year else ''}")


@login_required
@role_required(['ADMIN'])
def teacher_assignments_reset_all(request):
    """Reset/Clear all teacher class assignments for the active academic year."""
    from .utils import get_active_academic_year
    active_year = get_active_academic_year(request)
    
    cs_query = ClassSubject.objects.filter(teacher__isnull=False)
    if active_year:
        cs_query = cs_query.filter(classroom__academic_year=active_year)
    
    count = cs_query.count()
    cs_query.update(teacher=None)
    messages.success(request, f"បានសម្អាតការចាត់តាំងគ្រូទាំងអស់ទូទាំងសាលា ({count} ការចាត់តាំង) ជោគជ័យ! លោកអ្នកអាចចាប់ផ្តើមចាត់តាំងថ្មីបាន។")
    return redirect(f"/academics/teacher-assignments/{f'?year={active_year.id}' if active_year else ''}")


@login_required
@role_required(['ADMIN'])
def teacher_assignments_auto_assign(request):
    """
    Intelligently auto-assign active teachers to classes based on their subject specialization
    and pedagogical training level quota (គ្រូទុតិយភូមិ = 16h, ផ្សេងៗ = 18h).
    """
    from .utils import get_active_academic_year
    active_year = get_active_academic_year(request)
    
    quotas = get_training_level_quotas()
    teachers = list(Teacher.objects.filter(status='ACTIVE').order_by('id'))
    
    # 1. Sync / Update teacher max hours based on training level
    for t in teachers:
        t_level = (t.training_level or '').strip()
        if t_level in quotas:
            quota_val = quotas[t_level]
        elif 'ទុតិយភូមិ' in t_level:
            quota_val = quotas.get('គ្រូទុតិយភូមិ', 16)
        elif 'បឋមភូមិ' in t_level:
            quota_val = quotas.get('គ្រូបឋមភូមិ', 18)
        else:
            quota_val = quotas.get('default', 18)
        
        if not t.max_weekly_hours or t.max_weekly_hours in [16, 18]:
            t.max_weekly_hours = quota_val
            t.save(update_fields=['max_weekly_hours'])

    # Classrooms ordered by High School (12, 11, 10) down to Middle School (9, 8, 7)
    classrooms = list(Classroom.objects.filter(academic_year=active_year).order_by('-grade_level', 'code') if active_year else Classroom.objects.all().order_by('-grade_level', 'code'))
    subjects = list(Subject.objects.exclude(code__in=['R', 'D']).order_by('order', 'id'))
    
    rules_dict = {}
    for r in GradeLevelRule.objects.all():
        rules_dict[(r.subject_id, r.grade_level, r.track)] = r.weekly_hours
    
    teacher_loads = {t.id: 0 for t in teachers}
    teacher_max = {t.id: t.max_weekly_hours or 18 for t in teachers}
    assigned_count = 0

    with transaction.atomic():
        for cls in classrooms:
            is_high_school = cls.grade_level >= 10
            for sub in subjects:
                h_req = rules_dict.get((sub.id, cls.grade_level, cls.track))
                if h_req is None:
                    h_req = rules_dict.get((sub.id, cls.grade_level, 'GENERAL'), 0)
                
                if h_req <= 0:
                    continue

                # Find candidate teachers specializing in this subject
                candidates = [t for t in teachers if sub.name_kh in (t.specialization or '') or (sub.name_en and sub.name_en.lower() in (t.specialization or '').lower())]
                if not candidates:
                    candidates = teachers # Fallback to any teacher

                # Score candidates: Prioritize High School Teachers (គ្រូទុតិយភូមិ) for Grades 10-12, Middle School (គ្រូបឋមភូមិ) for Grades 7-9
                def score_candidate(cand):
                    is_tutiya = 'ទុតិយភូមិ' in (cand.training_level or '')
                    level_match_bonus = 0
                    if is_high_school and is_tutiya:
                        level_match_bonus = -50  # Lower score is prioritized
                    elif not is_high_school and not is_tutiya:
                        level_match_bonus = -50
                    return (level_match_bonus, teacher_loads[cand.id], cand.id)

                candidates.sort(key=score_candidate)
                
                chosen = None
                for cand in candidates:
                    if teacher_loads[cand.id] + h_req <= teacher_max[cand.id]:
                        chosen = cand
                        break
                if not chosen and candidates:
                    # Over-quota fallback candidate with minimum load
                    candidates.sort(key=lambda t: (teacher_loads[t.id], t.id))
                    chosen = candidates[0]

                if chosen:
                    cs, _ = ClassSubject.objects.get_or_create(classroom=cls, subject=sub)
                    cs.teacher = chosen
                    cs.save(update_fields=['teacher'])
                    teacher_loads[chosen.id] += h_req
                    assigned_count += 1

    messages.success(request, f"បានចាត់តាំងគ្រូបង្រៀនតាមឯកទេស និងកម្រិតបណ្តុះបណ្តាលស្វ័យប្រវត្តិ ({assigned_count} ការចាត់តាំង, គ្រូទុតិយភូមិ=16h, ផ្សេងៗ=18h) ជោគជ័យ!")
    return redirect(f"/academics/teacher-assignments/{f'?year={active_year.id}' if active_year else ''}")




@login_required
@role_required(['ADMIN'])
def student_promotion_view(request):
    academic_years = AcademicYear.objects.all()
    classrooms = Classroom.objects.all()

    source_class_id = request.GET.get('source_class')
    students = []
    source_class = None

    if source_class_id:
        source_class = Classroom.objects.filter(id=source_class_id).first()
        if source_class:
            students = Student.objects.filter(classroom=source_class, status='ACTIVE')

    if request.method == 'POST':
        target_year_id = request.POST.get('target_year')
        target_class_id = request.POST.get('target_class')
        action = request.POST.get('promotion_action')
        selected_student_ids = request.POST.getlist('student_ids')

        if not selected_student_ids:
            messages.error(request, "សូមជ្រើសរើសសិស្សយ៉ាងតិចម្នាក់ដើម្បីផ្ទេរ!")
            return redirect(f"/academics/promotion/?source_class={source_class_id}")

        target_year = get_object_or_404(AcademicYear, pk=target_year_id) if target_year_id else None
        target_class = get_object_or_404(Classroom, pk=target_class_id) if target_class_id else None

        with transaction.atomic():
            count = 0
            for student_id in selected_student_ids:
                student = Student.objects.filter(id=student_id).first()
                if not student:
                    continue
                
                if action == 'PROMOTE' and target_class and target_year:
                    student.classroom = target_class
                    student.academic_year = target_year
                    student.status = 'ACTIVE'
                    student.save()
                    count += 1
                elif action == 'RETAIN' and target_year:
                    student.academic_year = target_year
                    if target_class:
                        student.classroom = target_class
                    student.save()
                    count += 1
                elif action == 'GRADUATE':
                    student.status = 'GRADUATED'
                    student.save()
                    count += 1

            messages.success(request, f"🎉 ជោគជ័យ! បានដំណើរការឡើងថ្នាក់/ផ្ទេរសិស្សចំនួន {count} នាក់។")
            return redirect('classroom_list')

    return render(request, 'academics/promotion.html', {
        'academic_years': academic_years,
        'classrooms': classrooms,
        'source_class_id': source_class_id,
        'source_class': source_class,
        'students': students,
    })


# =========================================================================
# Academic Years Manager (គ្រប់គ្រងឆ្នាំសិក្សា)
# =========================================================================
@login_required
@role_required(['ADMIN'])
def academic_year_list(request):
    """
    Manage Academic Years (ឆ្នាំសិក្សា) - List, Add, Set Current, Edit, Delete.
    """
    academic_years = AcademicYear.objects.all().order_by('-start_date')
    form = AcademicYearForm()
    
    years_data = []
    for ay in academic_years:
        years_data.append({
            'year': ay,
            'students_count': ay.enrolled_students.count(),
            'classrooms_count': ay.classrooms.count(),
        })

    return render(request, 'academics/academic_year_list.html', {
        'years_data': years_data,
        'form': form,
    })


@login_required
@role_required(['ADMIN'])
def academic_year_create(request):
    if request.method == 'POST':
        form = AcademicYearForm(request.POST)
        if form.is_valid():
            ay = form.save()
            messages.success(request, f"🎉 បានបន្ថែមឆ្នាំសិក្សា {ay.name} ដោយជោគជ័យ!")
            return redirect('academic_year_list')
        else:
            messages.error(request, "សូមពិនិត្យទិន្នន័យឆ្នាំសិក្សាឡើងវិញ!")
    return redirect('academic_year_list')


@login_required
@role_required(['ADMIN'])
def academic_year_edit(request, pk):
    ay = get_object_or_404(AcademicYear, pk=pk)
    if request.method == 'POST':
        form = AcademicYearForm(request.POST, instance=ay)
        if form.is_valid():
            form.save()
            messages.success(request, f"បានកែប្រែឆ្នាំសិក្សា {ay.name} ដោយជោគជ័យ!")
            return redirect('academic_year_list')
    return redirect('academic_year_list')


@login_required
@role_required(['ADMIN'])
def academic_year_delete(request, pk):
    ay = get_object_or_404(AcademicYear, pk=pk)
    if ay.is_current:
        messages.error(request, f"មិនអាចលុបឆ្នាំសិក្សាបច្ចុប្បន្ន ({ay.name}) បានទេ! សូមកំណត់ឆ្នាំសិក្សាផ្សេងជាបច្ចុប្បន្នសិន។")
        return redirect('academic_year_list')
    
    if ay.enrolled_students.exists() or ay.classrooms.exists():
        messages.error(request, f"មិនអាចលុបឆ្នាំសិក្សា {ay.name} បានទេ ព្រោះមានទិន្នន័យសិស្ស ឬថ្នាក់រៀនភ្ជាប់ជាមួយ!")
        return redirect('academic_year_list')

    name = ay.name
    ay.delete()
    messages.success(request, f"បានលុបឆ្នាំសិក្សា {name} ដោយជោគជ័យ!")
    return redirect('academic_year_list')


@login_required
def academic_year_switch(request, pk):
    """
    Session-based Academic Year Switcher for the active session.
    """
    ay = get_object_or_404(AcademicYear, pk=pk)
    request.session['active_academic_year_id'] = ay.id
    messages.info(request, f"🔄 បានប្តូរទៅកាន់ឆ្នាំសិក្សា៖ {ay.name}")
    next_url = request.META.get('HTTP_REFERER') or '/'
    return redirect(next_url)


@login_required
@role_required(['ADMIN'])
def academic_year_set_current(request, pk):
    ay = get_object_or_404(AcademicYear, pk=pk)
    AcademicYear.objects.filter(is_current=True).update(is_current=False)
    ay.is_current = True
    ay.save()
    request.session['active_academic_year_id'] = ay.id
    messages.success(request, f"🎉 បានកំណត់ឆ្នាំសិក្សា {ay.name} ជាឆ្នាំសិក្សាបច្ចុប្បន្ន (Current Active Year)!")
    return redirect('academic_year_list')



# =========================================================================
# Location AJAX APIs (For Cascading Dropdowns in Forms)
# =========================================================================
def _location_sort_key(x):
    code_str = str(x.get('code') or '').strip()
    try:
        return (0, int(code_str), code_str)
    except ValueError:
        return (1, 0, code_str)


def api_locations_provinces(request):
    provinces = list(Province.objects.all().values('id', 'code', 'name_kh', 'name_en'))
    provinces.sort(key=_location_sort_key)
    return JsonResponse({'status': 'success', 'data': provinces})


def api_locations_districts(request):
    province_id = request.GET.get('province_id')
    districts = District.objects.all()
    if province_id:
        districts = districts.filter(province_id=province_id)
    data = list(districts.values('id', 'code', 'name_kh', 'name_en', 'province_id'))
    data.sort(key=_location_sort_key)
    return JsonResponse({'status': 'success', 'data': data})


def api_locations_communes(request):
    district_id = request.GET.get('district_id')
    communes = Commune.objects.all()
    if district_id:
        communes = communes.filter(district_id=district_id)
    data = list(communes.values('id', 'code', 'name_kh', 'name_en', 'district_id'))
    data.sort(key=_location_sort_key)
    return JsonResponse({'status': 'success', 'data': data})


def api_locations_villages(request):
    commune_id = request.GET.get('commune_id')
    villages = Village.objects.all()
    if commune_id:
        villages = villages.filter(commune_id=commune_id)
    data = list(villages.values('id', 'code', 'name_kh', 'name_en', 'commune_id'))
    data.sort(key=_location_sort_key)
    return JsonResponse({'status': 'success', 'data': data})


# =========================================================================
# Admin Location Manager (គ្រប់គ្រង និងកែតម្រូវឈ្មោះខេត្ត ស្រុក ឃុំ ភូមិ)
# =========================================================================
@login_required
@role_required(['ADMIN'])
def location_manager_view(request):
    """
    Administrative Divisions Manager (Admin only).
    Allows Admin to browse, search, sort, and edit Province, District, Commune, and Village names.
    """
    level = request.GET.get('level', 'province') # province, district, commune, village
    search = request.GET.get('q', '').strip()
    province_id = request.GET.get('province_id', '')
    district_id = request.GET.get('district_id', '')
    commune_id = request.GET.get('commune_id', '')
    sort_by = request.GET.get('sort', 'code') # code, name_kh, name_en, parent
    order = request.GET.get('order', 'asc') # asc, desc

    provinces = Province.objects.all().order_by('code')
    districts = District.objects.filter(province_id=province_id).order_by('code') if province_id else District.objects.none()
    communes = Commune.objects.filter(district_id=district_id).order_by('code') if district_id else Commune.objects.none()

    if level == 'province':
        qs = Province.objects.all()
        if search:
            qs = qs.filter(Q(name_kh__icontains=search) | Q(name_en__icontains=search) | Q(code__icontains=search))
    elif level == 'district':
        qs = District.objects.select_related('province').all()
        if province_id:
            qs = qs.filter(province_id=province_id)
        if search:
            qs = qs.filter(Q(name_kh__icontains=search) | Q(name_en__icontains=search) | Q(code__icontains=search))
    elif level == 'commune':
        qs = Commune.objects.select_related('district__province').all()
        if district_id:
            qs = qs.filter(district_id=district_id)
        elif province_id:
            qs = qs.filter(district__province_id=province_id)
        if search:
            qs = qs.filter(Q(name_kh__icontains=search) | Q(name_en__icontains=search) | Q(code__icontains=search))
    elif level == 'village':
        qs = Village.objects.select_related('commune__district__province').all()
        if commune_id:
            qs = qs.filter(commune_id=commune_id)
        elif district_id:
            qs = qs.filter(commune__district_id=district_id)
        elif province_id:
            qs = qs.filter(commune__district__province_id=province_id)
        if search:
            qs = qs.filter(Q(name_kh__icontains=search) | Q(name_en__icontains=search) | Q(code__icontains=search))
    else:
        qs = Province.objects.all()

    items = list(qs)

    # Natural sorting helper
    def natural_sort_key(item):
        if sort_by == 'code':
            c_str = str(getattr(item, 'code', '') or '').strip()
            try:
                return (0, int(c_str), c_str)
            except ValueError:
                return (1, 0, c_str)
        elif sort_by == 'name_kh':
            return (0, 0, getattr(item, 'name_kh', '') or '')
        elif sort_by == 'name_en':
            return (0, 0, (getattr(item, 'name_en', '') or '').lower())
        elif sort_by == 'parent':
            if hasattr(item, 'province'):
                return (0, 0, item.province.name_kh)
            elif hasattr(item, 'district'):
                return (0, 0, item.district.name_kh)
            elif hasattr(item, 'commune'):
                return (0, 0, item.commune.name_kh)
            return (0, 0, '')
        return (0, 0, '')

    is_reverse = (order == 'desc')
    items.sort(key=natural_sort_key, reverse=is_reverse)
    items = items[:250]

    level_names = {
        'province': 'ខេត្ត/រាជធានី',
        'district': 'ស្រុក/ខណ្ឌ/ក្រុង',
        'commune': 'ឃុំ/សង្កាត់',
        'village': 'ភូមិ',
    }
    level_kh = level_names.get(level, 'ខេត្ត/រាជធានី')

    context = {
        'level': level,
        'level_kh': level_kh,
        'search': search,
        'province_id': province_id,
        'district_id': district_id,
        'commune_id': commune_id,
        'sort_by': sort_by,
        'order': order,
        'provinces': provinces,
        'districts': districts,
        'communes': communes,
        'items': items,
        'total_provinces': Province.objects.count(),
        'total_districts': District.objects.count(),
        'total_communes': Commune.objects.count(),
        'total_villages': Village.objects.count(),
    }
    return render(request, 'academics/location_manager.html', context)


@login_required
@role_required(['ADMIN'])
def location_item_create(request):
    """
    POST create new location item (Province, District, Commune, Village).
    """
    if request.method == 'POST':
        level = request.POST.get('level')
        code = request.POST.get('code', '').strip()
        name_kh = request.POST.get('name_kh', '').strip()
        name_en = request.POST.get('name_en', '').strip()

        if not name_kh:
            messages.error(request, "សូមបំពេញឈ្មោះជាភាសាខ្មែរ!")
            return redirect(request.META.get('HTTP_REFERER', 'location_manager_view'))

        if level == 'province':
            if not code:
                last_code = Province.objects.order_by('-id').values_list('code', flat=True).first()
                code = str(int(last_code) + 1) if last_code and last_code.isdigit() else str(Province.objects.count() + 1)
            Province.objects.create(code=code, name_kh=name_kh, name_en=name_en)
            messages.success(request, f"🎉 បានបន្ថែមខេត្ត/រាជធានី {name_kh} ដោយជោគជ័យ!")

        elif level == 'district':
            province_id = request.POST.get('province_id')
            if not province_id:
                messages.error(request, "សូមជ្រើសរើសខេត្ត/រាជធានី!")
                return redirect(request.META.get('HTTP_REFERER', 'location_manager_view'))
            province = get_object_or_404(Province, id=province_id)
            if not code:
                code = f"{province.code}{District.objects.filter(province=province).count() + 1:02d}"
            District.objects.create(province=province, code=code, name_kh=name_kh, name_en=name_en)
            messages.success(request, f"🎉 បានបន្ថែមស្រុក/ខណ្ឌ/ក្រុង {name_kh} ក្នុង {province.name_kh} ដោយជោគជ័យ!")

        elif level == 'commune':
            district_id = request.POST.get('district_id')
            if not district_id:
                messages.error(request, "សូមជ្រើសរើសស្រុក/ខណ្ឌ!")
                return redirect(request.META.get('HTTP_REFERER', 'location_manager_view'))
            district = get_object_or_404(District, id=district_id)
            if not code:
                code = f"{district.code}{Commune.objects.filter(district=district).count() + 1:02d}"
            Commune.objects.create(district=district, code=code, name_kh=name_kh, name_en=name_en)
            messages.success(request, f"🎉 បានបន្ថែមឃុំ/សង្កាត់ {name_kh} ក្នុង {district.name_kh} ដោយជោគជ័យ!")

        elif level == 'village':
            commune_id = request.POST.get('commune_id')
            if not commune_id:
                messages.error(request, "សូមជ្រើសរើសឃុំ/សង្កាត់!")
                return redirect(request.META.get('HTTP_REFERER', 'location_manager_view'))
            commune = get_object_or_404(Commune, id=commune_id)
            if not code:
                code = f"{commune.code}{Village.objects.filter(commune=commune).count() + 1:02d}"
            Village.objects.create(commune=commune, code=code, name_kh=name_kh, name_en=name_en)
            messages.success(request, f"🎉 បានបន្ថែមភូមិ {name_kh} ក្នុង {commune.name_kh} ដោយជោគជ័យ!")

    return redirect(request.META.get('HTTP_REFERER', 'location_manager_view'))


@login_required
@role_required(['ADMIN'])
def location_item_delete(request):
    """
    POST delete a location item (Province, District, Commune, Village).
    """
    if request.method == 'POST':
        level = request.POST.get('level')
        item_id = request.POST.get('item_id')

        if level == 'province':
            item = get_object_or_404(Province, id=item_id)
            name = item.name_kh
            item.delete()
            messages.success(request, f"បានលុបខេត្ត/រាជធានី {name} ដោយជោគជ័យ!")
        elif level == 'district':
            item = get_object_or_404(District, id=item_id)
            name = item.name_kh
            item.delete()
            messages.success(request, f"បានលុបស្រុក/ខណ្ឌ {name} ដោយជោគជ័យ!")
        elif level == 'commune':
            item = get_object_or_404(Commune, id=item_id)
            name = item.name_kh
            item.delete()
            messages.success(request, f"បានលុបឃុំ/សង្កាត់ {name} ដោយជោគជ័យ!")
        elif level == 'village':
            item = get_object_or_404(Village, id=item_id)
            name = item.name_kh
            item.delete()
            messages.success(request, f"បានលុបភូមិ {name} ដោយជោគជ័យ!")

    return redirect(request.META.get('HTTP_REFERER', 'location_manager_view'))


@login_required
@role_required(['ADMIN'])
def location_item_edit(request):
    """
    POST edit location item name (Province, District, Commune, Village).
    """
    if request.method == 'POST':
        level = request.POST.get('level')
        item_id = request.POST.get('item_id')
        code = request.POST.get('code', '').strip()
        name_kh = request.POST.get('name_kh', '').strip()
        name_en = request.POST.get('name_en', '').strip()

        if not name_kh:
            messages.error(request, "ឈ្មោះមិនអាចទទេបានទេ!")
            return redirect(request.META.get('HTTP_REFERER', 'location_manager_view'))

        if level == 'province':
            item = get_object_or_404(Province, id=item_id)
        elif level == 'district':
            item = get_object_or_404(District, id=item_id)
        elif level == 'commune':
            item = get_object_or_404(Commune, id=item_id)
        elif level == 'village':
            item = get_object_or_404(Village, id=item_id)
        else:
            messages.error(request, "ប្រភេទមិនត្រឹមត្រូវ!")
            return redirect('location_manager_view')

        if code:
            item.code = code
        item.name_kh = name_kh
        item.name_en = name_en
        item.save()
        messages.success(request, f"🎉 បានកែសម្រួលឈ្មោះ {name_kh} ដោយជោគជ័យ!")

    return redirect(request.META.get('HTTP_REFERER', 'location_manager_view'))


@login_required
@role_required(['ADMIN'])
def location_sync_excel(request):
    """
    Re-sync all locations from E:/SchoolSM/Cambodia All List2025.xlsx.
    """
    import openpyxl
    excel_file = os.path.join(settings.BASE_DIR, 'Cambodia All List2025.xlsx')
    if not os.path.exists(excel_file):
        messages.error(request, f"រកមិនឃើញឯកសារ Excel នៅ {excel_file} ទេ!")
        return redirect('location_manager_view')

    try:
        wb = openpyxl.load_workbook(excel_file, data_only=True)
        # 1. Provinces
        ws_prov = wb['CambodiaProvinceList2025']
        provinces_to_create = []
        for r in range(2, ws_prov.max_row + 1):
            p_code = str(ws_prov.cell(row=r, column=1).value or '').strip()
            p_kh = str(ws_prov.cell(row=r, column=2).value or '').strip()
            p_en = str(ws_prov.cell(row=r, column=3).value or '').strip()
            if p_code and p_kh:
                provinces_to_create.append(Province(code=p_code, name_kh=p_kh, name_en=p_en))

        with transaction.atomic():
            Province.objects.all().delete()
            Province.objects.bulk_create(provinces_to_create)

        province_map = {p.code: p.id for p in Province.objects.all()}

        # 2. Districts
        ws_dist = wb['CambodiaDistrictList2025']
        districts_to_create = []
        for r in range(2, ws_dist.max_row + 1):
            p_code = str(ws_dist.cell(row=r, column=1).value or '').strip()
            d_code = str(ws_dist.cell(row=r, column=2).value or '').strip()
            d_kh = str(ws_dist.cell(row=r, column=3).value or '').strip()
            d_en = str(ws_dist.cell(row=r, column=4).value or '').strip()
            if d_code and d_kh and p_code in province_map:
                districts_to_create.append(District(province_id=province_map[p_code], code=d_code, name_kh=d_kh, name_en=d_en))

        with transaction.atomic():
            District.objects.all().delete()
            District.objects.bulk_create(districts_to_create)

        district_map = {d.code: d.id for d in District.objects.all()}

        # 3. Communes
        ws_comm = wb['CambodiaCommuneList2025']
        communes_to_create = []
        for r in range(2, ws_comm.max_row + 1):
            d_code = str(ws_comm.cell(row=r, column=2).value or '').strip()
            c_code = str(ws_comm.cell(row=r, column=3).value or '').strip()
            c_kh = str(ws_comm.cell(row=r, column=4).value or '').strip()
            c_en = str(ws_comm.cell(row=r, column=5).value or '').strip()
            if c_code and c_kh and d_code in district_map:
                communes_to_create.append(Commune(district_id=district_map[d_code], code=c_code, name_kh=c_kh, name_en=c_en))

        with transaction.atomic():
            Commune.objects.all().delete()
            Commune.objects.bulk_create(communes_to_create, batch_size=1000)

        commune_map = {c.code: c.id for c in Commune.objects.all()}

        # 4. Villages
        ws_vill = wb['CambodiaVillagesList2025']
        villages_to_create = []
        for r in range(2, ws_vill.max_row + 1):
            c_code = str(ws_vill.cell(row=r, column=3).value or '').strip()
            v_code = str(ws_vill.cell(row=r, column=4).value or '').strip()
            v_kh = str(ws_vill.cell(row=r, column=5).value or '').strip()
            v_en = str(ws_vill.cell(row=r, column=6).value or '').strip()
            if v_kh and c_code in commune_map:
                villages_to_create.append(Village(commune_id=commune_map[c_code], code=v_code, name_kh=v_kh, name_en=v_en))

        with transaction.atomic():
            Village.objects.all().delete()
            Village.objects.bulk_create(villages_to_create, batch_size=2000)

        messages.success(request, f"🎉 ជោគជ័យ! បានទាញយក និងធ្វើបច្ចុប្បន្នភាពទិន្នន័យ (ខេត្ត: {Province.objects.count()}, ស្រុក: {District.objects.count()}, ឃុំ: {Commune.objects.count()}, ភូមិ: {Village.objects.count()}) ពី Excel រួចរាល់!")
    except Exception as e:
        messages.error(request, f"កំហុសក្នុងការ Sync ទិន្នន័យ៖ {str(e)}")

    return redirect('location_manager_view')


@login_required
@role_required(['ADMIN'])
def location_export_excel(request):
    """
    Export Cambodia Administrative Divisions (Province, District, Commune, Village) to styled Excel (.xlsx).
    Supports individual levels (with active search/filters) or 'all' levels in separate sheets.
    """
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter

    level = request.GET.get('level', 'province')
    search = request.GET.get('q', '').strip()
    province_id = request.GET.get('province_id', '')
    district_id = request.GET.get('district_id', '')
    commune_id = request.GET.get('commune_id', '')

    wb = openpyxl.Workbook()
    default_sheet = wb.active

    def style_sheet(ws, title, meta_text, headers, rows, header_bg='1E40AF'):
        title_font = Font(name='Khmer OS Siemreap', size=13, bold=True, color='1E3A8A')
        meta_font = Font(name='Khmer OS Siemreap', size=9, italic=True, color='475569')
        header_font = Font(name='Khmer OS Siemreap', size=9, bold=True, color='FFFFFF')
        header_fill = PatternFill(start_color=header_bg, end_color=header_bg, fill_type='solid')
        data_font = Font(name='Khmer OS Siemreap', size=9)
        zebra_fill = PatternFill(start_color='F8FAFC', end_color='F8FAFC', fill_type='solid')
        thin_border = Border(
            left=Side(style='thin', color='CBD5E1'),
            right=Side(style='thin', color='CBD5E1'),
            top=Side(style='thin', color='CBD5E1'),
            bottom=Side(style='thin', color='CBD5E1')
        )

        total_cols = len(headers)
        end_col = get_column_letter(total_cols)

        # Title
        ws.merge_cells(f'A1:{end_col}1')
        ws['A1'] = title
        ws['A1'].font = title_font
        ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[1].height = 28

        # Metadata
        ws.merge_cells(f'A2:{end_col}2')
        ws['A2'] = meta_text
        ws['A2'].font = meta_font
        ws['A2'].alignment = Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[2].height = 18

        # Empty row 3
        ws.row_dimensions[3].height = 6

        # Header Row (Row 4)
        for col_idx, h in enumerate(headers, 1):
            cell = ws.cell(row=4, column=col_idx, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
            cell.border = thin_border
        ws.row_dimensions[4].height = 24

        # Append data rows
        for row in rows:
            ws.append(row)

        # If <= 3000 rows (provinces, districts, communes, or filtered lists), apply full styling
        if len(rows) <= 3000:
            for r_idx in range(5, 5 + len(rows)):
                is_even = (r_idx % 2 == 0)
                ws.row_dimensions[r_idx].height = 20
                for c_idx in range(1, total_cols + 1):
                    cell = ws.cell(row=r_idx, column=c_idx)
                    cell.font = data_font
                    cell.border = thin_border
                    if is_even:
                        cell.fill = zebra_fill
                    if c_idx in [1, 2, 4, 6, 8] or isinstance(cell.value, int):
                        cell.alignment = Alignment(horizontal='center', vertical='center')
                    else:
                        cell.alignment = Alignment(horizontal='left', vertical='center')

        # Auto width
        for col_idx, h in enumerate(headers, 1):
            col_letter = get_column_letter(col_idx)
            max_len = len(str(h))
            for r in rows[:100]:
                if col_idx - 1 < len(r):
                    max_len = max(max_len, len(str(r[col_idx - 1] or '')))
            ws.column_dimensions[col_letter].width = min(max(max_len + 4, 12), 45)

        ws.freeze_panes = 'A5'

    now_str = datetime.datetime.now().strftime('%d/%m/%Y %H:%M')

    # Build data for Provinces
    def get_province_rows():
        district_counts = dict(District.objects.values('province_id').annotate(c=Count('id')).values_list('province_id', 'c'))
        commune_counts = dict(Commune.objects.values('district__province_id').annotate(c=Count('id')).values_list('district__province_id', 'c'))
        village_counts = dict(Village.objects.values('commune__district__province_id').annotate(c=Count('id')).values_list('commune__district__province_id', 'c'))

        qs = Province.objects.all().order_by('code')
        if search and level == 'province':
            qs = qs.filter(Q(name_kh__icontains=search) | Q(name_en__icontains=search) | Q(code__icontains=search))
        rows = []
        for idx, p in enumerate(qs, 1):
            rows.append([
                idx,
                p.code,
                p.name_kh,
                p.name_en or '-',
                district_counts.get(p.id, 0),
                commune_counts.get(p.id, 0),
                village_counts.get(p.id, 0)
            ])
        return rows, len(rows)

    # Build data for Districts
    def get_district_rows():
        commune_counts = dict(Commune.objects.values('district_id').annotate(c=Count('id')).values_list('district_id', 'c'))
        village_counts = dict(Village.objects.values('commune__district_id').annotate(c=Count('id')).values_list('commune__district_id', 'c'))

        qs = District.objects.select_related('province').all().order_by('province__code', 'code')
        if province_id:
            qs = qs.filter(province_id=province_id)
        if search and (level == 'district' or not province_id):
            qs = qs.filter(Q(name_kh__icontains=search) | Q(name_en__icontains=search) | Q(code__icontains=search) | Q(province__name_kh__icontains=search))
        rows = []
        for idx, d in enumerate(qs, 1):
            rows.append([
                idx,
                d.province.code,
                d.province.name_kh,
                d.code,
                d.name_kh,
                d.name_en or '-',
                commune_counts.get(d.id, 0),
                village_counts.get(d.id, 0)
            ])
        return rows, len(rows)

    # Build data for Communes
    def get_commune_rows():
        village_counts = dict(Village.objects.values('commune_id').annotate(c=Count('id')).values_list('commune_id', 'c'))

        qs = Commune.objects.select_related('district__province').all().order_by('district__province__code', 'district__code', 'code')
        if commune_id:
            qs = qs.filter(id=commune_id)
        elif district_id:
            qs = qs.filter(district_id=district_id)
        elif province_id:
            qs = qs.filter(district__province_id=province_id)
        if search and level == 'commune':
            qs = qs.filter(Q(name_kh__icontains=search) | Q(name_en__icontains=search) | Q(code__icontains=search) | Q(district__name_kh__icontains=search) | Q(district__province__name_kh__icontains=search))
        rows = []
        for idx, c in enumerate(qs, 1):
            rows.append([
                idx,
                c.district.province.code,
                c.district.province.name_kh,
                c.district.code,
                c.district.name_kh,
                c.code,
                c.name_kh,
                c.name_en or '-',
                village_counts.get(c.id, 0)
            ])
        return rows, len(rows)

    # Build data for Villages
    def get_village_rows():
        qs = Village.objects.select_related('commune__district__province').all().order_by('commune__district__province__code', 'commune__district__code', 'commune__code', 'code')
        if commune_id:
            qs = qs.filter(commune_id=commune_id)
        elif district_id:
            qs = qs.filter(commune__district_id=district_id)
        elif province_id:
            qs = qs.filter(commune__district__province_id=province_id)
        if search and level == 'village':
            qs = qs.filter(Q(name_kh__icontains=search) | Q(name_en__icontains=search) | Q(code__icontains=search) | Q(commune__name_kh__icontains=search) | Q(commune__district__name_kh__icontains=search) | Q(commune__district__province__name_kh__icontains=search))

        val_list = qs.values_list(
            'commune__district__province__code',
            'commune__district__province__name_kh',
            'commune__district__code',
            'commune__district__name_kh',
            'commune__code',
            'commune__name_kh',
            'code',
            'name_kh',
            'name_en'
        )
        rows = []
        for idx, v in enumerate(val_list, 1):
            rows.append([
                idx,
                v[0],
                v[1],
                v[2],
                v[3],
                v[4],
                v[5],
                v[6],
                v[7],
                v[8] or '-'
            ])
        return rows, len(rows)

    if level == 'province':
        ws = wb.create_sheet(title="ខេត្ត-រាជធានី")
        rows, count = get_province_rows()
        headers = ["ល.រ", "កូដខេត្ត", "ឈ្មោះខេត្ត/រាជធានី (ខ្មែរ)", "ឈ្មោះខេត្ត/រាជធានី (ឡាតាំង)", "ចំនួនស្រុក/ខណ្ឌ", "ចំនួនឃុំ/សង្កាត់", "ចំនួនភូមិ"]
        meta = f"កាលបរិច្ឆេទ Export៖ {now_str} | សរុបខេត្ត/រាជធានី៖ {count}"
        style_sheet(ws, "តារាងបញ្ជីខេត្ត/រាជធានីនៃព្រះរាជាណាចក្រកម្ពុជា (Provinces List)", meta, headers, rows, header_bg='1E40AF')

    elif level == 'district':
        ws = wb.create_sheet(title="ស្រុក-ខណ្ឌ")
        rows, count = get_district_rows()
        headers = ["ល.រ", "កូដខេត្ត", "ខេត្ត/រាជធានី", "កូដស្រុក", "ឈ្មោះស្រុក/ខណ្ឌ/ក្រុង (ខ្មែរ)", "ឈ្មោះស្រុក/ខណ្ឌ/ក្រុង (ឡាតាំង)", "ចំនួនឃុំ/សង្កាត់", "ចំនួនភូមិ"]
        meta = f"កាលបរិច្ឆេទ Export៖ {now_str} | សរុបស្រុក/ខណ្ឌ៖ {count}"
        style_sheet(ws, "តារាងបញ្ជីស្រុក/ខណ្ឌ/ក្រុងនៃព្រះរាជាណាចក្រកម្ពុជា (Districts List)", meta, headers, rows, header_bg='047857')

    elif level == 'commune':
        ws = wb.create_sheet(title="ឃុំ-សង្កាត់")
        rows, count = get_commune_rows()
        headers = ["ល.រ", "កូដខេត្ត", "ខេត្ត/រាជធានី", "កូដស្រុក", "ស្រុក/ខណ្ឌ/ក្រុង", "កូដឃុំ", "ឈ្មោះឃុំ/សង្កាត់ (ខ្មែរ)", "ឈ្មោះឃុំ/សង្កាត់ (ឡាតាំង)", "ចំនួនភូមិ"]
        meta = f"កាលបរិច្ឆេទ Export៖ {now_str} | សរុបឃុំ/សង្កាត់៖ {count}"
        style_sheet(ws, "តារាងបញ្ជីឃុំ/សង្កាត់នៃព្រះរាជាណាចក្រកម្ពុជា (Communes List)", meta, headers, rows, header_bg='D97706')

    elif level == 'village':
        ws = wb.create_sheet(title="ភូមិ")
        rows, count = get_village_rows()
        headers = ["ល.រ", "កូដខេត្ត", "ខេត្ត/រាជធានី", "កូដស្រុក", "ស្រុក/ខណ្ឌ/ក្រុង", "កូដឃុំ", "ឃុំ/សង្កាត់", "កូដភូមិ", "ឈ្មោះភូមិ (ខ្មែរ)", "ឈ្មោះភូមិ (ឡាតាំង)"]
        meta = f"កាលបរិច្ឆេទ Export៖ {now_str} | សរុបភូមិ៖ {count}"
        style_sheet(ws, "តារាងបញ្ជីភូមិនៃព្រះរាជាណាចក្រកម្ពុជា (Villages List)", meta, headers, rows, header_bg='0284C7')

    elif level == 'all':
        # Sheet 1: Provinces
        ws1 = wb.create_sheet(title="១. ខេត្ត-រាជធានី")
        p_rows, p_cnt = get_province_rows()
        p_headers = ["ល.រ", "កូដខេត្ត", "ឈ្មោះខេត្ត/រាជធានី (ខ្មែរ)", "ឈ្មោះខេត្ត/រាជធានី (ឡាតាំង)", "ចំនួនស្រុក/ខណ្ឌ", "ចំនួនឃុំ/សង្កាត់", "ចំនួនភូមិ"]
        style_sheet(ws1, "១. តារាងបញ្ជីខេត្ត/រាជធានីនៃព្រះរាជាណាចក្រកម្ពុជា (Provinces)", f"កាលបរិច្ឆេទ Export៖ {now_str} | សរុប៖ {p_cnt}", p_headers, p_rows, header_bg='1E40AF')

        # Sheet 2: Districts
        ws2 = wb.create_sheet(title="២. ស្រុក-ខណ្ឌ")
        d_rows, d_cnt = get_district_rows()
        d_headers = ["ល.រ", "កូដខេត្ត", "ខេត្ត/រាជធានី", "កូដស្រុក", "ឈ្មោះស្រុក/ខណ្ឌ/ក្រុង (ខ្មែរ)", "ឈ្មោះស្រុក/ខណ្ឌ/ក្រុង (ឡាតាំង)", "ចំនួនឃុំ/សង្កាត់", "ចំនួនភូមិ"]
        style_sheet(ws2, "២. តារាងបញ្ជីស្រុក/ខណ្ឌ/ក្រុង (Districts)", f"កាលបរិច្ឆេទ Export៖ {now_str} | សរុប៖ {d_cnt}", d_headers, d_rows, header_bg='047857')

        # Sheet 3: Communes
        ws3 = wb.create_sheet(title="៣. ឃុំ-សង្កាត់")
        c_rows, c_cnt = get_commune_rows()
        c_headers = ["ល.រ", "កូដខេត្ត", "ខេត្ត/រាជធានី", "កូដស្រុក", "ស្រុក/ខណ្ឌ/ក្រុង", "កូដឃុំ", "ឈ្មោះឃុំ/សង្កាត់ (ខ្មែរ)", "ឈ្មោះឃុំ/សង្កាត់ (ឡាតាំង)", "ចំនួនភូមិ"]
        style_sheet(ws3, "៣. តារាងបញ្ជីឃុំ/សង្កាត់ (Communes)", f"កាលបរិច្ឆេទ Export៖ {now_str} | សរុប៖ {c_cnt}", c_headers, c_rows, header_bg='D97706')

        # Sheet 4: Villages
        ws4 = wb.create_sheet(title="៤. ភូមិ")
        v_rows, v_cnt = get_village_rows()
        v_headers = ["ល.រ", "កូដខេត្ត", "ខេត្ត/រាជធានី", "កូដស្រុក", "ស្រុក/ខណ្ឌ/ក្រុង", "កូដឃុំ", "ឃុំ/សង្កាត់", "កូដភូមិ", "ឈ្មោះភូមិ (ខ្មែរ)", "ឈ្មោះភូមិ (ឡាតាំង)"]
        style_sheet(ws4, "៤. តារាងបញ្ជីភូមិ (Villages)", f"កាលបរិច្ឆេទ Export៖ {now_str} | សរុប៖ {v_cnt}", v_headers, v_rows, header_bg='0284C7')

    # Remove default sheet
    if default_sheet in wb.worksheets:
        wb.remove(default_sheet)

    filename = f"Cambodia_Locations_{level}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


@login_required
@role_required(['ADMIN'])
def location_export_csv(request):
    """
    Export Cambodia Administrative Divisions to UTF-8 CSV (with BOM).
    """
    import csv

    level = request.GET.get('level', 'province')
    search = request.GET.get('q', '').strip()
    province_id = request.GET.get('province_id', '')
    district_id = request.GET.get('district_id', '')
    commune_id = request.GET.get('commune_id', '')

    filename = f"Cambodia_Locations_{level}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write('\ufeff')  # UTF-8 BOM

    writer = csv.writer(response)

    if level == 'province':
        writer.writerow(["ល.រ", "កូដខេត្ត", "ឈ្មោះខេត្ត_ខ្មែរ", "ឈ្មោះខេត្ត_ឡាតាំង", "ចំនួនស្រុក", "ចំនួនឃុំ", "ចំនួនភូមិ"])
        district_counts = dict(District.objects.values('province_id').annotate(c=Count('id')).values_list('province_id', 'c'))
        commune_counts = dict(Commune.objects.values('district__province_id').annotate(c=Count('id')).values_list('district__province_id', 'c'))
        village_counts = dict(Village.objects.values('commune__district__province_id').annotate(c=Count('id')).values_list('commune__district__province_id', 'c'))

        qs = Province.objects.all().order_by('code')
        if search:
            qs = qs.filter(Q(name_kh__icontains=search) | Q(name_en__icontains=search) | Q(code__icontains=search))
        for idx, p in enumerate(qs, 1):
            writer.writerow([idx, p.code, p.name_kh, p.name_en or '', district_counts.get(p.id, 0), commune_counts.get(p.id, 0), village_counts.get(p.id, 0)])

    elif level == 'district':
        writer.writerow(["ល.រ", "កូដខេត្ត", "ខេត្ត_ខ្មែរ", "កូដស្រុក", "ឈ្មោះស្រុក_ខ្មែរ", "ឈ្មោះស្រុក_ឡាតាំង", "ចំនួនឃុំ", "ចំនួនភូមិ"])
        commune_counts = dict(Commune.objects.values('district_id').annotate(c=Count('id')).values_list('district_id', 'c'))
        village_counts = dict(Village.objects.values('commune__district_id').annotate(c=Count('id')).values_list('commune__district_id', 'c'))

        qs = District.objects.select_related('province').all().order_by('province__code', 'code')
        if province_id:
            qs = qs.filter(province_id=province_id)
        if search:
            qs = qs.filter(Q(name_kh__icontains=search) | Q(name_en__icontains=search) | Q(code__icontains=search) | Q(province__name_kh__icontains=search))
        for idx, d in enumerate(qs, 1):
            writer.writerow([idx, d.province.code, d.province.name_kh, d.code, d.name_kh, d.name_en or '', commune_counts.get(d.id, 0), village_counts.get(d.id, 0)])

    elif level == 'commune':
        writer.writerow(["ល.រ", "កូដខេត្ត", "ខេត្ត_ខ្មែរ", "កូដស្រុក", "ស្រុក_ខ្មែរ", "កូដឃុំ", "ឈ្មោះឃុំ_ខ្មែរ", "ឈ្មោះឃុំ_ឡាតាំង", "ចំនួនភូមិ"])
        village_counts = dict(Village.objects.values('commune_id').annotate(c=Count('id')).values_list('commune_id', 'c'))

        qs = Commune.objects.select_related('district__province').all().order_by('district__province__code', 'district__code', 'code')
        if commune_id:
            qs = qs.filter(id=commune_id)
        elif district_id:
            qs = qs.filter(district_id=district_id)
        elif province_id:
            qs = qs.filter(district__province_id=province_id)
        if search:
            qs = qs.filter(Q(name_kh__icontains=search) | Q(name_en__icontains=search) | Q(code__icontains=search) | Q(district__name_kh__icontains=search) | Q(district__province__name_kh__icontains=search))
        for idx, c in enumerate(qs, 1):
            writer.writerow([idx, c.district.province.code, c.district.province.name_kh, c.district.code, c.district.name_kh, c.code, c.name_kh, c.name_en or '', village_counts.get(c.id, 0)])

    elif level == 'village':
        writer.writerow(["ល.រ", "កូដខេត្ត", "ខេត្ត_ខ្មែរ", "កូដស្រុក", "ស្រុក_ខ្មែរ", "កូដឃុំ", "ឃុំ_ខ្មែរ", "កូដភូមិ", "ឈ្មោះភូមិ_ខ្មែរ", "ឈ្មោះភូមិ_ឡាតាំង"])
        qs = Village.objects.select_related('commune__district__province').all().order_by('commune__district__province__code', 'commune__district__code', 'commune__code', 'code')
        if commune_id:
            qs = qs.filter(commune_id=commune_id)
        elif district_id:
            qs = qs.filter(commune__district_id=district_id)
        elif province_id:
            qs = qs.filter(commune__district__province_id=province_id)
        if search:
            qs = qs.filter(Q(name_kh__icontains=search) | Q(name_en__icontains=search) | Q(code__icontains=search) | Q(commune__name_kh__icontains=search) | Q(commune__district__name_kh__icontains=search) | Q(commune__district__province__name_kh__icontains=search))
        
        val_list = qs.values_list(
            'commune__district__province__code',
            'commune__district__province__name_kh',
            'commune__district__code',
            'commune__district__name_kh',
            'commune__code',
            'commune__name_kh',
            'code',
            'name_kh',
            'name_en'
        )
        for idx, v in enumerate(val_list, 1):
            writer.writerow([idx, v[0], v[1], v[2], v[3], v[4], v[5], v[6], v[7], v[8] or ''])

    elif level in ['all', 'full_flat']:
        writer.writerow(["ល.រ", "កូដខេត្ត", "ខេត្ត_ខ្មែរ", "ខេត្ត_ឡាតាំង", "កូដស្រុក", "ស្រុក_ខ្មែរ", "ស្រុក_ឡាតាំង", "កូដឃុំ", "ឃុំ_ខ្មែរ", "ឃុំ_ឡាតាំង", "កូដភូមិ", "ភូមិ_ខ្មែរ", "ភូមិ_ឡាតាំង"])
        qs = Village.objects.select_related('commune__district__province').all().order_by('commune__district__province__code', 'commune__district__code', 'commune__code', 'code')
        if commune_id:
            qs = qs.filter(commune_id=commune_id)
        elif district_id:
            qs = qs.filter(commune__district_id=district_id)
        elif province_id:
            qs = qs.filter(commune__district__province_id=province_id)
        if search:
            qs = qs.filter(Q(name_kh__icontains=search) | Q(name_en__icontains=search) | Q(code__icontains=search) | Q(commune__name_kh__icontains=search) | Q(commune__district__name_kh__icontains=search) | Q(commune__district__province__name_kh__icontains=search))
        
        val_list = qs.values_list(
            'commune__district__province__code',
            'commune__district__province__name_kh',
            'commune__district__province__name_en',
            'commune__district__code',
            'commune__district__name_kh',
            'commune__district__name_en',
            'commune__code',
            'commune__name_kh',
            'commune__name_en',
            'code',
            'name_kh',
            'name_en'
        )
        for idx, v in enumerate(val_list, 1):
            writer.writerow([
                idx,
                v[0],
                v[1],
                v[2] or '',
                v[3],
                v[4],
                v[5] or '',
                v[6],
                v[7],
                v[8] or '',
                v[9],
                v[10],
                v[11] or ''
            ])

    return response
