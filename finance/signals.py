from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.db import transaction as db_transaction
from django.db.models import F
from django.utils import timezone

from .models import WishlistItem, Transaction, Asset, Wallet, Budget


@receiver(pre_save, sender=WishlistItem)
def cache_previous_wishlist_state(sender, instance, **kwargs):
    if instance.pk:
        try:
            instance._previous_is_purchased = (
                WishlistItem.objects.get(pk=instance.pk).is_purchased
            )
        except WishlistItem.DoesNotExist:
            instance._previous_is_purchased = False
    else:
        instance._previous_is_purchased = False


@receiver(post_save, sender=WishlistItem)
def wishlist_purchased_handler(sender, instance, created, **kwargs):
    """
    Khi WishlistItem chuyển is_purchased: False → True:
      1. Tạo Transaction (chi tiêu) tự động
      2. Trừ số dư Wallet (atomic)
      3. Tạo Asset (đồ đạc đang sở hữu)
      4. Trừ HP nếu vượt ngân sách
    """
    if created or not instance.is_purchased:
        return

    was_purchased = getattr(instance, '_previous_is_purchased', False)
    if was_purchased:
        return

    if not instance.wallet:
        return

    with db_transaction.atomic():
        txn = Transaction.objects.create(
            user=instance.user,
            wallet=instance.wallet,
            transaction_type='expense',
            amount=instance.price,
            date=instance.purchased_date or timezone.now().date(),
            note=f"Mua từ Wishlist: {instance.name}",
            source='wishlist',
            wishlist_item=instance,
        )

        Wallet.objects.filter(pk=instance.wallet_id).update(
            balance=F('balance') - instance.price
        )

        Asset.objects.create(
            user=instance.user,
            name=instance.name,
            description=instance.description,
            purchase_price=instance.price,
            purchase_date=instance.purchased_date or timezone.now().date(),
            from_wishlist=instance,
        )

        _check_budget_and_penalize(instance.user, txn)


def _check_budget_and_penalize(user, transaction):
    if transaction.transaction_type != 'expense' or not transaction.category:
        return

    budget = Budget.objects.filter(
        user=user,
        category=transaction.category,
        month=transaction.date.month,
        year=transaction.date.year,
    ).first()

    if budget and budget.is_over_budget:
        overspent_ratio = float(
            (budget.spent - budget.amount) / budget.amount
        )
        hp_loss = min(int(overspent_ratio * 20), 30)
        if hp_loss > 0 and hasattr(user, 'profile'):
            user.profile.lose_hp(hp_loss)
