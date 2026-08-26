import io
import csv
import json
import math
import time
import hmac
import hashlib
from datetime import datetime, date, timedelta, time as dtime
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.core.files.base import ContentFile
from django.db.models import Q

from django.utils import timezone
from apps.accounts.decorators import role_required
from apps.accounts.models import User, SchoolProfile
from .models import (
    Teacher,
    TeacherAttendance,
    TeacherBiometricProfile,
    TeacherPunchLog,
    TeacherAttendanceConfig
)
from apps.academics.utils import get_active_academic_year



# ---------------------------------------------------------------------------
# Security & Calculation Helpers
# ---------------------------------------------------------------------------

def calculate_haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculates great-circle distance between two GPS coordinates in meters.
    """
    if None in (lat1, lon1, lat2, lon2):
        return 0.0
    R = 6371000.0 # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(R * c, 2)


def generate_rolling_qr_token(config=None):
    """
    Generates a time-synced dynamic cryptographic token that rotates every interval seconds.
    """
    if config is None:
        config = TeacherAttendanceConfig.get_settings()
    interval = config.rolling_qr_interval_seconds or 20
    current_step = int(time.time() // interval)
    secret = (config.biometric_push_secret or settings.SECRET_KEY).encode('utf-8')
    raw_msg = f"SCHOOLSM_QR_KIOSK_{current_step}".encode('utf-8')
    token_hash = hmac.new(secret, raw_msg, hashlib.sha256).hexdigest()[:16]
    expires_in = interval - int(time.time() % interval)
    return f"QR_{current_step}_{token_hash}", expires_in


def verify_rolling_qr_token(token, config=None):
    """
    Verifies if a token matches the current or previous step (allowing small network lag).
    """
    if not token or not token.startswith("QR_"):
        return False
    if config is None:
        config = TeacherAttendanceConfig.get_settings()
    interval = config.rolling_qr_interval_seconds or 20
    current_step = int(time.time() // interval)
    secret = (config.biometric_push_secret or settings.SECRET_KEY).encode('utf-8')

    # Allow current step and immediate previous step (grace period of 1 interval)
    for step in [current_step, current_step - 1]:
        raw_msg = f"SCHOOLSM_QR_KIOSK_{step}".encode('utf-8')
        expected_hash = hmac.new(secret, raw_msg, hashlib.sha256).hexdigest()[:16]
        expected_token = f"QR_{step}_{expected_hash}"
        if token == expected_token:
            return True
    return False


def record_teacher_punch(
    teacher,
    method,
    punch_type='CHECK_IN',
    punch_dt=None,
    gps_lat=None,
    gps_lng=None,
    device_uuid=None,
    ip_address=None,
    snapshot_data_url=None,
    notes=None,
    raw_payload=None
):
    """
    Core function to record a punch log, evaluate status (On-Time / Late),
    and sync/update the daily TeacherAttendance database record.
    """
    if punch_dt is None:
        punch_dt = timezone.now()
    elif timezone.is_naive(punch_dt):
        punch_dt = timezone.make_aware(punch_dt)
    
    punch_date = timezone.localdate(punch_dt)
    punch_time = timezone.localtime(punch_dt).time()
    config = TeacherAttendanceConfig.get_settings()
    school_profile = SchoolProfile.get_settings()


    # 1. Geofence evaluation
    is_within_geofence = True
    if config.require_gps_validation and gps_lat and gps_lng and school_profile.latitude and school_profile.longitude:
        dist = calculate_haversine_distance(gps_lat, gps_lng, school_profile.latitude, school_profile.longitude)
        radius = school_profile.gps_radius_meters or 100
        if dist > radius:
            is_within_geofence = False

    # 2. Timing and Shift status evaluation (Late / On Time)
    status_result = TeacherPunchLog.StatusResult.ON_TIME
    is_late = False
    late_minutes = 0

    # Determine shift (Morning vs Afternoon)
    if punch_time < dtime(12, 0): # Morning Shift
        late_threshold = config.morning_late_threshold or dtime(7, 15)
        if punch_time > late_threshold:
            status_result = TeacherPunchLog.StatusResult.LATE
            is_late = True
            t1 = datetime.combine(punch_date, punch_time)
            t2 = datetime.combine(punch_date, late_threshold)
            late_minutes = int((t1 - t2).total_seconds() // 60)
    else: # Afternoon Shift
        late_threshold = config.afternoon_late_threshold or dtime(13, 15)
        if punch_time > late_threshold:
            status_result = TeacherPunchLog.StatusResult.LATE
            is_late = True
            t1 = datetime.combine(punch_date, punch_time)
            t2 = datetime.combine(punch_date, late_threshold)
            late_minutes = int((t1 - t2).total_seconds() // 60)

    # 3. Create Punch Log
    punch_log = TeacherPunchLog(
        teacher=teacher,
        punch_time=punch_dt,
        date=punch_date,
        punch_type=punch_type,
        method=method,
        status_result=status_result,
        gps_lat=gps_lat,
        gps_lng=gps_lng,
        is_within_geofence=is_within_geofence,
        device_uuid=device_uuid,
        ip_address=ip_address,
        notes=notes,
        raw_payload=raw_payload or {}
    )

    # If base64 snapshot provided
    if snapshot_data_url and ',' in snapshot_data_url:
        try:
            fmt, imgstr = snapshot_data_url.split(';base64,')
            ext = fmt.split('/')[-1]
            data = base64.b64decode(imgstr)
            filename = f"punch_{teacher.teacher_id}_{punch_dt.strftime('%Y%m%d_%H%M%S')}.{ext}"
            punch_log.snapshot_photo.save(filename, ContentFile(data), save=False)
        except Exception:
            pass

    punch_log.save()

    # 4. Sync / Update TeacherAttendance record for today
    att, created = TeacherAttendance.objects.get_or_create(
        teacher=teacher,
        date=punch_date,
        defaults={
            'status': TeacherAttendance.Status.LATE if is_late else TeacherAttendance.Status.PRESENT,
            'check_in_time': punch_time,
            'check_in_method': method,
            'is_late': is_late,
            'late_minutes': late_minutes,
            'deduction_amount': Decimal('0.00'),
            'notes': f"Check-in តាម {punch_log.get_method_display()}"
        }
    )

    if not created:
        # Update existing attendance if not excused leave
        if att.status != TeacherAttendance.Status.EXCUSED_LEAVE:
            if not att.check_in_time or punch_time < att.check_in_time:
                att.check_in_time = punch_time
                att.check_in_method = method
                att.is_late = is_late
                att.late_minutes = late_minutes
                att.status = TeacherAttendance.Status.LATE if is_late else TeacherAttendance.Status.PRESENT
                att.deduction_amount = Decimal('0.00')
            elif punch_type == 'CHECK_OUT':
                att.check_out_time = punch_time
            att.save()

    return punch_log, att


# ---------------------------------------------------------------------------
# 1. Kiosk Display & Dynamic Rolling QR Code Views
# ---------------------------------------------------------------------------

@login_required
@role_required(['ADMIN', 'TEACHER'])
def teacher_kiosk_view(request):
    """
    Fullscreen Kiosk Display for school entrance / administration lobby.
    Displays Dynamic Rolling QR Code, Real-time Clock, Today Punch Statistics,
    and allows switching to Face AI Recognition mode.
    """
    config = TeacherAttendanceConfig.get_settings()
    school_profile = SchoolProfile.get_settings()
    token, expires_in = generate_rolling_qr_token(config)

    today = date.today()
    today_punches = TeacherPunchLog.objects.filter(date=today).select_related('teacher').order_by('-punch_time')[:15]
    total_punched_teachers = TeacherPunchLog.objects.filter(date=today).values('teacher_id').distinct().count()
    total_active_teachers = Teacher.objects.filter(status=Teacher.Status.ACTIVE).count()

    return render(request, 'teachers/kiosk_display.html', {
        'config': config,
        'school_profile': school_profile,
        'initial_token': token,
        'expires_in': expires_in,
        'today_punches': today_punches,
        'total_punched_teachers': total_punched_teachers,
        'total_active_teachers': total_active_teachers,
        'page_title': 'School Attendance Kiosk (អេក្រង់ស្កេនវត្តមានមុខសាលា)'
    })


def api_kiosk_qr_token(request):
    """
    JSON API endpoint polled by the Kiosk screen to get refreshed rolling QR token.
    """
    config = TeacherAttendanceConfig.get_settings()
    if not config.enable_qr_checkin:
        return JsonResponse({'status': 'error', 'message': 'មុខងារ QR Check-in ត្រូវបានបិទដោយ Admin'}, status=403)

    token, expires_in = generate_rolling_qr_token(config)
    today = date.today()
    total_punched = TeacherPunchLog.objects.filter(date=today).values('teacher_id').distinct().count()
    latest_punch = TeacherPunchLog.objects.filter(date=today).select_related('teacher').first()

    latest_punch_info = None
    if latest_punch:
        latest_punch_info = {
            'teacher_name': latest_punch.teacher.khmer_name,
            'punch_time': latest_punch.punch_time.strftime('%H:%M:%S'),
            'method': latest_punch.get_method_display(),
            'status': latest_punch.get_status_result_display(),
            'photo_url': latest_punch.teacher.photo.url if latest_punch.teacher.photo else None
        }

    return JsonResponse({
        'status': 'success',
        'token': token,
        'expires_in': expires_in,
        'interval': config.rolling_qr_interval_seconds,
        'total_punched': total_punched,
        'latest_punch': latest_punch_info
    })


# ---------------------------------------------------------------------------
# 2. Mobile QR Check-in & Scanner Views (Teacher's Phone)
# ---------------------------------------------------------------------------

@login_required
def mobile_qr_scan_view(request):
    """
    Mobile web page for teachers to scan the Kiosk's Dynamic QR Code using their phone camera.
    Includes GPS Geofencing validation, Device Binding, and optional selfie capture.
    """
    config = TeacherAttendanceConfig.get_settings()
    school_profile = SchoolProfile.get_settings()

    # Ensure teacher profile exists
    teacher = None
    if hasattr(request.user, 'teacher_profile'):
        teacher = request.user.teacher_profile
    elif request.user.role == User.Role.ADMIN:
        # Admin can test as any active teacher or first teacher
        teacher = Teacher.objects.filter(status=Teacher.Status.ACTIVE).first()

    if not teacher:
        messages.error(request, "គណនីរបស់អ្នកមិនទាន់បានភ្ជាប់ជាមួយ Teacher Profile នៅឡើយទេ!")
        return redirect('admin_dashboard')

    # Get or create biometric profile
    bio_profile, _ = TeacherBiometricProfile.objects.get_or_create(teacher=teacher)

    today = date.today()
    today_punches = TeacherPunchLog.objects.filter(teacher=teacher, date=today).order_by('-punch_time')
    today_att = TeacherAttendance.objects.filter(teacher=teacher, date=today).first()

    return render(request, 'teachers/mobile_qr_scan.html', {
        'config': config,
        'school_profile': school_profile,
        'teacher': teacher,
        'bio_profile': bio_profile,
        'today_punches': today_punches,
        'today_att': today_att,
        'page_title': 'ស្កេនវត្តមានលើទូរស័ព្ទ (Teacher Mobile Check-in)'
    })


@login_required
def api_process_qr_checkin(request):
    """
    POST API to process teacher QR check-in from mobile phone.
    Validates:
      1. Method enabled in Config
      2. Dynamic QR Token freshness
      3. Device Binding UUID (1 Device = 1 Teacher)
      4. GPS Geofencing radius
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid HTTP Method'}, status=405)

    config = TeacherAttendanceConfig.get_settings()
    if not config.enable_qr_checkin:
        return JsonResponse({'status': 'error', 'message': '❌ មុខងារស្កេន QR Code ត្រូវបានបិទជាបណ្តោះអាសន្ន!'}, status=403)

    if config.active_daily_mode not in ['ALL', 'OPTION_1_QR']:
        return JsonResponse({
            'status': 'error',
            'message': f'❌ Admin បានកំណត់ឱ្យប្រើ [{config.get_active_daily_mode_display()}] សម្រាប់ថ្ងៃនេះ។ មិនអនុញ្ញាតឱ្យស្កេន QR ឡើយ!'
        }, status=403)


    # Determine Teacher
    teacher = None
    if hasattr(request.user, 'teacher_profile'):
        teacher = request.user.teacher_profile
    elif request.user.role == User.Role.ADMIN:
        teacher_id = request.POST.get('teacher_id')
        if teacher_id:
            teacher = Teacher.objects.filter(id=teacher_id).first()
        if not teacher:
            teacher = Teacher.objects.filter(status=Teacher.Status.ACTIVE).first()

    if not teacher:
        return JsonResponse({'status': 'error', 'message': '❌ មិនមាន Teacher Profile សម្រាប់គណនីនេះទេ!'}, status=400)

    # 1. Verify Dynamic QR Token
    scanned_token = request.POST.get('token', '').strip()
    if not verify_rolling_qr_token(scanned_token, config):
        return JsonResponse({
            'status': 'error',
            'message': '❌ QR Code បានផុតកំណត់សុពលភាព ឬមិនត្រឹមត្រូវ! សូមស្កេន QR Code ថ្មីនៅលើអេក្រង់សាលា។'
        }, status=400)

    # 2. Verify Device Binding
    device_uuid = request.POST.get('device_uuid', '').strip()
    device_name = request.POST.get('device_name', '').strip()
    bio_profile, _ = TeacherBiometricProfile.objects.get_or_create(teacher=teacher)

    if config.require_device_binding:
        if not device_uuid:
            return JsonResponse({'status': 'error', 'message': '❌ មិនអាចផ្ទៀងផ្ទាត់សម្គាល់ទូរស័ព្ទបានឡើយ!'}, status=400)
        
        # If no device bound yet, bind this first phone automatically
        if not bio_profile.device_uuid:
            bio_profile.device_uuid = device_uuid
            bio_profile.device_name = device_name
            bio_profile.save(update_fields=['device_uuid', 'device_name'])
        elif bio_profile.device_uuid != device_uuid:
            return JsonResponse({
                'status': 'error',
                'message': f'❌ ទូរស័ព្ទនេះមិនត្រូវគ្នានឹងទូរស័ព្ទដែលបានចុះឈ្មោះ ({bio_profile.device_name or "ឧបករណ៍ចាស់"}) ឡើយ! មិនអាចស្កេនជំនួសគ្នាបានទេ។'
            }, status=403)

    # 3. Verify GPS Geofencing
    gps_lat_str = request.POST.get('latitude')
    gps_lng_str = request.POST.get('longitude')
    gps_lat = float(gps_lat_str) if gps_lat_str else None
    gps_lng = float(gps_lng_str) if gps_lng_str else None

    school_profile = SchoolProfile.get_settings()
    if config.require_gps_validation:
        if gps_lat is None or gps_lng is None:
            return JsonResponse({'status': 'error', 'message': '❌ សូមបើកទីតាំង GPS (Location) លើទូរស័ព្ទរបស់អ្នក!'}, status=400)
        
        if school_profile.latitude and school_profile.longitude:
            dist = calculate_haversine_distance(gps_lat, gps_lng, school_profile.latitude, school_profile.longitude)
            radius = school_profile.gps_radius_meters or 100
            if dist > radius:
                return JsonResponse({
                    'status': 'error',
                    'message': f'❌ អ្នកស្ថិតនៅចម្ងាយ {int(dist)}m ក្រៅបរិវេណសាលា (អនុញ្ញាតត្រឹម {radius}m)។ មិនអាច Check-in បានទេ!'
                }, status=400)

    # 4. Record Punch
    snapshot_url = request.POST.get('snapshot')
    ip_addr = request.META.get('REMOTE_ADDR')

    punch_log, att = record_teacher_punch(
        teacher=teacher,
        method=TeacherPunchLog.Method.QR_SCAN,
        punch_type=TeacherPunchLog.PunchType.CHECK_IN,
        punch_dt=datetime.now(),
        gps_lat=gps_lat,
        gps_lng=gps_lng,
        device_uuid=device_uuid,
        ip_address=ip_addr,
        snapshot_data_url=snapshot_url,
        notes="ស្កេន Dynamic QR Code លើទូរស័ព្ទដៃ"
    )

    status_kh = "ទាន់ពេល" if punch_log.status_result == TeacherPunchLog.StatusResult.ON_TIME else "មកយឺត"
    return JsonResponse({
        'status': 'success',
        'message': f'🎉 កត់ត្រាវត្តមានជោគជ័យ! {teacher.khmer_name} [{status_kh}] ម៉ោង {punch_log.punch_time.strftime("%H:%M:%S")}',
        'punch_id': punch_log.id,
        'punch_time': punch_log.punch_time.strftime('%H:%M:%S'),
        'status_result': punch_log.status_result,
        'status_label': punch_log.get_status_result_display(),
        'teacher_name': teacher.khmer_name,
        'is_late': att.is_late,
        'late_minutes': att.late_minutes
    })


