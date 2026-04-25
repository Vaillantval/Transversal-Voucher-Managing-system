from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from datetime import timedelta, date, datetime
from collections import defaultdict
import json

from sites_mgmt.models import HotspotSite, VoucherTier
from sites_mgmt.utils import find_tier, TZ_HAITI
from unifi_api import client as unifi


@login_required
def index(request):
    site_filter_id = request.GET.get('site', '')

    # Période : custom (cv + cu) ou bouton rapide (days)
    cv_raw   = request.GET.get('cv', '').strip()
    cu       = request.GET.get('cu', 'days')
    days_raw = request.GET.get('days', '')

    if cv_raw:
        cv_int = max(1, int(cv_raw))
        if cu == 'hours':
            delta = timedelta(hours=cv_int)
        elif cu == 'months':
            delta = timedelta(days=cv_int * 30)
        else:
            cu = 'days'
            delta = timedelta(days=cv_int)
        custom_value = str(cv_int)
    else:
        days_int    = int(days_raw) if days_raw else 30
        delta       = timedelta(days=days_int)
        cu          = 'days'
        custom_value = str(days_int)
        cv_int      = days_int

    now_dt       = datetime.now(TZ_HAITI)
    date_from_dt = now_dt - delta
    date_from_ts = date_from_dt.timestamp()
    date_from    = date_from_dt.date()
    days         = cv_int  # kept for template backward-compat (period buttons)

    is_super = request.user.is_superadmin
    if is_super:
        all_sites = HotspotSite.objects.filter(is_active=True)
    else:
        all_sites = request.user.managed_sites.filter(is_active=True)

    # Site_admin avec un seul site → vue détaillée directement (pas de tableau de breakdown vide)
    if not is_super and not site_filter_id:
        managed = list(all_sites.values_list('unifi_site_id', flat=True))
        if len(managed) == 1:
            from django.shortcuts import redirect as _redir
            params = request.GET.copy()
            params['site'] = managed[0]
            return _redir(f"{request.path}?{params.urlencode()}")

    # Site sélectionné ou tous
    selected_site = None
    if site_filter_id:
        selected_site = all_sites.filter(unifi_site_id=site_filter_id).first()
    sites = all_sites.filter(unifi_site_id=site_filter_id) if selected_site else all_sites

    now_ts = now_dt.timestamp()

    # Tiers par site (M2M)
    _all_tiers = VoucherTier.objects.filter(is_active=True).prefetch_related('sites')
    tiers_by_site_pk = defaultdict(list)
    for _t in _all_tiers:
        for _s in _t.sites.all():
            tiers_by_site_pk[_s.pk].append(_t)
    unifi_to_site_pk = {s.unifi_site_id: s.pk for s in all_sites}

    # ── Vouchers disponibles (non utilisés) ──────────────────────────────────
    all_vouchers       = unifi.get_all_vouchers(sites)
    period_vouchers    = [v for v in all_vouchers if v.get('create_time', 0) >= date_from_ts]
    # Stock total disponible : indépendant de la période (UniFi ne renvoie que les non-utilisés)
    available_vouchers = sum(1 for v in all_vouchers if v['is_available'])
    total_vouchers     = available_vouchers

    # ── Sessions voucher activées = source réelle des revenus ────────────────
    # UniFi supprime les vouchers de /stat/voucher dès activation ;
    # /stat/guest (POST with within=8760) est la seule source fiable.
    all_guests = unifi.get_all_guests(sites)

    for g in all_guests:
        _spk = unifi_to_site_pk.get(g.get('site_unifi_id', ''))
        _site_tiers = tiers_by_site_pk.get(_spk, []) if _spk else []
        t = find_tier(_site_tiers, g['duration_minutes'])
        g['tier_label'] = t.label if t else 'Sans tranche'
        g['price']      = float(t.price_htg) if t else 0

    sold_in_period  = [g for g in all_guests if g['sold_ts'] >= date_from_ts]
    for g in sold_in_period:
        g['is_currently_active'] = g.get('end', 0) > now_ts
    sold_vouchers   = len(sold_in_period)
    active_sessions = sum(1 for g in sold_in_period if g['is_currently_active'])
    total_revenue   = sum(g['price'] for g in sold_in_period)

    # Revenu par jour
    rev_day = defaultdict(float)
    for g in sold_in_period:
        if g['sold_dt']:
            rev_day[g['sold_dt'].strftime('%Y-%m-%d')] += g['price']
    revenue_by_day = [{'day': k, 'revenue': r} for k, r in sorted(rev_day.items())]

    # Répartition par tranche
    tier_counts = defaultdict(int)
    for g in sold_in_period:
        tier_counts[g['tier_label']] += 1
    by_tier = [{'tier__label': k, 'count': c}
               for k, c in sorted(tier_counts.items(), key=lambda x: -x[1])]

    # Breakdown par site (keyed par unifi_site_id pour permettre les liens)
    site_bd = defaultdict(lambda: {'name': '?', 'site_id': '', 'total': 0, 'sold': 0, 'active_sessions': 0, 'available': 0, 'revenue': 0.0})
    for v in period_vouchers:
        sid = v.get('site_unifi_id', '')
        site_bd[sid]['name']    = v.get('site_name', '?')
        site_bd[sid]['site_id'] = sid
        site_bd[sid]['total']  += 1
        if v['is_available']:
            site_bd[sid]['available'] += 1
    for g in sold_in_period:
        sid = g.get('site_unifi_id', '')
        site_bd[sid]['name']    = g.get('site_name', '?')
        site_bd[sid]['site_id'] = sid
        site_bd[sid]['sold']    += 1
        site_bd[sid]['revenue'] += g['price']
        if g.get('end', 0) > now_ts:
            site_bd[sid]['active_sessions'] += 1
    site_breakdown = sorted(site_bd.values(), key=lambda x: -x['revenue'])

    # ── Mode tous les sites ──────────────────────────────────────────────────
    live_stats = []
    revenue_by_site = []
    if not selected_site:
        rev_site = defaultdict(float)
        for g in sold_in_period:
            rev_site[g.get('site_name', '?')] += g['price']
        revenue_by_site = [
            {'site__name': k, 'revenue': r}
            for k, r in sorted(rev_site.items(), key=lambda x: -x[1])[:10]
        ]
        all_stats = unifi.get_all_site_stats(all_sites)
        for site in all_sites:
            live_stats.append({'site': site, 'stats': all_stats.get(site.unifi_site_id, {})})
        live_stats.sort(key=lambda x: -x['stats'].get('client_count', 0))

    total_clients         = sum(s['stats'].get('client_count', 0)   for s in live_stats)
    total_devices_online  = sum(s['stats'].get('device_online', 0)  for s in live_stats)
    total_devices_offline = sum(s['stats'].get('device_offline', 0) for s in live_stats)

    # ── Mode site unique : clients + devices live ────────────────────────────
    site_live = {}
    site_clients_list = []
    site_devices_list = []
    if selected_site:
        site_live = unifi.get_site_stats(selected_site.unifi_site_id)
        total_clients         = site_live.get('client_count', 0)
        total_devices_online  = site_live.get('device_online', 0)
        total_devices_offline = site_live.get('device_offline', 0)
        site_clients_list = site_live.get('clients', [])
        site_devices_list = site_live.get('devices', [])
        for c in site_clients_list:
            c['display_name'] = c.get('hostname') or c.get('last_ip') or c.get('mac', '?')

    unifi_warning = not unifi.can_connect()

    # Admins du site sélectionné
    site_admins = []
    if selected_site:
        from accounts.models import User as UserModel
        site_admins = list(
            UserModel.objects.filter(managed_sites=selected_site)
            .order_by('role', 'username')
        )

    context = {
        'page_title': 'Tableau de bord',
        'days': days,
        'custom_value': custom_value,
        'custom_unit': cu,
        'period_options': [(7, '7 jours'), (30, '30 jours'), (90, '90 jours'), (365, '12 mois')],
        'date_from': date_from,
        'all_sites': all_sites,
        'selected_site': selected_site,
        'selected_site_id': site_filter_id,
        'sites_count': sites.count(),
        'total_vouchers':     total_vouchers,
        'sold_vouchers':      sold_vouchers,
        'active_sessions':    active_sessions,
        'available_vouchers': available_vouchers,
        'total_revenue':      total_revenue,
        'revenue_by_site_json': json.dumps(revenue_by_site),
        'revenue_by_day_json':  json.dumps(revenue_by_day),
        'by_tier_json':         json.dumps(by_tier),
        'site_breakdown':        site_breakdown,
        'live_stats':            live_stats,
        'total_clients':         total_clients,
        'total_devices_online':  total_devices_online,
        'total_devices_offline': total_devices_offline,
        'site_clients_list':     site_clients_list,
        'site_devices_list':     site_devices_list,
        'period_vouchers':        period_vouchers,
        'sold_in_period':         sold_in_period,
        'all_available_vouchers': [v for v in all_vouchers if v['is_available']],
        'unifi_warning':          unifi_warning,
        'site_admins':            site_admins,
    }
    return render(request, 'dashboard/index.html', context)
