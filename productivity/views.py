from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count
from django.views.decorators.http import require_POST
from datetime import timedelta
import json
import math

from .models import Goal, Task, Habit, HabitLog, PomodoroSession
from .forms import GoalForm, TaskForm, HabitForm


@login_required
def productivity_dashboard(request):
    """Trang chủ phân hệ Hiệu suất & Thói quen."""
    goals = Goal.objects.filter(user=request.user).prefetch_related('tasks')
    tasks_todo = Task.objects.filter(goal__user=request.user, status='todo').order_by('due_date')
    tasks_in_progress = Task.objects.filter(goal__user=request.user, status='in_progress')
    tasks_done = Task.objects.filter(goal__user=request.user, status='done').order_by('-completed_at')[:5]

    habits = Habit.objects.filter(user=request.user, is_active=True).prefetch_related('logs')
    today = timezone.now().date()

    # Thống kê habit hôm nay
    today_habits = []
    for h in habits:
        log = h.logs.filter(date=today).first()
        today_habits.append({
            'habit': h,
            'completed': log.completed if log else False,
            'count': log.count if log else 0,
        })

    context = {
        'goals': goals,
        'tasks_todo': tasks_todo,
        'tasks_in_progress': tasks_in_progress,
        'tasks_done': tasks_done,
        'today_habits': today_habits,
        'today': today,
    }
    return render(request, 'productivity/dashboard.html', context)


# --- GOALS & KANBAN TASKS ---
@login_required
def goal_list(request):
    goals = Goal.objects.filter(user=request.user).prefetch_related('tasks')
    if request.method == 'POST':
        form = GoalForm(request.POST)
        if form.is_valid():
            goal = form.save(commit=False)
            goal.user = request.user
            goal.save()
            messages.success(request, f"Đã tạo mục tiêu: {goal.title}")
            return redirect('productivity:goal_list')
    else:
        form = GoalForm()
    return render(request, 'productivity/goal_list.html', {'goals': goals, 'form': form})


@login_required
def kanban_board(request):
    """Bảng Kanban kéo thả hoặc cập nhật nhanh trạng thái Task."""
    user_goals = Goal.objects.filter(user=request.user)
    tasks = Task.objects.filter(goal__user=request.user).select_related('goal')

    if request.method == 'POST':
        form = TaskForm(request.POST, user=request.user)
        if form.is_valid():
            task = form.save()
            task.goal.recalculate_progress()
            messages.success(request, f"Đã tạo Task mới: {task.title}")
            return redirect('productivity:kanban_board')
    else:
        form = TaskForm(user=request.user)

    todo_tasks = tasks.filter(status='todo')
    in_progress_tasks = tasks.filter(status='in_progress')
    done_tasks = tasks.filter(status='done')

    context = {
        'todo_tasks': todo_tasks,
        'in_progress_tasks': in_progress_tasks,
        'done_tasks': done_tasks,
        'form': form,
        'has_goals': user_goals.exists(),
        'today_str': timezone.now().date().isoformat(),
    }
    return render(request, 'productivity/kanban_board.html', context)


@login_required
@require_POST
def update_task_status(request, pk):
    """Cập nhật trạng thái Task (hỗ trợ kéo thả AJAX/Fetch API)."""
    task = get_object_or_404(Task, pk=pk, goal__user=request.user)
    try:
        data = json.loads(request.body)
        new_status = data.get('status')
    except Exception:
        new_status = request.POST.get('status')

    if new_status in ['todo', 'in_progress', 'done']:
        task.status = new_status
        task.save()  # Kích hoạt signal: tính Goal progress & cộng XP!
        return JsonResponse({
            'success': True,
            'status': task.status,
            'goal_progress': task.goal.progress,
            'user_xp': request.user.profile.xp,
            'user_level': request.user.profile.level,
        })
    return JsonResponse({'success': False, 'error': 'Invalid status'}, status=400)


# --- HABITS & HEATMAP ---
@login_required
def habit_tracker(request):
    habits = Habit.objects.filter(user=request.user)
    today = timezone.now().date()

    if request.method == 'POST':
        form = HabitForm(request.POST)
        if form.is_valid():
            habit = form.save(commit=False)
            habit.user = request.user
            habit.save()
            messages.success(request, f"Đã tạo thói quen mới: {habit.name}")
            return redirect('productivity:habit_tracker')
    else:
        form = HabitForm()

    # Chuẩn bị dữ liệu hiển thị heatmap 30 ngày gần nhất
    days_range = [today - timedelta(days=i) for i in reversed(range(30))]
    habit_matrix = []
    for h in habits:
        logs_dict = {l.date: l.completed for l in h.logs.filter(date__in=days_range)}
        row = [logs_dict.get(d, False) for d in days_range]
        habit_matrix.append({
            'habit': h,
            'history': row,
            'streak': h.current_streak,
        })

    context = {
        'habits': habits,
        'habit_matrix': habit_matrix,
        'year_heatmap': _build_year_heatmap(request.user, habits.count(), today),
        'days_range': days_range,
        'form': form,
        'today': today,
    }
    return render(request, 'productivity/habit_tracker.html', context)


