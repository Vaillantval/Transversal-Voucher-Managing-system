from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from django.http import JsonResponse


def health_check(request):
    return JsonResponse({"status": "ok"})


def unifi_debug(request):
    from django.conf import settings
    from unifi_api.client import _connect
    result = {
        "host": settings.UNIFI_HOST,
        "port": settings.UNIFI_PORT,
        "username": settings.UNIFI_USERNAME,
        "password_set": bool(settings.UNIFI_PASSWORD),
    }
    try:
        c = _connect()
        if c:
            sites = c.get_sites()
            result["connected"] = True
            result["sites_count"] = len(sites)
            result["sites"] = [s.get('desc', s.get('name')) for s in sites[:5]]
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
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('sites/', include('sites_mgmt.urls')),
    path('vouchers/', include('vouchers.urls')),
    path('reports/', include('reports.urls')),
    path('', RedirectView.as_view(url='/dashboard/', permanent=False)),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
