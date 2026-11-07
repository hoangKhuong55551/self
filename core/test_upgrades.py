"""Kiểm thử các chức năng nâng cấp: định kỳ thu/chi, thêm nhanh, lịch, task lặp lại, vay mượn, báo cáo."""
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core import quick_add
from finance.models import Category, Debt, DebtPayment, Subscription, Transaction, Wallet
from finance.services import charge_due_subscriptions
from productivity.models import Goal, Task

User = get_user_model()


class BaseCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='up', password='pw-12345678')
        self.client.force_login(self.user)
        self.today = timezone.localdate()
        self.wallet = Wallet.objects.create(user=self.user, name='Tiền mặt', balance=Decimal('1000000'))
        self.bank = Wallet.objects.create(user=self.user, name='VCB', balance=Decimal('5000000'))
        self.food = Category.objects.create(user=self.user, name='Ăn uống', type='expense')
        self.cafe = Category.objects.create(user=self.user, name='Cafe', type='expense')
        self.salary = Category.objects.create(user=self.user, name='Lương', type='income')

    def msgs(self, response):
        return [str(m) for m in get_messages(response.wsgi_request)]


# ── 1 + 2. Khoản định kỳ: thu & chi, tự ghi, báo cho người dùng ──
class RecurringTests(BaseCase):
    def test_income_recurring_adds_to_wallet(self):
        sub = Subscription.objects.create(
            user=self.user, name='Lương', transaction_type='income', amount=Decimal('15000000'),
            wallet=self.bank, category=self.salary, start_date=self.today, next_billing_date=self.today,
        )
        self.assertEqual(charge_due_subscriptions(Subscription.objects.all()), 1)
        self.bank.refresh_from_db()
        self.assertEqual(self.bank.balance, Decimal('20000000'))
        txn = Transaction.objects.get(subscription=sub)
        self.assertEqual(txn.transaction_type, 'income')
        self.assertIn('Thu định kỳ', txn.note)
        # Số dư tính lại từ lịch sử vẫn khớp
        self.assertEqual(self.bank.compute_balance(), self.bank.balance)

    def test_expense_recurring_still_subtracts(self):
        Subscription.objects.create(user=self.user, name='Netflix', amount=Decimal('260000'), wallet=self.wallet,
                                    start_date=self.today, next_billing_date=self.today)
        charge_due_subscriptions(Subscription.objects.all())
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('740000'))

    def test_creating_due_item_charges_immediately_and_reports(self):
        r = self.client.post(reverse('finance:subscription_list'), {
            'transaction_type': 'expense', 'name': 'Tiền nhà', 'amount': '3000000', 'wallet': self.bank.pk,
            'category': self.food.pk, 'billing_cycle': 'monthly',
            'start_date': self.today.isoformat(), 'next_billing_date': self.today.isoformat(),
        })
        self.assertEqual(r.status_code, 302)
        self.bank.refresh_from_db()
        self.assertEqual(self.bank.balance, Decimal('2000000'))
        self.assertTrue(any('đã đến hạn' in m for m in self.msgs(r)))

    def test_form_prefills_local_date(self):
        r = self.client.get(reverse('finance:subscription_list'))
        self.assertEqual(r.context['form'].initial['next_billing_date'], self.today)

    def test_category_must_match_type(self):
        r = self.client.post(reverse('finance:subscription_list'), {
            'transaction_type': 'income', 'name': 'Lương', 'amount': '1000', 'wallet': self.bank.pk,
            'category': self.food.pk, 'billing_cycle': 'monthly',
            'start_date': self.today.isoformat(), 'next_billing_date': self.today.isoformat(),
        })
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Subscription.objects.exists())

    @override_settings(CHARGE_SUBSCRIPTIONS_ON_REQUEST=True)
    def test_middleware_reports_auto_charges(self):
        Subscription.objects.create(user=self.user, name='Spotify', amount=Decimal('59000'), wallet=self.wallet,
                                    start_date=self.today, next_billing_date=self.today - timedelta(days=1))
        with mock.patch('core.middleware.cache.add', return_value=True):
            r = self.client.get(reverse('core:dashboard'))
        self.assertTrue(any('Đã tự động ghi 1 giao dịch' in m for m in self.msgs(r)))

    def test_list_page_shows_income_total(self):
        Subscription.objects.create(user=self.user, name='Lương', transaction_type='income', amount=Decimal('10000000'),
                                    wallet=self.bank, start_date=self.today, next_billing_date=self.today + timedelta(days=5))
        r = self.client.get(reverse('finance:subscription_list'))
        self.assertContains(r, 'Thu ~')
        self.assertContains(r, '+10.000.000')


