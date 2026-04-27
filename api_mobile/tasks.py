import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def send_push_campaign(campaign_id: int):
    from django.utils import timezone
    from store.models import StoreUser
    from .firebase import send_push
    from .models import DeviceToken, PushCampaign

    try:
        campaign = PushCampaign.objects.select_related('target_site').get(pk=campaign_id)
    except PushCampaign.DoesNotExist:
        logger.error(f'send_push_campaign: PushCampaign {campaign_id} not found')
        return

    tokens_qs = DeviceToken.objects.select_related('store_user')

    if campaign.target == PushCampaign.TARGET_SITE and campaign.target_site:
        user_ids = (
            StoreUser.objects
            .filter(profiles__orders__items__site=campaign.target_site)
            .distinct()
            .values_list('pk', flat=True)
        )
        tokens_qs = tokens_qs.filter(store_user_id__in=user_ids)

    if campaign.notif_promo_only:
        tokens_qs = tokens_qs.filter(store_user__notif_promo=True)

    tokens = list(tokens_qs.values_list('fcm_token', flat=True))
    sent = send_push(
        tokens,
        title=campaign.title,
        body=campaign.body,
        data={'campaign_id': str(campaign_id)},
    )

    campaign.sent_at = timezone.now()
    campaign.recipients_count = sent
    campaign.save(update_fields=['sent_at', 'recipients_count'])
    logger.info(f'Campaign {campaign_id} sent to {sent} device(s)')
