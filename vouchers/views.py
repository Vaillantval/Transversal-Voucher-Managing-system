from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils.safestring import mark_safe
from datetime import datetime, timedelta

from sites_mgmt.models import HotspotSite, VoucherTier
from sites_mgmt.utils import find_tier, TZ_HAITI
from sites_mgmt.views import sync_sites_from_unifi
from .models import VoucherLog
from unifi_api import client as unifi


def can_access_site(user, site):
    return user.is_superadmin or site in user.managed_sites.all()


@login_required
def voucher_list(request):
    site_filter = request.GET.get('site', '')
    per_page    = int(request.GET.get('per_page', 100))
    page        = int(request.GET.get('page', 1))

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
        days_int     = int(days_raw) if days_raw else 30
        delta        = timedelta(days=days_int)
        cu           = 'days'
        custom_value = str(days_int)
        cv_int       = days_int

    days = cv_int  # kept for template quick-buttons highlight

    # Filtres session-level
    f_tier        = request.GET.get('f_tier', '')
    f_active_from = request.GET.get('f_active_from', '')
    f_active_to   = request.GET.get('f_active_to', '')
    f_expire_from = request.GET.get('f_expire_from', '')
    f_expire_to   = request.GET.get('f_expire_to', '')
    f_dur_val     = request.GET.get('f_dur_val', '').strip()
    f_dur_unit    = request.GET.get('f_dur_unit', 'minutes')
    f_status      = request.GET.get('f_status', '')

    if request.user.is_superadmin:
        sync_sites_from_unifi()
        sites = HotspotSite.objects.filter(is_active=True)
    else:
        sites = request.user.managed_sites.filter(is_active=True)

    sites_to_fetch = sites.filter(unifi_site_id=site_filter) if site_filter else sites

    # ── Tiers par site (M2M) ─────────────────────────────────────
    from collections import defaultdict as _dd
    _all_tiers = VoucherTier.objects.filter(is_active=True).prefetch_related('sites')
    _tiers_by_site_pk = _dd(list)
    for _t in _all_tiers:
        for _s in _t.sites.all():
            _tiers_by_site_pk[_s.pk].append(_t)
    _unifi_to_pk = {s.unifi_site_id: s.pk for s in sites}

    # ── Vouchers disponibles (stock) ─────────────────────────────
    all_vouchers = unifi.get_all_vouchers(sites_to_fetch)

    for v in all_vouchers:
        _spk = _unifi_to_pk.get(v.get('site_unifi_id', ''))
        _st = _tiers_by_site_pk.get(_spk, []) if _spk else []
        t = find_tier(_st, v.get('duration', 0))
        v['tier_label'] = t.label if t else 'Sans tranche'
        v['price']      = float(t.price_htg) if t else 0

    # ── Sessions vendues (guests) ─────────────────────────────────
    now_dt       = datetime.now(TZ_HAITI)
    now_ts       = now_dt.timestamp()
    date_from_ts = (now_dt - delta).timestamp()

    all_guests = unifi.get_all_guests(sites_to_fetch)
    sessions   = [g for g in all_guests if g['sold_ts'] >= date_from_ts]

    for g in sessions:
        _spk = _unifi_to_pk.get(g.get('site_unifi_id', ''))
        _st = _tiers_by_site_pk.get(_spk, []) if _spk else []
        t = find_tier(_st, g['duration_minutes'])
        g['tier_label']          = t.label if t else 'Sans tranche'
        g['price']               = float(t.price_htg) if t else 0
        g['is_currently_active'] = g.get('end', 0) > now_ts

    sessions.sort(key=lambda g: g['sold_ts'], reverse=True)

    # Appliquer les filtres session-level
    if f_tier:
        sessions = [g for g in sessions if g['tier_label'] == f_tier]

    if f_active_from:
        try:
            ts = datetime.fromisoformat(f_active_from).replace(tzinfo=TZ_HAITI).timestamp()
            sessions = [g for g in sessions if g['sold_ts'] >= ts]
        except ValueError:
            pass

    if f_active_to:
        try:
            ts = datetime.fromisoformat(f_active_to).replace(tzinfo=TZ_HAITI).timestamp()
            sessions = [g for g in sessions if g['sold_ts'] <= ts]
        except ValueError:
            pass

    if f_expire_from:
        try:
            ts = datetime.fromisoformat(f_expire_from).replace(tzinfo=TZ_HAITI).timestamp()
            sessions = [g for g in sessions if g.get('end', 0) >= ts]
        except ValueError:
            pass

    if f_expire_to:
        try:
            ts = datetime.fromisoformat(f_expire_to).replace(tzinfo=TZ_HAITI).timestamp()
            sessions = [g for g in sessions if g.get('end', 0) <= ts]
        except ValueError:
            pass

    if f_dur_val:
        try:
            n = int(f_dur_val)
            unit_map = {'minutes': 1, 'hours': 60, 'days': 1440, 'months': 43200}
            target_min = n * unit_map.get(f_dur_unit, 1)
            matched_tier = find_tier(tiers, target_min)
            if matched_tier:
                sessions = [g for g in sessions if g['tier_label'] == matched_tier.label]
            else:
                sessions = []
        except (ValueError, TypeError):
            pass

    if f_status == 'active':
        sessions = [g for g in sessions if g.get('is_currently_active', False)]
    elif f_status == 'expired':
        sessions = [g for g in sessions if not g.get('is_currently_active', False)]

    total_sessions = len(sessions)
    total_revenue  = sum(g['price'] for g in sessions)
    start          = (page - 1) * per_page
    sessions_page  = sessions[start:start + per_page]
    total_pages    = max(1, (total_sessions + per_page - 1) // per_page)

    unifi_warning = not unifi.can_connect()

    qs = request.GET.copy()
    qs.pop('page', None)
    base_qs = mark_safe(qs.urlencode())

    return render(request, 'vouchers/list.html', {
        'available_vouchers': all_vouchers,
        'sessions':           sessions_page,
        'total_sessions':     total_sessions,
        'total_revenue':      total_revenue,
        'sites':              sites,
        'tiers':              list(_all_tiers),
        'days':               days,
        'custom_value':       custom_value,
        'custom_unit':        cu,
        'period_options':     [(7, '7 j'), (30, '30 j'), (90, '90 j'), (365, '1 an')],
        'per_page':           per_page,
        'per_page_options':   [50, 100, 200, 500],
        'page':               page,
        'total_pages':        total_pages,
        'site_filter':        site_filter,
        'page_title':         'Vouchers',
        'f_tier':             f_tier,
        'f_active_from':      f_active_from,
        'f_active_to':        f_active_to,
        'f_expire_from':      f_expire_from,
        'f_expire_to':        f_expire_to,
        'f_dur_val':          f_dur_val,
        'f_dur_unit':         f_dur_unit,
        'f_status':           f_status,
        'base_qs':            base_qs,
        'unifi_warning':      unifi_warning,
    })


@login_required
def voucher_create(request):
    if request.user.is_superadmin:
        sites = HotspotSite.objects.filter(is_active=True)
    else:
        sites = request.user.managed_sites.filter(is_active=True)

    std_tiers  = VoucherTier.objects.filter(is_active=True, is_replacement=False).prefetch_related('sites')
    repl_tiers = VoucherTier.objects.filter(is_active=True, is_replacement=True).prefetch_related('sites')

    if request.method == 'POST':
        site_pk = request.POST.get('site')
        site = get_object_or_404(HotspotSite, pk=site_pk)

        if not can_access_site(request.user, site):
            messages.error(request, "Accès refusé à ce site.")
            return redirect('vouchers:list')

        note  = request.POST.get('note', '').strip()
        count = int(request.POST.get('count', 1))

        use_replacement = request.POST.get('use_replacement') == '1'
        if use_replacement:
            rep_dur  = int(request.POST.get('rep_duration', 1))
            rep_unit = request.POST.get('rep_unit', 'hours')
            multipliers = {'hours': 60, 'days': 1440, 'months': 43200}
            expire_minutes = rep_dur * multipliers.get(rep_unit, 60)
            tier_pk = request.POST.get('repl_tier_pk', '')
            tier = VoucherTier.objects.filter(pk=tier_pk, is_replacement=True).first() if tier_pk else None
        else:
            tier_pk = request.POST.get('tier')
            tier    = get_object_or_404(VoucherTier, pk=tier_pk)
            expire_minutes = tier.duration_minutes

        tier_label  = tier.label if tier else ('Remplacement' if use_replacement else '?')
        default_note = f"BonNet-Remplacement" if use_replacement else f"BonNet-{tier_label}"
        final_note  = note or default_note

        created = unifi.create_vouchers(
            site_id=site.unifi_site_id,
            expire_minutes=expire_minutes,
            count=count,
            quota=1,
            note=final_note,
        )

        if created:
            for v in unifi.get_vouchers(site.unifi_site_id):
                if v.get('note', '') == final_note:
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
                            'price_htg': tier.price_htg if tier else 0,
                        }
                    )
            # Rafraîchit le cache du site en arrière-plan
            try:
                from unifi_api.tasks import refresh_site
                refresh_site.delay(site.unifi_site_id)
            except Exception:
                pass
            messages.success(request, f"{count} voucher(s) créé(s) avec succès !")
            return redirect('vouchers:list')
        else:
            messages.error(request, "Échec de la création sur le contrôleur UniFi.")

    return render(request, 'vouchers/create.html', {
        'sites':      sites,
        'tiers':      std_tiers,
        'repl_tiers': repl_tiers,
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
            try:
                from unifi_api.tasks import refresh_site
                refresh_site.delay(voucher.site.unifi_site_id)
            except Exception:
                pass
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
    site_tiers    = list(VoucherTier.objects.filter(is_active=True, sites=site))

    for v in raw_vouchers:
        tier = find_tier(site_tiers, v.get('duration', 0))
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
