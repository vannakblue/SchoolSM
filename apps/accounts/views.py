from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .forms import LoginForm, UserProfileForm, TelegramConfigForm, SchoolProfileForm
from .models import User, TelegramConfig, NotificationLog, SchoolProfile, MenuSection, MenuItem, RoleMenuPermission, DirectChatMessage
from .decorators import role_required
from .utils import send_telegram_notification

def _ensure_admin_exists():
    try:
        admin_user = User.objects.filter(username='admin').first() or User.objects.filter(is_superuser=True).first()
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
            admin_user.set_password('admin123')
            admin_user.save()
        else:
            if not admin_user.check_password('admin123'):
                admin_user.set_password('admin123')
                admin_user.is_staff = True
                admin_user.is_superuser = True
                admin_user.is_active = True
                admin_user.save()
    except Exception:
        pass


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')
    
    _ensure_admin_exists()
    
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"សូមស្វាគមន៍ {user.display_name}! ចូលប្រព័ន្ធជោគជ័យ។")
            return redirect('dashboard_redirect')
        else:
            uname = request.POST.get('username', '').strip()
            pword = request.POST.get('password', '').strip()
            user = authenticate(request, username=uname, password=pword)
            if user:
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                messages.success(request, f"សូមស្វាគមន៍ {user.display_name}! ចូលប្រព័ន្ធជោគជ័យ។")
                return redirect('dashboard_redirect')
            messages.error(request, "ឈ្មោះគណនី ឬពាក្យសម្ងាត់មិនត្រឹមត្រូវទេ!")
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form})


def demo_login_view(request, role):
    """
    1-Click Demo Login to switch between Super Admin, Accountant, Teacher, and Student
    """
    _ensure_admin_exists()
    user = User.objects.filter(role=role).first()
    if not user and role == 'ADMIN':
        user = User.objects.filter(username='admin').first() or User.objects.filter(is_superuser=True).first()

    if not user:
        try:
            if role == 'ADMIN':
                user, _ = User.objects.get_or_create(
                    username='admin',
                    defaults={'role': User.Role.ADMIN, 'khmer_name': 'បណ្ឌិត សុខ វិបុល', 'is_staff': True, 'is_superuser': True, 'is_active': True}
                )
                user.set_password('admin123')
                user.save()
            elif role == 'ACCOUNTANT':
                user, _ = User.objects.get_or_create(
                    username='accountant',
                    defaults={'role': User.Role.ACCOUNTANT, 'khmer_name': 'អ្នកស្រី គង់ សុភា', 'is_active': True}
                )
                user.set_password('admin123')
                user.save()
            elif role == 'TEACHER':
                user, _ = User.objects.get_or_create(
                    username='teacher',
                    defaults={'role': User.Role.TEACHER, 'khmer_name': 'លោកគ្រូ លី វណ្ណារ៉ា', 'is_active': True}
                )
                user.set_password('admin123')
                user.save()
                from apps.teachers.models import Teacher
                teacher_prof = getattr(user, 'teacher_profile', None)
                if not teacher_prof:
                    existing_t = Teacher.objects.filter(teacher_id='T-DEMO01').first()
                    if not existing_t:
                        Teacher.objects.create(
                            teacher_id='T-DEMO01',
                            user=user,
                            khmer_name='លោកគ្រូ លី វណ្ណារ៉ា',
                            latin_name='LY VANNARA',
                            specialization='គណិតវិទ្យា',
                            phone='012 345 678',
                            gender='M'
                        )
                    else:
                        existing_t.user = user
                        existing_t.save()
            elif role == 'STUDENT':
                user, _ = User.objects.get_or_create(
                    username='student',
                    defaults={'role': User.Role.STUDENT, 'khmer_name': 'សុខ ចិន្តា', 'is_active': True}
                )
                user.set_password('admin123')
                user.save()
        except Exception:
            pass

    if user:
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, f"បានចូលប្រើប្រាស់ជា {user.get_role_display()} ({user.display_name})")
        return redirect('dashboard_redirect')
    else:
        messages.error(request, f"មិនទាន់មានគណនីសម្រាប់តួនាទី {role} នៅឡើយទេ! សូមដំណើរការ Seed Data ជាមុនសិន។")
        return redirect('login')


