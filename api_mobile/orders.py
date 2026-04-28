import logging

from django.core.cache import cache
from django.db import transaction
from django.shortcuts import get_object_or_404
from ninja import Router

from .schemas import (
    CheckoutIn, CheckoutOut,
    OrderDetailOut, OrderItemOut, OrderStatusOut,
    OrderSummaryOut, PaginatedOrdersOut,
)
from .security import mobile_auth, get_optional_user

logger = logging.getLogger(__name__)
router = Router(tags=['Orders'])


def _assert_owner(order, store_user):
    """Raise 403-style if the order doesn't belong to this StoreUser."""
    if order.customer.store_user_id != store_user.pk:
        from ninja.errors import HttpError
        raise HttpError(403, 'Accès interdit')


@router.post('/checkout/', response={200: CheckoutOut, 400: dict, 422: dict})
def checkout(request, data: CheckoutIn):
    from sites_mgmt.models import HotspotSite, VoucherTier
    from store.models import CustomerProfile, Order, OrderItem
    from store.services.plopplop import create_transaction

    if data.payment_method not in ('moncash', 'natcash'):
        return 400, {'detail': 'payment_method doit être moncash ou natcash'}

    if not data.items:
        return 400, {'detail': 'La commande doit contenir au moins un article'}

    site = get_object_or_404(HotspotSite, pk=data.site_id, is_active=True)
    store_user = get_optional_user(request)  # None si non connecté

    # Validate items + compute total
    order_items_data = []
    total = 0
    for item_in in data.items:
        qty = max(1, min(10, item_in.quantity))
        tier = get_object_or_404(
            VoucherTier,
            pk=item_in.tier_id,
            sites=site,
            is_active=True,
            is_replacement=False,
            is_admin_code=False,
        )
        subtotal = tier.price_htg * qty
        total += subtotal
        order_items_data.append({'tier': tier, 'quantity': qty, 'unit_price': tier.price_htg})

    with transaction.atomic():
        if store_user:
            profile, _ = CustomerProfile.objects.update_or_create(
                store_user=store_user,
                defaults={'full_name': data.full_name, 'phone': data.phone},
            )
        else:
            profile = CustomerProfile.objects.create(
                full_name=data.full_name,
                phone=data.phone,
            )
        order = Order.objects.create(
            customer=profile,
            total_htg=total,
            payment_method=data.payment_method,
        )
        for item_data in order_items_data:
            OrderItem.objects.create(
                order=order,
                site=site,
                tier=item_data['tier'],
                quantity=item_data['quantity'],
                unit_price=item_data['unit_price'],
            )

    try:
        result = create_transaction(order.reference, float(total), data.payment_method)
    except Exception as exc:
        logger.error(f'PlopPlop create_transaction error for {order.reference}: {exc}')
        order.status = Order.STATUS_FAILED
        order.save(update_fields=['status'])
        return 400, {'detail': 'Service de paiement indisponible. Réessayez.'}

    if not result.get('status'):
        order.status = Order.STATUS_FAILED
        order.save(update_fields=['status'])
        return 400, {'detail': 'Échec création transaction PlopPlop'}

    order.plopplop_transaction_id = result.get('transaction_id', '')
    order.save(update_fields=['plopplop_transaction_id'])

    return 200, CheckoutOut(order_ref=order.reference, payment_url=result['url'])


@router.get('/orders/{order_ref}/status/', response={200: OrderStatusOut, 403: dict, 404: dict})
def order_status(request, order_ref: str):
    from store.models import Order
    from store.services.plopplop import verify_transaction

    order = get_object_or_404(Order, reference=order_ref)
    store_user = get_optional_user(request)
    if store_user and order.customer.store_user_id != store_user.pk:
        from ninja.errors import HttpError
        raise HttpError(403, 'Accès interdit')

    if order.status == Order.STATUS_DELIVERED:
        return 200, OrderStatusOut(status='delivered', voucher_codes=order.get_all_codes())

    if order.status == Order.STATUS_FAILED:
        return 200, OrderStatusOut(status='failed', voucher_codes=[])

    if order.status in (Order.STATUS_PROCESSING, Order.STATUS_PAID):
        return 200, OrderStatusOut(status='processing', voucher_codes=[])

    # Still pending — check with PlopPlop
    try:
        result = verify_transaction(order_ref)
    except Exception as exc:
        logger.warning(f'PlopPlop verify error for {order_ref}: {exc}')
        return 200, OrderStatusOut(status='pending', voucher_codes=[])

    if result.get('trans_status') == 'ok' and order.status == Order.STATUS_PENDING:
        lock_key = f'order_lock_{order_ref}'
        if cache.add(lock_key, 1, timeout=60):
            order.status = Order.STATUS_PAID
            order.save(update_fields=['status'])
            from store.tasks import deliver_order
            deliver_order.delay(order.pk)

    return 200, OrderStatusOut(status=order.status, voucher_codes=[])


@router.get('/orders/', auth=mobile_auth, response=PaginatedOrdersOut)
def list_orders(request, page: int = 1, page_size: int = 20):
    from store.models import Order

    page_size = min(100, max(1, page_size))
    page      = max(1, page)

    qs = (
        Order.objects
        .filter(customer__store_user=request.auth)
        .order_by('-created_at')
    )
    total = qs.count()
    offset = (page - 1) * page_size
    orders = qs[offset: offset + page_size]

    results = [
        OrderSummaryOut(
            reference=o.reference,
            created_at=o.created_at,
            status=o.status,
            total_htg=o.total_htg,
            items_count=o.items.count(),
        )
        for o in orders
    ]
    return PaginatedOrdersOut(count=total, page=page, page_size=page_size, results=results)


@router.get('/orders/{order_ref}/', auth=mobile_auth, response={200: OrderDetailOut, 403: dict, 404: dict})
def order_detail(request, order_ref: str):
    from store.models import Order

    order = get_object_or_404(
        Order.objects.prefetch_related('items__tier', 'items__site'),
        reference=order_ref,
    )
    _assert_owner(order, request.auth)

    items = [
        OrderItemOut(
            tier_label=i.tier.label,
            site_name=i.site.name,
            quantity=i.quantity,
            unit_price=i.unit_price,
            subtotal=i.subtotal,
            voucher_codes=i.voucher_codes,
        )
        for i in order.items.all()
    ]
    return 200, OrderDetailOut(
        reference=order.reference,
        created_at=order.created_at,
        status=order.status,
        total_htg=order.total_htg,
        payment_method=order.payment_method,
        items=items,
    )
