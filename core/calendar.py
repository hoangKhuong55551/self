"""
Lịch tổng hợp: gom mọi thứ có ngày tháng của các phân hệ vào một tháng.

Mỗi sự kiện: {'date', 'kind', 'title', 'subtitle', 'icon', 'tone', 'url', 'done'}
"""
import calendar as pycal
from collections import defaultdict
from datetime import date, timedelta

from django.db.models import Sum
from django.urls import reverse

from core.templatetags.core_tags import currency_vn

KINDS = {
    'class': ('Lịch học', 'bi-mortarboard', 'success'),
    'task': ('Task', 'bi-check2-square', 'primary'),
    'goal': ('Mục tiêu', 'bi-bullseye', 'warning'),
    'recurring': ('Định kỳ', 'bi-arrow-repeat', 'info'),
    'debt': ('Vay / cho mượn', 'bi-people', 'danger'),
    'saving': ('Tiết kiệm', 'bi-piggy-bank', 'warning'),
}


def _vnd(value):
    return currency_vn(value) + ' đ'


def _event(day, kind, title, subtitle='', url='', done=False, ref=None):
    label, icon, tone = KINDS[kind]
    return {'date': day, 'kind': kind, 'kind_label': label, 'title': title, 'subtitle': subtitle,
            'icon': icon, 'tone': tone, 'url': url, 'done': done, 'ref': ref}


def month_events(user, first, last):
    from finance.models import Debt, SavingGoal, Subscription, Transaction
    from productivity.models import Goal, Task

    events = []

    for t in Task.objects.filter(goal__user=user, due_date__range=[first, last]).select_related('goal'):
        when = f'{t.due_time:%H:%M} · ' if t.due_time else ''
        events.append(_event(t.due_date, 'task', t.title, when + t.goal.title,
                             reverse('productivity:task_edit', args=[t.pk]), done=t.status == 'done', ref=t.pk))

    for g in Goal.objects.filter(user=user, deadline__range=[first, last]).exclude(status='archived'):
        events.append(_event(g.deadline, 'goal', g.title, f'Hạn mục tiêu · {g.progress:.0f}%',
                             reverse('productivity:goal_list'), done=g.status == 'completed'))

    # Khoản định kỳ: kỳ đã ghi (giao dịch tự động) + các kỳ sắp tới theo chu kỳ
    for txn in Transaction.objects.filter(
        user=user, source=Transaction.Source.SUBSCRIPTION, date__range=[first, last], subscription__isnull=False,
    ).select_related('subscription'):
        sign = '+' if txn.transaction_type == 'income' else '-'
        events.append(_event(txn.date, 'recurring', txn.subscription.name, f'{sign}{_vnd(txn.amount)} · đã ghi',
                             reverse('finance:subscription_list'), done=True))
    for sub in Subscription.objects.filter(user=user, is_active=True, next_billing_date__lte=last):
        day = sub.next_billing_date
        # Đủ số bước để tới tháng đang xem dù ở xa (chu kỳ ngắn nhất là 1 tuần), có chặn trên
        for _ in range(min((last - day).days // 7 + 2, 5000)):
            if day > last:
                break
            if day >= first:
                sign = '+' if sub.is_income else '-'
                events.append(_event(day, 'recurring', sub.name, f'{sign}{_vnd(sub.amount)} · dự kiến',
                                     reverse('finance:subscription_list')))
            day = sub.billing_date_after(day)

    for d in Debt.objects.filter(user=user, due_date__range=[first, last]).annotate(_paid_sum=Sum('payments__amount')):
        d._paid = d._paid_sum or 0  # một truy vấn cho cả tháng thay vì mỗi khoản một lần
        events.append(_event(d.due_date, 'debt', d.title, f'Còn {_vnd(d.remaining)}',
                             reverse('finance:debt_list'), done=d.is_settled))

    for s in SavingGoal.objects.filter(user=user, deadline__range=[first, last]):
        events.append(_event(s.deadline, 'saving', s.name, 'Hạn quỹ tiết kiệm', reverse('finance:saving_goal_list')))

    from academic.services_schedule import sessions_between
    for day, s in sessions_between(user, first, last):
        room = f' · {s.room}' if s.room else ''
        events.append(_event(day, 'class', s.course.name, f'{s.start_time:%H:%M}–{s.end_time:%H:%M}{room}',
                             reverse('academic:schedule')))

    events.sort(key=lambda e: (e['date'], e['done'], e['kind']))
    return events


def build_month(user, year, month, today):
    first = date(year, month, 1)
    last = date(year, month, pycal.monthrange(year, month)[1])
    events = month_events(user, first, last)
    by_day = defaultdict(list)
    for e in events:
        by_day[e['date']].append(e)

    # Lưới bắt đầu từ thứ Hai, đủ các tuần chứa tháng
    start = first - timedelta(days=first.weekday())
    end = last + timedelta(days=6 - last.weekday())
    weeks, day = [], start
    while day <= end:
        week = []
        for _ in range(7):
            week.append({'date': day, 'in_month': day.month == month, 'is_today': day == today,
                         'events': by_day.get(day, [])})
            day += timedelta(days=1)
        weeks.append(week)

    agenda = [{'date': d, 'is_today': d == today, 'is_past': d < today, 'events': by_day[d]} for d in sorted(by_day)]
    counts = defaultdict(int)
    for e in events:
        counts[e['kind']] += 1
    legend = [{'kind': k, 'label': v[0], 'icon': v[1], 'tone': v[2], 'count': counts.get(k, 0)} for k, v in KINDS.items()]
    return {'weeks': weeks, 'agenda': agenda, 'legend': legend, 'first': first, 'last': last, 'total': len(events)}
