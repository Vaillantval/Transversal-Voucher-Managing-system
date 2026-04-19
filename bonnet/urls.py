from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required


def health_check(request):
    return JsonResponse({"status": "ok"})


@login_required
def debug_vouchers(request):
    if not getattr(request.user, 'is_superadmin', False):
        return HttpResponseForbidden('Accès réservé aux super-admins.')
    from unifi_api.client import get_controller
    from sites_mgmt.models import HotspotSite
    site_id = request.GET.get('site') or (
        HotspotSite.objects.filter(is_active=True).values_list('unifi_site_id', flat=True).first() or ''
    )
    result = {"site_id": site_id}
    try:
        c = get_controller(site_id)
        if c:
            vouchers = c.list_vouchers()
            result["voucher_count"] = len(vouchers)
            result["sample"] = vouchers[:2] if vouchers else []
        else:
            result["error"] = "controller is None"
    except Exception as e:
        result["error"] = str(e)
    return JsonResponse(result)


@login_required
def unifi_debug(request):
    if not getattr(request.user, 'is_superadmin', False):
        return HttpResponseForbidden('Accès réservé aux super-admins.')
    from unifi_api.client import _connect
    from sites_mgmt.models import HotspotSite
    result = {
        "host": settings.UNIFI_HOST,
        "port": settings.UNIFI_PORT,
        "username": settings.UNIFI_USERNAME,
        "password_set": bool(settings.UNIFI_PASSWORD),
        "user": str(request.user),
        "is_superadmin": getattr(request.user, 'is_superadmin', False),
        "db_sites_count": HotspotSite.objects.count(),
    }
    try:
        c = _connect()
        if c:
            sites = c.get_sites()
            result["connected"] = True
            result["unifi_sites_count"] = len(sites)
        else:
            result["connected"] = False
            result["error"] = "controller is None"
    except Exception as e:
        result["connected"] = False
        result["error"] = str(e)
    return JsonResponse(result)


urlpatterns = [
    path('health/', health_check),
    path('debug/unifi/', unifi_debug),
    path('debug/vouchers/', debug_vouchers),
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('sites/', include('sites_mgmt.urls')),
    path('vouchers/', include('vouchers.urls')),
    path('reports/', include('reports.urls')),
    path('', RedirectView.as_view(url='/dashboard/', permanent=False)),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
