from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Q, F
from decimal import Decimal

from .models import Wallet, Transaction, Budget, Subscription, WishlistItem, Asset
from .forms import WalletForm, TransactionForm, BudgetForm, SubscriptionForm, WishlistItemForm


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

    budgets = Budget.objects.filter(
        user=request.user,
        month=today.month,
        year=today.year
    ).select_related('category')

    subscriptions = Subscription.objects.filter(
        user=request.user,
        is_active=True
    ).order_by('next_billing_date')[:5]

    wishlist = WishlistItem.objects.filter(
        user=request.user,
        is_purchased=False
    ).order_by('-priority')[:5]

    context = {
        'wallets': wallets,
        'total_balance': total_balance,
        'recent_transactions': recent_transactions,
        'month_income': month_stats['total_income'] or Decimal('0'),
        'month_expense': month_stats['total_expense'] or Decimal('0'),
        'budgets': budgets,
        'subscriptions': subscriptions,
        'wishlist': wishlist,
        'current_month': today.strftime("%m/%Y"),
    }
    return render(request, 'finance/dashboard.html', context)


# --- WALLETS ---
@login_required
def wallet_list(request):
    wallets = Wallet.objects.filter(user=request.user)
    if request.method == 'POST':
        form = WalletForm(request.POST)
        if form.is_valid():
            wallet = form.save(commit=False)
            wallet.user = request.user
            wallet.save()
            messages.success(request, f"Đã thêm ví {wallet.name} thành công!")
            return redirect('finance:wallet_list')
    else:
        form = WalletForm()

    return render(request, 'finance/wallet_list.html', {'wallets': wallets, 'form': form})


# --- TRANSACTIONS ---
@login_required
def transaction_list(request):
    transactions = Transaction.objects.filter(
        user=request.user
    ).select_related('wallet', 'category').order_by('-date', '-created_at')

    if request.method == 'POST':
        form = TransactionForm(request.POST, user=request.user)
        if form.is_valid():
            txn = form.save(commit=False)
            txn.user = request.user
            txn.save()

            # Cập nhật số dư ví
            delta = txn.amount if txn.transaction_type == 'income' else -txn.amount
            Wallet.objects.filter(pk=txn.wallet_id).update(balance=F('balance') + delta)

            messages.success(request, "Đã ghi nhận giao dịch thành công!")
            return redirect('finance:transaction_list')
    else:
        form = TransactionForm(user=request.user)

    return render(request, 'finance/transaction_list.html', {'transactions': transactions, 'form': form})


# --- BUDGETS ---
@login_required
def budget_list(request):
    today = timezone.now().date()
    budgets = Budget.objects.filter(
        user=request.user,
        year=today.year,
        month=today.month
    ).select_related('category')

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


# --- SUBSCRIPTIONS ---
@login_required
def subscription_list(request):
    subs = Subscription.objects.filter(user=request.user).select_related('wallet', 'category')
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

    return render(request, 'finance/subscription_list.html', {'subscriptions': subs, 'form': form})


# --- WISHLIST ---
@login_required
def wishlist_view(request):
    items = WishlistItem.objects.filter(user=request.user).order_by('is_purchased', '-priority')
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
def wishlist_purchase(request, pk):
    """Xử lý hành động bấm MUA: kích hoạt Signal tạo giao dịch + tạo Asset."""
    item = get_object_or_404(WishlistItem, pk=pk, user=request.user)
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
