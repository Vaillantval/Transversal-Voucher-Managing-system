from django.db import models
from sites_mgmt.models import HotspotSite, VoucherTier
from accounts.models import User


class VoucherLog(models.Model):
    STATUS_ACTIVE = 'active'
    STATUS_USED = 'used'
    STATUS_EXPIRED = 'expired'
    STATUS_REVOKED = 'revoked'

    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Actif'),
        (STATUS_USED, 'Utilisé'),
        (STATUS_EXPIRED, 'Expiré'),
        (STATUS_REVOKED, 'Révoqué'),
    ]

    site = models.ForeignKey(HotspotSite, on_delete=models.CASCADE, related_name='voucher_logs')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_vouchers')
    tier = models.ForeignKey(VoucherTier, on_delete=models.SET_NULL, null=True, blank=True)

    unifi_id = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20)
    duration_minutes = models.PositiveIntegerField()
    quota = models.PositiveIntegerField(default=1)
    note = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    price_htg = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Voucher'
        verbose_name_plural = 'Vouchers'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['site', 'created_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.code} — {self.site.name} ({self.get_status_display()})"

    @property
    def duration_hours(self):
        return round(self.duration_minutes / 60, 1)