def init_admin_view(request):
    """
    Emergency setup and direct 1-click admin login
    """
    log_messages = []
    try:
        from django.core.management import call_command
        log_messages.append("1. Running database migrations...")
        call_command('migrate', interactive=False)
        log_messages.append("2. Running seed_school_data...")
        try:
            call_command('seed_school_data')
            log_messages.append("3. Seed data populated successfully.")
        except Exception as seed_err:
            log_messages.append(f"Seed note: {seed_err}")
    except Exception as e:
        log_messages.append(f"Migration error: {e}")

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
        admin_user.set_password('admin123')
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.is_active = True
        admin_user.save()
        
        login(request, admin_user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, "បានដំឡើងទិន្នន័យ និងចូលប្រើប្រាស់ជា Super Admin ដោយជោគជ័យ!")
        return redirect('dashboard_redirect')
    except Exception as e:
        from django.http import HttpResponse
        return HttpResponse(f"<h3>Setup Error: {e}</h3><pre>{'<br>'.join(log_messages)}</pre>")






@login_required
def logout_view(request):
    logout(request)
    messages.info(request, "លោកអ្នកបានចាកចេញពីប្រព័ន្ធដោយជោគជ័យ!")
    return redirect('login')


@login_required
def dashboard_redirect(request):
    """
    Redirects user to their role-specific dashboard
    """
    user = request.user
    if user.is_superuser or user.role == User.Role.ADMIN:
        return redirect('admin_dashboard')
    elif user.role == User.Role.ACCOUNTANT:
        return redirect('finance_dashboard')
    elif user.role == User.Role.TEACHER:
        return redirect('teacher_dashboard')
    elif user.role == User.Role.STUDENT:
        return redirect('student_dashboard')
    return redirect('admin_dashboard')


@login_required
def profile_view(request):
    user = request.user
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "បានកែប្រែព័ត៌មានគណនីជោគជ័យ!")
            return redirect('profile')
    else:
        form = UserProfileForm(instance=user)
    
    teacher_obj = getattr(user, 'teacher_profile', None)
    school_profile = SchoolProfile.get_settings()
    return render(request, 'accounts/profile.html', {
        'form': form,
        'user_obj': user,
        'teacher_obj': teacher_obj,
        'school_profile': school_profile,
    })


@login_required
def teacher_request_profile_change(request):
    """
    Allows teachers to submit an official profile correction/update request to the admin.
    Dispatches an instant Telegram alert to the Admin and logs in NotificationLog.
    """
    import datetime
    if request.method == 'POST':
        field_name = request.POST.get('field_name', '').strip()
        new_value = request.POST.get('new_value', '').strip()
        reason = request.POST.get('reason', '').strip()

        if not field_name or not new_value:
            messages.warning(request, "⚠️ សូមជ្រើសរើសប្រភេទព័ត៌មាន និងបញ្ចូលទិន្នន័យថ្មីដែលត្រឹមត្រូវ!")
            return redirect('profile')

        teacher = getattr(request.user, 'teacher_profile', None)
        teacher_display = teacher.khmer_name if teacher else (request.user.khmer_name or request.user.username)
        teacher_id_str = teacher.teacher_id if teacher else request.user.username
        phone_str = request.user.phone or (teacher.phone if teacher else '-')

        field_labels = {
            'khmer_name': 'ឈ្មោះជាភាសាខ្មែរ (Khmer Name)',
            'latin_name': 'ឈ្មោះជាអក្សរឡាតាំង (Latin Name)',
            'gender': 'ភេទ (Gender)',
            'date_of_birth': 'ថ្ងៃខែឆ្នាំកំណើត (DOB)',
            'teacher_id': 'អត្តលេខគ្រូ (Teacher ID)',
            'specialization': 'ឯកទេសបង្រៀន (Specialization)',
            'other': 'ព័ត៌មានផ្សេងៗ (Other Information)',
        }
        field_display = field_labels.get(field_name, field_name)

        now_str = datetime.datetime.now().strftime('%d-%m-%Y %H:%M')
        tg_title = "🔔 សំណើសុំកែប្រែព័ត៌មានអត្តសញ្ញាណគ្រូ"
        tg_msg = (
            f"🔔 <b>[សំណើសុំកែប្រែព័ត៌មានគ្រូ / Teacher Profile Correction Request]</b>\n\n"
            f"👤 <b>គ្រូបង្រៀន៖</b> {teacher_display} (កូដ: <code>{teacher_id_str}</code>)\n"
            f"📞 <b>លេខទូរស័ព្ទ៖</b> <code>{phone_str}</code>\n"
            f"📌 <b>ព័ត៌មានដែលស្នើសុំកែ៖</b> {field_display}\n"
            f"✏️ <b>ទិន្នន័យថ្មីដែលត្រឹមត្រូវ៖</b> <code>{new_value}</code>\n"
            f"📝 <b>មូលហេតុ/កំណត់ចំណាំ៖</b> {reason or 'គ្មាន'}\n"
            f"⏰ <b>ពេលវេលាស្នើសុំ៖</b> {now_str}\n\n"
            f"👉 <i>សូម Admin ចូលទៅកាន់ប្រព័ន្ធដើម្បីពិនិត្យ និងកែសម្រួលជូនគ្រូ!</i>"
        )

        send_telegram_notification(
            title=tg_title,
            message=tg_msg,
            recipient_name="Admin / រដ្ឋបាលសាលា",
            recipient_phone=phone_str,
            recipient_type="Admin"
        )

        messages.success(
            request,
            f"🎉 សំណើសុំកែប្រែ «{field_display}» ត្រូវបានផ្ញើជូន Admin តាមប្រព័ន្ធ Alert ស្វ័យប្រវត្តិតាម Telegram រួចរាល់! Admin នឹងពិនិត្យ និងកែសម្រួលជូនលោកអ្នកឆាប់ៗ។"
        )

        next_url = request.POST.get('next') or request.META.get('HTTP_REFERER')
        if next_url and 'profile' in next_url:
            return redirect('profile')
        elif next_url and 'teachers' in next_url and teacher:
            return redirect('teacher_detail', pk=teacher.id)
        return redirect('profile')

    return redirect('profile')