def _build_year_heatmap(user, habit_count, today, weeks=53):
    """
    Lưới heatmap kiểu GitHub cho tất cả thói quen trong ~1 năm.
    Mỗi ô = 1 ngày, level 0-4 theo tỉ lệ thói quen hoàn thành trong ngày.
    """
    if not habit_count:
        return None

    # Bắt đầu từ thứ Hai của tuần cách đây `weeks - 1` tuần
    start = today - timedelta(days=today.weekday() + 7 * (weeks - 1))
    done_by_day = dict(
        HabitLog.objects.filter(habit__user=user, completed=True, date__gte=start, date__lte=today)
        .values_list('date')
        .annotate(n=Count('id'))
        .values_list('date', 'n')
    )

    columns, month_labels = [], []
    last_month = None
    for w in range(weeks):
        week_start = start + timedelta(weeks=w)
        cells = []
        for d in range(7):
            day = week_start + timedelta(days=d)
            if day > today:
                cells.append(None)
                continue
            done = done_by_day.get(day, 0)
            level = min(4, math.ceil(done / habit_count * 4))
            cells.append({'date': day, 'done': done, 'level': level})
        columns.append(cells)
        month_labels.append(f'T{week_start.month}' if week_start.month != last_month else '')
        last_month = week_start.month

    # Tháng dở dang ở cột đầu: bỏ nhãn để không chồng lên nhãn tháng kế tiếp
    if any(month_labels[1:3]):
        month_labels[0] = ''

    # Chuỗi ngày liên tiếp có ít nhất 1 thói quen hoàn thành
    best = run = 0
    day = start
    while day <= today:
        run = run + 1 if done_by_day.get(day) else 0
        best = max(best, run)
        day += timedelta(days=1)

    # Hôm nay chưa check-in thì vẫn tính chuỗi tới hôm qua
    current = 0
    day = today if done_by_day.get(today) else today - timedelta(days=1)
    while done_by_day.get(day):
        current += 1
        day -= timedelta(days=1)

    return {
        'columns': columns,
        'month_labels': month_labels,
        'total': sum(done_by_day.values()),
        'active_days': len(done_by_day),
        'best_streak': best,
        'current_streak': current,
    }


@login_required
@require_POST
def toggle_habit_today(request, pk):
    """Đánh dấu hoàn thành/hủy hoàn thành habit hôm nay."""
    habit = get_object_or_404(Habit, pk=pk, user=request.user)
    today = timezone.now().date()
    log, created = HabitLog.objects.get_or_create(
        habit=habit, date=today,
        defaults={'count': habit.target_per_day, 'completed': True}
    )

    if not created:
        # Đảo trạng thái
        log.completed = not log.completed
        log.count = habit.target_per_day if log.completed else 0
        log.save()
    else:
        log.save()

    # XP được cộng trong signal của HabitLog (mỗi ngày một lần)
    if log.completed and request.POST.get('via') == 'form':
        messages.success(request, f"🔥 Đã check-in: {habit.name}")

    # Form trên trang Thói quen thì redirect; fetch() từ Dashboard nhận JSON
    if request.POST.get('via') == 'form':
        return redirect('productivity:habit_tracker')
    return JsonResponse({
        'success': True,
        'completed': log.completed,
        'streak': habit.current_streak,
    })

# --- POMODORO TIMER ---
@login_required
def pomodoro_timer(request):
    """Giao diện đồng hồ Pomodoro gắn với từng Task."""
    active_tasks = Task.objects.filter(goal__user=request.user).exclude(status='done')
    recent_sessions = PomodoroSession.objects.filter(
        task__goal__user=request.user, completed=True
    ).select_related('task').order_by('-start_time')[:10]

    context = {
        'tasks': active_tasks,
        'recent_sessions': recent_sessions,
    }
    return render(request, 'productivity/pomodoro.html', context)


@login_required
@require_POST
def save_pomodoro_session(request):
    """Lưu kết quả phiên Pomodoro vừa hoàn thành."""
    task_id = request.POST.get('task_id')
    duration = int(request.POST.get('duration_minutes', 25))
    note = request.POST.get('note', '')

    task = get_object_or_404(Task, pk=task_id, goal__user=request.user)

    now = timezone.now()
    session = PomodoroSession.objects.create(
        task=task,
        start_time=now - timedelta(minutes=duration),
        end_time=now,
        duration_minutes=duration,
        completed=True,
        note=note
    )

    # Thưởng 15 XP khi hoàn thành 1 pomodoro
    request.user.profile.award_xp_once(
        f'pomodoro:{session.pk}', 15, f'Pomodoro: {task.title}'
    )

    return JsonResponse({
        'success': True,
        'session_id': session.pk,
        'task_actual_pomodoros': task.actual_pomodoros,
        'user_xp': request.user.profile.xp,
    })