# ── 3. Thêm nhanh từ Ctrl+K ──
class QuickAddTests(BaseCase):
    def preview(self, q):
        return self.client.get(reverse('core:quick_add'), {'q': q}).json()

    def commit(self, q):
        return self.client.post(reverse('core:quick_add'), {'q': q})

    def test_amount_parsing(self):
        cases = {'50k': 50000, '1tr2': 1200000, '1.5tr': 1500000, '200.000': 200000, '2m': 2000000, '15tr': 15000000,
                 '1.200.000': 1200000, '1,200,000': 1200000, '2,5k': 2500, '300000đ': 300000}
        for text, value in cases.items():
            self.assertEqual(quick_add.parse_amount(text), Decimal(value), text)
        # Thập phân không đơn vị là mơ hồ: báo lỗi thay vì ghi 15 đ
        for bad in ('abc', '0k', '1k2', '1.5', '2,5', '1.200.00'):
            self.assertIsNone(quick_add.parse_amount(bad), bad)

    def test_not_a_command(self):
        self.assertEqual(self.preview('netflix'), {'match': False})

    def test_expense_preview_guesses_category_and_does_not_save(self):
        d = self.preview('-45k cafe sáng')
        self.assertTrue(d['ok'])
        self.assertIn('45.000', d['title'])
        self.assertIn('Cafe', d['subtitle'])
        self.assertFalse(Transaction.objects.exists())

    def test_expense_commit_updates_wallet(self):
        r = self.commit('-45k cafe sáng @tiền')
        self.assertEqual(r.status_code, 200)
        txn = Transaction.objects.get()
        self.assertEqual((txn.amount, txn.transaction_type, txn.wallet_id, txn.category.name), (Decimal('45000'), 'expense', self.wallet.pk, 'Cafe'))
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('955000'))

    def test_income_with_wallet_category_and_date(self):
        self.commit('+15tr #lương @vcb hôm qua')
        txn = Transaction.objects.get()
        self.assertEqual((txn.transaction_type, txn.wallet_id, txn.category.name), ('income', self.bank.pk, 'Lương'))
        self.assertEqual(txn.date, self.today - timedelta(days=1))

    def test_keyword_guess_for_default_categories(self):
        # Danh mục mặc định "Ăn uống"/"Di chuyển" (tạo sẵn cho user mới) được đoán theo từ khoá
        self.cafe.delete()
        self.food.delete()
        self.assertIn('Ăn uống', self.preview('-45k cafe sáng')['subtitle'])
        self.assertIn('Di chuyển', self.preview('-30k grab đi làm')['subtitle'])
        self.assertIn('Chưa phân loại', self.preview('-30k linh tinh')['subtitle'])

    def test_errors_are_reported_not_saved(self):
        self.assertFalse(self.preview('-50k @khongco')['ok'])
        self.assertFalse(self.preview('-50k #khongco')['ok'])
        self.assertFalse(self.preview('-50k ngày mai')['ok'])  # tương lai
        self.assertEqual(self.commit('-50k @khongco').status_code, 400)
        self.assertFalse(Transaction.objects.exists())

    def test_task_into_inbox_goal(self):
        self.commit('task: nộp báo cáo mai !')
        task = Task.objects.get()
        self.assertEqual(task.title, 'nộp báo cáo')
        self.assertEqual(task.due_date, self.today + timedelta(days=1))
        self.assertEqual(task.quadrant, 'do')
        self.assertEqual(task.goal.title, quick_add.INBOX_GOAL)
        self.assertEqual(task.goal.user, self.user)

    def test_task_into_named_goal_with_weekday(self):
        goal = Goal.objects.create(user=self.user, title='Học kỳ 1')
        self.commit('việc: ôn thi #học kỳ thứ 6')
        task = Task.objects.get()
        self.assertEqual(task.goal, goal)
        self.assertEqual(task.due_date.weekday(), 4)
        self.assertGreaterEqual(task.due_date, self.today)

    def test_task_needs_colon_so_search_still_works(self):
        for text in ('việc nhà', 'task list', 'tasks: x', 'task:'):
            self.assertEqual(self.preview(text), {'match': False}, text)
        self.assertTrue(self.preview('t: gọi điện')['ok'])

    def test_date_only_read_at_end_and_name_mai_kept(self):
        self.commit('task: gọi chị Mai')
        task = Task.objects.get()
        self.assertEqual((task.title, task.due_date), ('gọi chị Mai', None))
        task.delete()
        self.commit('task: hỏi mai về bài thứ 6')
        task = Task.objects.get()
        self.assertEqual(task.title, 'hỏi mai về bài')
        self.assertEqual(task.due_date.weekday(), 4)

    def test_task_past_dates(self):
        d = self.preview('task: nộp bài hôm qua')
        self.assertFalse(d['ok'])
        self.assertIn('đã qua', d['title'])
        past = self.today - timedelta(days=3)
        self.commit(f'task: ôn chương {past:%d/%m}')  # không có năm -> năm sau, không bị quá hạn ngay
        self.assertEqual(Task.objects.get().due_date, past.replace(year=past.year + 1))

    def test_multi_word_tags(self):
        Category.objects.create(user=self.user, name='Mua sắm online', type='expense')
        mua_sam = Category.objects.get(user=self.user, name='Mua sắm')
        self.commit('-200k áo khoác #mua sắm @tiền mặt')
        txn = Transaction.objects.get()
        self.assertEqual((txn.category_id, txn.wallet_id, txn.note), (mua_sam.pk, self.wallet.pk, 'áo khoác'))
        goal = Goal.objects.create(user=self.user, title='Học kỳ 1')
        Goal.objects.create(user=self.user, title='Học tiếng Anh')
        self.commit('task: ôn thi #học kỳ 1 mai')
        task = Task.objects.get()
        self.assertEqual((task.goal_id, task.title), (goal.pk, 'ôn thi'))

    def test_requires_login_and_csrf_protected_view(self):
        self.client.logout()
        r = self.client.post(reverse('core:quick_add'), {'q': '-50k x'})
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Transaction.objects.exists())


