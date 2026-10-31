from django.conf import settings
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.db import transaction as db_transaction
from django.db.models import F
from django.utils import timezone

from .defaults import create_default_categories
from .models import WishlistItem, Transaction, Asset, Wallet, Category
from .services import check_budget_and_penalize


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
            # Gắn danh mục "Mua sắm" nếu có để ngân sách và thống kê tính được khoản này
            category=Category.objects.filter(user=instance.user, type='expense', name='Mua sắm').first(),
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

        # Tiền mua lấy từ quỹ tiết kiệm dành cho món này
        if instance.saving_goal_id:
            instance.saving_goal.adjust(-instance.price)

        check_budget_and_penalize(instance.user, txn)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_default_categories_for_new_user(sender, instance, created, **kwargs):
    if created:
        create_default_categories(Category, instance.pk)
