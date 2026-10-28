from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction as db_transaction
from django.db.models import F

from finance.models import Subscription, Transaction, Wallet


class Command(BaseCommand):
    help = "Xu ly subscription den han: tao giao dich va tru vi tu dong."

    def handle(self, *args, **options):
        today = timezone.now().date()
        due_subscriptions = Subscription.objects.filter(
            is_active=True,
            next_billing_date__lte=today
        ).select_related('wallet', 'category', 'user')

        count = 0
        for sub in due_subscriptions:
            with db_transaction.atomic():
                Transaction.objects.create(
                    user=sub.user,
                    wallet=sub.wallet,
                    category=sub.category,
                    transaction_type='expense',
                    amount=sub.amount,
                    date=today,
                    note=f"[Tu dong] Gia han: {sub.name}",
                    source='subscription',
                    subscription=sub,
                )

                Wallet.objects.filter(pk=sub.wallet_id).update(
                    balance=F('balance') - sub.amount
                )

                sub.advance_billing_date()
                count += 1

        self.stdout.write(
            self.style.SUCCESS(f"Da xu ly {count} subscription(s) den han.")
        )
