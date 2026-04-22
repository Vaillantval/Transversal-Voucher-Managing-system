from django.contrib import admin
from .models import HotspotSite, VoucherTier

@admin.register(HotspotSite)
class HotspotSiteAdmin(admin.ModelAdmin):
    list_display = ('name', 'unifi_site_id', 'location', 'is_active')
    filter_horizontal = ('admins',)

@admin.register(VoucherTier)
class VoucherTierAdmin(admin.ModelAdmin):
    list_display = ('label', 'duration', 'unit', 'price_htg', 'is_active')
    filter_horizontal = ('sites',)
    ordering = ('duration', 'unit')
