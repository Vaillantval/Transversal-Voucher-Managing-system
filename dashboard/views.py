from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from datetime import timedelta, date, datetime
from collections import defaultdict
import json

from sites_mgmt.models import HotspotSite, VoucherTier
from unifi_api import client as unifi


@login_required
def index(request):
    today = date.today()
    days = int(request.GET.get('days', 30))
    site_filter_id = request.GET.get('site', '')
    date_from = today - timedelta(days=days)
    date_from_ts = datetime(date_from.year, date_from.month, date_from.day).timestamp()

    is_super = request.user.is_superadmin
    if is_super:
        all_sites = HotspotSite.objects.filter(is_active=True)
    else:
        all_sites = request.user.managed_sites.filter(is_active=True)

    # Site sélectionné ou tous
    selected_site = None
    if site_filter_id:
        selected_site = all_sites.filter(unifi_site_id=site_filter_id).first()
    sites = all_sites.filter(unifi_site_id=site_filter_id) if selected_site else all_sites

    # Tiers pour matching prix
    tiers = list(VoucherTier.objects.filter(is_active=True).order_by('min_minutes'))

    def tier_for(minutes):
        for t in tiers:
            if t.min_minutes <= minutes <= t.max_minutes:
                return t
        return None

    # Vouchers depuis UniFi (cache 2 min) — enrichissement de tous les vouchers
    all_vouchers = unifi.get_all_vouchers(sites)
    for v in all_vouchers:
        t = tier_for(v.get('duration', 0))
        v['tier_label'] = t.label if t else 'Sans tranche'
        v['price']      = float(t.price_htg) if t else 0

    # Vouchers créés dans la période → pour total et disponibles
    period_vouchers = [v for v in all_vouchers if v.get('create_time', 0) >= date_from_ts]

    # Vouchers activés (vendus) dans la période → pour revenus et graphiques
    # Si start_time est disponible (sold_ts > 0) on filtre dessus (date réelle de vente),
    # sinon on replie sur create_time (UniFi ne remplit pas toujours start_time).
    sold_in_period = [
        v for v in all_vouchers
        if v['is_sold'] and (
            (v['sold_ts'] > 0 and v['sold_ts'] >= date_from_ts)
            or (v['sold_ts'] == 0 and v.get('create_time', 0) >= date_from_ts)
        )
    ]

    total_vouchers     = len(period_vouchers)
    available_vouchers = sum(1 for v in period_vouchers if v['is_available'])
    sold_vouchers      = len(sold_in_period)
    active_sessions    = sum(1 for v in sold_in_period if v['is_active_session'])
    total_revenue      = sum(v['price'] for v in sold_in_period)

    # Revenu par jour — date de vente effective (sold_dt = start_time UniFi)
    rev_day = defaultdict(float)
    for v in sold_in_period:
        day_key = (v['sold_dt'] or v['created_dt'])
        if day_key:
            rev_day[day_key.strftime('%Y-%m-%d')] += v['price']
    revenue_by_day = [{'day': k, 'revenue': r} for k, r in sorted(rev_day.items())]

    # Répartition par tranche — uniquement les vendus dans la période
    tier_counts = defaultdict(int)
    for v in sold_in_period:
        tier_counts[v['tier_label']] += 1
    by_tier = [{'tier__label': k, 'count': c}
               for k, c in sorted(tier_counts.items(), key=lambda x: -x[1])]

    # Breakdown par site — basé sur les vendus dans la période
    site_bd = defaultdict(lambda: {'total': 0, 'sold': 0, 'active_sessions': 0, 'available': 0, 'revenue': 0.0})
    for v in period_vouchers:
        name = v.get('site_name', '?')
        site_bd[name]['total'] += 1
        if v['is_available']:
            site_bd[name]['available'] += 1
    for v in sold_in_period:
        name = v.get('site_name', '?')
        site_bd[name]['sold']    += 1
        site_bd[name]['revenue'] += v['price']
        if v['is_active_session']:
            site_bd[name]['active_sessions'] += 1
    site_breakdown = sorted(site_bd.items(), key=lambda x: -x[1]['sold'])

    # ── Mode tous les sites ──────────────────────────────────────────────────
    live_stats = []
    revenue_by_site = []
    if not selected_site:
        rev_site = defaultdict(float)
        for v in sold_in_period:
            rev_site[v.get('site_name', '?')] += v['price']
        revenue_by_site = [
            {'site__name': k, 'revenue': r}
            for k, r in sorted(rev_site.items(), key=lambda x: -x[1])[:10]
        ]
        all_stats = unifi.get_all_site_stats(all_sites)
        for site in all_sites:
            live_stats.append({'site': site, 'stats': all_stats.get(site.unifi_site_id, {})})

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

    context = {
        'page_title': 'Tableau de bord',
        'days': days,
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
    }
    return render(request, 'dashboard/index.html', context)
