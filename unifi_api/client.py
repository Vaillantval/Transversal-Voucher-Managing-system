"""
Client UniFi pour BonNet.
"""
import logging
from datetime import datetime
from typing import Optional
from django.conf import settings
from django.core.cache import cache
from sites_mgmt.utils import TZ_HAITI

logger = logging.getLogger(__name__)

# SSL verify désactivé intentionnellement (cert auto-signé UniFi) — on supprime le spam urllib3
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# TTL cache (secondes) — pre-warm toutes les 2 min, TTL long = résilience si pre-warm rate
_TTL_SITES    = 600   # 10 min
_TTL_VOUCHERS = 600   # 10 min (était 3 min)
_TTL_CLIENTS  = 300   # 5 min
_TTL_DEVICES  = 300   # 5 min
_TTL_GUESTS   = 900   # 15 min (était 6 min — données historiques, changent peu)

# Fenêtre historique guests (heures) – 1 an
_GUEST_HISTORY_HOURS = 8760


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


def create_site(display_name: str) -> Optional[dict]:
    """Crée un nouveau site UniFi. Retourne le dict site (name=internal_id, desc=display) ou None."""
    c = _connect()
    if not c:
        return None
    try:
        result = c.create_site(display_name)
        if result and isinstance(result, list) and len(result) > 0:
            cache.delete('unifi_sites')
            return result[0]
        return None
    except Exception as e:
        logger.error(f"create_site({display_name!r}): {e}")
        return None


# ─── DEVICES / CLIENTS ────────────────────────────────────────────────────────

def get_clients(site_id: str, _c=None):
    key = f'unifi_clients_{site_id}'
    cached = cache.get(key)
    if cached is not None:
        return cached
    c = _c or get_controller(site_id)
    if not c:
        return []
    try:
        c.site_id = site_id
        clients = c.get_clients()
        cache.set(key, clients, _TTL_CLIENTS)
        return clients
    except Exception as e:
        logger.error(f"get_clients({site_id}) : {e}")
        return []


def get_devices(site_id: str, _c=None):
    key = f'unifi_devices_{site_id}'
    cached = cache.get(key)
    if cached is not None:
        return cached
    c = _c or get_controller(site_id)
    if not c:
        return []
    try:
        c.site_id = site_id
        devices = c.get_aps()
        cache.set(key, devices, _TTL_DEVICES)
        return devices
    except Exception as e:
        logger.error(f"get_devices({site_id}) : {e}")
        return []


# ─── VOUCHERS ─────────────────────────────────────────────────────────────────

def _enrich_voucher(v: dict, site_name: str, site_unifi_id: str) -> dict:
    v['site_name']      = site_name
    v['site_unifi_id']  = site_unifi_id
    v['duration_minutes'] = v.get('duration', 0)
    v['duration_hours']   = round(v['duration_minutes'] / 60, 1)
    v['voucher_id']       = v.get('_id', '')  # _id interdit dans les templates Django
    code = v.get('code', '')
    v['code_display'] = f"{code[:5]}-{code[5:]}" if len(code) > 5 else code
    ts = v.get('create_time')
    v['created_dt'] = datetime.fromtimestamp(ts, tz=TZ_HAITI) if ts else None
    start_ts = v.get('start_time')
    v['sold_ts'] = start_ts or 0
    v['sold_dt'] = datetime.fromtimestamp(start_ts, tz=TZ_HAITI) if start_ts else None

    # États précis
    used           = v.get('used', 0)
    status_expires = v.get('status_expires', 0)
    v['is_sold']    = used > 0                          # vendu (activé au moins une fois)
    v['is_active_session'] = used > 0 and status_expires > 0  # session WiFi en cours
    v['is_available']      = used == 0                  # jamais activé
    # Libellé statut
    if used == 0:
        v['status_label'] = 'Disponible'
        v['status_color'] = 'success'
    elif status_expires > 0:
        v['status_label'] = 'En cours'
        v['status_color'] = 'primary'
    else:
        v['status_label'] = 'Expiré'
        v['status_color'] = 'secondary'
    return v


def _fetch_site_vouchers(site):
    """Fetch vouchers pour un site (appelé depuis un thread)."""
    key = f'unifi_vouchers_{site.unifi_site_id}'
    cached = cache.get(key)
    if cached is not None:
        return cached
    c = get_controller(site.unifi_site_id)
    if not c:
        return []
    try:
        vouchers = [_enrich_voucher(v, site.name, site.unifi_site_id)
                    for v in c.list_vouchers()]
        cache.set(key, vouchers, _TTL_VOUCHERS)
        return vouchers
    except Exception as e:
        logger.error(f"fetch_vouchers({site.unifi_site_id}) : {e}")
        return []


def get_all_vouchers(sites) -> list:
    """Récupère les vouchers de tous les sites en parallèle."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    sites_list = list(sites)
    if not sites_list:
        return []

    all_vouchers = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_fetch_site_vouchers, site): site
                   for site in sites_list}
        for future in as_completed(futures, timeout=45):
            try:
                all_vouchers.extend(future.result())
            except Exception as e:
                logger.error(f"Thread vouchers error: {e}")
    return all_vouchers


def get_vouchers(site_id: str) -> list:
    """Liste les vouchers d'un site (usage ponctuel)."""
    c = get_controller(site_id)
    if not c:
        return []
    try:
        return c.list_vouchers()
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
        c.delete_voucher(voucher_id)
        cache.delete(f'unifi_vouchers_{site_id}')
        return True
    except Exception as e:
        logger.error(f"delete_voucher({site_id}, {voucher_id}) : {e}")
        return False


