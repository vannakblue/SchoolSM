from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserChangeForm
from .models import User, TelegramConfig, SchoolProfile, GeminiAiConfig

class LoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'ឈ្មោះគណនី / Username',
            'autocomplete': 'username',
            'id': 'username_input'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'ពាក្យសម្ងាត់ / Password',
            'autocomplete': 'current-password',
            'id': 'password_input'
        })
    )


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['khmer_name', 'latin_name', 'email', 'phone', 'avatar']
        widgets = {
            'khmer_name': forms.TextInput(attrs={'class': 'form-control'}),
            'latin_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'avatar': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.role == User.Role.TEACHER:
            self.fields['khmer_name'].disabled = True
            self.fields['latin_name'].disabled = True
            self.fields['khmer_name'].help_text = "🔒 ព័ត៌មានអត្តសញ្ញាណត្រូវបានចាក់សោ (សូមស្នើសុំទៅ Admin ដើម្បីកែប្រែ)"
            self.fields['latin_name'].help_text = "🔒 ព័ត៌មានអត្តសញ្ញាណត្រូវបានចាក់សោ (សូមស្នើសុំទៅ Admin ដើម្បីកែប្រែ)"


class TelegramConfigForm(forms.ModelForm):
    class Meta:
        model = TelegramConfig
        fields = ['bot_token', 'chat_id', 'is_active', 'notify_on_absence', 'notify_on_exam', 'notify_on_fee']
        widgets = {
            'bot_token': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ'}),
            'chat_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. -100123456789 or @school_channel'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_on_absence': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_on_exam': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_on_fee': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class SchoolProfileForm(forms.ModelForm):
    class Meta:
        model = SchoolProfile
        fields = [
            'name_kh', 'name_en', 'short_name', 'short_name_en', 'school_code', 'school_type', 'school_type_en', 'institution_type', 'education_levels', 'education_levels_en', 'date_format', 'time_format', 'motto', 'motto_en',
            'about_school', 'about_school_en',
            'student_id_pattern', 'student_id_prefix', 'student_id_custom_template', 'student_id_digits', 'student_id_include_grade',
            'registration_mode',
            'is_registration_open', 'registration_start_date', 'registration_end_date', 'registration_closed_message',
            'allow_student_self_update', 'student_update_closed_message',
            'logo', 'seal', 'principal_signature',
            'ministry_name', 'ministry_name_en', 'poe_name', 'poe_name_en', 'doe_name', 'doe_name_en',
            'province', 'district', 'commune', 'commune_en', 'village', 'village_en', 'street_address', 'street_address_en',
            'latitude', 'longitude', 'google_maps_url', 'gps_radius_meters',
            'principal_name', 'principal_name_en', 'phone', 'email', 'website', 'facebook_page', 'telegram_channel',
            'display_font', 'report_header_font', 'theme_primary_color', 'header_bg_color', 'footer_bg_color', 'body_bg_color',
        ]
        widgets = {
            'name_kh': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. វិទ្យាល័យ ហ៊ុន សែន កំពង់កន្ទួត'}),
            'name_en': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Hun Sen Kampong Kantuot High School'}),
            'short_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. វិ. ហស កំពង់កន្ទួត'}),
            'short_name_en': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. HS Kampong Kantuot High School'}),
            'school_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. 08010306901'}),
            'school_type': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. វិទ្យាល័យ'}),
            'school_type_en': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. General High School'}),
            'institution_type': forms.Select(attrs={'class': 'form-select'}),
            'education_levels': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. មត្តេយ្យ, បឋមសិក្សា, អនុវិទ្យាល័យ, វិទ្យាល័យ'}),
            'education_levels_en': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Secondary & High School'}),
            'date_format': forms.Select(attrs={'class': 'form-select fw-bold border-primary'}),
            'time_format': forms.Select(attrs={'class': 'form-select fw-bold border-primary'}),
            'display_font': forms.Select(attrs={'class': 'form-select fw-bold border-primary', 'id': 'id_display_font'}),
            'report_header_font': forms.Select(attrs={'class': 'form-select fw-bold border-primary', 'id': 'id_report_header_font'}),
            'theme_primary_color': forms.TextInput(attrs={'class': 'form-control form-control-color w-100', 'type': 'color', 'id': 'id_theme_primary_color'}),
            'header_bg_color': forms.TextInput(attrs={'class': 'form-control form-control-color w-100', 'type': 'color', 'id': 'id_header_bg_color'}),
            'footer_bg_color': forms.TextInput(attrs={'class': 'form-control form-control-color w-100', 'type': 'color', 'id': 'id_footer_bg_color'}),
            'body_bg_color': forms.TextInput(attrs={'class': 'form-control form-control-color w-100', 'type': 'color', 'id': 'id_body_bg_color'}),
            'motto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. ចំណេះដឹង វិន័យ សីលធម៌ គុណធម៌'}),
            'motto_en': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Knowledge, Discipline, Morality, Virtue'}),
            'about_school': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'ពិពណ៌នាអំពីសាលារៀន ចក្ខុវិស័យ និងបេសកកម្ម...'}),
            'about_school_en': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Describe school vision, mission and values in English...'}),
            'student_id_pattern': forms.Select(attrs={'class': 'form-select fw-bold border-primary', 'id': 'id_student_id_pattern'}),
            'student_id_prefix': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_student_id_prefix', 'placeholder': 'ឧ. STU'}),
            'student_id_custom_template': forms.TextInput(attrs={'class': 'form-control font-monospace', 'id': 'id_student_id_custom_template', 'placeholder': '{PREFIX}-{YEAR2}-{SEQ}'}),
            'student_id_digits': forms.Select(attrs={'class': 'form-select', 'id': 'id_student_id_digits'}),
            'student_id_include_grade': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_student_id_include_grade'}),
            'registration_mode': forms.Select(attrs={'class': 'form-select fw-bold border-primary', 'id': 'id_registration_mode'}),
            'is_registration_open': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_is_registration_open'}),
            'registration_start_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local', 'id': 'id_registration_start_date'}),
            'registration_end_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local', 'id': 'id_registration_end_date'}),
            'registration_closed_message': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'សារជូនដំណឹងពេលបិទ ឬផុតកំណត់ការចុះឈ្មោះ'}),
            'allow_student_self_update': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_allow_student_self_update'}),
            'student_update_closed_message': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'សារជូនដំណឹងពេលបិទការកែប្រែព័ត៌មានសិស្ស'}),
            
            'logo': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*', 'id': 'id_logo'}),
            'seal': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*', 'id': 'id_seal'}),
            'principal_signature': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*', 'id': 'id_principal_signature'}),

            'ministry_name': forms.TextInput(attrs={'class': 'form-control'}),
            'ministry_name_en': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Ministry of Education, Youth and Sport'}),
            'poe_name': forms.TextInput(attrs={'class': 'form-control'}),
            'poe_name_en': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Provincial Department of Education'}),
            'doe_name': forms.TextInput(attrs={'class': 'form-control'}),
            'doe_name_en': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. District Office of Education'}),

            'province': forms.TextInput(attrs={'class': 'form-control', 'id': 'input_province', 'placeholder': 'ឧ. ខេត្តកណ្ដាល'}),
            'district': forms.TextInput(attrs={'class': 'form-control', 'id': 'input_district', 'placeholder': 'ឧ. ស្រុកកណ្ដាលស្ទឹង'}),
            'commune': forms.TextInput(attrs={'class': 'form-control', 'id': 'input_commune', 'placeholder': 'ឧ. ឃុំបារគូ'}),
            'commune_en': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Barkou Commune'}),
            'village': forms.TextInput(attrs={'class': 'form-control', 'id': 'input_village', 'placeholder': 'ឧ. ភូមិស្វាយមីង'}),
            'village_en': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Svay Ming Village'}),
            'street_address': forms.TextInput(attrs={'class': 'form-control', 'id': 'input_street_address', 'placeholder': 'ឧ. ផ្លូវលេខ២០៤ ភូមិស្វាយមីង ឃុំបារគូ'}),
            'street_address_en': forms.TextInput(attrs={'class': 'form-control', 'id': 'input_street_address_en', 'placeholder': 'e.g. Street 204, Svay Ming Village, Barkou Commune'}),

            'latitude': forms.NumberInput(attrs={'class': 'form-control', 'id': 'input_latitude', 'step': 'any', 'placeholder': '11.5564'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-control', 'id': 'input_longitude', 'step': 'any', 'placeholder': '104.9282'}),
            'google_maps_url': forms.URLInput(attrs={'class': 'form-control', 'id': 'input_google_maps_url', 'placeholder': 'https://maps.google.com/...'}),
            'gps_radius_meters': forms.NumberInput(attrs={'class': 'form-control', 'id': 'input_gps_radius_meters', 'placeholder': '100'}),

            'principal_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. លោក ផេង វ៉ូយ៉ា'}),
            'principal_name_en': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Mr. Pheng Voya'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. 093 995 947 / 089 995 947'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. info@schoolsm.edu.kh'}),
            'website': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://schoolsm.edu.kh'}),
            'facebook_page': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://facebook.com/schoolsm'}),
            'telegram_channel': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://t.me/school_channel'}),
        }

    def __init__(self, *args, **kwargs):
        language = kwargs.pop('language', 'km')
        super().__init__(*args, **kwargs)
        is_en = (language == 'en')
        if 'institution_type' in self.fields:
            cleaned_choices = []
            for val, label in self.fields['institution_type'].choices:
                if ' / ' in str(label):
                    parts = str(label).split(' / ')
                    cleaned_label = parts[1].strip() if is_en else parts[0].strip()
                else:
                    cleaned_label = label
                cleaned_choices.append((val, cleaned_label))
            self.fields['institution_type'].choices = cleaned_choices

        if is_en:
            if 'date_format' in self.fields:
                cleaned_choices = []
                for val, label in self.fields['date_format'].choices:
                    lbl = str(label).replace(' - លំនាំដើម', ' - Default').replace('(ឧ.', '(e.g.').replace('ឬរួមបញ្ចូលម៉ោង នាទី វិនាទី', 'or including time')
                    cleaned_choices.append((val, lbl))
                self.fields['date_format'].choices = cleaned_choices

            if 'time_format' in self.fields:
                cleaned_choices = []
                for val, label in self.fields['time_format'].choices:
                    lbl = str(label).replace(' - លំនាំដើម', ' - Default').replace('(ឧ.', '(e.g.').replace('២៤ ម៉ោង គ្មានវិនាទី', '24 Hours no seconds').replace('មានវិនាទី', 'with seconds').replace('១២ ម៉ោង', '12 Hours')
                    cleaned_choices.append((val, lbl))
                self.fields['time_format'].choices = cleaned_choices


