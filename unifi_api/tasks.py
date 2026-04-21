import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='unifi_api.prewarm_all_sites', bind=True, max_retries=2)
def prewarm_all_sites(self):
    """Rafraîchit le cache Redis pour tous les sites actifs."""
    try:
        from sites_mgmt.models import HotspotSite
        from unifi_api import client as unifi

        sites = list(HotspotSite.objects.filter(is_active=True))
        if not sites:
            return
        unifi.get_all_vouchers(sites)
        unifi.get_all_guests(sites)
        unifi.get_all_site_stats(sites)
        logger.info("prewarm_all_sites OK — %d sites", len(sites))
    except Exception as exc:
        logger.error("prewarm_all_sites échoué : %s", exc)
        raise self.retry(exc=exc, countdown=30)


@shared_task(name='unifi_api.refresh_site', bind=True, max_retries=2)
def refresh_site(self, site_unifi_id: str):
    """Rafraîchit le cache d'un site précis (appelé après create/delete voucher)."""
    try:
        from sites_mgmt.models import HotspotSite
        from unifi_api.client import (
            _fetch_site_vouchers, _fetch_site_guests, _fetch_site_stats,
        )
        from django.core.cache import cache

        site = HotspotSite.objects.get(unifi_site_id=site_unifi_id)

        # Invalide d'abord le cache pour forcer un vrai refresh
        cache.delete(f'unifi_vouchers_{site_unifi_id}')
        cache.delete(f'unifi_guests_{site_unifi_id}')
        cache.delete(f'unifi_stats_{site_unifi_id}')

        _fetch_site_vouchers(site)
        _fetch_site_guests(site)
        _fetch_site_stats(site)
        logger.info("refresh_site OK — %s", site_unifi_id)
    except HotspotSite.DoesNotExist:
        logger.warning("refresh_site : site introuvable %s", site_unifi_id)
    except Exception as exc:
        logger.error("refresh_site %s échoué : %s", site_unifi_id, exc)
        raise self.retry(exc=exc, countdown=15)
