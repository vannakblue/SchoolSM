from django import forms
from .models import Student, ScholarshipType, StudentStatusConfig
from apps.academics.models import Classroom, AcademicYear

class StudentEnrollmentForm(forms.ModelForm):
    student_id = forms.CharField(
        required=False,
        label="អត្តលេខសិស្ស / Student ID",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'ទុកទទេដើម្បីបង្កើតស្វ័យប្រវត្តិ (ឧ. 260001)',
            'id': 'id_student_id',
            'autocomplete': 'off'
        }),
        help_text="ទុកទទេដើម្បីឱ្យប្រព័ន្ធបង្កើតអត្តលេខស្វ័យប្រវត្តិតាមឆ្នាំសិក្សា ឬបញ្ចូលអត្តលេខផ្ទាល់ខ្លួនដែលមិនស្ទួន"
    )
    scholarship_type = forms.ChoiceField(
        choices=[],
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=True,
        label="ប្រភេទកម្រៃសិក្សា / អាហារូបករណ៍"
    )

    def __init__(self, *args, academic_year=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 1. Filter classrooms strictly by the specified or active academic year
        if academic_year:
            self.fields['classroom'].queryset = Classroom.objects.filter(academic_year=academic_year).select_related('academic_year').order_by('grade_level', 'code')
        elif self.instance and self.instance.academic_year:
            self.fields['classroom'].queryset = Classroom.objects.filter(academic_year=self.instance.academic_year).select_related('academic_year').order_by('grade_level', 'code')
        else:
            active_year = AcademicYear.objects.filter(is_current=True).first()
            if active_year:
                self.fields['classroom'].queryset = Classroom.objects.filter(academic_year=active_year).select_related('academic_year').order_by('grade_level', 'code')
            else:
                self.fields['classroom'].queryset = Classroom.objects.select_related('academic_year').order_by('grade_level', 'code')

        self.fields['classroom'].empty_label = "-- ជ្រើសរើសថ្នាក់រៀន / Select Classroom --"

        # 2. Populate dynamic scholarship types from database
        db_scholarships = list(ScholarshipType.objects.filter(is_active=True).order_by('order', 'id'))
        choices = []
        if db_scholarships:
            for st in db_scholarships:
                discount_text = f" ({st.discount_percentage:.0f}%)" if st.discount_percentage > 0 else ""
                choices.append((st.code, f"{st.name}{discount_text}"))
        else:
            choices = list(Student.ScholarshipType.choices)

        self.fields['scholarship_type'].choices = choices
        self.fields['scholarship_type'].widget.choices = choices

        # 3. Populate dynamic student statuses from database
        db_statuses = list(StudentStatusConfig.objects.filter(is_active=True).order_by('order', 'id'))
        status_choices = []
        if db_statuses:
            for sc in db_statuses:
                status_choices.append((sc.code, f"{sc.name} ({sc.name_en or sc.code})"))
        else:
            status_choices = list(Student.Status.choices)

        self.fields['status'].choices = status_choices
        self.fields['status'].widget.choices = status_choices

        # Set default value if creating new student
        if not self.instance.pk and choices:
            self.initial.setdefault('scholarship_type', choices[0][0])
        if not self.instance.pk and status_choices:
            self.initial.setdefault('status', 'ACTIVE')

    def clean_student_id(self):
        sid = self.cleaned_data.get('student_id')
        if sid:
            sid = str(sid).strip()
            if sid:
                qs = Student.objects.filter(student_id__iexact=sid)
                if self.instance and self.instance.pk:
                    qs = qs.exclude(pk=self.instance.pk)
                if qs.exists():
                    existing = qs.first()
                    class_info = f" ({existing.classroom.name})" if existing.classroom else ""
                    raise forms.ValidationError(
                        f"⚠️ អត្តលេខសិស្ស '{sid}' ត្រូវបានប្រើប្រាស់រួចហើយដោយសិស្ស {existing.khmer_name}{class_info}! សូមបញ្ចូលអត្តលេខផ្សេង ឬទុកទទេដើម្បីឱ្យប្រព័ន្ធបង្កើតស្វ័យប្រវត្តិ។"
                    )
        return sid or ''

    class Meta:
        model = Student
        fields = [
            'student_id', 'khmer_name', 'latin_name', 'gender', 'date_of_birth', 'place_of_birth',
            'current_address', 'phone', 'photo', 'birth_certificate',
            'classroom', 'academic_year', 'status', 'scholarship_type', 'fee_start_month', 'fee_end_month',
            'is_exam_suspended', 'exam_suspension_reason', 'exam_suspension_notes',
            'father_name', 'father_phone', 'father_job',
            'mother_name', 'mother_phone', 'mother_job',
            'guardian_name', 'emergency_phone', 'telegram_chat_id'
        ]
        widgets = {
            'student_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ទុកទទេដើម្បីបង្កើតស្វ័យប្រវត្តិ (ឧ. 260001)', 'id': 'id_student_id', 'autocomplete': 'off'}),
            'khmer_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. សុខ ចិន្តា'}),
            'latin_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. SOK CHINDA'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'place_of_birth': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'រាជធានីភ្នំពេញ'}),
            'current_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'ផ្ទះលេខ..., ផ្លូវ..., សង្កាត់...'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '012 345 678'}),
            'photo': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'birth_certificate': forms.FileInput(attrs={'class': 'form-control'}),
            
            'classroom': forms.Select(attrs={'class': 'form-select'}),
            'academic_year': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'scholarship_type': forms.Select(attrs={'class': 'form-select'}),
            'fee_start_month': forms.Select(attrs={'class': 'form-select'}),
            'fee_end_month': forms.Select(attrs={'class': 'form-select'}),
            
            'is_exam_suspended': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_is_exam_suspended'}),
            'exam_suspension_reason': forms.Select(attrs={'class': 'form-select'}),
            'exam_suspension_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'មូលហេតុ ឬកំណត់សម្គាល់ដកសិទ្ធិប្រឡង...'}),

            'father_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឈ្មោះឪពុក'}),
            'father_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '012 888 999'}),
            'father_job': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'មុខរបរឪពុក'}),
            'mother_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឈ្មោះម្តាយ'}),
            'mother_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '098 777 666'}),
            'mother_job': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'មុខរបរម្តាយ'}),
            'guardian_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឈ្មោះអាណាព្យាបាល'}),
            'emergency_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'លេខទាក់ទងបន្ទាន់'}),
            'telegram_chat_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Telegram ID សម្រាប់ទទួលដំណឹង'}),
        }


class ScholarshipTypeForm(forms.ModelForm):
    class Meta:
        model = ScholarshipType
        fields = ['name', 'code', 'discount_percentage', 'description', 'is_active', 'order']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. អាហារូបករណ៍សម្តេចតេជោ ១០០%'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. SAMDECH_TECHO_100'}),
            'discount_percentage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100', 'placeholder': '0 - 100'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'ការពិពណ៌នាអំពីលក្ខខណ្ឌអាហារូបករណ៍ ឬការបញ្ចុះតម្លៃ...'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
        }


class StudentStatusConfigForm(forms.ModelForm):
    class Meta:
        model = StudentStatusConfig
        fields = ['name', 'name_en', 'code', 'badge_color', 'category_type', 'description', 'is_active', 'order']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. ព្យួរការសិក្សាដោយជំងឺ / ផ្លាស់ប្តូរទៅក្រៅប្រទេស'}),
            'name_en': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Medical Leave / Exchange Program'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. MEDICAL_LEAVE / EXCHANGE_STUDY'}),
            'badge_color': forms.Select(attrs={'class': 'form-select'}),
            'category_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'ការពិពណ៌នាអំពីស្ថានភាពសិក្សានេះ...'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
        }

