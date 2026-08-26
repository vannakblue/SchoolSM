from django.contrib import admin
from .models import (
    ExamTerm, Grade,
    StandardizedExam, ExamRoom, ExamSubject, ExamCandidate, CandidateSubjectScore,
    ExamRoomSubjectCode, ExamStudentExclusion
)

@admin.register(ExamTerm)
class ExamTermAdmin(admin.ModelAdmin):
    list_display = ['name', 'academic_year', 'term_type', 'start_date', 'end_date', 'is_published']
    list_filter = ['academic_year', 'term_type', 'is_published']

@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ['student', 'subject', 'exam_term', 'classroom', 'score', 'max_score', 'grade_letter']
    list_filter = ['exam_term', 'classroom', 'subject', 'grade_letter']
    search_fields = ['student__khmer_name', 'student__student_id']

@admin.register(StandardizedExam)
class StandardizedExamAdmin(admin.ModelAdmin):
    list_display = ['name', 'academic_year', 'grade_level', 'track', 'exam_date', 'candidates_per_room', 'is_published']
    list_filter = ['academic_year', 'grade_level', 'track', 'is_published']
    search_fields = ['name']

@admin.register(ExamRoom)
class ExamRoomAdmin(admin.ModelAdmin):
    list_display = ['room_name', 'exam', 'room_number', 'secret_code', 'building', 'candidate_count']
    list_filter = ['exam']

@admin.register(ExamSubject)
class ExamSubjectAdmin(admin.ModelAdmin):
    list_display = ['subject', 'exam', 'max_score', 'coefficient', 'session', 'exam_date']
    list_filter = ['exam', 'session']

@admin.register(ExamRoomSubjectCode)
class ExamRoomSubjectCodeAdmin(admin.ModelAdmin):
    list_display = ['secret_code', 'exam_room', 'exam_subject', 'is_graded', 'graded_by', 'graded_at']
    list_filter = ['exam_subject__exam', 'is_graded']
    search_fields = ['secret_code']

@admin.register(ExamCandidate)
class ExamCandidateAdmin(admin.ModelAdmin):
    list_display = ['roll_number', 'desk_number', 'candidate_name_kh', 'gender', 'room', 'exam', 'is_disciplinary_blocked', 'total_score', 'average_score', 'grade_letter', 'rank_overall']
    list_filter = ['exam', 'room', 'gender', 'is_disciplinary_blocked', 'grade_letter']
    search_fields = ['candidate_name_kh', 'candidate_name_en', 'roll_number']

@admin.register(CandidateSubjectScore)
class CandidateSubjectScoreAdmin(admin.ModelAdmin):
    list_display = ['candidate', 'exam_subject', 'score', 'is_absent', 'signature_present']
    list_filter = ['exam_subject__exam', 'exam_subject', 'is_absent']

@admin.register(ExamStudentExclusion)
class ExamStudentExclusionAdmin(admin.ModelAdmin):
    list_display = ['student', 'academic_year', 'exam_term', 'standardized_exam', 'month', 'reason', 'is_active', 'excluded_by', 'created_at']
    list_filter = ['academic_year', 'reason', 'is_active', 'month']
    search_fields = ['student__khmer_name', 'student__student_id', 'notes']



