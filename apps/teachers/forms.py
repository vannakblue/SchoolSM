from django import forms
from .models import Teacher, TeacherAttendance

class TeacherForm(forms.ModelForm):
    class Meta:
        model = Teacher
        fields = [
            'teacher_id', 'khmer_name', 'latin_name', 'gender', 'date_of_birth',
            'phone', 'email', 'address', 'qualification', 'specialization',
            'base_salary', 'hire_date', 'photo', 'resume', 'status'
        ]
        widgets = {
            'teacher_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. TCH-001'}),
            'khmer_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. លី វណ្ណៈ'}),
            'latin_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. LY VANNAK'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '012 999 888'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'teacher@school.edu.kh'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'qualification': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'បរិញ្ញាបត្រគរុកោសល្យ'}),
            'specialization': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'គណិតវិទ្យា & រូបវិទ្យា'}),
            'base_salary': forms.NumberInput(attrs={'class': 'form-control'}),
            'hire_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'photo': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'resume': forms.FileInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }
