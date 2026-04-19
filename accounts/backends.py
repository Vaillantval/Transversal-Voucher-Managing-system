import logging
from django.contrib.auth.backends import BaseBackend
from django.conf import settings

logger = logging.getLogger(__name__)


def _sync_user_sites(user, controller):
    """Synchronise les sites gérés depuis le contrôleur UniFi."""
    from sites_mgmt.models import HotspotSite
    try:
        unifi_sites = controller.get_sites()
        site_ids = {s['name'] for s in unifi_sites}
        matching = HotspotSite.objects.filter(unifi_site_id__in=site_ids, is_active=True)
        user.managed_sites.set(matching)
    except Exception as e:
        logger.warning(f"Sync sites UniFi pour '{user.username}' : {e}")


class UniFiAuthBackend(BaseBackend):
    """Authentifie un utilisateur contre le contrôleur UniFi."""

    def authenticate(self, request, username=None, password=None):
        if not username or not password:
            return None

        try:
            from pyunifi.controller import Controller
            c = Controller(
                host=settings.UNIFI_HOST,
                username=username,
                password=password,
                port=settings.UNIFI_PORT,
                ssl_verify=settings.UNIFI_VERIFY_SSL,
                version='v5',
            )
        except Exception as e:
            logger.warning(f"Échec auth UniFi pour '{username}' : {e}")
            return None

        # Connexion UniFi réussie — créer/récupérer le user local (session uniquement)
        from .models import User
        user, created = User.objects.get_or_create(username=username)
        if created:
            user.set_unusable_password()
            user.role = User.ROLE_SITE_ADMIN
            user.save()

        _sync_user_sites(user, c)
        return user

    def get_user(self, user_id):
        from .models import User
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
