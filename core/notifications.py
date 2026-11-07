"""
Nhắc hạn cho chuông trên topbar: task trễ/sắp đến hạn, mục tiêu, subscription, ngân sách.

Danh sách được tính trên mọi trang nên cache theo user trong NOTIFICATIONS_CACHE_SECONDS.
Signal (core/signals.py) xoá cache ngay khi Task/Goal/Subscription/Budget/Transaction thay đổi,
nên chuông vẫn cập nhật tức thì; TTL chỉ là lưới an toàn cho các thao tác ghi bỏ qua signal.
"""
from datetime import timedelta

from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

NOTIFICATIONS_CACHE_SECONDS = 300
MAX_NOTIFICATIONS = 10


def _cache_key(user_id):
    return f'notifications:{user_id}'


def invalidate_notifications(user_id):
    if user_id:
        cache.delete(_cache_key(user_id))


def get_notifications(user):
    """Trả về (items, total) — dùng cache nếu còn hạn và cùng ngày."""
    today = timezone.localdate()
    key = _cache_key(user.pk)
    cached = cache.get(key)
    # Sang ngày mới thì "hạn hôm nay/ngày mai" đổi nghĩa, phải tính lại
    if cached and cached['day'] == today.isoformat():
        return cached['items'], cached['total']
    items = build_notifications(user, today)
    result = {'day': today.isoformat(), 'items': items[:MAX_NOTIFICATIONS], 'total': len(items)}
    cache.set(key, result, NOTIFICATIONS_CACHE_SECONDS)
    return result['items'], result['total']


def build_notifications(user, today):
    from finance.models import Budget, Subscription
    from finance.services import attach_budget_forecast
    from productivity.models import Goal, Task

    soon = today + timedelta(days=3)
    items = []

    open_tasks = Task.objects.filter(goal__user=user, due_date__isnull=False, due_date__lte=today + timedelta(days=1)).exclude(status='done')
    for task in open_tasks.order_by('due_date')[:5]:
        overdue = task.due_date < today
        items.append({
            'icon': 'bi-exclamation-octagon-fill' if overdue else 'bi-alarm',
            'tone': 'danger' if overdue else 'warning',
            'title': task.title,
            'subtitle': f'Trễ hạn {(today - task.due_date).days} ngày' if overdue else
                        ('Hạn hôm nay' if task.due_date == today else 'Hạn ngày mai'),
            'url': reverse('productivity:kanban_board'),
        })

    for goal in Goal.objects.filter(user=user, deadline__range=[today, soon]).exclude(status__in=['completed', 'archived'])[:3]:
        items.append({
            'icon': 'bi-bullseye', 'tone': 'warning',
            'title': goal.title,
            'subtitle': f'Mục tiêu hết hạn {goal.deadline:%d/%m} · {goal.progress:.0f}%',
            'url': reverse('productivity:goal_list'),
        })

    for sub in Subscription.objects.filter(user=user, is_active=True, next_billing_date__range=[today, soon])[:3]:
        items.append({
            'icon': 'bi-credit-card-2-front', 'tone': 'info',
            'title': f'{sub.name} {"sắp nhận" if sub.is_income else "sắp gia hạn"}',
            'subtitle': f'{"+" if sub.is_income else ""}{sub.amount:,.0f} đ vào {sub.next_billing_date:%d/%m}'.replace(',', '.'),
            'url': reverse('finance:subscription_list'),
        })

    budgets = attach_budget_forecast(
        Budget.objects.filter(user=user, month=today.month, year=today.year).select_related('category').with_spent(), today
    )
    for budget in budgets:
        if budget.is_over_budget:
            items.append({
                'icon': 'bi-cash-stack', 'tone': 'danger',
                'title': f'Vượt ngân sách {budget.category.name}',
                'subtitle': f'Đã dùng {budget.percent_used}%',
                'url': reverse('finance:budget_list'),
            })
        elif budget.projected_over and today.day >= 7:
            # Đầu tháng ít dữ liệu, dự báo dễ sai nên chỉ nhắc từ ngày 7
            items.append({
                'icon': 'bi-graph-up-arrow', 'tone': 'warning',
                'title': f'Sắp vượt ngân sách {budget.category.name}',
                'subtitle': f'Dự kiến {budget.projected:,.0f} / {budget.amount:,.0f} đ'.replace(',', '.'),
                'url': reverse('finance:budget_list'),
            })

    return items
