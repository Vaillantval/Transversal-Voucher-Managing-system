import logging
from datetime import date, timedelta

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

STOCK_ALERT_THRESHOLD = 30
STOCK_ALERT_COOLDOWN_HOURS = 24


def check_stock_levels():
    """Vérifie le stock de vouchers de chaque site, alerte si <= 15."""
    try:
        from sites_mgmt.models import HotspotSite
        from unifi_api import client as unifi
        from .models import Notification
        from .email_service import send_email, build_stock_alert_html

        sites = list(HotspotSite.objects.filter(is_active=True))
        if not sites:
            return

        all_vouchers = unifi.get_all_vouchers(sites)
        all_guests   = unifi.get_all_guests(sites)

        # Compter les disponibles par site
        site_counts: dict[str, int] = {}
        for v in all_vouchers:
            sid = v.get('site_unifi_id', '')
            if sid:
                site_counts[sid] = site_counts.get(sid, 0) + (1 if v.get('is_available') else 0)

        # Sessions actives dans les 2 dernières semaines par site
        two_weeks_ago = (timezone.now() - timedelta(weeks=2)).timestamp()
        active_sites: set[str] = set()
        for g in all_guests:
            if g.get('sold_ts', 0) >= two_weeks_ago:
                active_sites.add(g.get('site_unifi_id', ''))

        # Sites avec au moins 1 device
        all_stats = unifi.get_all_site_stats(sites)

        for site in sites:
            count = site_counts.get(site.unifi_site_id, 0)
            if count > STOCK_ALERT_THRESHOLD:
                continue

            # Site doit avoir au moins 1 device ET des sessions dans les 2 dernières semaines
            stats = all_stats.get(site.unifi_site_id, {})
            if stats.get('device_total', 0) == 0:
                continue
            if site.unifi_site_id not in active_sites:
                continue

            cutoff = timezone.now() - timedelta(hours=STOCK_ALERT_COOLDOWN_HOURS)
            already = Notification.objects.filter(
                type=Notification.TYPE_STOCK_LOW,
                site=site,
                created_at__gte=cutoff,
            ).exists()
            if already:
                continue

            notif = Notification.objects.create(
                type=Notification.TYPE_STOCK_LOW,
                site=site,
                title=f"Stock faible — {site.name}",
                message=(
                    f"Le site {site.name} a seulement {count} voucher(s) disponible(s). "
                    f"Veuillez en créer de nouveaux."
                ),
                stock_count=count,
            )
            logger.info(f"Stock alert créé : {site.name} ({count} vouchers)")

            admin_emails = list(
                site.admins.filter(email__isnull=False, role='site_admin')
                .exclude(email='')
                .values_list('email', flat=True)
            )
            if admin_emails:
                try:
                    html = build_stock_alert_html(site, count)
                    result = send_email(
                        to=admin_emails,
                        subject=f"[BonNet] ⚠️ Stock faible — {site.name} ({count} restant(s))",
                        html=html,
                    )
                    if result:
                        notif.email_sent = True
                        notif.save(update_fields=['email_sent'])
                except Exception as e:
                    logger.error(f"Email stock alert {site.name}: {e}")

    except Exception as e:
        logger.error(f"check_stock_levels error: {e}", exc_info=True)


def send_monthly_reports():
    """Envoie les rapports Excel mensuels de tous les sites aux emails ADMIN_NOTIFY."""
    try:
        from sites_mgmt.models import HotspotSite
        from .models import Notification
        from .email_service import send_email, build_monthly_report_html
        from .report_helper import generate_excel_bytes, generate_pdf_bytes

        admin_notify = getattr(settings, 'ADMIN_NOTIFY', '')
        to_emails = [e.strip() for e in admin_notify.split(',') if e.strip()]
        if not to_emails:
            logger.warning("ADMIN_NOTIFY non configuré — rapport mensuel non envoyé.")
            return

        today = date.today()
        first_day_prev = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        last_day_prev = today.replace(day=1) - timedelta(days=1)
        date_from = first_day_prev.isoformat()
        date_to = last_day_prev.isoformat()
        month_label = first_day_prev.strftime('%B %Y')

        sites = list(HotspotSite.objects.filter(is_active=True))
        if not sites:
            return

        attachments = []

        try:
            excel_bytes = generate_excel_bytes(sites=sites, date_from=date_from, date_to=date_to)
            attachments.append({
                "filename": f"bonnet_rapport_{date_from}_{date_to}.xlsx",
                "content": list(excel_bytes),
            })
        except Exception as e:
            logger.error(f"Excel generation: {e}")

        try:
            pdf_bytes = generate_pdf_bytes(sites=sites, date_from=date_from, date_to=date_to)
            attachments.append({
                "filename": f"bonnet_rapport_{date_from}_{date_to}.pdf",
                "content": list(pdf_bytes),
            })
        except Exception as e:
            logger.error(f"PDF generation: {e}")

        html = build_monthly_report_html(month_label, sites, date_from, date_to)
        result = send_email(
            to=to_emails,
            subject=f"[BonNet] Rapport mensuel — {month_label}",
            html=html,
            attachments=attachments or None,
        )

        Notification.objects.create(
            type=Notification.TYPE_MONTHLY_REPORT,
            title=f"Rapport mensuel — {month_label}",
            message=f"Rapport mensuel envoyé pour {len(sites)} site(s) à : {', '.join(to_emails)}",
            email_sent=bool(result),
        )
        logger.info(f"Rapport mensuel {month_label} envoyé à {to_emails}")

    except Exception as e:
        logger.error(f"send_monthly_reports error: {e}", exc_info=True)


def start():
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    from django_apscheduler.jobstores import DjangoJobStore

    scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)
    scheduler.add_jobstore(DjangoJobStore(), 'default')

    scheduler.add_job(
        check_stock_levels,
        trigger=IntervalTrigger(minutes=30),
        id='check_stock_levels',
        name='Vérification stock vouchers (toutes les 30 min)',
        replace_existing=True,
        misfire_grace_time=300,
    )

    scheduler.add_job(
        send_monthly_reports,
        trigger=CronTrigger(day='last', hour=8, minute=0, timezone=settings.TIME_ZONE),
        id='send_monthly_reports',
        name='Rapport mensuel automatique (dernier jour du mois, 8h)',
        replace_existing=True,
        misfire_grace_time=3600,
    )

    scheduler.start()
    logger.info("APScheduler démarré — jobs : stock toutes les 30 min, rapport le dernier jour du mois.")
