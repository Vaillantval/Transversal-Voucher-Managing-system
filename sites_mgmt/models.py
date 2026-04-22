import functools
from django.db import models
from accounts.models import User


class HotspotSite(models.Model):
    """
    Un site de vente BonNet (correspond à un site UniFi).
    """
    name = models.CharField(max_length=100, verbose_name='Nom du site')
    unifi_site_id = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='ID site UniFi',
        help_text='Identifiant interne UniFi (ex: default, site1)',
    )
    location = models.CharField(max_length=200, blank=True, verbose_name='Localisation')
    description = models.TextField(blank=True, verbose_name='Description')
    is_active = models.BooleanField(default=True, verbose_name='Actif')
    admins = models.ManyToManyField(
        User,
        blank=True,
        related_name='managed_sites',
        limit_choices_to={'role': User.ROLE_SITE_ADMIN},
        verbose_name='Administrateurs assignés',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Site Hotspot'
        verbose_name_plural = 'Sites Hotspot'
        ordering = ['name']
        indexes = [
            models.Index(fields=['is_active', 'name']),
        ]

    def __str__(self):
        return self.name


class SiteConfig(models.Model):
    footer_text        = models.CharField(max_length=300, blank=True, verbose_name='Texte du footer')
    logo1              = models.ImageField(upload_to='site_config/', blank=True, null=True, verbose_name='Logo 1')
    logo2              = models.ImageField(upload_to='site_config/', blank=True, null=True, verbose_name='Logo 2')
    partner_conditions = models.TextField(blank=True, verbose_name='Conditions de partenariat')

    class Meta:
        verbose_name = 'Configuration du site'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def footer(self):
        return self.footer_text or '© 2026 BonNet · Transversal'


class PartnerProduct(models.Model):
    name        = models.CharField(max_length=150, verbose_name='Nom')
    description = models.TextField(blank=True, verbose_name='Description')
    price_usd   = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Prix (USD)')
    is_active   = models.BooleanField(default=True, verbose_name='Actif')
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name          = 'Produit partenaire'
        verbose_name_plural   = 'Produits partenaires'
        ordering              = ['name']

    def __str__(self):
        return f"{self.name} — ${self.price_usd}"

    def cover_image(self):
        return self.images.first()


class PartnerProductImage(models.Model):
    product = models.ForeignKey(PartnerProduct, on_delete=models.CASCADE, related_name='images')
    image   = models.ImageField(upload_to='partner_products/')
    order   = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order', 'pk']


class VoucherTier(models.Model):
    """
    Forfait tarifaire par site.
    Durée fixe (ex: 24 heures) + prix + sites concernés.
    """
    UNIT_HOURS  = 'hours'
    UNIT_DAYS   = 'days'
    UNIT_MONTHS = 'months'
    UNIT_YEARS  = 'years'
    UNIT_CHOICES = [
        (UNIT_HOURS,  'Heures'),
        (UNIT_DAYS,   'Jours'),
        (UNIT_MONTHS, 'Mois'),
        (UNIT_YEARS,  'Années'),
    ]

    # Noms courants disponibles comme suggestions
    LABEL_PRESETS = ['Code_Admin', 'Remplacement', 'Promotionnel', 'Essai']

    label     = models.CharField(max_length=100, verbose_name='Label')
    duration  = models.PositiveIntegerField(verbose_name='Durée')
    unit      = models.CharField(max_length=10, choices=UNIT_CHOICES,
                                 default=UNIT_HOURS, verbose_name='Unité')
    sites     = models.ManyToManyField(
        'HotspotSite', blank=True, related_name='tiers', verbose_name='Sites'
    )
    price_htg      = models.DecimalField(max_digits=10, decimal_places=2,
                                         default=0, verbose_name='Prix (HTG)')
    is_replacement = models.BooleanField(default=False, verbose_name='Remplacement')
    is_active      = models.BooleanField(default=True, verbose_name='Actif')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Forfait tarifaire'
        verbose_name_plural = 'Forfaits tarifaires'
        ordering = ['duration', 'unit']

    @property
    def duration_minutes(self):
        """Durée convertie en minutes pour l'API UniFi."""
        multipliers = {
            self.UNIT_HOURS:  60,
            self.UNIT_DAYS:   1440,
            self.UNIT_MONTHS: 43200,
            self.UNIT_YEARS:  525600,
        }
        return self.duration * multipliers.get(self.unit, 60)

    @property
    def is_free(self):
        return self.price_htg == 0

    @property
    def duration_display(self):
        unit_labels = {
            self.UNIT_HOURS:  'h',
            self.UNIT_DAYS:   'j',
            self.UNIT_MONTHS: 'mois',
            self.UNIT_YEARS:  'an(s)',
        }
        return f"{self.duration} {unit_labels.get(self.unit, self.unit)}"

    def __str__(self):
        price = 'Gratuit' if self.is_free else f"{self.price_htg} HTG"
        return f"{self.label} — {self.duration_display} — {price}"
