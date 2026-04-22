from django.apps import AppConfig


class Config(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'sites_mgmt'

    def ready(self):
        import sites_mgmt.signals  # noqa: F401
