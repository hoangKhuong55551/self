"""
File lịch iCalendar (.ics) để Google Calendar / Apple / Outlook đăng ký theo link bí mật.

Gồm: hạn task (có giờ thì là sự kiện có giờ), hạn mục tiêu, khoản định kỳ dự kiến, hẹn trả nợ,
hạn quỹ tiết kiệm (sự kiện cả ngày) và buổi học (lặp hằng tuần bằng RRULE).
Định dạng theo RFC 5545: CRLF, gập dòng dài 75 byte, escape \\ ; , xuống dòng.
"""
import secrets
from datetime import datetime, timedelta, timezone as dt_timezone

from django.conf import settings
from django.utils import timezone

PAST_DAYS = 30      # vẫn thấy việc vừa quá hạn
FUTURE_DAYS = 180   # khoảng nửa năm tới


def new_token():
    return secrets.token_urlsafe(24)


def _escape(text):
    return (str(text).replace('\\', '\\\\').replace(';', '\\;').replace(',', '\\,')
            .replace('\r\n', '\\n').replace('\n', '\\n'))


def _fold(line):
    """Gập dòng > 75 byte (UTF-8), không cắt giữa ký tự nhiều byte."""
    out, current = [], ''
    for ch in line:
        limit = 75 if not out else 74  # dòng tiếp theo bắt đầu bằng 1 dấu cách
        if len((current + ch).encode('utf-8')) > limit:
            out.append(current)
            current = ch
        else:
            current += ch
    out.append(current)
    return '\r\n '.join(out)


def _utc(dt):
    return dt.astimezone(dt_timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def _local_dt(day, time):
    return timezone.make_aware(datetime.combine(day, time), timezone.get_default_timezone())


def _event(uid, summary, description, start, end, all_day=False, rrule=None, url=''):
    lines = ['BEGIN:VEVENT', f'UID:{uid}', f'DTSTAMP:{_utc(timezone.now())}']
    if all_day:
        lines += [f'DTSTART;VALUE=DATE:{start:%Y%m%d}', f'DTEND;VALUE=DATE:{end:%Y%m%d}']
    else:
        lines += [f'DTSTART:{_utc(start)}', f'DTEND:{_utc(end)}']
    if rrule:
        lines.append(f'RRULE:{rrule}')
    lines.append(f'SUMMARY:{_escape(summary)}')
    if description:
        lines.append(f'DESCRIPTION:{_escape(description)}')
    if url:
        lines.append(f'URL:{url}')
    lines.append('END:VEVENT')
    return lines


def build_ics(user, base_url, today=None):
    from academic.services_schedule import sessions_for_user
    from productivity.models import Task

    from .calendar import month_events

    today = today or timezone.localdate()
    first, last = today - timedelta(days=PAST_DAYS), today + timedelta(days=FUTURE_DAYS)
    host = base_url.split('//')[-1].split('/')[0] or 'lifeos'
    lines = [
        'BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Life OS//Lich ca nhan//VI', 'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH', f'X-WR-CALNAME:{_escape("Life OS · " + user.get_username())}',
        f'X-WR-TIMEZONE:{settings.TIME_ZONE}', 'REFRESH-INTERVAL;VALUE=DURATION:PT1H',
    ]

    # Task có giờ hạn: sự kiện 30 phút tại giờ đó (month_events chỉ có ngày)
    timed = {t.pk: t for t in Task.objects.filter(goal__user=user, due_date__range=[first, last], due_time__isnull=False)}
    for i, e in enumerate(month_events(user, first, last)):
        if e['kind'] == 'class':
            continue  # buổi học xuất ra bằng RRULE bên dưới
        title = ('✓ ' if e['done'] else '') + e['title']
        desc = f"{e['kind_label']}" + (f" · {e['subtitle']}" if e['subtitle'] else '')
        url = base_url + e['url'] if e['url'] else ''
        task_id = e['ref'] if e['kind'] == 'task' else None
        if task_id in timed:
            start = _local_dt(e['date'], timed[task_id].due_time)
            lines += _event(f'task-{task_id}@{host}', title, desc, start, start + timedelta(minutes=30), url=url)
        else:
            uid = f"{e['kind']}-{e['date']:%Y%m%d}-{i}@{host}" if e['kind'] != 'task' else f'task-{task_id}@{host}'
            lines += _event(uid, title, desc, e['date'], e['date'] + timedelta(days=1), all_day=True, url=url)

    for s in sessions_for_user(user):
        sem = s.course.semester
        start_day = max(sem.start_date or today - timedelta(days=PAST_DAYS), today - timedelta(days=PAST_DAYS))
        start_day += timedelta(days=(s.weekday - start_day.weekday()) % 7)
        end_day = sem.end_date or last
        if start_day > end_day:
            continue
        until = _utc(_local_dt(end_day, s.end_time))
        start = _local_dt(start_day, s.start_time)
        end = _local_dt(start_day, s.end_time)
        desc = ' · '.join(x for x in (s.room and f'Phòng {s.room}', s.note) if x)
        lines += _event(f'class-{s.pk}@{host}', f'📚 {s.course.name}', desc, start, end,
                        rrule=f'FREQ=WEEKLY;UNTIL={until}', url=base_url + '/academic/schedule/')

    lines.append('END:VCALENDAR')
    return '\r\n'.join(_fold(line) for line in lines) + '\r\n'
