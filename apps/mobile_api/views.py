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
from apps.academics.models import Timetable, Classroom, Subject, AcademicYear, GradeLevelRule
from apps.examinations.models import (
    ExamTerm, Grade, StandardizedExam, ExamSubject, ExamRoom,
    ExamRoomSubjectCode, ExamCandidate, CandidateSubjectScore, ExamStudentExclusion
)
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
            # Flexible multi-field lookup: username, phone, email, teacher_id, student_id
            matched_user = None
            u_obj = User.objects.filter(
                Q(username__iexact=username) | Q(phone=username) | Q(email__iexact=username)
            ).first()
            if u_obj and u_obj.check_password(password):
                matched_user = u_obj

            if not matched_user:
                teacher = Teacher.objects.filter(teacher_id__iexact=username).first()
                if teacher and teacher.user and teacher.user.check_password(password):
                    matched_user = teacher.user

            if not matched_user:
                student = Student.objects.filter(student_id__iexact=username).first()
                if student and student.user and student.user.check_password(password):
                    matched_user = student.user

            # Seamless Demo Role Switcher support (admin, teacher, student, accountant)
            if not matched_user and password in ['admin123', 'p123456']:
                uname_clean = username.lower().strip()
                if uname_clean in ['admin']:
                    matched_user = User.objects.filter(role=User.Role.ADMIN).first()
                elif uname_clean in ['teacher', 'teacher1', 'teachers']:
                    matched_user = User.objects.filter(role=User.Role.TEACHER).first()
                elif uname_clean in ['student', 'student1', 'students']:
                    matched_user = User.objects.filter(role=User.Role.STUDENT).first()
                elif uname_clean in ['accountant', 'finance']:
                    matched_user = User.objects.filter(role=User.Role.ACCOUNTANT).first()

            if matched_user:
                user = matched_user

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


# ==============================================================================
# MOBILE EXAMINATION GRADE ENTRY & BLIND SCORING APIS
# ==============================================================================

