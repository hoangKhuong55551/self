"""
Thêm nhanh từ thanh Ctrl+K bằng một dòng chữ.

Giao dịch (bắt đầu bằng - hoặc +):
    -50k cafe sáng                chi 50.000đ, đoán danh mục theo chữ, ví hay dùng nhất
    +15tr lương @vcb hôm qua      thu 15.000.000đ vào ví "VCB", ngày hôm qua
    -1.200.000 #nhà ở 05/11       chi 1.200.000đ, danh mục "Nhà ở & Hoá đơn", ngày 05/11
Task (bắt đầu bằng "task:", "t:" hoặc "việc:"):
    task: nộp báo cáo thứ 6 !     hạn thứ Sáu tới, "!" = quan trọng & khẩn cấp
    t: ôn thi #học kỳ 1 mai       gắn vào mục tiêu "Học kỳ 1", hạn ngày mai

Quy ước:
  - Ngày chỉ được đọc ở CUỐI câu ("gọi chị Mai" vẫn là tên task, không phải "ngày mai").
  - @ví / #danh mục / #mục tiêu khớp được tên nhiều từ ("#mua sắm", "@tiền mặt").
  - Lệnh task bắt buộc có dấu ":" để gõ "task ..."/"việc ..." vẫn là tìm kiếm bình thường.

parse() chỉ đọc, không ghi gì: dùng cho cả xem trước lẫn lưu thật (commit()).
"""
import re
import unicodedata
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone

from core.templatetags.core_tags import currency_vn

INBOX_GOAL = 'Việc lặt vặt'

UNIT_RE = re.compile(r'^(?P<num>\d+(?:[.,]\d+)?)(?P<unit>k|nghìn|ngàn|ng|tr|triệu|trieu|m)(?P<tail>\d{1,3})?$', re.I)
GROUPED_RE = re.compile(r'^\d{1,3}(?P<sep>[.,])\d{3}(?:(?P=sep)\d{3})*$')  # 1.200.000 / 1,200,000
DATE_RE = re.compile(r'^(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?$')
TASK_RE = re.compile(r'^(task|t|viec)\s*:\s*', re.I)
WEEKDAYS = {'2': 0, '3': 1, '4': 2, '5': 3, '6': 4, '7': 5}
MAX_TAG_WORDS = 5


def fold(text):
    """Bỏ dấu, viết thường: 'Ăn uống' -> 'an uong'."""
    text = unicodedata.normalize('NFD', text or '')
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    return text.replace('đ', 'd').replace('Đ', 'D').lower().strip()


def _vnd(value):
    return currency_vn(value) + ' đ'


def parse_amount(token):
    """
    '50k' -> 50000, '1tr2' -> 1200000, '1.5tr' -> 1500000, '1.200.000' -> 1200000, '200000' -> 200000.
    Số có phần thập phân mà không có đơn vị ('1.5', '2,5') là mơ hồ -> None (báo lỗi, không đoán).
    """
    token = re.sub(r'(đ|d|vnd)$', '', token.strip(), flags=re.I)
    try:
        m = UNIT_RE.match(token)
        if m:
            num, unit, tail = Decimal(m.group('num').replace(',', '.')), m.group('unit').lower(), m.group('tail')
            if unit in ('tr', 'triệu', 'trieu', 'm'):
                value = num * 1_000_000 + (Decimal('0.' + tail) * 1_000_000 if tail else 0)
            elif tail:
                return None  # "1k2" không rõ nghĩa
            else:
                value = num * 1000
        elif token.isdigit():
            value = Decimal(token)
        elif GROUPED_RE.match(token):
            value = Decimal(re.sub(r'[.,]', '', token))
        else:
            return None
    except InvalidOperation:
        return None
    value = value.quantize(Decimal('1'))
    return value if value > 0 else None


def _date_from(phrase, today, future):
    """Một cụm (đã bỏ dấu) -> ngày, hoặc None nếu không phải cụm chỉ ngày."""
    fixed = {'hom nay': 0, 'hom qua': -1, 'hom kia': -2, 'ngay mai': 1, 'mai': 1}
    if phrase in fixed:
        return today + timedelta(days=fixed[phrase])
    m = re.fullmatch(r'(?:thu |t)([2-7])', phrase)
    if m:
        return _weekday(today, WEEKDAYS[m.group(1)], future)
    if phrase in ('chu nhat', 'cn'):
        return _weekday(today, 6, future)
    m = DATE_RE.match(phrase)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), m.group(3)
        explicit_year = bool(year)
        year = (int(year) + (2000 if len(year) == 2 else 0)) if year else today.year
        try:
            found = today.replace(year=year, month=month, day=day)
            # Hạn task "05/01" gõ vào tháng 11 là tháng 1 năm sau
            if future and not explicit_year and found < today:
                found = found.replace(year=year + 1)
            return found
        except ValueError:
            return None
    return None


