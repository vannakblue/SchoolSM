import datetime
from datetime import time as dtime
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
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


class AssemblyAttendanceAPIView(APIView):
    """
    Mobile API for Pre-Class Morning Assembly / Flag Ceremony Attendance.
    Used by Class Monitors, Vice Monitors, Homeroom Teachers, and Admin on the Mobile App!
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        now_dt = timezone.localtime(timezone.now())
        current_time = now_dt.time()
        today_date = now_dt.date()

        from apps.attendance.models import AttendanceSetting, StudentAttendance
        from apps.academics.utils import get_active_academic_year
        active_year = get_active_academic_year(request)
        att_settings = AttendanceSetting.get_settings()

        student_profile = getattr(user, 'student_profile', None)
        teacher_profile = getattr(user, 'teacher_profile', None)

        authorized_classrooms = Classroom.objects.none()
        is_monitor = False
        is_vice_monitor = False

        if user.role == 'ADMIN' or user.is_superuser:
            authorized_classrooms = Classroom.objects.filter(academic_year=active_year).order_by('grade_level', 'code') if active_year else Classroom.objects.all().order_by('grade_level', 'code')
        elif user.role == 'TEACHER' and teacher_profile:
            if att_settings.allow_all_teachers_assembly_recording:
                authorized_classrooms = Classroom.objects.filter(academic_year=active_year).order_by('grade_level', 'code') if active_year else Classroom.objects.all().order_by('grade_level', 'code')
            else:
                duty_classes = Classroom.objects.filter(
                    Q(homeroom_teacher=teacher_profile) | Q(assembly_duty_teacher=teacher_profile),
                    academic_year=active_year
                ).order_by('grade_level', 'code')
                if duty_classes.exists():
                    authorized_classrooms = duty_classes
                else:
                    authorized_classrooms = Classroom.objects.filter(academic_year=active_year).order_by('grade_level', 'code') if active_year else Classroom.objects.all().order_by('grade_level', 'code')
        elif student_profile:
            monitor_classes = Classroom.objects.filter(
                Q(class_monitor=student_profile) | Q(vice_monitor=student_profile),
                academic_year=active_year
            )
            if monitor_classes.exists():
                authorized_classrooms = monitor_classes
                matched_cls = monitor_classes.first()
                if matched_cls.class_monitor_id == student_profile.id:
                    is_monitor = True
                else:
                    is_vice_monitor = True

        if not authorized_classrooms.exists():
            return Response({
                'status': 'error',
                'message': 'លោកអ្នកមិនមានសិទ្ធិជាប្រធានថ្នាក់ អនុប្រធានថ្នាក់ ឬគ្រូបង្រៀនសម្រាប់ស្រង់វត្តមានពេលគោរពទង់ជាតិឡើយ!'
            }, status=status.HTTP_403_FORBIDDEN)

        class_id = request.query_params.get('classroom_id')
        selected_class = authorized_classrooms.filter(id=class_id).first() if class_id else authorized_classrooms.first()

        req_session = request.query_params.get('session')
        selected_session = req_session if req_session in ['MORNING', 'AFTERNOON'] else 'MORNING'

        # Time Window
        m_start = att_settings.assembly_morning_start or dtime(6, 30)
        m_end = att_settings.assembly_morning_end or dtime(6, 50)
        a_start = att_settings.assembly_afternoon_start or dtime(12, 30)
        a_end = att_settings.assembly_afternoon_end or dtime(12, 50)

        window_start = m_start if selected_session == 'MORNING' else a_start
        window_end = m_end if selected_session == 'MORNING' else a_end
        is_within_window = (window_start <= current_time <= window_end)
        # Day of Week & Emergency Cancellation Check
        today_weekday_str = str(today_date.isoweekday())
        is_active_day = today_weekday_str in (att_settings.assembly_active_days or ["1", "2", "3", "4", "5", "6"])
        is_cancelled_today = att_settings.is_assembly_disabled_today and (att_settings.assembly_disabled_date == today_date or not att_settings.assembly_disabled_date)
        is_disabled_today = (not is_active_day) or is_cancelled_today or (not att_settings.enable_assembly_attendance)
        
        disabled_reason = ""
        if not att_settings.enable_assembly_attendance:
            disabled_reason = "ប្រព័ន្ធស្រង់វត្តមានពេលគោរពទង់ជាតិត្រូវបានបិទដំណើរការជាបណ្តោះអាសន្ន។"
        elif is_cancelled_today:
            disabled_reason = att_settings.assembly_disabled_reason or "គណៈគ្រប់គ្រងសាលាបានសម្រេចផ្អាកការស្រង់វត្តមានពេលគោរពទង់ជាតិសម្រាប់ថ្ងៃនេះ។"
        elif not is_active_day:
            disabled_reason = "ថ្ងៃនេះមិនមែនជាថ្ងៃដែលត្រូវស្រង់វត្តមានពេលគោរពទង់ជាតិនោះឡើយ។"

        remaining_minutes = 0
        if is_within_window:
            end_dt = datetime.datetime.combine(today_date, window_end)
            curr_dt = datetime.datetime.combine(today_date, current_time)
            remaining_minutes = max(0, int((end_dt - curr_dt).total_seconds() // 60))

        alarm_active = False
        if att_settings.assembly_last_alarm_sent:
            alarm_diff = (now_dt - att_settings.assembly_last_alarm_sent).total_seconds()
            if alarm_diff < 3600:
                alarm_active = True

        students = Student.objects.filter(classroom=selected_class, status='ACTIVE').order_by('khmer_name') if selected_class else []
        existing_records = {}
        if selected_class:
            recs = StudentAttendance.objects.filter(classroom=selected_class, date=today_date, session=selected_session, period_number=0)
            for r in recs:
                existing_records[r.student_id] = {'status': r.status, 'notes': r.notes or ''}

        student_list = []
        for st in students:
            rec = existing_records.get(st.id)
            student_list.append({
                'id': st.id,
                'student_id': st.student_id,
                'name': st.khmer_name,
                'gender': st.gender,
                'photo': st.photo.url if st.photo else None,
                'status': rec['status'] if rec else 'PRESENT',
                'notes': rec['notes'] if rec else ''
            })

        classrooms_list = [{'id': c.id, 'name': c.name, 'code': c.code, 'total_students': c.total_students} for c in authorized_classrooms]

        return Response({
            'status': 'success',
            'today': today_date.strftime('%Y-%m-%d'),
            'session': selected_session,
            'window_start': window_start.strftime('%H:%M'),
            'window_end': window_end.strftime('%H:%M'),
            'is_open': (is_within_window and not is_disabled_today) or is_admin,
            'enable_assembly_morning': att_settings.enable_assembly_morning,
            'enable_assembly_afternoon': att_settings.enable_assembly_afternoon,
            'is_disabled_today': is_disabled_today,
            'disabled_reason': disabled_reason,
            'remaining_minutes': remaining_minutes,
            'alarm_active': alarm_active,
            'alarm_message': att_settings.assembly_alarm_message,
            'is_monitor': is_monitor,
            'is_vice_monitor': is_vice_monitor,
            'selected_classroom': {'id': selected_class.id, 'name': selected_class.name} if selected_class else None,
            'classrooms': classrooms_list,
            'students': student_list,
        })

    def post(self, request):
        user = request.user
        now_dt = timezone.localtime(timezone.now())
        current_time = now_dt.time()
        today_date = now_dt.date()

        from apps.attendance.models import AttendanceSetting, StudentAttendance, AttendanceSubmissionLog
        att_settings = AttendanceSetting.get_settings()

        classroom_id = request.data.get('classroom_id')
        session_val = request.data.get('session') or 'MORNING'
        attendances_data = request.data.get('attendances') or []

        classroom = Classroom.objects.filter(id=classroom_id).first()
        if not classroom:
            return Response({'status': 'error', 'message': 'រកមិនឃើញថ្នាក់រៀនឡើយ!'}, status=status.HTTP_404_NOT_FOUND)

        # Permissions check
        student_profile = getattr(user, 'student_profile', None)
        teacher_profile = getattr(user, 'teacher_profile', None)
        is_admin = (user.role == 'ADMIN' or user.is_superuser)
        is_homeroom = (classroom.homeroom_teacher_id == getattr(teacher_profile, 'id', None))
        is_duty_teacher = (getattr(classroom, 'assembly_duty_teacher_id', None) == getattr(teacher_profile, 'id', None))
        is_teacher_allowed = (user.role == 'TEACHER' and (att_settings.allow_all_teachers_assembly_recording or is_homeroom or is_duty_teacher))
        is_monitor = (classroom.class_monitor_id == getattr(student_profile, 'id', None) or classroom.vice_monitor_id == getattr(student_profile, 'id', None))

        if not (is_admin or is_teacher_allowed or is_monitor):
            return Response({'status': 'error', 'message': 'លោកអ្នកគ្មានសិទ្ធិស្រង់វត្តមានថ្នាក់នេះឡើយ!'}, status=status.HTTP_403_FORBIDDEN)

        # Time Window check
        m_start = att_settings.assembly_morning_start or dtime(6, 30)
        m_end = att_settings.assembly_morning_end or dtime(6, 50)
        a_start = att_settings.assembly_afternoon_start or dtime(12, 30)
        a_end = att_settings.assembly_afternoon_end or dtime(12, 50)
        window_start = m_start if session_val == 'MORNING' else a_start
        window_end = m_end if session_val == 'MORNING' else a_end
        is_within_window = (window_start <= current_time <= window_end)

        if not is_within_window and not is_admin:
            return Response({
                'status': 'error',
                'message': f'ផុតម៉ោងកំណត់ស្រង់វត្តមានពេលគោរពទង់ជាតិហើយ! ({window_start.strftime("%H:%M")} - {window_end.strftime("%H:%M")})'
            }, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            StudentAttendance.objects.filter(
                classroom=classroom,
                date=today_date,
                session=session_val,
                period_number=0
            ).delete()

            new_records = []
            for item in attendances_data:
                st_id = item.get('student_id')
                status_code = item.get('status')
                notes_text = item.get('notes', '')

                if status_code in ['ABSENT', 'PERMISSION', 'LATE']:
                    student_obj = Student.objects.filter(id=st_id, classroom=classroom).first()
                    if student_obj:
                        new_records.append(StudentAttendance(
                            student=student_obj,
                            classroom=classroom,
                            date=today_date,
                            session=session_val,
                            period_number=0,
                            status=status_code,
                            notes=notes_text or 'វត្តមានពេលគោរពទង់ជាតិ (Mobile App)',
                            recorded_by=user
                        ))

            if new_records:
                StudentAttendance.objects.bulk_create(new_records)

            AttendanceSubmissionLog.objects.update_or_create(
                classroom=classroom,
                date=today_date,
                session=session_val,
                period_number=0,
                defaults={'recorded_by': user}
            )

        return Response({
            'status': 'success',
            'message': f'បានរក្សាទុកវត្តមានពេលគោរពទង់ជាតិ ({classroom.name}) ជោគជ័យ!',
            'absent_records_count': len(new_records)
        })