class TeacherGradeEntryMetaAPIView(APIView):
    """
    Returns available Exam Terms, Classrooms, and Subjects assigned to the authenticated teacher.
    Respects Admin vs Teacher role isolation and returns grading window status.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        is_admin = user.is_superuser or getattr(user, 'role', '') == 'ADMIN'
        teacher_profile = getattr(user, 'teacher_profile', None) if not is_admin else None

        active_year = AcademicYear.objects.filter(is_current=True).first() or AcademicYear.objects.first()

        terms_qs = ExamTerm.objects.filter(academic_year=active_year) if active_year else ExamTerm.objects.all()
        terms_data = []
        for t in terms_qs:
            is_open, status_code, status_msg = t.get_grading_status()
            terms_data.append({
                'id': t.id,
                'name': t.name,
                'term_type': t.term_type,
                'scoring_mode': t.scoring_mode,
                'start_date': t.start_date.strftime('%Y-%m-%d') if t.start_date else '',
                'end_date': t.end_date.strftime('%Y-%m-%d') if t.end_date else '',
                'grading_start': t.grading_start_datetime.strftime('%d/%m/%Y %H:%M') if t.grading_start_datetime else '',
                'grading_deadline': t.grading_end_datetime.strftime('%d/%m/%Y %H:%M') if t.grading_end_datetime else '',
                'is_grading_open': is_open or is_admin,
                'status_code': status_code,
                'status_message': status_msg,
            })

        # Classrooms & Subjects
        all_classrooms = Classroom.objects.filter(academic_year=active_year) if active_year else Classroom.objects.all()
        teacher_assigned_classes = set()
        teacher_assigned_subjects = set()

        if teacher_profile:
            from apps.academics.models import ClassSubject
            cs_qs = ClassSubject.objects.filter(teacher=teacher_profile)
            if active_year:
                cs_qs = cs_qs.filter(classroom__academic_year=active_year)
            teacher_assigned_classes = set(cs_qs.values_list('classroom_id', flat=True))
            teacher_assigned_subjects = set(cs_qs.values_list('subject_id', flat=True))
            homeroom_cls_ids = set(Classroom.objects.filter(homeroom_teacher=teacher_profile).values_list('id', flat=True))
            teacher_assigned_classes.update(homeroom_cls_ids)
            
            allowed_classrooms = all_classrooms.filter(id__in=teacher_assigned_classes) if teacher_assigned_classes else all_classrooms
        else:
            allowed_classrooms = all_classrooms

        classrooms_data = [
            {
                'id': c.id,
                'name': c.name,
                'grade_level': c.grade_level,
                'track': c.track,
                'track_display': c.get_track_display(),
            }
            for c in allowed_classrooms.order_by('grade_level', 'code')
        ]

        # Standardized Exams for blind scoring
        std_exams_qs = StandardizedExam.objects.filter(academic_year=active_year) if active_year else StandardizedExam.objects.all()
        if not is_admin:
            std_exams_qs = std_exams_qs.filter(is_published=True)

        std_exams_data = []
        for se in std_exams_qs.order_by('-exam_date', '-id'):
            is_open, status_code, status_msg = se.get_grading_status()
            std_exams_data.append({
                'id': se.id,
                'name': se.name,
                'grade_level': se.grade_level,
                'track': se.track,
                'exam_date': se.exam_date.strftime('%Y-%m-%d') if se.exam_date else '',
                'candidates_per_room': se.candidates_per_room,
                'is_grading_open': is_open or is_admin,
                'status_message': status_msg,
            })

        return Response({
            'status': 'success',
            'is_admin': is_admin,
            'exam_terms': terms_data,
            'classrooms': classrooms_data,
            'standardized_exams': std_exams_data,
        })


class TeacherGradeEntrySheetAPIView(APIView):
    """
    Returns student grading sheet for a specific (term, classroom, subject) on mobile.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        term_id = request.query_params.get('term_id')
        classroom_id = request.query_params.get('classroom_id')
        subject_id = request.query_params.get('subject_id')

        if not term_id or not classroom_id:
            return Response({'status': 'error', 'message': 'សូមផ្តល់ term_id និង classroom_id!'}, status=status.HTTP_400_BAD_REQUEST)

        exam_term = get_object_or_404(ExamTerm, id=term_id)
        classroom = get_object_or_404(Classroom, id=classroom_id)
        is_admin = request.user.is_superuser or getattr(request.user, 'role', '') == 'ADMIN'
        teacher_profile = getattr(request.user, 'teacher_profile', None) if not is_admin else None

        # Check grading window
        is_grading_open, status_code, status_msg = exam_term.get_grading_status()

        # Subject rules
        rules_qs = classroom.get_subject_rules()
        if rules_qs.exists():
            subject_rules = list(rules_qs)
        else:
            subject_rules = [GradeLevelRule(grade_level=classroom.grade_level, track=classroom.track, subject=s, max_score=Decimal('100.00')) for s in Subject.objects.all()]

        if subject_id and str(subject_id).isdigit():
            subject_rules = [r for r in subject_rules if r.subject_id == int(subject_id)]

        # Exclusions
        term_month = exam_term.start_date.month if exam_term.start_date else None
        exclusions_qs = ExamStudentExclusion.objects.filter(
            academic_year=exam_term.academic_year,
            is_active=True
        ).filter(
            Q(exam_term=exam_term) | (Q(month=term_month) if term_month else Q())
        )
        excluded_ids = {e.student_id: e.get_reason_display() for e in exclusions_qs}

        students = Student.objects.filter(classroom=classroom).order_by('student_id')
        existing_grades = {
            (g.student_id, g.subject_id): g
            for g in Grade.objects.filter(classroom=classroom, exam_term=exam_term)
        }

        # Check teacher assigned subjects
        teacher_assigned_subjects = set()
        if teacher_profile:
            from apps.academics.models import ClassSubject
            teacher_assigned_subjects = set(ClassSubject.objects.filter(teacher=teacher_profile, classroom=classroom).values_list('subject_id', flat=True))
            if classroom.homeroom_teacher_id == teacher_profile.id:
                teacher_assigned_subjects = {r.subject_id for r in subject_rules}

        subjects_data = []
        for r in subject_rules:
            subjects_data.append({
                'id': r.subject.id,
                'name_kh': r.subject.name_kh,
                'code': r.subject.code,
                'max_score': float(r.max_score),
                'can_edit': (is_admin or is_grading_open) and (is_admin or not teacher_profile or r.subject_id in teacher_assigned_subjects)
            })

        students_data = []
        for st in students:
            is_excluded = (st.id in excluded_ids) or (st.status != 'ACTIVE') or getattr(st, 'is_exam_suspended', False)
            exc_reason = excluded_ids.get(st.id, '')
            if getattr(st, 'is_exam_suspended', False):
                exc_reason = st.get_exam_suspension_reason_display()

            scores_list = []
            for r in subject_rules:
                g = existing_grades.get((st.id, r.subject_id))
                val = float(g.score) if g and g.score is not None else (0.0 if is_excluded else None)
                letter = g.grade_letter if g else ('F' if is_excluded else '-')
                can_edit = (is_admin or is_grading_open) and (is_admin or not is_excluded) and (is_admin or not teacher_profile or r.subject_id in teacher_assigned_subjects)

                scores_list.append({
                    'subject_id': r.subject_id,
                    'subject_name': r.subject.name_kh,
                    'max_score': float(r.max_score),
                    'score': val,
                    'grade_letter': letter,
                    'can_edit': can_edit,
                })

            students_data.append({
                'student_id': st.id,
                'student_code': st.student_id,
                'khmer_name': st.khmer_name,
                'gender': st.gender,
                'is_excluded': is_excluded,
                'exclusion_reason': exc_reason,
                'scores': scores_list,
            })

        return Response({
            'status': 'success',
            'term': {
                'id': exam_term.id,
                'name': exam_term.name,
                'is_grading_open': is_grading_open or is_admin,
                'status_message': status_msg,
            },
            'classroom': {
                'id': classroom.id,
                'name': classroom.name,
                'total_students': len(students_data),
            },
            'subjects': subjects_data,
            'students': students_data,
        })


