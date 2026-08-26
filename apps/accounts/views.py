from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .forms import LoginForm, UserProfileForm, TelegramConfigForm, SchoolProfileForm
from .models import User, TelegramConfig, NotificationLog, SchoolProfile, MenuSection, MenuItem, RoleMenuPermission
from .decorators import role_required
from .utils import send_telegram_notification

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')
    
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"សូមស្វាគមន៍ {user.display_name}! ចូលប្រព័ន្ធជោគជ័យ។")
            return redirect('dashboard_redirect')
        else:
            messages.error(request, "ឈ្មោះគណនី ឬពាក្យសម្ងាត់មិនត្រឹមត្រូវទេ!")
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form})


def demo_login_view(request, role):
    """
    1-Click Demo Login to switch between Super Admin, Accountant, Teacher, and Student
    """
    user = User.objects.filter(role=role).first()
    if not user:
        if role == 'ADMIN':
            user = User.objects.filter(is_superuser=True).first()
    
    if user:
        login(request, user)
        messages.success(request, f"បានចូលប្រើប្រាស់ជា {user.get_role_display()} ({user.display_name})")
        return redirect('dashboard_redirect')
    else:
        messages.error(request, f"មិនទាន់មានគណនីសម្រាប់តួនាទី {role} នៅឡើយទេ! សូមដំណើរការ Seed Data ជាមុនសិន។")
        return redirect('login')


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
    
    return render(request, 'accounts/profile.html', {'form': form, 'user_obj': user})


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



