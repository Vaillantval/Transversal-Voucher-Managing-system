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


def build_auto_gen_html(site, tier_results: list, stock_count: int, date_label: str) -> str:
    rows_html = ''.join(
        f"""<tr>
          <td style="padding:8px 12px;border-bottom:1px solid #e5e7eb">{r['tier'].label}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;text-align:center">
            {'<span style="color:#10b981;font-weight:600">' + str(r['count']) + '</span>'
             if r['success'] else '<span style="color:#ef4444">Échec</span>'}
          </td>
        </tr>"""
        for r in tier_results
    )
    total = sum(r['count'] for r in tier_results)
    return f"""
    <div style="font-family:system-ui,sans-serif;max-width:560px;margin:0 auto">
      <div style="background:#111827;padding:20px 24px;border-radius:8px 8px 0 0">
        <h2 style="color:#fff;margin:0;font-size:1.2rem">
          Bon<span style="color:#1A56DB">Net</span>
          <span style="color:#9ca3af;font-weight:400;font-size:.9rem;margin-left:8px">Génération automatique</span>
        </h2>
      </div>
      <div style="background:#fff;padding:24px;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 8px 8px">
        <div style="background:#f0fdf4;border-left:4px solid #10b981;padding:12px 16px;border-radius:4px;margin-bottom:20px">
          <strong style="color:#065f46">✅ Vouchers générés automatiquement</strong>
        </div>
        <p style="margin:0 0 4px;color:#374151">
          Site : <strong>{site.name}</strong>
        </p>
        <p style="margin:0 0 16px;color:#6b7280;font-size:.9rem">
          Stock détecté : <strong>{stock_count}</strong> voucher(s) — aucune action de l'admin après le délai configuré.
        </p>
        <table style="width:100%;border-collapse:collapse;margin-bottom:20px">
          <thead>
            <tr style="background:#f9fafb">
              <th style="padding:8px 12px;text-align:left;border-bottom:2px solid #e5e7eb;font-size:.85rem;color:#6b7280">FORFAIT</th>
              <th style="padding:8px 12px;text-align:center;border-bottom:2px solid #e5e7eb;font-size:.85rem;color:#6b7280">CRÉÉS</th>
            </tr>
          </thead>
          <tbody>{rows_html}</tbody>
          <tfoot>
            <tr style="background:#f9fafb">
              <td style="padding:8px 12px;font-weight:700">Total</td>
              <td style="padding:8px 12px;text-align:center;font-weight:700;color:#10b981">{total}</td>
            </tr>
          </tfoot>
        </table>
        <hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0 12px">
        <p style="margin:0;color:#9ca3af;font-size:.8rem">
          BonNet — Gestion vouchers WiFi · Transversal Haïti · {date_label}
        </p>
      </div>
    </div>
    """