# ---------------------------------------------------------------------------
# 3. Webcam Face Recognition AI Views
# ---------------------------------------------------------------------------

@login_required
@role_required(['ADMIN', 'TEACHER'])
def face_ai_kiosk_view(request):
    """
    Webcam Face Recognition AI Kiosk page for Tablet/Laptop at school gate.
    Runs real-time face detection and 128-d embedding matching.
    """
    config = TeacherAttendanceConfig.get_settings()
    school_profile = SchoolProfile.get_settings()

    enrolled_count = TeacherBiometricProfile.objects.filter(is_enrolled_face=True).count()
    total_teachers = Teacher.objects.filter(status=Teacher.Status.ACTIVE).count()

    return render(request, 'teachers/face_ai_kiosk.html', {
        'config': config,
        'school_profile': school_profile,
        'enrolled_count': enrolled_count,
        'total_teachers': total_teachers,
        'page_title': 'Webcam Face AI Attendance (ស្កេនផ្ទៃមុខ AI)'
    })


@login_required
def api_get_enrolled_faces(request):
    """
    Returns enrolled teacher face descriptors and profile pictures for client-side matcher.
    """
    profiles = TeacherBiometricProfile.objects.filter(
        is_enrolled_face=True,
        teacher__status=Teacher.Status.ACTIVE
    ).select_related('teacher')

    data = []
    for p in profiles:
        data.append({
            'id': p.teacher.id,
            'teacher_id': p.teacher.teacher_id,
            'khmer_name': p.teacher.khmer_name,
            'latin_name': p.teacher.latin_name,
            'specialization': p.teacher.specialization,
            'photo_url': p.face_photo.url if p.face_photo else (p.teacher.photo.url if p.teacher.photo else None),
            'descriptors': p.face_descriptor or []
        })

    return JsonResponse({'status': 'success', 'teachers': data, 'count': len(data)})


