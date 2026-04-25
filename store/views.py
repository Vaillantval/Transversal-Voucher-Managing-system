import json
import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.core.cache import cache

from sites_mgmt.models import HotspotSite, VoucherTier
from .models import StoreBanner, CustomerProfile, Cart, CartItem, Order, OrderItem, StoreUser
from .services.plopplop import create_transaction, verify_transaction
from .google_auth import build_google_auth_url, exchange_code, get_or_create_store_user, merge_session_cart

logger = logging.getLogger(__name__)


def filter_plans_for_storefront(tiers):
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


def _get_store_user(request):
    uid = request.session.get('store_user_id')
    if not uid:
        return None
    try:
        return StoreUser.objects.get(pk=uid)
    except StoreUser.DoesNotExist:
        request.session.pop('store_user_id', None)
        return None


def _get_or_create_cart(request):
    store_user = _get_store_user(request)
    if store_user:
        cart, _ = Cart.objects.get_or_create(store_user=store_user)
        return cart
    if not request.session.session_key:
        request.session.create()
    cart, _ = Cart.objects.get_or_create(session_key=request.session.session_key)
    return cart


def storefront(request):
    banners = StoreBanner.objects.filter(is_active=True).order_by('order')
    all_tiers = VoucherTier.objects.filter(
        is_active=True, is_replacement=False, is_admin_code=False, price_htg__gt=0
    ).prefetch_related('sites')
    plans = filter_plans_for_storefront(list(all_tiers))
    sites = HotspotSite.objects.filter(is_active=True).order_by('name')

    sites_json = json.dumps([
        {
            'id': s.pk,
            'name': s.name,
            'latitude': float(s.latitude) if s.latitude else None,
            'longitude': float(s.longitude) if s.longitude else None,
        }
        for s in sites
    ])

    profile = None
    if request.session.session_key:
        profile = CustomerProfile.objects.filter(
            session_key=request.session.session_key
        ).first()

    cart = _get_or_create_cart(request)

    partner_perks = [
        ('cash-coin',        'Revenu mensuel'),
        ('tools',            'Équipement fourni'),
        ('headset',          'Support 7j/7'),
        ('graph-up-arrow',   'Croissance garantie'),
    ]

    return render(request, 'store/storefront.html', {
        'banners':        banners,
        'plans':          plans,
        'sites':          sites,
        'sites_json':     sites_json,
        'profile':        profile,
        'cart_count':     cart.item_count,
        'partner_perks':  partner_perks,
    })


def plan_detail_api(request, tier_id):
    tier = get_object_or_404(
        VoucherTier, pk=tier_id, is_active=True, is_replacement=False, is_admin_code=False
    )
    sites = list(tier.sites.filter(is_active=True).values('id', 'name'))
    return JsonResponse({
        'id':               tier.pk,
        'label':            tier.label,
        'duration_display': tier.duration_display,
        'price_htg':        str(tier.price_htg),
        'sites':            sites,
    })


def site_tiers_api(request, site_id):
    """Retourne les tiers actifs disponibles pour un site donné."""
    site = get_object_or_404(HotspotSite, pk=site_id, is_active=True)
    tiers = VoucherTier.objects.filter(
        sites=site, is_active=True, is_replacement=False,
        is_admin_code=False, price_htg__gt=0,
    ).order_by('duration', 'unit')
    return JsonResponse({'tiers': [
        {
            'id':               t.pk,
            'label':            t.label,
            'duration_display': t.duration_display,
            'price_htg':        str(t.price_htg),
            'duration_minutes': t.duration_minutes,
        }
        for t in tiers
    ]})


@require_POST
def cart_add(request):
    tier_id = request.POST.get('tier_id')
    site_id = request.POST.get('site_id')
    try:
        quantity = max(1, min(10, int(request.POST.get('quantity', 1))))
    except (ValueError, TypeError):
        quantity = 1

    tier = get_object_or_404(VoucherTier, pk=tier_id, is_active=True)
    site = get_object_or_404(HotspotSite, pk=site_id, is_active=True)

    cart = _get_or_create_cart(request)
    item, created = CartItem.objects.get_or_create(
        cart=cart, tier=tier, site=site,
        defaults={'quantity': quantity},
    )
    if not created:
        item.quantity = min(10, item.quantity + quantity)
        item.save(update_fields=['quantity'])

    if request.POST.get('buy_now'):
        return redirect('store:cart_view')

    return JsonResponse({'cart_count': cart.item_count, 'added': True})


@require_POST
def cart_remove(request):
    item_id = request.POST.get('item_id')
    cart = _get_or_create_cart(request)
    CartItem.objects.filter(pk=item_id, cart=cart).delete()
    return redirect('store:cart_view')


def cart_view(request):
    cart = _get_or_create_cart(request)
    profile = None
    if request.session.session_key:
        profile = CustomerProfile.objects.filter(
            session_key=request.session.session_key
        ).first()
    payment_methods = [
        ('moncash', 'MonCash'),
        ('natcash', 'NatCash'),
    ]
    return render(request, 'store/cart.html', {
        'cart':             cart,
        'cart_count':       cart.item_count,
        'profile':          profile,
        'payment_methods':  payment_methods,
    })


