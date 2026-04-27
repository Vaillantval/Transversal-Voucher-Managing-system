from django.conf import settings
from django.db import models
from store.models import StoreUser


class DeviceToken(models.Model):
    store_user = models.ForeignKey(StoreUser, on_delete=models.CASCADE, related_name='device_tokens')
    fcm_token  = models.TextField()
    platform   = models.CharField(max_length=10, choices=[('android', 'Android'), ('ios', 'iOS')])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('store_user', 'fcm_token')
        verbose_name = 'Device token'
        verbose_name_plural = 'Device tokens'

    def __str__(self):
        return f'{self.store_user.email} — {self.platform}'


class PushCampaign(models.Model):
    TARGET_ALL  = 'all'
    TARGET_SITE = 'site'
    TARGET_CHOICES = [
        (TARGET_ALL,  'Tous les clients'),
        (TARGET_SITE, 'Par site'),
    ]

    title            = models.CharField(max_length=100, verbose_name='Titre')
    body             = models.TextField(verbose_name='Message')
    target           = models.CharField(max_length=20, choices=TARGET_CHOICES, default=TARGET_ALL, verbose_name='Cible')
    target_site      = models.ForeignKey(
        'sites_mgmt.HotspotSite', null=True, blank=True,
        on_delete=models.SET_NULL, verbose_name='Site cible',
    )
    notif_promo_only = models.BooleanField(
        default=True, verbose_name='Promos seulement',
        help_text='Envoyer uniquement aux clients ayant activé les notifs promo',
    )
    sent_at          = models.DateTimeField(null=True, blank=True, verbose_name='Envoyée le')
    recipients_count = models.PositiveIntegerField(default=0, verbose_name='Destinataires atteints')
    created_by       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, verbose_name='Créée par',
    )
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Campagne push'
        verbose_name_plural = 'Campagnes push'

    def __str__(self):
        return self.title

    @property
    def is_sent(self):
        return self.sent_at is not None
