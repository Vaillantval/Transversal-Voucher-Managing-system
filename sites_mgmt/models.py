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
    auto_generate_vouchers = models.BooleanField(
        default=False,
        verbose_name='Génération automatique',
        help_text='Génère 50 vouchers par forfait si le stock reste faible 36h après alerte.',
    )
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

    def __str__(self):
        return self.name


class SiteConfig(models.Model):
    footer_text = models.CharField(max_length=300, blank=True, verbose_name='Texte du footer')
    logo1 = models.ImageField(upload_to='site_config/', blank=True, null=True, verbose_name='Logo 1')
    logo2 = models.ImageField(upload_to='site_config/', blank=True, null=True, verbose_name='Logo 2')

    class Meta:
        verbose_name = 'Configuration du site'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def footer(self):
        return self.footer_text or '© 2026 BonNet · Transversal'


class VoucherTier(models.Model):
    """
    Tranche tarifaire définie par le superadmin.
    Ex : durée entre 0 et 720 minutes → 50 HTG
    """
    label = models.CharField(max_length=100, verbose_name='Label', help_text='Ex: Forfait 12h')
    min_minutes = models.PositiveIntegerField(verbose_name='Durée min (minutes)')
    max_minutes = models.PositiveIntegerField(verbose_name='Durée max (minutes)')
    price_htg = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Prix (HTG)',
    )
    is_active = models.BooleanField(default=True, verbose_name='Actif')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Tranche tarifaire'
        verbose_name_plural = 'Tranches tarifaires'
        ordering = ['min_minutes']

    def __str__(self):
        h_min = self.min_minutes // 60
        h_max = self.max_minutes // 60
        return f"{self.label} ({h_min}h–{h_max}h) = {self.price_htg} HTG"

    @staticmethod
    def get_price_for_minutes(minutes: int):
        """Retourne la tranche et le prix pour une durée donnée en minutes."""
        tier = VoucherTier.objects.filter(
            is_active=True,
            min_minutes__lte=minutes,
            max_minutes__gte=minutes,
        ).first()
        return tier
