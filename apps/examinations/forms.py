from django import forms
from .models import ExamTerm, Grade, StandardizedExam, StandardizedExamType

class ExamTermForm(forms.ModelForm):
    class Meta:
        model = ExamTerm
        fields = [
            'name', 'academic_year', 'semester', 'term_type', 'scoring_mode',
            'is_counted_in_semester', 'start_date', 'end_date',
            'grading_start_datetime', 'grading_end_datetime', 'is_grading_locked',
            'is_published'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. ប្រឡងប្រចាំខែមករា / January Monthly Exam'}),
            'academic_year': forms.Select(attrs={'class': 'form-select'}),
            'semester': forms.Select(attrs={'class': 'form-select'}),
            'term_type': forms.Select(attrs={'class': 'form-select'}),
            'scoring_mode': forms.Select(attrs={'class': 'form-select'}),
            'is_counted_in_semester': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'start_date': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'grading_start_datetime': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'grading_end_datetime': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'is_grading_locked': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class StandardizedExamForm(forms.ModelForm):
    exam_type = forms.ChoiceField(
        choices=(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="ប្រភេទសម័យប្រឡង / Exam Type"
    )

    class Meta:
        model = StandardizedExam
        fields = [
            'name', 'academic_year', 'exam_type', 'exam_term', 'grade_level', 'track', 'session',
            'exam_date', 'candidates_per_room', 'grading_method', 'description',
            'grading_start_datetime', 'grading_end_datetime', 'is_grading_locked',
            'is_published'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. ការប្រឡងតេស្តស្តង់ដា ឆមាសទី១ ថ្នាក់ទី១២ ឆ្នាំសិក្សា ២០២៥-២០២៦'}),
            'academic_year': forms.Select(attrs={'class': 'form-select'}),
            'exam_term': forms.Select(attrs={'class': 'form-select'}),
            'grade_level': forms.NumberInput(attrs={'class': 'form-control', 'min': 7, 'max': 12}),
            'track': forms.Select(attrs={'class': 'form-select'}),
            'session': forms.Select(attrs={'class': 'form-select'}),
            'exam_date': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'candidates_per_room': forms.NumberInput(attrs={'class': 'form-control', 'min': 5, 'max': 60}),
            'grading_method': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'សេចក្តីណែនាំ ឬការកំណត់សម្គាល់បន្ថែម...'}),
            'grading_start_datetime': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'grading_end_datetime': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'is_grading_locked': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            types = StandardizedExamType.get_active_types()
            if types.exists():
                choices = [(t.code, f"{t.icon} {t.name}") for t in types]
                curr = self.instance.exam_type if self.instance and self.instance.pk else None
                existing = [c[0] for c in choices]
                if curr and curr not in existing:
                    choices.append((curr, curr))
                self.fields['exam_type'].choices = choices
                self.fields['exam_type'].widget.choices = choices
            else:
                default_choices = [
                    ('BASELINE', '🎯 តេស្តដើមឆ្នាំ'),
                    ('SEMESTER_1', '🎓 ប្រឡងឆមាសទី១'),
                    ('SEMESTER_2', '🎓 ប្រឡងឆមាសទី២'),
                    ('MOCK', '📝 ប្រឡងសាកល្បង'),
                    ('ENDLINE', '🏁 តេស្តចុងឆ្នាំ'),
                    ('MONTHLY', '📅 ប្រឡងប្រចាំខែ...'),
                    ('OTHER', '📌 ការប្រឡងផ្សេងៗ'),
                ]
                self.fields['exam_type'].choices = default_choices
                self.fields['exam_type'].widget.choices = default_choices
        except Exception:
            default_choices = [
                ('BASELINE', '🎯 តេស្តដើមឆ្នាំ'),
                ('SEMESTER_1', '🎓 ប្រឡងឆមាសទី១'),
                ('SEMESTER_2', '🎓 ប្រឡងឆមាសទី២'),
                ('MOCK', '📝 ប្រឡងសាកល្បង'),
                ('ENDLINE', '🏁 តេស្តចុងឆ្នាំ'),
                ('MONTHLY', '📅 ប្រឡងប្រចាំខែ...'),
                ('OTHER', '📌 ការប្រឡងផ្សេងៗ'),
            ]
            self.fields['exam_type'].choices = default_choices
            self.fields['exam_type'].widget.choices = default_choices


class StandardizedExamTypeForm(forms.ModelForm):
    class Meta:
        model = StandardizedExamType
        fields = [
            'name', 'code', 'icon', 'default_title', 'is_monthly',
            'linked_term_type', 'order', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. ប្រឡងឆមាសទី១'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. SEMESTER_1'}),
            'icon': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. 🎯 ឬ 🎓'}),
            'default_title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. ការប្រឡងឆមាសទី១'}),
            'is_monthly': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'linked_term_type': forms.Select(choices=[
                ('', '-- មិនភ្ជាប់ / None --'),
                ('SEMESTER_1', 'ប្រឡងឆមាសទី១ (Semester 1)'),
                ('SEMESTER_2', 'ប្រឡងឆមាសទី២ (Semester 2)'),
                ('MONTHLY', 'ប្រឡងប្រចាំខែ (Monthly)'),
                ('ANNUAL', 'ប្រឡងចុងឆ្នាំ (Annual)'),
            ], attrs={'class': 'form-select'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


