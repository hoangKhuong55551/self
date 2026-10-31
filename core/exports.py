"""
Xuất dữ liệu cá nhân: một file JSON đầy đủ để sao lưu, và CSV theo từng phân hệ.
"""
import csv
import io
import json

from django.apps import apps
from django.core.serializers import serialize
from django.utils import timezone

# (model label, đường dẫn tới user) cho mọi dữ liệu thuộc về một người dùng
USER_OWNED_MODELS = [
    ('core.UserProfile', 'user'),
    ('core.XPEvent', 'user'),
    ('core.UserAchievement', 'user'),
    ('core.WeeklyReflection', 'user'),
    ('finance.Wallet', 'user'),
    ('finance.Category', 'user'),
    ('finance.Transaction', 'user'),
    ('finance.Budget', 'user'),
    ('finance.Subscription', 'user'),
    ('finance.WishlistItem', 'user'),
    ('finance.SavingGoal', 'user'),
    ('finance.Asset', 'user'),
    ('finance.WorkoutLog', 'user'),
    ('productivity.Goal', 'user'),
    ('productivity.Task', 'goal__user'),
    ('productivity.PomodoroSession', 'task__goal__user'),
    ('productivity.Habit', 'user'),
    ('productivity.HabitLog', 'habit__user'),
    ('academic.Semester', 'user'),
    ('academic.Course', 'semester__user'),
    ('academic.Tag', 'user'),
    ('academic.Note', 'user'),
    ('academic.CodeSnippet', 'user'),
    ('library.MediaItem', 'user'),
    ('library.LibraryGoal', 'user'),
]


def export_json(user):
    """Toàn bộ dữ liệu của user, nhóm theo model, dạng chuỗi JSON."""
    data = {
        'exported_at': timezone.now().isoformat(),
        'username': user.username,
        'models': {},
    }
    for label, user_path in USER_OWNED_MODELS:
        model = apps.get_model(label)
        queryset = model.objects.filter(**{user_path: user})
        data['models'][label] = json.loads(serialize('json', queryset))
    return json.dumps(data, ensure_ascii=False, indent=2)


def _transactions(user):
    from finance.models import Transaction
    rows = Transaction.objects.filter(user=user).select_related('wallet', 'category').order_by('-date')
    header = ['Ngày', 'Loại', 'Số tiền', 'Ví', 'Danh mục', 'Ghi chú']
    body = ([t.date, t.get_transaction_type_display(), t.amount, t.wallet.name,
             t.category.name if t.category else '', t.note] for t in rows)
    return header, body


def _tasks(user):
    from productivity.models import Task
    rows = Task.objects.filter(goal__user=user).select_related('goal').order_by('-id')
    header = ['Task', 'Mục tiêu', 'Trạng thái', 'Ma trận', 'Hạn', 'Hoàn thành lúc', 'Pomodoro']
    body = ([t.title, t.goal.title, t.get_status_display(), t.get_quadrant_display(), t.due_date or '',
             t.completed_at or '', f'{t.actual_pomodoros}/{t.estimated_pomodoros}'] for t in rows)
    return header, body


def _habits(user):
    from productivity.models import HabitLog
    rows = HabitLog.objects.filter(habit__user=user).select_related('habit').order_by('-date')
    header = ['Ngày', 'Thói quen', 'Số lần', 'Hoàn thành']
    body = ([log.date, log.habit.name, log.count, 'Có' if log.completed else 'Không'] for log in rows)
    return header, body


def _library(user):
    from library.models import MediaItem
    rows = MediaItem.objects.filter(user=user).order_by('media_type', 'title')
    header = ['Loại', 'Tên', 'Tác giả/Đạo diễn', 'Thể loại', 'Trạng thái', 'Tiến độ', 'Đánh giá', 'Bắt đầu', 'Hoàn thành', 'Cảm nhận']
    body = ([m.get_media_type_display(), m.title, m.creator, m.genre, m.status_label,
             f'{m.progress_current}/{m.progress_total} {m.progress_unit}' if m.progress_total else '',
             m.rating or '', m.started_on or '', m.finished_on or '', m.review] for m in rows)
    return header, body


def _notes(user):
    from academic.models import Note
    rows = Note.objects.filter(user=user).prefetch_related('tags').order_by('-updated_at')
    header = ['Tiêu đề', 'Nội dung', 'Tags', 'Cập nhật']
    body = ([n.title, n.content, ', '.join(t.name for t in n.tags.all()), n.updated_at] for n in rows)
    return header, body


CSV_EXPORTS = {
    'transactions': ('Giao dịch', 'bi-receipt', _transactions),
    'tasks': ('Task', 'bi-check2-square', _tasks),
    'habits': ('Nhật ký thói quen', 'bi-fire', _habits),
    'library': ('Thư viện', 'bi-collection-play', _library),
    'notes': ('Ghi chú', 'bi-journal-text', _notes),
}


def export_csv(user, kind):
    """CSV có BOM UTF-8 để Excel hiển thị đúng tiếng Việt."""
    header, body = CSV_EXPORTS[kind][2](user)
    buffer = io.StringIO()
    buffer.write('﻿')
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(body)
    return buffer.getvalue()
