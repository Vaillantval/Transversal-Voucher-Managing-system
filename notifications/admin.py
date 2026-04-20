from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'type', 'site', 'stock_count', 'is_read', 'email_sent', 'created_at']
    list_filter = ['type', 'is_read', 'email_sent', 'site']
    readonly_fields = ['created_at']
    search_fields = ['title', 'message']