AVAILABLE_GEMINI_MODELS_KM = [
    ('gemini-3.8-flash', '⚡ Gemini 3.8 Flash (ជំនាន់ថ្មី & ឆ្លាតវៃ - ណែនាំ)'),
    ('gemini-3.5-flash-lite', '🚀 Gemini 3.5 Flash-Lite (ស្រាល & ល្បឿនលឿនបំផុត ~1-2s)'),
    ('gemini-3.5-flash', '⚡ Gemini 3.5 Flash (ស្តង់ដារ)'),
    ('gemini-flash-latest', '🔄 Gemini Flash Latest (បច្ចុប្បន្នភាពស្វ័យប្រវត្តិ)'),
    ('custom', '✏️ ផ្សេងទៀត (បញ្ចូលឈ្មោះម៉ូដែលផ្ទាល់)...'),
]

AVAILABLE_GEMINI_MODELS_EN = [
    ('gemini-3.8-flash', '⚡ Gemini 3.8 Flash (Latest & Smartest - Recommended)'),
    ('gemini-3.5-flash-lite', '🚀 Gemini 3.5 Flash-Lite (Ultra Fast Speed ~1-2s)'),
    ('gemini-3.5-flash', '⚡ Gemini 3.5 Flash (Standard)'),
    ('gemini-flash-latest', '🔄 Gemini Flash Latest (Always Latest Version)'),
    ('custom', '✏️ Custom (Enter custom model name)...'),
]


