"""
Middleware de rate limiting BonNet.

Stocké dans Redis — appliqué globalement par préfixe d'URL.
Retourne HTTP 429 si la limite est dépassée.
"""
import logging
from django.core.cache import cache
from django.http import JsonResponse

logger = logging.getLogger(__name__)

# (limite, fenêtre en secondes)
# Clé : préfixe d'URL à matcher
_LIMITS = {
    '/accounts/login/': {
        'rate': (10, 60),      # 10 req/min — anti brute-force login
        'methods': {'POST'},   # seulement les soumissions de formulaire
        'key': 'ip',
    },
    '/reports/': {
        'rate': (15, 60),      # 15/min — génération PDF/Excel lourde
        'methods': None,       # toutes méthodes
        'key': 'user',
    },
    '/vouchers/': {
        'rate': (60, 60),      # 60/min — appels UniFi
        'methods': None,
        'key': 'user',
    },
    '/sites/': {
        'rate': (60, 60),
        'methods': None,
        'key': 'user',
    },
    '/dashboard/': {
        'rate': (120, 60),     # dashboard très consulté
        'methods': None,
        'key': 'user',
    },
}


def _get_client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


class RateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self._check_rate_limit(request)
        if response is not None:
            return response
        return self.get_response(request)

    def _check_rate_limit(self, request):
        path = request.path

        for prefix, config in _LIMITS.items():
            if not path.startswith(prefix):
                continue

            methods = config.get('methods')
            if methods and request.method not in methods:
                break

            limit, window = config['rate']

            if config['key'] == 'ip' or not request.user.is_authenticated:
                identity = f"ip:{_get_client_ip(request)}"
            else:
                identity = f"u:{request.user.pk}"

            cache_key = f"rl:{prefix.strip('/')}:{identity}"

            count = cache.get(cache_key)
            if count is None:
                cache.set(cache_key, 1, window)
            else:
                try:
                    count = cache.incr(cache_key)
                except Exception:
                    cache.set(cache_key, 1, window)
                    count = 1

                if count > limit:
                    logger.warning(
                        "Rate limit dépassé — %s %s identity=%s count=%d",
                        request.method, path, identity, count,
                    )
                    return JsonResponse(
                        {'error': 'Trop de requêtes. Réessayez dans une minute.'},
                        status=429,
                    )
            break

        return None
