from collections import defaultdict

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST

from .models import Notification


def _group_by_site(qs):
    """Retourne une liste ordonnée de (site_label, site_obj_or_None, [notifs], unread_count)."""
    groups = defaultdict(list)
    site_objs = {}
    for n in qs:
        key = n.site_id or 0
        groups[key].append(n)
        if n.site and key not in site_objs:
            site_objs[key] = n.site

    result = []
    for site_id, notifs in sorted(groups.items(), key=lambda x: (
        x[0] == 0,
        site_objs.get(x[0], None) and site_objs[x[0]].name or '',
    )):
        site = site_objs.get(site_id)
        label = site.name if site else 'Général'
        unread_count = sum(1 for n in notifs if not n.is_read)
        result.append((label, site, notifs, unread_count))
    return result


@login_required
def notification_list(request):
    if getattr(request.user, 'is_superadmin', False):
        qs = Notification.objects.select_related('site').all()
    else:
        site_ids = request.user.managed_sites.values_list('pk', flat=True)
        qs = Notification.objects.select_related('site').filter(site_id__in=site_ids)

    type_filter = request.GET.get('type', '')
    if type_filter in (Notification.TYPE_STOCK_LOW, Notification.TYPE_MONTHLY_REPORT, Notification.TYPE_AUTO_GENERATED):
        qs = qs.filter(type=type_filter)

    read_filter = request.GET.get('read', '')
    if read_filter == '0':
        qs = qs.filter(is_read=False)
    elif read_filter == '1':
        qs = qs.filter(is_read=True)

    groups = _group_by_site(qs[:200])
    total  = sum(len(notifs) for _, _, notifs, _ in groups)
    unread = sum(u for _, _, _, u in groups)

    return render(request, 'notifications/list.html', {
        'groups':      groups,
        'total':       total,
        'unread':      unread,
        'type_filter': type_filter,
        'read_filter': read_filter,
        'page_title':  'Notifications',
    })


@login_required
@require_POST
def mark_read(request, pk):
    if getattr(request.user, 'is_superadmin', False):
        notif = get_object_or_404(Notification, pk=pk)
    else:
        site_ids = request.user.managed_sites.values_list('pk', flat=True)
        notif = get_object_or_404(Notification, pk=pk, site_id__in=site_ids)

    notif.is_read = True
    notif.save(update_fields=['is_read'])
    return JsonResponse({'ok': True})


@login_required
@require_POST
def mark_all_read(request):
    if getattr(request.user, 'is_superadmin', False):
        qs = Notification.objects.filter(is_read=False)
    else:
        site_ids = request.user.managed_sites.values_list('pk', flat=True)
        qs = Notification.objects.filter(is_read=False, site_id__in=site_ids)

    count = qs.update(is_read=True)
    return JsonResponse({'ok': True, 'marked': count})


@login_required
@require_POST
def delete_notification(request, pk):
    if getattr(request.user, 'is_superadmin', False):
        notif = get_object_or_404(Notification, pk=pk)
    else:
        site_ids = request.user.managed_sites.values_list('pk', flat=True)
        notif = get_object_or_404(Notification, pk=pk, site_id__in=site_ids)

    notif.delete()
    return JsonResponse({'ok': True})
