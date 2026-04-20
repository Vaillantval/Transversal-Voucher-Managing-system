def site_config(request):
    try:
        from .models import SiteConfig
        return {'site_config': SiteConfig.get()}
    except Exception:
        return {'site_config': None}