# ── 4. Lịch tổng hợp ──
class CalendarTests(BaseCase):
    def test_month_collects_all_kinds(self):
        goal = Goal.objects.create(user=self.user, title='Ra mắt app', deadline=self.today)
        Task.objects.create(goal=goal, title='Viết test', due_date=self.today)
        Subscription.objects.create(user=self.user, name='Netflix', amount=Decimal('260000'), wallet=self.wallet,
                                    start_date=self.today, next_billing_date=self.today + timedelta(days=1),
                                    billing_cycle='weekly')
        Debt.objects.create(user=self.user, person='Nam', amount=Decimal('500000'), due_date=self.today)
        r = self.client.get(reverse('core:calendar'), {'m': f'{self.today:%Y-%m}'})
        self.assertEqual(r.status_code, 200)
        for text in ('Viết test', 'Ra mắt app', 'Netflix', 'Cho Nam mượn'):
            self.assertContains(r, text)
        kinds = {e['kind'] for day in r.context['agenda'] for e in day['events']}
        self.assertEqual(kinds, {'task', 'goal', 'recurring', 'debt'})

    def test_weekly_recurring_projects_several_times(self):
        first = self.today.replace(day=1)
        Subscription.objects.create(user=self.user, name='Gym', amount=Decimal('1'), wallet=self.wallet,
                                    start_date=first, next_billing_date=first, billing_cycle='weekly')
        r = self.client.get(reverse('core:calendar'), {'m': f'{first:%Y-%m}'})
        gym = [e for d in r.context['agenda'] for e in d['events'] if e['title'] == 'Gym']
        self.assertGreaterEqual(len(gym), 4)

    def test_extreme_months_do_not_crash(self):
        for m in ('9999-12', '1-1', '2026-13', '0-0'):
            self.assertEqual(self.client.get(reverse('core:calendar'), {'m': m}).status_code, 200, m)

    def test_far_future_month_still_shows_weekly_items(self):
        Subscription.objects.create(user=self.user, name='Gym', amount=Decimal('1'), wallet=self.wallet,
                                    start_date=self.today, next_billing_date=self.today, billing_cycle='weekly')
        far = self.today.replace(day=1) + timedelta(days=365 * 3)
        r = self.client.get(reverse('core:calendar'), {'m': f'{far:%Y-%m}'})
        self.assertTrue(any(e['title'] == 'Gym' for d in r.context['agenda'] for e in d['events']))

    def test_debt_events_use_one_query(self):
        for i in range(5):
            Debt.objects.create(user=self.user, person=f'P{i}', amount=Decimal('10'), due_date=self.today)
        from core.calendar import month_events
        first = self.today.replace(day=1)
        with self.assertNumQueries(6):  # task, mục tiêu, giao dịch định kỳ, khoản định kỳ, nợ, tiết kiệm; không thêm truy vấn theo từng khoản nợ
            month_events(self.user, first, first + timedelta(days=27))

    def test_bad_month_falls_back_and_other_users_hidden(self):
        other = User.objects.create_user(username='other', password='pw-12345678')
        og = Goal.objects.create(user=other, title='Bí mật', deadline=self.today)
        Task.objects.create(goal=og, title='Việc của người khác', due_date=self.today)
        r = self.client.get(reverse('core:calendar'), {'m': 'abc'})
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'Việc của người khác')


