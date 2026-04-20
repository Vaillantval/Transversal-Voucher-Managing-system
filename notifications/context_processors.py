from .models import Notification


def unread_notifications(request):
    if not request.user.is_authenticated:
        return {'unread_notifications_count': 0}

    qs = Notification.objects.filter(is_read=False)
    if not getattr(request.user, 'is_superadmin', False):
        site_ids = request.user.managed_sites.values_list('pk', flat=True)
        qs = qs.filter(site_id__in=site_ids)

    return {'unread_notifications_count': qs.count()}
