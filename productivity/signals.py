from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Task, HabitLog


@receiver(pre_save, sender=Task)
def cache_previous_task_status(sender, instance, **kwargs):
    if instance.pk:
        try:
            instance._previous_status = Task.objects.get(pk=instance.pk).status
        except Task.DoesNotExist:
            instance._previous_status = None
    else:
        instance._previous_status = None


@receiver(post_save, sender=Task)
def task_status_changed(sender, instance, created, **kwargs):
    """
    Khi Task chuyển sang 'done':
      1. Ghi nhận thời gian hoàn thành
      2. Tính lại progress của Goal cha
      3. Cộng XP cho user (Gamification)
    """
    previous = getattr(instance, '_previous_status', None)
    current = instance.status

    if current == 'done' and previous != 'done':
        if not instance.completed_at:
            Task.objects.filter(pk=instance.pk).update(
                completed_at=timezone.now()
            )

        instance.goal.recalculate_progress()

        xp_reward = _calculate_task_xp(instance)
        if hasattr(instance.goal.user, 'profile'):
            instance.goal.user.profile.add_xp(xp_reward)

    elif previous == 'done' and current != 'done':
        instance.goal.recalculate_progress()


def _calculate_task_xp(task):
    base_xp = 10
    quadrant_bonus = {
        'do': 20,
        'schedule': 15,
        'delegate': 10,
        'eliminate': 5,
    }
    return base_xp + quadrant_bonus.get(task.quadrant, 0)


@receiver(post_save, sender=HabitLog)
def habit_completed_handler(sender, instance, created, **kwargs):
    """
    Khi HabitLog.completed = True:
      1. Cộng XP
      2. Cập nhật longest_streak
    """
    if not instance.completed:
        return

    user = instance.habit.user
    if hasattr(user, 'profile'):
        profile = user.profile
        profile.add_xp(5)

        current = instance.habit.current_streak
        if current > profile.longest_streak:
            profile.longest_streak = current
            profile.save(update_fields=['longest_streak'])
