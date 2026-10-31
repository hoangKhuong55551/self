from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from decimal import Decimal
from io import StringIO

from dateutil.relativedelta import relativedelta
from django.core.management import call_command
from django.utils import timezone

from finance.models import Asset, Budget, Category, Subscription, Transaction, Wallet, WishlistItem, WorkoutLog

User = get_user_model()

class FinanceModuleTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='financier', password='password123')
        self.client = Client()
        self.client.login(username='financier', password='password123')
        self.wallet = Wallet.objects.create(user=self.user, name='Ví tiền', balance=Decimal('5000000'))
        self.category = Category.objects.create(user=self.user, name='Ăn uống', type='expense')

    def test_finance_dashboard_view(self):
        response = self.client.get(reverse('finance:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '5000000')

    def test_create_transaction_updates_wallet(self):
        response = self.client.post(reverse('finance:transaction_list'), {
            'wallet': self.wallet.pk,
            'category': self.category.pk,
            'transaction_type': 'expense',
            'amount': '50000',
            'date': '2026-10-28',
            'note': 'Ăn trưa'
        })
        self.assertEqual(response.status_code, 302)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('4950000'))

    def test_wishlist_purchase_flow(self):
        item = WishlistItem.objects.create(
            user=self.user,
            wallet=self.wallet,
            name='Bàn phím cơ',
            price=Decimal('1000000')
        )
        response = self.client.post(reverse('finance:wishlist_purchase', args=[item.pk]))
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertTrue(item.is_purchased)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('4000000'))


class TransactionSecurityTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='owner', password='password123')
        self.other = User.objects.create_user(username='intruder', password='password123')
        self.client.login(username='intruder', password='password123')
        self.victim_wallet = Wallet.objects.create(user=self.user, name='Ví chính', balance=Decimal('1000'))

    def test_cannot_post_transaction_to_other_users_wallet(self):
        self.client.post(reverse('finance:transaction_list'), {
            'wallet': self.victim_wallet.pk, 'transaction_type': 'expense',
            'amount': '500', 'date': '2026-10-28', 'note': 'hack',
        })
        self.victim_wallet.refresh_from_db()
        self.assertEqual(self.victim_wallet.balance, Decimal('1000'))
        self.assertFalse(Transaction.objects.exists())

    def test_cannot_purchase_other_users_wishlist_item(self):
        item = WishlistItem.objects.create(user=self.user, wallet=self.victim_wallet, name='X', price=Decimal('100'))
        response = self.client.post(reverse('finance:wishlist_purchase', args=[item.pk]))
        self.assertEqual(response.status_code, 404)

    def test_income_increases_balance(self):
        wallet = Wallet.objects.create(user=self.other, name='Ví', balance=Decimal('0'))
        self.client.post(reverse('finance:transaction_list'), {
            'wallet': wallet.pk, 'transaction_type': 'income', 'amount': '2000', 'date': '2026-10-28',
        })
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, Decimal('2000'))


class WishlistPurchaseTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='buyer', password='password123')
        self.client.login(username='buyer', password='password123')
        self.wallet = Wallet.objects.create(user=self.user, name='Ví', balance=Decimal('1000'))
        self.item = WishlistItem.objects.create(
            user=self.user, wallet=self.wallet, name='Tai nghe', price=Decimal('300')
        )

    def test_get_does_not_purchase(self):
        self.client.get(reverse('finance:wishlist_purchase', args=[self.item.pk]))
        self.item.refresh_from_db()
        self.assertFalse(self.item.is_purchased)

    def test_purchase_creates_asset_and_is_idempotent(self):
        url = reverse('finance:wishlist_purchase', args=[self.item.pk])
        self.client.post(url)
        self.client.post(url)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('700'))
        self.assertEqual(Transaction.objects.filter(source='wishlist').count(), 1)
        self.assertEqual(Asset.objects.get(from_wishlist=self.item).purchase_price, Decimal('300'))


class BudgetTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='budgeter', password='password123')
        self.client.login(username='budgeter', password='password123')
        self.wallet = Wallet.objects.create(user=self.user, name='Ví', balance=Decimal('10000000'))
        self.food = Category.objects.create(user=self.user, name='Ăn uống', type='expense')
        self.today = timezone.now().date()
        self.budget = Budget.objects.create(
            user=self.user, category=self.food, month=self.today.month, year=self.today.year,
            amount=Decimal('1000'),
        )

    def _spend(self, amount, day=None):
        return self.client.post(reverse('finance:transaction_list'), {
            'wallet': self.wallet.pk, 'category': self.food.pk, 'transaction_type': 'expense',
            'amount': str(amount), 'date': (day or self.today).isoformat(),
        })

    def test_spent_only_counts_current_month(self):
        self._spend(400)
        self._spend(9999, day=self.today - relativedelta(months=1))
        self.assertEqual(self.budget.spent, Decimal('400'))
        self.assertEqual(self.budget.remaining, Decimal('600'))
        self.assertEqual(self.budget.percent_used, Decimal('40.0'))
        self.assertFalse(self.budget.is_over_budget)

    def test_overspending_costs_hp(self):
        hp_before = self.user.profile.hp
        self._spend(1500)  # vượt 50% => mất 10 HP
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.hp, hp_before - 10)

    def test_duplicate_budget_shows_form_error_instead_of_crashing(self):
        response = self.client.post(reverse('finance:budget_list'), {
            'category': self.food.pk, 'amount': '5000', 'month': self.today.month, 'year': self.today.year,
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.assertEqual(Budget.objects.count(), 1)

    def test_duplicate_wallet_name_shows_form_error(self):
        response = self.client.post(reverse('finance:wallet_list'), {
            'name': 'Ví', 'balance': '0', 'currency': 'VND', 'icon': 'wallet',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)


class SubscriptionTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='subber', password='password123')
        self.wallet = Wallet.objects.create(user=self.user, name='Ví', balance=Decimal('1000000'))
        self.today = timezone.now().date()

    def _sub(self, cycle='monthly', next_date=None, active=True):
        return Subscription.objects.create(
            user=self.user, wallet=self.wallet, name='Netflix', amount=Decimal('100000'),
            billing_cycle=cycle, start_date=self.today, next_billing_date=next_date or self.today,
            is_active=active,
        )

    def test_monthly_cost(self):
        self.assertEqual(self._sub('monthly').monthly_cost, Decimal('100000'))
        self.assertEqual(self._sub('yearly').monthly_cost, Decimal('8333.33'))
        self.assertEqual(self._sub('weekly').monthly_cost, Decimal('433000'))

    def test_command_charges_due_and_skips_inactive(self):
        due = self._sub()
        self._sub(active=False)
        self._sub(next_date=self.today + relativedelta(days=3))
        call_command('process_subscriptions', stdout=StringIO())
        self.wallet.refresh_from_db()
        due.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('900000'))
        self.assertEqual(due.next_billing_date, self.today + relativedelta(months=1))

    def test_overdue_subscription_catches_up_all_missed_cycles(self):
        sub = self._sub(next_date=self.today - relativedelta(months=2))
        call_command('process_subscriptions', stdout=StringIO())
        sub.refresh_from_db()
        self.assertEqual(Transaction.objects.filter(subscription=sub).count(), 3)
        self.assertGreater(sub.next_billing_date, self.today)

    def test_middleware_runs_once_per_day(self):
        self._sub()
        self.client.login(username='subber', password='password123')
        self.client.get(reverse('finance:dashboard'))
        self.client.get(reverse('finance:dashboard'))
        self.assertEqual(Transaction.objects.filter(source='subscription').count(), 1)


class WorkoutGearTest(TestCase):
    def test_gear_wear_updates_condition(self):
        user = User.objects.create_user(username='runner', password='password123')
        shoes = Asset.objects.create(user=user, name='Giày chạy', max_lifespan_hours=10)
        WorkoutLog.objects.create(user=user, activity_type='running', duration_minutes=300, gear_used=shoes)
        shoes.refresh_from_db()
        self.assertEqual(shoes.usage_hours, 5)
        self.assertEqual(shoes.condition, 'worn')
        WorkoutLog.objects.create(user=user, activity_type='running', duration_minutes=240, gear_used=shoes)
        shoes.refresh_from_db()
        self.assertTrue(shoes.needs_replacement)
        self.assertEqual(shoes.condition, 'replace')
