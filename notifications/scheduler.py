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
    """Vérifie le stock par forfait standard de chaque site, alerte si un forfait a < 30 vouchers."""
    try:
        from sites_mgmt.models import HotspotSite, VoucherTier
        from sites_mgmt.utils import find_tier
        from unifi_api import client as unifi
        from .models import Notification, AutoGenConfig

        sites = list(HotspotSite.objects.filter(is_active=True))
        if not sites:
            return

        all_vouchers = unifi.get_all_vouchers(sites)
        all_guests   = unifi.get_all_guests(sites)
        all_stats    = unifi.get_all_site_stats(sites)

        # Sessions actives dans les 2 dernières semaines par site
        two_weeks_ago = (timezone.now() - timedelta(weeks=2)).timestamp()
        active_sites: set[str] = set()
        for g in all_guests:
            if g.get('sold_ts', 0) >= two_weeks_ago:
                active_sites.add(g.get('site_unifi_id', ''))

        # Tiers standard par site (M2M) — exclut remplacement et admin
        std_tiers_qs = VoucherTier.objects.filter(
            is_active=True, is_replacement=False, is_admin_code=False,
        ).prefetch_related('sites')
        from collections import defaultdict as _dd
        std_tiers_by_site: dict[int, list] = _dd(list)
        for t in std_tiers_qs:
            for s in t.sites.all():
                std_tiers_by_site[s.pk].append(t)

        # Compter les vouchers disponibles par (site_unifi_id, duration_minutes)
        avail_by_site_dur: dict[tuple, int] = _dd(int)
        for v in all_vouchers:
            if v.get('is_available'):
                sid = v.get('site_unifi_id', '')
                dur = v.get('duration', 0)
                avail_by_site_dur[(sid, dur)] += 1

        autogen = AutoGenConfig.get()
        autogen_site_ids = set(autogen.sites.values_list('unifi_site_id', flat=True)) if autogen.enabled else set()

        # Lancer la génération admin (indépendante du stock standard)
        if autogen.enabled:
            _auto_generate_admin_vouchers(sites, autogen)

        notify_on = autogen.notify_site_admin

        for site in sites:
            # Site doit avoir au moins 1 device ET des sessions récentes
            stats = all_stats.get(site.unifi_site_id, {})
            if stats.get('device_total', 0) == 0:
                continue
            if site.unifi_site_id not in active_sites:
                continue

            site_std_tiers = std_tiers_by_site.get(site.pk, [])
            if not site_std_tiers:
                continue

            for tier in site_std_tiers:
                count = avail_by_site_dur.get((site.unifi_site_id, tier.duration_minutes), 0)
                if count >= STOCK_ALERT_THRESHOLD:
                    continue

                can_autogen = autogen.enabled and site.unifi_site_id in autogen_site_ids

                # ── Cas : AutoGen ON + Notif OFF → génération immédiate ────────
                if can_autogen and not notify_on:
                    cutoff = timezone.now() - timedelta(hours=STOCK_ALERT_COOLDOWN_HOURS)
                    already_generated = Notification.objects.filter(
                        type=Notification.TYPE_AUTO_GENERATED,
                        site=site,
                        title__contains=tier.label,
                        created_at__gte=cutoff,
                    ).exists()
                    if not already_generated:
                        logger.info(f"Auto-gen immédiate {site.name} / {tier.label} (stock={count})")
                        _auto_generate_vouchers_for_tier(site, tier, count, autogen.count_per_tier)
                    continue

                # ── Cas : Notif ON (avec ou sans AutoGen) ─────────────────────
                cutoff = timezone.now() - timedelta(hours=STOCK_ALERT_COOLDOWN_HOURS)
                already = Notification.objects.filter(
                    type=Notification.TYPE_STOCK_LOW,
                    site=site,
                    title__contains=tier.label,
                    created_at__gte=cutoff,
                ).exists()

                if already:
                    # 2ème détection : générer seulement si AutoGen ON
                    if can_autogen:
                        trigger_cutoff = timezone.now() - timedelta(hours=autogen.delay_hours)
                        pending_alert = Notification.objects.filter(
                            type=Notification.TYPE_STOCK_LOW,
                            site=site,
                            title__contains=tier.label,
                            created_at__lte=trigger_cutoff,
                            auto_gen_triggered=False,
                        ).first()
                        if pending_alert:
                            logger.info(f"Auto-gen std {site.name} / {tier.label} (stock={count})")
                            pending_alert.delete()
                            _auto_generate_vouchers_for_tier(site, tier, count, autogen.count_per_tier)
                    continue

                # 1ère détection : créer notif + email
                notif = Notification.objects.create(
                    type=Notification.TYPE_STOCK_LOW,
                    site=site,
                    title=f"Stock faible — {site.name} / {tier.label}",
                    message=(
                        f"Le forfait « {tier.label} » sur {site.name} "
                        f"n'a plus que {count} voucher(s) disponible(s)."
                    ),
                    stock_count=count,
                )
                logger.info(f"Stock alert : {site.name} / {tier.label} ({count} vouchers)")

                try:
                    from .email_service import send_email, build_stock_alert_html
                    admin_emails = list(
                        site.admins.filter(email__isnull=False, role='site_admin')
                        .exclude(email='')
                        .values_list('email', flat=True)
                    )
                    if admin_emails:
                        html = build_stock_alert_html(site, count)
                        result = send_email(
                            to=admin_emails,
                            subject=f"[BonNet] ⚠️ Stock faible — {site.name} / {tier.label} ({count} restant(s))",
                            html=html,
                        )
                        if result:
                            notif.email_sent = True
                            notif.save(update_fields=['email_sent'])
                except Exception as e:
                    logger.error(f"Email stock alert {site.name}/{tier.label}: {e}")

        _cleanup_old_notifications()

    except Exception as e:
        logger.error(f"check_stock_levels error: {e}", exc_info=True)