class TeacherGradeEntrySaveAPIView(APIView):
    """
    Saves student scores submitted via Mobile App.
    Payload:
    {
        "term_id": 1,
        "classroom_id": 2,
        "scores": [
            {"student_id": 10, "subject_id": 3, "score": 45.5, "is_absent": false}
        ]
    }
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        data = request.data
        term_id = data.get('term_id')
        classroom_id = data.get('classroom_id')
        scores_list = data.get('scores', [])

        if not term_id or not classroom_id or not scores_list:
            return Response({'status': 'error', 'message': 'ទិន្នន័យមិនពេញលេញ!'}, status=status.HTTP_400_BAD_REQUEST)

        exam_term = get_object_or_404(ExamTerm, id=term_id)
        classroom = get_object_or_404(Classroom, id=classroom_id)
        is_admin = request.user.is_superuser or getattr(request.user, 'role', '') == 'ADMIN'
        teacher_profile = getattr(request.user, 'teacher_profile', None) if not is_admin else None

        # Check grading window
        is_grading_open, _, status_msg = exam_term.get_grading_status()
        if not is_grading_open and not is_admin:
            return Response({'status': 'error', 'message': f'⚠️ មិនអាចរក្សាទុកបានទេ៖ {status_msg}!'}, status=status.HTTP_403_FORBIDDEN)

        # Pre-cache max scores
        rules_map = {r.subject_id: r.max_score for r in classroom.get_subject_rules()}

        # Teacher assigned subjects
        teacher_assigned_subjects = set()
        if teacher_profile:
            from apps.academics.models import ClassSubject
            teacher_assigned_subjects = set(ClassSubject.objects.filter(teacher=teacher_profile, classroom=classroom).values_list('subject_id', flat=True))
            if classroom.homeroom_teacher_id == teacher_profile.id:
                teacher_assigned_subjects = set(rules_map.keys())

        # Exclusions map
        term_month = exam_term.start_date.month if exam_term.start_date else None
        exclusions_qs = ExamStudentExclusion.objects.filter(
            academic_year=exam_term.academic_year,
            is_active=True
        ).filter(
            Q(exam_term=exam_term) | (Q(month=term_month) if term_month else Q())
        )
        excluded_ids = set(exclusions_qs.values_list('student_id', flat=True))

        saved_count = 0
        with transaction.atomic():
            for item in scores_list:
                st_id = item.get('student_id')
                sub_id = item.get('subject_id')
                score_raw = str(item.get('score', '')).strip().upper()
                is_absent = bool(item.get('is_absent', False)) or (score_raw == 'A')

                if not st_id or not sub_id:
                    continue

                # Non-admin teacher can only save assigned subjects
                if teacher_profile and sub_id not in teacher_assigned_subjects and not is_admin:
                    continue

                # Excluded student positive score blocked for non-admin
                if (st_id in excluded_ids) and not is_admin:
                    continue

                student = Student.objects.filter(id=st_id, classroom=classroom).first()
                subject = Subject.objects.filter(id=sub_id).first()
                if not student or not subject:
                    continue

                max_sc = rules_map.get(sub_id, Decimal('100.00'))

                if is_absent:
                    score_num = Decimal('0.00')
                elif score_raw != '' and score_raw != '-':
                    try:
                        score_num = Decimal(score_raw)
                        if score_num > max_sc:
                            score_num = max_sc
                        if score_num < Decimal('0.00'):
                            score_num = Decimal('0.00')
                    except Exception:
                        continue
                else:
                    continue

                Grade.objects.update_or_create(
                    student=student,
                    subject=subject,
                    exam_term=exam_term,
                    classroom=classroom,
                    defaults={
                        'score': score_num,
                        'max_score': max_sc,
                    }
                )
                saved_count += 1

        return Response({
            'status': 'success',
            'message': f'🎉 បានរក្សាទុកពិន្ទុចំនួន {saved_count} ជោគជ័យ!',
            'saved_count': saved_count
        })


class MobileBlindScoringValidateAPIView(APIView):
    """
    Validates Secret Code on Mobile App and returns anonymous desk list (Desks 01 to N).
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        data = request.data
        exam_id = data.get('exam_id')
        subject_id = data.get('subject_id')
        secret_code = str(data.get('secret_code', '')).strip().upper()

        if not exam_id or not subject_id or not secret_code:
            return Response({'status': 'error', 'message': 'សូមជ្រើសរើសសម័យប្រឡង មុខវិជ្ជា និងលេខកូដសម្ងាត់!'}, status=status.HTTP_400_BAD_REQUEST)

        exam = get_object_or_404(StandardizedExam, id=exam_id)
        exam_subject = get_object_or_404(ExamSubject.objects.select_related('subject'), id=subject_id, exam=exam)
        is_admin = request.user.is_superuser or getattr(request.user, 'role', '') == 'ADMIN'

        # Check grading window
        is_grading_open, _, grading_msg = exam.get_grading_status()

        code_obj = ExamRoomSubjectCode.objects.filter(
            secret_code__iexact=secret_code,
            exam_subject=exam_subject
        ).select_related('exam_room').first()

        room = code_obj.exam_room if code_obj else ExamRoom.objects.filter(exam=exam, secret_code__iexact=secret_code).first()
        if not room:
            return Response({
                'status': 'error',
                'message': f'លេខកូដសម្ងាត់ «{secret_code}» មិនត្រឹមត្រូវ ឬមិនត្រូវគ្នានឹងមុខវិជ្ជា {exam_subject.subject.name_kh} ឡើយ!'
            }, status=status.HTTP_404_NOT_FOUND)

        candidates = room.candidates.all().order_by('desk_number', 'id')
        scores_map = {
            sc.candidate_id: sc
            for sc in CandidateSubjectScore.objects.filter(candidate__in=candidates, exam_subject=exam_subject)
        }

        desks_data = []
        for cand in candidates:
            sc = scores_map.get(cand.id)
            score_val = None
            is_absent = False
            if sc:
                is_absent = sc.is_absent
                if sc.score is not None and not is_absent:
                    score_val = float(sc.score)

            desks_data.append({
                'desk_number': cand.desk_number,
                'candidate_id': cand.id,
                'score': score_val,
                'is_absent': is_absent,
            })

        display_room_name = room.room_name if is_admin else f"កញ្ចប់កូដសម្ងាត់ #{secret_code}"

        return Response({
            'status': 'success',
            'room_id': room.id,
            'room_name': display_room_name,
            'is_blind_mode': not is_admin,
            'is_grading_open': is_grading_open or is_admin,
            'grading_status_msg': grading_msg,
            'subject_id': exam_subject.id,
            'subject_name': exam_subject.subject.name_kh,
            'max_score': float(exam_subject.max_score),
            'coefficient': float(exam_subject.coefficient),
            'candidate_count': len(desks_data),
            'is_already_graded': code_obj.is_graded if code_obj else False,
            'desks': desks_data
        })


class MobileBlindScoringSaveAPIView(APIView):
    """
    Saves scores submitted blindly via Mobile App by desk number (01 to N).
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        data = request.data
        exam_id = data.get('exam_id')
        subject_id = data.get('subject_id')
        secret_code = str(data.get('secret_code', '')).strip().upper()
        scores_list = data.get('scores', [])

        if not exam_id or not subject_id or not secret_code or not scores_list:
            return Response({'status': 'error', 'message': 'ទិន្នន័យមិនពេញលេញ!'}, status=status.HTTP_400_BAD_REQUEST)

        exam = get_object_or_404(StandardizedExam, id=exam_id)
        exam_subject = get_object_or_404(ExamSubject.objects.select_related('subject'), id=subject_id, exam=exam)
        is_admin = request.user.is_superuser or getattr(request.user, 'role', '') == 'ADMIN'

        # Check grading window
        is_grading_open, _, grading_msg = exam.get_grading_status()
        if not is_grading_open and not is_admin:
            return Response({'status': 'error', 'message': f'⚠️ មិនអាចរក្សាទុកបានទេ៖ {grading_msg}!'}, status=status.HTTP_403_FORBIDDEN)

        code_obj = ExamRoomSubjectCode.objects.filter(
            secret_code__iexact=secret_code,
            exam_subject=exam_subject
        ).select_related('exam_room').first()

        room = code_obj.exam_room if code_obj else ExamRoom.objects.filter(exam=exam, secret_code__iexact=secret_code).first()
        if not room:
            return Response({'status': 'error', 'message': 'លេខកូដសម្ងាត់មិនត្រឹមត្រូវ!'}, status=status.HTTP_404_NOT_FOUND)

        candidates_by_desk = {c.desk_number: c for c in room.candidates.all()}
        saved_count = 0
        absent_count = 0

        with transaction.atomic():
            for item in scores_list:
                desk_num = int(item.get('desk_number', 0))
                score_raw = str(item.get('score', '')).strip().upper()
                is_absent = bool(item.get('is_absent', False)) or (score_raw == 'A')

                cand = candidates_by_desk.get(desk_num)
                if not cand:
                    continue

                score_obj, _ = CandidateSubjectScore.objects.get_or_create(
                    candidate=cand,
                    exam_subject=exam_subject
                )

                if is_absent:
                    score_obj.is_absent = True
                    score_obj.score = Decimal('0.00')
                    absent_count += 1
                elif score_raw != '' and score_raw != '-':
                    try:
                        val = Decimal(score_raw)
                        if val > exam_subject.max_score:
                            val = exam_subject.max_score
                        if val < Decimal('0.00'):
                            val = Decimal('0.00')
                        score_obj.score = val
                        score_obj.is_absent = False
                    except Exception:
                        continue
                else:
                    continue

                if not score_obj.entered_by:
                    score_obj.entered_by = request.user
                if not score_obj.entered_at:
                    score_obj.entered_at = timezone.now()
                score_obj.secret_code_used = secret_code
                score_obj.last_modified_by = request.user

                score_obj.save()
                saved_count += 1

            if code_obj:
                code_obj.is_graded = True
                code_obj.graded_by = request.user
                code_obj.graded_at = timezone.now()
                code_obj.save(update_fields=['is_graded', 'graded_by', 'graded_at'])

            exam.recalculate_all_ranks()

        return Response({
            'status': 'success',
            'message': f'🎉 បានរក្សាទុកពិន្ទុកញ្ចប់ {secret_code} ចំនួន {saved_count} តុជោគជ័យ!',
            'saved_count': saved_count,
            'absent_count': absent_count
        })


# =========================================================================
# 7. Administrative Locations API (ខេត្ត ស្រុក ឃុំ ភូមិ Cascading Dropdowns)
# =========================================================================

def _mobile_location_sort_key(x):
    code_str = str(x.get('code') or '').strip()
    try:
        return (0, int(code_str), code_str)
    except ValueError:
        return (1, 0, code_str)


class MobileLocationProvincesAPIView(APIView):
    """
    Mobile API: Returns list of all 25 Provinces / Cities in Cambodia.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from apps.academics.models import Province
        provinces = list(Province.objects.all().values('id', 'code', 'name_kh', 'name_en'))
        provinces.sort(key=_mobile_location_sort_key)
        return Response({
            'status': 'success',
            'count': len(provinces),
            'data': provinces
        })


