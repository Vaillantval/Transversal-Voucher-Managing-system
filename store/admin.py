from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Q
from .models import StoreBanner, CustomerProfile, Cart, CartItem, Order, OrderItem, StoreUser


@admin.register(StoreBanner)
class StoreBannerAdmin(admin.ModelAdmin):
    list_display  = ('title', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    ordering      = ('order',)


@admin.register(StoreUser)
class StoreUserAdmin(admin.ModelAdmin):
    list_display   = ('full_name', 'email', 'phone', 'address', 'created_at', 'orders_link')
    search_fields  = ('full_name', 'email', 'phone')
    readonly_fields = ('google_id', 'created_at', 'orders_link')
    ordering       = ('-created_at',)

    @admin.display(description='Commandes')
    def orders_link(self, obj):
        profiles = obj.profiles.all()
        count = Order.objects.filter(customer__in=profiles).count()
        if not count:
            return '—'
        ids = ','.join(str(p.pk) for p in profiles)
        url = reverse('admin:store_order_changelist') + f'?customer__id__in={ids}'
        return format_html('<a href="{}">{} commande(s)</a>', url, count)


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display  = ('full_name', 'phone', 'store_user_link', 'preferred_site', 'orders_count', 'created_at')
    search_fields = ('full_name', 'phone')
    readonly_fields = ('store_user_link', 'created_at')

    @admin.display(description='Compte Google')
    def store_user_link(self, obj):
        if not obj.store_user:
            return '—'
        url = reverse('admin:store_storeuser_change', args=[obj.store_user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.store_user.email)

    @admin.display(description='Commandes')
    def orders_count(self, obj):
        count = obj.orders.count()
        if not count:
            return '—'
        url = reverse('admin:store_order_changelist') + f'?customer__id__exact={obj.pk}'
        return format_html('<a href="{}">{}</a>', url, count)


class OrderItemInline(admin.TabularInline):
    model           = OrderItem
    extra           = 0
    fields          = ('tier', 'site', 'quantity', 'unit_price', 'voucher_codes_display')
    readonly_fields = ('voucher_codes_display',)

    @admin.display(description='Codes livrés')
    def voucher_codes_display(self, obj):
        if not obj.voucher_codes:
            return '—'
        badges = ' '.join(
            f'<code style="background:#f3f4f6;padding:2px 6px;border-radius:4px;font-size:.85em">{c}</code>'
            for c in obj.voucher_codes
        )
        return format_html(badges)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display    = ('reference', 'client_name', 'client_phone', 'sites_display',
                       'payment_method', 'total_htg', 'status', 'created_at')
    list_filter     = ('status', 'payment_method', 'items__site')
    search_fields   = ('reference', 'customer__full_name', 'customer__phone',
                       'plopplop_transaction_id')
    search_help_text = 'Référence, nom client, téléphone, transaction PlopPlop ou code voucher (10 chiffres)'
    date_hierarchy  = 'created_at'
    readonly_fields = ('reference', 'plopplop_transaction_id', 'created_at', 'store_user_link')
    inlines         = [OrderItemInline]
    ordering        = ('-created_at',)

    fieldsets = (
        ('Commande', {
            'fields': ('reference', 'status', 'payment_method', 'total_htg', 'created_at')
        }),
        ('Paiement', {
            'fields': ('plopplop_transaction_id',)
        }),
        ('Client', {
            'fields': ('customer', 'store_user_link')
        }),
    )

    @admin.display(description='Client', ordering='customer__full_name')
    def client_name(self, obj):
        return obj.customer.full_name if obj.customer else '—'

    @admin.display(description='Téléphone')
    def client_phone(self, obj):
        return obj.customer.phone if obj.customer else '—'

    @admin.display(description='Site(s)')
    def sites_display(self, obj):
        names = {item.site.name for item in obj.items.all() if item.site}
        return ', '.join(sorted(names)) or '—'

    @admin.display(description='Compte Google')
    def store_user_link(self, obj):
        if not obj.customer or not obj.customer.store_user:
            return '—'
        su = obj.customer.store_user
        url = reverse('admin:store_storeuser_change', args=[su.pk])
        return format_html('<a href="{}">{} ({})</a>', url, su.full_name, su.email)

    def get_search_results(self, request, queryset, search_term):
        queryset, may_have_duplicates = super().get_search_results(request, queryset, search_term)
        # Si le terme ressemble à un code voucher (10 chiffres), chercher dans les JSONField
        if search_term and search_term.isdigit() and len(search_term) == 10:
            voucher_qs = Order.objects.filter(items__voucher_codes__contains=search_term)
            queryset |= voucher_qs
            may_have_duplicates = True
        return queryset, may_have_duplicates

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'customer__store_user'
        ).prefetch_related('items__site')


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('store_user', 'session_key', 'item_count', 'created_at')

    @admin.display(description='Articles')
    def item_count(self, obj):
        return obj.item_count
