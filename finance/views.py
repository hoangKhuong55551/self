from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction as db_transaction
from django.utils import timezone
from django.db.models import Sum, Q, F
from django.urls import reverse
from django.views.decorators.http import require_POST
from datetime import timedelta
from decimal import Decimal

from .models import Wallet, Transaction, Budget, Subscription, WishlistItem, Asset, Category, Transfer, SavingGoal
from .forms import (
    WalletForm, WalletEditForm, TransactionForm, BudgetForm, SubscriptionForm, WishlistItemForm,
    CategoryForm, TransferForm, SavingGoalForm, SavingGoalAdjustForm, TransactionFilterForm,
    TransactionImportForm,
)
from .services import (
    attach_budget_forecast, category_spending, check_budget_and_penalize, import_transactions_csv,
    monthly_cashflow, savings_rate,
)

TRANSACTIONS_PER_PAGE = 25


def _edit_page(request, instance, form_class, *, title, back_url, delete_url=None, delete_warning='', **form_kwargs):
    """
    Trang sửa dùng chung: GET hiện form, POST hợp lệ thì lưu và trả về instance đã lưu,
    ngược lại trả về HttpResponse để view trả thẳng cho client.
    """
    form = form_class(request.POST or None, instance=instance, **form_kwargs)
    if request.method == 'POST' and form.is_valid():
        return form.save()
    return render(request, 'finance/form_page.html', {
        'form': form, 'title': title, 'back_url': back_url,
        'delete_url': delete_url, 'delete_warning': delete_warning,
    })


def _saved(result):
    return not hasattr(result, 'status_code')


@login_required
def finance_dashboard(request):
    """Trang chủ phân hệ Tài chính."""
    today = timezone.now().date()
    wallets = Wallet.objects.filter(user=request.user, is_active=True)
    total_balance = wallets.aggregate(total=Sum('balance'))['total'] or Decimal('0')

    recent_transactions = Transaction.objects.filter(
        user=request.user
    ).select_related('wallet', 'category')[:10]

    # Thu chi tháng này
    month_stats = Transaction.objects.filter(
        user=request.user,
        date__year=today.year,
        date__month=today.month
    ).aggregate(
        total_income=Sum('amount', filter=Q(transaction_type='income')),
        total_expense=Sum('amount', filter=Q(transaction_type='expense')),
    )
    month_income = month_stats['total_income'] or Decimal('0')
    month_expense = month_stats['total_expense'] or Decimal('0')

    budgets = attach_budget_forecast(Budget.objects.filter(
        user=request.user,
        month=today.month,
        year=today.year
    ).select_related('category'), today)

    subscriptions = Subscription.objects.filter(
        user=request.user,
        is_active=True
    ).order_by('next_billing_date')[:5]

    wishlist = WishlistItem.objects.filter(
        user=request.user,
        is_purchased=False
    ).select_related('saving_goal').order_by('-priority')[:5]

    context = {
        'wallets': wallets,
        'total_balance': total_balance,
        'recent_transactions': recent_transactions,
        'month_income': month_income,
        'month_expense': month_expense,
        'month_savings_rate': savings_rate(month_income, month_expense),
        'budgets': budgets,
        'subscriptions': subscriptions,
        'wishlist': wishlist,
        'saving_goals': SavingGoal.objects.filter(user=request.user, is_completed=False)[:3],
        'current_month': today.strftime("%m/%Y"),
        'cashflow': monthly_cashflow(request.user, today=today),
        'category_spending': category_spending(request.user, today.year, today.month),
    }
    return render(request, 'finance/dashboard.html', context)


# --- WALLETS ---
@login_required
def wallet_list(request):
    wallets = Wallet.objects.filter(user=request.user).order_by('-is_active', '-created_at')
    if request.method == 'POST':
        form = WalletForm(request.POST, user=request.user)
        if form.is_valid():
            wallet = form.save(commit=False)
            wallet.user = request.user
            wallet.save()
            messages.success(request, f"Đã thêm ví {wallet.name} thành công!")
            return redirect('finance:wallet_list')
    else:
        form = WalletForm(user=request.user)

    return render(request, 'finance/wallet_list.html', {'wallets': wallets, 'form': form})