def _take_date(words, today, future):
    """Cụm chỉ ngày ở CUỐI câu (2 từ rồi 1 từ). Trả về (ngày | None, các từ còn lại)."""
    for size in (2, 1):
        if len(words) >= size:
            if size == 1 and words[-1] != words[-1].lower() and fold(words[-1]) == 'mai':
                continue  # "Mai" viết hoa là tên người ("gọi chị Mai"); "mai"/"ngày mai" mới là ngày
            found = _date_from(fold(' '.join(words[-size:])), today, future)
            if found:
                return found, words[:-size]
    return None, words


def _weekday(today, target, future):
    """future: ngày đó sắp tới (hôm nay nếu trùng). Ngược lại: ngày đó vừa qua (hôm nay nếu trùng)."""
    if future:
        return today + timedelta(days=(target - today.weekday()) % 7)
    return today - timedelta(days=(today.weekday() - target) % 7)


def _match(query, objects, attr):
    q = fold(query)
    for test in (lambda n: n == q, lambda n: n.startswith(q), lambda n: q in n):
        found = [o for o in objects if test(fold(getattr(o, attr)))]
        if found:
            return min(found, key=lambda o: len(getattr(o, attr)))
    return None


def _take_named(words, prefix, objects, attr='name'):
    """
    '@tiền mặt' / '#mua sắm': khớp tên nhiều từ, ưu tiên cụm dài nhất trùng khớp hoàn toàn.
    Trả về (object | None, chuỗi người dùng gõ | None, các từ còn lại).
    """
    for i, w in enumerate(words):
        if not (w.startswith(prefix) and len(w) > 1):
            continue
        tail = [w[1:]]
        for nxt in words[i + 1:i + MAX_TAG_WORDS]:
            if nxt[:1] in ('@', '#'):
                break
            tail.append(nxt)
        names = {fold(getattr(o, attr)): o for o in objects}
        for size in range(len(tail), 0, -1):
            phrase = fold(' '.join(tail[:size]))
            if phrase in names:
                return names[phrase], ' '.join(tail[:size]), words[:i] + words[i + size:]
        # Không trùng hoàn toàn: cụm dài nhất là phần đầu của một tên ("#học kỳ" -> "Học kỳ 1")
        for size in range(len(tail), 1, -1):
            phrase = fold(' '.join(tail[:size]))
            starts = [o for o in objects if fold(getattr(o, attr)).startswith(phrase + ' ')]
            if starts:
                return (min(starts, key=lambda o: len(getattr(o, attr))), ' '.join(tail[:size]),
                        words[:i] + words[i + size:])
        # Cuối cùng: khớp theo từ đầu tiên (tiền tố / chứa)
        return _match(tail[0], objects, attr), tail[0], words[:i] + words[i + 1:]
    return None, None, words


# Từ khoá thường gặp -> tên (đã bỏ dấu) của các danh mục mặc định
CATEGORY_KEYWORDS = {
    'an uong': ['cafe', 'ca phe', 'cf', 'tra sua', 'com', 'pho', 'bun', 'banh', 'an sang', 'an trua', 'an toi',
                'an vat', 'lau', 'nhau', 'do an', 'tra da', 'sinh to', 'kem'],
    'di chuyen': ['grab', 'be', 'xanh sm', 'xang', 'taxi', 'gui xe', 'bus', 've xe', 'gojek', 'sua xe'],
    'mua sam': ['shopee', 'lazada', 'tiki', 'tiktok shop', 'quan ao', 'giay', 'ao', 'quan', 'my pham'],
    'nha o & hoa don': ['tien dien', 'tien nuoc', 'internet', 'wifi', 'tien nha', 'thue nha', 'gas', 'dien thoai'],
    'giai tri': ['phim', 'xem phim', 'netflix', 'game', 'spotify', 'karaoke', 'du lich', 'concert'],
    'suc khoe': ['thuoc', 'kham', 'gym', 'bac si', 'benh vien', 'nha khoa', 'yoga'],
    'hoc tap': ['sach', 'hoc phi', 'khoa hoc', 'tai lieu', 'photo'],
    'luong': ['luong', 'salary'],
    'freelance': ['freelance', 'du an', 'job'],
    'thu nhap khac': ['thuong', 'bonus', 'li xi', 'qua', 'hoan tien'],
}


def _guess_category(note, categories):
    """Danh mục có tên nằm trong ghi chú; không có thì dò theo từ khoá thường gặp."""
    text = ' ' + fold(note) + ' '
    best = None
    for c in categories:
        name = fold(c.name)
        if (' ' + name + ' ') in text and (not best or len(name) > len(fold(best.name))):
            best = c
    if best:
        return best
    by_name = {fold(c.name): c for c in categories}
    for cat_name, keywords in CATEGORY_KEYWORDS.items():
        if cat_name in by_name and any((' ' + k + ' ') in text for k in keywords):
            return by_name[cat_name]
    return None


def detect_kind(text):
    t = (text or '').strip()
    if re.match(r'^[-+]\s*\d', t):
        return 'transaction'
    if TASK_RE.match(fold(t)) and TASK_RE.sub('', fold(t)):
        return 'task'
    return None


def parse(user, text):
    kind = detect_kind(text)
    if kind == 'transaction':
        return _parse_transaction(user, text.strip())
    if kind == 'task':
        return _parse_task(user, text.strip())
    return None


