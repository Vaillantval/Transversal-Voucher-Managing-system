import logging
from datetime import date, timedelta

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

STOCK_ALERT_THRESHOLD = 30
STOCK_ALERT_COOLDOWN_HOURS = 24

_MOIS_FR = {
    1: 'Janvier', 2: 'Février', 3: 'Mars', 4: 'Avril',
    5: 'Mai', 6: 'Juin', 7: 'Juillet', 8: 'Août',
    9: 'Septembre', 10: 'Octobre', 11: 'Novembre', 12: 'Décembre',
}


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

        from .models import AutoGenConfig
        autogen = AutoGenConfig.get()
        autogen_site_ids = set(autogen.sites.values_list('unifi_site_id', flat=True)) if autogen.enabled else set()

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
                # Vérifier si on doit déclencher la génération automatique
                if autogen.enabled and site.unifi_site_id in autogen_site_ids:
                    trigger_cutoff = timezone.now() - timedelta(hours=autogen.delay_hours)
                    pending_alert = Notification.objects.filter(
                        type=Notification.TYPE_STOCK_LOW,
                        site=site,
                        created_at__lte=trigger_cutoff,
                        auto_gen_triggered=False,
                    ).first()
                    if pending_alert:
                        logger.info(f"Auto-gen déclenchée pour {site.name} (stock={count})")
                        pending_alert.auto_gen_triggered = True
                        pending_alert.save(update_fields=['auto_gen_triggered'])
                        _auto_generate_vouchers_for_site(site, count, autogen.count_per_tier)
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


def _auto_generate_vouchers_for_site(site, current_stock: int, count_per_tier: int = 100):
    """Génère 50 vouchers × chaque forfait actif pour un site, puis notifie par email."""
    try:
        from sites_mgmt.models import VoucherTier
        from vouchers.models import VoucherLog
        from unifi_api import client as unifi
        from .models import Notification
        from .email_service import send_email, build_auto_gen_html

        now = timezone.now()
        date_label = f"{now.day} {_MOIS_FR[now.month]} {now.year}"

        tiers = list(VoucherTier.objects.filter(is_active=True))
        if not tiers:
            logger.warning(f"Auto-gen {site.name}: aucun forfait actif.")
            return

        total_created = 0
        tier_results = []

        for tier in tiers:
            note = f"{tier.label}_{site.name}_{date_label}"
            created = unifi.create_vouchers(
                site_id=site.unifi_site_id,
                expire_minutes=tier.max_minutes,
                count=count_per_tier,
                quota=1,
                note=note,
            )
            if not created:
                logger.error(f"Auto-gen {site.name} / {tier.label}: échec UniFi.")
                tier_results.append({'tier': tier, 'count': 0, 'success': False})
                continue

            # Sync en base
            synced = 0
            for v in unifi.get_vouchers(site.unifi_site_id):
                if v.get('note', '') == note:
                    _, is_new = VoucherLog.objects.get_or_create(
                        unifi_id=v['_id'],
                        defaults={
                            'site': site,
                            'created_by': None,
                            'tier': tier,
                            'code': v.get('code', ''),
                            'duration_minutes': v.get('duration', tier.max_minutes),
                            'quota': v.get('quota', 1),
                            'note': note,
                            'price_htg': tier.price_htg,
                        }
                    )
                    if is_new:
                        synced += 1

            total_created += synced
            tier_results.append({'tier': tier, 'count': synced, 'success': True})
            logger.info(f"Auto-gen {site.name} / {tier.label}: {synced} vouchers créés.")

        # Notification en base
        notif = Notification.objects.create(
            type=Notification.TYPE_AUTO_GENERATED,
            site=site,
            title=f"Génération automatique — {site.name}",
            message=(
                f"{total_created} voucher(s) générés automatiquement sur {site.name} "
                f"({len(tiers)} forfait(s), {count_per_tier} par forfait)."
            ),
            stock_count=current_stock,
        )

        # Email aux ADMIN_NOTIFY (fallback unifi@transversal.ht)
        admin_notify = getattr(settings, 'ADMIN_NOTIFY', '')
        to_emails = [e.strip() for e in admin_notify.split(',') if e.strip()]
        if not to_emails:
            to_emails = ['unifi@transversal.ht']

        try:
            html = build_auto_gen_html(site, tier_results, current_stock, date_label)
            result = send_email(
                to=to_emails,
                subject=f"[BonNet] ✅ Génération automatique — {site.name} ({total_created} vouchers)",
                html=html,
            )
            if result:
                notif.email_sent = True
                notif.save(update_fields=['email_sent'])
        except Exception as e:
            logger.error(f"Email auto-gen {site.name}: {e}")

    except Exception as e:
        logger.error(f"_auto_generate_vouchers_for_site({site.name}): {e}", exc_info=True)


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

        import calendar
        today = date.today()

        # Celery Beat déclenche jours 28-31 — on n'exécute que le dernier jour réel du mois
        last_day_of_month = calendar.monthrange(today.year, today.month)[1]
        if today.day != last_day_of_month:
            logger.info(f"send_monthly_reports: jour {today.day}/{last_day_of_month}, pas le dernier jour — ignoré.")
            return

        first_day_prev = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        last_day_prev = today.replace(day=1) - timedelta(days=1)
        date_from = first_day_prev.isoformat()
        date_to = last_day_prev.isoformat()
        month_label = f"{_MOIS_FR[first_day_prev.month]} {first_day_prev.year}"

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

        # Calcul des données pour le corps de l'email (cache hit — déjà chargé par Excel/PDF)
        sites_summary = []
        try:
            from .report_helper import _fetch_guests_per_site
            from collections import defaultdict
            from django.utils import timezone as tz
            by_site = _fetch_guests_per_site(sites, date_from, date_to)
            now_ts = tz.now().timestamp()
            for site in sites:
                guests = by_site.get(site.unifi_site_id, [])
                by_tier = defaultdict(lambda: {'count': 0, 'revenue': 0.0})
                for g in guests:
                    by_tier[g['tier_label']]['count'] += 1
                    by_tier[g['tier_label']]['revenue'] += g['price']
                sites_summary.append({
                    'site': site,
                    'sessions': len(guests),
                    'active': sum(1 for g in guests if g.get('end', 0) > now_ts),
                    'revenue': sum(g['price'] for g in guests),
                    'by_tier': [
                        {'tier_label': k, 'count': v['count'], 'revenue': v['revenue']}
                        for k, v in sorted(by_tier.items())
                    ],
                })
        except Exception as e:
            logger.error(f"sites_summary computation: {e}")
            sites_summary = [{'site': s, 'sessions': 0, 'active': 0, 'revenue': 0, 'by_tier': []} for s in sites]

        html = build_monthly_report_html(month_label, sites_summary, date_from, date_to)
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