def build_monthly_report_html(month_label: str, sites_summary: list, date_from: str, date_to: str) -> str:
    """
    sites_summary : liste de dicts
        {'site': HotspotSite, 'sessions': int, 'active': int, 'revenue': float,
         'by_tier': [{'tier_label': str, 'count': int, 'revenue': float}, ...]}
    """
    TH  = 'padding:8px 12px;border-bottom:2px solid #e5e7eb;font-size:.8rem;color:#6b7280;text-align:center'
    TH_L = TH.replace('text-align:center', 'text-align:left')
    TD  = 'padding:7px 12px;border-bottom:1px solid #f3f4f6;font-size:.85rem;text-align:center'
    TD_L = TD.replace('text-align:center', 'text-align:left')
    TD_B = TD + ';font-weight:700'
    TD_BL = TD_L + ';font-weight:700'

    grand_sessions = sum(s['sessions'] for s in sites_summary)
    grand_revenue  = sum(s['revenue']  for s in sites_summary)
    multi_site     = len(sites_summary) > 1

    # ── Tableau récapitulatif global (uniquement multi-sites) ─────────────────
    if multi_site:
        recap_rows = f"""
        <tr style="background:#eff6ff">
          <td style="{TD_BL}">TOTAL — {len(sites_summary)} sites</td>
          <td style="{TD_B}">{grand_sessions}</td>
          <td style="{TD_B}">—</td>
          <td style="{TD_B}">{grand_revenue:,.2f} HTG</td>
        </tr>"""
        for i, s in enumerate(sites_summary):
            bg = 'background:#f8faff' if i % 2 == 0 else ''
            recap_rows += f"""
            <tr style="{bg}">
              <td style="{TD_L}">{s['site'].name}</td>
              <td style="{TD}">{s['sessions']}</td>
              <td style="{TD}">{s['active']}</td>
              <td style="{TD}">{s['revenue']:,.2f} HTG</td>
            </tr>"""
        recap_table = f"""
        <p style="margin:0 0 10px;font-weight:700;color:#111827">Récapitulatif global</p>
        <table style="width:100%;border-collapse:collapse;margin-bottom:28px">
          <thead><tr style="background:#1e40af">
            <th style="{TH_L};color:#fff;border:none">Site</th>
            <th style="{TH};color:#fff;border:none">Sessions vendues</th>
            <th style="{TH};color:#fff;border:none">Sessions actives</th>
            <th style="{TH};color:#fff;border:none">Revenu total</th>
          </tr></thead>
          <tbody>{recap_rows}</tbody>
        </table>"""
    else:
        recap_table = ''

    # ── Détail par site ────────────────────────────────────────────────────────
    site_sections = ''
    for s in sites_summary:
        if not s['by_tier']:
            tier_rows = f'<tr><td colspan="3" style="{TD};color:#9ca3af">Aucune session sur cette période.</td></tr>'
        else:
            tier_rows = ''
            for j, t in enumerate(s['by_tier']):
                bg = 'background:#f8faff' if j % 2 == 0 else ''
                tier_rows += f"""
                <tr style="{bg}">
                  <td style="{TD_L}">{t['tier_label']}</td>
                  <td style="{TD}">{t['count']}</td>
                  <td style="{TD}">{t['revenue']:,.2f} HTG</td>
                </tr>"""
            site_rev = s['revenue']
            tier_rows += f"""
            <tr style="background:#eff6ff">
              <td style="{TD_BL}">Total {s['site'].name}</td>
              <td style="{TD_B}">{s['sessions']}</td>
              <td style="{TD_B}">{site_rev:,.2f} HTG</td>
            </tr>"""

        site_sections += f"""
        <div style="margin-bottom:24px">
          <p style="margin:0 0 6px;font-weight:700;color:#1e40af;font-size:.95rem">
            {s['site'].name}
          </p>
          <table style="width:100%;border-collapse:collapse">
            <thead><tr style="background:#1e40af">
              <th style="{TH_L};color:#fff;border:none">Forfait</th>
              <th style="{TH};color:#fff;border:none">Sessions</th>
              <th style="{TH};color:#fff;border:none">Revenu</th>
            </tr></thead>
            <tbody>{tier_rows}</tbody>
          </table>
        </div>"""

    return f"""
    <div style="font-family:system-ui,sans-serif;max-width:620px;margin:0 auto">
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
        <p style="margin:0 0 20px;color:#6b7280;font-size:.9rem">
          Période : <strong style="color:#374151">{date_from}</strong> → <strong style="color:#374151">{date_to}</strong>
          &nbsp;·&nbsp; Les fichiers Excel et PDF complets sont joints à cet email.
        </p>

        {recap_table}

        <p style="margin:0 0 14px;font-weight:700;color:#111827">{'Détail par site' if multi_site else 'Détail des ventes'}</p>
        {site_sections}

        <hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0 12px">
        <p style="margin:0;color:#9ca3af;font-size:.8rem">
          BonNet — Gestion vouchers WiFi · Transversal Haïti
        </p>
      </div>
    </div>
    """