@login_required
def api_pop_chat_send(request):
    """
    Handles two-way live chat messages between each teacher and the admin.
    - Supports text messages & voice audio messages (MediaRecorder WebM/WAV/MP3).
    - Teachers send requests/messages/voice to Admin (also alerts Admin Telegram).
    - Admin sends direct replies back to specific teachers.
    - Saved into DirectChatMessage table for persistent 1-on-1 thread history.
    """
    import json
    import datetime
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST method is allowed.'}, status=405)

    msg_text = ''
    category = 'profile_correction'
    target_user_id = None
    voice_file = request.FILES.get('voice_file')
    voice_duration = 0

    if request.content_type and 'application/json' in request.content_type:
        try:
            data = json.loads(request.body)
            msg_text = str(data.get('message', '')).strip()
            category = str(data.get('category', 'profile_correction')).strip()
            target_user_id = data.get('target_user_id')
        except Exception:
            pass
    else:
        msg_text = request.POST.get('message', '').strip()
        category = request.POST.get('category', 'profile_correction').strip()
        target_user_id = request.POST.get('target_user_id')
        try:
            voice_duration = int(request.POST.get('voice_duration') or 0)
        except Exception:
            voice_duration = 0

    if not msg_text and not voice_file:
        return JsonResponse({'status': 'error', 'message': 'សូមបញ្ចូលខ្លឹមសារសារ ឬថតសំឡេង!'}, status=400)

    if voice_file and not msg_text:
        msg_text = f"🎙️ សារជាសំឡេង ({voice_duration}s)" if voice_duration > 0 else "🎙️ សារជាសំឡេង (Voice Note)"

    user = request.user
    is_admin = user.role == User.Role.ADMIN or user.is_superuser
    now = datetime.datetime.now()
    now_str = now.strftime('%d-%m-%Y %H:%M')

    if is_admin:
        # Admin sending direct reply to a specific teacher / user
        if not target_user_id:
            return JsonResponse({'status': 'error', 'message': 'សូមជ្រើសរើសគ្រូ ឬគណនីដែលត្រូវឆ្លើយតប!'}, status=400)
        
        target_user = get_object_or_404(User, id=target_user_id)
        chat_msg = DirectChatMessage.objects.create(
            sender=user,
            recipient=target_user,
            message=msg_text,
            voice_file=voice_file,
            voice_duration=voice_duration,
            category=category or DirectChatMessage.Category.ADMIN_RESPONSE,
            is_from_admin=True,
            is_read=False
        )

        return JsonResponse({
            'status': 'success',
            'message_id': chat_msg.id,
            'reply': msg_text,
            'voice_url': chat_msg.voice_file.url if chat_msg.voice_file else '',
            'voice_duration': chat_msg.voice_duration,
            'is_from_admin': True,
            'is_me': True,
            'timestamp': now_str,
            'sender_name': user.display_name
        })

    else:
        # Teacher or standard user sending to Admin
        admin_user = User.objects.filter(role=User.Role.ADMIN).first() or User.objects.filter(is_superuser=True).first()
        chat_msg = DirectChatMessage.objects.create(
            sender=user,
            recipient=admin_user,
            message=msg_text,
            voice_file=voice_file,
            voice_duration=voice_duration,
            category=category or DirectChatMessage.Category.PROFILE_CORRECTION,
            is_from_admin=False,
            is_read=False
        )

        teacher = getattr(user, 'teacher_profile', None)
        student = getattr(user, 'student_profile', None)
        sender_name = user.display_name
        sender_role = user.get_role_display()
        sender_id = teacher.teacher_id if teacher else (student.student_id if student else user.username)
        sender_phone = user.phone or (teacher.phone if teacher else (student.phone if student else '-'))

        cat_map = {
            'profile_correction': '📌 ស្នើសុំកែប្រែព័ត៌មានអត្តសញ្ញាណ (Profile Correction)',
            'general_inquiry': '❓ សាកសួរព័ត៌មានរដ្ឋបាល/ប្រាក់ខែ (General Inquiry)',
            'technical_help': '🛠️ រាយការណ៍បញ្ហាបច្ចេកទេស (Technical Help)',
            'other': '💬 សារទូទៅ (Live Pop Chat)',
        }
        cat_label = cat_map.get(category, '💬 សារពី Pop Chat')

        tg_title = f"💬 Pop Chat: សារស្នើសុំពី {sender_name}"
        tg_msg = (
            f"💬 <b>[សារថ្មីពី Pop Chat On-Screen / Live Chat Request]</b>\n\n"
            f"👤 <b>អ្នកផ្ញើ៖</b> {sender_name} (តួនាទី: <code>{sender_role}</code>)\n"
            f"🆔 <b>កូដសម្គាល់៖</b> <code>{sender_id}</code>\n"
            f"📞 <b>ទូរស័ព្ទ៖</b> <code>{sender_phone or '-'}</code>\n"
            f"🏷️ <b>ប្រភេទសំណើ៖</b> {cat_label}\n\n"
            f"📝 <b>ខ្លឹមសារសារ៖</b>\n<i>«{msg_text}»</i>\n\n"
            f"⏰ <b>ពេលវេលា៖</b> {now_str}\n"
            f"👉 <i>សូម Admin ចូលទៅកាន់ Pop Chat ឬប្រព័ន្ធដើម្បីឆ្លើយតបជូនគ្រូ!</i>"
        )

        send_telegram_notification(
            title=tg_title,
            message=tg_msg,
            recipient_name="Admin / រដ្ឋបាលសាលា",
            recipient_phone=sender_phone,
            recipient_type="Admin"
        )

        reply_msg = (
            f"✅ សារ{'សំឡេង' if voice_file else ''}របស់អ្នកត្រូវបានបញ្ជូនជា **Alert ស្វ័យប្រវត្តិតាម Telegram ទៅកាន់ Admin** រួចរាល់ហើយ!\n"
            f"Admin នឹងពិនិត្យមើល និងធ្វើការឆ្លើយតបជូនលោកអ្នកតាមប្រព័ន្ធ Chat នេះឆាប់ៗ។"
        )

        return JsonResponse({
            'status': 'success',
            'reply': reply_msg,
            'message_id': chat_msg.id,
            'voice_url': chat_msg.voice_file.url if chat_msg.voice_file else '',
            'voice_duration': chat_msg.voice_duration,
            'is_from_admin': False,
            'is_me': True,
            'timestamp': now_str,
            'sender_name': sender_name
        })


