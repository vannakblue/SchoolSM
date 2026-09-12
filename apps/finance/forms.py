from django import forms
from .models import (
    FeeCategory, Invoice, PaymentTransaction, Expense, Payroll,
    SchoolRevenue, TeacherOvertimeConfig, TeacherOvertimeRecord
)

class FeeCategoryForm(forms.ModelForm):
    class Meta:
        model = FeeCategory
        fields = ['name', 'category_type', 'default_amount', 'applicable_grade_note', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. ថ្លៃចុះឈ្មោះចូលរៀនដើមឆ្នាំ ឬ វិភាគទានសាលារៀន'}),
            'category_type': forms.Select(attrs={'class': 'form-select'}),
            'default_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '25.00'}),
            'applicable_grade_note': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. សម្រាប់តែថ្នាក់ទី ៧ ឬសិស្សចុះឈ្មោះថ្មី'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'បញ្ជាក់អត្ថន័យចំណាយឱ្យបានច្បាស់លាស់ ឧ. សេវាចុះឈ្មោះ សៀវភៅតាមដាន និងកាតសិស្ស'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ['student', 'fee_category', 'academic_year', 'original_amount', 'discount_percent', 'due_date', 'notes']
        widgets = {
            'student': forms.Select(attrs={'class': 'form-select select2'}),
            'fee_category': forms.Select(attrs={'class': 'form-select'}),
            'academic_year': forms.Select(attrs={'class': 'form-select'}),
            'original_amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'discount_percent': forms.NumberInput(attrs={'class': 'form-control'}),
            'due_date': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class PaymentTransactionForm(forms.ModelForm):
    class Meta:
        model = PaymentTransaction
        fields = ['amount', 'payment_method', 'transaction_reference', 'notes']
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'transaction_reference': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'លេខកូដប្រតិបត្តិការធនាគារ (បើមាន)'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'កំណត់ចំណាំបន្ថែម'}),
        }


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['title', 'category', 'amount_khr', 'amount', 'date', 'voucher_file', 'notes']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. ទិញដីស ហ្វឺត និងក្រដាស A4 សម្រាប់សាលា'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'amount_khr': forms.NumberInput(attrs={'class': 'form-control', 'step': '500', 'placeholder': '0'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'date': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'voucher_file': forms.FileInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'ព័ត៌មានលម្អិតបន្ថែម ឬលេខវិក្កយបត្រចំណាយ'}),
        }


class SchoolRevenueForm(forms.ModelForm):
    class Meta:
        model = SchoolRevenue
        fields = ['title', 'source_type', 'amount_khr', 'amount_usd', 'date', 'academic_year', 'receipt_reference', 'receipt_file', 'notes']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. ថវិកាកម្មវិធីរដ្ឋ (PB) ឆមាសទី១ ឬ វិភាគទានសហគមន៍'}),
            'source_type': forms.Select(attrs={'class': 'form-select'}),
            'amount_khr': forms.NumberInput(attrs={'class': 'form-control', 'step': '500', 'placeholder': '0'}),
            'amount_usd': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'date': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'academic_year': forms.Select(attrs={'class': 'form-select'}),
            'receipt_reference': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'លេខលិខិត ឬលេខបង្កាន់ដៃយោង'}),
            'receipt_file': forms.FileInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'កំណត់ចំណាំបន្ថែម'}),
        }


class TeacherOvertimeConfigForm(forms.ModelForm):
    class Meta:
        model = TeacherOvertimeConfig
        fields = ['rate_per_hour_khr', 'rate_per_hour_usd', 'standard_hours_weekly', 'standard_hours_monthly', 'notes']
        widgets = {
            'rate_per_hour_khr': forms.NumberInput(attrs={'class': 'form-control', 'step': '500'}),
            'rate_per_hour_usd': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.10'}),
            'standard_hours_weekly': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'standard_hours_monthly': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class TeacherOvertimeRecordForm(forms.ModelForm):
    class Meta:
        model = TeacherOvertimeRecord
        fields = ['teacher', 'academic_year', 'month', 'year', 'standard_hours', 'actual_hours', 'rate_per_hour_khr', 'rate_per_hour_usd', 'notes']
        widgets = {
            'teacher': forms.Select(attrs={'class': 'form-select select2'}),
            'academic_year': forms.Select(attrs={'class': 'form-select'}),
            'month': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '12'}),
            'year': forms.NumberInput(attrs={'class': 'form-control'}),
            'standard_hours': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'actual_hours': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5'}),
            'rate_per_hour_khr': forms.NumberInput(attrs={'class': 'form-control', 'step': '500'}),
            'rate_per_hour_usd': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.10'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

