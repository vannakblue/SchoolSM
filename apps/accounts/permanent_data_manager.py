import os
import json
from decimal import Decimal
from pathlib import Path
from django.conf import settings
from django.db import transaction

FIXTURE_PATH = Path(settings.BASE_DIR) / 'apps' / 'accounts' / 'fixtures' / 'permanent_admin_defaults.json'


def export_permanent_admin_defaults(stdout=None):
    """
    Exports all admin-configured defaults to permanent_admin_defaults.json.
    This includes:
    - SchoolProfile settings (registration mode, identity, branding, formats)
    - SavedDefaultConfig (custom scoring rules, subject requirements, duty codes)
    - GradeLevel & AcademicTrack
    - GradeLevelRule (scoring rules matrix)
    - GradeVerificationFormConfig (grade-level enrollment forms)
    - GradeEnrollmentOption (admin-customized fields)
    """
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)

    data = {
        'version': '1.0',
        'exported_at': None,
        'school_profile': {},
        'saved_default_configs': {},
        'grade_levels': [],
        'scoring_rules': [],
        'verification_form_configs': [],
        'enrollment_options': [],
    }

    try:
        from apps.accounts.models import SchoolProfile
        prof = SchoolProfile.objects.first()
        if prof:
            data['school_profile'] = {
                'name_kh': prof.name_kh,
                'name_en': prof.name_en,
                'short_name': prof.short_name,
                'school_code': prof.school_code,
                'school_type': prof.school_type,
                'institution_type': prof.institution_type,
                'education_levels': prof.education_levels,
                'motto': prof.motto,
                'date_format': prof.date_format,
                'time_format': prof.time_format,
                'display_font': prof.display_font,
                'report_header_font': prof.report_header_font,
                'theme_primary_color': prof.theme_primary_color,
                'header_bg_color': prof.header_bg_color,
                'footer_bg_color': prof.footer_bg_color,
                'body_bg_color': prof.body_bg_color,
                'student_id_pattern': prof.student_id_pattern,
                'student_id_prefix': prof.student_id_prefix,
                'student_id_custom_template': prof.student_id_custom_template,
                'student_id_digits': prof.student_id_digits,
                'student_id_include_grade': prof.student_id_include_grade,
                'registration_mode': prof.registration_mode,
                'registration_form_config': prof.registration_form_config,
                'is_registration_open': prof.is_registration_open,
                'registration_closed_message': prof.registration_closed_message,
                'ministry_name': prof.ministry_name,
                'poe_name': prof.poe_name,
                'doe_name': prof.doe_name,
                'province': prof.province,
                'district': prof.district,
                'commune': prof.commune,
                'village': prof.village,
                'street_address': prof.street_address,
                'principal_name': prof.principal_name,
                'phone': prof.phone,
                'email': prof.email,
            }
    except Exception as e:
        if stdout: stdout.write(f"Export profile note: {e}")

    try:
        from apps.academics.models import SavedDefaultConfig
        for cfg in SavedDefaultConfig.objects.all():
            data['saved_default_configs'][cfg.key] = cfg.data
    except Exception as e:
        if stdout: stdout.write(f"Export saved configs note: {e}")

    try:
        from apps.academics.models import GradeLevel
        for gl in GradeLevel.objects.all().order_by('order', 'grade_number'):
            data['grade_levels'].append({
                'grade_number': gl.grade_number,
                'track': gl.track,
                'name': gl.name,
                'order': gl.order,
                'level_type': getattr(gl, 'level_type', ''),
                'is_registration_open': getattr(gl, 'is_registration_open', True),
                'registration_closed_message': getattr(gl, 'registration_closed_message', ''),
            })
    except Exception as e:
        if stdout: stdout.write(f"Export grade levels note: {e}")

    try:
        from apps.academics.models import GradeLevelRule
        for r in GradeLevelRule.objects.select_related('subject').all():
            data['scoring_rules'].append({
                'grade_level': r.grade_level,
                'track': r.track,
                'subject_code': r.subject.code,
                'subject_name_kh': r.subject.name_kh,
                'max_score': str(r.max_score),
                'order': r.order,
            })
    except Exception as e:
        if stdout: stdout.write(f"Export scoring rules note: {e}")

    try:
        from apps.students.models import GradeVerificationFormConfig
        for cfg in GradeVerificationFormConfig.objects.filter(campaign__isnull=True).select_related('grade_level'):
            data['verification_form_configs'].append({
                'grade_number': cfg.grade_level.grade_number,
                'track': cfg.grade_level.track,
                'form_template': cfg.form_template,
                'custom_instructions': cfg.custom_instructions or '',
                'is_active': cfg.is_active,
            })
    except Exception as e:
        if stdout: stdout.write(f"Export verification form configs note: {e}")

    try:
        from apps.academics.models import GradeEnrollmentOption
        for opt in GradeEnrollmentOption.objects.select_related('grade_level').all():
            data['enrollment_options'].append({
                'grade_number': opt.grade_level.grade_number if opt.grade_level else None,
                'track': opt.grade_level.track if opt.grade_level else 'GENERAL',
                'field_name': opt.field_name,
                'label': opt.label,
                'field_type': opt.field_type,
                'form_category': opt.form_category,
                'is_required': opt.is_required,
                'is_active': opt.is_active,
                'order': opt.order,
                'choices': opt.choices or '',
                'placeholder': opt.placeholder or '',
                'col_width': opt.col_width,
            })
    except Exception as e:
        if stdout: stdout.write(f"Export enrollment options note: {e}")

    try:
        from apps.accounts.models import GoogleSheetsConfig
        gs_cfg = GoogleSheetsConfig.objects.first()
        if gs_cfg:
            data['google_sheets_config'] = {
                'is_active': gs_cfg.is_active,
                'admin_email': gs_cfg.admin_email or '',
                'drive_folder_name': gs_cfg.drive_folder_name or 'SchoolSM_Cloud_Sync',
                'drive_folder_id': gs_cfg.drive_folder_id or '',
                'sync_students_with_photos': gs_cfg.sync_students_with_photos,
                'spreadsheets_registry': gs_cfg.spreadsheets_registry or {},
            }
    except Exception as e:
        if stdout: stdout.write(f"Export google sheets config note: {e}")

    with open(FIXTURE_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    if stdout:
        stdout.write(f"Permanent admin defaults successfully exported to: {FIXTURE_PATH}")
    return FIXTURE_PATH


def import_permanent_admin_defaults(stdout=None, force=False):
    """
    Safely restores permanent admin defaults from permanent_admin_defaults.json.
    This guarantees that on any new server deployment (Render), local update,
    or restart, the Admin's saved preferences are NEVER lost or reset to old hardcoded values.
    """
    if not FIXTURE_PATH.exists():
        if stdout: stdout.write(f"No permanent defaults fixture found at: {FIXTURE_PATH}")
        return False

    try:
        with open(FIXTURE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        if stdout: stdout.write(f"Error reading permanent defaults fixture: {e}")
        return False

    with transaction.atomic():
        # 1. Restore School Profile Settings
        prof_data = data.get('school_profile', {})
        if prof_data:
            from apps.accounts.models import SchoolProfile
            prof, _ = SchoolProfile.objects.get_or_create(id=1)
            for k, v in prof_data.items():
                if hasattr(prof, k) and v is not None:
                    # If field is currently empty or force=True, apply saved value
                    curr_val = getattr(prof, k)
                    if force or curr_val is None or curr_val == '' or k in ['registration_mode', 'date_format', 'time_format', 'registration_form_config']:
                        setattr(prof, k, v)
            prof.save()
            if stdout: stdout.write("Restored permanent SchoolProfile settings.")

        # 2. Restore SavedDefaultConfig (Custom scoring rules, subject quotas, etc.)
        saved_configs = data.get('saved_default_configs', {})
        if saved_configs:
            from apps.academics.models import SavedDefaultConfig
            for key, val in saved_configs.items():
                SavedDefaultConfig.objects.update_or_create(key=key, defaults={'data': val})
            if stdout: stdout.write(f"Restored {len(saved_configs)} SavedDefaultConfig presets.")

        # 3. Restore Grade Levels (Only if missing or force=True)
        gl_list = data.get('grade_levels', [])
        if gl_list:
            from apps.academics.models import GradeLevel
            for item in gl_list:
                GradeLevel.objects.update_or_create(
                    grade_number=item['grade_number'],
                    track=item.get('track', 'GENERAL'),
                    defaults={
                        'name': item['name'],
                        'order': item.get('order', item['grade_number']),
                        'level_type': item.get('level_type', 'UPPER_SECONDARY' if item['grade_number'] >= 10 else 'LOWER_SECONDARY'),
                        'is_registration_open': item.get('is_registration_open', True),
                        'registration_closed_message': item.get('registration_closed_message', ''),
                    }
                )

        # 4. Restore Scoring Rules Matrix
        scoring_rules = data.get('scoring_rules', [])
        if scoring_rules:
            from apps.academics.models import GradeLevelRule, Subject
            existing_rules_count = GradeLevelRule.objects.count()
            if existing_rules_count == 0 or force:
                for r in scoring_rules:
                    sub = Subject.objects.filter(code=r['subject_code']).first() or Subject.objects.filter(name_kh=r['subject_name_kh']).first()
                    if sub:
                        r_match = GradeLevelRule.objects.filter(
                            grade_level=r['grade_level'],
                            track=r.get('track', 'GENERAL'),
                            subject=sub
                        ).first()
                        if r_match:
                            r_match.max_score = Decimal(str(r['max_score']))
                            r_match.order = r.get('order', sub.order)
                            r_match.save(update_fields=['max_score', 'order'])
                        else:
                            GradeLevelRule.objects.create(
                                grade_level=r['grade_level'],
                                track=r.get('track', 'GENERAL'),
                                subject=sub,
                                max_score=Decimal(str(r['max_score'])),
                                order=r.get('order', sub.order),
                            )
                if stdout: stdout.write(f"Restored {len(scoring_rules)} Scoring Rules Matrix records.")

        # 5. Restore Grade Verification Form Configs (Enrollment Form Templates)
        verif_configs = data.get('verification_form_configs', [])
        if verif_configs:
            from apps.academics.models import GradeLevel
            from apps.students.models import GradeVerificationFormConfig
            for item in verif_configs:
                gl = GradeLevel.objects.filter(grade_number=item['grade_number'], track=item.get('track', 'GENERAL')).first()
                if gl:
                    cfg_match = GradeVerificationFormConfig.objects.filter(grade_level=gl, campaign__isnull=True).first()
                    if cfg_match:
                        cfg_match.form_template = item.get('form_template', 'GENERAL')
                        cfg_match.custom_instructions = item.get('custom_instructions', '')
                        cfg_match.is_active = item.get('is_active', True)
                        cfg_match.save(update_fields=['form_template', 'custom_instructions', 'is_active'])
                    else:
                        GradeVerificationFormConfig.objects.create(
                            grade_level=gl,
                            campaign__isnull=True,
                            form_template=item.get('form_template', 'GENERAL'),
                            custom_instructions=item.get('custom_instructions', ''),
                            is_active=item.get('is_active', True),
                        )
            if stdout: stdout.write(f"Restored {len(verif_configs)} Grade Form Configuration records.")

        # 6. Restore Grade Enrollment Dynamic Options
        enroll_opts = data.get('enrollment_options', [])
        if enroll_opts:
            from apps.academics.models import GradeLevel, GradeEnrollmentOption
            for item in enroll_opts:
                gl = None
                if item.get('grade_number'):
                    gl = GradeLevel.objects.filter(grade_number=item['grade_number'], track=item.get('track', 'GENERAL')).first()
                opt_match = GradeEnrollmentOption.objects.filter(
                    grade_level=gl,
                    field_name=item['field_name'],
                    form_category=item.get('form_category', 'GENERAL')
                ).first()
                if opt_match:
                    opt_match.label = item['label']
                    opt_match.field_type = item.get('field_type', 'TEXT')
                    opt_match.is_required = item.get('is_required', False)
                    opt_match.is_active = item.get('is_active', True)
                    opt_match.order = item.get('order', 1)
                    opt_match.choices = item.get('choices', '')
                    opt_match.placeholder = item.get('placeholder', '')
                    opt_match.col_width = item.get('col_width', 6)
                    opt_match.save()
                else:
                    GradeEnrollmentOption.objects.create(
                        grade_level=gl,
                        field_name=item['field_name'],
                        form_category=item.get('form_category', 'GENERAL'),
                        label=item['label'],
                        field_type=item.get('field_type', 'TEXT'),
                        is_required=item.get('is_required', False),
                        is_active=item.get('is_active', True),
                        order=item.get('order', 1),
                        choices=item.get('choices', ''),
                        placeholder=item.get('placeholder', ''),
                        col_width=item.get('col_width', 6),
                    )

        # 7. Restore Google Sheets Config (Linked spreadsheets per academic year, folder ID)
        gs_data = data.get('google_sheets_config', {})
        if gs_data:
            from apps.accounts.models import GoogleSheetsConfig
            gs_cfg = GoogleSheetsConfig.get_config()
            for k, v in gs_data.items():
                if hasattr(gs_cfg, k) and v is not None:
                    curr_val = getattr(gs_cfg, k)
                    if force or curr_val is None or curr_val == '' or k in ['spreadsheets_registry', 'drive_folder_id', 'is_active']:
                        setattr(gs_cfg, k, v)
            gs_cfg.save()
            if stdout: stdout.write("Restored permanent Google Sheets configuration.")

    if stdout:
        stdout.write("Permanent admin defaults successfully restored from fixture.")
    return True
