from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='sites_mgmt.HotspotSite')
def assign_admin_forfait_to_new_site(sender, instance, created, **kwargs):
    """Assigne automatiquement le(s) forfait(s) admin existants à tout nouveau site."""
    if not created:
        return
    from .models import VoucherTier
    admin_tiers = VoucherTier.objects.filter(is_admin_code=True, is_active=True)
    for tier in admin_tiers:
        tier.sites.add(instance)
