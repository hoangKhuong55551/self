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

    # --- GAMIFICATION ---
    profile = user.profile

    return {
        # Finance
        'total_balance': total_balance,
        'savings_this_week': savings_this_week,
        'total_income': finance_summary['total_income'] or 0,
        'total_expense': finance_summary['total_expense'] or 0,
        'transaction_count': finance_summary['transaction_count'],
        'overbudget_categories': overbudget_categories,

        # Productivity
        'tasks_completed': tasks_completed_this_week,
        'pomodoro_sessions': pomodoro_stats['total_sessions'] or 0,
        'focus_hours': round((pomodoro_stats['total_minutes'] or 0) / 60, 1),
        'habits_completed': habit_stats['completed_count'] or 0,

        # Academic
        'current_gpa': current_gpa,

        # Gamification
        'xp': profile.xp,
        'hp': profile.hp,
        'level': profile.level,
        'xp_progress': profile.xp_progress_percent,
        'longest_streak': profile.longest_streak,

        # Meta
        'week_start': week_start,
        'week_end': week_end,
    }