class MobileLocationDistrictsAPIView(APIView):
    """
    Mobile API: Returns districts filtered by province_id (or province code).
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from apps.academics.models import District
        province_id = request.GET.get('province_id')
        districts = District.objects.all()
        if province_id:
            districts = districts.filter(province_id=province_id)
        data = list(districts.values('id', 'code', 'name_kh', 'name_en', 'province_id'))
        data.sort(key=_mobile_location_sort_key)
        return Response({
            'status': 'success',
            'count': len(data),
            'data': data
        })


class MobileLocationCommunesAPIView(APIView):
    """
    Mobile API: Returns communes filtered by district_id.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from apps.academics.models import Commune
        district_id = request.GET.get('district_id')
        communes = Commune.objects.all()
        if district_id:
            communes = communes.filter(district_id=district_id)
        data = list(communes.values('id', 'code', 'name_kh', 'name_en', 'district_id'))
        data.sort(key=_mobile_location_sort_key)
        return Response({
            'status': 'success',
            'count': len(data),
            'data': data
        })


class MobileLocationVillagesAPIView(APIView):
    """
    Mobile API: Returns villages filtered by commune_id.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from apps.academics.models import Village
        commune_id = request.GET.get('commune_id')
        villages = Village.objects.all()
        if commune_id:
            villages = villages.filter(commune_id=commune_id)
        data = list(villages.values('id', 'code', 'name_kh', 'name_en', 'commune_id'))
        data.sort(key=_mobile_location_sort_key)
        return Response({
            'status': 'success',
            'count': len(data),
            'data': data
        })


class MobileLocationHierarchyAPIView(APIView):
    """
    Mobile API: Returns a lightweight hierarchy of provinces and districts (or full tree)
    for mobile apps to cache locally for instant, offline-capable cascading dropdowns.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from apps.academics.models import Province, District
        provinces = list(Province.objects.all().prefetch_related('districts').order_by('id'))
        tree = []
        for p in provinces:
            districts = [
                {'id': d.id, 'code': d.code, 'name_kh': d.name_kh, 'name_en': d.name_en}
                for d in p.districts.all()
            ]
            districts.sort(key=_mobile_location_sort_key)
            tree.append({
                'id': p.id,
                'code': p.code,
                'name_kh': p.name_kh,
                'name_en': p.name_en,
                'districts': districts
            })
        tree.sort(key=_mobile_location_sort_key)
        return Response({
            'status': 'success',
            'count': len(tree),
            'data': tree
        })


