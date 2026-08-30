import datetime
from decimal import Decimal
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.contrib.auth import authenticate
from django.db.models import Avg, Count, Q

from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User, SchoolProfile
from apps.teachers.models import Teacher, TeacherAttendance
from apps.students.models import Student
from apps.attendance.models import StudentAttendance
from apps.academics.models import Timetable, Classroom, Subject, AcademicYear
from apps.examinations.models import ExamTerm, Grade
from .models import DeviceFCMToken, MobileNotificationLog
from .serializers import (
    UserProfileSerializer, TeacherProfileSerializer, StudentProfileSerializer,
    StudentAttendanceSerializer, TeacherAttendanceSerializer, TimetableSerializer,
    ExamGradeSerializer, MobileNotificationSerializer, SchoolInfoSerializer
)
from .firebase_service import send_mobile_push_notification


class MobileLoginView(APIView):
    """
    Mobile Login endpoint: Authenticates with username & password, returns JWT tokens + user profile.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        username = request.data.get('username', '').strip()
        password = request.data.get('password', '').strip()
        device_token = request.data.get('device_token', '').strip()
        device_type = request.data.get('device_type', 'android').strip().lower()
        device_name = request.data.get('device_name', '')
        app_version = request.data.get('app_version', '1.0.0')

        if not username or not password:
            return Response({
                'status': 'error',
                'message': 'សូមបញ្ចូលឈ្មោះគណនី និងពាក្យសម្ងាត់ (Username and Password are required)!'
            }, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(username=username, password=password)
        if not user:
            return Response({
                'status': 'error',
                'message': 'ឈ្មោះគណនី ឬពាក្យសម្ងាត់មិនត្រឹមត្រូវទេ (Invalid credentials)!'
            }, status=status.HTTP_401_UNAUTHORIZED)

        if not user.is_active:
            return Response({
                'status': 'error',
                'message': 'គណនីនេះត្រូវបានចាក់សោ (Account is deactivated)!'
            }, status=status.HTTP_403_FORBIDDEN)

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        # Register FCM token if provided
        if device_token:
            DeviceFCMToken.objects.update_or_create(
                token=device_token,
                defaults={
                    'user': user,
                    'device_type': device_type,
                    'device_name': device_name,
                    'app_version': app_version,
                    'is_active': True
                }
            )

        user_serializer = UserProfileSerializer(user, context={'request': request})
        school_profile = SchoolProfile.get_settings()
        school_serializer = SchoolInfoSerializer(school_profile, context={'request': request})

        # Fetch role-specific details
        role_profile = None
        if user.role == User.Role.TEACHER:
            teacher = getattr(user, 'teacher_profile', None)
            if teacher:
                role_profile = TeacherProfileSerializer(teacher, context={'request': request}).data
        elif user.role == User.Role.STUDENT:
            student = getattr(user, 'student_profile', None)
            if student:
                role_profile = StudentProfileSerializer(student, context={'request': request}).data

        return Response({
            'status': 'success',
            'message': f'សូមស្វាគមន៍ {user.display_name}!',
            'tokens': {
                'access': access_token,
                'refresh': str(refresh),
            },
            'user': user_serializer.data,
            'role_profile': role_profile,
            'school_info': school_serializer.data
        }, status=status.HTTP_200_OK)


class RegisterFCMTokenView(APIView):
    """
    Registers or updates the FCM push notification device token.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        token = request.data.get('token', '').strip()
        device_type = request.data.get('device_type', 'android').strip().lower()
        device_name = request.data.get('device_name', '')
        app_version = request.data.get('app_version', '')

        if not token:
            return Response({'status': 'error', 'message': 'Token is required'}, status=status.HTTP_400_BAD_REQUEST)

        DeviceFCMToken.objects.update_or_create(
            token=token,
            defaults={
                'user': request.user,
                'device_type': device_type,
                'device_name': device_name,
                'app_version': app_version,
                'is_active': True
            }
        )
        return Response({'status': 'success', 'message': 'Device token registered successfully.'})


