import uuid
from django.db import models


def _gen_reference():
    return 'BONNET-' + uuid.uuid4().hex[:8].upper()


class StoreUser(models.Model):
    google_id  = models.CharField(max_length=64, unique=True)
    email      = models.EmailField(unique=True)
    full_name  = models.CharField(max_length=100, verbose_name='Nom complet')
    phone      = models.CharField(max_length=20, blank=True, verbose_name='Téléphone')
    address    = models.TextField(blank=True, verbose_name='Adresse')
    avatar_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Utilisateur store'
        verbose_name_plural = 'Utilisateurs store'

    def __str__(self):
        return f'{self.full_name} ({self.email})'

    @property
    def first_name(self):
        return self.full_name.split()[0] if self.full_name else ''


class StoreBanner(models.Model):
    title     = models.CharField(max_length=100, verbose_name='Titre')
    subtitle  = models.CharField(max_length=200, blank=True, verbose_name='Sous-titre')
    image     = models.ImageField(upload_to='banners/', verbose_name='Image')
    cta_text  = models.CharField(max_length=50, default='Voir les plans', verbose_name='Texte bouton')
    order     = models.PositiveIntegerField(default=0, verbose_name='Ordre')
    is_active = models.BooleanField(default=True, verbose_name='Actif')

    class Meta:
        ordering = ['order']
        verbose_name = 'Bannière'
        verbose_name_plural = 'Bannières'

    def __str__(self):
        return self.title


class CustomerProfile(models.Model):
    store_user     = models.ForeignKey(
        StoreUser, on_delete=models.CASCADE,
        null=True, blank=True, related_name='profiles'
    )
    session_key    = models.CharField(max_length=64, null=True, blank=True, unique=True)
    full_name      = models.CharField(max_length=100, verbose_name='Nom complet')
    phone          = models.CharField(max_length=20, verbose_name='Téléphone')
    preferred_site = models.ForeignKey(
        'sites_mgmt.HotspotSite', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name='Site préféré'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Profil client'
        verbose_name_plural = 'Profils clients'

    def __str__(self):
        return f'{self.full_name} ({self.phone})'


class Cart(models.Model):
    store_user  = models.OneToOneField(
        StoreUser, on_delete=models.CASCADE,
        null=True, blank=True, related_name='cart'
    )
    session_key = models.CharField(max_length=64, null=True, blank=True, unique=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    @property
    def total(self):
        return sum(item.subtotal for item in self.items.select_related('tier').all())

    @property
    def item_count(self):
        return sum(item.quantity for item in self.items.all())

    def __str__(self):
        if self.store_user:
            return f'Panier {self.store_user.email}'
        return f'Panier {(self.session_key or "")[:8]}'


class CartItem(models.Model):
    cart     = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
    tier     = models.ForeignKey('sites_mgmt.VoucherTier', on_delete=models.PROTECT)
    site     = models.ForeignKey('sites_mgmt.HotspotSite', on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)

    @property
    def subtotal(self):
        return self.tier.price_htg * self.quantity

    def __str__(self):
        return f'{self.quantity}× {self.tier.label} @ {self.site.name}'


class Order(models.Model):
    STATUS_PENDING    = 'pending'
    STATUS_PAID       = 'paid'
    STATUS_PROCESSING = 'processing'
    STATUS_DELIVERED  = 'delivered'
    STATUS_FAILED     = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING,    'En attente'),
        (STATUS_PAID,       'Payé'),
        (STATUS_PROCESSING, 'En traitement'),
        (STATUS_DELIVERED,  'Livré'),
        (STATUS_FAILED,     'Échoué'),
    ]

    PAYMENT_MONCASH = 'moncash'
    PAYMENT_NATCASH = 'natcash'
    PAYMENT_CHOICES = [
        (PAYMENT_MONCASH, 'MonCash'),
        (PAYMENT_NATCASH, 'NatCash'),
    ]

    reference               = models.CharField(max_length=30, unique=True, default=_gen_reference)
    customer                = models.ForeignKey(CustomerProfile, on_delete=models.PROTECT, related_name='orders')
    status                  = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    payment_method          = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default=PAYMENT_MONCASH, verbose_name='Méthode de paiement')
    total_htg               = models.DecimalField(max_digits=10, decimal_places=2)
    plopplop_transaction_id = models.CharField(max_length=64, blank=True)
    created_at              = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Commande'
        verbose_name_plural = 'Commandes'

    def get_all_codes(self):
        codes = []
        for item in self.items.all():
            codes.extend(item.voucher_codes)
        return codes

    def __str__(self):
        return f'{self.reference} — {self.get_status_display()}'


class OrderItem(models.Model):
    order         = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    tier          = models.ForeignKey('sites_mgmt.VoucherTier', on_delete=models.PROTECT)
    site          = models.ForeignKey('sites_mgmt.HotspotSite', on_delete=models.PROTECT)
    quantity      = models.PositiveIntegerField()
    unit_price    = models.DecimalField(max_digits=8, decimal_places=2)
    voucher_codes = models.JSONField(default=list)

    @property
    def subtotal(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f'{self.quantity}× {self.tier.label} @ {self.site.name}'
