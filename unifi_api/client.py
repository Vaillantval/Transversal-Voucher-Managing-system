"""
Client UniFi pour BonNet.
Wrapper autour de pyunifi avec gestion d'erreurs et cache.
"""
import logging
from typing import Optional
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


def get_controller():
    """Retourne une instance Controller UniFi connectée."""
    try:
        from pyunifi.controller import Controller
        c = Controller(
            host=settings.UNIFI_HOST,
            username=settings.UNIFI_USERNAME,
            password=settings.UNIFI_PASSWORD,
            port=settings.UNIFI_PORT,
            ssl_verify=settings.UNIFI_VERIFY_SSL,
            version='UDMP-unifiOS',
        )
        return c
    except Exception as e:
        logger.error(f"Connexion UniFi échouée : {e}")
        return None


# ─── SITES ────────────────────────────────────────────────────────────────────

def get_sites():
    """Liste tous les sites UniFi."""
    cached = cache.get('unifi_sites')
    if cached:
        return cached
    c = get_controller()
    if not c:
        return []
    try:
        sites = c.get_sites()
        cache.set('unifi_sites', sites, 300)
        return sites
    except Exception as e:
        logger.error(f"get_sites : {e}")
        return []


# ─── DEVICES / CLIENTS ────────────────────────────────────────────────────────

def get_clients(site_id: str):
    """Clients actuellement connectés sur un site."""
    cache_key = f'unifi_clients_{site_id}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    c = get_controller()
    if not c:
        return []
    try:
        clients = c.get_clients()
        cache.set(cache_key, clients, 60)
        return clients
    except Exception as e:
        logger.error(f"get_clients({site_id}) : {e}")
        return []


def get_devices(site_id: str):
    """Appareils réseau (AP, switch, USG) d'un site."""
    cache_key = f'unifi_devices_{site_id}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    c = get_controller()
    if not c:
        return []
    try:
        devices = c.get_aps()
        cache.set(cache_key, devices, 120)
        return devices
    except Exception as e:
        logger.error(f"get_devices({site_id}) : {e}")
        return []


# ─── VOUCHERS ─────────────────────────────────────────────────────────────────

def get_vouchers(site_id: str):
    """
    Liste tous les vouchers d'un site.
    Retourne une liste de dicts avec : _id, code, duration, quota,
    used, note, create_time, start_time, end_time, status.
    """
    c = get_controller()
    if not c:
        return []
    try:
        vouchers = c.get_vouchers()
        # Invalidate cache
        cache.delete(f'unifi_vouchers_{site_id}')
        return vouchers
    except Exception as e:
        logger.error(f"get_vouchers({site_id}) : {e}")
        return []


def create_vouchers(
    site_id: str,
    expire_minutes: int,
    count: int = 1,
    quota: int = 1,
    note: str = '',
    up_kbps: Optional[int] = None,
    down_kbps: Optional[int] = None,
    bytes_limit: Optional[int] = None,
) -> list:
    """
    Crée des vouchers sur un site UniFi.
    expire_minutes : durée de validité en minutes (ex: 1440 = 24h)
    count          : nombre de vouchers à créer
    quota          : utilisations par voucher (0 = illimité)
    note           : étiquette/note
    Retourne la liste des vouchers créés.
    """
    c = get_controller()
    if not c:
        return []
    try:
        result = c.create_voucher(
            number=count,
            quota=quota,
            expire=expire_minutes,
            up_bandwidth=up_kbps,
            down_bandwidth=down_kbps,
            byte_quota=bytes_limit,
            note=note,
        )
        cache.delete(f'unifi_vouchers_{site_id}')
        return result or []
    except Exception as e:
        logger.error(f"create_vouchers({site_id}) : {e}")
        return []


def delete_voucher(site_id: str, voucher_id: str) -> bool:
    """Supprime un voucher par son _id UniFi."""
    c = get_controller()
    if not c:
        return False
    try:
        c.revoke_voucher(voucher_id)
        cache.delete(f'unifi_vouchers_{site_id}')
        return True
    except Exception as e:
        logger.error(f"delete_voucher({site_id}, {voucher_id}) : {e}")
        return False


# ─── STATISTIQUES ─────────────────────────────────────────────────────────────

def get_site_stats(site_id: str) -> dict:
    """
    Statistiques agrégées d'un site :
    clients connectés, devices en ligne/hors ligne.
    """
    clients = get_clients(site_id)
    devices = get_devices(site_id)

    online_devices = [d for d in devices if d.get('state') == 1]
    offline_devices = [d for d in devices if d.get('state') != 1]

    return {
        'client_count': len(clients),
        'device_total': len(devices),
        'device_online': len(online_devices),
        'device_offline': len(offline_devices),
        'devices': devices,
        'clients': clients,
    }
