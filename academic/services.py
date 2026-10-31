"""
Thống kê học tập: xu hướng GPA và thời gian tập trung theo môn học.
"""
from django.db.models import Count, Q, Sum

from .models import Course, Semester

# Thứ tự trong một năm học: HK1 -> HK2 -> Hè
TERM_ORDER = {
    Semester.Term.SPRING: 0,
    Semester.Term.FALL: 1,
    Semester.Term.SUMMER: 2,
}


def gpa_trend(user):
    """
    List các học kỳ theo thời gian, mỗi phần tử gồm GPA học kỳ và cGPA tích lũy tới kỳ đó.
    Bỏ qua học kỳ chưa có môn nào được chấm điểm.
    """
    semesters = sorted(
        Semester.objects.filter(user=user).prefetch_related('courses'),
        key=lambda s: (s.year, TERM_ORDER.get(s.term, 9)),
    )
    trend = []
    total_weighted = total_credits = 0.0
    for sem in semesters:
        graded = [c for c in sem.courses.all() if c.is_completed and c.grade is not None]
        credits = sum(c.credits for c in graded)
        if not credits:
            continue
        weighted = sum(c.grade * c.credits for c in graded)
        total_weighted += weighted
        total_credits += credits
        trend.append({
            'label': sem.name,
            'gpa': round(weighted / credits, 2),
            'cgpa': round(total_weighted / total_credits, 2),
        })
    return trend


def study_time_by_course(user, semester=None):
    """Tổng phút Pomodoro hoàn thành của các task gắn với từng môn học."""
    courses = Course.objects.filter(semester__user=user)
    if semester is not None:
        courses = courses.filter(semester=semester)
    done = Q(tasks__pomodoro_sessions__completed=True)
    return list(
        courses.annotate(
            focus_minutes=Sum('tasks__pomodoro_sessions__duration_minutes', filter=done),
            sessions=Count('tasks__pomodoro_sessions', filter=done),
        )
        .filter(focus_minutes__gt=0)
        .order_by('-focus_minutes')
    )
