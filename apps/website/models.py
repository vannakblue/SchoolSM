from django.db import models
from django.conf import settings


class NewsArticle(models.Model):
    class Category(models.TextChoices):
        NEWS = 'NEWS', 'ព័ត៌មានទូទៅ / General News'
        EVENT = 'EVENT', 'ព្រឹត្តិការណ៍ & កម្មវិធីសាលា / School Event'
        ACADEMICS = 'ACADEMICS', 'កម្មវិធីសិក្សា & អប់រំ / Academics'
        ACHIEVEMENT = 'ACHIEVEMENT', 'ស្នាដៃ & មោទនភាព / Achievements'
        SPORTS = 'SPORTS', 'កីឡា & សុខភាព / Sports & Health'
        OTHER = 'OTHER', 'ផ្សេងៗ / Other'

    title = models.CharField(max_length=255, verbose_name="ចំណងជើងអត្ថបទ / Article Title")
    category = models.CharField(max_length=30, choices=Category.choices, default=Category.NEWS, verbose_name="ប្រភេទ / Category")
    excerpt = models.TextField(max_length=500, blank=True, verbose_name="ខ្លឹមសារសង្ខេប / Short Excerpt")
    content = models.TextField(verbose_name="ខ្លឹមសារលម្អិត / Full Content")
    cover_image = models.ImageField(upload_to='website/news/', blank=True, null=True, verbose_name="រូបភាព Cover / Featured Image")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="អ្នកនិពន្ធ / Author")
    views_count = models.PositiveIntegerField(default=0, verbose_name="ចំនួនអ្នកអាន / Views Count")
    is_featured = models.BooleanField(default=False, verbose_name="អត្ថបទលេចធ្លោ (Hero/Pinned) / Featured")
    is_published = models.BooleanField(default=True, verbose_name="ផ្សាយជាសាធារណៈ / Is Published")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="កាលបរិច្ឆេទបង្កើត / Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="កាលបរិច្ឆេទកែប្រែ / Updated At")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "អត្ថបទព័ត៌មានសាលា / News Article"
        verbose_name_plural = "អត្ថបទព័ត៌មានសាលាទាំងអស់ / News Articles"

    def __str__(self):
        return self.title


class GalleryAlbum(models.Model):
    title = models.CharField(max_length=200, verbose_name="ឈ្មោះអាល់ប៊ុម / Album Title")
    description = models.TextField(blank=True, null=True, verbose_name="ការពិពណ៌នា / Description")
    cover_image = models.ImageField(upload_to='website/gallery/covers/', blank=True, null=True, verbose_name="រូបភាពតំណាង / Cover Photo")
    event_date = models.DateField(blank=True, null=True, verbose_name="កាលបរិច្ឆេទកម្មវិធី / Event Date")
    is_published = models.BooleanField(default=True, verbose_name="ផ្សាយជាសាធារណៈ / Is Published")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="កាលបរិច្ឆេទបង្កើត / Created At")

    class Meta:
        ordering = ['-event_date', '-created_at']
        verbose_name = "អាល់ប៊ុមរូបភាព / Gallery Album"
        verbose_name_plural = "អាល់ប៊ុមរូបភាពទាំងអស់ / Gallery Albums"

    def __str__(self):
        return self.title

    @property
    def photo_count(self):
        return self.photos.count()


class GalleryPhoto(models.Model):
    album = models.ForeignKey(GalleryAlbum, on_delete=models.CASCADE, related_name='photos', verbose_name="អាល់ប៊ុម / Album")
    image = models.ImageField(upload_to='website/gallery/photos/', verbose_name="រូបថត / Photo")
    caption = models.CharField(max_length=255, blank=True, null=True, verbose_name="ចំណងជើងរូបភាព / Caption")
    order = models.PositiveIntegerField(default=0, verbose_name="លំដាប់រៀប / Order")
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="ថ្ងៃបញ្ចូល / Uploaded At")

    class Meta:
        ordering = ['order', 'id']
        verbose_name = "រូបថត / Photo"
        verbose_name_plural = "រូបថតទាំងអស់ / Photos"

    def __str__(self):
        return f"{self.album.title} - Photo #{self.id}"


class WebsiteBanner(models.Model):
    title = models.CharField(max_length=200, verbose_name="ចំណងជើងបដា / Banner Title")
    subtitle = models.CharField(max_length=300, blank=True, null=True, verbose_name="ចំណងជើងរង / Subtitle")
    badge_text = models.CharField(max_length=100, blank=True, null=True, verbose_name="ស្លាកចំណាំ (Badge) / Badge Text")
    image = models.ImageField(upload_to='website/banners/', blank=True, null=True, verbose_name="រូបភាពបដា / Banner Background Image")
    primary_btn_text = models.CharField(max_length=100, default="ស្វែងយល់បន្ថែម", blank=True, verbose_name="ប៊ូតុងទី១ / Primary Button Text")
    primary_btn_url = models.CharField(max_length=255, default="#about", blank=True, verbose_name="តំណភ្ជាប់ប៊ូតុងទី១ / Primary Button URL")
    secondary_btn_text = models.CharField(max_length=100, default="ចូលប្រព័ន្ធគ្រប់គ្រង", blank=True, verbose_name="ប៊ូតុងទី២ / Secondary Button Text")
    secondary_btn_url = models.CharField(max_length=255, default="/accounts/login/", blank=True, verbose_name="តំណភ្ជាប់ប៊ូតុងទី២ / Secondary Button URL")
    order = models.PositiveIntegerField(default=0, verbose_name="លំដាប់បង្ហាញ / Order")
    is_active = models.BooleanField(default=True, verbose_name="សកម្ម / Is Active")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="ថ្ងៃបង្កើត / Created At")

    class Meta:
        ordering = ['order', '-id']
        verbose_name = "ផ្ទាំងបដាទំព័រដើម / Homepage Banner"
        verbose_name_plural = "ផ្ទាំងបដាទំព័រដើមទាំងអស់ / Homepage Banners"

    def __str__(self):
        return self.title


class ContactMessage(models.Model):
    name = models.CharField(max_length=150, verbose_name="ឈ្មោះអ្នកផ្ញើ / Sender Name")
    email = models.EmailField(blank=True, null=True, verbose_name="អ៊ីមែល / Email")
    phone = models.CharField(max_length=50, verbose_name="លេខទូរស័ព្ទ / Phone Number")
    subject = models.CharField(max_length=200, verbose_name="ប្រធានបទ / Subject")
    message = models.TextField(verbose_name="ខ្លឹមសារសារ / Message")
    is_read = models.BooleanField(default=False, verbose_name="បានអានរួច / Is Read")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="កាលបរិច្ឆេទផ្ញើ / Sent Date")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "សារទំនាក់ទំនងពីភ្ញៀវ / Contact Inquiry"
        verbose_name_plural = "សារទំនាក់ទំនងពីភ្ញៀវទាំងអស់ / Contact Inquiries"

    def __str__(self):
        return f"{self.name} - {self.subject}"
