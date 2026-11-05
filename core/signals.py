from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in

from .models import UserProfile

User = get_user_model()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Tự động tạo UserProfile khi User mới được đăng ký."""
    if created:
        UserProfile.objects.create(user=instance)


@receiver(user_logged_in)
def touch_last_active(sender, request, user, **kwargs):
    """
    Ghi ngày hoạt động gần nhất khi đăng nhập.
    Dùng UPDATE một cột thay vì profile.save(): bản profile trong bộ nhớ có thể đã cũ,
    lưu cả bản ghi sẽ ghi đè XP/HP mới hơn (lỗi của handler save_user_profile trước đây).
    """
    from django.utils import timezone
    UserProfile.objects.filter(user=user).update(last_active=timezone.localdate())


# --- Xoá cache chuông nhắc hạn khi dữ liệu liên quan thay đổi ---
from django.db.models.signals import post_delete  # noqa: E402

from .notifications import invalidate_notifications  # noqa: E402


def _owner_id(instance):
    user_id = getattr(instance, 'user_id', None)
    if user_id is None and getattr(instance, 'goal_id', None):
        # Task không có user, lấy qua Goal (Goal có thể đã bị xoá cùng lúc)
        from productivity.models import Goal
        user_id = Goal.objects.filter(pk=instance.goal_id).values_list('user_id', flat=True).first()
    return user_id


def _invalidate_owner(sender, instance, **kwargs):
    invalidate_notifications(_owner_id(instance))


def connect_notification_signals():
    from finance.models import Budget, Subscription, Transaction
    from productivity.models import Goal, Task

    for model in (Task, Goal, Subscription, Budget, Transaction):
        uid = f'notifications-invalidate-{model._meta.label_lower}'
        post_save.connect(_invalidate_owner, sender=model, dispatch_uid=uid + '-save')
        post_delete.connect(_invalidate_owner, sender=model, dispatch_uid=uid + '-delete')
