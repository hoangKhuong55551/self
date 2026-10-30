from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from core.models import UserProfile
from library.models import MediaItem, LibraryGoal
from library.signals import XP_REWARDS

User = get_user_model()


class LibraryModuleTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='bookworm', password='password123')
        UserProfile.objects.get_or_create(user=self.user)
        self.client = Client()
        self.client.login(username='bookworm', password='password123')

        self.book = MediaItem.objects.create(
            user=self.user, media_type='book', title='Nhà Giả Kim', creator='Paulo Coelho',
            progress_total=228,
        )

    def _profile_xp_total(self):
        profile = UserProfile.objects.get(user=self.user)
        # Quy đổi level + xp thành tổng để so sánh không phụ thuộc vào ngưỡng level
        return profile.level, profile.xp

    def test_progress_percent_and_unit(self):
        self.book.progress_current = 57
        self.assertEqual(self.book.progress_percent, 25)
        self.assertEqual(self.book.progress_unit, 'trang')

    def test_start_sets_started_on(self):
        self.book.status = MediaItem.Status.IN_PROGRESS
        self.book.save()
        self.book.refresh_from_db()
        self.assertEqual(self.book.started_on, timezone.localdate())

    def test_done_fills_progress_and_awards_xp_once(self):
        before = self._profile_xp_total()
        self.book.status = MediaItem.Status.DONE
        self.book.save()
        self.book.refresh_from_db()
        self.assertEqual(self.book.progress_current, 228)
        self.assertEqual(self.book.finished_on, timezone.localdate())
        after_first = self._profile_xp_total()
        self.assertNotEqual(before, after_first)

        # Lưu lại khi đã 'done' không được cộng XP thêm lần nữa
        self.book.review = 'Rất hay'
        self.book.save()
        self.assertEqual(self._profile_xp_total(), after_first)

    def test_quick_progress_completes_item(self):
        self.book.progress_current = 220
        self.book.status = MediaItem.Status.IN_PROGRESS
        self.book.save()
        self.client.post(reverse('library:item_quick_update', args=[self.book.pk]), {'action': 'progress', 'step': 10})
        self.book.refresh_from_db()
        self.assertEqual(self.book.progress_current, 228)
        self.assertEqual(self.book.status, MediaItem.Status.DONE)

    def test_quick_update_rejects_external_next(self):
        response = self.client.post(
            reverse('library:item_quick_update', args=[self.book.pk]),
            {'action': 'start', 'next': 'https://evil.example.com/'},
        )
        self.assertRedirects(response, reverse('library:shelf'))

    def test_shelf_filters_and_goal(self):
        MediaItem.objects.create(user=self.user, media_type='game', title='Hollow Knight')
        response = self.client.get(reverse('library:shelf'), {'type': 'game'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([i.title for i in response.context['shelf']], ['Hollow Knight'])

        self.client.post(reverse('library:shelf'), {'set_goal': '', 'media_type': 'book', 'target': 12})
        self.client.post(reverse('library:shelf'), {'set_goal': '', 'media_type': 'book', 'target': 24})
        goal = LibraryGoal.objects.get(user=self.user, media_type='book')
        self.assertEqual(goal.target, 24)

        self.book.status = MediaItem.Status.DONE
        self.book.save()
        response = self.client.get(reverse('library:shelf'))
        self.assertEqual(response.context['goals'][0]['done'], 1)

    def test_other_users_items_are_private(self):
        other = User.objects.create_user(username='stranger', password='password123')
        item = MediaItem.objects.create(user=other, media_type='movie', title='Secret')
        self.assertEqual(self.client.get(reverse('library:item_detail', args=[item.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('library:item_delete', args=[item.pk])).status_code, 404)

    def test_progress_cannot_exceed_total(self):
        response = self.client.post(reverse('library:item_detail', args=[self.book.pk]), {
            'media_type': 'book', 'title': 'Nhà Giả Kim', 'status': 'in_progress',
            'progress_current': 300, 'progress_total': 228,
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)

    def test_dashboard_shows_current_items(self):
        self.book.status = MediaItem.Status.IN_PROGRESS
        self.book.save()
        response = self.client.get(reverse('core:dashboard'))
        self.assertContains(response, 'Nhà Giả Kim')

    def test_xp_rewards_defined_for_all_types(self):
        self.assertEqual(set(XP_REWARDS), set(MediaItem.MediaType.values))
