import os
from django.core.management.base import BaseCommand
from accounts.models import User


class Command(BaseCommand):
    help = "Crée ou met à jour le superadmin depuis DJANGO_SUPERUSER_USERNAME (ou UNIFI_USERNAME)."

    def handle(self, *args, **kwargs):
        username = (
            os.getenv('DJANGO_SUPERUSER_USERNAME', '').strip()
            or os.getenv('UNIFI_USERNAME', '').strip()
        )
        password = os.getenv('DJANGO_SUPERUSER_PASSWORD', '').strip()
        email    = os.getenv('DJANGO_SUPERUSER_EMAIL', '').strip()

        if not username:
            self.stdout.write(self.style.WARNING(
                'ensure_superadmin: aucune variable DJANGO_SUPERUSER_USERNAME / UNIFI_USERNAME — rien à faire.'
            ))
            return

        user, created = User.objects.get_or_create(username=username)
        user.role         = User.ROLE_SUPERADMIN
        user.is_staff     = True
        user.is_superuser = True
        if email:
            user.email = email
        if password:
            user.set_password(password)
        elif created:
            user.set_unusable_password()
        user.save()

        action = 'créé' if created else 'mis à jour'
        self.stdout.write(self.style.SUCCESS(
            f'ensure_superadmin: utilisateur "{username}" {action} (superadmin, is_staff, is_superuser).'
        ))
