from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST

from .models import Notification


@login_required
def notification_list(request):
    if getattr(request.user, 'is_superadmin', False):
        qs = Notification.objects.select_related('site').all()
    else:
        site_ids = request.user.managed_sites.values_list('pk', flat=True)
        qs = Notification.objects.select_related('site').filter(site_id__in=site_ids)

    # Filtre type
    type_filter = request.GET.get('type', '')
    if type_filter in (Notification.TYPE_STOCK_LOW, Notification.TYPE_MONTHLY_REPORT, Notification.TYPE_AUTO_GENERATED):
        qs = qs.filter(type=type_filter)

    # Filtre lu/non-lu
    read_filter = request.GET.get('read', '')
    if read_filter == '0':
        qs = qs.filter(is_read=False)
    elif read_filter == '1':
        qs = qs.filter(is_read=True)

    notifications = qs[:100]

    return render(request, 'notifications/list.html', {
        'notifications': notifications,
        'type_filter': type_filter,
        'read_filter': read_filter,
        'page_title': 'Notifications',
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