# ── 5. Task lặp lại, checklist, giờ hạn ──
class TaskUpgradeTests(BaseCase):
    def setUp(self):
        super().setUp()
        self.goal = Goal.objects.create(user=self.user, title='Sức khoẻ')

    def test_next_due_date_rules(self):
        t = Task(goal=self.goal, title='x', due_date=date(2026, 1, 31), recurrence='monthly')
        self.assertEqual(t.next_due_date(date(2026, 1, 31)), date(2026, 2, 28))
        t = Task(goal=self.goal, title='x', due_date=date(2026, 11, 6), recurrence='weekdays')  # thứ Sáu
        self.assertEqual(t.next_due_date(date(2026, 11, 6)), date(2026, 11, 9))  # thứ Hai
        t = Task(goal=self.goal, title='x', due_date=date(2026, 11, 1), recurrence='daily')  # trễ một tuần
        self.assertEqual(t.next_due_date(date(2026, 11, 8)), date(2026, 11, 9))

    def test_completing_recurring_task_spawns_once(self):
        task = Task.objects.create(goal=self.goal, title='Chạy bộ', due_date=self.today, recurrence='daily',
                                   checklist=[{'text': 'Giãn cơ', 'done': True}])
        url = reverse('productivity:update_task_status', args=[task.pk])
        r = self.client.post(url, '{"status": "done"}', content_type='application/json')
        self.assertIsNotNone(r.json()['next_task'])
        nxt = Task.objects.exclude(pk=task.pk).get()
        self.assertEqual((nxt.title, nxt.status, nxt.recurrence), ('Chạy bộ', 'todo', 'daily'))
        self.assertEqual(nxt.due_date, self.today + timedelta(days=1))
        self.assertEqual(nxt.checklist, [{'text': 'Giãn cơ', 'done': False}])
        # Bỏ tick rồi tick lại: không sinh thêm
        self.client.post(url, '{"status": "todo"}', content_type='application/json')
        r = self.client.post(url, '{"status": "done"}', content_type='application/json')
        self.assertIsNone(r.json()['next_task'])
        self.assertEqual(Task.objects.count(), 2)

    def test_non_recurring_does_not_spawn(self):
        task = Task.objects.create(goal=self.goal, title='Một lần', due_date=self.today)
        self.client.post(reverse('productivity:update_task_status', args=[task.pk]), '{"status": "done"}',
                         content_type='application/json')
        self.assertEqual(Task.objects.count(), 1)

    def test_form_parses_checklist_time_and_requires_due_for_recurrence(self):
        data = {'goal': self.goal.pk, 'title': 'Dọn nhà', 'status': 'todo', 'quadrant': 'schedule',
                'estimated_pomodoros': 1, 'recurrence': 'weekly', 'due_date': '', 'due_time': '19:30',
                'checklist_text': 'Hút bụi\n[x] Lau bàn\n\n- Đổ rác'}
        r = self.client.post(reverse('productivity:kanban_board'), data)
        self.assertEqual(r.status_code, 200)  # thiếu hạn
        self.assertFalse(Task.objects.exists())
        data['due_date'] = self.today.isoformat()
        self.client.post(reverse('productivity:kanban_board'), data)
        task = Task.objects.get()
        self.assertEqual(task.checklist, [{'text': 'Hút bụi', 'done': False}, {'text': 'Lau bàn', 'done': True},
                                          {'text': 'Đổ rác', 'done': False}])
        self.assertEqual(task.due_time.strftime('%H:%M'), '19:30')
        # Trang sửa hiện lại checklist dạng chữ
        r = self.client.get(reverse('productivity:task_edit', args=[task.pk]))
        self.assertContains(r, '[x] Lau bàn')

    def test_toggle_checklist_item(self):
        task = Task.objects.create(goal=self.goal, title='x', checklist=[{'text': 'a', 'done': False}])
        url = reverse('productivity:toggle_checklist_item', args=[task.pk])
        r = self.client.post(url, {'index': 0})
        self.assertEqual(r.json(), {'success': True, 'done': True, 'done_count': 1, 'total': 1})
        self.assertEqual(self.client.post(url, {'index': 5}).status_code, 404)
        self.assertEqual(self.client.post(url, {'index': 'x'}).status_code, 404)
        other = User.objects.create_user(username='o2', password='pw-12345678')
        self.client.force_login(other)
        self.assertEqual(self.client.post(url, {'index': 0}).status_code, 404)