def _auto_generate_vouchers_for_tier(site, tier, current_stock: int, count_per_tier: int = 100):
    """Génère count_per_tier vouchers pour un forfait standard donné sur un site."""
    try:
        from vouchers.models import VoucherLog
        from unifi_api import client as unifi
        from .models import Notification
        from .email_service import send_email, build_auto_gen_html

        now = timezone.now()
        date_label = f"{now.day} {_MOIS_FR[now.month]} {now.year}"
        note = f"{tier.label}_{site.name}_{date_label}"

        created = unifi.create_vouchers(
            site_id=site.unifi_site_id,
            expire_minutes=tier.duration_minutes,
            count=count_per_tier,
            quota=1,
            note=note,
        )
        if not created:
            logger.error(f"Auto-gen std {site.name} / {tier.label}: échec UniFi.")
            return

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
                        'duration_minutes': v.get('duration', tier.duration_minutes),
                        'quota': v.get('quota', 1),
                        'note': note,
                        'price_htg': tier.price_htg,
                    }
                )
                if is_new:
                    synced += 1

        logger.info(f"Auto-gen std {site.name} / {tier.label}: {synced} vouchers créés.")

        tier_results = [{'tier': tier, 'count': synced, 'success': True}]
        notif = Notification.objects.create(
            type=Notification.TYPE_AUTO_GENERATED,
            site=site,
            title=f"Génération automatique — {site.name} / {tier.label}",
            message=f"{synced} voucher(s) générés pour le forfait « {tier.label} » sur {site.name}.",
            stock_count=current_stock,
        )

        admin_notify = getattr(settings, 'ADMIN_NOTIFY', '')
        to_emails = [e.strip() for e in admin_notify.split(',') if e.strip()] or ['unifi@transversal.ht']
        try:
            html = build_auto_gen_html(site, tier_results, current_stock, date_label)
            result = send_email(
                to=to_emails,
                subject=f"[BonNet] ✅ Auto-gen — {site.name} / {tier.label} ({synced} vouchers)",
                html=html,
            )
            if result:
                notif.email_sent = True
                notif.save(update_fields=['email_sent'])
        except Exception as e:
            logger.error(f"Email auto-gen std {site.name}/{tier.label}: {e}")

    except Exception as e:
        logger.error(f"_auto_generate_vouchers_for_tier({site.name}, {tier.label}): {e}", exc_info=True)