@login_required
def wallet_edit(request, pk):
    wallet = get_object_or_404(Wallet, pk=pk, user=request.user)
    result = _edit_page(
        request, wallet, WalletEditForm, user=request.user,
        title=f'Sửa ví: {wallet.name}', back_url=reverse('finance:wallet_list'),
        delete_url=reverse('finance:wallet_delete', args=[pk]),
        delete_warning='Chỉ xoá được ví chưa có giao dịch. Ví đã dùng hãy bỏ chọn "Đang sử dụng" để khoá.',
    )
    if not _saved(result):
        return result
    messages.success(request, f"Đã cập nhật ví {wallet.name}.")
    return redirect('finance:wallet_list')


@login_required
@require_POST
def wallet_delete(request, pk):
    wallet = get_object_or_404(Wallet, pk=pk, user=request.user)
    in_use = (
        wallet.transactions.exists() or wallet.transfers_in.exists()
        or wallet.transfers_out.exists() or wallet.subscriptions.exists()
    )
    if in_use:
        messages.error(request, f"Ví {wallet.name} đã có lịch sử nên không thể xoá. Hãy khoá ví thay vì xoá.")
        return redirect('finance:wallet_edit', pk=pk)
    wallet.delete()
    messages.success(request, f"Đã xoá ví {wallet.name}.")
    return redirect('finance:wallet_list')


@login_required
@require_POST
def wallet_recalculate(request, pk):
    wallet = get_object_or_404(Wallet, pk=pk, user=request.user)
    before = wallet.balance
    wallet.recalculate_balance()
    if wallet.balance == before:
        messages.info(request, f"Số dư ví {wallet.name} đã chính xác.")
    else:
        messages.warning(request, f"Đã điều chỉnh số dư ví {wallet.name}: {before:,.0f} → {wallet.balance:,.0f} đ.")
    return redirect('finance:wallet_list')


# --- CATEGORIES ---
@login_required
def category_list(request):
    categories = Category.objects.filter(user=request.user).order_by('type', 'name')
    if request.method == 'POST':
        form = CategoryForm(request.POST, user=request.user)
        if form.is_valid():
            category = form.save(commit=False)
            category.user = request.user
            category.save()
            messages.success(request, f"Đã thêm danh mục {category.name}.")
            return redirect('finance:category_list')
    else:
        form = CategoryForm(user=request.user, initial={'type': 'expense', 'color': '#6366f1'})

    return render(request, 'finance/category_list.html', {
        'expense_categories': [c for c in categories if c.type == 'expense'],
        'income_categories': [c for c in categories if c.type == 'income'],
        'form': form,
    })


@login_required
def category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk, user=request.user)
    result = _edit_page(
        request, category, CategoryForm, user=request.user,
        title=f'Sửa danh mục: {category.name}', back_url=reverse('finance:category_list'),
        delete_url=reverse('finance:category_delete', args=[pk]),
        delete_warning='Giao dịch thuộc danh mục sẽ thành "Chưa phân loại" và ngân sách của danh mục sẽ bị xoá.',
    )
    if not _saved(result):
        return result
    messages.success(request, f"Đã cập nhật danh mục {category.name}.")
    return redirect('finance:category_list')


@login_required
@require_POST
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk, user=request.user)
    category.delete()
    messages.success(request, f"Đã xoá danh mục {category.name}.")
    return redirect('finance:category_list')


# --- TRANSACTIONS ---
@login_required
def transaction_list(request):
    transactions = Transaction.objects.filter(
        user=request.user
    ).select_related('wallet', 'category').order_by('-date', '-created_at')

    filter_form = TransactionFilterForm(request.GET or None, user=request.user)
    transactions = filter_form.apply(transactions)
    totals = transactions.aggregate(
        income=Sum('amount', filter=Q(transaction_type='income')),
        expense=Sum('amount', filter=Q(transaction_type='expense')),
    )

    if request.method == 'POST':
        form = TransactionForm(request.POST, user=request.user)
        if form.is_valid():
            txn = form.save(commit=False)
            txn.user = request.user
            txn.save()

            # Cập nhật số dư ví
            delta = txn.amount if txn.transaction_type == 'income' else -txn.amount
            Wallet.objects.filter(pk=txn.wallet_id).update(balance=F('balance') + delta)
            check_budget_and_penalize(request.user, txn)

            messages.success(request, "Đã ghi nhận giao dịch thành công!")
            return redirect('finance:transaction_list')
    else:
        form = TransactionForm(user=request.user)

    page = Paginator(transactions, TRANSACTIONS_PER_PAGE).get_page(request.GET.get('page'))
    query = request.GET.copy()
    query.pop('page', None)

    return render(request, 'finance/transaction_list.html', {
        'transactions': page,
        'page_obj': page,
        'form': form,
        'filter_form': filter_form,
        'is_filtered': any(v for k, v in request.GET.items() if k != 'page'),
        'filter_query': query.urlencode(),
        'filtered_income': totals['income'] or Decimal('0'),
        'filtered_expense': totals['expense'] or Decimal('0'),
    })


