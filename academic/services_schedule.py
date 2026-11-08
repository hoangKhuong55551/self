"""Thời khoá biểu: các buổi học diễn ra trong một ngày / một khoảng ngày."""
from datetime import timedelta

from django.db.models import Q

from .models import ClassSession


def sessions_for_user(user):
    """Buổi học còn hiệu lực: môn chưa hoàn thành, thuộc học kỳ hiện tại hoặc học kỳ có khai báo ngày."""
    return list(ClassSession.objects.filter(
        course__semester__user=user, course__is_completed=False,
    ).filter(
        Q(course__semester__is_current=True) | Q(course__semester__start_date__isnull=False)
    ).select_related('course__semester'))


def sessions_on(user, day, sessions=None):
    """Buổi học trong ngày `day`, theo giờ bắt đầu."""
    sessions = sessions_for_user(user) if sessions is None else sessions
    return sorted((s for s in sessions if s.runs_on(day)), key=lambda s: s.start_time)


def sessions_between(user, first, last):
    """[(ngày, buổi học)] trong khoảng [first, last]."""
    sessions = sessions_for_user(user)
    out, day = [], first
    while day <= last:
        out.extend((day, s) for s in sessions_on(user, day, sessions))
        day += timedelta(days=1)
    return out