def _auto_generate_admin_vouchers(sites: list, autogen):
    """Génère des vouchers admin quand la date d'expiration est atteinte (ou absente)."""
    try:
        from sites_mgmt.models import VoucherTier
        from vouchers.models import VoucherLog
        from unifi_api import client as unifi
        from .models import AdminVoucherGenLog, Notification
        from .email_service import send_email, build_auto_gen_html

        today = date.today()
        now = timezone.now()
        date_label = f"{now.day} {_MOIS_FR[now.month]} {now.year}"

        admin_tiers_qs = VoucherTier.objects.filter(
            is_active=True, is_admin_code=True,
        ).prefetch_related('sites')

        from collections import defaultdict as _dd
        admin_tiers_by_site: dict[int, list] = _dd(list)
        for t in admin_tiers_qs:
            for s in t.sites.all():
                admin_tiers_by_site[s.pk].append(t)

        for site in sites:
            admin_tiers = admin_tiers_by_site.get(site.pk, [])
            for tier in admin_tiers:
                try:
                    log = AdminVoucherGenLog.objects.get(site=site, tier=tier)
                    if today < log.expires_at:
                        continue  # Pas encore expiré
                except AdminVoucherGenLog.DoesNotExist:
                    log = None

                # Générer les vouchers admin (max_vouchers par tier)
                count = tier.max_vouchers
                note = f"BonNet-{tier.label}"
                created = unifi.create_vouchers(
                    site_id=site.unifi_site_id,
                    expire_minutes=tier.duration_minutes,
                    count=count,
                    quota=1,
                    note=note,
                )
                if not created:
                    logger.error(f"Auto-gen admin {site.name} / {tier.label}: échec UniFi.")
                    continue

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
                                'duration_minutes': v.get('duration', tier.duration_minutes),
                                'quota': v.get('quota', 1),
                                'note': note,
                                'price_htg': 0,
                            }
                        )
                        if is_new:
                            synced += 1

                # Calculer expires_at = aujourd'hui + durée du tier
                import math
                duration_days = math.ceil(tier.duration_minutes / 1440)
                new_expires_at = today + timedelta(days=duration_days)

                AdminVoucherGenLog.objects.update_or_create(
                    site=site, tier=tier,
                    defaults={'expires_at': new_expires_at},
                )

                logger.info(f"Auto-gen admin {site.name} / {tier.label}: {synced} vouchers, expire {new_expires_at}.")

                tier_results = [{'tier': tier, 'count': synced, 'success': True}]
                notif = Notification.objects.create(
                    type=Notification.TYPE_AUTO_GENERATED,
                    site=site,
                    title=f"Génération admin — {site.name} / {tier.label}",
                    message=(
                        f"{synced} voucher(s) admin générés pour « {tier.label} » sur {site.name}. "
                        f"Prochaine génération après le {new_expires_at.strftime('%d/%m/%Y')}."
                    ),
                    stock_count=synced,
                )

                admin_notify = getattr(settings, 'ADMIN_NOTIFY', '')
                to_emails = [e.strip() for e in admin_notify.split(',') if e.strip()] or ['unifi@transversal.ht']
                try:
                    html = build_auto_gen_html(site, tier_results, 0, date_label)
                    result = send_email(
                        to=to_emails,
                        subject=f"[BonNet] ✅ Auto-gen admin — {site.name} / {tier.label} ({synced} vouchers)",
                        html=html,
                    )
                    if result:
                        notif.email_sent = True
                        notif.save(update_fields=['email_sent'])
                except Exception as e:
                    logger.error(f"Email auto-gen admin {site.name}/{tier.label}: {e}")

    except Exception as e:
        logger.error(f"_auto_generate_admin_vouchers: {e}", exc_info=True)


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


def _cleanup_old_notifications():
    """
    Supprime automatiquement les notifications obsolètes :
    - Lues depuis plus de 7 jours (basé sur created_at comme proxy)
    - auto_generated lues depuis plus de 7 jours
    - monthly_report lues depuis plus de 30 jours
    """
    try:
        from .models import Notification
        cutoff_7  = timezone.now() - timedelta(days=7)
        cutoff_30 = timezone.now() - timedelta(days=30)

        deleted, _ = Notification.objects.filter(
            is_read=True,
            type__in=[Notification.TYPE_STOCK_LOW, Notification.TYPE_AUTO_GENERATED],
            created_at__lt=cutoff_7,
        ).delete()

        deleted_r, _ = Notification.objects.filter(
            is_read=True,
            type=Notification.TYPE_MONTHLY_REPORT,
            created_at__lt=cutoff_30,
        ).delete()

        if deleted or deleted_r:
            logger.info(f"Cleanup notifications: {deleted + deleted_r} supprimée(s)")
    except Exception as e:
        logger.error(f"_cleanup_old_notifications: {e}")


