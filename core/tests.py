from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from decimal import Decimal
from finance.models import Wallet, WishlistItem, Transaction, Asset
from productivity.models import Goal, Task, Habit, HabitLog
from core.models import UserProfile

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


class XPLedgerTest(TestCase):
    """Sổ XP: mỗi nguồn thưởng chỉ được cộng một lần."""

    def setUp(self):
        from productivity.models import Goal, Task, Habit
        self.user = User.objects.create_user(username='xp_farmer', password='password123')
        self.goal = Goal.objects.create(user=self.user, title='Goal')
        self.task = Task.objects.create(goal=self.goal, title='Task', quadrant='do')
        self.habit = Habit.objects.create(user=self.user, name='Chạy bộ')
        self.client = Client()
        self.client.login(username='xp_farmer', password='password123')

    def _xp_events_total(self):
        return sum(self.user.xp_events.values_list('amount', flat=True))

    def test_task_toggle_awards_once(self):
        for status in ['done', 'todo', 'done', 'todo', 'done']:
            self.task.status = status
            self.task.save()
        self.assertEqual(self._xp_events_total(), 30)

    def test_habit_toggle_awards_once_per_day(self):
        url = reverse('productivity:toggle_habit', args=[self.habit.pk])
        for _ in range(5):
            self.client.post(url)
        self.assertEqual(self._xp_events_total(), 10)

    def test_award_xp_once_uses_fresh_profile(self):
        stale = UserProfile.objects.get(user=self.user)
        UserProfile.objects.get(user=self.user).add_xp(40)
        stale.award_xp_once('manual:1', 5)
        self.assertEqual(UserProfile.objects.get(user=self.user).xp, 45)


class GlobalSearchTest(TestCase):
    def setUp(self):
        from library.models import MediaItem
        from academic.models import Note
        self.user = User.objects.create_user(username='searcher', password='password123')
        other = User.objects.create_user(username='other', password='password123')
        goal = Goal.objects.create(user=self.user, title='Học Django')
        Task.objects.create(goal=goal, title='Viết signal Django')
        Note.objects.create(user=self.user, title='Ghi chú Django ORM', content='...')
        MediaItem.objects.create(user=self.user, title='Two Scoops of Django')
        MediaItem.objects.create(user=other, title='Django bí mật của người khác')
        self.client = Client()
        self.client.login(username='searcher', password='password123')

    def test_search_across_modules_only_own_data(self):
        data = self.client.get(reverse('core:search'), {'q': 'django'}).json()
        titles = [r['title'] for r in data['results']]
        self.assertIn('Viết signal Django', titles)
        self.assertIn('Ghi chú Django ORM', titles)
        self.assertIn('Two Scoops of Django', titles)
        self.assertNotIn('Django bí mật của người khác', titles)

    def test_short_query_returns_nothing(self):
        self.assertEqual(self.client.get(reverse('core:search'), {'q': 'd'}).json()['results'], [])


class AchievementTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='hunter', password='password123')
        self.client = Client()
        self.client.login(username='hunter', password='password123')
        self.goal = Goal.objects.create(user=self.user, title='G')

    def test_first_task_unlocks_once_and_awards_bonus(self):
        from core.achievements import evaluate_achievements
        task = Task.objects.create(goal=self.goal, title='T', quadrant='do')
        task.status = 'done'
        task.save()

        _, new = evaluate_achievements(self.user)
        self.assertIn('first_task', [a.code for a in new])
        _, new_again = evaluate_achievements(self.user)
        self.assertEqual(new_again, [])
        self.assertTrue(self.user.xp_events.filter(key='achievement:first_task', amount=10).exists())

    def test_achievements_page_shows_progress(self):
        response = self.client.get(reverse('core:achievements'))
        self.assertEqual(response.status_code, 200)
        first = next(p for p in response.context['progress'] if p['achievement'].code == 'first_task')
        self.assertEqual(first['percent'], 0)
        self.assertIsNone(first['unlocked_at'])


class WeeklyReviewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='reviewer', password='password123')
        self.client = Client()
        self.client.login(username='reviewer', password='password123')

    def test_review_page_and_save_reflection(self):
        from core.models import WeeklyReflection
        response = self.client.get(reverse('core:weekly_review'))
        self.assertEqual(response.status_code, 200)
        week_start = response.context['week_start']
        self.assertEqual(week_start.weekday(), 0)
        self.assertIsNone(response.context['next_week'])

        self.client.post(reverse('core:weekly_review') + f'?week={week_start.isoformat()}', {
            'mood': 4, 'went_well': 'Đọc xong sách', 'to_improve': '', 'next_focus': 'Ôn thi',
        })
        reflection = WeeklyReflection.objects.get(user=self.user, week_start=week_start)
        self.assertEqual(reflection.mood, 4)

    def test_future_week_is_clamped_and_bad_input_ignored(self):
        response = self.client.get(reverse('core:weekly_review'), {'week': '2999-01-01'})
        self.assertEqual(response.context['is_current_week'], True)
        response = self.client.get(reverse('core:weekly_review'), {'week': 'abc'})
        self.assertEqual(response.status_code, 200)


class NotificationsTest(TestCase):
    def test_overdue_task_appears_in_bell(self):
        from datetime import timedelta
        from django.utils import timezone
        user = User.objects.create_user(username='late', password='password123')
        goal = Goal.objects.create(user=user, title='G')
        Task.objects.create(goal=goal, title='Nộp báo cáo', due_date=timezone.localdate() - timedelta(days=2))
        Task.objects.create(goal=goal, title='Đã xong rồi', status='done', due_date=timezone.localdate() - timedelta(days=2))
        client = Client()
        client.login(username='late', password='password123')
        response = client.get(reverse('core:dashboard'))
        titles = [n['title'] for n in response.context['notifications']]
        self.assertIn('Nộp báo cáo', titles)
        self.assertNotIn('Đã xong rồi', titles)
        self.assertContains(response, 'Trễ hạn 2 ngày')


class ExportTest(TestCase):
    def setUp(self):
        from library.models import MediaItem
        self.user = User.objects.create_user(username='exporter', password='password123')
        other = User.objects.create_user(username='someone', password='password123')
        MediaItem.objects.create(user=self.user, title='Sách của tôi')
        MediaItem.objects.create(user=other, title='Sách người khác')
        self.client = Client()
        self.client.login(username='exporter', password='password123')

    def test_json_backup_contains_only_own_data(self):
        import json
        response = self.client.get(reverse('core:export_download', args=['json']))
        self.assertIn('attachment', response['Content-Disposition'])
        data = json.loads(response.content)
        titles = [row['fields']['title'] for row in data['models']['library.MediaItem']]
        self.assertEqual(titles, ['Sách của tôi'])

    def test_csv_exports(self):
        from core.exports import CSV_EXPORTS
        for kind in CSV_EXPORTS:
            response = self.client.get(reverse('core:export_download', args=[kind]))
            self.assertEqual(response.status_code, 200, kind)
        library_csv = self.client.get(reverse('core:export_download', args=['library'])).content.decode('utf-8-sig')
        self.assertIn('Sách của tôi', library_csv)
        self.assertNotIn('Sách người khác', library_csv)
        self.assertEqual(self.client.get(reverse('core:export_download', args=['nope'])).status_code, 404)


class PWATest(TestCase):
    def test_service_worker_and_offline_page(self):
        client = Client()
        sw = client.get('/sw.js')
        self.assertEqual(sw.status_code, 200)
        self.assertEqual(sw['Content-Type'], 'application/javascript')
        self.assertContains(sw, "OFFLINE_URL = '/offline/'")
        self.assertEqual(client.get(reverse('core:offline')).status_code, 200)
