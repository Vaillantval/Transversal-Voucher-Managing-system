try:
    from .celery import app as celery_app
    __all__ = ('celery_app',)
except ImportError:
    pass  # Celery non installé (dev sans Redis)
