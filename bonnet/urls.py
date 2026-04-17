from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from django.http import JsonResponse


def health_check(request):
    return JsonResponse({"status": "ok"})


def debug_vouchers(request):
    from unifi_api.client import get_controller
    site_id = request.GET.get('site', 'ng3dxydx')
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


def unifi_debug(request):
    from django.conf import settings
    from unifi_api.client import _connect, get_sites
    from sites_mgmt.models import HotspotSite
    result = {
        "host": settings.UNIFI_HOST,
        "port": settings.UNIFI_PORT,
        "username": settings.UNIFI_USERNAME,
        "password_set": bool(settings.UNIFI_PASSWORD),
        "user": str(request.user),
        "is_authenticated": request.user.is_authenticated,
        "user_role": getattr(request.user, 'role', 'N/A'),
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