@login_required
def api_face_checkin(request):
    """
    POST API called when the Face AI recognizer matches a teacher.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid HTTP Method'}, status=405)

    config = TeacherAttendanceConfig.get_settings()
    if not config.enable_face_ai_checkin:
        return JsonResponse({'status': 'error', 'message': '❌ មុខងារ Face Recognition AI ត្រូវបានបិទដោយ Admin!'}, status=403)

    if config.active_daily_mode not in ['ALL', 'OPTION_2_FACE']:
        return JsonResponse({
            'status': 'error',
            'message': f'❌ Admin បានកំណត់ឱ្យប្រើ [{config.get_active_daily_mode_display()}] សម្រាប់ថ្ងៃនេះ។ មិនអនុញ្ញាតឱ្យស្កេនផ្ទៃមុខឡើយ!'
        }, status=403)


    teacher_id = request.POST.get('teacher_id')
    teacher = get_object_or_404(Teacher, pk=teacher_id)

    snapshot_url = request.POST.get('snapshot')
    ip_addr = request.META.get('REMOTE_ADDR')

    punch_log, att = record_teacher_punch(
        teacher=teacher,
        method=TeacherPunchLog.Method.FACE_AI,
        punch_type=TeacherPunchLog.PunchType.CHECK_IN,
        punch_dt=datetime.now(),
        ip_address=ip_addr,
        snapshot_data_url=snapshot_url,
        notes="ស្កេនផ្ទៃមុខតាមរយៈ Webcam Face AI Recognition"
    )

    status_kh = "ទាន់ពេល" if punch_log.status_result == TeacherPunchLog.StatusResult.ON_TIME else "មកយឺត"
    return JsonResponse({
        'status': 'success',
        'message': f'🎉 ស្កាល់ផ្ទៃមុខជោគជ័យ! {teacher.khmer_name} [{status_kh}] ម៉ោង {punch_log.punch_time.strftime("%H:%M:%S")}',
        'punch_id': punch_log.id,
        'punch_time': punch_log.punch_time.strftime('%H:%M:%S'),
        'status_result': punch_log.status_result,
        'status_label': punch_log.get_status_result_display(),
        'teacher_name': teacher.khmer_name,
        'teacher_id': teacher.teacher_id,
        'photo_url': teacher.photo.url if teacher.photo else None
    })


@login_required
@role_required(['ADMIN', 'TEACHER'])
def face_enroll_view(request, pk):
    """
    Face Enrollment Tool to capture or upload teacher's face photo and save 128-d descriptors.
    """
    teacher = get_object_or_404(Teacher, pk=pk)
    bio_profile, _ = TeacherBiometricProfile.objects.get_or_create(teacher=teacher)

    if request.method == 'POST':
        descriptor_raw = request.POST.get('face_descriptor')
        photo_data_url = request.POST.get('photo_data')

        if descriptor_raw:
            try:
                descriptor = json.loads(descriptor_raw)
                bio_profile.face_descriptor = descriptor
                bio_profile.is_enrolled_face = True
            except Exception:
                pass

        if photo_data_url and ',' in photo_data_url:
            try:
                fmt, imgstr = photo_data_url.split(';base64,')
                ext = fmt.split('/')[-1]
                data = base64.b64decode(imgstr)
                filename = f"face_{teacher.teacher_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
                bio_profile.face_photo.save(filename, ContentFile(data), save=False)
                bio_profile.is_enrolled_face = True
            except Exception:
                pass

        bio_profile.save()
        messages.success(request, f"🎉 បានចុះឈ្មោះផ្ទៃមុខសម្រាប់លោកគ្រូ/អ្នកគ្រូ {teacher.khmer_name} ដោយជោគជ័យ!")
        return redirect('face_enroll', pk=teacher.pk)

    return render(request, 'teachers/face_enroll.html', {
        'teacher': teacher,
        'bio_profile': bio_profile,
        'page_title': f'ចុះឈ្មោះផ្ទៃមុខ (Face Enrollment) - {teacher.khmer_name}'
    })


# ---------------------------------------------------------------------------
# 4. Biometric Hub (ZKTeco / Hikvision / USB / File Import) Views
# ---------------------------------------------------------------------------

@login_required
@role_required(['ADMIN'])
def biometric_hub_view(request):
    """
    Biometric & Hardware Management Hub.
    Tabs for:
      - ZKTeco / Hikvision Push Webhook status
      - Direct IP Network Sync (Socket/pyzk)
      - USB Desktop Fingerprint Reader
      - USB Flash Drive (Excel / CSV / DAT) File Import
    """
    config = TeacherAttendanceConfig.get_settings()
    teachers = Teacher.objects.filter(status=Teacher.Status.ACTIVE).select_related('biometric_profile')
    recent_punches = TeacherPunchLog.objects.select_related('teacher').order_by('-punch_time')[:20]

    # Server Push Webhook URL
    host = request.get_host()
    scheme = 'https' if request.is_secure() else 'http'
    webhook_url = f"{scheme}://{host}/teachers/attendance/biometric/api/push/?secret={config.biometric_push_secret or 'YOUR_SECRET'}"

    return render(request, 'teachers/biometric_hub.html', {
        'config': config,
        'teachers': teachers,
        'recent_punches': recent_punches,
        'webhook_url': webhook_url,
        'page_title': 'ឧបករណ៍ Biometric & Fingerprint Integration Hub'
    })


@csrf_exempt
def api_biometric_push_webhook(request):
    """
    Webhook accepting real-time push logs from ZKTeco (ADMS/Cloud Push) and Hikvision (ISAPI).
    Accepts JSON, Form-data, or Raw Log Streams.
    """
    config = TeacherAttendanceConfig.get_settings()
    if not config.enable_biometric_device:
        return JsonResponse({'status': 'error', 'message': 'Biometric Integration disabled'}, status=403)

    # Validate secret token if set
    secret = request.GET.get('secret') or request.headers.get('X-Biometric-Secret')
    if config.biometric_push_secret and secret != config.biometric_push_secret:
        return JsonResponse({'status': 'error', 'message': 'Unauthorized Secret'}, status=401)

    try:
        data = {}
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST.dict() or json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        data = request.POST.dict()

    # Extract user pin / teacher id, timestamp, verify mode
    user_pin = data.get('pin') or data.get('user_id') or data.get('employee_no') or data.get('card_no')
    timestamp_str = data.get('time') or data.get('timestamp') or data.get('punch_time')

    if not user_pin:
        return HttpResponse("OK") # Return OK for handshake protocols

    # Match teacher by zk_pin, teacher_id, or card_rfid
    teacher = Teacher.objects.filter(
        Q(teacher_id__iexact=str(user_pin)) |
        Q(biometric_profile__zk_pin=str(user_pin)) |
        Q(biometric_profile__card_rfid=str(user_pin))
    ).first()

    if not teacher:
        return JsonResponse({'status': 'warning', 'message': f'Teacher not found for PIN: {user_pin}'}, status=404)

    punch_dt = datetime.now()
    if timestamp_str:
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y/%m/%d %H:%M:%S'):
            try:
                punch_dt = datetime.strptime(timestamp_str.strip()[:19], fmt)
                break
            except ValueError:
                pass

    punch_log, att = record_teacher_punch(
        teacher=teacher,
        method=TeacherPunchLog.Method.BIOMETRIC_DEVICE,
        punch_type=TeacherPunchLog.PunchType.CHECK_IN,
        punch_dt=punch_dt,
        notes=f"Biometric Push Webhook ({config.get_biometric_device_type_display()})",
        raw_payload=data
    )

    return JsonResponse({
        'status': 'success',
        'punch_id': punch_log.id,
        'teacher': teacher.khmer_name,
        'time': punch_log.punch_time.strftime('%Y-%m-%d %H:%M:%S')
    })


@login_required
@role_required(['ADMIN'])
def api_sync_biometric_device(request):
    """
    Initiates a direct network sync with ZKTeco or Hikvision terminal over LAN IP.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)

    config = TeacherAttendanceConfig.get_settings()
    device_ip = request.POST.get('device_ip') or config.biometric_device_ip
    device_port = int(request.POST.get('device_port') or config.biometric_device_port or 4370)

    # Simulate / execute connection probe and log fetch
    today = date.today()
    synced_count = 0

    # In production, pyzk: zk = ZK(device_ip, port=device_port, timeout=5); conn = zk.connect(); logs = conn.get_attendance()
    # Here we provide a robust connection test & sample sync
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM if config.biometric_device_type == 'HIKVISION' else socket.SOCK_DGRAM)
        sock.settimeout(2.0)
        sock.connect((device_ip, device_port))
        sock.close()
        is_reachable = True
    except Exception:
        is_reachable = False

    return JsonResponse({
        'status': 'success' if is_reachable else 'info',
        'is_online': is_reachable,
        'synced_count': synced_count,
        'message': f"បានភ្ជាប់ទៅកាន់ម៉ាស៊ីន {device_ip}:{device_port} {'ដោយជោគជ័យ' if is_reachable else '(ម៉ាស៊ីនមិនឆ្លើយតប សូមពិនិត្យខ្សែបណ្តាញ Network/Wi-Fi)'}!"
    })


