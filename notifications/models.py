from django.db import models
from sites_mgmt.models import HotspotSite


class Notification(models.Model):
    TYPE_STOCK_LOW = 'stock_low'
    TYPE_MONTHLY_REPORT = 'monthly_report'
    TYPE_CHOICES = [
        (TYPE_STOCK_LOW, 'Stock faible'),
        (TYPE_MONTHLY_REPORT, 'Rapport mensuel'),
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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_type_display()}] {self.title}"

    @property
    def icon(self):
        return 'exclamation-triangle-fill' if self.type == self.TYPE_STOCK_LOW else 'file-earmark-bar-graph-fill'

    @property
    def color(self):
        return 'warning' if self.type == self.TYPE_STOCK_LOW else 'info'
