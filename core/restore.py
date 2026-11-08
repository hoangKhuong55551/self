"""
Khôi phục dữ liệu từ file JSON do core.exports.export_json tạo ra.

An toàn:
  - Mọi khoá chính trong file được ánh xạ sang bản ghi MỚI; khoá ngoại chỉ trỏ tới bản ghi vừa
    khôi phục (hoặc user đang đăng nhập). File sửa tay cũng không chạm được dữ liệu người khác.
  - Trường file/ảnh bị bỏ trống: đường dẫn trong file không được trỏ tới file trên máy chủ.
  - Không gửi signal (bulk_create): không cộng XP lần nữa, không trừ HP vì vượt ngân sách...
  - Tất cả trong một transaction: lỗi giữa chừng thì không thay đổi gì.

Chế độ:
  - replace: xoá dữ liệu hiện tại của tài khoản rồi khôi phục y như bản sao lưu (kể cả XP, huy hiệu).
  - merge:   giữ dữ liệu hiện tại, thêm dữ liệu trong file; bỏ qua XP/huy hiệu/hồ sơ, gộp danh mục
             và thẻ trùng tên.
"""
import json

from django.apps import apps
from django.conf import settings
from django.db import IntegrityError, models, transaction

from .exports import USER_OWNED_MODELS

MAX_BYTES = 20 * 1024 * 1024
MAX_OBJECTS = 200_000

# Thứ tự tạo: bảng được trỏ tới đứng trước (khoá ngoại không bắt buộc trỏ ngược thì gắn sau)
RESTORE_ORDER = [
    'core.UserProfile', 'core.XPEvent', 'core.UserAchievement', 'core.WeeklyReflection',
    'finance.Wallet', 'finance.Category', 'finance.SavingGoal', 'finance.WishlistItem', 'finance.Subscription',
    'finance.Transaction', 'finance.Transfer', 'finance.Budget', 'finance.Debt', 'finance.DebtPayment',
    'finance.Asset', 'finance.WorkoutLog',
    'academic.Semester', 'academic.Course', 'academic.ClassSession', 'academic.Tag', 'academic.Note',
    'academic.CodeSnippet',
    'productivity.Goal', 'productivity.Task', 'productivity.PomodoroSession', 'productivity.Habit',
    'productivity.HabitLog',
    'library.MediaItem', 'library.LibraryGoal',
]
GAMIFICATION = {'core.UserProfile', 'core.XPEvent', 'core.UserAchievement'}
# Chế độ merge: bản ghi trùng "khoá tự nhiên" (ràng buộc duy nhất theo user) là cùng một thứ,
# nên trỏ vào bản ghi đã có thay vì tạo mới (danh mục mặc định, ví cùng tên, học kỳ cùng năm/kỳ...)
MERGE_BY = {
    'finance.Category': ('name', 'type'),
    'finance.Wallet': ('name',),
    'finance.Budget': ('category_id', 'month', 'year'),
    'academic.Semester': ('year', 'term'),
    'academic.Tag': ('name',),
    'core.WeeklyReflection': ('week_start',),
    'library.LibraryGoal': ('year', 'media_type'),
}


class RestoreError(Exception):
    pass


