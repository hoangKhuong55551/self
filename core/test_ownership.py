"""
Kiểm tra phân quyền dữ liệu: user khác không được xem, sửa hay xoá bản ghi của mình.

Test duyệt TẤT CẢ URL có tham số <pk> (đọc trực tiếp từ urlconf), nên view mới thêm
sau này cũng tự được kiểm tra — chỉ cần bổ sung bản ghi mẫu vào `make_objects`.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import URLPattern, URLResolver, get_resolver, reverse

from academic.models import ClassSession, CodeSnippet, Course, Note, Semester
from finance.models import (
    Asset, Budget, Category, Debt, DebtPayment, SavingGoal, Subscription, Transaction, Transfer, Wallet, WishlistItem,
    WorkoutLog,
)
from library.models import MediaItem
from productivity.models import Goal, Habit, Task

User = get_user_model()


def make_objects(user):
    """Một bản ghi của mỗi loại, trả về {tiền tố tên URL: object}."""
    wallet = Wallet.objects.create(user=user, name='Ví A', balance=Decimal('1000000'))
    wallet2 = Wallet.objects.create(user=user, name='Ví A2', balance=Decimal('0'))
    category = Category.objects.create(user=user, name='Ăn', type='expense')
    goal = Goal.objects.create(user=user, title='Mục tiêu A')
    debt = Debt.objects.create(user=user, person='Bạn A', amount=Decimal('100'), wallet=wallet)
    semester = Semester.objects.create(user=user, name='HK1', year=2026, term=Semester._meta.get_field('term').choices[0][0])
    return {
        'finance:wallet': wallet,
        'finance:category': category,
        'finance:transaction': Transaction.objects.create(
            user=user, wallet=wallet, category=category, transaction_type='expense', amount=Decimal('10')),
        'finance:transfer': Transfer.objects.create(
            user=user, from_wallet=wallet, to_wallet=wallet2, amount=Decimal('5')),
        'finance:budget': Budget.objects.create(user=user, category=category, month=1, year=2026, amount=Decimal('100')),
        'finance:subscription': Subscription.objects.create(
            user=user, name='Sub', amount=Decimal('50'), wallet=wallet,
            start_date=date(2026, 1, 1), next_billing_date=date(2099, 1, 1)),
        'finance:saving_goal': SavingGoal.objects.create(user=user, name='Quỹ', target_amount=Decimal('1000')),
        'finance:wishlist': WishlistItem.objects.create(user=user, name='Món', price=Decimal('20'), wallet=wallet),
        'finance:asset': Asset.objects.create(user=user, name='Giày'),
        'finance:workout': WorkoutLog.objects.create(
            user=user, activity_type=WorkoutLog._meta.get_field('activity_type').choices[0][0], duration_minutes=30),
        'finance:debt': debt,
        'finance:debt_payment': DebtPayment.objects.create(debt=debt, amount=Decimal('10'), wallet=wallet),
        'productivity:goal': goal,
        'productivity:toggle_checklist_item': Task.objects.create(
            goal=goal, title='Task A3', checklist=[{'text': 'bí mật', 'done': False}]),
        'productivity:task': Task.objects.create(goal=goal, title='Task A'),
        'productivity:update_task_status': Task.objects.create(goal=goal, title='Task A2'),
        'productivity:habit': Habit.objects.create(user=user, name='Habit A'),
        'productivity:toggle_habit': Habit.objects.create(user=user, name='Habit A2'),
        'academic:semester': semester,
        'academic:course': (course := Course.objects.create(semester=semester, name='Môn A')),
        'academic:class_session': ClassSession.objects.create(
            course=course, weekday=0, start_time='07:00', end_time='09:00', room='A1'),
        'academic:note': Note.objects.create(user=user, title='Ghi chú A', content='bí mật'),
        'academic:snippet': CodeSnippet.objects.create(user=user, title='Snippet A', code='print(1)'),
        'library:item': MediaItem.objects.create(user=user, title='Sách A'),
    }


def pk_url_names():
    """Tên đầy đủ (namespace:name) của mọi URL có tham số pk."""
    names = []

    def walk(patterns, namespace):
        for p in patterns:
            if isinstance(p, URLResolver):
                walk(p.url_patterns, p.namespace or namespace)
            elif isinstance(p, URLPattern) and p.name and 'pk' in p.pattern.converters:
                names.append(f'{namespace}:{p.name}' if namespace else p.name)

    walk(get_resolver().url_patterns, None)
    return names


def owner_object(objects, url_name):
    """Ghép URL với bản ghi theo tiền tố dài nhất (vd 'finance:wallet_edit' -> 'finance:wallet')."""
    matches = [key for key in objects if url_name == key or url_name.startswith(key + '_')]
    return objects[max(matches, key=len)] if matches else None


class OwnershipTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='password123')
        self.intruder = User.objects.create_user('intruder', password='password123')
        self.objects = make_objects(self.owner)
        self.client.force_login(self.intruder)

    def _snapshot(self):
        return {key: (type(obj).objects.filter(pk=obj.pk).values().first()) for key, obj in self.objects.items()}

    def test_every_pk_url_is_covered(self):
        missing = [name for name in pk_url_names() if owner_object(self.objects, name) is None]
        self.assertEqual(missing, [], 'Thêm bản ghi mẫu cho các URL này vào make_objects()')

    def test_intruder_cannot_read_or_modify_other_users_data(self):
        before = self._snapshot()
        for name in pk_url_names():
            obj = owner_object(self.objects, name)
            url = reverse(name, kwargs={'pk': obj.pk})
            for method in ('get', 'post'):
                with self.subTest(url=name, method=method):
                    response = getattr(self.client, method)(url, {'status': 'done', 'amount': '1', 'delta': '1'})
                    self.assertIn(response.status_code, (404, 405), f'{method.upper()} {url}')
        # Không bản ghi nào của chủ sở hữu bị đổi hay bị xoá
        self.assertEqual(self._snapshot(), before)

    def test_intruder_does_not_see_other_users_data_in_lists(self):
        pages = ['finance:wallet_list', 'finance:transaction_list', 'productivity:goal_list',
                 'productivity:kanban_board', 'academic:note_list', 'library:shelf']
        for name in pages:
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                for text in ('Ví A', 'Mục tiêu A', 'Task A', 'Ghi chú A', 'Sách A'):
                    self.assertNotContains(response, text)

    def test_forms_reject_other_users_wallet_and_task(self):
        wallet = self.objects['finance:wallet']
        mine = Wallet.objects.create(user=self.intruder, name='Ví của tôi', balance=Decimal('0'))
        response = self.client.post(reverse('finance:transaction_list'), {
            'wallet': wallet.pk, 'transaction_type': 'expense', 'amount': '1000', 'date': '2026-01-01',
        })
        self.assertFalse(Transaction.objects.filter(user=self.intruder).exists())
        self.assertEqual(response.status_code, 200)  # form báo lỗi, không tạo giao dịch
        self.client.post(reverse('finance:transfer_list'), {
            'from_wallet': mine.pk, 'to_wallet': wallet.pk, 'amount': '1', 'date': '2026-01-01',
        })
        self.assertFalse(Transfer.objects.filter(user=self.intruder).exists())

        task = self.objects['productivity:task']
        response = self.client.post(reverse('productivity:save_pomodoro_session'), {'task_id': task.pk})
        self.assertEqual(response.status_code, 404)
