from django import forms
from .models import Teacher, TeacherAttendance

class TeacherForm(forms.ModelForm):
    class Meta:
        model = Teacher
        fields = [
            'teacher_id', 'khmer_name', 'latin_name', 'gender', 'date_of_birth',
            'phone', 'email', 'address', 'qualification', 'specialization',
            'training_level', 'state_hire_date', 'permanent_date',
            'primary_subject', 'secondary_subject', 'current_duty',
            'prakas_category', 'prakas_year', 'prakas_number',
            'base_salary', 'hire_date', 'photo', 'resume', 'status'
        ]
        widgets = {
            'teacher_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. T-001 ឬ អត្តលេខ...'}),
            'khmer_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. សុខ វិបុល'}),
            'latin_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. SOK VIBOL'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '012 345 678'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'teacher@school.edu.kh'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'ភូមិ ឃុំ ស្រុក ខេត្ត...'}),
            'qualification': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. បាក់ឌុប, បរិញ្ញាបត្រ, អនុបណ្ឌិត...'}),
            'specialization': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. គណិតវិទ្យា & រូបវិទ្យា'}),
            'training_level': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. គរុកោសល្យបឋម, មូលដ្ឋាន (១២+២), ឧត្តម (បរិញ្ញាបត្រ+១)...'}),
            'state_hire_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'permanent_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'primary_subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. គណិតវិទ្យា'}),
            'secondary_subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. រូបវិទ្យា'}),
            'current_duty': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. គ្រូបង្រៀន, នាយករង, ប្រធានបច្ចេកទេស...'}),
            'prakas_category': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. ក្របខ័ណ្ឌ ក.១, ខ.១, គ.១...'}),
            'prakas_year': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. 2018'}),
            'prakas_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. ប្រកាសលេខ ១២៣ អយក.ប្រក'}),
            'base_salary': forms.NumberInput(attrs={'class': 'form-control'}),
            'hire_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'photo': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'resume': forms.FileInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }
