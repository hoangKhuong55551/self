"""
Nghiệp vụ tài chính dùng chung cho view, middleware và management command.
"""
import calendar
import csv
import io
import re
import unicodedata
from datetime import datetime
from decimal import Decimal, InvalidOperation

from dateutil.relativedelta import relativedelta
from django.db import transaction as db_transaction
from django.db.models import F, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from .models import Budget, Category, Transaction, Wallet

# Giới hạn số kỳ bù mỗi lần chạy, tránh vòng lặp vô hạn với dữ liệu hỏng
MAX_CATCH_UP_CYCLES = 60


def check_budget_and_penalize(user, txn):
    """Trừ HP nếu giao dịch chi tiêu làm vượt ngân sách tháng của danh mục."""
    if txn.transaction_type != Transaction.TransactionType.EXPENSE or not txn.category_id:
        return

    budget = Budget.objects.filter(
        user=user,
        category_id=txn.category_id,
        month=txn.date.month,
        year=txn.date.year,
    ).first()

    if budget and budget.is_over_budget:
        overspent_ratio = float((budget.spent - budget.amount) / budget.amount)
        hp_loss = min(int(overspent_ratio * 20), 30)
        if hp_loss > 0 and hasattr(user, 'profile'):
            user.profile.lose_hp(hp_loss)


def charge_due_subscriptions(subscriptions, today=None):
    """
    Tạo giao dịch cho mọi kỳ đến hạn (kể cả các kỳ bị bỏ lỡ) và trừ ví.
    Trả về số giao dịch đã tạo.
    """
    today = today or timezone.now().date()
    count = 0
    for sub in subscriptions.filter(is_active=True, next_billing_date__lte=today).select_related('user'):
        for _ in range(MAX_CATCH_UP_CYCLES):
            if sub.next_billing_date > today:
                break
            with db_transaction.atomic():
                txn = Transaction.objects.create(
                    user=sub.user,
                    wallet_id=sub.wallet_id,
                    category_id=sub.category_id,
                    transaction_type=Transaction.TransactionType.EXPENSE,
                    amount=sub.amount,
                    date=sub.next_billing_date,
                    note=f"[Tự động] Gia hạn: {sub.name}",
                    source=Transaction.Source.SUBSCRIPTION,
                    subscription=sub,
                )
                Wallet.objects.filter(pk=sub.wallet_id).update(balance=F('balance') - sub.amount)
                sub.advance_billing_date()
            check_budget_and_penalize(sub.user, txn)
            count += 1
    return count


def monthly_cashflow(user, months=12, today=None):
    """
    Thu/chi theo từng tháng trong `months` tháng gần nhất (kể cả tháng hiện tại),
    tháng không có giao dịch vẫn có mặt với giá trị 0.
    """
    today = today or timezone.now().date()
    first = today.replace(day=1) - relativedelta(months=months - 1)
    rows = (
        Transaction.objects.filter(user=user, date__gte=first, date__lte=today)
        .annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(
            income=Sum('amount', filter=Q(transaction_type=Transaction.TransactionType.INCOME)),
            expense=Sum('amount', filter=Q(transaction_type=Transaction.TransactionType.EXPENSE)),
        )
    )
    by_month = {r['month']: r for r in rows}
    result = []
    for i in range(months):
        month = first + relativedelta(months=i)
        row = by_month.get(month, {})
        income = row.get('income') or Decimal('0')
        expense = row.get('expense') or Decimal('0')
        result.append({
            'label': f'T{month.month}/{month.year % 100:02d}',
            'income': float(income),
            'expense': float(expense),
            'net': float(income - expense),
        })
    return result


def savings_rate(income, expense):
    """% thu nhập giữ lại được; None khi không có thu nhập."""
    if not income:
        return None
    return round((income - expense) / income * 100)


def category_spending(user, year, month):
    """Chi tiêu theo danh mục trong tháng, giảm dần, kèm % trên tổng chi."""
    rows = list(
        Transaction.objects.filter(
            user=user, transaction_type=Transaction.TransactionType.EXPENSE,
            date__year=year, date__month=month,
        )
        .values('category__name', 'category__color', 'category__icon')
        .annotate(total=Sum('amount'))
        .order_by('-total', 'category__name')
    )
    grand = sum((r['total'] for r in rows), Decimal('0'))
    return [{
        'name': r['category__name'] or 'Chưa phân loại',
        'color': r['category__color'] or '#64748b',
        'icon': r['category__icon'] or 'tag',
        'total': r['total'],
        'percent': round(r['total'] / grand * 100, 1) if grand else 0,
    } for r in rows]


def attach_budget_forecast(budgets, today=None):
    """
    Gắn dự báo chi cuối tháng vào từng Budget (theo tốc độ chi trung bình mỗi ngày tới hôm nay).
    Chỉ dự báo cho tháng hiện tại; tháng khác `projected` là None.
    """
    today = today or timezone.now().date()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    for budget in budgets:
        budget.projected = None
        budget.projected_over = False
        if (budget.year, budget.month) != (today.year, today.month):
            continue
        spent = budget.spent
        budget.projected = round(spent / today.day * days_in_month, 0)
        budget.projected_over = not budget.is_over_budget and budget.projected > budget.amount
    return budgets


# --- Import CSV sao kê ---

MAX_IMPORT_ROWS = 5000

# Tên cột đã bỏ dấu, viết thường -> trường nội bộ
COLUMN_ALIASES = {
    'date': {'ngay', 'date', 'ngay giao dich', 'ngay gd', 'transaction date', 'posting date', 'ngay hach toan'},
    'amount': {'so tien', 'amount', 'gia tri', 'so tien gd'},
    'debit': {'ghi no', 'debit', 'chi', 'tien ra', 'withdrawal', 'so tien ghi no', 'rut'},
    'credit': {'ghi co', 'credit', 'thu', 'tien vao', 'deposit', 'so tien ghi co', 'nap'},
    'type': {'loai', 'type', 'loai giao dich'},
    'note': {'ghi chu', 'noi dung', 'mo ta', 'description', 'note', 'dien giai', 'chi tiet', 'noi dung giao dich'},
    'category': {'danh muc', 'category'},
}
INCOME_WORDS = {'thu', 'thu nhap', 'income', 'credit', 'cr', 'c'}
EXPENSE_WORDS = {'chi', 'chi tieu', 'expense', 'debit', 'dr', 'd'}
DATE_FORMATS = ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y', '%d/%m/%y', '%Y/%m/%d')


def _plain(text):
    """Bỏ dấu tiếng Việt, viết thường, gộp khoảng trắng."""
    text = unicodedata.normalize('NFD', str(text or '')).replace('đ', 'd').replace('Đ', 'D')
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    return re.sub(r'\s+', ' ', text).strip().lower()


def parse_amount(raw):
    """'1.234.567' / '1,234,567.50' / '-50.000 đ' / '(200)' -> Decimal; None nếu không đọc được."""
    text = str(raw or '').strip()
    negative = text.startswith('-') or (text.startswith('(') and text.endswith(')'))
    text = re.sub(r'[^\d.,]', '', text)
    if not text:
        return None
    if '.' in text and ',' in text:
        # Dấu xuất hiện sau cùng là dấu thập phân
        decimal_sep = '.' if text.rfind('.') > text.rfind(',') else ','
        thousands_sep = ',' if decimal_sep == '.' else '.'
        text = text.replace(thousands_sep, '').replace(decimal_sep, '.')
    else:
        sep = '.' if '.' in text else (',' if ',' in text else None)
        if sep:
            parts = text.split(sep)
            # Nhiều dấu, hoặc một dấu theo sau đúng 3 chữ số => phân cách hàng nghìn
            if len(parts) > 2 or len(parts[-1]) == 3:
                text = text.replace(sep, '')
            else:
                text = text.replace(sep, '.')
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    return -value if negative else value


