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


class OnlineExamForm(forms.ModelForm):
    class Meta:
        from .models import OnlineExam
        model = OnlineExam
        fields = [
            'title', 'description', 'exam_term', 'subject', 'grade_level',
            'target_classrooms', 'duration_minutes', 'total_score', 'pass_score',
            'max_attempts', 'start_time', 'end_time', 'status', 'is_published',
            'shuffle_questions', 'shuffle_options', 'show_result_immediately',
            'show_correct_answers', 'access_code'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. វិញ្ញាសាតេស្តប្រចាំខែមករា គណិតវិទ្យា'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'សេចក្តីណែនាំ និងលក្ខខណ្ឌនៃការប្រឡង...'}),
            'exam_term': forms.Select(attrs={'class': 'form-select'}),
            'subject': forms.Select(attrs={'class': 'form-select'}),
            'grade_level': forms.Select(choices=[
                ('', '-- ជ្រើសរើសកម្រិតថ្នាក់ / All Grades --'),
                (7, 'ថ្នាក់ទី ៧ (Grade 7)'),
                (8, 'ថ្នាក់ទី ៨ (Grade 8)'),
                (9, 'ថ្នាក់ទី ៩ (Grade 9)'),
                (10, 'ថ្នាក់ទី ១០ (Grade 10)'),
                (11, 'ថ្នាក់ទី ១១ (Grade 11)'),
                (12, 'ថ្នាក់ទី ១២ (Grade 12)'),
            ], attrs={'class': 'form-select'}),
            'target_classrooms': forms.SelectMultiple(attrs={'class': 'form-select', 'size': 5}),
            'duration_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': 5, 'max': 300}),
            'total_score': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5', 'min': 1}),
            'pass_score': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5', 'min': 0}),
            'max_attempts': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 10}),
            'start_time': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'end_time': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'shuffle_questions': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'shuffle_options': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'show_result_immediately': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'show_correct_answers': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'access_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ទុកទទេប្រសិនបើគ្មាន PIN'}),
        }

    def __init__(self, *args, teacher=None, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.academics.models import Classroom, Subject
        from .models import ExamTerm

        # Order active terms
        self.fields['exam_term'].queryset = ExamTerm.objects.all().order_by('-start_date')
        self.fields['subject'].queryset = Subject.objects.all().order_by('order', 'id')
        self.fields['target_classrooms'].queryset = Classroom.objects.all().order_by('grade_level', 'name')
        self.fields['target_classrooms'].required = False


class OnlineExamQuestionForm(forms.ModelForm):
    class Meta:
        from .models import OnlineExamQuestion
        model = OnlineExamQuestion
        fields = ['question_text', 'image', 'points', 'order', 'explanation']
        widgets = {
            'question_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'បញ្ចូលខ្លឹមសារសំណួរ...'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'points': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5', 'min': '0.5'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'explanation': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'ការពន្យល់ចម្លើយត្រឹមត្រូវ (បង្ហាញពេល Review)...'}),
        }



