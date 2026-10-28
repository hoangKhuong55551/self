"""
Middleware: Tự động kiểm tra subscription đến hạn
mỗi khi user truy cập trang (thay thế cron cho môi trường dev).
"""
from django.utils import timezone


class SubscriptionCheckMiddleware:
    """
    Kiểm tra và xử lý subscription đến hạn khi user đăng nhập.
    Chỉ chạy 1 lần/ngày/user (dùng session để track).
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            today_str = timezone.now().date().isoformat()
            session_key = f'sub_checked_{today_str}'

            if not request.session.get(session_key, False):
                self._process_due_subscriptions(request.user)
                request.session[session_key] = True

        return self.get_response(request)

    def _process_due_subscriptions(self, user):
        from django.db import transaction as db_transaction
        from django.db.models import F
        from finance.models import Subscription, Transaction, Wallet

        today = timezone.now().date()
        due_subs = Subscription.objects.filter(
            user=user,
            is_active=True,
            next_billing_date__lte=today
        ).select_related('wallet', 'category')

        for sub in due_subs:
            with db_transaction.atomic():
                Transaction.objects.create(
                    user=user,
                    wallet=sub.wallet,
                    category=sub.category,
                    transaction_type='expense',
                    amount=sub.amount,
                    date=today,
                    note=f"[Tự động] Gia hạn: {sub.name}",
                    source='subscription',
                    subscription=sub,
                )
                Wallet.objects.filter(pk=sub.wallet_id).update(
                    balance=F('balance') - sub.amount
                )
                sub.advance_billing_date()
