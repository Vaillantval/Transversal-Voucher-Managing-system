from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.conf import settings

from notifications.email_service import send_email, build_monthly_report_html
from notifications.report_helper import generate_excel_bytes, generate_pdf_bytes
from notifications.models import Notification
from sites_mgmt.models import HotspotSite


class Command(BaseCommand):
    help = "Envoie immédiatement le rapport pour les N derniers jours (défaut: 30)"

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=30,
                            help='Nombre de jours à couvrir (défaut: 30)')

    def handle(self, *args, **options):
        days = options['days']
        today = date.today()
        date_to   = today.isoformat()
        date_from = (today - timedelta(days=days)).isoformat()
        label     = f"Derniers {days} jours ({date_from} → {date_to})"

        admin_notify = getattr(settings, 'ADMIN_NOTIFY', '')
        to_emails = [e.strip() for e in admin_notify.split(',') if e.strip()]
        if not to_emails:
            self.stderr.write("ADMIN_NOTIFY non configuré — abandon.")
            return

        sites = list(HotspotSite.objects.filter(is_active=True))
        if not sites:
            self.stderr.write("Aucun site actif trouvé.")
            return

        self.stdout.write(f"Génération rapport pour {len(sites)} site(s)…")

        attachments = []

        try:
            excel = generate_excel_bytes(sites=sites, date_from=date_from, date_to=date_to)
            attachments.append({
                "filename": f"bonnet_rapport_{date_from}_{date_to}.xlsx",
                "content": list(excel),
            })
            self.stdout.write("  ✓ Excel généré")
        except Exception as e:
            self.stderr.write(f"  ✗ Excel : {e}")

        try:
            pdf = generate_pdf_bytes(sites=sites, date_from=date_from, date_to=date_to)
            attachments.append({
                "filename": f"bonnet_rapport_{date_from}_{date_to}.pdf",
                "content": list(pdf),
            })
            self.stdout.write("  ✓ PDF généré")
        except Exception as e:
            self.stderr.write(f"  ✗ PDF : {e}")

        html   = build_monthly_report_html(label, sites, date_from, date_to)
        result = send_email(
            to=to_emails,
            subject=f"[BonNet] Rapport — {label}",
            html=html,
            attachments=attachments or None,
        )

        if result:
            Notification.objects.create(
                type=Notification.TYPE_MONTHLY_REPORT,
                title=f"Rapport envoyé — {label}",
                message=f"Rapport envoyé à : {', '.join(to_emails)}",
                email_sent=True,
            )
            self.stdout.write(self.style.SUCCESS(f"Email envoyé à : {', '.join(to_emails)}"))
        else:
            self.stderr.write("Échec envoi email (vérifier RESEND_API_KEY).")
