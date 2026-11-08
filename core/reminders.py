"""
Nhắc việc qua thông báo đẩy. Chạy định kỳ bằng: python manage.py send_reminders --loop

  - Task có giờ hạn: nhắc trước REMINDER_MINUTES_BEFORE phút (không nhắc nếu đã trễ quá 2 giờ).
  - Tóm tắt buổi sáng (từ REMINDER_DIGEST_HOUR giờ): task hạn hôm nay / quá hạn, buổi học hôm nay,
    khoản định kỳ ngày mai, hẹn trả nợ hôm nay. Không có gì thì không gửi.
Mỗi lời nhắc có khoá riêng (ReminderLog): chạy lại bao nhiêu lần cũng không gửi trùng.
"""
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from core.templatetags.core_tags import currency_vn

STALE_AFTER = timedelta(hours=2)


def due_reminders(user, now):
    """[(khoá, tiêu đề, nội dung, url)] cần gửi lúc `now` (chưa lọc những cái đã gửi)."""
    from academic.services_schedule import sessions_on
    from finance.models import Debt, Subscription
    from productivity.models import Task

    local = timezone.localtime(now)
    today = local.date()
    out = []

    lead = timedelta(minutes=settings.REMINDER_MINUTES_BEFORE)
    timed = Task.objects.filter(
        goal__user=user, due_date__range=[today - timedelta(days=1), today + timedelta(days=1)],
        due_time__isnull=False,
    ).exclude(status='done')
    for t in timed:
        due = timezone.make_aware(datetime.combine(t.due_date, t.due_time), timezone.get_current_timezone())
        if due - lead <= now <= due + STALE_AFTER:
            out.append((f'task:{t.pk}:{t.due_date}:{t.due_time:%H%M}', f'⏰ {t.title}',
                        f'Hạn lúc {t.due_time:%H:%M}' + (' (đã tới giờ)' if now >= due else ''),
                        reverse('productivity:kanban_board')))

    if local.hour >= settings.REMINDER_DIGEST_HOUR:
        lines = []
        tasks = list(Task.objects.filter(goal__user=user, due_date__lte=today).exclude(status='done'))
        due_today = [t.title for t in tasks if t.due_date == today]
        overdue = sum(1 for t in tasks if t.due_date < today)
        if due_today:
            lines.append(f'{len(due_today)} việc hạn hôm nay: ' + ', '.join(due_today[:3]) + ('…' if len(due_today) > 3 else ''))
        if overdue:
            lines.append(f'{overdue} việc đã quá hạn')
        classes = sessions_on(user, today)
        if classes:
            lines.append('Học: ' + ', '.join(f'{s.course.name} {s.start_time:%H:%M}' for s in classes[:3]))
        tomorrow = today + timedelta(days=1)
        for s in Subscription.objects.filter(user=user, is_active=True, next_billing_date=tomorrow)[:3]:
            lines.append(f'Mai {"nhận" if s.is_income else "trả"} {s.name} {currency_vn(s.amount)} đ')
        for d in Debt.objects.filter(user=user, due_date=today)[:3]:
            if not d.is_settled:
                lines.append(f'Hẹn trả hôm nay: {d.title} còn {currency_vn(d.remaining)} đ')
        if lines:
            out.append((f'digest:{today}', '☀️ Hôm nay của bạn', '\n'.join(lines), reverse('core:calendar')))
    return out


def send_due_reminders(now=None):
    """Gửi mọi lời nhắc đến hạn cho mọi người dùng có thiết bị đăng ký. Trả về số lời nhắc đã gửi."""
    from .models import PushSubscription, ReminderLog
    from .push import send_push

    now = now or timezone.now()
    sent = 0
    user_ids = PushSubscription.objects.values_list('user_id', flat=True).distinct()
    for user in get_user_model().objects.filter(pk__in=user_ids, is_active=True):
        for key, title, body, url in due_reminders(user, now):
            try:
                with transaction.atomic():
                    # "Giành" trước khi gửi: hai tiến trình chạy song song cũng không gửi trùng
                    ReminderLog.objects.create(user=user, key=key)
            except IntegrityError:
                continue
            if send_push(user, title, body, url, tag=key):
                sent += 1
    return sent
