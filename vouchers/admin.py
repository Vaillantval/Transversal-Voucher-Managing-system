from django.contrib import admin
from .models import VoucherLog

@admin.register(VoucherLog)
class VoucherLogAdmin(admin.ModelAdmin):
    list_display = ('code', 'site', 'tier', 'duration_hours', 'price_htg', 'status', 'created_at')
    list_filter = ('site', 'status', 'tier')
    search_fields = ('code', 'note')
    readonly_fields = ('unifi_id', 'code', 'created_at')

    def duration_hours(self, obj):
        return f"{obj.duration_hours}h"
    duration_hours.short_description = 'Durée'