@login_required
def api_pop_chat_history(request):
    """
    Returns full two-way message history:
    - For Teachers: returns their 1-on-1 thread with Admin.
    - For Admin: returns the 1-on-1 thread with the selected target teacher.
    """
    from django.db.models import Q
    user = request.user
    is_admin = user.role == User.Role.ADMIN or user.is_superuser
    target_user_id = request.GET.get('target_user_id') or request.GET.get('teacher_id')

    if is_admin:
        if not target_user_id:
            return JsonResponse({'status': 'success', 'messages': []})
        target_user = get_object_or_404(User, id=target_user_id)
        # Mark unread incoming messages from target_user as read
        DirectChatMessage.objects.filter(sender=target_user, is_read=False).update(is_read=True)
        messages_qs = DirectChatMessage.objects.filter(
            Q(sender=target_user) | Q(recipient=target_user)
        ).select_related('sender', 'recipient').order_by('created_at')
    else:
        # For Teacher: mark incoming admin replies as read
        DirectChatMessage.objects.filter(recipient=user, is_from_admin=True, is_read=False).update(is_read=True)
        messages_qs = DirectChatMessage.objects.filter(
            Q(sender=user) | Q(recipient=user)
        ).select_related('sender', 'recipient').order_by('created_at')

    msg_list = []
    for m in messages_qs:
        msg_list.append({
            'id': m.id,
            'sender_id': m.sender_id,
            'sender_name': m.sender.display_name,
            'is_from_admin': m.is_from_admin,
            'is_me': (m.sender_id == user.id),
            'message': m.message,
            'voice_url': m.voice_file.url if m.voice_file else '',
            'voice_duration': m.voice_duration,
            'category': m.get_category_display(),
            'created_at': m.created_at.strftime('%d-%m-%Y %H:%M')
        })

    return JsonResponse({'status': 'success', 'messages': msg_list})


