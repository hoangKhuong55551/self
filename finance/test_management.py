"""
Test cho các thao tác quản lý tài chính: danh mục, sửa/xoá, chuyển tiền, tiết kiệm,
lọc giao dịch, import CSV và thống kê.
"""
import calendar
from datetime import date, timedelta
from decimal import Decimal
from importlib import import_module

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.exports import export_csv
from core.models import XPEvent
from finance.defaults import DEFAULT_CATEGORIES
from finance.models import (
    Budget, Category, SavingGoal, Subscription, Transaction, Transfer, Wallet, WishlistItem,
)
from finance.services import (
    attach_budget_forecast, category_spending, import_transactions_csv, monthly_cashflow,
    parse_amount, parse_date, savings_rate,
)

User = get_user_model()


class FinanceTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='owner', password='password123')
        self.other = User.objects.create_user(username='other', password='password123')
        self.client.login(username='owner', password='password123')
        self.wallet = Wallet.objects.create(user=self.user, name='Tiền mặt', balance=Decimal('1000000'))
        self.food = Category.objects.get(user=self.user, name='Ăn uống')
        self.salary = Category.objects.get(user=self.user, name='Lương')
        self.today = timezone.now().date()

    def add_txn(self, amount, kind='expense', category=None, wallet=None, day=None, note=''):
        return self.client.post(reverse('finance:transaction_list'), {
            'wallet': (wallet or self.wallet).pk, 'transaction_type': kind, 'amount': str(amount),
            'category': category.pk if category else '', 'date': (day or self.today).isoformat(), 'note': note,
        })

    def balance(self, wallet=None):
        wallet = wallet or self.wallet
        wallet.refresh_from_db()
        return wallet.balance


class DefaultCategoryTest(FinanceTestCase):
    def test_new_user_gets_default_categories(self):
        self.assertEqual(Category.objects.filter(user=self.user).count(), len(DEFAULT_CATEGORIES))
        self.assertTrue(Category.objects.filter(user=self.user, type='income').exists())

    def test_registration_creates_categories(self):
        self.client.logout()
        self.client.post(reverse('core:register'), {
            'username': 'newbie', 'email': 'newbie@example.com', 'first_name': 'Nguyen', 'last_name': 'An', 'password1': 'Str0ng-pass-123', 'password2': 'Str0ng-pass-123',
        })
        newbie = User.objects.get(username='newbie')
        self.assertEqual(Category.objects.filter(user=newbie).count(), len(DEFAULT_CATEGORIES))

    def test_backfill_migration(self):
        """Ví cũ: ban đầu = số dư - (thu - chi); user chưa có danh mục được tạo mặc định."""
        Category.objects.filter(user=self.other).delete()
        wallet = Wallet.objects.create(user=self.other, name='Cũ', balance=Decimal('0'))
        Transaction.objects.create(user=self.other, wallet=wallet, transaction_type='expense', amount=Decimal('100'))
        Wallet.objects.filter(pk=wallet.pk).update(balance=Decimal('900'), initial_balance=Decimal('0'))

        migration = import_module('finance.migrations.0003_backfill_initial_balance_and_categories')
        migration.forwards(apps, None)

        wallet.refresh_from_db()
        self.assertEqual(wallet.initial_balance, Decimal('1000'))
        self.assertEqual(wallet.compute_balance(), Decimal('900'))
        self.assertEqual(Category.objects.filter(user=self.other).count(), len(DEFAULT_CATEGORIES))
        # User đã có danh mục thì không bị tạo thêm
        self.assertEqual(Category.objects.filter(user=self.user).count(), len(DEFAULT_CATEGORIES))


