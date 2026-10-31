from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import MediaItem

# XP thưởng khi hoàn thành từng loại media
XP_REWARDS = {
    MediaItem.MediaType.BOOK: 30,
    MediaItem.MediaType.MOVIE: 10,
    MediaItem.MediaType.SERIES: 20,
    MediaItem.MediaType.GAME: 25,
}


@receiver(pre_save, sender=MediaItem)
def media_item_status_changed(sender, instance, **kwargs):
    """
    Khi MediaItem chuyển sang 'done': ghi nhận ngày hoàn thành, đẩy tiến độ lên 100%.
    Khi chuyển sang 'in_progress' lần đầu: ghi nhận ngày bắt đầu.
    """
    previous = None
    if instance.pk:
        previous = MediaItem.objects.filter(pk=instance.pk).values_list('status', flat=True).first()

    today = timezone.localdate()

    if instance.status == MediaItem.Status.IN_PROGRESS and not instance.started_on:
        instance.started_on = today

    if instance.status == MediaItem.Status.DONE and previous != MediaItem.Status.DONE:
        if not instance.finished_on:
            instance.finished_on = today
        if instance.progress_total:
            instance.progress_current = instance.progress_total


@receiver(post_save, sender=MediaItem)
def media_item_award_xp(sender, instance, **kwargs):
    # Mỗi mục chỉ được thưởng một lần, kể cả khi đổi trạng thái qua lại
    if instance.status != MediaItem.Status.DONE:
        return
    if hasattr(instance.user, 'profile'):
        instance.user.profile.award_xp_once(
            f'media:{instance.pk}', XP_REWARDS.get(instance.media_type, 10),
            f'Hoàn thành: {instance.title}'
        )
