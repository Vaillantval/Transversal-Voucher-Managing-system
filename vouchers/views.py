from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta

from sites_mgmt.models import HotspotSite, VoucherTier
from sites_mgmt.views import sync_sites_from_unifi
from .models import VoucherLog
from unifi_api import client as unifi


def can_access_site(user, site):
    return user.is_superadmin or site in user.managed_sites.all()


@login_required
def voucher_list(request):
    site_filter = request.GET.get('site', '')
    status_filter = request.GET.get('status', '')
    per_page = int(request.GET.get('per_page', 100))
    page = int(request.GET.get('page', 1))

    if request.user.is_superadmin:
        sync_sites_from_unifi()
        sites = HotspotSite.objects.filter(is_active=True)
    else:
        sites = request.user.managed_sites.filter(is_active=True)

    # Filtrer sur un site précis si demandé
    sites_to_fetch = sites.filter(unifi_site_id=site_filter) if site_filter else sites

    # Récupérer depuis UniFi
    all_vouchers = unifi.get_all_vouchers(sites_to_fetch)

    # Filtre statut côté Python
    STATUS_MAP = {'active': 0, 'used': 1}
    if status_filter == 'active':
        all_vouchers = [v for v in all_vouchers if v.get('used', 0) < v.get('quota', 1)]
    elif status_filter == 'used':
        all_vouchers = [v for v in all_vouchers if v.get('used', 0) >= v.get('quota', 1)]

    # Pagination manuelle
    total = len(all_vouchers)
    start = (page - 1) * per_page
    end = start + per_page
    vouchers_page = all_vouchers[start:end]
    total_pages = max(1, (total + per_page - 1) // per_page)

    return render(request, 'vouchers/list.html', {
        'vouchers': vouchers_page,
        'sites': sites,
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': total_pages,
        'per_page_options': [50, 100, 200, 500],
        'status_filter': status_filter,
        'site_filter': site_filter,
        'page_title': 'Vouchers',
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

        count = int(request.POST.get('count', 1))
        tier_pk = request.POST.get('tier')
        note = request.POST.get('note', '').strip()

        tier = get_object_or_404(VoucherTier, pk=tier_pk)
        expire_minutes = tier.max_minutes

        # Créer sur UniFi
        created = unifi.create_vouchers(
            site_id=site.unifi_site_id,
            expire_minutes=expire_minutes,
            count=count,
            quota=1,
            note=note or f"BonNet-{tier.label}",
        )

        if created:
            # Synchroniser en base locale
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
    """Synchronise les vouchers UniFi → base locale."""
    site = get_object_or_404(HotspotSite, pk=site_pk)
    if not can_access_site(request.user, site):
        messages.error(request, "Accès refusé.")
        return redirect('vouchers:list')

    raw_vouchers = unifi.get_vouchers(site.unifi_site_id)
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
