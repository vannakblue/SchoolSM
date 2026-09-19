from django import forms
from .models import NewsArticle, GalleryAlbum, GalleryPhoto, WebsiteBanner, ContactMessage


class NewsArticleForm(forms.ModelForm):
    class Meta:
        model = NewsArticle
        fields = ['title', 'title_en', 'category', 'cover_image', 'excerpt', 'excerpt_en', 'content', 'content_en', 'is_featured', 'is_published']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'បញ្ចូលចំណងជើងព័ត៌មាន (Khmer)...'}),
            'title_en': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'English news title (or leave blank to auto-translate by AI)...'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'cover_image': forms.FileInput(attrs={'class': 'form-control'}),
            'excerpt': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'សង្ខេបខ្លឹមសារខ្លីៗ (Khmer)...'}),
            'excerpt_en': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'English short excerpt (or leave blank to auto-translate by AI)...'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 10, 'placeholder': 'សរសេរខ្លឹមសារលម្អិតនៃអត្ថបទព័ត៌មាន (Khmer)...'}),
            'content_en': forms.Textarea(attrs={'class': 'form-control', 'rows': 10, 'placeholder': 'Detailed English content (or leave blank to auto-translate by AI)...'}),
            'is_featured': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class GalleryAlbumForm(forms.ModelForm):
    class Meta:
        model = GalleryAlbum
        fields = ['title', 'title_en', 'description', 'description_en', 'cover_image', 'event_date', 'is_published']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. ការប្រកួតកីឡាបាល់ទាត់ប្រចាំឆ្នាំ (Khmer)...'}),
            'title_en': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'English album title (or leave blank to auto-translate by AI)...'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'ពិពណ៌នាអំពីព្រឹត្តិការណ៍នេះ (Khmer)...'}),
            'description_en': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'English description (or leave blank to auto-translate by AI)...'}),
            'cover_image': forms.FileInput(attrs={'class': 'form-control'}),
            'event_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={'class': 'form-control'}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result


class GalleryPhotosUploadForm(forms.Form):
    photos = MultipleFileField(required=True, label="ជ្រើសរើសរូបភាព (អាចជ្រើសបានច្រើនក្នុងពេលតែមួយ)")
    caption = forms.CharField(max_length=255, required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ចំណងជើងរូបភាពរួម (ស្រេចចិត្ត)'}))


class WebsiteBannerForm(forms.ModelForm):
    class Meta:
        model = WebsiteBanner
        fields = ['title', 'subtitle', 'badge_text', 'image', 'primary_btn_text', 'primary_btn_url', 'secondary_btn_text', 'secondary_btn_url', 'order', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ស្វាគមន៍មកកាន់...'}),
            'subtitle': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'បាវចនា ឬពាក្យស្លោក...'}),
            'badge_text': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. ឆ្នាំសិក្សាថ្មី ២០២៦-២០២៧'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'primary_btn_text': forms.TextInput(attrs={'class': 'form-control'}),
            'primary_btn_url': forms.TextInput(attrs={'class': 'form-control'}),
            'secondary_btn_text': forms.TextInput(attrs={'class': 'form-control'}),
            'secondary_btn_url': forms.TextInput(attrs={'class': 'form-control'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ContactMessageForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ['name', 'phone', 'email', 'subject', 'message']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឈ្មោះពេញរបស់លោកអ្នក *', 'required': 'true'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'លេខទូរស័ព្ទទំនាក់ទំនង *', 'required': 'true'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'អាសយដ្ឋានអ៊ីមែល (ប្រសិនបើមាន)'}),
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ប្រធានបទសាកសួរ *', 'required': 'true'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'សរសេរខ្លឹមសារសំណួរ ឬសាររបស់លោកអ្នកនៅទីនេះ... *', 'required': 'true'}),
        }

    def __init__(self, *args, **kwargs):
        is_english = kwargs.pop('is_english', False)
        super().__init__(*args, **kwargs)
        if is_english:
            self.fields['name'].widget.attrs['placeholder'] = 'Your Full Name *'
            self.fields['phone'].widget.attrs['placeholder'] = 'Your Contact Phone Number *'
            self.fields['email'].widget.attrs['placeholder'] = 'Email Address (Optional)'
            self.fields['subject'].widget.attrs['placeholder'] = 'Subject of Inquiry *'
            self.fields['message'].widget.attrs['placeholder'] = 'Write your question or message here... *'