@login_required
def api_pop_chat_threads(request):
    """
    For Admin: returns the list of all teacher conversation threads with unread counts & last message preview.
    """
    from django.db.models import Q, Max
    user = request.user
    is_admin = user.role == User.Role.ADMIN or user.is_superuser
    if not is_admin:
        return JsonResponse({'status': 'error', 'message': 'Access denied.'}, status=403)

    # Get all users who have exchanged chat messages or are teachers
    user_ids_with_chats = set(DirectChatMessage.objects.values_list('sender_id', flat=True)).union(
        set(DirectChatMessage.objects.exclude(recipient__isnull=True).values_list('recipient_id', flat=True))
    )
    user_ids_with_chats.discard(user.id)

    # Add all teachers
    teacher_user_ids = set(User.objects.filter(role=User.Role.TEACHER).values_list('id', flat=True))
    all_target_user_ids = user_ids_with_chats.union(teacher_user_ids)

    threads = []
    for uid in all_target_user_ids:
        u = User.objects.filter(id=uid).select_related('teacher_profile').first()
        if not u or u.role == User.Role.ADMIN:
            continue

        teacher = getattr(u, 'teacher_profile', None)
        identifier = teacher.teacher_id if teacher else u.username
        unread_count = DirectChatMessage.objects.filter(sender=u, is_read=False).count()
        last_msg = DirectChatMessage.objects.filter(Q(sender=u) | Q(recipient=u)).order_by('-created_at').first()

        threads.append({
            'user_id': u.id,
            'name': u.display_name,
            'role': u.get_role_display(),
            'identifier': identifier,
            'phone': u.phone or (teacher.phone if teacher else '-'),
            'unread_count': unread_count,
            'last_message': last_msg.message if last_msg else 'មិនទាន់មានសារ',
            'last_message_time': last_msg.created_at.strftime('%d-%m %H:%M') if last_msg else '',
            'last_timestamp': last_msg.created_at.timestamp() if last_msg else 0
        })

    # Sort threads: unread first, then newest message
    threads.sort(key=lambda x: (x['unread_count'] > 0, x['last_timestamp']), reverse=True)

    return JsonResponse({'status': 'success', 'threads': threads})


@login_required
@role_required(['ADMIN'])
def telegram_settings_view(request):
    config = TelegramConfig.objects.first()
    if not config:
        config = TelegramConfig.objects.create()

    if request.method == 'POST':
        if 'test_message' in request.POST:
            test_msg = request.POST.get('message_text', 'សួស្តី! នេះជាសារសាកល្បងពីប្រព័ន្ធគ្រប់គ្រងសាលារៀន (SchoolSM).')
            log = send_telegram_notification("សារសាកល្បង / Test Alert", test_msg, recipient_name="អ្នកគ្រប់គ្រង")
            if log.status == NotificationLog.Status.SENT:
                messages.success(request, "បានផ្ញើសារ Telegram ទៅកាន់ Channel/Chat ជោគជ័យ!")
            else:
                messages.warning(request, f"បានកត់ត្រាសារក្នុងប្រព័ន្ធ (ស្ថានភាព: {log.get_status_display()})។ ប្រសិនបើចង់ផ្ញើពិតប្រាកដ សូមបញ្ចូល Telegram Bot Token និង Chat ID ត្រឹមត្រូវ។")
            return redirect('telegram_settings')
            
        form = TelegramConfigForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, "បានរក្សាទុកការកំណត់ Telegram Bot ជោគជ័យ!")
            return redirect('telegram_settings')
    else:
        form = TelegramConfigForm(instance=config)

    logs = NotificationLog.objects.all()[:20]
    return render(request, 'accounts/telegram_settings.html', {'form': form, 'config': config, 'logs': logs})


