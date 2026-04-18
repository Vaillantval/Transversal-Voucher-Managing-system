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

    # Vouchers depuis UniFi (cache 2 min)
    all_vouchers = unifi.get_all_vouchers(sites)
    period_vouchers = [v for v in all_vouchers if v.get('create_time', 0) >= date_from_ts]

    for v in period_vouchers:
        t = tier_for(v.get('duration', 0))
        v['tier_label'] = t.label if t else 'Sans tranche'
        v['price']      = float(t.price_htg) if t else 0

    total_vouchers   = len(period_vouchers)
    sold_vouchers    = sum(1 for v in period_vouchers if v['is_sold'])
    active_sessions  = sum(1 for v in period_vouchers if v['is_active_session'])
    available_vouchers = sum(1 for v in period_vouchers if v['is_available'])
    total_revenue    = sum(v['price'] for v in period_vouchers if v['is_sold'])

    # Revenu par jour
    rev_day = defaultdict(float)
    for v in period_vouchers:
        if v['is_sold'] and v.get('created_dt'):
            rev_day[v['created_dt'].strftime('%Y-%m-%d')] += v['price']
    revenue_by_day = [{'day': k, 'revenue': r} for k, r in sorted(rev_day.items())]

    # Répartition par tranche
    tier_counts = defaultdict(int)
    for v in period_vouchers:
        tier_counts[v['tier_label']] += 1
    by_tier = [{'tier__label': k, 'count': c}
               for k, c in sorted(tier_counts.items(), key=lambda x: -x[1])]

    # Breakdown par site
    site_bd = defaultdict(lambda: {'total': 0, 'sold': 0, 'active_sessions': 0, 'available': 0, 'revenue': 0.0})
    for v in period_vouchers:
        name = v.get('site_name', '?')
        site_bd[name]['total'] += 1
        if v['is_sold']:
            site_bd[name]['sold']    += 1
            site_bd[name]['revenue'] += v['price']
        if v['is_active_session']:
            site_bd[name]['active_sessions'] += 1
        if v['is_available']:
            site_bd[name]['available'] += 1
    site_breakdown = sorted(site_bd.items(), key=lambda x: -x[1]['sold'])

    # ── Mode tous les sites ──────────────────────────────────────────────────
    live_stats = []
    revenue_by_site = []
    if not selected_site:
        rev_site = defaultdict(float)
        for v in period_vouchers:
            if v['is_sold']:
                rev_site[v.get('site_name', '?')] += v['price']
        revenue_by_site = [
            {'site__name': k, 'revenue': r}
            for k, r in sorted(rev_site.items(), key=lambda x: -x[1])[:10]
        ]
        for site in list(all_sites)[:10]:
            stats = unifi.get_site_stats(site.unifi_site_id)
            live_stats.append({'site': site, 'stats': stats})

    total_clients         = sum(s['stats']['client_count']   for s in live_stats)
    total_devices_online  = sum(s['stats']['device_online']  for s in live_stats)
    total_devices_offline = sum(s['stats']['device_offline'] for s in live_stats)

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
