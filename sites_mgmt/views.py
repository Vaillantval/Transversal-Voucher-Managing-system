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

def sync_sites_from_unifi():
    """Crée en DB les sites UniFi qui n'existent pas encore. Max 1× toutes les 5 min."""
    from django.core.cache import cache
    if cache.get('_sync_sites_throttle'):
        return
    cache.set('_sync_sites_throttle', 1, 300)
    for us in unifi.get_sites():
        HotspotSite.objects.get_or_create(
            unifi_site_id=us.get('name', us.get('_id', '')),
            defaults={
                'name': us.get('desc', us.get('name', '')),
                'location': '',
                'description': '',
            },
        )


@login_required
def site_list(request):
    if request.user.is_superadmin:
        sync_sites_from_unifi()

    if request.user.is_superadmin:
        sites = HotspotSite.objects.prefetch_related('admins').all()
    else:
        sites = request.user.managed_sites.filter(is_active=True)

    search = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')

    if search:
        sites = sites.filter(name__icontains=search) | sites.filter(location__icontains=search)
    if status_filter == 'active':
        sites = sites.filter(is_active=True)
    elif status_filter == 'inactive':
        sites = sites.filter(is_active=False)

    all_stats = unifi.get_all_site_stats(sites)
    sites_data = [
        {'site': site, 'stats': all_stats.get(site.unifi_site_id, {})}
        for site in sites
    ]

    return render(request, 'sites_mgmt/list.html', {
        'sites_data': sites_data,
        'search': search,
        'status_filter': status_filter,
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
    site_filter = request.GET.get('site', '')
    all_sites   = HotspotSite.objects.filter(is_active=True).order_by('name')

    qs = VoucherTier.objects.filter(is_replacement=False, is_admin_code=False).prefetch_related('sites')
    if site_filter:
        selected_site = all_sites.filter(pk=site_filter).first()
        qs = qs.filter(sites__pk=site_filter)
    else:
        selected_site = None

    admin_qs = VoucherTier.objects.filter(is_admin_code=True).prefetch_related('sites')
    if site_filter:
        admin_qs = admin_qs.filter(sites__pk=site_filter)

    return render(request, 'sites_mgmt/tiers.html', {
        'tiers':        qs,
        'admin_tiers':  admin_qs,
        'all_sites':    all_sites,
        'selected_site': selected_site,
        'site_filter':  site_filter,
        'page_title':   'Forfaits tarifaires',
        'label_presets': VoucherTier.LABEL_PRESETS,
    })


@login_required
@superadmin_required
def tier_admin_create(request):
    if request.method == 'POST':
        try:
            tier = VoucherTier.objects.create(
                label         = request.POST.get('label', 'Code Admin'),
                duration      = int(request.POST.get('duration', 120)),
                unit          = request.POST.get('unit', 'days'),
                price_htg     = 0,
                is_admin_code = True,
                max_vouchers  = int(request.POST.get('max_vouchers', 15)),
            )
            site_pks = request.POST.getlist('sites')
            if site_pks:
                tier.sites.set(HotspotSite.objects.filter(pk__in=site_pks))
            messages.success(request, f'Code Admin « {tier.label} » créé.')
        except Exception as e:
            messages.error(request, f'Erreur : {e}')
    return redirect('sites:tiers')


@login_required
@superadmin_required
def tier_admin_edit(request, pk):
    tier = get_object_or_404(VoucherTier, pk=pk, is_admin_code=True)
    if request.method == 'POST':
        try:
            tier.label        = request.POST.get('label', tier.label)
            tier.duration     = int(request.POST.get('duration', tier.duration))
            tier.unit         = request.POST.get('unit', tier.unit)
            tier.max_vouchers = int(request.POST.get('max_vouchers', tier.max_vouchers))
            tier.is_active    = request.POST.get('is_active') == 'on'
            tier.save()
            tier.sites.set(HotspotSite.objects.filter(pk__in=request.POST.getlist('sites')))
            messages.success(request, f'Code Admin « {tier.label} » mis à jour.')
        except Exception as e:
            messages.error(request, f'Erreur : {e}')
    return redirect('sites:tiers')


@login_required
@superadmin_required
def tier_replacement_list(request):
    all_sites   = HotspotSite.objects.filter(is_active=True).order_by('name')
    site_filter = request.GET.get('site', '')

    qs = VoucherTier.objects.filter(is_replacement=True).prefetch_related('sites')
    if site_filter:
        qs = qs.filter(sites__pk=site_filter)

    return render(request, 'sites_mgmt/tiers_replacement.html', {
        'tiers':       qs,
        'all_sites':   all_sites,
        'site_filter': site_filter,
        'page_title':  'Forfaits Remplacement',
    })


@login_required
@superadmin_required
def tier_replacement_create(request):
    if request.method == 'POST':
        try:
            tier = VoucherTier.objects.create(
                label          = request.POST['label'],
                duration       = int(request.POST['duration']),
                unit           = request.POST['unit'],
                price_htg      = 0,
                is_replacement = True,
            )
            site_pks = request.POST.getlist('sites')
            if site_pks:
                tier.sites.set(HotspotSite.objects.filter(pk__in=site_pks))
            messages.success(request, f'Forfait remplacement « {tier.label} » créé.')
        except Exception as e:
            messages.error(request, f'Erreur : {e}')
    return redirect('sites:tier_replacement_list')


@login_required
@superadmin_required
def tier_create(request):
    if request.method == 'POST':
        try:
            tier = VoucherTier.objects.create(
                label     = request.POST['label'],
                duration  = int(request.POST['duration']),
                unit      = request.POST['unit'],
                price_htg = request.POST.get('price_htg') or 0,
            )
            site_pks = request.POST.getlist('sites')
            if site_pks:
                tier.sites.set(HotspotSite.objects.filter(pk__in=site_pks))
            messages.success(request, f'Forfait « {tier.label} » créé.')
        except Exception as e:
            messages.error(request, f'Erreur : {e}')
    return redirect(request.POST.get('next', 'sites:tiers'))


@login_required
@superadmin_required
def tier_edit(request, pk):
    tier = get_object_or_404(VoucherTier, pk=pk)
    if request.method == 'POST':
        try:
            tier.label     = request.POST['label']
            tier.duration  = int(request.POST['duration'])
            tier.unit      = request.POST['unit']
            if not tier.is_replacement:
                tier.price_htg = request.POST.get('price_htg') or 0
            tier.is_active = request.POST.get('is_active') == 'on'
            tier.save()
            site_pks = request.POST.getlist('sites')
            tier.sites.set(HotspotSite.objects.filter(pk__in=site_pks))
            messages.success(request, f'Forfait « {tier.label} » mis à jour.')
        except Exception as e:
            messages.error(request, f'Erreur : {e}')
    redirect_to = 'sites:tier_replacement_list' if tier.is_replacement else 'sites:tiers'
    return redirect(redirect_to)


@login_required
@superadmin_required
def tier_delete(request, pk):
    tier = get_object_or_404(VoucherTier, pk=pk)
    is_repl = tier.is_replacement
    if request.method == 'POST':
        name = tier.label
        tier.delete()
        messages.success(request, f'Forfait « {name} » supprimé.')
    return redirect('sites:tier_replacement_list' if is_repl else 'sites:tiers')


@login_required
@superadmin_required
def tier_remove_site(request, pk, site_pk):
    if request.method == 'POST':
        tier = get_object_or_404(VoucherTier, pk=pk)
        tier.sites.remove(site_pk)
    return redirect(request.POST.get('next', 'sites:tiers'))


# ─── CONFIGURATION GLOBALE ────────────────────────────────────────────────────

@login_required
@superadmin_required
def config_edit(request):
    from .models import SiteConfig
    from notifications.models import AutoGenConfig

    config = SiteConfig.get()
    autogen = AutoGenConfig.get()
    all_sites = HotspotSite.objects.filter(is_active=True).order_by('name')

    if request.method == 'POST':
        # Logos, footer & conditions partenaire
        config.footer_text        = request.POST.get('footer_text', '').strip()
        config.partner_conditions = request.POST.get('partner_conditions', '').strip()

        if request.FILES.get('logo1'):
            config.logo1 = request.FILES['logo1']
        elif request.POST.get('clear_logo1'):
            config.logo1 = None

        if request.FILES.get('logo2'):
            config.logo2 = request.FILES['logo2']
        elif request.POST.get('clear_logo2'):
            config.logo2 = None

        config.save()

        # Auto-gen
        autogen.enabled = request.POST.get('autogen_enabled') == 'on'
        try:
            autogen.count_per_tier = max(1, int(request.POST.get('autogen_count', 100)))
        except (ValueError, TypeError):
            autogen.count_per_tier = 100
        try:
            autogen.delay_hours = max(1, int(request.POST.get('autogen_delay', 24)))
        except (ValueError, TypeError):
            autogen.delay_hours = 24
        autogen.save()

        selected_site_ids = request.POST.getlist('autogen_sites')
        autogen.sites.set(HotspotSite.objects.filter(pk__in=selected_site_ids))

        messages.success(request, 'Configuration mise à jour.')
        return redirect('sites:config')

    from accounts.models import PartnerApplication
    pending_partners = PartnerApplication.objects.filter(status=PartnerApplication.STATUS_PENDING).count()

    return render(request, 'sites_mgmt/config.html', {
        'config':          config,
        'autogen':         autogen,
        'all_sites':       all_sites,
        'autogen_site_ids': list(autogen.sites.values_list('pk', flat=True)),
        'pending_partners': pending_partners,
        'page_title':      'Configuration',
    })


# ─── PARTENAIRES (admin) ─────────────────────────────────────────────────────

@login_required
@superadmin_required
def partners_view(request):
    """Gestion des demandes partenaires + éditeur des conditions."""
    from accounts.models import PartnerApplication
    from .models import SiteConfig

    config = SiteConfig.get()

    if request.method == 'POST' and 'save_conditions' in request.POST:
        config.partner_conditions = request.POST.get('partner_conditions', '')
        config.save(update_fields=['partner_conditions'])
        messages.success(request, 'Conditions de partenariat mises à jour.')
        return redirect('sites:partners')

    applications  = PartnerApplication.objects.select_related('user').all()
    pending_count = applications.filter(status=PartnerApplication.STATUS_PENDING).count()

    return render(request, 'sites_mgmt/partners.html', {
        'config':        config,
        'applications':  applications,
        'pending_count': pending_count,
        'page_title':    'Gestion des partenaires',
    })


@login_required
@superadmin_required
def partner_approve(request, pk):
    """Approuve une demande : crée User + site UniFi + HotspotSite + envoie email."""
    if request.method != 'POST':
        return redirect('sites:partners')

    import secrets, string, logging
    from accounts.models import PartnerApplication, User as BonUser
    from django.utils import timezone

    logger_local = logging.getLogger(__name__)
    application = get_object_or_404(PartnerApplication, pk=pk, status=PartnerApplication.STATUS_PENDING)

    # Générer username unique (email tronqué)
    base = application.email[:150]
    username = base
    counter  = 1
    while BonUser.objects.filter(username=username).exists():
        suffix   = str(counter)
        username = base[:150 - len(suffix)] + suffix
        counter += 1

    # Mot de passe temporaire sécurisé
    alphabet     = string.ascii_letters + string.digits + '!@#$%'
    temp_password = ''.join(secrets.choice(alphabet) for _ in range(12))

    # Créer le compte
    user = BonUser.objects.create_user(
        username=username,
        email=application.email,
        password=temp_password,
        first_name=application.first_name,
        last_name=application.last_name,
        phone=application.phone,
        role=BonUser.ROLE_SITE_ADMIN,
        is_active=True,
    )

    # Créer site UniFi
    site_name = f"{application.first_name} {application.last_name}"
    from unifi_api import client as unifi
    unifi_site = unifi.create_site(site_name)

    if unifi_site:
        site_unifi_id = unifi_site.get('name', '')
        hotspot = HotspotSite.objects.create(
            name=site_name,
            unifi_site_id=site_unifi_id,
            location=application.address,
            description=f"Site partenaire — {application.email}",
            is_active=True,
        )
        hotspot.admins.add(user)
        messages.success(request, f'Partenaire {site_name} approuvé — site UniFi créé (ID : {site_unifi_id}).')
    else:
        messages.warning(
            request,
            f'Partenaire {site_name} approuvé, mais la création du site UniFi a échoué. '
            f'Créez-le manuellement et assignez l\'utilisateur « {username} ».'
        )

    # Enregistrer l'approbation
    application.user        = user
    application.status      = PartnerApplication.STATUS_APPROVED
    application.reviewed_at = timezone.now()
    application.save()

    # Envoyer email avec identifiants
    try:
        from notifications.email_service import send_email
        html = f"""
        <div style="font-family:sans-serif;max-width:560px;margin:auto">
          <h2 style="color:#1d4ed8">Bienvenue chez BonNet, {application.first_name}&nbsp;!</h2>
          <p>Votre demande de partenariat a été approuvée. Voici vos identifiants de connexion :</p>
          <table style="border-collapse:collapse;margin:16px 0">
            <tr>
              <td style="padding:6px 12px;background:#f3f4f6;font-weight:600">Identifiant</td>
              <td style="padding:6px 12px;font-family:monospace">{username}</td>
            </tr>
            <tr>
              <td style="padding:6px 12px;background:#f3f4f6;font-weight:600">Mot de passe temporaire</td>
              <td style="padding:6px 12px;font-family:monospace;letter-spacing:.1em">{temp_password}</td>
            </tr>
          </table>
          <p style="color:#ef4444;font-weight:600">Changez votre mot de passe dès votre première connexion.</p>
        </div>
        """
        send_email(
            to=[application.email],
            subject='[BonNet] ✅ Votre compte partenaire est activé',
            html=html,
        )
    except Exception as e:
        logger_local.error(f"Email approbation {application.email}: {e}")

    return redirect('sites:partners')


@login_required
@superadmin_required
def partner_reject(request, pk):
    """Rejette une demande partenaire."""
    if request.method != 'POST':
        return redirect('sites:partners')

    from accounts.models import PartnerApplication
    from django.utils import timezone

    application = get_object_or_404(PartnerApplication, pk=pk, status=PartnerApplication.STATUS_PENDING)
    application.status      = PartnerApplication.STATUS_REJECTED
    application.admin_notes = request.POST.get('notes', '').strip()
    application.reviewed_at = timezone.now()
    application.save()

    messages.success(request, f'Demande de {application.first_name} {application.last_name} rejetée.')
    return redirect('sites:partners')


# ─── PRODUITS PARTENAIRES (admin) ─────────────────────────────────────────────

@login_required
@superadmin_required
def product_list(request):
    from .models import PartnerProduct
    products = PartnerProduct.objects.prefetch_related('images').all()
    return render(request, 'sites_mgmt/products.html', {
        'products':   products,
        'page_title': 'Produits partenaires',
    })


@login_required
@superadmin_required
def product_create(request):
    from .models import PartnerProduct, PartnerProductImage
    errors    = {}
    form_data = {'name': '', 'description': '', 'price_usd': '', 'is_active': True}

    if request.method == 'POST':
        name        = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        price_str   = request.POST.get('price_usd', '').strip()
        is_active   = request.POST.get('is_active') == 'on'

        form_data = {'name': name, 'description': description, 'price_usd': price_str, 'is_active': is_active}

        if not name:
            errors['name'] = 'Ce champ est requis.'
        price_usd = None
        try:
            price_usd = float(price_str) if price_str else None
            if price_usd is None or price_usd < 0:
                errors['price_usd'] = 'Entrez un prix valide (≥ 0).'
        except ValueError:
            errors['price_usd'] = 'Entrez un prix valide.'

        if not errors:
            product = PartnerProduct.objects.create(
                name=name, description=description, price_usd=price_usd, is_active=is_active
            )
            for i, f in enumerate(request.FILES.getlist('images')):
                PartnerProductImage.objects.create(product=product, image=f, order=i)
            messages.success(request, f'Produit « {name} » créé.')
            return redirect('sites:product_list')

    return render(request, 'sites_mgmt/product_form.html', {
        'errors':     errors,
        'form_data':  form_data,
        'action':     'create',
        'page_title': 'Nouveau produit',
    })


@login_required
@superadmin_required
def product_edit(request, pk):
    from .models import PartnerProduct, PartnerProductImage
    product = get_object_or_404(PartnerProduct, pk=pk)
    errors  = {}

    if request.method == 'POST':
        product.name        = request.POST.get('name', '').strip()
        product.description = request.POST.get('description', '').strip()
        product.is_active   = request.POST.get('is_active') == 'on'

        price_str = request.POST.get('price_usd', '').strip()
        try:
            price_usd = float(price_str) if price_str else None
            if price_usd is None or price_usd < 0:
                errors['price_usd'] = 'Entrez un prix valide (≥ 0).'
            else:
                product.price_usd = price_usd
        except ValueError:
            errors['price_usd'] = 'Entrez un prix valide.'

        if not product.name:
            errors['name'] = 'Ce champ est requis.'

        if not errors:
            product.save()
            next_order = product.images.count()
            for i, f in enumerate(request.FILES.getlist('images')):
                PartnerProductImage.objects.create(product=product, image=f, order=next_order + i)
            messages.success(request, f'Produit « {product.name} » mis à jour.')
            return redirect('sites:product_edit', pk=product.pk)

    return render(request, 'sites_mgmt/product_form.html', {
        'product':    product,
        'images':     list(product.images.all()),
        'errors':     errors,
        'action':     'edit',
        'page_title': f'Modifier — {product.name}',
    })


@login_required
@superadmin_required
def product_image_delete(request, pk):
    from .models import PartnerProductImage
    if request.method != 'POST':
        return redirect('sites:product_list')
    img = get_object_or_404(PartnerProductImage, pk=pk)
    product_pk = img.product_id
    img.image.delete(save=False)
    img.delete()
    return redirect('sites:product_edit', pk=product_pk)


@login_required
@superadmin_required
def product_detail(request, pk):
    from .models import PartnerProduct
    product = get_object_or_404(PartnerProduct, pk=pk)
    images  = list(product.images.all())
    return render(request, 'sites_mgmt/product_detail.html', {
        'product':    product,
        'images':     images,
        'page_title': product.name,
    })


@login_required
@superadmin_required
def product_delete(request, pk):
    from .models import PartnerProduct
    if request.method != 'POST':
        return redirect('sites:product_list')
    product = get_object_or_404(PartnerProduct, pk=pk)
    name = product.name
    product.delete()
    messages.success(request, f'Produit « {name} » supprimé.')
    return redirect('sites:product_list')


# ─── API JSON (pour charts) ────────────────────────────────────────────────────

@login_required
def site_guests_json(request, site_id):
    """Endpoint debug : historique guests brut d'un site."""
    site = get_object_or_404(HotspotSite, unifi_site_id=site_id)
    if not request.user.is_superadmin and site not in request.user.managed_sites.all():
        return JsonResponse({'error': 'Accès refusé'}, status=403)
    guests = unifi.get_guests(site_id)
    return JsonResponse({'count': len(guests), 'guests': guests})


@login_required
def site_stats_json(request, site_id):
    """Endpoint AJAX : stats live d'un site."""
    site = get_object_or_404(HotspotSite, unifi_site_id=site_id)
    if not request.user.is_superadmin and site not in request.user.managed_sites.all():
        return JsonResponse({'error': 'Accès refusé'}, status=403)

    stats = unifi.get_site_stats(site_id)
    return JsonResponse(stats)