def load_backup(upload):
    if upload.size > MAX_BYTES:
        raise RestoreError('File quá lớn (tối đa 20 MB).')
    try:
        data = json.loads(upload.read().decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RestoreError('File không phải bản sao lưu JSON hợp lệ.')
    if not isinstance(data, dict) or not isinstance(data.get('models'), dict):
        raise RestoreError('File không đúng định dạng sao lưu của Life OS (thiếu "models").')
    total = sum(len(v) for v in data['models'].values() if isinstance(v, list))
    if total > MAX_OBJECTS:
        raise RestoreError('File có quá nhiều bản ghi.')
    return data


def summarize(data):
    """{nhãn model: số bản ghi} cho các model khôi phục được."""
    return {label: len(rows) for label, rows in data['models'].items()
            if label in RESTORE_ORDER and isinstance(rows, list) and rows}


def _wipe(user):
    """Xoá dữ liệu hiện tại (trừ hồ sơ) theo thứ tự ngược để không vướng khoá ngoại RESTRICT."""
    paths = dict(USER_OWNED_MODELS)
    for label in reversed(RESTORE_ORDER):
        if label == 'core.UserProfile' or label not in paths:
            continue
        apps.get_model(label).objects.filter(**{paths[label]: user}).delete()


def restore(user, data, mode='replace'):
    """Khôi phục; trả về {nhãn model: số bản ghi đã tạo}."""
    if mode not in ('replace', 'merge'):
        raise RestoreError('Chế độ không hợp lệ.')
    user_model_label = settings.AUTH_USER_MODEL.lower()
    id_map = {}      # label -> {pk cũ: pk mới}
    deferred = []    # (model, pk mới, tên trường, label đích, pk cũ đích)
    m2m_later = []   # (model, pk mới, tên trường, label đích, [pk cũ])
    counts = {}

    with transaction.atomic():
        if mode == 'replace':
            _wipe(user)
        for label in RESTORE_ORDER:
            rows = data['models'].get(label)
            if not isinstance(rows, list) or (mode == 'merge' and label in GAMIFICATION):
                continue
            model = apps.get_model(label)
            id_map[label] = {}
            existing = _merge_index(user, label) if mode == 'merge' else {}
            for row in rows:
                if not isinstance(row, dict) or not isinstance(row.get('fields'), dict):
                    continue
                new_pk = _restore_row(user, model, label, row, id_map, deferred, m2m_later,
                                      existing, user_model_label)
                if new_pk is not None:
                    id_map[label][row.get('pk')] = new_pk
                    counts[label] = counts.get(label, 0) + 1

        for model, pk, field, target, old in deferred:
            new = id_map.get(target, {}).get(old)
            if new is not None:
                model.objects.filter(pk=pk).update(**{f'{field}_id': new})
        for model, pk, field, target, olds in m2m_later:
            new_ids = [id_map.get(target, {}).get(o) for o in olds]
            getattr(model.objects.get(pk=pk), field).set([i for i in new_ids if i is not None])

        # Số dư ví khớp với lịch sử vừa khôi phục
        from finance.models import Wallet
        for wallet in Wallet.objects.filter(user=user):
            wallet.recalculate_balance()
    return counts


def _merge_index(user, label):
    keys = MERGE_BY.get(label)
    if not keys:
        return {}
    model = apps.get_model(label)
    return {tuple(getattr(o, k) for k in keys): o.pk for o in model.objects.filter(user=user)}


def _restore_row(user, model, label, row, id_map, deferred, m2m_later, existing, user_model_label):
    fields = row['fields']
    values, later, keep_dates = {}, [], {}
    for field in model._meta.concrete_fields:
        if field.primary_key or field.name not in fields:
            continue
        raw = fields[field.name]
        if isinstance(field, models.FileField):
            values[field.attname] = ''
            continue
        if field.is_relation:
            target = field.related_model._meta.label
            if target.lower() == user_model_label:
                values[field.attname] = user.pk
            elif raw is None:
                values[field.attname] = None
            elif target in id_map and raw in id_map[target]:
                values[field.attname] = id_map[target][raw]
            elif field.null:
                values[field.attname] = None
                if target not in id_map:  # bảng đích tạo sau: gắn lại ở cuối
                    later.append((field.name, target, raw))
            else:
                return None  # thiếu bản ghi bắt buộc (vd task của mục tiêu không có trong file)
            continue
        try:
            value = field.to_python(raw)
        except Exception:
            return None
        if getattr(field, 'auto_now_add', False) or getattr(field, 'auto_now', False):
            keep_dates[field.attname] = value
        values[field.attname] = value

    # Trường user thường là "user"; model sở hữu gián tiếp (task, buổi học...) đã có khoá ngoại ở trên
    if 'user' in {f.name for f in model._meta.concrete_fields}:
        values['user_id'] = user.pk

    if label == 'core.UserProfile':
        profile = model.objects.get_or_create(user=user)[0]
        for name in ('xp', 'hp', 'level', 'longest_streak'):
            if name in values:
                setattr(profile, name, values[name])
        profile.save(update_fields=['xp', 'hp', 'level', 'longest_streak'])
        return profile.pk

    keys = MERGE_BY.get(label)
    if existing and keys:
        match = existing.get(tuple(values.get(k) for k in keys))
        if match:
            return match

    obj = model(**values)
    try:
        with transaction.atomic():  # savepoint: bản ghi trùng ràng buộc thì bỏ qua, không hỏng cả lần khôi phục
            model.objects.bulk_create([obj])
    except IntegrityError:
        return None
    if keep_dates:
        model.objects.filter(pk=obj.pk).update(**{k: v for k, v in keep_dates.items() if v is not None})
    for name, target, old in later:
        deferred.append((model, obj.pk, name, target, old))
    for field in model._meta.many_to_many:
        olds = fields.get(field.name)
        if isinstance(olds, list) and olds:
            m2m_later.append((model, obj.pk, field.name, field.related_model._meta.label, olds))
    return obj.pk
