"""
Service layer cho Dashboard tuần: tổng hợp dữ liệu cross-module.
Sử dụng ORM nâng cao: annotate, aggregate, Q, F.
"""
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal


def get_weekly_dashboard(user):
    """
    Trả về dict dữ liệu tổng hợp cho Dashboard cuối tuần.
    """
    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())  # Thứ Hai
    week_end = week_start + timedelta(days=6)

    # --- FINANCE ---
    from finance.models import Transaction, Wallet, Budget

    weekly_transactions = Transaction.objects.filter(
        user=user,
        date__range=[week_start, week_end]
    )

    finance_summary = weekly_transactions.aggregate(
        total_income=Sum('amount', filter=Q(transaction_type='income')),
        total_expense=Sum('amount', filter=Q(transaction_type='expense')),
        transaction_count=Count('id'),
    )

    total_balance = Wallet.objects.filter(
        user=user, is_active=True
    ).aggregate(total=Sum('balance'))['total'] or Decimal('0')

    savings_this_week = (
        (finance_summary['total_income'] or Decimal('0'))
        - (finance_summary['total_expense'] or Decimal('0'))
    )

    # Budgets status cho tháng hiện tại
    current_budgets = Budget.objects.filter(
        user=user,
        month=today.month,
        year=today.year
    ).select_related('category')

    overbudget_categories = [b for b in current_budgets if b.is_over_budget]

    # --- PRODUCTIVITY ---
    from productivity.models import Task, PomodoroSession, HabitLog

    tasks_completed_this_week = Task.objects.filter(
        goal__user=user,
        status='done',
        completed_at__date__range=[week_start, week_end]
    ).count()

    pomodoro_stats = PomodoroSession.objects.filter(
        task__goal__user=user,
        completed=True,
        start_time__date__range=[week_start, week_end]
    ).aggregate(
        total_sessions=Count('id'),
        total_minutes=Sum('duration_minutes'),
    )

    # Habits: số ngày hoàn thành trong tuần
    habit_stats = HabitLog.objects.filter(
        habit__user=user,
        completed=True,
        date__range=[week_start, week_end]
    ).aggregate(
        completed_count=Count('id'),
    )

    # --- ACADEMIC ---
    from academic.models import Semester
    current_semester = Semester.objects.filter(
        user=user, is_current=True
    ).first()
    current_gpa = current_semester.gpa if current_semester else 0.0

    # --- LIBRARY ---
    from library.models import MediaItem

    library_current = MediaItem.objects.filter(
        user=user, status=MediaItem.Status.IN_PROGRESS
    )[:4]

    # --- GAMIFICATION ---
    profile = user.profile

    # Recent activities (Tasks + Transactions)
    recent_tasks = Task.objects.filter(goal__user=user).select_related('goal').order_by('-updated_at' if hasattr(Task, 'updated_at') else '-id')[:5]
    recent_txns = weekly_transactions.select_related('category', 'wallet').order_by('-date', '-created_at')[:5]

    return {
        # Finance
        'total_balance': total_balance,
        'savings_this_week': savings_this_week,
        'total_income': finance_summary['total_income'] or 0,
        'total_expense': finance_summary['total_expense'] or 0,
        'transaction_count': finance_summary['transaction_count'],
        'overbudget_categories': overbudget_categories,
        'current_budgets': current_budgets,

        # Productivity
        'tasks_completed': tasks_completed_this_week,
        'pomodoro_sessions': pomodoro_stats['total_sessions'] or 0,
        'focus_hours': round((pomodoro_stats['total_minutes'] or 0) / 60, 1),
        'habits_completed': habit_stats['completed_count'] or 0,
        'recent_tasks': recent_tasks,
        'recent_txns': recent_txns,

        # Academic
        'current_gpa': current_gpa,

        # Library
        'library_current': library_current,

        # Gamification
        'xp': profile.xp,
        'hp': profile.hp,
        'level': profile.level,
        'xp_progress': profile.xp_progress_percent,
        'xp_for_next': profile.xp_for_next_level,
        'longest_streak': profile.longest_streak,

        # Meta
        'week_start': week_start,
        'week_end': week_end,
    }


