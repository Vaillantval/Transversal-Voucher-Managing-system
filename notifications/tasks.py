import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='notifications.tasks.check_stock_levels')
def check_stock_levels():
    try:
        from notifications.scheduler import check_stock_levels as _fn
        _fn()
    except Exception as e:
        logger.error("check_stock_levels task échoué : %s", e)


@shared_task(name='notifications.tasks.send_monthly_reports')
def send_monthly_reports():
    try:
        from notifications.scheduler import send_monthly_reports as _fn
        _fn()
    except Exception as e:
        logger.error("send_monthly_reports task échoué : %s", e)
