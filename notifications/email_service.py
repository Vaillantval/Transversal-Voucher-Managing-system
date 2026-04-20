import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def send_email(to: list, subject: str, html: str, attachments: list = None):
    import resend
    resend.api_key = getattr(settings, 'RESEND_API_KEY', '')
    if not resend.api_key:
        logger.warning("RESEND_API_KEY non configuré — email non envoyé.")
        return None

    params = {
        "from": getattr(settings, 'RESEND_FROM_EMAIL', 'BonNet <noreply@bonnet.ht>'),
        "to": to,
        "subject": subject,
        "html": html,
    }
    if attachments:
        params["attachments"] = attachments

    try:
        return resend.Emails.send(params)
    except Exception as e:
        logger.error(f"Resend send_email failed: {e}")
        return None


def build_stock_alert_html(site, count: int) -> str:
    color = '#F59E0B' if count > 5 else '#EF4444'
    return f"""
    <div style="font-family:system-ui,sans-serif;max-width:560px;margin:0 auto">
      <div style="background:#111827;padding:20px 24px;border-radius:8px 8px 0 0">
        <h2 style="color:#fff;margin:0;font-size:1.2rem">
          Bon<span style="color:#1A56DB">Net</span>
          <span style="color:#9ca3af;font-weight:400;font-size:.9rem;margin-left:8px">Alerte stock</span>
        </h2>
      </div>
      <div style="background:#fff;padding:24px;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 8px 8px">
        <div style="background:{color}18;border-left:4px solid {color};padding:12px 16px;border-radius:4px;margin-bottom:20px">
          <strong style="color:{color}">⚠️ Stock faible détecté</strong>
        </div>
        <p style="margin:0 0 12px;color:#374151">
          Le site <strong>{site.name}</strong> ne dispose plus que de
          <strong style="color:{color};font-size:1.2em">{count}</strong> voucher(s) disponible(s).
        </p>
        <p style="margin:0 0 20px;color:#6b7280;font-size:.9rem">
          Veuillez créer de nouveaux vouchers pour éviter une interruption de service.
        </p>
        <a href="#"
           style="display:inline-block;background:#1A56DB;color:#fff;padding:10px 20px;
                  border-radius:6px;text-decoration:none;font-weight:600;font-size:.9rem">
          Créer des vouchers →
        </a>
        <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0 12px">
        <p style="margin:0;color:#9ca3af;font-size:.8rem">
          BonNet — Gestion vouchers WiFi · Transversal Haïti
        </p>
      </div>
    </div>
    """


def build_monthly_report_html(month_label: str, sites: list, date_from: str, date_to: str) -> str:
    sites_list_html = ''.join(
        f'<li style="color:#374151;margin:4px 0">{s.name}</li>' for s in sites
    )
    return f"""
    <div style="font-family:system-ui,sans-serif;max-width:560px;margin:0 auto">
      <div style="background:#111827;padding:20px 24px;border-radius:8px 8px 0 0">
        <h2 style="color:#fff;margin:0;font-size:1.2rem">
          Bon<span style="color:#1A56DB">Net</span>
          <span style="color:#9ca3af;font-weight:400;font-size:.9rem;margin-left:8px">Rapport mensuel</span>
        </h2>
      </div>
      <div style="background:#fff;padding:24px;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 8px 8px">
        <div style="background:#EFF6FF;border-left:4px solid #1A56DB;padding:12px 16px;border-radius:4px;margin-bottom:20px">
          <strong style="color:#1E40AF">📊 Rapport mensuel — {month_label}</strong>
        </div>
        <p style="margin:0 0 12px;color:#374151">
          Veuillez trouver ci-joint les rapports Excel pour la période
          <strong>{date_from}</strong> → <strong>{date_to}</strong>.
        </p>
        <p style="margin:0 0 8px;color:#374151;font-weight:600">Sites inclus :</p>
        <ul style="margin:0 0 20px;padding-left:20px">
          {sites_list_html}
        </ul>
        <hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0 12px">
        <p style="margin:0;color:#9ca3af;font-size:.8rem">
          BonNet — Gestion vouchers WiFi · Transversal Haïti
        </p>
      </div>
    </div>
    """
