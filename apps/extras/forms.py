from django import forms
from .models import Book, BookBorrowing, InventoryItem, InventoryTransaction, Announcement

class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = ['isbn', 'title', 'author', 'category', 'quantity', 'shelf_location']
        widgets = {
            'isbn': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 978-99950-0-000-0'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ចំណងជើងសៀវភៅ'}),
            'author': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឈ្មោះអ្នកនិពន្ធ'}),
            'category': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ប្រវត្តិវិទ្យា, វិទ្យាសាស្ត្រ, អក្សរសិល្ប៍'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'shelf_location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ធ្នើ A-01'}),
        }


class BookBorrowingForm(forms.ModelForm):
    class Meta:
        model = BookBorrowing
        fields = ['book', 'student', 'teacher', 'due_date', 'notes']
        widgets = {
            'book': forms.Select(attrs={'class': 'form-select'}),
            'student': forms.Select(attrs={'class': 'form-select'}),
            'teacher': forms.Select(attrs={'class': 'form-select'}),
            'due_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class InventoryItemForm(forms.ModelForm):
    class Meta:
        model = InventoryItem
        fields = ['item_code', 'name', 'category', 'unit_price', 'stock_quantity', 'min_alert_level']
        widgets = {
            'item_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. UNIFORM-M'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឯកសណ្ឋានសិស្សប្រុស Size M'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control'}),
            'stock_quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'min_alert_level': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class InventoryTransactionForm(forms.ModelForm):
    class Meta:
        model = InventoryTransaction
        fields = ['item', 'transaction_type', 'quantity', 'unit_price', 'student', 'notes']
        widgets = {
            'item': forms.Select(attrs={'class': 'form-select'}),
            'transaction_type': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control'}),
            'student': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class AnnouncementForm(forms.ModelForm):
    broadcast_telegram = forms.BooleanField(required=False, initial=True, label="ផ្ញើដំណឹងតាម Telegram ស្វ័យប្រវត្តិ")

    class Meta:
        model = Announcement
        fields = ['title', 'category', 'target_audience', 'priority', 'content', 'attachment', 'is_published']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. សេចក្តីជូនដំណឹងស្តីពីការប្រជុំមាតាបិតាសិស្សឆមាសទី១'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'target_audience': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'សរសេរខ្លឹមសារសេចក្តីជូនដំណឹងនៅទីនេះ...'}),
            'attachment': forms.FileInput(attrs={'class': 'form-control'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