# ── 6. Vay / cho mượn ──
class DebtTests(BaseCase):
    def test_lend_and_get_back_updates_wallet(self):
        r = self.client.post(reverse('finance:debt_list'), {
            'direction': 'lent', 'person': 'Nam', 'amount': '300000', 'wallet': self.wallet.pk,
            'date': self.today.isoformat(),
        })
        self.assertEqual(r.status_code, 302)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('700000'))
        debt = Debt.objects.get()
        self.client.post(reverse('finance:debt_pay', args=[debt.pk]), {'amount': '100000', 'wallet': self.wallet.pk, 'date': self.today.isoformat()})
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('800000'))
        self.assertEqual(debt.remaining, Decimal('200000'))
        # Không nhận quá số còn lại
        self.client.post(reverse('finance:debt_pay', args=[debt.pk]), {'amount': '999999', 'date': self.today.isoformat()})
        self.assertEqual(DebtPayment.objects.count(), 1)
        self.client.post(reverse('finance:debt_pay', args=[debt.pk]), {'amount': '200000', 'wallet': self.wallet.pk, 'date': self.today.isoformat()})
        debt = Debt.objects.get()
        self.assertTrue(debt.is_settled)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('1000000'))

    def test_borrow_adds_then_delete_restores(self):
        self.client.post(reverse('finance:debt_list'), {
            'direction': 'borrowed', 'person': 'Mẹ', 'amount': '2000000', 'wallet': self.bank.pk,
            'date': self.today.isoformat(),
        })
        self.bank.refresh_from_db()
        self.assertEqual(self.bank.balance, Decimal('7000000'))
        debt = Debt.objects.get()
        self.client.post(reverse('finance:debt_pay', args=[debt.pk]), {'amount': '500000', 'wallet': self.bank.pk, 'date': self.today.isoformat()})
        self.bank.refresh_from_db()
        self.assertEqual(self.bank.balance, Decimal('6500000'))
        self.assertEqual(self.bank.compute_balance(), self.bank.balance)
        self.client.post(reverse('finance:debt_delete', args=[debt.pk]))
        self.bank.refresh_from_db()
        self.assertEqual(self.bank.balance, Decimal('5000000'))

    def test_debt_without_wallet_leaves_balances(self):
        self.client.post(reverse('finance:debt_list'), {'direction': 'lent', 'person': 'Lan', 'amount': '50000', 'date': self.today.isoformat()})
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('1000000'))
        r = self.client.get(reverse('finance:debt_list'))
        self.assertContains(r, 'Cho Lan mượn')
        self.assertEqual(r.context['lent_total'], Decimal('50000'))

    def test_changing_direction_recalculates_payment_wallets(self):
        self.client.post(reverse('finance:debt_list'), {'direction': 'lent', 'person': 'An', 'amount': '1000000',
                                                        'wallet': self.wallet.pk, 'date': self.today.isoformat()})
        debt = Debt.objects.get()
        self.client.post(reverse('finance:debt_pay', args=[debt.pk]), {'amount': '400000', 'wallet': self.bank.pk, 'date': self.today.isoformat()})
        self.client.post(reverse('finance:debt_edit', args=[debt.pk]), {
            'direction': 'borrowed', 'person': 'An', 'amount': '1000000', 'wallet': self.wallet.pk, 'date': self.today.isoformat()})
        for w in (self.wallet, self.bank):
            w.refresh_from_db()
            self.assertEqual(w.balance, w.compute_balance(), w.name)
        self.assertEqual(self.bank.balance, Decimal('4600000'))  # trả nợ 400k đi ra khỏi VCB

    def test_edit_cannot_go_below_paid_and_moving_wallet_recalculates(self):
        debt = Debt.objects.create(user=self.user, person='An', amount=Decimal('100000'), wallet=self.wallet)
        self.wallet.recalculate_balance()
        DebtPayment.objects.create(debt=debt, amount=Decimal('60000'))
        data = {'direction': 'lent', 'person': 'An', 'amount': '50000', 'wallet': self.bank.pk, 'date': self.today.isoformat()}
        r = self.client.post(reverse('finance:debt_edit', args=[debt.pk]), data)
        self.assertEqual(r.status_code, 200)  # 50k < đã trả 60k
        data['amount'] = '100000'
        self.client.post(reverse('finance:debt_edit', args=[debt.pk]), data)
        self.wallet.refresh_from_db()
        self.bank.refresh_from_db()
        self.assertEqual((self.wallet.balance, self.bank.balance), (Decimal('1000000'), Decimal('4900000')))

    def test_deleting_user_with_debts_works(self):
        debt = Debt.objects.create(user=self.user, person='An', amount=Decimal('1'), wallet=self.wallet)
        DebtPayment.objects.create(debt=debt, amount=Decimal('1'), wallet=self.bank)
        self.user.delete()
        self.assertFalse(Debt.objects.exists())

    def test_wallet_with_debt_cannot_be_deleted_and_ownership(self):
        debt = Debt.objects.create(user=self.user, person='An', amount=Decimal('1'), wallet=self.wallet)
        self.client.post(reverse('finance:wallet_delete', args=[self.wallet.pk]))
        self.assertTrue(Wallet.objects.filter(pk=self.wallet.pk).exists())
        other = User.objects.create_user(username='o3', password='pw-12345678')
        self.client.force_login(other)
        self.assertEqual(self.client.post(reverse('finance:debt_pay', args=[debt.pk]), {'amount': '1', 'date': self.today.isoformat()}).status_code, 404)
        self.assertEqual(self.client.get(reverse('finance:debt_edit', args=[debt.pk])).status_code, 404)