class GeminiAiConfigForm(forms.ModelForm):
    def __init__(self, *args, language='km', **kwargs):
        super().__init__(*args, **kwargs)
        if 'thinking_level' in self.fields:
            if language == 'en':
                self.fields['thinking_level'].choices = [
                    ('low', '⚡ Low (Fast)'),
                    ('medium', '⚖️ Medium (Balanced Standard)'),
                    ('high', '🧠 High (Deep Thinking)'),
                ]
            else:
                self.fields['thinking_level'].choices = [
                    ('low', '⚡ លឿនរហ័ស'),
                    ('medium', '⚖️ មធ្យម (ស្តង់ដារ)'),
                    ('high', '🧠 ស៊ីជម្រៅ'),
                ]

        if 'model_name' in self.fields:
            current_val = ''
            if self.instance and self.instance.pk:
                current_val = self.instance.model_name
            elif 'model_name' in self.initial:
                current_val = self.initial['model_name']

            raw_choices = AVAILABLE_GEMINI_MODELS_EN if language == 'en' else AVAILABLE_GEMINI_MODELS_KM
            standard_keys = [k for k, _ in raw_choices]

            model_choices = list(raw_choices)
            if current_val and current_val not in standard_keys and current_val != 'custom':
                custom_lbl = f'✨ {current_val} (Custom)' if language == 'en' else f'✨ {current_val} (ម៉ូដែលផ្ទាល់ខ្លួន)'
                model_choices.insert(-1, (current_val, custom_lbl))

            self.fields['model_name'].widget = forms.Select(
                attrs={
                    'class': 'form-select fw-semibold',
                    'id': 'id_model_name',
                    'onchange': 'handleModelSelectionChange(this.value)'
                },
                choices=model_choices
            )

    def clean_model_name(self):
        val = self.cleaned_data.get('model_name', '').strip()
        if val == 'custom':
            custom = self.data.get('custom_model_name', '').strip()
            if custom:
                return custom
            return 'gemini-3.5-flash'
        return val or 'gemini-3.5-flash'

    class Meta:
        model = GeminiAiConfig
        fields = ['api_keys', 'model_name', 'thinking_level', 'is_active', 'rotation_enabled']
        widgets = {
            'api_keys': forms.Textarea(attrs={
                'class': 'form-control font-monospace small',
                'rows': 5,
                'placeholder': 'AIzaSyKey1_xxxxxxxxxxxx\nAIzaSyKey2_yyyyyyyyyyyy\nAIzaSyKey3_zzzzzzzzzzzz'
            }),
            'thinking_level': forms.Select(attrs={
                'class': 'form-select'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'rotation_enabled': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

