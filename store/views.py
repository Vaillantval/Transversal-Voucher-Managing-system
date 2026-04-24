import json
import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.core.cache import cache

from sites_mgmt.models import HotspotSite, VoucherTier
from .models import StoreBanner, CustomerProfile, Cart, CartItem, Order, OrderItem
from .services.plopplop import create_transaction, verify_transaction

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


def _get_or_create_cart(request):
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

    return render(request, 'store/storefront.html', {
        'banners':     banners,
        'plans':       plans,
        'sites':       sites,
        'sites_json':  sites_json,
        'profile':     profile,
        'cart_count':  cart.item_count,
    })


def plan_detail_api(request, tier_id):
    tier = get_object_or_404(
        VoucherTier, pk=tier_id, is_active=True, is_replacement=False, is_admin_code=False
    )
    sites = list(tier.sites.filter(is_active=True).values('id', 'name'))
    return JsonResponse({
        'id':              tier.pk,
        'label':           tier.label,
        'duration_display': tier.duration_display,
        'price_htg':       str(tier.price_htg),
        'sites':           sites,
    })


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
        return redirect('store:checkout')

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
        ('all',      'Toutes méthodes'),
        ('moncash',  'MonCash'),
        ('natcash',  'NatCash'),
        ('kashpaw',  'Kashpaw'),
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
    payment_method = request.POST.get('payment_method', 'all')

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
