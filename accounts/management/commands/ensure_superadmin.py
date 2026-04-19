import os
from django.core.management.base import BaseCommand
from accounts.models import User


class Command(BaseCommand):
    help = "Crée le superadmin depuis UNIFI_USERNAME si aucun superadmin n'existe."

    def handle(self, *args, **kwargs):
        username = os.getenv('UNIFI_USERNAME', '').strip()

        if not username:
            self.stdout.write(self.style.WARNING(
                'ensure_superadmin: UNIFI_USERNAME non définie — aucun superadmin créé.'
            ))
            return

        if User.objects.filter(role=User.ROLE_SUPERADMIN).exists():
            self.stdout.write(self.style.SUCCESS(
                'ensure_superadmin: un superadmin existe déjà — rien à faire.'
            ))
            return

        user, created = User.objects.get_or_create(username=username)
        user.role = User.ROLE_SUPERADMIN
        user.set_unusable_password()
        user.save()

        action = 'créé' if created else 'promu superadmin'
        self.stdout.write(self.style.SUCCESS(
            f'ensure_superadmin: utilisateur "{username}" {action}.'
        ))
