from django.contrib import admin
from .models import NewsArticle, GalleryAlbum, GalleryPhoto, WebsiteBanner, ContactMessage


class GalleryPhotoInline(admin.TabularInline):
    model = GalleryPhoto
    extra = 3


@admin.register(NewsArticle)
class NewsArticleAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'author', 'views_count', 'is_featured', 'is_published', 'created_at']
    list_filter = ['category', 'is_featured', 'is_published', 'created_at']
    search_fields = ['title', 'excerpt', 'content']
    date_hierarchy = 'created_at'


@admin.register(GalleryAlbum)
class GalleryAlbumAdmin(admin.ModelAdmin):
    list_display = ['title', 'event_date', 'photo_count', 'is_published', 'created_at']
    list_filter = ['is_published', 'event_date']
    search_fields = ['title', 'description']
    inlines = [GalleryPhotoInline]


@admin.register(WebsiteBanner)
class WebsiteBannerAdmin(admin.ModelAdmin):
    list_display = ['title', 'order', 'is_active', 'created_at']
    list_editable = ['order', 'is_active']


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'email', 'subject', 'is_read', 'created_at']
    list_filter = ['is_read', 'created_at']
    search_fields = ['name', 'phone', 'email', 'subject', 'message']
