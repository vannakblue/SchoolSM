from django import forms
from .models import AcademicYear, Classroom, Subject, ClassSubject, Timetable, GradeLevel, GradeEnrollmentOption, AcademicTrack
from apps.teachers.models import Teacher


class AcademicTrackForm(forms.ModelForm):
    order = forms.IntegerField(required=False, initial=1, widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1}))

    class Meta:
        model = AcademicTrack
        fields = ['code', 'name_kh', 'name_en', 'order']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. TECH, BILINGUAL, ARTS'}),
            'name_kh': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. ថ្នាក់បច្ចេកវិទ្យា & IT'}),
            'name_en': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Technology / IT Track'}),
        }

    def clean_order(self):
        return self.cleaned_data.get('order') or 1


class AcademicYearForm(forms.ModelForm):
    class Meta:
        model = AcademicYear
        fields = ['name', 'start_date', 'end_date', 'is_current']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 2026-2027 ឬ ២០២៦-២០២៧'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_current': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class GradeLevelForm(forms.ModelForm):
    class Meta:
        model = GradeLevel
        fields = ['name', 'grade_number', 'track', 'order']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. ថ្នាក់ទី ១០ វិទ្យាសាស្ត្រ, ថ្នាក់ទី ១០ វិទ្យាសាស្ត្រសង្គម'}),
            'grade_number': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 12, 'placeholder': 'e.g. 10'}),
            'track': forms.Select(attrs={'class': 'form-select'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'placeholder': 'e.g. 4'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['track'].widget.choices = AcademicTrack.get_track_choices()


class ClassroomForm(forms.ModelForm):
    class Meta:
        model = Classroom
        fields = ['name', 'code', 'grade_level', 'track', 'academic_year', 'room_number', 'capacity', 'homeroom_teacher', 'assembly_duty_teacher', 'class_monitor', 'vice_monitor']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. ថ្នាក់ទី១០A, ទី១១ វិទ្យាសាស្ត្រ'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 10A, 11-SCI'}),
            'grade_level': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 12}),
            'track': forms.Select(attrs={'class': 'form-select'}),
            'academic_year': forms.Select(attrs={'class': 'form-select'}),
            'room_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. បន្ទប់ 201'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. 45 (ទុកទទេ = មិនកំណត់)', 'min': 1}),
            'homeroom_teacher': forms.Select(attrs={'class': 'form-select'}),
            'assembly_duty_teacher': forms.Select(attrs={'class': 'form-select'}),
            'class_monitor': forms.Select(attrs={'class': 'form-select'}),
            'vice_monitor': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, academic_year=None, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.students.models import Student
        from apps.teachers.models import Teacher
        self.fields['capacity'].required = False
        self.fields['track'].widget.choices = AcademicTrack.get_track_choices()
        self.fields['academic_year'].queryset = AcademicYear.objects.all().order_by('-start_date')
        self.fields['academic_year'].empty_label = "-- ជ្រើសរើសឆ្នាំសិក្សា / Select Academic Year --"
        self.fields['homeroom_teacher'].empty_label = "-- ជ្រើសរើសគ្រូបន្ទុកថ្នាក់ (Homeroom Teacher) --"
        self.fields['assembly_duty_teacher'].empty_label = "-- ជ្រើសរើសគ្រូប្រចាំការស្រង់វត្តមាន (Assembly Duty Teacher) --"
        self.fields['assembly_duty_teacher'].queryset = Teacher.objects.filter(status='ACTIVE').order_by('khmer_name')
        self.fields['class_monitor'].empty_label = "-- ជ្រើសរើសប្រធានថ្នាក់ (Class Monitor) --"
        self.fields['vice_monitor'].empty_label = "-- ជ្រើសរើសអនុប្រធានថ្នាក់ (Vice Monitor) --"
        
        if self.instance.pk:
            self.fields['class_monitor'].queryset = Student.objects.filter(classroom=self.instance, status='ACTIVE').order_by('khmer_name')
            self.fields['vice_monitor'].queryset = Student.objects.filter(classroom=self.instance, status='ACTIVE').order_by('khmer_name')
        else:
            self.fields['class_monitor'].queryset = Student.objects.none()
            self.fields['vice_monitor'].queryset = Student.objects.none()

        if not self.instance.pk and not self.initial.get('academic_year'):
            if academic_year:
                self.initial['academic_year'] = academic_year
            else:
                curr = AcademicYear.objects.filter(is_current=True).first()
                if curr:
                    self.initial['academic_year'] = curr


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name_kh', 'name_en', 'code', 'category', 'color_code', 'credit', 'order']
        widgets = {
            'name_kh': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. គណិតវិទ្យា, ភូមិវិទ្យា, ពលរដ្ឋវិជ្ជា'}),
            'name_en': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Mathematics, Geography, Civics'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. M, G, K, R, D'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'credit': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'color_code': forms.TextInput(attrs={'class': 'form-control form-control-color', 'type': 'color'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['credit'].required = False
        self.fields['order'].required = False
        self.fields['category'].required = False
        if not self.instance.pk:
            if not self.initial.get('credit'):
                self.initial['credit'] = 2
            if not self.initial.get('category'):
                self.initial['category'] = 'GENERAL'
            if not self.initial.get('order'):
                last_order = Subject.objects.order_by('-order').values_list('order', flat=True).first() or 0
                self.initial['order'] = last_order + 1

    def clean_category(self):
        cat = self.cleaned_data.get('category')
        if cat:
            return cat
        if self.instance.pk and self.instance.category:
            return self.instance.category
        return 'GENERAL'

    def clean_credit(self):
        credit = self.cleaned_data.get('credit')
        return credit if credit is not None else 2

    def clean_order(self):
        order = self.cleaned_data.get('order')
        if order is not None:
            return order
        if self.instance.pk and self.instance.order:
            return self.instance.order
        last_order = Subject.objects.order_by('-order').values_list('order', flat=True).first() or 0
        return last_order + 1


class TimetableForm(forms.ModelForm):
    class Meta:
        model = Timetable
        fields = ['classroom', 'subject', 'teacher', 'day_of_week', 'period_number', 'start_time', 'end_time', 'room']
        widgets = {
            'classroom': forms.Select(attrs={'class': 'form-select', 'id': 'tt_classroom'}),
            'subject': forms.Select(attrs={'class': 'form-select', 'id': 'tt_subject'}),
            'teacher': forms.Select(attrs={'class': 'form-select', 'id': 'tt_teacher'}),
            'day_of_week': forms.Select(attrs={'class': 'form-select', 'id': 'tt_day'}),
            'period_number': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 8, 'id': 'tt_period'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time', 'id': 'tt_start'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time', 'id': 'tt_end'}),
            'room': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Room 101'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['period_number'].required = False
        self.fields['room'].required = False
        if not self.instance.pk and not self.initial.get('period_number'):
            self.initial['period_number'] = 1

    def clean_period_number(self):
        p = self.cleaned_data.get('period_number')
        return p if p else (self.instance.period_number if self.instance.pk and self.instance.period_number else 1)


class GradeEnrollmentOptionForm(forms.ModelForm):
    class Meta:
        model = GradeEnrollmentOption
        fields = ['grade_level', 'label', 'field_name', 'field_type', 'col_width', 'choices', 'placeholder', 'is_required', 'order', 'is_active']
        widgets = {
            'grade_level': forms.Select(attrs={'class': 'form-select'}),
            'label': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. ឈ្មោះសាលាបឋមសិក្សាដើម, និទ្ទេសឌីប្លូម, ថ្ងៃចុះឈ្មោះ...'}),
            'field_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. previous_school, diploma_grade, custom_date'}),
            'field_type': forms.Select(attrs={'class': 'form-select', 'id': 'opt_field_type'}),
            'col_width': forms.Select(attrs={'class': 'form-select', 'id': 'opt_col_width'}),
            'choices': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'ឧ. និទ្ទេស A, និទ្ទេស B, និទ្ទេស C, និទ្ទេស D, និទ្ទេស E (បំបែកដោយក្បៀស)'}),
            'placeholder': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. សូមបញ្ចូល ឬជ្រើសរើស...'}),
            'is_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

