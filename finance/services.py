"""
Nghiệp vụ tài chính dùng chung cho view, middleware và management command.
"""
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.db import transaction as db_transaction
from django.db.models import F, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from .models import Budget, Transaction, Wallet

# Giới hạn số kỳ bù mỗi lần chạy, tránh vòng lặp vô hạn với dữ liệu hỏng
MAX_CATCH_UP_CYCLES = 60


def check_budget_and_penalize(user, txn):
    """Trừ HP nếu giao dịch chi tiêu làm vượt ngân sách tháng của danh mục."""
    if txn.transaction_type != Transaction.TransactionType.EXPENSE or not txn.category_id:
        return

    budget = Budget.objects.filter(
        user=user,
        category_id=txn.category_id,
        month=txn.date.month,
        year=txn.date.year,
    ).first()

    if budget and budget.is_over_budget:
        overspent_ratio = float((budget.spent - budget.amount) / budget.amount)
        hp_loss = min(int(overspent_ratio * 20), 30)
        if hp_loss > 0 and hasattr(user, 'profile'):
            user.profile.lose_hp(hp_loss)


def charge_due_subscriptions(subscriptions, today=None):
    """
    Tạo giao dịch cho mọi kỳ đến hạn (kể cả các kỳ bị bỏ lỡ) và trừ ví.
    Trả về số giao dịch đã tạo.
    """
    today = today or timezone.now().date()
    count = 0
    for sub in subscriptions.filter(is_active=True, next_billing_date__lte=today).select_related('user'):
        for _ in range(MAX_CATCH_UP_CYCLES):
            if sub.next_billing_date > today:
                break
            with db_transaction.atomic():
                txn = Transaction.objects.create(
                    user=sub.user,
                    wallet_id=sub.wallet_id,
                    category_id=sub.category_id,
                    transaction_type=Transaction.TransactionType.EXPENSE,
                    amount=sub.amount,
                    date=sub.next_billing_date,
                    note=f"[Tự động] Gia hạn: {sub.name}",
                    source=Transaction.Source.SUBSCRIPTION,
                    subscription=sub,
                )
                Wallet.objects.filter(pk=sub.wallet_id).update(balance=F('balance') - sub.amount)
                sub.advance_billing_date()
            check_budget_and_penalize(sub.user, txn)
            count += 1
    return count


def monthly_cashflow(user, months=12, today=None):
    """
    Thu/chi theo từng tháng trong `months` tháng gần nhất (kể cả tháng hiện tại),
    tháng không có giao dịch vẫn có mặt với giá trị 0.
    """
    today = today or timezone.now().date()
    first = today.replace(day=1) - relativedelta(months=months - 1)
    rows = (
        Transaction.objects.filter(user=user, date__gte=first, date__lte=today)
        .annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(
            income=Sum('amount', filter=Q(transaction_type=Transaction.TransactionType.INCOME)),
            expense=Sum('amount', filter=Q(transaction_type=Transaction.TransactionType.EXPENSE)),
        )
    )
    by_month = {r['month']: r for r in rows}
    result = []
    for i in range(months):
        month = first + relativedelta(months=i)
        row = by_month.get(month, {})
        income = row.get('income') or Decimal('0')
        expense = row.get('expense') or Decimal('0')
        result.append({
            'label': f'T{month.month}/{month.year % 100:02d}',
            'income': float(income),
            'expense': float(expense),
            'net': float(income - expense),
        })
    return result