def send_weekly_store_report():
    """Envoie chaque lundi à 8h le rapport PDF des ventes store de la semaine écoulée."""
    try:
        from collections import defaultdict
        from .email_service import send_email, build_weekly_store_report_html
        from .report_helper import generate_store_weekly_pdf_bytes
        from store.models import Order
        from sites_mgmt.utils import TZ_HAITI

        admin_notify = getattr(settings, 'ADMIN_NOTIFY', '')
        to_emails = [e.strip() for e in admin_notify.split(',') if e.strip()]
        if not to_emails:
            logger.warning("ADMIN_NOTIFY non configuré — rapport hebdo non envoyé.")
            return

        today      = date.today()
        date_to    = today - timedelta(days=1)          # hier (dimanche)
        date_from  = date_to - timedelta(days=6)        # lundi précédent
        date_from_s = date_from.isoformat()
        date_to_s   = date_to.isoformat()

        from django.utils import timezone as tz
        from sites_mgmt.utils import TZ_HAITI
        import datetime as _dt
        dt_from = _dt.datetime.combine(date_from, _dt.time.min).replace(tzinfo=TZ_HAITI)
        dt_to   = _dt.datetime.combine(date_to,   _dt.time.max).replace(tzinfo=TZ_HAITI)

        orders = list(
            Order.objects.filter(
                created_at__gte=dt_from,
                created_at__lte=dt_to,
                status=Order.STATUS_DELIVERED,
            ).prefetch_related('items__tier', 'items__site')
        )

        total_revenue = float(sum(o.total_htg for o in orders))
        by_site = defaultdict(lambda: {'count': 0, 'revenue': 0.0})
        by_tier = defaultdict(lambda: {'count': 0, 'revenue': 0.0})
        for o in orders:
            for item in o.items.all():
                sname  = item.site.name  if item.site  else '—'
                tlabel = item.tier.label if item.tier  else '—'
                qty    = item.quantity
                rev    = float(item.unit_price) * qty
                by_site[sname]['count']   += qty
                by_site[sname]['revenue'] += rev
                by_tier[tlabel]['count']  += qty
                by_tier[tlabel]['revenue']+= rev

        attachments = []
        try:
            pdf_bytes = generate_store_weekly_pdf_bytes(date_from_s, date_to_s)
            attachments.append({
                "filename": f"bonnet_ventes_{date_from_s}_{date_to_s}.pdf",
                "content":  list(pdf_bytes),
            })
        except Exception as e:
            logger.error(f"Weekly PDF generation: {e}")

        html = build_weekly_store_report_html(
            date_from_s, date_to_s,
            n_orders=len(orders),
            total_revenue=total_revenue,
            by_site=dict(by_site),
            by_tier=dict(by_tier),
        )
        send_email(
            to=to_emails,
            subject=f"[BonNet] Rapport hebdo ventes — {date_from_s} → {date_to_s}",
            html=html,
            attachments=attachments or None,
        )
        logger.info(f"Rapport hebdo store envoyé : {len(orders)} commandes, {total_revenue:.2f} HTG")

    except Exception as e:
        logger.error(f"send_weekly_store_report error: {e}", exc_info=True)


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

    scheduler.add_job(
        send_weekly_store_report,
        trigger=CronTrigger(day_of_week='mon', hour=8, minute=0, timezone=settings.TIME_ZONE),
        id='send_weekly_store_report',
        name='Rapport hebdo ventes store (lundi 8h)',
        replace_existing=True,
        misfire_grace_time=3600,
    )

    scheduler.start()
    logger.info("APScheduler démarré (MemoryJobStore) — pre-warm/2min, stock/12h, rapport mensuel.")

    # Pre-warm immédiat au démarrage (cache froid après redéploiement)
    threading.Thread(target=prewarm_cache, daemon=True, name='prewarm-startup').start()
