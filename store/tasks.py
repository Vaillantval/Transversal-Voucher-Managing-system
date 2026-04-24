import logging
from celery import shared_task

logger = logging.getLogger(__name__)


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
