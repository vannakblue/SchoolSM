from rest_framework import serializers
from apps.accounts.models import User, SchoolProfile
from apps.teachers.models import Teacher, TeacherAttendance
from apps.students.models import Student
from apps.attendance.models import StudentAttendance
from apps.academics.models import Timetable, Classroom, Subject
from apps.examinations.models import ExamTerm, Grade
from .models import DeviceFCMToken, MobileNotificationLog


class UserProfileSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    display_name = serializers.CharField(read_only=True)
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'role', 'role_display', 'khmer_name', 'latin_name',
            'display_name', 'phone', 'email', 'avatar_url', 'is_active', 'date_joined'
        ]

    def get_avatar_url(self, obj):
        if obj.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None


class TeacherProfileSerializer(serializers.ModelSerializer):
    user_details = UserProfileSerializer(source='user', read_only=True)
    gender_display = serializers.CharField(source='get_gender_display', read_only=True)

    class Meta:
        model = Teacher
        fields = [
            'id', 'teacher_id', 'khmer_name', 'latin_name', 'gender', 'gender_display',
            'date_of_birth', 'phone', 'email', 'specialization', 'qualification',
            'status', 'user_details'
        ]


class StudentProfileSerializer(serializers.ModelSerializer):
    user_details = UserProfileSerializer(source='user', read_only=True)
    gender_display = serializers.CharField(source='get_gender_display', read_only=True)
    classroom_name = serializers.CharField(source='classroom.name', read_only=True, default='')

    class Meta:
        model = Student
        fields = [
            'id', 'student_id', 'khmer_name', 'latin_name', 'gender', 'gender_display',
            'date_of_birth', 'classroom_name', 'phone', 'father_name', 'father_phone',
            'mother_name', 'mother_phone', 'status', 'user_details'
        ]


class StudentAttendanceSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.khmer_name', read_only=True)
    student_id_str = serializers.CharField(source='student.student_id', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = StudentAttendance
        fields = [
            'id', 'date', 'student_name', 'student_id_str', 'status',
            'status_display', 'session', 'remarks', 'created_at'
        ]


class TeacherAttendanceSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source='teacher.khmer_name', read_only=True)
    teacher_id_str = serializers.CharField(source='teacher.teacher_id', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = TeacherAttendance
        fields = [
            'id', 'date', 'teacher_name', 'teacher_id_str', 'status',
            'status_display', 'check_in_time', 'check_out_time', 'check_in_method', 'notes'
        ]


class TimetableSerializer(serializers.ModelSerializer):
    classroom_name = serializers.CharField(source='classroom.name', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    subject_code = serializers.CharField(source='subject.code', read_only=True, default='')
    teacher_name = serializers.CharField(source='teacher.khmer_name', read_only=True, default='')
    day_display = serializers.CharField(source='get_day_of_week_display', read_only=True)

    class Meta:
        model = Timetable
        fields = [
            'id', 'day_of_week', 'day_display', 'period_number', 'start_time', 'end_time', 'room',
            'classroom_name', 'subject_name', 'subject_code', 'teacher_name'
        ]


class ExamGradeSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    exam_title = serializers.CharField(source='exam_term.name', read_only=True)
    student_name = serializers.CharField(source='student.khmer_name', read_only=True)

    class Meta:
        model = Grade
        fields = [
            'id', 'student_name', 'exam_title', 'subject_name',
            'score', 'max_score', 'grade_letter', 'remarks'
        ]


class MobileNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = MobileNotificationLog
        fields = ['id', 'title', 'body', 'data_payload', 'is_read', 'sent_at']


class SchoolInfoSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()
    seal_url = serializers.SerializerMethodField()

    class Meta:
        model = SchoolProfile
        fields = [
            'name_kh', 'name_en', 'short_name', 'school_code', 'school_type',
            'motto', 'logo_url', 'seal_url', 'principal_name', 'phone', 'email',
            'facebook_page', 'telegram_channel'
        ]

    def get_logo_url(self, obj):
        if obj.logo:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.logo.url) if request else obj.logo.url
        return None

    def get_seal_url(self, obj):
        if obj.seal:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.seal.url) if request else obj.seal.url
        return None