# ─── GUEST HISTORY ───────────────────────────────────────────────────────────

def _enrich_guest(g: dict, site_name: str, site_unifi_id: str) -> dict:
    g['site_name']      = site_name
    g['site_unifi_id']  = site_unifi_id
    start_ts = g.get('start', 0)
    end_ts   = g.get('end', 0)
    g['sold_ts'] = start_ts
    g['sold_dt'] = datetime.fromtimestamp(start_ts, tz=TZ_HAITI) if start_ts else None
    g['end_dt']  = datetime.fromtimestamp(end_ts,   tz=TZ_HAITI) if end_ts   else None
    g['duration_minutes'] = round((end_ts - start_ts) / 60) if start_ts and end_ts > start_ts else 0
    return g


def _fetch_site_guests(site) -> list:
    """Fetch sessions voucher pour un site via POST /stat/guest (appelé depuis un thread)."""
    key = f'unifi_guests_{site.unifi_site_id}'
    cached = cache.get(key)
    if cached is not None:
        return cached
    c = get_controller(site.unifi_site_id)
    if not c:
        return []
    try:
        # POST with within=8760 (1 year) to get full history
        raw = c._write(c._api_url() + 'stat/guest', {'within': _GUEST_HISTORY_HOURS})
        guests = [
            _enrich_guest(g, site.name, site.unifi_site_id)
            for g in (raw or [])
            if g.get('authorized_by') == 'voucher' and g.get('start')
        ]
        cache.set(key, guests, _TTL_GUESTS)
        return guests
    except Exception as e:
        logger.error(f"fetch_guests({site.unifi_site_id}) : {e}")
        return []


def get_all_guests(sites) -> list:
    """Récupère l'historique voucher-guests de tous les sites en parallèle."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    sites_list = list(sites)
    if not sites_list:
        return []
    all_guests = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_fetch_site_guests, site): site for site in sites_list}
        for future in as_completed(futures, timeout=60):
            try:
                all_guests.extend(future.result())
            except Exception as e:
                logger.error(f"Thread guests error: {e}")
    return all_guests


def get_guests(site_id: str) -> list:
    """Historique brut guests d'un site (endpoint debug)."""
    c = get_controller(site_id)
    if not c:
        return []
    try:
        return c._write(c._api_url() + 'stat/guest', {'within': _GUEST_HISTORY_HOURS}) or []
    except Exception as e:
        logger.error(f"get_guests({site_id}) : {e}")
        return []


# ─── STATISTIQUES ─────────────────────────────────────────────────────────────

def get_site_stats(site_id: str, _c=None) -> dict:
    clients = get_clients(site_id, _c)
    devices = get_devices(site_id, _c)
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


def _fetch_site_stats(site) -> tuple:
    """Retourne (site_id, stats_dict) — appelé depuis un thread."""
    key = f'unifi_stats_{site.unifi_site_id}'
    cached = cache.get(key)
    if cached is not None:
        return site.unifi_site_id, cached
    stats = get_site_stats(site.unifi_site_id)
    cache.set(key, stats, _TTL_DEVICES)
    return site.unifi_site_id, stats


def get_all_site_stats(sites) -> dict:
    """Stats de tous les sites en parallèle. Retourne {site_id: stats}."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    sites_list = list(sites)
    if not sites_list:
        return {}
    result = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_fetch_site_stats, site): site for site in sites_list}
        for future in as_completed(futures, timeout=60):
            try:
                site_id, stats = future.result()
                result[site_id] = stats
            except Exception as e:
                logger.error(f"Thread stats error: {e}")
    return result


def get_all_admins() -> list:
    """
    Retourne tous les admins avec leurs sites assignés.
    Scan get-admins sur chaque site pour construire le mapping inverse.
    Cache 5 min.
    """
    key = 'unifi_all_admins'
    cached = cache.get(key)
    if cached is not None:
        return cached

    c = _connect()
    if not c:
        return []

    try:
        all_sites = c.get_sites()
    except Exception as e:
        logger.error(f"get_all_admins get_sites : {e}")
        return []

    admin_map = {}
    for site in all_sites:
        site_id = site['name']
        try:
            admins = c._write(c.url + f"api/s/{site_id}/cmd/sitemgr", {'cmd': 'get-admins'})
            for admin in (admins or []):
                name = admin.get('name', '').strip()
                if not name:
                    continue
                if name not in admin_map:
                    admin_map[name] = {
                        'name': name,
                        'email': admin.get('email', ''),
                        'is_super': admin.get('is_super', False),
                        'site_ids': [],
                    }
                if not admin_map[name]['is_super']:
                    admin_map[name]['site_ids'].append(site_id)
        except Exception as e:
            logger.warning(f"get_all_admins({site_id}) : {e}")

    result = list(admin_map.values())
    cache.set(key, result, 300)
    return result


def can_connect() -> bool:
    """Vérifie si le contrôleur UniFi est joignable (résultat mis en cache 30 s)."""
    key = 'unifi_can_connect'
    cached = cache.get(key)
    if cached is not None:
        return cached
    result = _connect() is not None
    cache.set(key, result, 120)
    return result
