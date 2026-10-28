from django.contrib import admin
from .models import Goal, Task, PomodoroSession, Habit, HabitLog

class TaskInline(admin.TabularInline):
    model = Task
    extra = 1

@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'status', 'progress', 'deadline')
    list_filter = ('status', 'deadline')
    search_fields = ('title', 'user__username')
    inlines = [TaskInline]

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'goal', 'status', 'quadrant', 'due_date', 'estimated_pomodoros')
    list_filter = ('status', 'quadrant', 'due_date')
    search_fields = ('title', 'goal__title')

@admin.register(PomodoroSession)
class PomodoroSessionAdmin(admin.ModelAdmin):
    list_display = ('task', 'start_time', 'duration_minutes', 'completed')
    list_filter = ('completed', 'start_time')

class HabitLogInline(admin.TabularInline):
    model = HabitLog
    extra = 1

@admin.register(Habit)
class HabitAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'frequency', 'target_per_day', 'is_active')
    list_filter = ('frequency', 'is_active')
    search_fields = ('name', 'user__username')
    inlines = [HabitLogInline]

@admin.register(HabitLog)
class HabitLogAdmin(admin.ModelAdmin):
    list_display = ('habit', 'date', 'count', 'completed')
    list_filter = ('completed', 'date')