class UserProfileView(APIView):
    """
    Retrieves and updates the logged-in user profile.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        serializer = UserProfileSerializer(user, context={'request': request})
        role_profile = None

        if user.role == User.Role.TEACHER:
            teacher = getattr(user, 'teacher_profile', None)
            if teacher:
                role_profile = TeacherProfileSerializer(teacher, context={'request': request}).data
        elif user.role == User.Role.STUDENT:
            student = getattr(user, 'student_profile', None)
            if student:
                role_profile = StudentProfileSerializer(student, context={'request': request}).data

        return Response({
            'status': 'success',
            'user': serializer.data,
            'role_profile': role_profile
        })

    def patch(self, request):
        user = request.user
        phone = request.data.get('phone')
        email = request.data.get('email')

        if phone is not None:
            user.phone = phone.strip() or None
        if email is not None:
            user.email = email.strip()

        user.save()
        return Response({
            'status': 'success',
            'message': 'បានកែប្រែព័ត៌មានជោគជ័យ!',
            'user': UserProfileSerializer(user, context={'request': request}).data
        })


class MobileChangePasswordView(APIView):
    """
    Allows user to change their password securely via mobile API.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        current_password = request.data.get('current_password', '').strip()
        new_password = request.data.get('new_password', '').strip()

        if current_password and not user.check_password(current_password):
            return Response({
                'status': 'error',
                'message': 'ពាក្យសម្ងាត់បច្ចុប្បន្នមិនត្រឹមត្រូវទេ (Current password incorrect)!'
            }, status=status.HTTP_400_BAD_REQUEST)

        if not new_password or len(new_password) < 4:
            return Response({
                'status': 'error',
                'message': 'ពាក្យសម្ងាត់ថ្មីត្រូវមានយ៉ាងហោចណាស់ ៤ តួអក្សរ!'
            }, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()

        return Response({
            'status': 'success',
            'message': '🎉 បានផ្លាស់ប្តូរពាក្យសម្ងាត់ដោយជោគជ័យ!'
        })


class QRAttendanceScanView(APIView):
    """
    Processes QR Code scans from the mobile camera for Teacher & Student check-in.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        qr_code = request.data.get('qr_code', '').strip()
        scan_type = request.data.get('scan_type', 'AUTO').upper()  # TEACHER, STUDENT, AUTO

        if not qr_code:
            return Response({'status': 'error', 'message': 'QR code data is empty.'}, status=status.HTTP_400_BAD_REQUEST)

        today = timezone.now().date()
        now_time = timezone.now().time()

        # 1. Check if Teacher scan
        teacher = Teacher.objects.filter(Q(teacher_id__iexact=qr_code) | Q(user__username__iexact=qr_code)).first()
        if teacher and (scan_type in ['TEACHER', 'AUTO']):
            att, created = TeacherAttendance.objects.get_or_create(
                teacher=teacher,
                date=today,
                defaults={
                    'status': TeacherAttendance.Status.PRESENT,
                    'check_in_time': now_time,
                    'check_in_method': 'QR_CODE',
                    'notes': 'Checked in via Mobile QR Scanner'
                }
            )
            if not created and not att.check_out_time:
                att.check_out_time = now_time
                att.save(update_fields=['check_out_time'])
                msg = f'👋 លោកគ្រូ/អ្នកគ្រូ {teacher.khmer_name} បានស្កេន Check-Out ម៉ោង {now_time.strftime("%H:%M")}'
            else:
                msg = f'✅ លោកគ្រូ/អ្នកគ្រូ {teacher.khmer_name} បានស្កេន Check-In ម៉ោង {now_time.strftime("%H:%M")}'

            return Response({
                'status': 'success',
                'type': 'TEACHER',
                'message': msg,
                'name': teacher.khmer_name,
                'id': teacher.teacher_id,
                'time': now_time.strftime('%H:%M')
            })

        # 2. Check if Student scan
        student = Student.objects.filter(Q(student_id__iexact=qr_code) | Q(user__username__iexact=qr_code)).first()
        if student and (scan_type in ['STUDENT', 'AUTO']):
            classroom = student.classroom or Classroom.objects.first()
            att, created = StudentAttendance.objects.get_or_create(
                student=student,
                date=today,
                classroom=classroom,
                defaults={
                    'status': 'PRESENT',
                    'session': 'MORNING',
                    'notes': 'Checked in via Mobile QR Scanner'
                }
            )
            return Response({
                'status': 'success',
                'type': 'STUDENT',
                'message': f'✅ សិស្ស {student.khmer_name} (ថ្នាក់ {student.classroom.name if student.classroom else "-"}) មានវត្តមាន!',
                'name': student.khmer_name,
                'id': student.student_id,
                'classroom': student.classroom.name if student.classroom else '',
                'time': now_time.strftime('%H:%M')
            })

        return Response({
            'status': 'error',
            'message': f'រកមិនឃើញទិន្នន័យសម្រាប់ QR Code "{qr_code}" នេះទេ!'
        }, status=status.HTTP_404_NOT_FOUND)


class AttendanceHistoryView(APIView):
    """
    Returns attendance logs for the logged-in user or student's classroom.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        limit = int(request.query_params.get('limit', 30))

        if user.role == User.Role.STUDENT:
            student = getattr(user, 'student_profile', None)
            if not student:
                return Response({'status': 'success', 'records': []})
            records = StudentAttendance.objects.filter(student=student).order_by('-date')[:limit]
            serializer = StudentAttendanceSerializer(records, many=True)
            return Response({'status': 'success', 'records': serializer.data})

        elif user.role == User.Role.TEACHER:
            teacher = getattr(user, 'teacher_profile', None)
            if not teacher:
                return Response({'status': 'success', 'records': []})
            records = TeacherAttendance.objects.filter(teacher=teacher).order_by('-date')[:limit]
            serializer = TeacherAttendanceSerializer(records, many=True)
            return Response({'status': 'success', 'records': serializer.data})

        else:
            # Admin summary
            today = timezone.now().date()
            teacher_records = TeacherAttendance.objects.filter(date=today).order_by('-check_in_time')[:limit]
            serializer = TeacherAttendanceSerializer(teacher_records, many=True)
            return Response({'status': 'success', 'records': serializer.data})


class TimetableView(APIView):
    """
    Returns timetable schedule by day for student's classroom or teacher's assignments.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        day = request.query_params.get('day')

        qs = Timetable.objects.select_related('classroom', 'subject', 'teacher').all()

        if user.role == User.Role.STUDENT:
            student = getattr(user, 'student_profile', None)
            if student and student.classroom:
                qs = qs.filter(classroom=student.classroom)
        elif user.role == User.Role.TEACHER:
            teacher = getattr(user, 'teacher_profile', None)
            if teacher:
                qs = qs.filter(teacher=teacher)

        if day:
            qs = qs.filter(day_of_week=day)

        serializer = TimetableSerializer(qs.order_by('day_of_week', 'period_number', 'start_time'), many=True)
        return Response({'status': 'success', 'timetable': serializer.data})


class ExamGradesView(APIView):
    """
    Returns examination scores and report results for student.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role == User.Role.STUDENT:
            student = getattr(user, 'student_profile', None)
            if not student:
                return Response({'status': 'success', 'scores': []})
            scores = Grade.objects.filter(student=student).select_related('exam_term', 'subject').order_by('-exam_term__start_date', 'subject__name')
            serializer = ExamGradeSerializer(scores, many=True)
            return Response({'status': 'success', 'scores': serializer.data})

        return Response({'status': 'success', 'scores': []})


class MobileNotificationListView(APIView):
    """
    Returns in-app notifications for the logged in user.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        logs = MobileNotificationLog.objects.filter(user=request.user).order_by('-sent_at')[:50]
        serializer = MobileNotificationSerializer(logs, many=True)
        unread_count = MobileNotificationLog.objects.filter(user=request.user, is_read=False).count()
        return Response({
            'status': 'success',
            'unread_count': unread_count,
            'notifications': serializer.data
        })

    def post(self, request):
        # Mark all as read
        MobileNotificationLog.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({'status': 'success', 'message': 'All notifications marked as read.'})


class MobileDashboardSummaryView(APIView):
    """
    Provides aggregated dashboard stats for the mobile home screen.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        today = timezone.now().date()

        data = {
            'role': user.role,
            'user_display_name': user.display_name,
            'today': today.strftime('%d-%m-%Y'),
        }

        if user.role == User.Role.TEACHER:
            teacher = getattr(user, 'teacher_profile', None)
            today_att = TeacherAttendance.objects.filter(teacher=teacher, date=today).first() if teacher else None
            classes_count = Timetable.objects.filter(teacher=teacher).values('classroom').distinct().count() if teacher else 0
            today_classes = Timetable.objects.filter(teacher=teacher, day=today.strftime('%a').upper()).count() if teacher else 0

            data['stats'] = {
                'check_in_status': today_att.status if today_att else 'NOT_YET',
                'check_in_time': today_att.check_in_time.strftime('%H:%M') if today_att and today_att.check_in_time else None,
                'total_classes': classes_count,
                'today_classes': today_classes,
            }

        elif user.role == User.Role.STUDENT:
            student = getattr(user, 'student_profile', None)
            today_att = StudentAttendance.objects.filter(student=student, date=today).first() if student else None
            classroom_name = student.classroom.name if student and student.classroom else '-'
            recent_scores = Grade.objects.filter(student=student).order_by('-id')[:5]

            data['stats'] = {
                'classroom': classroom_name,
                'today_attendance': today_att.get_status_display() if today_att else 'មិនទាន់កត់ត្រា',
                'attendance_status_code': today_att.status if today_att else 'NONE',
                'total_exams_recorded': Grade.objects.filter(student=student).count() if student else 0,
            }

        else:
            # Admin stats
            data['stats'] = {
                'total_students': Student.objects.filter(status='ACTIVE').count(),
                'total_teachers': Teacher.objects.filter(status='ACTIVE').count(),
                'today_teacher_attendance': TeacherAttendance.objects.filter(date=today, status='PRESENT').count(),
            }

        return Response({'status': 'success', 'dashboard': data})
