from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta, date
import json

from sites_mgmt.models import HotspotSite
from vouchers.models import VoucherLog
from unifi_api import client as unifi


@login_required
def index(request):
    if not request.user.is_authenticated:
        return redirect('accounts:login')

    today = date.today()
    # Période filtrable (défaut : 30 derniers jours)
    days = int(request.GET.get('days', 30))
    date_from = today - timedelta(days=days)

    is_super = request.user.is_superadmin
    if is_super:
        sites = HotspotSite.objects.filter(is_active=True)
    else:
        sites = request.user.managed_sites.filter(is_active=True)

    site_ids = sites.values_list('id', flat=True)

    # Vouchers sur la période
    vouchers_qs = VoucherLog.objects.filter(
        site_id__in=site_ids,
        created_at__date__gte=date_from,
    )

    total_vouchers = vouchers_qs.count()
    used_vouchers = vouchers_qs.filter(status=VoucherLog.STATUS_USED).count()
    active_vouchers = vouchers_qs.filter(status=VoucherLog.STATUS_ACTIVE).count()
    total_revenue = vouchers_qs.filter(
        status=VoucherLog.STATUS_USED
    ).aggregate(t=Sum('price_htg'))['t'] or 0

    # Revenu par site (pour chart)
    revenue_by_site = list(
        vouchers_qs.filter(status=VoucherLog.STATUS_USED)
        .values('site__name')
        .annotate(revenue=Sum('price_htg'), count=Count('id'))
        .order_by('-revenue')
    )

    # Revenu par jour (courbe)
    revenue_by_day = list(
        vouchers_qs.filter(status=VoucherLog.STATUS_USED)
        .extra(select={'day': 'DATE(created_at)'})
        .values('day')
        .annotate(revenue=Sum('price_htg'), count=Count('id'))
        .order_by('day')
    )

    # Vouchers par tranche tarifaire (donut)
    by_tier = list(
        vouchers_qs.values('tier__label', 'tier__price_htg')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    # Stats UniFi live
    live_stats = []
    for site in sites[:10]:  # limiter les appels API
        stats = unifi.get_site_stats(site.unifi_site_id)
        live_stats.append({'site': site, 'stats': stats})

    total_clients = sum(s['stats']['client_count'] for s in live_stats)
    total_devices_online = sum(s['stats']['device_online'] for s in live_stats)
    total_devices_offline = sum(s['stats']['device_offline'] for s in live_stats)

    context = {
        'page_title': 'Tableau de bord',
        'days': days,
        'period_options': [(7, '7 jours'), (30, '30 jours'), (90, '90 jours'), (365, '12 mois')],
        'date_from': date_from,
        'sites': sites,
        'sites_count': sites.count(),
        # Vouchers
        'total_vouchers': total_vouchers,
        'used_vouchers': used_vouchers,
        'active_vouchers': active_vouchers,
        'total_revenue': total_revenue,
        # Charts data (JSON)
        'revenue_by_site_json': json.dumps(revenue_by_site, default=str),
        'revenue_by_day_json': json.dumps(revenue_by_day, default=str),
        'by_tier_json': json.dumps(by_tier, default=str),
        # Stats live
        'live_stats': live_stats,
        'total_clients': total_clients,
        'total_devices_online': total_devices_online,
        'total_devices_offline': total_devices_offline,
    }
    return render(request, 'dashboard/index.html', context)
