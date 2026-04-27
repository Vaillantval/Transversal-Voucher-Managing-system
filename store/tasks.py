import logging
from celery import shared_task

logger = logging.getLogger(__name__)


def _claim_from_stock(item, order_reference):
    """Tente de réserver `item.quantity` vouchers actifs depuis le stock existant.
    Utilise select_for_update(skip_locked) pour éviter les doublons en concurrence.
    Retourne la liste de codes réservés, ou [] si le stock est insuffisant."""
    from django.db import transaction
    from django.utils import timezone
    from vouchers.models import VoucherLog

    with transaction.atomic():
        stock = list(
            VoucherLog.objects.select_for_update(skip_locked=True).filter(
                site=item.site,
                tier=item.tier,
                status=VoucherLog.STATUS_ACTIVE,
            ).order_by('created_at')[:item.quantity]
        )

        if len(stock) < item.quantity:
            return []

        VoucherLog.objects.filter(pk__in=[v.pk for v in stock]).update(
            status=VoucherLog.STATUS_USED,
            used_at=timezone.now(),
            note=f'BonNet-{order_reference}',
        )
        return [v.code for v in stock]


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def deliver_order(self, order_id):
    from .models import Order
    from unifi_api import client as unifi
    from .services.sms import send_voucher_sms

    try:
        order = Order.objects.get(pk=order_id)
    except Order.DoesNotExist:
        logger.error(f'deliver_order: Order {order_id} not found')
        return

    codes = []
    for item in order.items.select_related('tier', 'site').all():
        try:
            # 1. Priorité : stock existant (autogen)
            item_codes = _claim_from_stock(item, order.reference)

            if item_codes:
                logger.info(
                    f'deliver_order: {len(item_codes)} codes from stock '
                    f'(item {item.pk}, site {item.site.name})'
                )
            else:
                # 2. Fallback : génération à la volée via UniFi
                logger.info(
                    f'deliver_order: stock insuffisant pour item {item.pk}, '
                    f'génération UniFi en cours'
                )
                result = unifi.create_vouchers(
                    site_id=item.site.unifi_site_id,
                    expire_minutes=item.tier.duration_minutes,
                    count=item.quantity,
                    quota=1,
                    note=f'BonNet-{order.reference}',
                )
                item_codes = [v.get('code', '') for v in (result or []) if v.get('code')]

                if not item_codes:
                    all_vouchers = unifi.get_vouchers(item.site.unifi_site_id)
                    item_codes = [
                        v.get('code', '') for v in all_vouchers
                        if v.get('note') == f'BonNet-{order.reference}' and v.get('code')
                    ]

            item.voucher_codes = item_codes
            item.save(update_fields=['voucher_codes'])
            codes.extend(item_codes)

        except Exception as e:
            logger.error(f'deliver_order item {item.pk}: {e}')
            raise self.retry(exc=e)

    order.status = Order.STATUS_DELIVERED
    order.save(update_fields=['status'])

    try:
        site_name = order.items.first().site.name if order.items.exists() else ''
        send_voucher_sms(order.customer.phone, codes, site_name)
    except Exception as e:
        logger.warning(f'SMS failed for order {order.reference}: {e}')

    # Push notification vers l'app mobile (si le client a des device tokens)
    try:
        if order.customer.store_user_id:
            from api_mobile.firebase import send_push
            from api_mobile.models import DeviceToken
            tokens = list(
                DeviceToken.objects
                .filter(store_user_id=order.customer.store_user_id)
                .values_list('fcm_token', flat=True)
            )
            send_push(
                tokens,
                title='Tes codes sont prêts ✅',
                body=f'Ta commande {order.reference} est livrée. Ouvre l\'app pour voir tes codes.',
                data={'order_ref': order.reference},
            )
    except Exception as e:
        logger.warning(f'Push failed for order {order.reference}: {e}')
