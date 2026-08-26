from django import forms
from .models import ExamTerm, Grade, StandardizedExam

class ExamTermForm(forms.ModelForm):
    class Meta:
        model = ExamTerm
        fields = ['name', 'academic_year', 'semester', 'term_type', 'scoring_mode', 'is_counted_in_semester', 'start_date', 'end_date', 'is_published']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. ប្រឡងប្រចាំខែមករា / January Monthly Exam'}),
            'academic_year': forms.Select(attrs={'class': 'form-select'}),
            'semester': forms.Select(attrs={'class': 'form-select'}),
            'term_type': forms.Select(attrs={'class': 'form-select'}),
            'scoring_mode': forms.Select(attrs={'class': 'form-select'}),
            'is_counted_in_semester': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class StandardizedExamForm(forms.ModelForm):
    class Meta:
        model = StandardizedExam
        fields = ['name', 'academic_year', 'grade_level', 'track', 'session', 'exam_date', 'candidates_per_room', 'description', 'is_published']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. ការប្រឡងតេស្តស្តង់ដា ឆមាសទី១ ថ្នាក់ទី១២ ឆ្នាំសិក្សា ២០២៥-២០២៦'}),
            'academic_year': forms.Select(attrs={'class': 'form-select'}),
            'grade_level': forms.NumberInput(attrs={'class': 'form-control', 'min': 7, 'max': 12}),
            'track': forms.Select(attrs={'class': 'form-select'}),
            'session': forms.Select(attrs={'class': 'form-select'}),
            'exam_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'candidates_per_room': forms.NumberInput(attrs={'class': 'form-control', 'min': 5, 'max': 50}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'សេចក្តីណែនាំ ឬការកំណត់សម្គាល់បន្ថែម...'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

