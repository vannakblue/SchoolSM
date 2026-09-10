from django import forms
from django.db.models import Q
from .models import Student, ScholarshipType, StudentStatusConfig
from apps.academics.models import Classroom, AcademicYear

class StudentEnrollmentForm(forms.ModelForm):
    student_id = forms.CharField(
        required=False,
        label="អត្តលេខសិស្ស / Student ID",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'ទុកទទេដើម្បីបង្កើតស្វ័យប្រវត្តិ (ឧ. 270001)',
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

    def clean(self):
        cleaned_data = super().clean()
        khmer_name = (cleaned_data.get('khmer_name') or '').strip()
        dob = cleaned_data.get('date_of_birth')
        academic_year = cleaned_data.get('academic_year')
        classroom = cleaned_data.get('classroom')
        if not academic_year and classroom:
            academic_year = classroom.academic_year

        father_name = (cleaned_data.get('father_name') or '').strip()
        mother_name = (cleaned_data.get('mother_name') or '').strip()
        father_phone = (cleaned_data.get('father_phone') or '').strip().replace(' ', '').replace('-', '')
        mother_phone = (cleaned_data.get('mother_phone') or '').strip().replace(' ', '').replace('-', '')
        student_phone = (cleaned_data.get('phone') or '').strip().replace(' ', '').replace('-', '')
        emergency_phone = (cleaned_data.get('emergency_phone') or '').strip().replace(' ', '').replace('-', '')

        if khmer_name and dob:
            # Combined Rule 1 (Name + DOB) & Rule 2 (Guardian / Phone)
            qs = Student.objects.filter(
                khmer_name__iexact=khmer_name,
                date_of_birth=dob
            )
            if academic_year:
                qs = qs.filter(Q(academic_year=academic_year) | Q(classroom__academic_year=academic_year))

            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            for existing in qs:
                exist_father = (existing.father_name or '').strip()
                exist_mother = (existing.mother_name or '').strip()
                exist_f_phone = (existing.father_phone or '').strip().replace(' ', '').replace('-', '')
                exist_m_phone = (existing.mother_phone or '').strip().replace(' ', '').replace('-', '')
                exist_s_phone = (existing.phone or '').strip().replace(' ', '').replace('-', '')
                exist_e_phone = (existing.emergency_phone or '').strip().replace(' ', '').replace('-', '')

                parent_match = False
                if (father_name and exist_father and father_name.lower() == exist_father.lower()) or \
                   (mother_name and exist_mother and mother_name.lower() == exist_mother.lower()):
                    parent_match = True

                phone_match = False
                phones_submitted = {p for p in [father_phone, mother_phone, student_phone, emergency_phone] if p}
                phones_existing = {p for p in [exist_f_phone, exist_m_phone, exist_s_phone, exist_e_phone] if p}
                if phones_submitted and phones_existing and (phones_submitted & phones_existing):
                    phone_match = True

                class_str = f"ថ្នាក់ {existing.classroom.name}" if existing.classroom else "មិនទាន់មានថ្នាក់"
                dob_str = dob.strftime('%d/%m/%Y') if hasattr(dob, 'strftime') else str(dob)
                
                detail_reasons = []
                if parent_match:
                    detail_reasons.append("ឈ្មោះឪពុក/ម្តាយដូចគ្នា")
                if phone_match:
                    detail_reasons.append("លេខទូរស័ព្ទដូចគ្នា")

                reason_text = f" (ផ្ទៀងផ្ទាត់ឃើញ៖ {', '.join(detail_reasons)})" if detail_reasons else ""

                raise forms.ValidationError(
                    f"⚠️ សិស្សឈ្មោះ «{khmer_name}» កើតថ្ងៃទី {dob_str} បានចុះឈ្មោះចូលរៀនរួចហើយក្នុង{class_str} (អត្តលេខ: {existing.student_id}){reason_text}! ដើម្បីការពារទិន្នន័យស្ទួន សូមកុំចុះឈ្មោះឡើងវិញ។"
                )

        return cleaned_data

    class Meta:
        model = Student
        fields = [
            'student_id', 'khmer_name', 'latin_name', 'gender', 'date_of_birth', 'place_of_birth',
            'current_address', 'phone', 'photo', 'birth_certificate',
            'classroom', 'academic_year', 'status', 'scholarship_type', 'fee_start_month', 'fee_end_month',
            'is_repeating_grade',
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
            'date_of_birth': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
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
            
            'is_repeating_grade': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_is_repeating_grade'}),
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


class MoeysIndividualStudentForm(forms.ModelForm):
    """
    Dedicated Registration & Edit Form for MoEYS Individual Student Profile (សម្រង់ព័ត៌មានសិស្សម្នាក់ៗ - 35 Columns).
    Enables Admin and Applicants to register or edit student records strictly conforming to MoEYS Census 35 Columns.
    """
    student_id = forms.CharField(
        required=False,
        label="អត្តលេខសិស្ស / Student ID",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'ទុកទទេដើម្បីបង្កើតស្វ័យប្រវត្តិ (ឧ. 270001)',
            'id': 'moeys_student_id',
            'autocomplete': 'off'
        }),
        help_text="ទុកទទេដើម្បីឱ្យប្រព័ន្ធបង្កើតអត្តលេខស្វ័យប្រវត្តិតាមឆ្នាំសិក្សា"
    )
    surname = forms.CharField(
        required=True,
        label="នាមត្រកូល / Surname",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. សុខ', 'id': 'moeys_surname'})
    )
    given_name = forms.CharField(
        required=True,
        label="នាមខ្លួន / Given Name",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. ចិន្តា', 'id': 'moeys_given_name'})
    )
    latin_name = forms.CharField(
        required=True,
        label="ឈ្មោះជាអក្សរឡាតាំង / Latin Name",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. SOK CHINDA', 'id': 'moeys_latin_name'})
    )
    gender = forms.ChoiceField(
        choices=Student.Gender.choices,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'moeys_gender'}),
        label="ភេទ / Gender"
    )
    date_of_birth = forms.DateField(
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date', 'id': 'moeys_dob'}),
        label="ថ្ងៃខែឆ្នាំកំណើត / Date of Birth"
    )

    # Place of Birth (MoEYS 3 columns: Commune, District, Province)
    pob_commune = forms.CharField(
        required=False,
        label="ឃុំ/សង្កាត់កំណើត / POB Commune",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. សង្កាត់វត្តភ្នំ', 'id': 'moeys_pob_commune'})
    )
    pob_district = forms.CharField(
        required=False,
        label="ក្រុង/ស្រុក/ខណ្ឌកំណើត / POB District",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. ខណ្ឌដូនពេញ', 'id': 'moeys_pob_district'})
    )
    pob_province = forms.CharField(
        required=False,
        label="រាជធានី/ខេត្តកំណើត / POB Province",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. រាជធានីភ្នំពេញ', 'id': 'moeys_pob_province'})
    )

    # Classroom, Track, Academic Year
    classroom = forms.ModelChoiceField(
        queryset=Classroom.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'moeys_classroom'}),
        label="ថ្នាក់រៀន / Classroom",
        empty_label="-- ជ្រើសរើសថ្នាក់រៀន --"
    )
    academic_year = forms.ModelChoiceField(
        queryset=AcademicYear.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'moeys_academic_year'}),
        label="ឆ្នាំសិក្សា / Academic Year"
    )
    track = forms.ChoiceField(
        choices=[
            ('ទូទៅ', 'ទូទៅ (General Track)'),
            ('វិទ្យាសាស្ត្រ', 'វិទ្យាសាស្ត្រ (Science Track)'),
            ('វិទ្យាសាស្ត្រសង្គម', 'វិទ្យាសាស្ត្រសង្គម (Social Track)'),
            ('វិជ្ជាជីវៈ', 'វិជ្ជាជីវៈ (Vocational Track)'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'moeys_track'}),
        label="ជំនាញ / គន្លងអប់រំ (Track)"
    )
    is_repeating_grade = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'moeys_is_repeating_grade'}),
        label="ជាសិស្សត្រួតថ្នាក់ (Repeating Grade)"
    )

    # Parents & Guardian Info
    father_name = forms.CharField(required=False, label="ឈ្មោះឪពុក", widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឈ្មោះឪពុក', 'id': 'moeys_father_name'}))
    father_job = forms.CharField(required=False, label="មុខរបរឪពុក", widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'មុខរបរឪពុក', 'id': 'moeys_father_job'}))
    father_phone = forms.CharField(required=False, label="លេខទូរស័ព្ទឪពុក", widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '012 888 999', 'id': 'moeys_father_phone'}))
    mother_name = forms.CharField(required=False, label="ឈ្មោះម្តាយ", widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឈ្មោះម្តាយ', 'id': 'moeys_mother_name'}))
    mother_job = forms.CharField(required=False, label="មុខរបរម្តាយ", widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'មុខរបរម្តាយ', 'id': 'moeys_mother_job'}))
    mother_phone = forms.CharField(required=False, label="លេខទូរស័ព្ទម្តាយ", widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '098 777 666', 'id': 'moeys_mother_phone'}))
    guardian_name = forms.CharField(required=False, label="ឈ្មោះអាណាព្យាបាលជំនួស", widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឈ្មោះអាណាព្យាបាល', 'id': 'moeys_guardian_name'}))
    guardian_job = forms.CharField(required=False, label="មុខរបរអាណាព្យាបាល", widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'មុខរបរអាណាព្យាបាល', 'id': 'moeys_guardian_job'}))

    # Extended MoEYS census columns
    orphan_status = forms.ChoiceField(
        choices=[('មិនមែន', 'មិនមែន'), ('កំព្រាឪពុក', 'កំព្រាឪពុក'), ('កំព្រាម្តាយ', 'កំព្រាម្តាយ'), ('កំព្រាទាំងពីរ', 'កំព្រាទាំងពីរ')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'moeys_orphan_status'}),
        label="ស្ថានភាពកុមារកំព្រា (Orphan Status)"
    )
    primary_school = forms.CharField(required=False, label="សាលាបឋមសិក្សាពីមុន", widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. បឋមសិក្សា ហ៊ុន សែន...', 'id': 'moeys_primary_school'}))
    secondary_school = forms.CharField(required=False, label="គ្រឹះស្ថានមធ្យមសិក្សាពីមុន", widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. អនុវិទ្យាល័យ / វិទ្យាល័យ...', 'id': 'moeys_secondary_school'}))
    ethnic_minority = forms.ChoiceField(
        choices=[('មិនមែន', 'មិនមែន'), ('ជនជាតិដើមភាគតិច', 'ជនជាតិដើមភាគតិច'), ('ផ្សេងៗ', 'ផ្សេងៗ')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'moeys_ethnic_minority'}),
        label="ជនជាតិដើមភាគតិច (Ethnic Minority)"
    )
    disability_physical = forms.ChoiceField(
        choices=[('មិនមាន', 'មិនមាន'), ('ពិការដៃ', 'ពិការដៃ'), ('ពិការជើង', 'ពិការជើង'), ('ពិការរាងកាយ', 'ពិការរាងកាយ'), ('ផ្សេងៗ', 'ផ្សេងៗ')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'moeys_disability_physical'}),
        label="ពិការភាពកាយសម្បទា (Physical Disability)"
    )
    disability_sight = forms.ChoiceField(
        choices=[('មិនមាន', 'មិនមាន'), ('ពិការភ្នែកទាំងសងខាង', 'ពិការភ្នែកទាំងសងខាង'), ('ពិការភ្នែកម្ខាង', 'ពិការភ្នែកម្ខាង'), ('មើលមិនសូវច្បាស់', 'មើលមិនសូវច្បាស់')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'moeys_disability_sight'}),
        label="ពិការភាពគំហើញ (Sight Disability)"
    )
    disability_hearing = forms.ChoiceField(
        choices=[('មិនមាន', 'មិនមាន'), ('ថ្លង់ទាំងសងខាង', 'ថ្លង់ទាំងសងខាង'), ('ថ្លង់ម្ខាង', 'ថ្លង់ម្ខាង'), ('គរ', 'គរ'), ('ស្តាប់មិនសូវឮ', 'ស្តាប់មិនសូវឮ')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'moeys_disability_hearing'}),
        label="ពិការភាពការស្តាប់ (Hearing Disability)"
    )
    equity_card_1 = forms.ChoiceField(
        choices=[('មិនមាន', 'មិនមាន'), ('មាន', 'មានប័ណ្ណសមធម៌ (ក្រ១)')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'moeys_equity_card_1'}),
        label="ប័ណ្ណសមធម៌ក្រ១ (IDPoor 1)"
    )
    equity_card_2 = forms.ChoiceField(
        choices=[('មិនមាន', 'មិនមាន'), ('មាន', 'មានប័ណ្ណសមធម៌ (ក្រ២)')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'moeys_equity_card_2'}),
        label="ប័ណ្ណសមធម៌ក្រ២ (IDPoor 2)"
    )
    risk_card = forms.ChoiceField(
        choices=[('មិនមាន', 'មិនមាន'), ('មាន', 'មានប័ណ្ណហានិភ័យ')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'moeys_risk_card'}),
        label="ប័ណ្ណហានិភ័យ (At-Risk Card)"
    )
    scholarship = forms.ChoiceField(
        choices=[('មិនមាន', 'មិនមាន'), ('អាហារូបករណ៍រដ្ឋ', 'អាហារូបករណ៍រដ្ឋ'), ('អាហារូបករណ៍អង្គការ', 'អាហារូបករណ៍អង្គការ'), ('អាហារូបករណ៍សាលា', 'អាហារូបករណ៍សាលា'), ('ផ្សេងៗ', 'ផ្សេងៗ')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'moeys_scholarship'}),
        label="អាហារូបករណ៍ (Scholarship)"
    )
    phone = forms.CharField(required=False, label="លេខទូរស័ព្ទសិស្ស/ទំនាក់ទំនង", widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '012 345 678', 'id': 'moeys_phone'}))
    photo = forms.ImageField(required=False, widget=forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*', 'id': 'moeys_photo'}), label="រូបថតសិស្ស (៤x៦)")
    birth_certificate = forms.FileField(required=False, widget=forms.FileInput(attrs={'class': 'form-control', 'id': 'moeys_birth_certificate'}), label="សំបុត្រកំណើត / សៀវភៅគ្រួសារ")
    scholarship_type = forms.ChoiceField(choices=[], widget=forms.Select(attrs={'class': 'form-select', 'id': 'moeys_scholarship_type'}), required=False, label="ប្រភេទកម្រៃសិក្សា")
    status = forms.ChoiceField(choices=[], widget=forms.Select(attrs={'class': 'form-select', 'id': 'moeys_status'}), required=False, label="ស្ថានភាពសិក្សា")

    def __init__(self, *args, academic_year=None, **kwargs):
        super().__init__(*args, **kwargs)
        import re

        # Classrooms filtered by academic year
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

        # Populate dynamic scholarship types
        db_scholarships = list(ScholarshipType.objects.filter(is_active=True).order_by('order', 'id'))
        if db_scholarships:
            st_choices = [(st.code, st.name) for st in db_scholarships]
        else:
            st_choices = list(Student.ScholarshipType.choices)
        self.fields['scholarship_type'].choices = st_choices

        # Populate dynamic student statuses
        db_statuses = list(StudentStatusConfig.objects.filter(is_active=True).order_by('order', 'id'))
        if db_statuses:
            status_choices = [(sc.code, f"{sc.name} ({sc.name_en or sc.code})") for sc in db_statuses]
        else:
            status_choices = list(Student.Status.choices)
        self.fields['status'].choices = status_choices

        # Pre-fill initial values if editing existing student
        if self.instance and self.instance.pk:
            ed = dict(self.instance.enrollment_data or {})
            
            # Name pre-fill
            s_name = ed.get('surname', '')
            g_name = ed.get('given_name', '')
            if not s_name and not g_name and self.instance.khmer_name:
                parts = self.instance.khmer_name.strip().split(None, 1)
                s_name = parts[0] if len(parts) >= 2 else ''
                g_name = parts[1] if len(parts) >= 2 else parts[0]
            self.initial.setdefault('surname', s_name)
            self.initial.setdefault('given_name', g_name)

            # POB pre-fill
            pob_c = ed.get('pob_commune', '')
            pob_d = ed.get('pob_district', '')
            pob_p = ed.get('pob_province', '')
            if not pob_c and not pob_d and not pob_p and self.instance.place_of_birth:
                p_parts = [p.strip() for p in re.split(r'[,،]+', self.instance.place_of_birth) if p.strip()]
                if len(p_parts) >= 3:
                    pob_c, pob_d, pob_p = p_parts[0], p_parts[1], p_parts[2]
                elif len(p_parts) == 2:
                    pob_d, pob_p = p_parts[0], p_parts[1]
                elif len(p_parts) == 1:
                    pob_p = p_parts[0]
            self.initial.setdefault('pob_commune', pob_c)
            self.initial.setdefault('pob_district', pob_d)
            self.initial.setdefault('pob_province', pob_p)

            # Job & extended pre-fill
            self.initial.setdefault('father_job', ed.get('father_job') or self.instance.father_job or '')
            self.initial.setdefault('mother_job', ed.get('mother_job') or self.instance.mother_job or '')
            self.initial.setdefault('guardian_name', ed.get('guardian_name') or self.instance.guardian_name or '')
            self.initial.setdefault('guardian_job', ed.get('guardian_job', ''))
            self.initial.setdefault('orphan_status', ed.get('orphan_status', 'មិនមែន'))
            self.initial.setdefault('primary_school', ed.get('primary_school', ''))
            self.initial.setdefault('secondary_school', ed.get('secondary_school', ''))
            self.initial.setdefault('ethnic_minority', ed.get('ethnic_minority', 'មិនមែន'))
            self.initial.setdefault('disability_physical', ed.get('disability_physical', 'មិនមាន'))
            self.initial.setdefault('disability_sight', ed.get('disability_sight', 'មិនមាន'))
            self.initial.setdefault('disability_hearing', ed.get('disability_hearing', 'មិនមាន'))
            self.initial.setdefault('equity_card_1', ed.get('equity_card_1', 'មិនមាន'))
            self.initial.setdefault('equity_card_2', ed.get('equity_card_2', 'មិនមាន'))
            self.initial.setdefault('risk_card', ed.get('risk_card', 'មិនមាន'))
            self.initial.setdefault('scholarship', ed.get('scholarship', 'មិនមាន'))
            self.initial.setdefault('track', ed.get('track', ''))
        else:
            if st_choices:
                self.initial.setdefault('scholarship_type', st_choices[0][0])
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

    def clean(self):
        cleaned_data = super().clean()
        surname = (cleaned_data.get('surname') or '').strip()
        given_name = (cleaned_data.get('given_name') or '').strip()
        khmer_name = f"{surname} {given_name}".strip()
        dob = cleaned_data.get('date_of_birth')
        academic_year = cleaned_data.get('academic_year')
        classroom = cleaned_data.get('classroom')
        if not academic_year and classroom:
            academic_year = classroom.academic_year

        father_name = (cleaned_data.get('father_name') or '').strip()
        mother_name = (cleaned_data.get('mother_name') or '').strip()
        father_phone = (cleaned_data.get('father_phone') or '').strip().replace(' ', '').replace('-', '')
        mother_phone = (cleaned_data.get('mother_phone') or '').strip().replace(' ', '').replace('-', '')
        student_phone = (cleaned_data.get('phone') or '').strip().replace(' ', '').replace('-', '')

        if khmer_name and dob:
            qs = Student.objects.filter(
                khmer_name__iexact=khmer_name,
                date_of_birth=dob
            )
            if academic_year:
                qs = qs.filter(Q(academic_year=academic_year) | Q(classroom__academic_year=academic_year))
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            for existing in qs:
                exist_father = (existing.father_name or '').strip()
                exist_mother = (existing.mother_name or '').strip()
                exist_f_phone = (existing.father_phone or '').strip().replace(' ', '').replace('-', '')
                exist_m_phone = (existing.mother_phone or '').strip().replace(' ', '').replace('-', '')
                exist_s_phone = (existing.phone or '').strip().replace(' ', '').replace('-', '')

                parent_match = False
                if (father_name and exist_father and father_name.lower() == exist_father.lower()) or \
                   (mother_name and exist_mother and mother_name.lower() == exist_mother.lower()):
                    parent_match = True

                phone_match = False
                phones_submitted = {p for p in [father_phone, mother_phone, student_phone] if p}
                phones_existing = {p for p in [exist_f_phone, exist_m_phone, exist_s_phone] if p}
                if phones_submitted and phones_existing and (phones_submitted & phones_existing):
                    phone_match = True

                class_str = f"ថ្នាក់ {existing.classroom.name}" if existing.classroom else "មិនទាន់មានថ្នាក់"
                dob_str = dob.strftime('%d/%m/%Y') if hasattr(dob, 'strftime') else str(dob)
                detail_reasons = []
                if parent_match:
                    detail_reasons.append("ឈ្មោះឪពុក/ម្តាយដូចគ្នា")
                if phone_match:
                    detail_reasons.append("លេខទូរស័ព្ទដូចគ្នា")
                reason_text = f" (ផ្ទៀងផ្ទាត់ឃើញ៖ {', '.join(detail_reasons)})" if detail_reasons else ""

                raise forms.ValidationError(
                    f"⚠️ សិស្សឈ្មោះ «{khmer_name}» កើតថ្ងៃទី {dob_str} បានចុះឈ្មោះចូលរៀនរួចហើយក្នុង{class_str} (អត្តលេខ: {existing.student_id}){reason_text}! ដើម្បីការពារទិន្នន័យស្ទួន សូមកុំចុះឈ្មោះឡើងវិញ។"
                )
        return cleaned_data

    def save(self, commit=True):
        student = super().save(commit=False)
        surname = self.cleaned_data.get('surname', '').strip()
        given_name = self.cleaned_data.get('given_name', '').strip()
        student.khmer_name = f"{surname} {given_name}".strip()
        student.latin_name = self.cleaned_data.get('latin_name', '').strip()

        pob_c = self.cleaned_data.get('pob_commune', '').strip()
        pob_d = self.cleaned_data.get('pob_district', '').strip()
        pob_p = self.cleaned_data.get('pob_province', '').strip()
        pob_parts = [p for p in [pob_c, pob_d, pob_p] if p]
        if pob_parts:
            student.place_of_birth = ", ".join(pob_parts)

        student.father_name = self.cleaned_data.get('father_name', '').strip() or None
        student.father_job = self.cleaned_data.get('father_job', '').strip() or None
        student.father_phone = self.cleaned_data.get('father_phone', '').strip() or None
        student.mother_name = self.cleaned_data.get('mother_name', '').strip() or None
        student.mother_job = self.cleaned_data.get('mother_job', '').strip() or None
        student.mother_phone = self.cleaned_data.get('mother_phone', '').strip() or None
        student.guardian_name = self.cleaned_data.get('guardian_name', '').strip() or None
        student.phone = self.cleaned_data.get('phone', '').strip() or None
        student.is_repeating_grade = bool(self.cleaned_data.get('is_repeating_grade'))

        # Build & sync MoEYS enrollment_data JSON
        ed = dict(student.enrollment_data or {})
        track_val = self.cleaned_data.get('track', '').strip()
        is_sc = ('វិទ្យាសាស្ត្រ' in track_val and 'សង្គម' not in track_val)
        is_ss = ('សង្គម' in track_val)
        is_voc = ('វិជ្ជាជីវៈ' in track_val)

        moeys_dict = {
            'surname': surname,
            'given_name': given_name,
            'pob_commune': pob_c,
            'pob_district': pob_d,
            'pob_province': pob_p,
            'father_job': self.cleaned_data.get('father_job', ''),
            'mother_job': self.cleaned_data.get('mother_job', ''),
            'guardian_name': self.cleaned_data.get('guardian_name', ''),
            'guardian_job': self.cleaned_data.get('guardian_job', ''),
            'orphan_status': self.cleaned_data.get('orphan_status', 'មិនមែន'),
            'primary_school': self.cleaned_data.get('primary_school', ''),
            'secondary_school': self.cleaned_data.get('secondary_school', ''),
            'ethnic_minority': self.cleaned_data.get('ethnic_minority', 'មិនមែន'),
            'disability_physical': self.cleaned_data.get('disability_physical', 'មិនមាន'),
            'disability_sight': self.cleaned_data.get('disability_sight', 'មិនមាន'),
            'disability_hearing': self.cleaned_data.get('disability_hearing', 'មិនមាន'),
            'equity_card_1': self.cleaned_data.get('equity_card_1', 'មិនមាន'),
            'equity_card_2': self.cleaned_data.get('equity_card_2', 'មិនមាន'),
            'risk_card': self.cleaned_data.get('risk_card', 'មិនមាន'),
            'scholarship': self.cleaned_data.get('scholarship', 'មិនមាន'),
            'track': track_val,
            'is_sc': is_sc,
            'is_ss': is_ss,
            'is_voc': is_voc,
        }
        ed.update(moeys_dict)
        student.enrollment_data = ed

        if commit:
            student.save()
        return student

    class Meta:
        model = Student
        fields = [
            'student_id', 'latin_name', 'gender', 'date_of_birth',
            'classroom', 'academic_year', 'status', 'scholarship_type',
            'father_name', 'father_phone', 'mother_name', 'mother_phone',
            'guardian_name', 'phone', 'photo', 'birth_certificate', 'is_repeating_grade'
        ]


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

