from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta

from sites_mgmt.models import HotspotSite, VoucherTier
from .models import VoucherLog
from unifi_api import client as unifi


def can_access_site(user, site):
    return user.is_superadmin or site in user.managed_sites.all()


@login_required
def voucher_list(request):
    site_id = request.GET.get('site')
    status_filter = request.GET.get('status', '')
    date_from = request.GET.get('from', '')
    date_to = request.GET.get('to', '')

    if user := request.user:
        if user.is_superadmin:
            sites = HotspotSite.objects.filter(is_active=True)
        else:
            sites = user.managed_sites.filter(is_active=True)

    vouchers = VoucherLog.objects.select_related('site', 'tier', 'created_by')

    if not request.user.is_superadmin:
        vouchers = vouchers.filter(site__in=sites)

    if site_id:
        vouchers = vouchers.filter(site__unifi_site_id=site_id)
    if status_filter:
        vouchers = vouchers.filter(status=status_filter)
    if date_from:
        vouchers = vouchers.filter(created_at__date__gte=date_from)
    if date_to:
        vouchers = vouchers.filter(created_at__date__lte=date_to)

    total_revenue = vouchers.filter(status=VoucherLog.STATUS_USED).aggregate(
        total=Sum('price_htg'))['total'] or 0

    return render(request, 'vouchers/list.html', {
        'vouchers': vouchers[:200],
        'sites': sites,
        'total_revenue': total_revenue,
        'status_choices': VoucherLog.STATUS_CHOICES,
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
