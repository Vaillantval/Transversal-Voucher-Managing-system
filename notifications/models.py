from django.db import models
from sites_mgmt.models import HotspotSite


class AutoGenConfig(models.Model):
    """Singleton — configuration globale de la génération automatique de vouchers."""
    enabled = models.BooleanField(
        default=False,
        verbose_name='Génération automatique activée',
    )
    count_per_tier = models.PositiveIntegerField(
        default=100,
        verbose_name='Vouchers à générer par forfait',
    )
    delay_hours = models.PositiveIntegerField(
        default=24,
        verbose_name='Délai avant génération (heures après alerte stock)',
    )
    sites = models.ManyToManyField(
        HotspotSite,
        blank=True,
        related_name='autogen_configs',
        verbose_name='Sites concernés',
    )

    class Meta:
        verbose_name = 'Configuration génération automatique'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        status = 'activée' if self.enabled else 'désactivée'
        return f'AutoGen ({status}, {self.count_per_tier} vouchers/forfait, délai {self.delay_hours}h)'


class Notification(models.Model):
    TYPE_STOCK_LOW = 'stock_low'
    TYPE_MONTHLY_REPORT = 'monthly_report'
    TYPE_AUTO_GENERATED = 'auto_generated'
    TYPE_CHOICES = [
        (TYPE_STOCK_LOW, 'Stock faible'),
        (TYPE_MONTHLY_REPORT, 'Rapport mensuel'),
        (TYPE_AUTO_GENERATED, 'Génération automatique'),
    ]

    type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    site = models.ForeignKey(
        HotspotSite, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='notifications',
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    stock_count = models.PositiveIntegerField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    email_sent = models.BooleanField(default=False)
    auto_gen_triggered = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_type_display()}] {self.title}"

    @property
    def icon(self):
        icons = {
            self.TYPE_STOCK_LOW: 'exclamation-triangle-fill',
            self.TYPE_MONTHLY_REPORT: 'file-earmark-bar-graph-fill',
            self.TYPE_AUTO_GENERATED: 'lightning-charge-fill',
        }
        return icons.get(self.type, 'bell-fill')

    @property
    def color(self):
        colors = {
            self.TYPE_STOCK_LOW: 'warning',
            self.TYPE_MONTHLY_REPORT: 'info',
            self.TYPE_AUTO_GENERATED: 'success',
        }
        return colors.get(self.type, 'secondary')
