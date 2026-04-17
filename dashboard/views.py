from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
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
    date_from = today - timedelta(days=days)
    date_from_ts = datetime(date_from.year, date_from.month, date_from.day).timestamp()

    is_super = request.user.is_superadmin
    if is_super:
        sites = HotspotSite.objects.filter(is_active=True)
    else:
        sites = request.user.managed_sites.filter(is_active=True)

    # Tiers chargés une seule fois pour le matching prix
    tiers = list(VoucherTier.objects.filter(is_active=True).order_by('min_minutes'))

    def tier_for(minutes):
        for t in tiers:
            if t.min_minutes <= minutes <= t.max_minutes:
                return t
        return None

    # Tous les vouchers depuis UniFi (cache 2 min)
    all_vouchers = unifi.get_all_vouchers(sites)

    # Filtre période via create_time (timestamp Unix)
    period_vouchers = [v for v in all_vouchers if v.get('create_time', 0) >= date_from_ts]

    # Enrichissement prix
    for v in period_vouchers:
        t = tier_for(v.get('duration', 0))
        v['tier_label'] = t.label if t else 'Sans tranche'
        v['price'] = float(t.price_htg) if t else 0
        v['is_used'] = v.get('used', 0) > 0

    total_vouchers = len(period_vouchers)
    used_vouchers  = sum(1 for v in period_vouchers if v['is_used'])
    active_vouchers = total_vouchers - used_vouchers
    total_revenue  = sum(v['price'] for v in period_vouchers if v['is_used'])

    # Revenu par jour
    rev_day = defaultdict(float)
    for v in period_vouchers:
        if v['is_used'] and v.get('created_dt'):
            rev_day[v['created_dt'].strftime('%Y-%m-%d')] += v['price']
    revenue_by_day = [{'day': k, 'revenue': r} for k, r in sorted(rev_day.items())]

    # Revenu par site (top 10)
    rev_site = defaultdict(float)
    for v in period_vouchers:
        if v['is_used']:
            rev_site[v.get('site_name', '?')] += v['price']
    revenue_by_site = [
        {'site__name': k, 'revenue': r}
        for k, r in sorted(rev_site.items(), key=lambda x: -x[1])[:10]
    ]

    # Répartition par tranche
    tier_counts = defaultdict(int)
    for v in period_vouchers:
        tier_counts[v['tier_label']] += 1
    by_tier = [{'tier__label': k, 'count': c}
               for k, c in sorted(tier_counts.items(), key=lambda x: -x[1])]

    # Breakdown par site : total / utilisés / non utilisés / revenu
    site_breakdown = defaultdict(lambda: {'total': 0, 'used': 0, 'unused': 0, 'revenue': 0.0})
    for v in period_vouchers:
        name = v.get('site_name', '?')
        site_breakdown[name]['total'] += 1
        if v['is_used']:
            site_breakdown[name]['used']    += 1
            site_breakdown[name]['revenue'] += v['price']
        else:
            site_breakdown[name]['unused'] += 1
    site_breakdown = sorted(site_breakdown.items(), key=lambda x: -x[1]['used'])

    # Stats live UniFi (10 premiers sites pour éviter timeout)
    live_stats = []
    for site in list(sites)[:10]:
        stats = unifi.get_site_stats(site.unifi_site_id)
        live_stats.append({'site': site, 'stats': stats})

    total_clients        = sum(s['stats']['client_count']   for s in live_stats)
    total_devices_online = sum(s['stats']['device_online']  for s in live_stats)
    total_devices_offline = sum(s['stats']['device_offline'] for s in live_stats)

    context = {
        'page_title': 'Tableau de bord',
        'days': days,
        'period_options': [(7, '7 jours'), (30, '30 jours'), (90, '90 jours'), (365, '12 mois')],
        'date_from': date_from,
        'sites': sites,
        'sites_count': sites.count(),
        'total_vouchers':  total_vouchers,
        'used_vouchers':   used_vouchers,
        'active_vouchers': active_vouchers,
        'total_revenue':   total_revenue,
        'revenue_by_site_json': json.dumps(revenue_by_site),
        'revenue_by_day_json':  json.dumps(revenue_by_day),
        'by_tier_json':         json.dumps(by_tier),
        'live_stats':            live_stats,
        'total_clients':         total_clients,
        'total_devices_online':  total_devices_online,
        'total_devices_offline': total_devices_offline,
        'site_breakdown': site_breakdown,
    }
    return render(request, 'dashboard/index.html', context)
