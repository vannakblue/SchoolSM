from django import forms
from .models import NewsArticle, GalleryAlbum, GalleryPhoto, WebsiteBanner, ContactMessage


class NewsArticleForm(forms.ModelForm):
    class Meta:
        model = NewsArticle
        fields = ['title', 'category', 'cover_image', 'excerpt', 'content', 'is_featured', 'is_published']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'បញ្ចូលចំណងជើងព័ត៌មាន...'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'cover_image': forms.FileInput(attrs={'class': 'form-control'}),
            'excerpt': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'សង្ខេបខ្លឹមសារខ្លីៗសម្រាប់បង្ហាញលើកាតព័ត៌មាន...'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 10, 'placeholder': 'សរសេរខ្លឹមសារលម្អិតនៃអត្ថបទព័ត៌មាន...'}),
            'is_featured': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class GalleryAlbumForm(forms.ModelForm):
    class Meta:
        model = GalleryAlbum
        fields = ['title', 'description', 'cover_image', 'event_date', 'is_published']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ឧ. ទិវាគ្រូបង្រៀន ឬ ការប្រកួតកីឡាសាលា...'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'ពិពណ៌នាអំពីព្រឹត្តិការណ៍នេះ...'}),
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