def global_search(user, query, per_type=5):
    """
    Tìm kiếm xuyên module cho thanh Ctrl+K.
    Trả về list dict: type, title, subtitle, url, icon.
    """
    from django.urls import reverse
    from finance.models import Transaction, WishlistItem
    from productivity.models import Goal, Task
    from academic.models import Note, CodeSnippet
    from library.models import MediaItem

    query = (query or '').strip()
    if len(query) < 2:
        return []

    results = []

    for task in Task.objects.filter(goal__user=user, title__icontains=query).select_related('goal')[:per_type]:
        results.append({
            'type': 'Task', 'icon': 'bi-check2-square',
            'title': task.title, 'subtitle': f'{task.get_status_display()} • {task.goal.title}',
            'url': reverse('productivity:kanban_board'),
        })

    for goal in Goal.objects.filter(user=user, title__icontains=query)[:per_type]:
        results.append({
            'type': 'Mục tiêu', 'icon': 'bi-bullseye',
            'title': goal.title, 'subtitle': f'{goal.progress:.0f}% hoàn thành',
            'url': reverse('productivity:goal_list'),
        })

    for note in Note.objects.filter(user=user).filter(Q(title__icontains=query) | Q(content__icontains=query))[:per_type]:
        results.append({
            'type': 'Ghi chú', 'icon': 'bi-journal-text',
            'title': note.title, 'subtitle': note.updated_at.strftime('%d/%m/%Y'),
            'url': reverse('academic:note_detail', args=[note.pk]),
        })

    for snippet in CodeSnippet.objects.filter(user=user, title__icontains=query)[:per_type]:
        results.append({
            'type': 'Code', 'icon': 'bi-code-slash',
            'title': snippet.title, 'subtitle': snippet.get_language_display(),
            'url': reverse('academic:snippet_detail', args=[snippet.pk]),
        })

    for item in MediaItem.objects.filter(user=user).filter(Q(title__icontains=query) | Q(creator__icontains=query))[:per_type]:
        results.append({
            'type': 'Thư viện', 'icon': item.type_icon,
            'title': item.title, 'subtitle': f'{item.status_label}{" • " + item.creator if item.creator else ""}',
            'url': reverse('library:item_detail', args=[item.pk]),
        })

    for txn in Transaction.objects.filter(user=user, note__icontains=query).select_related('wallet')[:per_type]:
        sign = '+' if txn.transaction_type == 'income' else '-'
        results.append({
            'type': 'Giao dịch', 'icon': 'bi-receipt',
            'title': txn.note, 'subtitle': f'{sign}{txn.amount:,.0f} đ • {txn.date:%d/%m/%Y}'.replace(',', '.'),
            'url': reverse('finance:transaction_list'),
        })

    for wish in WishlistItem.objects.filter(user=user, name__icontains=query)[:per_type]:
        results.append({
            'type': 'Wishlist', 'icon': 'bi-bag-heart',
            'title': wish.name, 'subtitle': f'{wish.price:,.0f} đ'.replace(',', '.'),
            'url': reverse('finance:wishlist'),
        })

    return results


def get_week_review(user, week_start):
    """Số liệu tổng kết cho tuần bắt đầu từ `week_start` (thứ Hai)."""
    from finance.models import Transaction
    from productivity.models import Task, PomodoroSession, HabitLog, Habit
    from library.models import MediaItem
    from .models import XPEvent, UserAchievement
    from .achievements import ACHIEVEMENTS_BY_CODE

    week_end = week_start + timedelta(days=6)
    days = [week_start, week_end]

    txns = Transaction.objects.filter(user=user, date__range=days)
    money = txns.aggregate(
        income=Sum('amount', filter=Q(transaction_type='income')),
        expense=Sum('amount', filter=Q(transaction_type='expense')),
    )
    income = money['income'] or Decimal('0')
    expense = money['expense'] or Decimal('0')
    top_expenses = (
        txns.filter(transaction_type='expense')
        .values('category__name')
        .annotate(total=Sum('amount'))
        .order_by('-total')[:4]
    )

    tasks_done = Task.objects.filter(
        goal__user=user, status='done', completed_at__date__range=days
    ).select_related('goal')

    focus = PomodoroSession.objects.filter(
        task__goal__user=user, completed=True, start_time__date__range=days
    ).aggregate(sessions=Count('id'), minutes=Sum('duration_minutes'))

    habit_count = Habit.objects.filter(user=user).count()
    checkins = HabitLog.objects.filter(habit__user=user, completed=True, date__range=days).count()
    habit_rate = round(checkins / (habit_count * 7) * 100) if habit_count else 0

    media_done = MediaItem.objects.filter(user=user, status='done', finished_on__range=days)

    xp_week = XPEvent.objects.filter(
        user=user, created_at__date__range=days
    ).aggregate(total=Sum('amount'))['total'] or 0

    badges = [
        ACHIEVEMENTS_BY_CODE[code]
        for code in UserAchievement.objects.filter(
            user=user, unlocked_at__date__range=days
        ).values_list('code', flat=True)
        if code in ACHIEVEMENTS_BY_CODE
    ]

    return {
        'week_start': week_start,
        'week_end': week_end,
        'income': income,
        'expense': expense,
        'savings': income - expense,
        'top_expenses': top_expenses,
        'tasks_done': tasks_done,
        'focus_sessions': focus['sessions'] or 0,
        'focus_hours': round((focus['minutes'] or 0) / 60, 1),
        'checkins': checkins,
        'habit_rate': habit_rate,
        'media_done': media_done,
        'xp_week': xp_week,
        'badges': badges,
    }