@login_required
def transaction_edit(request, pk):
    txn = get_object_or_404(Transaction, pk=pk, user=request.user)
    old_wallet_id = txn.wallet_id
    result = _edit_page(
        request, txn, TransactionForm, user=request.user,
        title='Sửa giao dịch', back_url=reverse('finance:transaction_list'),
        delete_url=reverse('finance:transaction_delete', args=[pk]),
        delete_warning='Số dư ví sẽ được tính lại sau khi xoá.',
    )
    if not _saved(result):
        return result
    # Tính lại cả ví cũ lẫn ví mới (nếu đổi ví)
    for wallet in Wallet.objects.filter(pk__in={old_wallet_id, result.wallet_id}):
        wallet.recalculate_balance()
    messages.success(request, "Đã cập nhật giao dịch, số dư ví đã được tính lại.")
    return redirect('finance:transaction_list')


@login_required
@require_POST
def transaction_delete(request, pk):
    txn = get_object_or_404(Transaction, pk=pk, user=request.user)
    wallet = txn.wallet
    with db_transaction.atomic():
        txn.delete()
        wallet.recalculate_balance()
    messages.success(request, "Đã xoá giao dịch, số dư ví đã được tính lại.")
    return redirect('finance:transaction_list')


@login_required
def transaction_import(request):
    result = None
    form = TransactionImportForm(request.POST or None, request.FILES or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        result = import_transactions_csv(request.user, form.cleaned_data['wallet'], form.cleaned_data['file'].read())
        if result['created']:
            messages.success(request, f"Đã nhập {result['created']} giao dịch vào ví {form.cleaned_data['wallet'].name}.")
        elif not result['errors']:
            messages.info(request, "Không có giao dịch mới nào để nhập.")
    return render(request, 'finance/transaction_import.html', {'form': form, 'result': result})


# --- TRANSFERS ---
@login_required
def transfer_list(request):
    transfers = Transfer.objects.filter(user=request.user).select_related('from_wallet', 'to_wallet')
    form = TransferForm(request.POST or None, user=request.user, initial={'date': timezone.now().date()})
    if request.method == 'POST' and form.is_valid():
        with db_transaction.atomic():
            transfer = form.save(commit=False)
            transfer.user = request.user
            transfer.save()
            transfer.from_wallet.recalculate_balance()
            transfer.to_wallet.recalculate_balance()
        messages.success(request, f"Đã chuyển {transfer.amount:,.0f} đ từ {transfer.from_wallet.name} sang {transfer.to_wallet.name}.")
        return redirect('finance:transfer_list')
    return render(request, 'finance/transfer_list.html', {'transfers': transfers[:50], 'form': form})


@login_required
@require_POST
def transfer_delete(request, pk):
    transfer = get_object_or_404(Transfer, pk=pk, user=request.user)
    wallets = [transfer.from_wallet, transfer.to_wallet]
    with db_transaction.atomic():
        transfer.delete()
        for wallet in wallets:
            wallet.recalculate_balance()
    messages.success(request, "Đã huỷ lệnh chuyển tiền.")
    return redirect('finance:transfer_list')


# --- BUDGETS ---
@login_required
def budget_list(request):
    today = timezone.now().date()
    budgets = attach_budget_forecast(Budget.objects.filter(
        user=request.user,
        year=today.year,
        month=today.month
    ).select_related('category'), today)

    if request.method == 'POST':
        form = BudgetForm(request.POST, user=request.user)
        if form.is_valid():
            budget = form.save(commit=False)
            budget.user = request.user
            budget.save()
            messages.success(request, "Đã thiết lập hạn mức ngân sách!")
            return redirect('finance:budget_list')
    else:
        form = BudgetForm(user=request.user, initial={'month': today.month, 'year': today.year})

    return render(request, 'finance/budget_list.html', {'budgets': budgets, 'form': form, 'today': today})


@login_required
def budget_edit(request, pk):
    budget = get_object_or_404(Budget, pk=pk, user=request.user)
    result = _edit_page(
        request, budget, BudgetForm, user=request.user,
        title=f'Sửa ngân sách: {budget.category.name}', back_url=reverse('finance:budget_list'),
        delete_url=reverse('finance:budget_delete', args=[pk]),
    )
    if not _saved(result):
        return result
    messages.success(request, "Đã cập nhật ngân sách.")
    return redirect('finance:budget_list')


@login_required
@require_POST
def budget_delete(request, pk):
    get_object_or_404(Budget, pk=pk, user=request.user).delete()
    messages.success(request, "Đã xoá ngân sách.")
    return redirect('finance:budget_list')


@login_required
@require_POST
def budget_copy_last_month(request):
    """Sao chép các hạn mức tháng trước sang tháng này (bỏ qua danh mục đã có)."""
    today = timezone.now().date()
    last = today.replace(day=1) - timedelta(days=1)
    existing = set(Budget.objects.filter(
        user=request.user, month=today.month, year=today.year
    ).values_list('category_id', flat=True))
    copied = [
        Budget(user=request.user, category_id=b.category_id, month=today.month, year=today.year, amount=b.amount)
        for b in Budget.objects.filter(user=request.user, month=last.month, year=last.year)
        if b.category_id not in existing
    ]
    Budget.objects.bulk_create(copied)
    messages.success(request, f"Đã sao chép {len(copied)} hạn mức từ tháng {last:%m/%Y}.")
    return redirect('finance:budget_list')


# --- SUBSCRIPTIONS ---
@login_required
def subscription_list(request):
    subs = Subscription.objects.filter(user=request.user).select_related('wallet', 'category').order_by('-is_active', 'next_billing_date')
    if request.method == 'POST':
        form = SubscriptionForm(request.POST, user=request.user)
        if form.is_valid():
            sub = form.save(commit=False)
            sub.user = request.user
            sub.save()
            messages.success(request, f"Đã thêm gói dịch vụ {sub.name}!")
            return redirect('finance:subscription_list')
    else:
        form = SubscriptionForm(user=request.user, initial={'start_date': timezone.now().date(), 'next_billing_date': timezone.now().date()})

    monthly_total = sum((s.monthly_cost for s in subs if s.is_active), Decimal('0'))
    return render(request, 'finance/subscription_list.html', {
        'subscriptions': subs, 'form': form, 'monthly_total': monthly_total,
    })


@login_required
def subscription_edit(request, pk):
    sub = get_object_or_404(Subscription, pk=pk, user=request.user)
    result = _edit_page(
        request, sub, SubscriptionForm, user=request.user,
        title=f'Sửa dịch vụ: {sub.name}', back_url=reverse('finance:subscription_list'),
        delete_url=reverse('finance:subscription_delete', args=[pk]),
        delete_warning='Các giao dịch đã trừ trước đây vẫn được giữ lại.',
    )
    if not _saved(result):
        return result
    messages.success(request, f"Đã cập nhật {sub.name}.")
    return redirect('finance:subscription_list')


@login_required
@require_POST
def subscription_toggle(request, pk):
    sub = get_object_or_404(Subscription, pk=pk, user=request.user)
    sub.is_active = not sub.is_active
    if sub.is_active and sub.next_billing_date < timezone.now().date():
        # Kích hoạt lại: không truy thu các kỳ trong thời gian tạm dừng
        sub.next_billing_date = timezone.now().date()
    sub.save(update_fields=['is_active', 'next_billing_date'])
    messages.success(request, f"{'Đã kích hoạt lại' if sub.is_active else 'Đã tạm dừng'} {sub.name}.")
    return redirect('finance:subscription_list')


@login_required
@require_POST
def subscription_delete(request, pk):
    sub = get_object_or_404(Subscription, pk=pk, user=request.user)
    sub.delete()
    messages.success(request, f"Đã xoá {sub.name}.")
    return redirect('finance:subscription_list')


# --- SAVING GOALS ---
@login_required
def saving_goal_list(request):
    goals = SavingGoal.objects.filter(user=request.user).prefetch_related('wishlist_items')
    form = SavingGoalForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        goal = form.save(commit=False)
        goal.user = request.user
        goal.save()
        messages.success(request, f"Đã tạo mục tiêu tiết kiệm {goal.name}.")
        return redirect('finance:saving_goal_list')
    totals = goals.aggregate(saved=Sum('current_amount'), target=Sum('target_amount'))
    return render(request, 'finance/saving_goal_list.html', {
        'goals': goals, 'form': form,
        'total_saved': totals['saved'] or Decimal('0'),
        'total_target': totals['target'] or Decimal('0'),
    })


@login_required
@require_POST
def saving_goal_adjust(request, pk):
    goal = get_object_or_404(SavingGoal, pk=pk, user=request.user)
    form = SavingGoalAdjustForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Số tiền không hợp lệ.")
        return redirect('finance:saving_goal_list')
    amount = form.cleaned_data['amount']
    if form.cleaned_data['action'] == 'withdraw':
        amount = -min(amount, goal.current_amount)
    reached = goal.adjust(amount)
    if reached:
        if hasattr(request.user, 'profile'):
            request.user.profile.award_xp_once(f'saving_goal:{goal.pk}', 50, f'Đạt mục tiêu tiết kiệm: {goal.name}')
        messages.success(request, f"🎉 Đã đạt mục tiêu {goal.name}! +50 XP")
    else:
        verb = 'Đã nạp' if amount >= 0 else 'Đã rút'
        messages.success(request, f"{verb} {abs(amount):,.0f} đ — {goal.name} đạt {goal.progress_percent}%.")
    return redirect('finance:saving_goal_list')


@login_required
def saving_goal_edit(request, pk):
    goal = get_object_or_404(SavingGoal, pk=pk, user=request.user)
    result = _edit_page(
        request, goal, SavingGoalForm,
        title=f'Sửa mục tiêu: {goal.name}', back_url=reverse('finance:saving_goal_list'),
        delete_url=reverse('finance:saving_goal_delete', args=[pk]),
        delete_warning='Món trong Wishlist gắn với quỹ này sẽ được gỡ liên kết.',
    )
    if not _saved(result):
        return result
    goal.adjust(0)  # cập nhật trạng thái hoàn thành nếu đổi số tiền cần
    messages.success(request, f"Đã cập nhật {goal.name}.")
    return redirect('finance:saving_goal_list')


@login_required
@require_POST
def saving_goal_delete(request, pk):
    goal = get_object_or_404(SavingGoal, pk=pk, user=request.user)
    goal.delete()
    messages.success(request, f"Đã xoá mục tiêu {goal.name}.")
    return redirect('finance:saving_goal_list')


# --- WISHLIST ---
@login_required
def wishlist_view(request):
    items = WishlistItem.objects.filter(user=request.user).select_related('saving_goal').order_by('is_purchased', '-priority')
    if request.method == 'POST':
        form = WishlistItemForm(request.POST, user=request.user)
        if form.is_valid():
            item = form.save(commit=False)
            item.user = request.user
            item.save()
            messages.success(request, f"Đã thêm {item.name} vào Wishlist!")
            return redirect('finance:wishlist')
    else:
        form = WishlistItemForm(user=request.user)

    return render(request, 'finance/wishlist.html', {'items': items, 'form': form})


@login_required
def wishlist_edit(request, pk):
    item = get_object_or_404(WishlistItem, pk=pk, user=request.user, is_purchased=False)
    result = _edit_page(
        request, item, WishlistItemForm, user=request.user,
        title=f'Sửa: {item.name}', back_url=reverse('finance:wishlist'),
        delete_url=reverse('finance:wishlist_delete', args=[pk]),
    )
    if not _saved(result):
        return result
    messages.success(request, f"Đã cập nhật {item.name}.")
    return redirect('finance:wishlist')


@login_required
@require_POST
def wishlist_delete(request, pk):
    item = get_object_or_404(WishlistItem, pk=pk, user=request.user)
    item.delete()
    messages.success(request, f"Đã xoá {item.name} khỏi Wishlist.")
    return redirect('finance:wishlist')


@login_required
@require_POST
def wishlist_purchase(request, pk):
    """Xử lý hành động bấm MUA: kích hoạt Signal tạo giao dịch + tạo Asset."""
    item = get_object_or_404(WishlistItem, pk=pk, user=request.user)
    if not item.wallet_id:
        messages.error(request, f"Hãy chọn ví thanh toán cho '{item.name}' trước khi đánh dấu đã mua.")
        return redirect('finance:wishlist_edit', pk=pk)
    if not item.is_purchased:
        item.is_purchased = True
        item.purchased_date = timezone.now().date()
        item.save()  # Kích hoạt signal wishlist_purchased_handler!
        messages.success(request, f"🎉 Chúc mừng! Đã mua '{item.name}'. Tiền đã trừ và chuyển sang danh mục Tài sản/Dụng cụ.")
    return redirect('finance:wishlist')


# --- ASSETS ---
@login_required
def asset_list(request):
    assets = Asset.objects.filter(user=request.user)
    return render(request, 'finance/asset_list.html', {'assets': assets})
