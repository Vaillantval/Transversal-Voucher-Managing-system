import os
import sys
from django.apps import AppConfig


_SKIP_CMDS = {'migrate', 'makemigrations', 'collectstatic', 'shell',
               'dbshell', 'showmigrations', 'sqlmigrate', 'check',
               'createsuperuser', 'ensure_superadmin', 'test'}


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'notifications'
    verbose_name = 'Notifications'

    def ready(self):
        if any(cmd in sys.argv for cmd in _SKIP_CMDS):
            return
        # Évite le double démarrage avec le reloader Django en dev
        if os.environ.get('RUN_MAIN') == 'true' or not os.environ.get('RUN_MAIN'):
            try:
                from . import scheduler
                scheduler.start()
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Scheduler start error: {e}")
