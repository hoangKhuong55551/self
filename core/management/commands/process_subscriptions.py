from django.core.management.base import BaseCommand

from finance.models import Subscription
from finance.services import charge_due_subscriptions


class Command(BaseCommand):
    help = "Xu ly subscription den han: tao giao dich va tru vi tu dong."

    def handle(self, *args, **options):
        count = charge_due_subscriptions(Subscription.objects.all())
        self.stdout.write(
            self.style.SUCCESS(f"Da tao {count} giao dich subscription den han.")
        )