# ── 7. Báo cáo ──
class ReportTests(BaseCase):
    def test_report_totals_and_category_comparison(self):
        this = self.today.replace(day=1)
        last = (this - timedelta(days=1)).replace(day=1)
        for d, amount, cat in [(this, 300000, self.food), (last, 100000, self.food), (this, 50000, self.cafe)]:
            Transaction.objects.create(user=self.user, wallet=self.wallet, category=cat, transaction_type='expense', amount=Decimal(amount), date=d)
        Transaction.objects.create(user=self.user, wallet=self.bank, category=self.salary, transaction_type='income', amount=Decimal('1000000'), date=this)
        r = self.client.get(reverse('finance:report'), {'year': this.year, 'month': this.month})
        self.assertEqual(r.status_code, 200)
        food = next(c for c in r.context['categories'] if c['name'] == 'Ăn uống')
        self.assertEqual((food['this'], food['last'], food['change']), (Decimal('300000'), Decimal('100000'), 200))
        cafe = next(c for c in r.context['categories'] if c['name'] == 'Cafe')
        self.assertIsNone(cafe['change'])  # mới phát sinh
        month = r.context['overview']['months'][this.month - 1]
        self.assertEqual((month['income'], month['expense'], month['rate']), (Decimal('1000000'), Decimal('350000'), 65))
        self.assertEqual(r.context['top'][0].amount, Decimal('300000'))

    def test_report_bad_params_fallback(self):
        r = self.client.get(reverse('finance:report'), {'year': 'x', 'month': '13'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['year'], self.today.year)