@login_required
@role_required(['ADMIN'])
def biometric_file_import_view(request):
    """
    Upload and parse Excel / CSV / DAT Log files exported from biometric machines via USB Flash Drive.
    """
    if request.method != 'POST' or 'log_file' not in request.FILES:
        messages.error(request, "សូមជ្រើសរើស File Log (CSV, Excel, ឬ .DAT) ដើម្បី Upload!")
        return redirect('biometric_hub')

    uploaded_file = request.FILES['log_file']
    filename = uploaded_file.name.lower()
    created_count = 0
    skipped_count = 0
    errors = []

    try:
        content = uploaded_file.read()
        
        # Handle CSV / DAT / Text log formats
        if filename.endswith('.csv') or filename.endswith('.dat') or filename.endswith('.txt'):
            decoded = content.decode('utf-8', errors='ignore')
            reader = csv.reader(io.StringIO(decoded), delimiter=',' if ',' in decoded else ('\t' if '\t' in decoded else ' '))
            
            for row in reader:
                clean_row = [col.strip() for col in row if col.strip()]
                if len(clean_row) < 2:
                    continue
                
                # Check for PIN / Teacher ID and Date/Time
                pin_candidate = clean_row[0]
                time_candidate = None
                for item in clean_row[1:]:
                    if ('-' in item or '/' in item) and (':' in item or len(clean_row) > 2):
                        time_candidate = item
                        break

                if not time_candidate and len(clean_row) >= 3:
                    time_candidate = f"{clean_row[1]} {clean_row[2]}"

                if not time_candidate:
                    continue

                # Match Teacher
                teacher = Teacher.objects.filter(
                    Q(teacher_id__iexact=pin_candidate) |
                    Q(biometric_profile__zk_pin=pin_candidate)
                ).first()

                if not teacher:
                    skipped_count += 1
                    continue

                punch_dt = None
                for fmt in ('%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S', '%d/%m/%Y %H:%M:%S', '%Y-%m-%d'):
                    try:
                        punch_dt = datetime.strptime(time_candidate[:19], fmt)
                        break
                    except ValueError:
                        pass

                if not punch_dt:
                    continue

                record_teacher_punch(
                    teacher=teacher,
                    method=TeacherPunchLog.Method.USB_FILE_IMPORT,
                    punch_type=TeacherPunchLog.PunchType.CHECK_IN,
                    punch_dt=punch_dt,
                    notes=f"Import ពី USB File ({uploaded_file.name})"
                )
                created_count += 1

        elif filename.endswith('.xlsx') or filename.endswith('.xls'):
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
            ws = wb.active
            for row in ws.iter_rows(min_row=2, values_only=True):
                if not row or not row[0]:
                    continue
                pin_candidate = str(row[0]).strip()
                time_val = row[1] if len(row) > 1 else None

                teacher = Teacher.objects.filter(
                    Q(teacher_id__iexact=pin_candidate) |
                    Q(biometric_profile__zk_pin=pin_candidate)
                ).first()

                if not teacher or not time_val:
                    skipped_count += 1
                    continue

                punch_dt = time_val if isinstance(time_val, datetime) else None
                if not punch_dt and isinstance(time_val, str):
                    try:
                        punch_dt = datetime.strptime(time_val.strip()[:19], '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        pass

                if punch_dt:
                    record_teacher_punch(
                        teacher=teacher,
                        method=TeacherPunchLog.Method.USB_FILE_IMPORT,
                        punch_type=TeacherPunchLog.PunchType.CHECK_IN,
                        punch_dt=punch_dt,
                        notes=f"Import ពី Excel ({uploaded_file.name})"
                    )
                    created_count += 1

        messages.success(
            request,
            f"🎉 បាន Import ទិន្នន័យពី Flash Drive ជោគជ័យ! បញ្ចូលវត្តមានគ្រូចំនួន {created_count} កំណត់ត្រា (មិនស្គាល់ ID ចំនួន {skipped_count})។"
        )
    except Exception as e:
        messages.error(request, f"❌ មានបញ្ហាក្នុងការអាន File: {str(e)}")

    return redirect('biometric_hub')


@login_required
def api_usb_fingerprint_punch(request):
    """
    Endpoint for USB Desktop Fingerprint Reader (e.g. ZK4500) directly on the web page.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)

    teacher_id = request.POST.get('teacher_id')
    teacher = get_object_or_404(Teacher, pk=teacher_id)

    punch_log, att = record_teacher_punch(
        teacher=teacher,
        method=TeacherPunchLog.Method.USB_FINGERPRINT,
        punch_type=TeacherPunchLog.PunchType.CHECK_IN,
        punch_dt=datetime.now(),
        notes="ស្កេនតាមកូនឧបករណ៍ USB Fingerprint Reader"
    )

    return JsonResponse({
        'status': 'success',
        'message': f'🎉 បានកត់ត្រាវត្តមានតាម USB Fingerprint! {teacher.khmer_name}',
        'punch_id': punch_log.id,
        'punch_time': punch_log.punch_time.strftime('%H:%M:%S'),
        'teacher_name': teacher.khmer_name
    })


# ---------------------------------------------------------------------------
# 5. Admin Settings & Audit Trail Views
# ---------------------------------------------------------------------------

@login_required
@role_required(['ADMIN'])
def teacher_attendance_settings_view(request):
    """
    Admin Configuration Center:
    - Toggle which check-in methods are active (QR / Face AI / Biometric / Timetable Sync)
    - Set Shift working hours and late cutoffs
    - Set GPS radius, Device binding, and Biometric IP/Secret
    """
    config = TeacherAttendanceConfig.get_settings()
    school_profile = SchoolProfile.get_settings()

    if request.method == 'POST':
        # Admin Active Daily Enforced Mode
        config.active_daily_mode = request.POST.get('active_daily_mode') or TeacherAttendanceConfig.DailyMode.ALL

        # Method toggles
        config.enable_qr_checkin = request.POST.get('enable_qr_checkin') == 'on'
        config.enable_face_ai_checkin = request.POST.get('enable_face_ai_checkin') == 'on'
        config.enable_biometric_device = request.POST.get('enable_biometric_device') == 'on'
        config.enable_usb_fingerprint = request.POST.get('enable_usb_fingerprint') == 'on'
        config.enable_file_import = request.POST.get('enable_file_import') == 'on'
        config.enable_timetable_sync = request.POST.get('enable_timetable_sync') == 'on'

        # Security policies
        config.require_gps_validation = request.POST.get('require_gps_validation') == 'on'
        config.require_device_binding = request.POST.get('require_device_binding') == 'on'
        config.require_selfie_snap = request.POST.get('require_selfie_snap') == 'on'
        config.rolling_qr_interval_seconds = int(request.POST.get('rolling_qr_interval_seconds') or 20)

        # Shifts
        config.morning_checkin_start = request.POST.get('morning_checkin_start') or '06:30'
        config.morning_checkin_end = request.POST.get('morning_checkin_end') or '08:30'
        config.morning_late_threshold = request.POST.get('morning_late_threshold') or '07:15'
        config.afternoon_checkin_start = request.POST.get('afternoon_checkin_start') or '12:30'
        config.afternoon_checkin_end = request.POST.get('afternoon_checkin_end') or '14:30'
        config.afternoon_late_threshold = request.POST.get('afternoon_late_threshold') or '13:15'

        # Leave Policies
        config.emergency_leave_cutoff_time = request.POST.get('emergency_leave_cutoff_time') or '17:00'

        # Hardware
        config.biometric_device_ip = request.POST.get('biometric_device_ip') or '192.168.1.201'
        config.biometric_device_port = int(request.POST.get('biometric_device_port') or 4370)
        config.biometric_device_type = request.POST.get('biometric_device_type') or 'ZKTECO'
        config.biometric_push_secret = request.POST.get('biometric_push_secret') or ''
        config.notify_telegram_on_punch = request.POST.get('notify_telegram_on_punch') == 'on'


        config.save()
        messages.success(request, "🎉 បានរក្សាទុកការកំណត់ប្រព័ន្ធវត្តមាន និងឧបករណ៍ Biometric ដោយជោគជ័យ!")
        return redirect('teacher_attendance_settings')

    return render(request, 'teachers/attendance_settings.html', {
        'config': config,
        'school_profile': school_profile,
        'daily_mode_choices': TeacherAttendanceConfig.DailyMode.choices,
        'page_title': 'ការកំណត់វិធីសាស្ត្រវត្តមានគ្រូ & ឧបករណ៍ (Attendance & Biometric Settings)'
    })


@login_required
@role_required(['ADMIN', 'TEACHER'])
def teacher_punch_logs_view(request):
    """
    Detailed Audit Trail & Punch Log Viewer with filtering by Date, Teacher, Method, and Status.
    Enforces strict user isolation: Teachers can ONLY see their own punch records.
    """
    query = request.GET.get('q', '').strip()
    method_filter = request.GET.get('method', '')
    status_filter = request.GET.get('status', '')
    date_filter = request.GET.get('date', date.today().strftime('%Y-%m-%d'))

    logs = TeacherPunchLog.objects.select_related('teacher').order_by('-punch_time')

    if date_filter:
        try:
            d = datetime.strptime(date_filter, '%Y-%m-%d').date()
            logs = logs.filter(date=d)
        except ValueError:
            pass

    if method_filter:
        logs = logs.filter(method=method_filter)

    if status_filter:
        logs = logs.filter(status_result=status_filter)

    if query:
        logs = logs.filter(
            Q(teacher__teacher_id__icontains=query) |
            Q(teacher__khmer_name__icontains=query) |
            Q(teacher__latin_name__icontains=query)
        )

    # Strict Privacy Isolation: Teachers only see their own logs
    if request.user.role == User.Role.TEACHER:
        if hasattr(request.user, 'teacher_profile'):
            logs = logs.filter(teacher=request.user.teacher_profile)
        else:
            logs = logs.none()

    total_count = logs.count()
    logs_page = logs[:100]

    return render(request, 'teachers/punch_logs.html', {
        'logs': logs_page,
        'total_count': total_count,
        'selected_date': date_filter,
        'selected_method': method_filter,
        'selected_status': status_filter,
        'query': query,
        'method_choices': TeacherPunchLog.Method.choices,
        'status_choices': TeacherPunchLog.StatusResult.choices,
        'page_title': 'កំណត់ត្រាស្កេនវត្តមានគ្រូលម្អិត (Punch Logs & Audit Trail)'
    })


@login_required
@role_required(['ADMIN', 'TEACHER'])
def teacher_my_attendance_history_view(request):
    """
    Personal Attendance & Punch History portal for teachers.
    Enforces strict isolation: Teachers can ONLY view their own records.
    """
    user = request.user
    teacher = getattr(user, 'teacher_profile', None)

    if not teacher and user.role == User.Role.ADMIN:
        # Admin can view a selected teacher or default to first teacher
        t_id = request.GET.get('teacher_id')
        teacher = Teacher.objects.filter(id=t_id).first() if t_id else Teacher.objects.first()

    if not teacher:
        messages.error(request, "មិនមានទិន្នន័យ Teacher Profile សម្រាប់គណនីនេះឡើយ!")
        return redirect('teacher_dashboard')

    today = date.today()
    month_str = request.GET.get('month', today.strftime('%Y-%m'))
    try:
        y, m = map(int, month_str.split('-'))
    except ValueError:
        y, m = today.year, today.month
        month_str = today.strftime('%Y-%m')

    start_date = date(y, m, 1)
    import calendar
    _, last_day = calendar.monthrange(y, m)
    end_date = date(y, m, last_day)

    # Fetch Attendance Records & Punch logs for this teacher only
    attendances = TeacherAttendance.objects.filter(
        teacher=teacher,
        date__range=[start_date, end_date]
    ).order_by('-date')

    punch_logs = TeacherPunchLog.objects.filter(
        teacher=teacher,
        date__range=[start_date, end_date]
    ).order_by('-punch_time')

    # Summary stats
    total_present = attendances.filter(status=TeacherAttendance.Status.PRESENT).count()
    total_late = attendances.filter(status=TeacherAttendance.Status.LATE).count()
    total_excused = attendances.filter(status=TeacherAttendance.Status.EXCUSED_LEAVE).count()
    total_unexcused = attendances.filter(status=TeacherAttendance.Status.UNEXCUSED_ABSENCE).count()
    total_deduction = sum(att.deduction_amount for att in attendances)

    return render(request, 'teachers/my_attendance_history.html', {
        'teacher': teacher,
        'attendances': attendances,
        'punch_logs': punch_logs,
        'selected_month': month_str,
        'total_present': total_present,
        'total_late': total_late,
        'total_excused': total_excused,
        'total_unexcused': total_unexcused,
        'total_deduction': total_deduction,
        'page_title': f'ប្រវត្តិចុះវត្តមានផ្ទាល់ខ្លួន - {teacher.khmer_name}'
    })

