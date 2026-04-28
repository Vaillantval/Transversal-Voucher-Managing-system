from ninja import Router
from django.shortcuts import get_object_or_404

from .schemas import BannerOut, SiteOut, TierOut

router = Router(tags=['Store'])


@router.get('/banners/', response=list[BannerOut])
def list_banners(request):
    from store.models import StoreBanner
    banners = StoreBanner.objects.filter(is_active=True).order_by('order')
    results = []
    for b in banners:
        image_url = ''
        if b.image:
            try:
                image_url = request.build_absolute_uri(b.image.url)
            except Exception:
                pass
        results.append(BannerOut(
            id=b.pk,
            title=b.title,
            subtitle=b.subtitle,
            image_url=image_url,
            cta_text=b.cta_text,
        ))
    return results


@router.get('/sites/', response=list[SiteOut])
def list_sites(request):
    from sites_mgmt.models import HotspotSite, VoucherTier
    active_site_ids = (
        VoucherTier.objects
        .filter(is_active=True, is_replacement=False, is_admin_code=False, price_htg__gt=0)
        .values_list('sites', flat=True)
        .distinct()
    )
    sites = (
        HotspotSite.objects
        .filter(pk__in=active_site_ids, is_active=True)
        .order_by('name')
    )
    return [
        SiteOut(
            id=s.pk,
            name=s.name,
            location=s.location,
            latitude=float(s.latitude) if s.latitude is not None else None,
            longitude=float(s.longitude) if s.longitude is not None else None,
        )
        for s in sites
    ]


@router.get('/sites/{site_id}/tiers/', response=list[TierOut])
def list_site_tiers(request, site_id: int):
    from sites_mgmt.models import HotspotSite, VoucherTier
    site = get_object_or_404(HotspotSite, pk=site_id, is_active=True)
    tiers = sorted(
        VoucherTier.objects.filter(
            sites=site,
            is_active=True,
            is_replacement=False,
            is_admin_code=False,
            price_htg__gt=0,
        ),
        key=lambda t: t.duration_minutes,
    )
    return [
        TierOut(
            id=t.pk,
            label=t.label,
            duration_minutes=t.duration_minutes,
            duration_display=t.duration_display,
            price_htg=t.price_htg,
        )
        for t in tiers
    ]


def _filter_catalog(tiers):
    """Déduplique les forfaits : écart min 5h, même durée → garde le moins cher."""
    sorted_tiers = sorted(tiers, key=lambda t: t.duration_minutes)
    filtered = []
    for tier in sorted_tiers:
        if not filtered:
            filtered.append(tier)
            continue
        last = filtered[-1]
        diff = tier.duration_minutes - last.duration_minutes
        if diff == 0:
            if tier.price_htg < last.price_htg:
                filtered[-1] = tier
        elif diff < 300:
            continue
        else:
            filtered.append(tier)
    return filtered


@router.get('/tiers/', response=list[TierOut])
def list_tiers(request):
    """Catalogue global dédupliqué — même logique que le storefront web."""
    from sites_mgmt.models import VoucherTier
    raw = list(
        VoucherTier.objects.filter(
            is_active=True,
            is_replacement=False,
            is_admin_code=False,
            price_htg__gt=0,
        ).prefetch_related('sites')
    )
    # Garder seulement les tiers liés à au moins un site actif
    raw = [t for t in raw if t.sites.filter(is_active=True).exists()]
    return [
        TierOut(
            id=t.pk,
            label=t.label,
            duration_minutes=t.duration_minutes,
            duration_display=t.duration_display,
            price_htg=t.price_htg,
        )
        for t in _filter_catalog(raw)
    ]


@router.get('/tiers/{tier_id}/sites/', response=list[SiteOut])
def tier_sites(request, tier_id: int):
    """Sites disponibles pour un forfait donné (ManyToMany inverse)."""
    from sites_mgmt.models import VoucherTier
    tier = get_object_or_404(
        VoucherTier,
        pk=tier_id,
        is_active=True,
        is_replacement=False,
        is_admin_code=False,
    )
    sites = tier.sites.filter(is_active=True).order_by('name')
    return [
        SiteOut(
            id=s.pk,
            name=s.name,
            location=s.location,
            latitude=float(s.latitude) if s.latitude is not None else None,
            longitude=float(s.longitude) if s.longitude is not None else None,
        )
        for s in sites
    ]
