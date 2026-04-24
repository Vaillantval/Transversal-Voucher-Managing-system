from django.contrib import admin
from .models import StoreBanner, CustomerProfile, Cart, CartItem, Order, OrderItem


@admin.register(StoreBanner)
class StoreBannerAdmin(admin.ModelAdmin):
    list_display  = ('title', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    ordering      = ('order',)


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'phone', 'preferred_site', 'created_at')
    search_fields = ('full_name', 'phone')


class OrderItemInline(admin.TabularInline):
    model  = OrderItem
    extra  = 0
    fields = ('tier', 'site', 'quantity', 'unit_price', 'voucher_codes')
    readonly_fields = ('voucher_codes',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display   = ('reference', 'customer', 'status', 'total_htg', 'created_at')
    list_filter    = ('status',)
    search_fields  = ('reference', 'customer__full_name', 'customer__phone')
    readonly_fields = ('reference', 'plopplop_transaction_id', 'created_at')
    inlines        = [OrderItemInline]


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('session_key', 'created_at')
