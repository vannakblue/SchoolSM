from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserChangeForm
from .models import User, TelegramConfig, SchoolProfile

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
            'name_kh', 'name_en', 'short_name', 'school_code', 'school_type', 'institution_type', 'education_levels', 'motto',
            'logo', 'seal', 'principal_signature',
            'ministry_name', 'poe_name', 'doe_name',
            'province', 'district', 'commune', 'village', 'street_address',
            'latitude', 'longitude', 'google_maps_url', 'gps_radius_meters',
            'principal_name', 'phone', 'email', 'website', 'facebook_page', 'telegram_channel',
        ]
        widgets = {
            'name_kh': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. វិទ្យាល័យអន្តរជាតិ សាលារៀន SM'}),
            'name_en': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. SchoolSM International High School'}),
            'short_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. សាលារៀន SM'}),
            'school_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. 080101'}),
            'school_type': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. វិទ្យាល័យចំណេះទូទៅ / General High School'}),
            'institution_type': forms.Select(attrs={'class': 'form-select'}),
            'education_levels': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. មត្តេយ្យ, បឋមសិក្សា, អនុវិទ្យាល័យ, វិទ្យាល័យ'}),
            'motto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. ចំណេះដឹង វិន័យ សីលធម៌ គុណធម៌'}),
            
            'logo': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'seal': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'principal_signature': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),

            'ministry_name': forms.TextInput(attrs={'class': 'form-control'}),
            'poe_name': forms.TextInput(attrs={'class': 'form-control'}),
            'doe_name': forms.TextInput(attrs={'class': 'form-control'}),

            'province': forms.TextInput(attrs={'class': 'form-control', 'id': 'input_province', 'placeholder': 'ឧ. រាជធានីភ្នំពេញ'}),
            'district': forms.TextInput(attrs={'class': 'form-control', 'id': 'input_district', 'placeholder': 'ឧ. ខណ្ឌដូនពេញ'}),
            'commune': forms.TextInput(attrs={'class': 'form-control', 'id': 'input_commune', 'placeholder': 'ឧ. សង្កាត់វត្តភ្នំ'}),
            'village': forms.TextInput(attrs={'class': 'form-control', 'id': 'input_village', 'placeholder': 'ឧ. ភូមិ១'}),
            'street_address': forms.TextInput(attrs={'class': 'form-control', 'id': 'input_street_address', 'placeholder': 'ឧ. មហាវិថីព្រះនរោត្តម សង្កាត់វត្តភ្នំ'}),

            'latitude': forms.NumberInput(attrs={'class': 'form-control', 'id': 'input_latitude', 'step': 'any', 'placeholder': '11.5564'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-control', 'id': 'input_longitude', 'step': 'any', 'placeholder': '104.9282'}),
            'google_maps_url': forms.URLInput(attrs={'class': 'form-control', 'id': 'input_google_maps_url', 'placeholder': 'https://maps.google.com/...'}),
            'gps_radius_meters': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '100'}),

            'principal_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. លោកបណ្ឌិត សុខ ចាន់ថន'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. 023 888 999 / 012 345 678'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. info@schoolsm.edu.kh'}),
            'website': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://schoolsm.edu.kh'}),
            'facebook_page': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://facebook.com/schoolsm'}),
            'telegram_channel': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://t.me/school_channel'}),
        }