# =========================================================================
# 8. Student Promotion & Grade Retention APIs (ឡើងថ្នាក់ & ត្រួតថ្នាក់)
# =========================================================================

class MobileStudentPromotionMetaAPIView(APIView):
    """
    Mobile API: Returns metadata for Student Promotion:
    - Allowed source classrooms for current user
    - Target academic years
    - Available target classrooms
    - MoEYS standard promotion reasons & actions
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from apps.students.models import StudentPromotionRecord
        from apps.academics.models import ClassSubject

        is_admin = request.user.is_superuser or getattr(request.user, 'role', '') == 'ADMIN'
        teacher_profile = Teacher.objects.filter(user=request.user).first() if not is_admin else None

        if not is_admin and not teacher_profile:
            return Response({
                'status': 'error',
                'message': 'អ្នកមិនមានសិទ្ធិចាត់ចែងការឡើងថ្នាក់/ត្រួតថ្នាក់សិស្សឡើយ!'
            }, status=status.HTTP_403_FORBIDDEN)

        if not is_admin:
            taught_cids = set(ClassSubject.objects.filter(teacher=teacher_profile).values_list('classroom_id', flat=True))
            if hasattr(Classroom, 'teacher'):
                taught_cids.update(Classroom.objects.filter(teacher=teacher_profile).values_list('id', flat=True))
            source_classes = Classroom.objects.filter(id__in=taught_cids).select_related('academic_year')
        else:
            source_classes = Classroom.objects.all().select_related('academic_year')

        source_classes_data = [
            {
                'id': c.id,
                'name': c.name,
                'grade_level': c.grade_level,
                'academic_year_id': c.academic_year_id,
                'academic_year_name': c.academic_year.name if c.academic_year else '',
                'student_count': c.students.filter(status='ACTIVE').count()
            }
            for c in source_classes
        ]

        target_years_data = [
            {
                'id': y.id,
                'name': y.name,
                'is_current': y.is_current
            }
            for y in AcademicYear.objects.all().order_by('-start_date')
        ]

        all_target_classes_data = [
            {
                'id': c.id,
                'name': c.name,
                'grade_level': c.grade_level,
                'academic_year_id': c.academic_year_id,
                'academic_year_name': c.academic_year.name if c.academic_year else ''
            }
            for c in Classroom.objects.all().select_related('academic_year').order_by('grade_level', 'name')
        ]

        reasons_data = [
            {'code': code, 'label': label}
            for code, label in StudentPromotionRecord.StandardReason.choices
        ]

        actions_data = [
            {'code': code, 'label': label}
            for code, label in StudentPromotionRecord.Action.choices
        ]

        return Response({
            'status': 'success',
            'is_admin': is_admin,
            'source_classrooms': source_classes_data,
            'target_academic_years': target_years_data,
            'all_target_classrooms': all_target_classes_data,
            'standard_reasons': reasons_data,
            'actions': actions_data
        })


class MobileStudentPromotionClassStudentsAPIView(APIView):
    """
    Mobile API: Returns the active students of a source class for promotion decisions.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        source_class_id = request.GET.get('source_class_id')
        if not source_class_id:
            return Response({'status': 'error', 'message': 'source_class_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        classroom = get_object_or_404(Classroom, id=source_class_id)
        students = Student.objects.filter(classroom=classroom, status='ACTIVE').order_by('student_id')

        students_data = [
            {
                'id': s.id,
                'student_id': s.student_id,
                'khmer_name': s.khmer_name,
                'latin_name': s.latin_name,
                'gender': s.gender,
                'gender_display': s.get_gender_display(),
                'status': s.status,
                'status_display': s.get_status_display(),
                'is_repeating_grade': s.is_repeating_grade,
                'last_promotion_status': s.last_promotion_status or '',
                'last_promotion_reason': s.last_promotion_reason or '',
                'default_action': 'PROMOTE',
                'default_reason': 'PASSED_YEAR'
            }
            for s in students
        ]

        return Response({
            'status': 'success',
            'classroom_id': classroom.id,
            'classroom_name': classroom.name,
            'academic_year': classroom.academic_year.name if classroom.academic_year else '',
            'student_count': len(students_data),
            'students': students_data
        })


class MobileStudentPromotionSubmitAPIView(APIView):
    """
    Mobile API: Submits individual student promotion & grade retention decisions.
    Payload:
    {
      "source_class_id": 1,
      "target_year_id": 2,
      "students": [
         {
           "student_id": 10,
           "action": "PROMOTE" | "RETAIN" | "GRADUATE" | "TRANSFER" | "DROP",
           "target_class_id": 15,
           "standard_reason": "PASSED_YEAR" | "FAILED_YEAR" | ...,
           "custom_notes": "optional notes"
         }
      ]
    }
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from apps.students.models import StudentPromotionRecord

        data = request.data
        source_class_id = data.get('source_class_id')
        target_year_id = data.get('target_year_id')
        students_payload = data.get('students', [])

        if not source_class_id or not students_payload:
            return Response({
                'status': 'error',
                'message': 'ទិន្នន័យមិនពេញលេញ! source_class_id និងបញ្ជីសិស្សត្រូវតែបញ្ជាក់។'
            }, status=status.HTTP_400_BAD_REQUEST)

        source_class = get_object_or_404(Classroom, id=source_class_id)
        target_year = AcademicYear.objects.filter(id=target_year_id).first() if target_year_id else source_class.academic_year

        is_admin = request.user.is_superuser or getattr(request.user, 'role', '') == 'ADMIN'
        if not is_admin:
            teacher_profile = Teacher.objects.filter(user=request.user).first()
            if not teacher_profile:
                return Response({'status': 'error', 'message': 'គ្មានសិទ្ធិអនុវត្ត!'}, status=status.HTTP_403_FORBIDDEN)

        promoted_count = 0
        retained_count = 0
        other_count = 0

        with transaction.atomic():
            for item in students_payload:
                s_id = item.get('student_id')
                action = item.get('action', 'PROMOTE')
                target_cid = item.get('target_class_id')
                standard_reason = item.get('standard_reason', 'PASSED_YEAR')
                custom_notes = str(item.get('custom_notes', '')).strip()

                student = Student.objects.filter(id=s_id, classroom=source_class).first()
                if not student:
                    continue

                target_cls = Classroom.objects.filter(id=target_cid).first() if target_cid else None
                old_class = student.classroom
                old_year = student.academic_year

                reason_display = dict(StudentPromotionRecord.StandardReason.choices).get(standard_reason, standard_reason)
                full_reason = f"{reason_display}" + (f" ({custom_notes})" if custom_notes else "")

                if action == 'PROMOTE':
                    student.academic_year = target_year or old_year
                    if target_cls:
                        student.classroom = target_cls
                    student.status = 'ACTIVE'
                    student.is_repeating_grade = False
                    student.last_promotion_status = 'ឡើងថ្នាក់'
                    student.last_promotion_reason = full_reason
                    student.save()
                    promoted_count += 1

                elif action == 'RETAIN':
                    student.academic_year = target_year or old_year
                    if target_cls:
                        student.classroom = target_cls
                    student.status = 'ACTIVE'
                    student.is_repeating_grade = True
                    student.last_promotion_status = 'ត្រួតថ្នាក់'
                    student.last_promotion_reason = full_reason
                    student.save()
                    retained_count += 1

                elif action == 'GRADUATE':
                    student.status = 'GRADUATED'
                    student.is_repeating_grade = False
                    student.last_promotion_status = 'បញ្ចប់ការសិក្សា'
                    student.last_promotion_reason = full_reason
                    student.save()
                    other_count += 1

                elif action == 'TRANSFER':
                    student.status = 'TRANSFERRED'
                    student.last_promotion_status = 'ផ្ទេរចេញ'
                    student.last_promotion_reason = full_reason
                    student.save()
                    other_count += 1

                elif action == 'DROP':
                    student.status = 'DROPPED'
                    student.last_promotion_status = 'ឈប់រៀន'
                    student.last_promotion_reason = full_reason
                    student.save()
                    other_count += 1

                # Record Promotion Audit
                StudentPromotionRecord.objects.create(
                    student=student,
                    from_academic_year=old_year,
                    to_academic_year=target_year or old_year,
                    from_classroom=old_class,
                    to_classroom=target_cls,
                    action=action,
                    standard_reason=standard_reason,
                    custom_notes=custom_notes,
                    processed_by=request.user
                )

        total_done = promoted_count + retained_count + other_count
        return Response({
            'status': 'success',
            'message': f'🎉 បានដំណើរការឡើងថ្នាក់/ត្រួតថ្នាក់សិស្សចំនួន {total_done} នាក់ជោគជ័យ!',
            'total_processed': total_done,
            'promoted_count': promoted_count,
            'retained_count': retained_count,
            'other_count': other_count
        })


