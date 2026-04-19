from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import User


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard:index')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            if not request.POST.get('remember_me'):
                request.session.set_expiry(0)  # expire à la fermeture du navigateur
            else:
                request.session.set_expiry(60 * 60 * 24 * 30)  # 30 jours
            next_url = request.GET.get('next', '/dashboard/')
            return redirect(next_url)
        else:
            messages.error(request, 'Identifiants incorrects. Veuillez réessayer.')

    return render(request, 'accounts/login.html')


@login_required
def logout_view(request):
    logout(request)
    return redirect('accounts:login')


@login_required
def profile_view(request):
    return render(request, 'accounts/profile.html', {'user': request.user})


def _sync_unifi_users_to_db():
    """Importe/met à jour tous les admins UniFi dans la base BonNet."""
    from unifi_api.client import get_all_admins
    from sites_mgmt.models import HotspotSite

    admins = get_all_admins()
    if not admins:
        return

    site_map = {s.unifi_site_id: s for s in HotspotSite.objects.filter(is_active=True)}
    all_sites = list(site_map.values())

    for admin in admins:
        username = admin.get('name', '').strip()
        if not username:
            continue

        is_super = admin.get('is_super', False)

        user, created = User.objects.get_or_create(username=username)
        if created:
            user.set_unusable_password()

        user.role = User.ROLE_SUPERADMIN if is_super else User.ROLE_SITE_ADMIN
        user.save()

        if is_super:
            user.managed_sites.set(all_sites)
        else:
            site_ids = set()
            for perm in admin.get('permissions', []):
                for sid in perm.get('sites', []):
                    site_ids.add(sid)
            user.managed_sites.set([site_map[sid] for sid in site_ids if sid in site_map])


@login_required
def user_list(request):
    if not request.user.is_superadmin:
        messages.error(request, 'Accès réservé aux super-admins.')
        return redirect('dashboard:index')

    from sites_mgmt.models import HotspotSite
    _sync_unifi_users_to_db()
    users = User.objects.all().prefetch_related('managed_sites').order_by('role', 'username')
    sites = HotspotSite.objects.filter(is_active=True).order_by('name')
    return render(request, 'accounts/users.html', {
        'page_title': 'Gestion des utilisateurs',
        'users': users,
        'sites': sites,
    })


@login_required
def user_edit(request, pk):
    if not request.user.is_superadmin:
        messages.error(request, 'Accès réservé aux super-admins.')
        return redirect('dashboard:index')

    if request.method != 'POST':
        return redirect('accounts:users')

    from sites_mgmt.models import HotspotSite
    target = get_object_or_404(User, pk=pk)

    # Empêcher de se rétrograder soi-même
    if target == request.user and request.POST.get('role') != User.ROLE_SUPERADMIN:
        messages.error(request, 'Vous ne pouvez pas changer votre propre rôle.')
        return redirect('accounts:users')

    new_role = request.POST.get('role', User.ROLE_SITE_ADMIN)
    if new_role not in (User.ROLE_SUPERADMIN, User.ROLE_SITE_ADMIN):
        new_role = User.ROLE_SITE_ADMIN

    target.role = new_role
    target.save()

    # Mise à jour des sites assignés
    site_pks = request.POST.getlist('sites')
    all_sites = HotspotSite.objects.all()
    for site in all_sites:
        if str(site.pk) in site_pks:
            site.admins.add(target)
        else:
            site.admins.remove(target)

    messages.success(request, f'Utilisateur « {target.username} » mis à jour.')
    return redirect('accounts:users')


@login_required
def user_delete(request, pk):
    if not request.user.is_superadmin:
        messages.error(request, 'Accès réservé aux super-admins.')
        return redirect('dashboard:index')

    if request.method != 'POST':
        return redirect('accounts:users')

    target = get_object_or_404(User, pk=pk)

    if target == request.user:
        messages.error(request, 'Vous ne pouvez pas supprimer votre propre compte.')
        return redirect('accounts:users')

    username = target.username
    target.delete()
    messages.success(request, f'Utilisateur « {username} » supprimé.')
    return redirect('accounts:users')
