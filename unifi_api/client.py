"""
Client UniFi pour BonNet.
"""
import logging
from datetime import datetime
from typing import Optional
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# TTL cache (secondes)
_TTL_SITES    = 300   # 5 min
_TTL_VOUCHERS = 120   # 2 min
_TTL_CLIENTS  = 60    # 1 min
_TTL_DEVICES  = 120   # 2 min


def _connect() -> Optional[object]:
    """Ouvre une session UniFi (1 login). Retourne le controller ou None."""
    try:
        from pyunifi.controller import Controller
        return Controller(
            host=settings.UNIFI_HOST,
            username=settings.UNIFI_USERNAME,
            password=settings.UNIFI_PASSWORD,
            port=settings.UNIFI_PORT,
            ssl_verify=settings.UNIFI_VERIFY_SSL,
            version='v5',
        )
    except Exception as e:
        logger.error(f"Connexion UniFi échouée : {e}")
        return None


def get_controller(site_id: str = 'default'):
    """Controller pour un site précis (usage ponctuel : create/delete)."""
    try:
        from pyunifi.controller import Controller
        return Controller(
            host=settings.UNIFI_HOST,
            username=settings.UNIFI_USERNAME,
            password=settings.UNIFI_PASSWORD,
            port=settings.UNIFI_PORT,
            ssl_verify=settings.UNIFI_VERIFY_SSL,
            version='v5',
            site_id=site_id,
        )
    except Exception as e:
        logger.error(f"Connexion UniFi échouée (site={site_id}) : {e}")
        return None


# ─── SITES ────────────────────────────────────────────────────────────────────

def get_sites():
    cached = cache.get('unifi_sites')
    if cached is not None:
        return cached
    c = _connect()
    if not c:
        return []
    try:
        sites = c.get_sites()
        cache.set('unifi_sites', sites, _TTL_SITES)
        return sites
    except Exception as e:
        logger.error(f"get_sites : {e}")
        return []


# ─── DEVICES / CLIENTS ────────────────────────────────────────────────────────

def get_clients(site_id: str):
    key = f'unifi_clients_{site_id}'
    cached = cache.get(key)
    if cached is not None:
        return cached
    c = get_controller(site_id)
    if not c:
        return []
    try:
        clients = c.get_clients()
        cache.set(key, clients, _TTL_CLIENTS)
        return clients
    except Exception as e:
        logger.error(f"get_clients({site_id}) : {e}")
        return []


def get_devices(site_id: str):
    key = f'unifi_devices_{site_id}'
    cached = cache.get(key)
    if cached is not None:
        return cached
    c = get_controller(site_id)
    if not c:
        return []
    try:
        devices = c.get_aps()
        cache.set(key, devices, _TTL_DEVICES)
        return devices
    except Exception as e:
        logger.error(f"get_devices({site_id}) : {e}")
        return []


# ─── VOUCHERS ─────────────────────────────────────────────────────────────────

def _enrich_voucher(v: dict, site_name: str, site_unifi_id: str) -> dict:
    v['site_name'] = site_name
    v['site_unifi_id'] = site_unifi_id
    v['duration_hours'] = round(v.get('duration', 0) / 60, 1)
    ts = v.get('create_time')
    v['created_dt'] = datetime.fromtimestamp(ts) if ts else None
    return v


def get_all_vouchers(sites) -> list:
    """
    Récupère les vouchers de tous les sites en un seul login,
    avec cache par site.
    """
    all_vouchers = []
    c = _connect()  # 1 seul login pour tous les sites
    if not c:
        return []

    for site in sites:
        key = f'unifi_vouchers_{site.unifi_site_id}'
        cached = cache.get(key)
        if cached is not None:
            all_vouchers.extend(cached)
            continue
        try:
            c._site = site.unifi_site_id  # changer de site sans re-login
            vouchers = [_enrich_voucher(v, site.name, site.unifi_site_id)
                        for v in c.get_vouchers()]
            cache.set(key, vouchers, _TTL_VOUCHERS)
            all_vouchers.extend(vouchers)
        except Exception as e:
            logger.error(f"get_all_vouchers({site.unifi_site_id}) : {e}")

    return all_vouchers


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
    c = get_controller(site_id)
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
    c = get_controller(site_id)
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
    clients = get_clients(site_id)
    devices = get_devices(site_id)
    online  = [d for d in devices if d.get('state') == 1]
    offline = [d for d in devices if d.get('state') != 1]
    return {
        'client_count':    len(clients),
        'device_total':    len(devices),
        'device_online':   len(online),
        'device_offline':  len(offline),
        'devices':         devices,
        'clients':         clients,
    }
