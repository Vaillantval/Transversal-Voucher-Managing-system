from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse

from .models import HotspotSite, VoucherTier
from unifi_api import client as unifi


def superadmin_required(view_func):
    """Décorateur : réservé aux super-admins."""
    from functools import wraps
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_superadmin:
            messages.error(request, "Accès réservé aux super-administrateurs.")
            return redirect('dashboard:index')
        return view_func(request, *args, **kwargs)
    return wrapper


# ─── SITES ────────────────────────────────────────────────────────────────────

@login_required
def site_list(request):
    # Auto-sync : créer les sites UniFi manquants en base
    if request.user.is_superadmin:
        unifi_sites = unifi.get_sites()
        for us in unifi_sites:
            HotspotSite.objects.get_or_create(
                unifi_site_id=us.get('name', us.get('_id', '')),
                defaults={
                    'name': us.get('desc', us.get('name', '')),
                    'location': '',
                    'description': '',
                },
            )

    if request.user.is_superadmin:
        sites = HotspotSite.objects.prefetch_related('admins').all()
    else:
        sites = request.user.managed_sites.filter(is_active=True)

    all_stats = unifi.get_all_site_stats(sites)
    sites_data = [
        {'site': site, 'stats': all_stats.get(site.unifi_site_id, {})}
        for site in sites
    ]

    return render(request, 'sites_mgmt/list.html', {
        'sites_data': sites_data,
        'page_title': 'Sites',
    })


@login_required
@superadmin_required
def site_create(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        unifi_id = request.POST.get('unifi_site_id', '').strip()
        location = request.POST.get('location', '').strip()
        description = request.POST.get('description', '').strip()

        if not name or not unifi_id:
            messages.error(request, 'Nom et ID UniFi sont obligatoires.')
        else:
            HotspotSite.objects.create(
                name=name,
                unifi_site_id=unifi_id,
                location=location,
                description=description,
            )
            messages.success(request, f'Site « {name} » créé avec succès.')
            return redirect('sites:list')

    # Pour le formulaire : liste des sites UniFi disponibles
    unifi_sites = unifi.get_sites()
    return render(request, 'sites_mgmt/form.html', {
        'unifi_sites': unifi_sites,
        'page_title': 'Nouveau site',
        'action': 'Créer',
    })


@login_required
@superadmin_required
def site_edit(request, pk):
    site = get_object_or_404(HotspotSite, pk=pk)

    if request.method == 'POST':
        site.name = request.POST.get('name', site.name).strip()
        site.location = request.POST.get('location', site.location).strip()
        site.description = request.POST.get('description', site.description).strip()
        site.is_active = request.POST.get('is_active') == 'on'

        # Admins assignés
        admin_ids = request.POST.getlist('admins')
        from accounts.models import User
        site.admins.set(User.objects.filter(pk__in=admin_ids, role=User.ROLE_SITE_ADMIN))

        site.save()
        messages.success(request, f'Site « {site.name} » mis à jour.')
        return redirect('sites:list')

    from accounts.models import User
    site_admins = User.objects.filter(role=User.ROLE_SITE_ADMIN, is_active=True)
    return render(request, 'sites_mgmt/form.html', {
        'site': site,
        'site_admins': site_admins,
        'page_title': f'Modifier — {site.name}',
        'action': 'Modifier',
    })


# ─── TARIFS ───────────────────────────────────────────────────────────────────

@login_required
@superadmin_required
def tier_list(request):
    tiers = VoucherTier.objects.all()
    return render(request, 'sites_mgmt/tiers.html', {
        'tiers': tiers,
        'page_title': 'Tranches tarifaires',
    })


@login_required
@superadmin_required
def tier_create(request):
    if request.method == 'POST':
        try:
            VoucherTier.objects.create(
                label=request.POST['label'],
                min_minutes=int(request.POST['min_minutes']),
                max_minutes=int(request.POST['max_minutes']),
                price_htg=request.POST['price_htg'],
            )
            messages.success(request, 'Tranche tarifaire créée.')
            return redirect('sites:tiers')
        except Exception as e:
            messages.error(request, f'Erreur : {e}')

    return redirect('sites:tiers')


@login_required
@superadmin_required
def tier_delete(request, pk):
    tier = get_object_or_404(VoucherTier, pk=pk)
    if request.method == 'POST':
        tier.delete()
        messages.success(request, 'Tranche supprimée.')
    return redirect('sites:tiers')


# ─── API JSON (pour charts) ────────────────────────────────────────────────────

@login_required
def site_stats_json(request, site_id):
    """Endpoint AJAX : stats live d'un site."""
    site = get_object_or_404(HotspotSite, unifi_site_id=site_id)
    if not request.user.is_superadmin and site not in request.user.managed_sites.all():
        return JsonResponse({'error': 'Accès refusé'}, status=403)

    stats = unifi.get_site_stats(site_id)
    return JsonResponse(stats)
