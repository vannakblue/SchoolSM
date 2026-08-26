from django.contrib import admin
from .models import User, SchoolProfile, TelegramConfig, NotificationLog

@admin.register(SchoolProfile)
class SchoolProfileAdmin(admin.ModelAdmin):
    list_display = ('name_kh', 'school_code', 'province', 'principal_name', 'phone', 'updated_at')

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'khmer_name', 'role', 'phone', 'is_active')
    list_filter = ('role', 'is_active')
    search_fields = ('username', 'khmer_name', 'latin_name', 'phone')

@admin.register(TelegramConfig)
class TelegramConfigAdmin(admin.ModelAdmin):
    list_display = ('bot_token', 'chat_id', 'is_active')

@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ('title', 'recipient_name', 'channel', 'status', 'created_at')
    list_filter = ('channel', 'status', 'created_at')

