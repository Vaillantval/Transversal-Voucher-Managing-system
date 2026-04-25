from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Envoie immédiatement le rapport hebdomadaire des ventes store."

    def handle(self, *args, **options):
        from notifications.scheduler import send_weekly_store_report
        self.stdout.write("Envoi du rapport hebdo store...")
        send_weekly_store_report()
        self.stdout.write(self.style.SUCCESS("Fait."))