def parse_date(raw):
    text = str(raw or '').strip().split(' ')[0].split('T')[0]
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _decode(data):
    for encoding in ('utf-8-sig', 'cp1258', 'latin-1'):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode('utf-8', errors='replace')


def _map_columns(header):
    mapping = {}
    for index, name in enumerate(header):
        key = _plain(name)
        for field, aliases in COLUMN_ALIASES.items():
            if key in aliases and field not in mapping:
                mapping[field] = index
    return mapping


def import_transactions_csv(user, wallet, data):
    """
    Nhập giao dịch từ CSV (bytes). Nhận diện cột theo tên (tiếng Việt có/không dấu hoặc tiếng Anh),
    hỗ trợ một cột số tiền có dấu, cột Loại, hoặc cặp cột Ghi nợ/Ghi có.
    Bỏ qua dòng trùng với giao dịch đã có. Trả về dict: created, duplicates, errors [(dòng, lý do)].
    """
    text = _decode(data)
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=',;\t')
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(io.StringIO(text), dialect))
    result = {'created': 0, 'duplicates': 0, 'errors': []}
    if not rows:
        result['errors'].append((0, 'File trống.'))
        return result

    columns = _map_columns(rows[0])
    has_amount = 'amount' in columns or 'debit' in columns or 'credit' in columns
    if 'date' not in columns or not has_amount:
        result['errors'].append((1, 'Không tìm thấy cột Ngày và Số tiền (hoặc Ghi nợ/Ghi có).'))
        return result

    categories = {
        (_plain(c.name), c.type): c for c in Category.objects.filter(user=user)
    }

    def cell(row, field):
        index = columns.get(field)
        return row[index].strip() if index is not None and index < len(row) else ''

    to_create = []
    seen = set()
    for line_no, row in enumerate(rows[1:MAX_IMPORT_ROWS + 1], start=2):
        if not any(c.strip() for c in row):
            continue
        day = parse_date(cell(row, 'date'))
        if not day:
            result['errors'].append((line_no, f"Ngày không hợp lệ: '{cell(row, 'date')}'"))
            continue

        debit, credit = parse_amount(cell(row, 'debit')), parse_amount(cell(row, 'credit'))
        amount = parse_amount(cell(row, 'amount'))
        kind_word = _plain(cell(row, 'type'))
        if debit:
            kind, amount = Transaction.TransactionType.EXPENSE, abs(debit)
        elif credit:
            kind, amount = Transaction.TransactionType.INCOME, abs(credit)
        elif amount:
            if kind_word in INCOME_WORDS:
                kind = Transaction.TransactionType.INCOME
            elif kind_word in EXPENSE_WORDS:
                kind = Transaction.TransactionType.EXPENSE
            else:
                kind = Transaction.TransactionType.EXPENSE if amount < 0 else Transaction.TransactionType.INCOME
            amount = abs(amount)
        else:
            result['errors'].append((line_no, 'Thiếu số tiền.'))
            continue
        amount = amount.quantize(Decimal('0.01'))
        if amount <= 0:
            result['errors'].append((line_no, 'Số tiền phải lớn hơn 0.'))
            continue

        note = cell(row, 'note')[:500]
        signature = (day, kind, amount, note)
        duplicate = signature in seen or Transaction.objects.filter(
            wallet=wallet, date=day, transaction_type=kind, amount=amount, note=note
        ).exists()
        if duplicate:
            result['duplicates'] += 1
            continue
        seen.add(signature)
        to_create.append(Transaction(
            user=user, wallet=wallet, date=day, transaction_type=kind, amount=amount, note=note,
            category=categories.get((_plain(cell(row, 'category')), kind)),
        ))

    if len(rows) - 1 > MAX_IMPORT_ROWS:
        result['errors'].append((MAX_IMPORT_ROWS + 2, f'Chỉ nhập {MAX_IMPORT_ROWS} dòng đầu tiên.'))

    with db_transaction.atomic():
        Transaction.objects.bulk_create(to_create)
        wallet.recalculate_balance()
    result['created'] = len(to_create)
    return result
