from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from decimal import Decimal
from finance.models import Wallet, WishlistItem, Transaction, Asset
from productivity.models import Goal, Task, Habit
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
        Task.objects.create(goal=goal, title='Xây dựng Frontend', status='todo', quadrant='schedule')

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
        from productivity.models import Goal, Task
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


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                                       'LOCATION': 'notifications-test'}})
class NotificationsCacheTest(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.user = User.objects.create_user(username='cached', password='password123')
        self.goal = Goal.objects.create(user=self.user, title='G')

    def _titles(self):
        from core.notifications import get_notifications
        return [n['title'] for n in get_notifications(self.user)[0]]

    def test_second_call_hits_cache(self):
        from core.notifications import get_notifications
        get_notifications(self.user)
        with self.assertNumQueries(0):
            get_notifications(self.user)

    def test_task_changes_invalidate_cache(self):
        from django.utils import timezone
        self.assertEqual(self._titles(), [])
        task = Task.objects.create(goal=self.goal, title='Hạn hôm nay', due_date=timezone.localdate())
        self.assertIn('Hạn hôm nay', self._titles())
        task.status = 'done'
        task.save()
        self.assertNotIn('Hạn hôm nay', self._titles())

    def test_overspending_invalidates_cache(self):
        from django.utils import timezone
        from finance.models import Budget, Category
        today = timezone.localdate()
        wallet = Wallet.objects.create(user=self.user, name='Ví', balance=Decimal('1000000'))
        food = Category.objects.create(user=self.user, name='Ăn', type='expense')
        Budget.objects.create(user=self.user, category=food, month=today.month, year=today.year, amount=Decimal('100'))
        self.assertEqual(self._titles(), [])
        Transaction.objects.create(user=self.user, wallet=wallet, category=food, transaction_type='expense',
                                   amount=Decimal('500'), date=today)
        self.assertIn('Vượt ngân sách Ăn', self._titles())

    def test_cache_is_per_user(self):
        from django.utils import timezone
        other = User.objects.create_user(username='other', password='password123')
        Task.objects.create(goal=self.goal, title='Của tôi', due_date=timezone.localdate())
        self.assertIn('Của tôi', self._titles())
        from core.notifications import get_notifications
        self.assertEqual(get_notifications(other)[0], [])


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


@override_settings(AXES_ENABLED=True, AXES_FAILURE_LIMIT=3)
class LoginLockoutTest(TestCase):
    def setUp(self):
        User.objects.create_user(username='victim', password='correct-horse-1')

    def _login(self, password):
        return self.client.post(reverse('login'), {'username': 'victim', 'password': password})

    def test_locks_after_repeated_failures_even_with_correct_password(self):
        for _ in range(2):
            self.assertContains(self._login('wrong'), 'không chính xác')
        locked = self._login('wrong')
        self.assertEqual(locked.status_code, 429)
        self.assertContains(locked, 'Tạm khoá đăng nhập', status_code=429)
        self.assertContains(locked, '15 phút', status_code=429)
        # Đã bị khoá thì mật khẩu đúng cũng không vào được
        self.assertEqual(self._login('correct-horse-1').status_code, 429)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_success_resets_failure_counter(self):
        self._login('wrong')
        self._login('wrong')
        self.assertEqual(self._login('correct-horse-1').status_code, 302)
        self.client.logout()
        self._login('wrong')
        self._login('wrong')
        self.assertEqual(self._login('correct-horse-1').status_code, 302)


class AdminUrlTest(TestCase):
    def test_admin_link_only_for_staff(self):
        user = User.objects.create_user(username='normal', password='password123')
        self.client.force_login(user)
        self.assertNotContains(self.client.get(reverse('core:dashboard')), reverse('admin:index'))
        user.is_staff = True
        user.save()
        self.assertContains(self.client.get(reverse('core:dashboard')), reverse('admin:index'))

    def test_service_worker_skips_configured_admin_prefix(self):
        response = self.client.get(reverse('core:service_worker'))
        self.assertContains(response, f"const ADMIN_PREFIX = '{reverse('admin:index')}'".replace('/', '\u002F'))


class RegistrationToggleTest(TestCase):
    @override_settings(ALLOW_REGISTRATION=False)
    def test_registration_can_be_disabled(self):
        self.assertEqual(self.client.get(reverse('core:register')).status_code, 404)
        response = self.client.post(reverse('core:register'), {
            'username': 'stranger', 'first_name': 'A', 'last_name': 'B', 'email': 'a@b.vn',
            'password1': 'Very-strong-pass-9', 'password2': 'Very-strong-pass-9',
        })
        self.assertEqual(response.status_code, 404)
        self.assertFalse(User.objects.filter(username='stranger').exists())
        self.assertNotContains(self.client.get(reverse('login')), reverse('core:register'))

    def test_registration_logs_user_in(self):
        response = self.client.post(reverse('core:register'), {
            'username': 'newbie', 'first_name': 'A', 'last_name': 'B', 'email': 'a@b.vn',
            'password1': 'Very-strong-pass-9', 'password2': 'Very-strong-pass-9',
        })
        self.assertRedirects(response, reverse('core:dashboard'))
        self.assertEqual(int(self.client.session['_auth_user_id']), User.objects.get(username='newbie').pk)


class SeedDataGuardTest(TestCase):
    @override_settings(DEBUG=False)
    def test_refuses_to_create_weak_superuser_in_production(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            call_command('seed_data')
        self.assertFalse(User.objects.filter(username='student').exists())


class ProfileSaveTest(TestCase):
    def test_saving_user_does_not_overwrite_newer_xp(self):
        user = User.objects.create_user(username='stale', password='password123')
        user.profile  # profile được nạp vào bộ nhớ (xp=0)
        UserProfile.objects.filter(user=user).update(xp=50, hp=70)  # nơi khác vừa cộng XP / trừ HP
        user.first_name = 'Đổi tên'
        user.save()
        profile = UserProfile.objects.get(user=user)
        self.assertEqual((profile.xp, profile.hp), (50, 70))

    def test_login_updates_last_active_without_touching_xp(self):
        from datetime import timedelta
        from django.utils import timezone
        user = User.objects.create_user(username='active', password='password123')
        UserProfile.objects.filter(user=user).update(xp=42, last_active=timezone.localdate() - timedelta(days=3))
        self.client.post(reverse('login'), {'username': 'active', 'password': 'password123'})
        profile = UserProfile.objects.get(user=user)
        self.assertEqual(profile.last_active, timezone.localdate())
        self.assertEqual(profile.xp, 42)


class CssPctFilterTest(TestCase):
    def test_always_dot_decimal_and_clamped(self):
        from django.utils import translation
        from core.templatetags.core_tags import css_pct
        from django.template import Context, Template
        with translation.override('vi'):
            html = Template('{{ v|css_pct }}').render(Context({'v': 100 / 3}))
        self.assertEqual(html, '33.33')
        self.assertEqual(css_pct(Decimal('250')), '100')
        self.assertEqual(css_pct(-5), '0')
        self.assertEqual(css_pct(None), '0')
        self.assertEqual(css_pct(40), '40')
