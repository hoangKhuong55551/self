from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from decimal import Decimal
from finance.models import Wallet, Category, WishlistItem

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
        response = self.client.get(reverse('finance:wishlist_purchase', args=[item.pk]))
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertTrue(item.is_purchased)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('4000000'))