class CategoryCrudTest(FinanceTestCase):
    def test_create_edit_delete(self):
        self.client.post(reverse('finance:category_list'), {
            'name': 'Thú cưng', 'type': 'expense', 'icon': 'heart', 'color': '#ff0000',
        })
        pet = Category.objects.get(user=self.user, name='Thú cưng')
        self.client.post(reverse('finance:category_edit', args=[pet.pk]), {
            'name': 'Chó mèo', 'type': 'expense', 'icon': 'heart', 'color': '#00ff00',
        })
        pet.refresh_from_db()
        self.assertEqual(pet.name, 'Chó mèo')
        self.client.post(reverse('finance:category_delete', args=[pet.pk]))
        self.assertFalse(Category.objects.filter(pk=pet.pk).exists())

    def test_duplicate_name_rejected(self):
        response = self.client.post(reverse('finance:category_list'), {
            'name': 'ăn uống', 'type': 'expense', 'icon': 'x', 'color': '#000000',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)

    def test_delete_keeps_transactions_uncategorized(self):
        self.add_txn(50000, category=self.food)
        self.client.post(reverse('finance:category_delete', args=[self.food.pk]))
        self.assertIsNone(Transaction.objects.get().category)

    def test_cannot_touch_other_users_category(self):
        foreign = Category.objects.filter(user=self.other).first()
        self.assertEqual(self.client.get(reverse('finance:category_edit', args=[foreign.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('finance:category_delete', args=[foreign.pk])).status_code, 404)


class TransactionEditTest(FinanceTestCase):
    def test_category_must_match_type(self):
        response = self.add_txn(100, kind='expense', category=self.salary)
        self.assertEqual(response.status_code, 200)
        self.assertIn('category', response.context['form'].errors)
        self.assertFalse(Transaction.objects.exists())

    def test_edit_amount_recalculates_balance(self):
        self.add_txn(200000, category=self.food)
        txn = Transaction.objects.get()
        self.client.post(reverse('finance:transaction_edit', args=[txn.pk]), {
            'wallet': self.wallet.pk, 'transaction_type': 'expense', 'amount': '50000',
            'category': self.food.pk, 'date': self.today.isoformat(), 'note': '',
        })
        self.assertEqual(self.balance(), Decimal('950000'))

    def test_edit_form_shows_existing_date(self):
        self.add_txn(1000, day=date(2026, 3, 9))
        response = self.client.get(reverse('finance:transaction_edit', args=[Transaction.objects.get().pk]))
        self.assertContains(response, 'value="2026-03-09"')

    def test_move_to_other_wallet_recalculates_both(self):
        bank = Wallet.objects.create(user=self.user, name='Ngân hàng', balance=Decimal('500000'))
        self.add_txn(100000)
        txn = Transaction.objects.get()
        self.client.post(reverse('finance:transaction_edit', args=[txn.pk]), {
            'wallet': bank.pk, 'transaction_type': 'expense', 'amount': '100000',
            'date': self.today.isoformat(), 'note': '',
        })
        self.assertEqual(self.balance(), Decimal('1000000'))
        self.assertEqual(self.balance(bank), Decimal('400000'))

    def test_delete_restores_balance(self):
        self.add_txn(300000, kind='income', category=self.salary)
        self.assertEqual(self.balance(), Decimal('1300000'))
        self.client.post(reverse('finance:transaction_delete', args=[Transaction.objects.get().pk]))
        self.assertEqual(self.balance(), Decimal('1000000'))

    def test_delete_requires_post_and_ownership(self):
        self.add_txn(1000)
        txn = Transaction.objects.get()
        self.assertEqual(self.client.get(reverse('finance:transaction_delete', args=[txn.pk])).status_code, 405)
        self.client.logout()
        self.client.login(username='other', password='password123')
        self.assertEqual(self.client.post(reverse('finance:transaction_delete', args=[txn.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('finance:transaction_edit', args=[txn.pk])).status_code, 404)


class WalletManagementTest(FinanceTestCase):
    def test_initial_balance_set_on_create_and_recalculate_is_consistent(self):
        self.assertEqual(self.wallet.initial_balance, Decimal('1000000'))
        self.add_txn(100000, category=self.food)
        self.add_txn(40000, kind='income', category=self.salary)
        item = WishlistItem.objects.create(user=self.user, wallet=self.wallet, name='Sách', price=Decimal('60000'))
        self.client.post(reverse('finance:wishlist_purchase', args=[item.pk]))
        expected = Decimal('880000')
        self.assertEqual(self.balance(), expected)
        self.client.post(reverse('finance:wallet_recalculate', args=[self.wallet.pk]))
        self.assertEqual(self.balance(), expected)

    def test_recalculate_fixes_drift(self):
        Wallet.objects.filter(pk=self.wallet.pk).update(balance=Decimal('1'))
        self.client.post(reverse('finance:wallet_recalculate', args=[self.wallet.pk]))
        self.assertEqual(self.balance(), Decimal('1000000'))

    def test_edit_cannot_change_balance_and_can_archive(self):
        self.client.post(reverse('finance:wallet_edit', args=[self.wallet.pk]), {
            'name': 'Ví mới', 'currency': 'VND', 'icon': 'cash', 'balance': '999',
        })
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.name, 'Ví mới')
        self.assertFalse(self.wallet.is_active)
        self.assertEqual(self.wallet.balance, Decimal('1000000'))

    def test_delete_only_unused_wallet(self):
        self.add_txn(1000)
        self.client.post(reverse('finance:wallet_delete', args=[self.wallet.pk]))
        self.assertTrue(Wallet.objects.filter(pk=self.wallet.pk).exists())
        empty = Wallet.objects.create(user=self.user, name='Trống')
        self.client.post(reverse('finance:wallet_delete', args=[empty.pk]))
        self.assertFalse(Wallet.objects.filter(pk=empty.pk).exists())


class TransferTest(FinanceTestCase):
    def setUp(self):
        super().setUp()
        self.bank = Wallet.objects.create(user=self.user, name='Ngân hàng', balance=Decimal('2000000'))

    def transfer(self, from_wallet, to_wallet, amount):
        return self.client.post(reverse('finance:transfer_list'), {
            'from_wallet': from_wallet.pk, 'to_wallet': to_wallet.pk, 'amount': str(amount),
            'date': self.today.isoformat(), 'note': 'Rút ATM',
        })

    def test_transfer_moves_money_without_income_or_expense(self):
        self.transfer(self.bank, self.wallet, 500000)
        self.assertEqual(self.balance(self.bank), Decimal('1500000'))
        self.assertEqual(self.balance(), Decimal('1500000'))
        self.assertFalse(Transaction.objects.exists())
        month = monthly_cashflow(self.user)[-1]
        self.assertEqual((month['income'], month['expense']), (0.0, 0.0))

    def test_delete_restores_balances(self):
        self.transfer(self.bank, self.wallet, 500000)
        self.client.post(reverse('finance:transfer_delete', args=[Transfer.objects.get().pk]))
        self.assertEqual(self.balance(self.bank), Decimal('2000000'))
        self.assertEqual(self.balance(), Decimal('1000000'))

    def test_same_wallet_rejected(self):
        response = self.transfer(self.wallet, self.wallet, 100)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transfer.objects.exists())

    def test_cannot_use_other_users_wallet(self):
        foreign = Wallet.objects.create(user=self.other, name='Lạ', balance=Decimal('100'))
        self.transfer(foreign, self.wallet, 100)
        self.assertFalse(Transfer.objects.exists())
        self.assertEqual(self.balance(foreign), Decimal('100'))


class BudgetManagementTest(FinanceTestCase):
    def setUp(self):
        super().setUp()
        self.budget = Budget.objects.create(
            user=self.user, category=self.food, month=self.today.month, year=self.today.year, amount=Decimal('3000000'),
        )

    def test_edit_and_delete(self):
        self.client.post(reverse('finance:budget_edit', args=[self.budget.pk]), {
            'category': self.food.pk, 'amount': '4000000', 'month': self.today.month, 'year': self.today.year,
        })
        self.budget.refresh_from_db()
        self.assertEqual(self.budget.amount, Decimal('4000000'))
        self.client.post(reverse('finance:budget_delete', args=[self.budget.pk]))
        self.assertFalse(Budget.objects.exists())

    def test_invalid_month_rejected(self):
        response = self.client.post(reverse('finance:budget_list'), {
            'category': Category.objects.get(user=self.user, name='Di chuyển').pk, 'amount': '1', 'month': 13, 'year': 2026,
        })
        self.assertIn('month', response.context['form'].errors)

    def test_copy_last_month_skips_existing(self):
        last = self.today.replace(day=1) - timedelta(days=1)
        transport = Category.objects.get(user=self.user, name='Di chuyển')
        Budget.objects.create(user=self.user, category=self.food, month=last.month, year=last.year, amount=Decimal('1'))
        Budget.objects.create(user=self.user, category=transport, month=last.month, year=last.year, amount=Decimal('500000'))
        self.client.post(reverse('finance:budget_copy_last_month'))
        current = Budget.objects.filter(user=self.user, month=self.today.month, year=self.today.year)
        self.assertEqual(current.count(), 2)
        self.assertEqual(current.get(category=self.food).amount, Decimal('3000000'))
        self.assertEqual(current.get(category=transport).amount, Decimal('500000'))

    def test_forecast(self):
        day10 = self.today.replace(day=10)
        Transaction.objects.create(
            user=self.user, wallet=self.wallet, category=self.food, transaction_type='expense',
            amount=Decimal('1500000'), date=day10.replace(day=5),
        )
        [budget] = attach_budget_forecast([self.budget], today=day10)
        days = calendar.monthrange(day10.year, day10.month)[1]
        self.assertEqual(budget.projected, round(Decimal('1500000') / 10 * days, 0))
        self.assertTrue(budget.projected_over)

    def test_forecast_skips_other_months(self):
        self.budget.month = 1 if self.today.month != 1 else 2
        [budget] = attach_budget_forecast([self.budget], today=self.today)
        self.assertIsNone(budget.projected)


class SubscriptionManagementTest(FinanceTestCase):
    def setUp(self):
        super().setUp()
        self.sub = Subscription.objects.create(
            user=self.user, wallet=self.wallet, name='Netflix', amount=Decimal('100000'),
            start_date=self.today, next_billing_date=self.today + timedelta(days=5),
        )

    def test_paused_subscription_is_not_charged(self):
        self.client.post(reverse('finance:subscription_toggle', args=[self.sub.pk]))
        Subscription.objects.filter(pk=self.sub.pk).update(next_billing_date=self.today - timedelta(days=40))
        from finance.services import charge_due_subscriptions
        self.assertEqual(charge_due_subscriptions(Subscription.objects.all()), 0)

    def test_reactivation_does_not_back_charge(self):
        Subscription.objects.filter(pk=self.sub.pk).update(is_active=False, next_billing_date=self.today - timedelta(days=60))
        self.client.post(reverse('finance:subscription_toggle', args=[self.sub.pk]))
        self.sub.refresh_from_db()
        self.assertTrue(self.sub.is_active)
        self.assertEqual(self.sub.next_billing_date, self.today)

    def test_edit_and_delete_keep_history(self):
        Transaction.objects.create(
            user=self.user, wallet=self.wallet, transaction_type='expense', amount=Decimal('100000'),
            source='subscription', subscription=self.sub,
        )
        self.client.post(reverse('finance:subscription_edit', args=[self.sub.pk]), {
            'name': 'Netflix Premium', 'amount': '260000', 'wallet': self.wallet.pk, 'billing_cycle': 'monthly',
            'start_date': self.today.isoformat(), 'next_billing_date': self.today.isoformat(),
        })
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.amount, Decimal('260000'))
        self.client.post(reverse('finance:subscription_delete', args=[self.sub.pk]))
        self.assertEqual(Transaction.objects.count(), 1)


class SavingGoalTest(FinanceTestCase):
    def setUp(self):
        super().setUp()
        self.goal = SavingGoal.objects.create(user=self.user, name='Laptop', target_amount=Decimal('1000000'))

    def adjust(self, action, amount):
        return self.client.post(reverse('finance:saving_goal_adjust', args=[self.goal.pk]), {'action': action, 'amount': amount})

    def test_deposit_withdraw_clamped(self):
        self.adjust('deposit', 300000)
        self.adjust('withdraw', 999999)
        self.goal.refresh_from_db()
        self.assertEqual(self.goal.current_amount, Decimal('0'))

    def test_reaching_target_awards_xp_once(self):
        self.adjust('deposit', 1000000)
        self.goal.refresh_from_db()
        self.assertTrue(self.goal.is_completed)
        self.adjust('withdraw', 10)
        self.adjust('deposit', 10)
        self.assertEqual(XPEvent.objects.filter(key=f'saving_goal:{self.goal.pk}').count(), 1)

    def test_monthly_needed(self):
        self.goal.deadline = self.today + timedelta(days=150)
        self.goal.current_amount = Decimal('400000')
        months = (self.goal.deadline.year - self.today.year) * 12 + self.goal.deadline.month - self.today.month
        self.assertEqual(self.goal.monthly_needed, round(Decimal('600000') / months, 0))

    def test_wishlist_item_uses_goal(self):
        item = WishlistItem.objects.create(
            user=self.user, wallet=self.wallet, name='Laptop', price=Decimal('800000'), saving_goal=self.goal,
        )
        self.adjust('deposit', 400000)
        item.refresh_from_db()
        self.assertEqual(item.affordability(), 50)
        self.adjust('deposit', 600000)
        self.client.post(reverse('finance:wishlist_purchase', args=[item.pk]))
        self.goal.refresh_from_db()
        self.assertEqual(self.goal.current_amount, Decimal('200000'))
        self.assertFalse(self.goal.is_completed)
        self.assertEqual(Transaction.objects.get(source='wishlist').category.name, 'Mua sắm')

    def test_cannot_adjust_other_users_goal(self):
        foreign = SavingGoal.objects.create(user=self.other, name='X', target_amount=Decimal('10'))
        response = self.client.post(reverse('finance:saving_goal_adjust', args=[foreign.pk]), {'action': 'deposit', 'amount': 5})
        self.assertEqual(response.status_code, 404)


class WishlistManagementTest(FinanceTestCase):
    def test_purchase_without_wallet_is_refused(self):
        item = WishlistItem.objects.create(user=self.user, name='Ghế', price=Decimal('100'))
        self.client.post(reverse('finance:wishlist_purchase', args=[item.pk]))
        item.refresh_from_db()
        self.assertFalse(item.is_purchased)

    def test_edit_and_delete(self):
        item = WishlistItem.objects.create(user=self.user, name='Ghế', price=Decimal('100'))
        self.client.post(reverse('finance:wishlist_edit', args=[item.pk]), {
            'name': 'Ghế công thái học', 'price': '3000000', 'priority': 3, 'wallet': self.wallet.pk,
        })
        item.refresh_from_db()
        self.assertEqual((item.name, item.wallet), ('Ghế công thái học', self.wallet))
        self.client.post(reverse('finance:wishlist_delete', args=[item.pk]))
        self.assertFalse(WishlistItem.objects.exists())


class TransactionFilterTest(FinanceTestCase):
    def setUp(self):
        super().setUp()
        for i in range(30):
            Transaction.objects.create(
                user=self.user, wallet=self.wallet, transaction_type='expense', category=self.food,
                amount=Decimal(1000 * (i + 1)), date=date(2026, 9, 1) + timedelta(days=i), note=f'Cơm {i}',
            )
        Transaction.objects.create(
            user=self.user, wallet=self.wallet, transaction_type='income', category=self.salary,
            amount=Decimal('9000000'), date=date(2026, 10, 5), note='Lương tháng 10',
        )

    def get(self, **params):
        return self.client.get(reverse('finance:transaction_list'), params)

    def test_pagination(self):
        first = self.get()
        self.assertEqual(len(first.context['transactions']), 25)
        self.assertEqual(len(self.get(page=2).context['transactions']), 6)

    def test_filters_combine_and_totals_follow(self):
        response = self.get(type='expense', date_from='2026-09-10', date_to='2026-09-12')
        self.assertEqual(response.context['page_obj'].paginator.count, 3)
        self.assertEqual(response.context['filtered_expense'], Decimal('10000') + Decimal('11000') + Decimal('12000'))
        self.assertEqual(response.context['filtered_income'], Decimal('0'))
        self.assertEqual(self.get(q='lương').context['page_obj'].paginator.count, 1)
        self.assertEqual(self.get(amount_min='29000').context['page_obj'].paginator.count, 3)
        self.assertEqual(self.get(category=self.salary.pk).context['page_obj'].paginator.count, 1)

    def test_pagination_links_keep_filters(self):
        response = self.get(type='expense')
        self.assertContains(response, 'type=expense&amp;page=2')

    def test_invalid_filter_values_are_ignored(self):
        response = self.get(date_from='not-a-date', wallet='abc')
        self.assertEqual(response.status_code, 200)


class CsvImportTest(FinanceTestCase):
    def run_import(self, text, encoding='utf-8'):
        return import_transactions_csv(self.user, self.wallet, text.encode(encoding))

    def test_parse_amount_formats(self):
        cases = {
            '1.250.000': Decimal('1250000'), '1,250,000.50': Decimal('1250000.50'),
            '1.250.000,50': Decimal('1250000.50'), '-50.000 đ': Decimal('-50000'),
            '(200)': Decimal('-200'), '50000.00': Decimal('50000.00'), '12,5': Decimal('12.5'),
            '': None, 'abc': None,
        }
        for raw, expected in cases.items():
            self.assertEqual(parse_amount(raw), expected, raw)

    def test_parse_date_formats(self):
        for raw in ('2026-10-31', '31/10/2026', '31-10-2026', '31.10.2026', '2026-10-31 08:15:00'):
            self.assertEqual(parse_date(raw), date(2026, 10, 31), raw)
        self.assertIsNone(parse_date('31/13/2026'))

    def test_bank_debit_credit_columns_with_semicolon(self):
        result = self.run_import(
            'Ngày GD;Diễn giải;Ghi nợ;Ghi có\n'
            '31/10/2026;Cà phê;45.000;\n'
            '30/10/2026;Lương tháng 10;;15.000.000\n'
        )
        self.assertEqual(result['created'], 2)
        self.assertEqual(self.balance(), Decimal('1000000') - 45000 + 15000000)
        coffee = Transaction.objects.get(note='Cà phê')
        self.assertEqual((coffee.transaction_type, coffee.amount), ('expense', Decimal('45000')))

    def test_signed_amount_and_category_matching(self):
        self.run_import('date,description,amount,category\n2026-10-01,Bún bò,-35000,ăn uống\n2026-10-02,Bonus,500000,\n')
        bun = Transaction.objects.get(note='Bún bò')
        self.assertEqual((bun.transaction_type, bun.category), ('expense', self.food))
        self.assertEqual(Transaction.objects.get(note='Bonus').transaction_type, 'income')

    def test_reimport_skips_duplicates(self):
        text = 'Ngày,Số tiền,Ghi chú\n2026-10-01,-35000,Bún bò\n2026-10-01,-35000,Bún bò\n'
        first = self.run_import(text)
        second = self.run_import(text)
        self.assertEqual((first['created'], first['duplicates']), (1, 1))
        self.assertEqual((second['created'], second['duplicates']), (0, 2))
        self.assertEqual(Transaction.objects.count(), 1)

    def test_bad_rows_reported_good_rows_kept(self):
        result = self.run_import('Ngày,Số tiền\n2026-10-01,-1000\nhôm qua,-2000\n2026-10-03,\n\n2026-10-04,0\n')
        self.assertEqual(result['created'], 1)
        self.assertEqual([line for line, _ in result['errors']], [3, 4, 6])

    def test_missing_columns(self):
        result = self.run_import('foo,bar\n1,2\n')
        self.assertEqual(result['created'], 0)
        self.assertTrue(result['errors'])

    def test_round_trip_with_export(self):
        self.add_txn(45000, category=self.food, note='Cơm trưa', day=date(2026, 10, 1))
        self.add_txn(2000000, kind='income', category=self.salary, note='Lương', day=date(2026, 10, 2))
        exported = export_csv(self.user, 'transactions')
        bank = Wallet.objects.create(user=self.user, name='Ngân hàng')
        result = import_transactions_csv(self.user, bank, exported.encode('utf-8'))
        self.assertEqual(result['created'], 2)
        imported = Transaction.objects.filter(wallet=bank)
        self.assertEqual(imported.get(note='Cơm trưa').category, self.food)
        self.assertEqual(imported.get(note='Lương').transaction_type, 'income')
        self.assertEqual(self.balance(bank), Decimal('1955000'))

    def test_cp1258_and_upload_view(self):
        upload = SimpleUploadedFile('sao-ke.csv', 'Ngày,Số tiền,Ghi chú\n2026-10-01,-1000,Phở\n'.encode('utf-8-sig'))
        response = self.client.post(reverse('finance:transaction_import'), {'wallet': self.wallet.pk, 'file': upload})
        self.assertEqual(response.context['result']['created'], 1)
        self.assertTrue(Transaction.objects.filter(note='Phở').exists())

    def test_cannot_import_into_other_users_wallet(self):
        foreign = Wallet.objects.create(user=self.other, name='Lạ')
        upload = SimpleUploadedFile('a.csv', b'date,amount\n2026-10-01,-1\n')
        response = self.client.post(reverse('finance:transaction_import'), {'wallet': foreign.pk, 'file': upload})
        self.assertIsNone(response.context['result'])
        self.assertFalse(Transaction.objects.exists())


class FinanceStatsTest(FinanceTestCase):
    def test_savings_rate(self):
        self.assertIsNone(savings_rate(Decimal('0'), Decimal('100')))
        self.assertEqual(savings_rate(Decimal('1000'), Decimal('250')), 75)
        self.assertEqual(savings_rate(Decimal('1000'), Decimal('1500')), -50)

    def test_category_spending(self):
        transport = Category.objects.get(user=self.user, name='Di chuyển')
        self.add_txn(300, category=self.food)
        self.add_txn(150, category=transport)
        self.add_txn(50)
        self.add_txn(999, kind='income', category=self.salary)
        rows = category_spending(self.user, self.today.year, self.today.month)
        self.assertEqual([(r['name'], r['percent']) for r in rows],
                         [('Ăn uống', Decimal('60.0')), ('Di chuyển', Decimal('30.0')), ('Chưa phân loại', Decimal('10.0'))])

    def test_dashboard_context(self):
        self.add_txn(1000, kind='income', category=self.salary)
        self.add_txn(400, category=self.food)
        response = self.client.get(reverse('finance:dashboard'))
        self.assertEqual(response.context['month_savings_rate'], 60)
        self.assertEqual(response.context['category_spending'][0]['name'], 'Ăn uống')

    def test_weekly_review_has_savings_rate(self):
        self.add_txn(1000, kind='income', category=self.salary)
        self.add_txn(250, category=self.food)
        response = self.client.get(reverse('core:weekly_review'))
        self.assertEqual(response.context['savings_rate'], 75)

    def test_all_finance_pages_render(self):
        goal = SavingGoal.objects.create(user=self.user, name='G', target_amount=Decimal('10'))
        names = ['dashboard', 'wallet_list', 'category_list', 'transaction_list', 'transaction_import',
                 'transfer_list', 'budget_list', 'subscription_list', 'saving_goal_list', 'wishlist', 'asset_list']
        for name in names:
            self.assertEqual(self.client.get(reverse(f'finance:{name}')).status_code, 200, name)
        self.assertEqual(self.client.get(reverse('finance:saving_goal_edit', args=[goal.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('finance:wallet_edit', args=[self.wallet.pk])).status_code, 200)