def prewarm_cache():
    """Pré-charge les données UniFi de tous les sites dans le cache Redis."""
    try:
        from sites_mgmt.models import HotspotSite
        from unifi_api import client as unifi

        sites = list(HotspotSite.objects.filter(is_active=True))
        if not sites:
            return

        unifi.get_all_vouchers(sites)
        unifi.get_all_guests(sites)
        unifi.get_all_site_stats(sites)
        logger.info(f"Cache pre-warm OK — {len(sites)} sites")
    except Exception as e:
        logger.error(f"prewarm_cache error: {e}", exc_info=True)


def start():
    import os
    import threading
    from django.core.cache import cache
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.jobstores.memory import MemoryJobStore
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger

    # Un seul worker Gunicorn doit faire tourner le scheduler.
    # cache.add() est atomique : retourne True seulement si la clé n'existait pas.
    leader_key = 'apscheduler_leader'
    is_leader = cache.add(leader_key, os.getpid(), timeout=300)
    if not is_leader:
        logger.info("APScheduler: worker %s n'est pas leader, démarrage ignoré.", os.getpid())
        # Pre-warm immédiat quand même si le cache est froid au démarrage
        threading.Thread(target=prewarm_cache, daemon=True, name='prewarm-startup').start()
        return

    logger.info("APScheduler: worker %s élu leader.", os.getpid())

    # MemoryJobStore : zéro connexion DB, les jobs sont définis dans le code
    scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)
    scheduler.add_jobstore(MemoryJobStore(), 'default')

    scheduler.add_job(
        prewarm_cache,
        trigger=IntervalTrigger(minutes=2),
        id='prewarm_cache',
        name='Pré-chargement cache UniFi (toutes les 2 min)',
        replace_existing=True,
        misfire_grace_time=60,
    )

    scheduler.add_job(
        check_stock_levels,
        trigger=IntervalTrigger(hours=12),
        id='check_stock_levels',
        name='Vérification stock vouchers (toutes les 12h)',
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
    logger.info("APScheduler démarré (MemoryJobStore) — pre-warm/2min, stock/12h, rapport mensuel.")

    # Pre-warm immédiat au démarrage (cache froid après redéploiement)
    threading.Thread(target=prewarm_cache, daemon=True, name='prewarm-startup').start()
