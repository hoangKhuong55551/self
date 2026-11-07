from django.db import models
from django.conf import settings
from django.utils import timezone
from django.db.models import Count, Q
from datetime import timedelta


class Goal(models.Model):
    """Mục tiêu lớn (OKR), chứa nhiều Task con."""

    class Status(models.TextChoices):
        NOT_STARTED = 'not_started', 'Chưa bắt đầu'
        IN_PROGRESS = 'in_progress', 'Đang thực hiện'
        COMPLETED = 'completed', 'Hoàn thành'
        ARCHIVED = 'archived', 'Lưu trữ'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='goals'
    )
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True, default='')
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.NOT_STARTED
    )
    progress = models.FloatField(
        default=0,
        help_text="0-100, tự động tính từ Tasks"
    )
    deadline = models.DateField(null=True, blank=True)
    color = models.CharField(max_length=7, default='#6366f1')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"🎯 {self.title} ({self.progress:.0f}%)"

    def recalculate_progress(self):
        """Tính lại progress dựa trên tỉ lệ Task 'done' / tổng Tasks."""
        stats = self.tasks.aggregate(
            total=Count('id'),
            done=Count('id', filter=Q(status='done'))
        )
        total = stats['total']
        done = stats['done']

        if total == 0:
            self.progress = 0
        else:
            self.progress = round((done / total) * 100, 1)

        if self.progress >= 100:
            self.status = self.Status.COMPLETED
        elif self.progress > 0:
            self.status = self.Status.IN_PROGRESS

        self.save(update_fields=['progress', 'status', 'updated_at'])


class Task(models.Model):
    """Công việc cụ thể, thuộc về một Goal."""

    class Status(models.TextChoices):
        TODO = 'todo', 'To Do'
        IN_PROGRESS = 'in_progress', 'In Progress'
        DONE = 'done', 'Done'

    class Quadrant(models.TextChoices):
        """Ma trận Eisenhower."""
        DO = 'do', '🔴 Quan trọng & Khẩn cấp'
        SCHEDULE = 'schedule', '🟡 Quan trọng & Không khẩn'
        DELEGATE = 'delegate', '🔵 Không quan trọng & Khẩn'
        ELIMINATE = 'eliminate', '⚪ Không quan trọng & Không khẩn'

    class Recurrence(models.TextChoices):
        NONE = 'none', 'Không lặp lại'
        DAILY = 'daily', 'Hằng ngày'
        WEEKDAYS = 'weekdays', 'Ngày làm việc (T2–T6)'
        WEEKLY = 'weekly', 'Hằng tuần'
        MONTHLY = 'monthly', 'Hằng tháng'

    goal = models.ForeignKey(
        Goal,
        on_delete=models.CASCADE,
        related_name='tasks'
    )
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True, default='')
    course = models.ForeignKey(
        'academic.Course',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='tasks',
        help_text="Môn học liên quan (để thống kê thời gian học)"
    )
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.TODO
    )
    quadrant = models.CharField(
        max_length=10,
        choices=Quadrant.choices,
        default=Quadrant.SCHEDULE
    )
    due_date = models.DateField(null=True, blank=True)
    due_time = models.TimeField(null=True, blank=True)
    recurrence = models.CharField(
        max_length=10,
        choices=Recurrence.choices,
        default=Recurrence.NONE,
        help_text="Xong task thì tự tạo lần kế tiếp (cần có hạn hoàn thành)",
    )
    # [{"text": "...", "done": false}, ...]
    checklist = models.JSONField(default=list, blank=True)
    # Đã sinh lần lặp kế tiếp (tránh sinh trùng khi bỏ tick rồi tick lại)
    spawned_next = models.BooleanField(default=False, editable=False)
    estimated_pomodoros = models.PositiveIntegerField(
        default=1,
        help_text="Số pomodoro dự kiến"
    )
    order = models.PositiveIntegerField(default=0, help_text="Thứ tự trong kanban")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['order', '-created_at']

    def __str__(self):
        return f"{'✅' if self.status == 'done' else '📋'} {self.title}"

    @property
    def checklist_done(self):
        return sum(1 for item in self.checklist or [] if item.get('done'))

    def next_due_date(self, today):
        """Hạn của lần lặp kế tiếp: bước theo chu kỳ cho tới khi sau hôm nay."""
        from dateutil.relativedelta import relativedelta
        if self.recurrence == self.Recurrence.NONE or not self.due_date:
            return None
        step = {
            'daily': relativedelta(days=1), 'weekdays': relativedelta(days=1),
            'weekly': relativedelta(weeks=1), 'monthly': relativedelta(months=1),
        }[self.recurrence]
        nxt, n = self.due_date, 1
        while True:
            # Cộng từ hạn gốc (không cộng dồn) để "hằng tháng ngày 31" không trôi về 28
            nxt = self.due_date + step * n
            n += 1
            if self.recurrence == 'weekdays' and nxt.weekday() >= 5:
                continue
            if nxt > today or n > 400:
                return nxt

    @property
    def actual_pomodoros(self):
        return self.pomodoro_sessions.filter(completed=True).count()

    @property
    def total_focus_minutes(self):
        from django.db.models import Sum
        return self.pomodoro_sessions.filter(
            completed=True
        ).aggregate(
            total=Sum('duration_minutes')
        )['total'] or 0


