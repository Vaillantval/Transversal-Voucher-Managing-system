from django.db import models
from sites_mgmt.models import HotspotSite


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
