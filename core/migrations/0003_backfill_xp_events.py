from django.db import migrations


def backfill(apps, schema_editor):
    """
    Đánh dấu các nguồn thưởng đã hoàn thành trước khi có sổ XP là "đã nhận"
    (amount=0) để bỏ check rồi check lại không cộng XP thêm lần nữa.
    """
    XPEvent = apps.get_model('core', 'XPEvent')
    Task = apps.get_model('productivity', 'Task')
    HabitLog = apps.get_model('productivity', 'HabitLog')
    MediaItem = apps.get_model('library', 'MediaItem')

    events = []
    for pk, user_id in Task.objects.filter(status='done').values_list('pk', 'goal__user_id'):
        events.append(XPEvent(user_id=user_id, key=f'task:{pk}', amount=0, reason='Backfill'))
    for pk, user_id in HabitLog.objects.filter(completed=True).values_list('pk', 'habit__user_id'):
        events.append(XPEvent(user_id=user_id, key=f'habitlog:{pk}', amount=0, reason='Backfill'))
    for pk, user_id in MediaItem.objects.filter(status='done').values_list('pk', 'user_id'):
        events.append(XPEvent(user_id=user_id, key=f'media:{pk}', amount=0, reason='Backfill'))
    XPEvent.objects.bulk_create(events, ignore_conflicts=True)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_xpevent'),
        ('productivity', '0001_initial'),
        ('library', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