class PomodoroSession(models.Model):
    """Một phiên tập trung Pomodoro."""
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='pomodoro_sessions'
    )
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(default=25)
    completed = models.BooleanField(default=False)
    note = models.CharField(max_length=200, blank=True, default='')

    class Meta:
        ordering = ['-start_time']

    def __str__(self):
        status = "✅" if self.completed else "⏸️"
        return f"{status} Pomodoro for {self.task.title[:30]} ({self.duration_minutes}m)"


class Habit(models.Model):
    """Thói quen cần theo dõi hàng ngày."""

    class Frequency(models.TextChoices):
        DAILY = 'daily', 'Hàng ngày'
        WEEKDAYS = 'weekdays', 'Ngày trong tuần'
        CUSTOM = 'custom', 'Tùy chỉnh'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='habits'
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    frequency = models.CharField(
        max_length=10,
        choices=Frequency.choices,
        default=Frequency.DAILY
    )
    target_per_day = models.PositiveIntegerField(
        default=1,
        help_text="Số lần cần hoàn thành mỗi ngày"
    )
    icon = models.CharField(max_length=50, default='✅')
    color = models.CharField(max_length=7, default='#10b981')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.icon} {self.name}"

    @property
    def current_streak(self):
        today = timezone.now().date()
        streak = 0
        check_date = today

        while True:
            log = self.logs.filter(date=check_date, completed=True).first()
            if log:
                streak += 1
                check_date -= timedelta(days=1)
            else:
                break

        return streak

    def get_heatmap_data(self, days=365):
        today = timezone.now().date()
        start_date = today - timedelta(days=days)

        logs = self.logs.filter(
            date__gte=start_date,
            date__lte=today
        ).values_list('date', 'count')

        return {
            date.isoformat(): count
            for date, count in logs
        }


class HabitLog(models.Model):
    """Bản ghi theo dõi thói quen theo ngày."""
    habit = models.ForeignKey(
        Habit,
        on_delete=models.CASCADE,
        related_name='logs'
    )
    date = models.DateField(default=timezone.now)
    count = models.PositiveIntegerField(
        default=1,
        help_text="Số lần hoàn thành trong ngày"
    )
    completed = models.BooleanField(
        default=False,
        help_text="True khi count >= habit.target_per_day"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['habit', 'date'],
                name='unique_habit_log_per_day'
            )
        ]
        ordering = ['-date']

    def __str__(self):
        return f"{self.habit.name} | {self.date} | {'✅' if self.completed else '❌'}"

    def save(self, *args, **kwargs):
        self.completed = self.count >= self.habit.target_per_day
        super().save(*args, **kwargs)
