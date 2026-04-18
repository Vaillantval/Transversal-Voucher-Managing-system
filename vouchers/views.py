from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from datetime import datetime, timedelta

from sites_mgmt.models import HotspotSite, VoucherTier
from sites_mgmt.views import sync_sites_from_unifi
from .models import VoucherLog
from unifi_api import client as unifi


def can_access_site(user, site):
    return user.is_superadmin or site in user.managed_sites.all()


@login_required
def voucher_list(request):
    site_filter = request.GET.get('site', '')
    days        = int(request.GET.get('days', 30))
    per_page    = int(request.GET.get('per_page', 100))
    page        = int(request.GET.get('page', 1))

    if request.user.is_superadmin:
        sync_sites_from_unifi()
        sites = HotspotSite.objects.filter(is_active=True)
    else:
        sites = request.user.managed_sites.filter(is_active=True)

    sites_to_fetch = sites.filter(unifi_site_id=site_filter) if site_filter else sites

    # ── Vouchers disponibles (stock) ─────────────────────────────
    all_vouchers = unifi.get_all_vouchers(sites_to_fetch)
    tiers = list(VoucherTier.objects.filter(is_active=True).order_by('min_minutes'))

    def tier_for(minutes):
        for t in tiers:
            if t.min_minutes <= minutes <= t.max_minutes:
                return t
        return None

    for v in all_vouchers:
        t = tier_for(v.get('duration', 0))
        v['tier_label'] = t.label if t else 'Sans tranche'
        v['price']      = float(t.price_htg) if t else 0

    # ── Sessions vendues (guests) ─────────────────────────────────
    now_ts       = datetime.now().timestamp()
    date_from_ts = (datetime.now() - timedelta(days=days)).timestamp()

    all_guests = unifi.get_all_guests(sites_to_fetch)
    sessions   = [g for g in all_guests if g['sold_ts'] >= date_from_ts]

    for g in sessions:
        t = tier_for(g['duration_minutes'])
        g['tier_label']          = t.label if t else 'Sans tranche'
        g['price']               = float(t.price_htg) if t else 0
        g['is_currently_active'] = g.get('end', 0) > now_ts

    sessions.sort(key=lambda g: g['sold_ts'], reverse=True)

    total_sessions = len(sessions)
    total_revenue  = sum(g['price'] for g in sessions)
    start          = (page - 1) * per_page
    sessions_page  = sessions[start:start + per_page]
    total_pages    = max(1, (total_sessions + per_page - 1) // per_page)

    return render(request, 'vouchers/list.html', {
        'available_vouchers': all_vouchers,
        'sessions':           sessions_page,
        'total_sessions':     total_sessions,
        'total_revenue':      total_revenue,
        'sites':              sites,
        'days':               days,
        'period_options':     [(7, '7 j'), (30, '30 j'), (90, '90 j'), (365, '1 an')],
        'per_page':           per_page,
        'per_page_options':   [50, 100, 200, 500],
        'page':               page,
        'total_pages':        total_pages,
        'site_filter':        site_filter,
        'page_title':         'Vouchers',
    })


@login_required
def voucher_create(request):
    if request.user.is_superadmin:
        sites = HotspotSite.objects.filter(is_active=True)
    else:
        sites = request.user.managed_sites.filter(is_active=True)

    tiers = VoucherTier.objects.filter(is_active=True)

    if request.method == 'POST':
        site_pk = request.POST.get('site')
        site = get_object_or_404(HotspotSite, pk=site_pk)

        if not can_access_site(request.user, site):
            messages.error(request, "Accès refusé à ce site.")
            return redirect('vouchers:list')

        count    = int(request.POST.get('count', 1))
        tier_pk  = request.POST.get('tier')
        note     = request.POST.get('note', '').strip()
        tier     = get_object_or_404(VoucherTier, pk=tier_pk)
        expire_minutes = tier.max_minutes

        created = unifi.create_vouchers(
            site_id=site.unifi_site_id,
            expire_minutes=expire_minutes,
            count=count,
            quota=1,
            note=note or f"BonNet-{tier.label}",
        )

        if created:
            for v in unifi.get_vouchers(site.unifi_site_id):
                if v.get('note', '') == (note or f"BonNet-{tier.label}"):
                    VoucherLog.objects.get_or_create(
                        unifi_id=v['_id'],
                        defaults={
                            'site': site,
                            'created_by': request.user,
                            'tier': tier,
                            'code': v.get('code', ''),
                            'duration_minutes': v.get('duration', expire_minutes),
                            'quota': v.get('quota', 1),
                            'note': v.get('note', ''),
                            'price_htg': tier.price_htg,
                        }
                    )
            messages.success(request, f"{count} voucher(s) créé(s) avec succès !")
            return redirect('vouchers:list')
        else:
            messages.error(request, "Échec de la création sur le contrôleur UniFi.")

    return render(request, 'vouchers/create.html', {
        'sites': sites,
        'tiers': tiers,
        'page_title': 'Créer des vouchers',
    })


@login_required
def voucher_delete(request, unifi_id):
    voucher = get_object_or_404(VoucherLog, unifi_id=unifi_id)
    if not can_access_site(request.user, voucher.site):
        messages.error(request, "Accès refusé.")
        return redirect('vouchers:list')

    if request.method == 'POST':
        if unifi.delete_voucher(voucher.site.unifi_site_id, voucher.unifi_id):
            voucher.status = VoucherLog.STATUS_REVOKED
            voucher.save()
            messages.success(request, f"Voucher {voucher.code} révoqué.")
        else:
            messages.error(request, "Erreur lors de la révocation.")
    return redirect('vouchers:list')


@login_required
def sync_vouchers(request, site_pk):
    site = get_object_or_404(HotspotSite, pk=site_pk)
    if not can_access_site(request.user, site):
        messages.error(request, "Accès refusé.")
        return redirect('vouchers:list')

    raw_vouchers  = unifi.get_vouchers(site.unifi_site_id)
    created_count = 0

    for v in raw_vouchers:
        tier = VoucherTier.get_price_for_minutes(v.get('duration', 0))
        _, created = VoucherLog.objects.update_or_create(
            unifi_id=v['_id'],
            defaults={
                'site': site,
                'code': v.get('code', ''),
                'duration_minutes': v.get('duration', 0),
                'quota': v.get('quota', 1),
                'note': v.get('note', ''),
                'tier': tier,
                'price_htg': tier.price_htg if tier else None,
                'status': (
                    VoucherLog.STATUS_USED if v.get('used', 0) >= v.get('quota', 1)
                    else VoucherLog.STATUS_ACTIVE
                ),
            }
        )
        if created:
            created_count += 1

    messages.success(request, f"Sync terminée — {created_count} nouveaux vouchers importés.")
    return redirect('vouchers:list')