@login_required
@role_required(['ADMIN'])
def school_profile_settings_view(request):
    """
    Dedicated view for School Information, Identity, Logos, MoEYS Hierarchy & Location Settings
    """
    school_profile = SchoolProfile.get_settings()

    if request.method == 'POST':
        form = SchoolProfileForm(request.POST, request.FILES, instance=school_profile)
        if form.is_valid():
            form.save()
            messages.success(request, "បានរក្សាទុក និងធ្វើបច្ចុប្បន្នភាពព័ត៌មានសាលារៀនជោគជ័យ!")
            return redirect('school_profile_settings')
        else:
            messages.error(request, "មានបញ្ហាក្នុងការរក្សាទុក! សូមពិនិត្យមើលទិន្នន័យដែលបានបញ្ចូលឡើងវិញ។")
    else:
        form = SchoolProfileForm(instance=school_profile)

    return render(request, 'accounts/school_settings.html', {
        'form': form,
        'school_profile': school_profile,
    })


import json
from django.views.decorators.csrf import csrf_exempt
from apps.accounts.utils import edit_telegram_message, answer_telegram_callback_query
from apps.attendance.telegram_utils import process_teacher_leave_action


@csrf_exempt
def telegram_webhook(request):
    """
    Receives incoming updates from Telegram Webhook.
    Handles callback_query for interactive inline buttons:
    - leave:approve:<leave_id>
    - leave:reject:<leave_id>
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'ok', 'message': 'Telegram webhook active. POST required.'})

    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

    # 1. Handle Callback Query (Button clicks)
    if 'callback_query' in data:
        cb = data['callback_query']
        cb_id = cb.get('id')
        cb_data = cb.get('data', '')
        user_info = cb.get('from', {})
        first_name = user_info.get('first_name', '')
        username = user_info.get('username')
        user_disp = f"{first_name} (@{username})" if username else (first_name or "Admin តាម Telegram")
        
        msg = cb.get('message', {})
        chat_id = msg.get('chat', {}).get('id')
        message_id = msg.get('message_id')

        if cb_data.startswith('leave:'):
            parts = cb_data.split(':') # ['leave', 'approve'/'reject', '<id>']
            if len(parts) >= 3:
                action = parts[1]
                leave_id = parts[2]
                res = process_teacher_leave_action(
                    leave_id=leave_id,
                    action=action,
                    approver_name=user_disp
                )

                # Show pop-up toast in Telegram
                toast_text = res.get('message', 'បានដំណើរការរួចរាល់!')
                answer_telegram_callback_query(cb_id, text=toast_text, show_alert=True)

                # Edit message to update status and remove action buttons
                if chat_id and message_id and 'updated_text' in res:
                    edit_telegram_message(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=res['updated_text'],
                        reply_markup=None
                    )

                clean_res = {
                    'success': res.get('success', False),
                    'message': res.get('message', ''),
                    'action': res.get('action', ''),
                    'leave_id': leave_id
                }
                return JsonResponse({'status': 'ok', 'result': clean_res})

        elif cb_data.startswith('feepay:'):
            from apps.finance.telegram_bot import process_telegram_fee_callback
            res = process_telegram_fee_callback(cb_data, user_disp, chat_id, message_id)
            toast_text = res.get('message', 'បានកត់ត្រារួចរាល់!')
            answer_telegram_callback_query(cb_id, text=toast_text, show_alert=True)
            if chat_id and message_id and 'updated_text' in res:
                edit_telegram_message(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=res['updated_text'],
                    reply_markup=None
                )
            return JsonResponse({'status': 'ok', 'result': res})

    # 2. Handle Text Messages & Bot Commands
    if 'message' in data:
        msg = data['message']
        text = msg.get('text', '')
        if text.startswith(('/fees', '/fee', '/due', '/pay', '/collect')):
            from apps.finance.telegram_bot import handle_telegram_fees_message
            handle_telegram_fees_message(msg)
            return JsonResponse({'status': 'ok'})

    return JsonResponse({'status': 'ok'})


from .menu_registry import (
    get_menu_catalog,
    get_role_permissions_map,
    set_role_permission,
    reset_role_permissions,
    create_menu_item,
    update_menu_item,
    delete_menu_item,
    MENU_SECTIONS_CATALOG,
)


@login_required
@role_required(['ADMIN'])
def menu_permissions_view(request):
    """
    Dedicated visual portal for Admin to configure menu and submenu access permissions
    for Teachers, Students/Parents, and Accountants.
    """
    catalog = get_menu_catalog()
    
    available_roles = [
        ('TEACHER', 'គ្រូបង្រៀន (Teacher)', 'fa-chalkboard-user', 'warning'),
        ('STUDENT', 'សិស្ស និងអាណាព្យាបាល (Student & Parent)', 'fa-user-graduate', 'info'),
        ('ACCOUNTANT', 'គណនេយ្យករ (Accountant)', 'fa-wallet', 'success'),
    ]
    
    role_keys = [r[0] for r in available_roles]
    active_role = request.GET.get('role', 'TEACHER')
    if active_role not in role_keys:
        active_role = 'TEACHER'

    if request.method == 'POST':
        # Batch save from standard form submission
        selected_role = request.POST.get('target_role', active_role)
        if selected_role in role_keys:
            # For each catalog section and item, check if checked in POST
            for section in catalog:
                sec_key = section['key']
                sec_allowed = (sec_key in request.POST)
                set_role_permission(selected_role, sec_key, sec_allowed)

                for item in section.get('items', []):
                    item_key = item['key']
                    item_allowed = (item_key in request.POST)
                    set_role_permission(selected_role, item_key, item_allowed)

            role_dict = dict((r[0], r[1]) for r in available_roles)
            messages.success(request, f"បានរក្សាទុកការកំណត់សិទ្ធិ Menu សម្រាប់ {role_dict.get(selected_role)} ជោគជ័យ!")
            return redirect(f"{request.path}?role={selected_role}")

    # Compute permission map for active role
    role_perms = get_role_permissions_map(active_role)
    
    # Prepare enriched catalog with is_allowed for direct template rendering
    import copy
    catalog_display = copy.deepcopy(catalog)
    total_items = 0
    allowed_count = 0
    for section in catalog_display:
        section['is_allowed'] = role_perms.get(section['key'], False)
        for item in section.get('items', []):
            total_items += 1
            item_is_allowed = role_perms.get(item['key'], False)
            item['is_allowed'] = item_is_allowed
            if item_is_allowed:
                allowed_count += 1

    return render(request, 'accounts/menu_permissions.html', {
        'catalog': catalog_display,
        'active_role': active_role,
        'available_roles': available_roles,
        'role_perms': role_perms,
        'total_items': total_items,
        'allowed_count': allowed_count,
        'disallowed_count': total_items - allowed_count,
    })


@login_required
@role_required(['ADMIN'])
def api_toggle_menu_permission(request):
    """
    AJAX endpoint for instant toggle of individual menu/submenu permission.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST request required'}, status=400)

    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body.decode('utf-8'))
        else:
            data = request.POST
        
        role = data.get('role')
        menu_key = data.get('menu_key')
        is_allowed = data.get('is_allowed')

        if isinstance(is_allowed, str):
            is_allowed = is_allowed.lower() in ['true', '1', 'yes', 'on']
        else:
            is_allowed = bool(is_allowed)

        if not role or not menu_key:
            return JsonResponse({'status': 'error', 'message': 'Role and Menu Key are required.'}, status=400)

        set_role_permission(role, menu_key, is_allowed)
        
        # Recalculate full perms to return updated state
        updated_perms = get_role_permissions_map(role)

        return JsonResponse({
            'status': 'success',
            'role': role,
            'menu_key': menu_key,
            'is_allowed': is_allowed,
            'updated_perms': updated_perms,
            'message': 'បានកែប្រែសិទ្ធិដោយជោគជ័យ'
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@role_required(['ADMIN'])
def api_bulk_menu_permission(request):
    """
    AJAX endpoint for bulk actions: allow_all, disallow_all, or reset_default for a role.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST request required'}, status=400)

    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body.decode('utf-8'))
        else:
            data = request.POST

        role = data.get('role')
        action = data.get('action') # 'allow_all', 'disallow_all', 'reset_default'

        if not role:
            return JsonResponse({'status': 'error', 'message': 'Role is required.'}, status=400)

        catalog = get_menu_catalog()

        if action == 'reset_default':
            reset_role_permissions(role)
            msg = "បានកំណត់សិទ្ធិឡើងវិញទៅតាមលំនាំដើម (Default) ជោគជ័យ!"
        elif action == 'allow_all':
            for section in catalog:
                set_role_permission(role, section['key'], True)
                for item in section.get('items', []):
                    set_role_permission(role, item['key'], True)
            msg = "បានបើកសិទ្ធិប្រើប្រាស់ Menu ទាំងអស់ជោគជ័យ!"
        elif action == 'disallow_all':
            for section in catalog:
                set_role_permission(role, section['key'], False)
                for item in section.get('items', []):
                    set_role_permission(role, item['key'], False)
            msg = "បានបិទសិទ្ធិ Menu ទាំងអស់ជោគជ័យ!"
        else:
            return JsonResponse({'status': 'error', 'message': 'Invalid action'}, status=400)

        updated_perms = get_role_permissions_map(role)
        return JsonResponse({
            'status': 'success',
            'role': role,
            'action': action,
            'message': msg,
            'updated_perms': updated_perms
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@role_required(['ADMIN'])
def api_create_menu_item(request):
    """
    AJAX / POST endpoint for Admin to add a new menu/submenu item dynamically.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=400)

    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body.decode('utf-8'))
        else:
            data = request.POST

        section_id = data.get('section_id')
        code = data.get('code', '').strip().replace(' ', '_').lower()
        name_kh = data.get('name_kh', '').strip()
        name_en = data.get('name_en', '').strip()
        icon = data.get('icon', 'fa-solid fa-circle-dot').strip()
        url_name = data.get('url_name', '').strip() or None
        custom_url = data.get('custom_url', '').strip() or None
        is_admin_only = bool(data.get('is_admin_only', False))
        roles = data.get('roles', ['ADMIN', 'TEACHER', 'STUDENT', 'ACCOUNTANT'])
        if isinstance(roles, str):
            roles = [r.strip() for r in roles.split(',') if r.strip()]

        if not section_id or not code or not name_kh:
            return JsonResponse({'status': 'error', 'message': 'សូមបញ្ចូល ផ្នែកម៉ឺនុយ, កូដម៉ឺនុយ និងឈ្មោះខ្មែរ ឱ្យបានត្រឹមត្រូវ!'}, status=400)

        if MenuItem.objects.filter(code=code).exists():
            return JsonResponse({'status': 'error', 'message': f'កូដម៉ឺនុយ "{code}" មានរួចហើយក្នុងប្រព័ន្ធ!'}, status=400)

        item = create_menu_item(
            section_id=section_id,
            code=code,
            name_kh=name_kh,
            name_en=name_en or name_kh,
            icon=icon,
            url_name=url_name,
            custom_url=custom_url,
            default_roles=roles,
            is_admin_only=is_admin_only
        )

        return JsonResponse({
            'status': 'success',
            'message': f'បានបង្កើត Menu "{item.name_kh}" ជោគជ័យ និងរក្សាទុកក្នុង Database!',
            'item_id': item.id,
            'code': item.code
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@role_required(['ADMIN'])
def api_edit_menu_item(request, item_id):
    """
    AJAX / POST endpoint for Admin to edit an existing menu/submenu item.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=400)

    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body.decode('utf-8'))
        else:
            data = request.POST

        name_kh = data.get('name_kh', '').strip()
        name_en = data.get('name_en', '').strip()
        icon = data.get('icon', 'fa-solid fa-circle-dot').strip()
        url_name = data.get('url_name', '').strip() or None
        custom_url = data.get('custom_url', '').strip() or None
        is_admin_only = bool(data.get('is_admin_only', False))

        if not name_kh:
            return JsonResponse({'status': 'error', 'message': 'សូមបញ្ចូលឈ្មោះម៉ឺនុយជាភាសាខ្មែរ!'}, status=400)

        item = update_menu_item(
            item_id=item_id,
            name_kh=name_kh,
            name_en=name_en or name_kh,
            icon=icon,
            url_name=url_name,
            custom_url=custom_url,
            is_admin_only=is_admin_only
        )

        return JsonResponse({
            'status': 'success',
            'message': f'បានកែប្រែ Menu "{item.name_kh}" ជោគជ័យក្នុង Database!',
            'item_id': item.id,
            'name_kh': item.name_kh,
            'name_en': item.name_en,
            'icon': item.icon
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@role_required(['ADMIN'])
def api_delete_menu_item(request, item_id):
    """
    AJAX / POST endpoint for Admin to delete a menu/submenu item from database.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=400)

    try:
        item = get_object_or_404(MenuItem, id=item_id)
        item_name = item.name_kh
        delete_menu_item(item_id)
        return JsonResponse({
            'status': 'success',
            'message': f'បានលុប Menu "{item_name}" ចេញពី Database ដោយជោគជ័យ!'
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


from .search_service import global_omnisearch


@login_required
def api_global_search(request):
    """
    JSON API for Omnisearch Command Palette (Ctrl+K).
    Returns instant matching suggestions with titles, icons, categories, and URLs.
    """
    query = request.GET.get('q', '').strip()
    results = global_omnisearch(query, user=request.user, limit=12)
    return JsonResponse({'results': results})



