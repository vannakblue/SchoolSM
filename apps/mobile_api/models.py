from django.db import models
from django.conf import settings


class DeviceFCMToken(models.Model):
    """
    Stores Firebase Cloud Messaging (FCM) device registration tokens for push notifications.
    """
    DEVICE_TYPES = (
        ('android', 'Android'),
        ('ios', 'iOS'),
        ('web', 'Web'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='fcm_tokens',
        verbose_name="អ្នកប្រើប្រាស់"
    )
    token = models.CharField(max_length=512, unique=True, verbose_name="FCM Token")
    device_type = models.CharField(max_length=20, choices=DEVICE_TYPES, default='android', verbose_name="ប្រភេទឧបករណ៍")
    device_name = models.CharField(max_length=150, blank=True, null=True, verbose_name="ឈ្មោះឧបករណ៍")
    app_version = models.CharField(max_length=50, blank=True, null=True, verbose_name="ជំនាន់ App")
    is_active = models.BooleanField(default=True, verbose_name="ដំណើរការ")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="កាលបរិច្ឆេទបង្កើត")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="កែប្រែចុងក្រោយ")

    class Meta:
        verbose_name = "Device FCM Token"
        verbose_name_plural = "Device FCM Tokens"
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.user.username} ({self.device_type}) - {self.token[:20]}..."


class MobileNotificationLog(models.Model):
    """
    Logs all push notifications sent to mobile apps.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='mobile_notifications',
        verbose_name="អ្នកទទួល"
    )
    title = models.CharField(max_length=255, verbose_name="ចំណងជើង")
    body = models.TextField(verbose_name="ខ្លឹមសារ")
    data_payload = models.JSONField(default=dict, blank=True, verbose_name="Data Payload")
    is_read = models.BooleanField(default=False, verbose_name="បានអាន")
    sent_at = models.DateTimeField(auto_now_add=True, verbose_name="កាលបរិច្ឆេទផ្ញើ")

    class Meta:
        verbose_name = "Mobile Notification"
        verbose_name_plural = "Mobile Notifications"
        ordering = ['-sent_at']

    def __str__(self):
        return f"To {self.user.username}: {self.title}"
