"""
Huy hiệu thành tích. Mỗi huy hiệu đo một con số từ dữ liệu sẵn có;
đạt ngưỡng thì mở khoá (lưu vào UserAchievement) và thưởng XP một lần.
"""
from dataclasses import dataclass
from typing import Callable

from django.db.models import Sum
from django.utils import timezone


@dataclass(frozen=True)
class Achievement:
    code: str
    title: str
    description: str
    icon: str
    tier: str          # bronze / silver / gold, quyết định màu huy hiệu
    target: int
    xp: int
    measure: Callable  # measure(user) -> int


def _tasks_done(user):
    from productivity.models import Task
    return Task.objects.filter(goal__user=user, status='done').count()


def _pomodoros(user):
    from productivity.models import PomodoroSession
    return PomodoroSession.objects.filter(task__goal__user=user, completed=True).count()


def _focus_hours(user):
    from productivity.models import PomodoroSession
    minutes = PomodoroSession.objects.filter(
        task__goal__user=user, completed=True
    ).aggregate(total=Sum('duration_minutes'))['total'] or 0
    return minutes // 60


def _longest_streak(user):
    return user.profile.longest_streak if hasattr(user, 'profile') else 0


def _checkins(user):
    from productivity.models import HabitLog
    return HabitLog.objects.filter(habit__user=user, completed=True).count()


def _media_done(*types):
    def measure(user):
        from library.models import MediaItem
        return MediaItem.objects.filter(user=user, status='done', media_type__in=types).count()
    return measure


def _level(user):
    return user.profile.level if hasattr(user, 'profile') else 1


def _transactions(user):
    from finance.models import Transaction
    return Transaction.objects.filter(user=user).count()


def _notes(user):
    from academic.models import Note
    return Note.objects.filter(user=user).count()


ACHIEVEMENTS = [
    Achievement('first_task', 'Khởi động', 'Hoàn thành task đầu tiên', 'bi-flag-fill', 'bronze', 1, 10, _tasks_done),
    Achievement('tasks_25', 'Người thực thi', 'Hoàn thành 25 task', 'bi-check2-all', 'silver', 25, 50, _tasks_done),
    Achievement('tasks_100', 'Cỗ máy năng suất', 'Hoàn thành 100 task', 'bi-lightning-charge-fill', 'gold', 100, 150, _tasks_done),
    Achievement('pomodoro_10', 'Tập trung', 'Hoàn thành 10 phiên Pomodoro', 'bi-stopwatch-fill', 'bronze', 10, 20, _pomodoros),
    Achievement('focus_50h', 'Deep Work', 'Tích luỹ 50 giờ tập trung', 'bi-hourglass-split', 'gold', 50, 150, _focus_hours),
    Achievement('streak_7', 'Một tuần bền bỉ', 'Giữ một thói quen 7 ngày liên tiếp', 'bi-fire', 'bronze', 7, 30, _longest_streak),
    Achievement('streak_30', 'Thói quen thép', 'Giữ một thói quen 30 ngày liên tiếp', 'bi-gem', 'gold', 30, 150, _longest_streak),
    Achievement('checkins_100', 'Trăm lần như một', '100 lượt check-in thói quen', 'bi-calendar2-check-fill', 'silver', 100, 60, _checkins),
    Achievement('book_1', 'Mọt sách tập sự', 'Đọc xong cuốn sách đầu tiên', 'bi-book-fill', 'bronze', 1, 15, _media_done('book')),
    Achievement('books_10', 'Mọt sách', 'Đọc xong 10 cuốn sách', 'bi-bookshelf', 'silver', 10, 80, _media_done('book')),
    Achievement('cinephile_20', 'Tín đồ điện ảnh', 'Xem xong 20 phim lẻ hoặc phim bộ', 'bi-film', 'silver', 20, 60, _media_done('movie', 'series')),
    Achievement('gamer_5', 'Game thủ', 'Phá đảo 5 game', 'bi-controller', 'silver', 5, 50, _media_done('game')),
    Achievement('level_5', 'Lên tầm', 'Đạt level 5', 'bi-star-fill', 'silver', 5, 0, _level),
    Achievement('level_10', 'Huyền thoại', 'Đạt level 10', 'bi-trophy-fill', 'gold', 10, 0, _level),
    Achievement('ledger_50', 'Kế toán cá nhân', 'Ghi 50 giao dịch', 'bi-journal-bookmark-fill', 'bronze', 50, 30, _transactions),
    Achievement('notes_20', 'Bộ não thứ hai', 'Viết 20 ghi chú', 'bi-lightbulb-fill', 'bronze', 20, 30, _notes),
]

ACHIEVEMENTS_BY_CODE = {a.code: a for a in ACHIEVEMENTS}


def evaluate_achievements(user):
    """
    Tính tiến độ mọi huy hiệu, mở khoá cái mới đạt ngưỡng.
    Trả về (danh sách tiến độ, danh sách huy hiệu vừa mở khoá).
    """
    from .models import UserAchievement

    unlocked = dict(UserAchievement.objects.filter(user=user).values_list('code', 'unlocked_at'))
    measured = {}
    progress, newly_unlocked = [], []

    for ach in ACHIEVEMENTS:
        # Nhiều huy hiệu dùng chung một phép đo, chỉ query một lần
        if ach.measure not in measured:
            measured[ach.measure] = ach.measure(user)
        value = measured[ach.measure]

        if ach.code not in unlocked and value >= ach.target:
            _, created = UserAchievement.objects.get_or_create(user=user, code=ach.code)
            if created:
                unlocked[ach.code] = timezone.now()
                newly_unlocked.append(ach)
                if ach.xp and hasattr(user, 'profile'):
                    user.profile.award_xp_once(f'achievement:{ach.code}', ach.xp, f'Huy hiệu: {ach.title}')

        progress.append({
            'achievement': ach,
            'value': min(value, ach.target),
            'percent': min(round(value / ach.target * 100), 100),
            'unlocked_at': unlocked.get(ach.code),
        })

    return progress, newly_unlocked