@require_POST
def initiate_checkout(request):
    full_name      = request.POST.get('full_name', '').strip()
    phone          = request.POST.get('phone', '').strip()
    payment_method = request.POST.get('payment_method', 'moncash')

    if not full_name or not phone:
        messages.error(request, 'Nom et numéro de téléphone obligatoires.')
        return redirect('store:cart_view')

    cart = _get_or_create_cart(request)
    if not cart.items.exists():
        messages.error(request, 'Votre panier est vide.')
        return redirect('store:storefront')

    profile, _ = CustomerProfile.objects.update_or_create(
        session_key=request.session.session_key,
        defaults={'full_name': full_name, 'phone': phone},
    )

    total = cart.total
    order = Order.objects.create(customer=profile, total_htg=total)
    for item in cart.items.select_related('tier', 'site').all():
        OrderItem.objects.create(
            order=order,
            tier=item.tier,
            site=item.site,
            quantity=item.quantity,
            unit_price=item.tier.price_htg,
        )

    try:
        result = create_transaction(order.reference, float(total), payment_method)
        if result.get('status'):
            order.plopplop_transaction_id = result.get('transaction_id', '')
            order.save(update_fields=['plopplop_transaction_id'])
            cart.items.all().delete()
            return redirect(result['url'])
        else:
            order.status = Order.STATUS_FAILED
            order.save(update_fields=['status'])
            messages.error(request, 'Erreur lors de l\'initiation du paiement. Veuillez réessayer.')
    except Exception as e:
        logger.error(f'PlopPlop create_transaction error: {e}')
        order.status = Order.STATUS_FAILED
        order.save(update_fields=['status'])
        messages.error(request, 'Impossible de joindre le service de paiement. Réessayez dans quelques instants.')

    return redirect('store:cart_view')


def order_confirm(request, order_ref):
    order = get_object_or_404(Order, reference=order_ref)
    return render(request, 'store/confirm.html', {'order': order})


def plopplop_return(request):
    """Landing page statique configurée dans le dashboard PlopPlop.
    PlopPlop redirige ici avec ?refference_id=BONNET-XXXXXXXX après paiement."""
    order_ref = request.GET.get('refference_id', '').strip()
    if order_ref:
        return redirect('store:order_confirm', order_ref=order_ref)
    return redirect('store:storefront')


def order_status_api(request, order_ref):
    order = get_object_or_404(Order, reference=order_ref)

    if order.status == Order.STATUS_DELIVERED:
        return JsonResponse({'status': 'delivered', 'codes': order.get_all_codes()})

    if order.status in (Order.STATUS_PROCESSING, Order.STATUS_PAID):
        return JsonResponse({'status': 'processing'})

    if order.status == Order.STATUS_FAILED:
        return JsonResponse({'status': 'failed'})

    try:
        result = verify_transaction(order_ref)
    except Exception as e:
        logger.warning(f'PlopPlop verify error for {order_ref}: {e}')
        return JsonResponse({'status': 'pending'})

    if result.get('trans_status') == 'ok' and order.status == Order.STATUS_PENDING:
        lock_key = f'order_lock_{order_ref}'
        if not cache.add(lock_key, 1, timeout=60):
            return JsonResponse({'status': 'processing'})
        order.status = Order.STATUS_PAID
        order.save(update_fields=['status'])
        from .tasks import deliver_order
        deliver_order.delay(order.pk)

    return JsonResponse({'status': order.status})


def partner_page(request):
    return redirect('accounts:partner_register')


# ── Google OAuth ──────────────────────────────────────────────────────────────

def google_login(request):
    next_url = request.GET.get('next', '')
    if next_url:
        request.session['google_next'] = next_url
    return redirect(build_google_auth_url(request))


def google_callback(request):
    state_in   = request.GET.get('state', '')
    state_sess = request.session.pop('google_oauth_state', None)
    if not state_sess or state_in != state_sess:
        messages.error(request, 'Erreur d\'authentification. Veuillez réessayer.')
        return redirect('store:storefront')

    code = request.GET.get('code')
    if not code:
        messages.error(request, 'Connexion Google annulée.')
        return redirect('store:storefront')

    try:
        userinfo   = exchange_code(request, code)
        store_user = get_or_create_store_user(userinfo)
        merge_session_cart(request, store_user)
        request.session['store_user_id'] = store_user.pk
        messages.success(request, f'Bienvenue, {store_user.first_name} !')
    except Exception as e:
        logger.error(f'Google OAuth callback error: {e}')
        messages.error(request, 'Impossible de se connecter avec Google. Réessayez.')
        return redirect('store:storefront')

    next_url = request.session.pop('google_next', '')
    return redirect(next_url or 'store:storefront')


def store_logout(request):
    request.session.pop('store_user_id', None)
    return redirect('store:storefront')


# ── Profil client ─────────────────────────────────────────────────────────────

def my_orders(request):
    store_user = _get_store_user(request)
    if not store_user:
        return redirect('store:google_login')
    profiles = store_user.profiles.prefetch_related('orders__items__tier', 'orders__items__site').all()
    orders = Order.objects.filter(customer__in=profiles).order_by('-created_at')
    return render(request, 'store/my_orders.html', {
        'store_user': store_user,
        'orders':     orders,
        'cart_count': _get_or_create_cart(request).item_count,
    })


@require_POST
def update_profile(request):
    store_user = _get_store_user(request)
    if not store_user:
        return redirect('store:google_login')
    store_user.phone   = request.POST.get('phone', '').strip()
    store_user.address = request.POST.get('address', '').strip()
    store_user.save(update_fields=['phone', 'address'])
    messages.success(request, 'Profil mis à jour.')
    return redirect('store:my_orders')