def _fail(kind, error):
    return {'kind': kind, 'ok': False, 'error': error}


def _parse_transaction(user, text):
    from finance.models import Category, Transaction, Wallet

    today = timezone.localdate()
    sign, words = text[0], text[1:].split()
    if not words:
        return _fail('transaction', 'Thiếu số tiền, ví dụ: -50k cafe')
    amount = parse_amount(words[0])
    if amount is None:
        return _fail('transaction', f'Không hiểu số tiền "{words[0]}". Ví dụ: 50k, 1tr2, 1.200.000')
    words = words[1:]
    ttype = Transaction.TransactionType.INCOME if sign == '+' else Transaction.TransactionType.EXPENSE

    wallets = list(Wallet.objects.filter(user=user, is_active=True))
    if not wallets:
        return _fail('transaction', 'Bạn chưa có ví nào. Tạo ví trước ở Tài chính → Ví.')
    categories = list(Category.objects.filter(user=user, type=ttype))

    wallet, wallet_q, words = _take_named(words, '@', wallets)
    if wallet_q and not wallet:
        return _fail('transaction', f'Không có ví nào tên "{wallet_q}".')
    category, cat_q, words = _take_named(words, '#', categories)
    if cat_q and not category:
        return _fail('transaction', f'Không có danh mục {"thu" if sign == "+" else "chi"} nào tên "{cat_q}".')
    date, words = _take_date(words, today, future=False)
    date = date or today
    if date > today:
        return _fail('transaction', 'Ngày giao dịch không được ở tương lai.')
    note = ' '.join(words).strip()

    if not wallet:
        # Ví dùng nhiều nhất 60 ngày gần đây
        wallet = (Wallet.objects.filter(user=user, is_active=True)
                  .annotate(n=Count('transactions', filter=Q(transactions__date__gte=today - timedelta(days=60))))
                  .order_by('-n', 'pk').first())
    category = category or _guess_category(note, categories)

    label = 'Thu' if sign == '+' else 'Chi'
    parts = [wallet.name, category.name if category else 'Chưa phân loại', date.strftime('%d/%m/%Y')]
    return {
        'kind': 'transaction', 'ok': True,
        'title': f'{label} {_vnd(amount)}' + (f' · {note}' if note else ''),
        'subtitle': ' · '.join(parts) + ' — Enter để lưu',
        'data': {'transaction_type': ttype, 'amount': amount, 'wallet': wallet, 'category': category,
                 'date': date, 'note': note},
    }


def _parse_task(user, text):
    from productivity.models import Goal, Task

    today = timezone.localdate()
    words = text.split(':', 1)[1].split()  # detect_kind đã kiểm tra tiền tố "task:" / "t:" / "việc:"

    # "!" đứng riêng ở bất kỳ đâu = quan trọng & khẩn cấp
    urgent = any(set(w) == {'!'} for w in words)
    words = [w for w in words if set(w) != {'!'}]

    goals = list(Goal.objects.filter(user=user).exclude(status=Goal.Status.ARCHIVED))
    goal, goal_q, words = _take_named(words, '#', goals, attr='title')
    if goal_q and not goal:
        return _fail('task', f'Không có mục tiêu nào tên "{goal_q}".')
    due, words = _take_date(words, today, future=True)
    if due and due < today:
        return _fail('task', f'Hạn {due:%d/%m/%Y} đã qua. Ghi ngày sắp tới, ví dụ: mai, thứ 6, 20/11.')
    title = ' '.join(words).strip()
    if not title:
        return _fail('task', 'Thiếu tên công việc, ví dụ: task: nộp báo cáo thứ 6')

    quadrant = Task.Quadrant.DO if urgent else Task.Quadrant.SCHEDULE
    parts = [f'Mục tiêu: {goal.title if goal else INBOX_GOAL}', f'Hạn {due:%d/%m/%Y}' if due else 'Không có hạn']
    if urgent:
        parts.append('Khẩn cấp')
    return {
        'kind': 'task', 'ok': True,
        'title': f'Tạo task: {title}',
        'subtitle': ' · '.join(parts) + ' — Enter để lưu',
        'data': {'title': title, 'goal': goal, 'due': due, 'quadrant': quadrant},
    }


def commit(user, parsed):
    """Lưu kết quả parse(). Trả về (thông báo, url để xem)."""
    data = parsed['data']
    if parsed['kind'] == 'transaction':
        from finance.services import record_transaction

        record_transaction(user, **data)
        return f'Đã ghi: {parsed["title"]}', reverse('finance:transaction_list')

    from productivity.models import Goal, Task

    goal = data['goal']
    if goal is None:
        goal, _ = Goal.objects.get_or_create(
            user=user, title=INBOX_GOAL,
            defaults={'description': 'Task thêm nhanh từ Ctrl+K không gắn mục tiêu nào.', 'status': Goal.Status.IN_PROGRESS},
        )
    task = Task.objects.create(goal=goal, title=data['title'], due_date=data['due'], quadrant=data['quadrant'])
    goal.recalculate_progress()
    return f'Đã tạo task: {task.title}', reverse('productivity:kanban_board')
