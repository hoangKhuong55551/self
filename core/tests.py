from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal
from finance.models import Wallet, WishlistItem, Transaction, Asset
from productivity.models import Goal, Task, Habit, HabitLog

User = get_user_model()

class CrossModuleIntegrationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='teststudent', password='password123')
        self.wallet = Wallet.objects.create(user=self.user, name='Ví chính', balance=Decimal('1000000'))

    def test_user_profile_auto_created(self):
        """Kiểm tra signal tự động tạo UserProfile khi tạo User."""
        self.assertIsNotNone(self.user.profile)
        self.assertEqual(self.user.profile.level, 1)
        self.assertEqual(self.user.profile.hp, 100)

    def test_wishlist_to_transaction_and_asset(self):
        """Kiểm tra Liên kết 2: Wishlist -> Transaction + Asset + Trừ Ví."""
        item = WishlistItem.objects.create(
            user=self.user,
            wallet=self.wallet,
            name='Giày chạy bộ Nike',
            price=Decimal('200000')
        )
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(Asset.objects.count(), 0)

        # Đánh dấu đã mua
        item.is_purchased = True
        item.save()

        # Kiểm tra Transaction được tạo
        self.assertEqual(Transaction.objects.count(), 1)
        txn = Transaction.objects.first()
        self.assertEqual(txn.amount, Decimal('200000'))
        self.assertEqual(txn.source, 'wishlist')

        # Kiểm tra ví bị trừ tiền
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('800000'))

        # Kiểm tra Asset được tạo
        self.assertEqual(Asset.objects.count(), 1)
        asset = Asset.objects.first()
        self.assertEqual(asset.name, 'Giày chạy bộ Nike')

    def test_task_done_recalculates_goal_and_gives_xp(self):
        """Kiểm tra Liên kết 3: Task Done -> Recalculate Goal Progress + Cộng XP."""
        goal = Goal.objects.create(user=self.user, title='Hoàn thành Đồ án Django')
        task1 = Task.objects.create(goal=goal, title='Thiết kế CSDL', status='todo', quadrant='do')
        task2 = Task.objects.create(goal=goal, title='Xây dựng Frontend', status='todo', quadrant='schedule')

        self.assertEqual(goal.progress, 0)
        initial_xp = self.user.profile.xp

        # Hoàn thành task 1
        task1.status = 'done'
        task1.save()

        goal.refresh_from_db()
        self.assertEqual(goal.progress, 50.0)
        self.assertEqual(goal.status, 'in_progress')

        self.user.profile.refresh_from_db()
        # quadrant 'do' = 10 base + 20 bonus = 30 XP
        self.assertEqual(self.user.profile.xp, initial_xp + 30)
