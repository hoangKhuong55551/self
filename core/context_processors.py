def user_profile_context(request):
    """Inject user profile vào mọi template để dùng {{ profile.xp }}, {{ profile.level }}..."""
    if request.user.is_authenticated:
        try:
            return {'profile': request.user.profile}
        except Exception:
            return {'profile': None}
    return {'profile': None}


def notifications_context(request):
    """Nhắc hạn cho chuông trên topbar: task trễ/sắp đến hạn, mục tiêu, subscription, ngân sách."""
    if not request.user.is_authenticated:
        return {}

    from datetime import timedelta
    from django.urls import reverse
    from django.utils import timezone
    from finance.models import Budget, Subscription
    from productivity.models import Goal, Task

    user = request.user
    today = timezone.localdate()
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
            'title': f'{sub.name} sắp gia hạn',
            'subtitle': f'{sub.amount:,.0f} đ vào {sub.next_billing_date:%d/%m}'.replace(',', '.'),
            'url': reverse('finance:subscription_list'),
        })

    for budget in Budget.objects.filter(user=user, month=today.month, year=today.year).select_related('category'):
        if budget.is_over_budget:
            items.append({
                'icon': 'bi-cash-stack', 'tone': 'danger',
                'title': f'Vượt ngân sách {budget.category.name}',
                'subtitle': f'Đã dùng {budget.percent_used}%',
                'url': reverse('finance:budget_list'),
            })

    return {'notifications': items[:10], 'notification_count': len(items)}
