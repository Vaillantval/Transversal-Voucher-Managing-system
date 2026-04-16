from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Sum, Count
from datetime import date, timedelta
import csv, io

from sites_mgmt.models import HotspotSite
from vouchers.models import VoucherLog


def get_queryset(request, site_id=None, date_from=None, date_to=None):
    if request.user.is_superadmin:
        qs = VoucherLog.objects.select_related('site', 'tier', 'created_by')
    else:
        qs = VoucherLog.objects.filter(
            site__in=request.user.managed_sites.all()
        ).select_related('site', 'tier', 'created_by')

    if site_id:
        qs = qs.filter(site__unifi_site_id=site_id)
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)
    return qs


@login_required
def report_index(request):
    today = date.today()
    sites = HotspotSite.objects.filter(is_active=True) if request.user.is_superadmin \
        else request.user.managed_sites.filter(is_active=True)
    return render(request, 'reports/index.html', {
        'sites': sites,
        'today': today,
        'page_title': 'Rapports & Exports',
    })


# ─── CSV ──────────────────────────────────────────────────────────────────────

@login_required
def export_csv(request):
    site_id = request.GET.get('site', '')
    date_from = request.GET.get('from', (date.today() - timedelta(days=30)).isoformat())
    date_to = request.GET.get('to', date.today().isoformat())

    qs = get_queryset(request, site_id or None, date_from, date_to)

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    filename = f"bonnet_vouchers_{date_from}_{date_to}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow([
        'Code', 'Site', 'Tranche', 'Durée (min)', 'Prix (HTG)',
        'Statut', 'Créé par', 'Date création',
    ])
    for v in qs:
        writer.writerow([
            v.code,
            v.site.name,
            v.tier.label if v.tier else '-',
            v.duration_minutes,
            v.price_htg or '-',
            v.get_status_display(),
            v.created_by.get_full_name() if v.created_by else '-',
            v.created_at.strftime('%Y-%m-%d %H:%M'),
        ])
    return response


# ─── EXCEL ────────────────────────────────────────────────────────────────────

@login_required
def export_excel(request):
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter

    site_id = request.GET.get('site', '')
    date_from = request.GET.get('from', (date.today() - timedelta(days=30)).isoformat())
    date_to = request.GET.get('to', date.today().isoformat())

    qs = get_queryset(request, site_id or None, date_from, date_to)

    wb = openpyxl.Workbook()

    # ── Feuille 1 : Détail vouchers ──
    ws = wb.active
    ws.title = "Vouchers"

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="1A56DB")
    headers = ['Code', 'Site', 'Tranche', 'Durée (h)', 'Prix (HTG)', 'Statut', 'Créé par', 'Date']

    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')

    for row_idx, v in enumerate(qs, 2):
        ws.cell(row=row_idx, column=1, value=v.code)
        ws.cell(row=row_idx, column=2, value=v.site.name)
        ws.cell(row=row_idx, column=3, value=v.tier.label if v.tier else '-')
        ws.cell(row=row_idx, column=4, value=round(v.duration_minutes / 60, 1))
        ws.cell(row=row_idx, column=5, value=float(v.price_htg) if v.price_htg else 0)
        ws.cell(row=row_idx, column=6, value=v.get_status_display())
        ws.cell(row=row_idx, column=7, value=v.created_by.get_full_name() if v.created_by else '-')
        ws.cell(row=row_idx, column=8, value=v.created_at.strftime('%Y-%m-%d %H:%M'))

    # Largeur auto
    for col in range(1, 9):
        ws.column_dimensions[get_column_letter(col)].width = 18

    # ── Feuille 2 : Résumé par site ──
    ws2 = wb.create_sheet("Résumé par site")
    summary = list(
        qs.filter(status=VoucherLog.STATUS_USED)
        .values('site__name')
        .annotate(total=Sum('price_htg'), count=Count('id'))
        .order_by('-total')
    )

    ws2.cell(1, 1, 'Site').font = Font(bold=True)
    ws2.cell(1, 2, 'Vouchers utilisés').font = Font(bold=True)
    ws2.cell(1, 3, 'Revenu (HTG)').font = Font(bold=True)

    for i, row in enumerate(summary, 2):
        ws2.cell(i, 1, row['site__name'])
        ws2.cell(i, 2, row['count'])
        ws2.cell(i, 3, float(row['total'] or 0))

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f"bonnet_rapport_{date_from}_{date_to}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


# ─── PDF ─────────────────────────────────────────────────────────────────────

@login_required
def export_pdf(request):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.enums import TA_CENTER

    site_id = request.GET.get('site', '')
    date_from = request.GET.get('from', (date.today() - timedelta(days=30)).isoformat())
    date_to = request.GET.get('to', date.today().isoformat())

    qs = get_queryset(request, site_id or None, date_from, date_to)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                            rightMargin=1*cm, leftMargin=1*cm,
                            topMargin=1.5*cm, bottomMargin=1*cm)

    styles = getSampleStyleSheet()
    elements = []

    # Titre
    title_style = ParagraphStyle('title', parent=styles['Title'],
                                 textColor=colors.HexColor('#1A56DB'), fontSize=18)
    elements.append(Paragraph("BonNet — Rapport Vouchers", title_style))
    elements.append(Paragraph(f"Période : {date_from} → {date_to}", styles['Normal']))
    elements.append(Spacer(1, 0.5*cm))

    # KPIs
    used = qs.filter(status=VoucherLog.STATUS_USED)
    total_rev = used.aggregate(t=Sum('price_htg'))['t'] or 0
    kpi_data = [
        ['Total vouchers', 'Utilisés', 'Actifs', 'Revenu total (HTG)'],
        [qs.count(), used.count(),
         qs.filter(status=VoucherLog.STATUS_ACTIVE).count(),
         f"{total_rev:,.2f}"],
    ]
    kpi_table = Table(kpi_data, colWidths=[6*cm]*4)
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1A56DB')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#EBF5FF'), colors.white]),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(kpi_table)
    elements.append(Spacer(1, 0.5*cm))

    # Tableau détail (max 500 lignes)
    data = [['Code', 'Site', 'Tranche', 'Durée', 'Prix HTG', 'Statut', 'Date']]
    for v in qs[:500]:
        data.append([
            v.code,
            v.site.name[:20],
            (v.tier.label[:15] if v.tier else '-'),
            f"{v.duration_hours}h",
            str(v.price_htg or '-'),
            v.get_status_display(),
            v.created_at.strftime('%d/%m/%Y'),
        ])

    table = Table(data, colWidths=[3*cm, 4*cm, 4*cm, 2*cm, 2.5*cm, 2.5*cm, 2.5*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1A56DB')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#F9FAFB'), colors.white]),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
    ]))
    elements.append(table)

    doc.build(elements)
    buffer.seek(0)

    response = HttpResponse(buffer, content_type='application/pdf')
    filename = f"bonnet_rapport_{date_from}_{date_to}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
