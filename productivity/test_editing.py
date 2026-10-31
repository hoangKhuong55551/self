from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import XPEvent
from productivity.models import Goal, Habit, HabitLog, Task

User = get_user_model()


class ProductivityEditTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='doer', password='password123')
        self.other = User.objects.create_user(username='other', password='password123')
        self.client.login(username='doer', password='password123')
        self.goal = Goal.objects.create(user=self.user, title='Đồ án')
        self.goal2 = Goal.objects.create(user=self.user, title='IELTS')
        self.task = Task.objects.create(goal=self.goal, title='Thiết kế DB', status='done')
        Task.objects.create(goal=self.goal, title='Viết API')
        self.goal.recalculate_progress()

    def task_data(self, **overrides):
        data = {
            'goal': self.goal.pk, 'title': 'Thiết kế DB', 'status': 'done', 'quadrant': 'do',
            'estimated_pomodoros': 2, 'due_date': '', 'description': '', 'course': '',
        }
        data.update(overrides)
        return data

    def test_goal_edit_and_delete_cascades_tasks(self):
        self.client.post(reverse('productivity:goal_edit', args=[self.goal.pk]), {
            'title': 'Đồ án tốt nghiệp', 'status': 'in_progress', 'color': '#123456', 'deadline': '2026-12-31',
        })
        self.goal.refresh_from_db()
        self.assertEqual((self.goal.title, self.goal.deadline), ('Đồ án tốt nghiệp', date(2026, 12, 31)))
        self.client.post(reverse('productivity:goal_delete', args=[self.goal.pk]))
        self.assertFalse(Task.objects.filter(goal_id=self.goal.pk).exists())

    def test_edit_form_shows_existing_date(self):
        Goal.objects.filter(pk=self.goal.pk).update(deadline=date(2026, 5, 4))
        response = self.client.get(reverse('productivity:goal_edit', args=[self.goal.pk]))
        self.assertContains(response, 'value="2026-05-04"')

    def test_moving_task_recalculates_both_goals(self):
        self.assertEqual(self.goal.progress, 50)
        self.client.post(reverse('productivity:task_edit', args=[self.task.pk]), self.task_data(goal=self.goal2.pk))
        self.goal.refresh_from_db()
        self.goal2.refresh_from_db()
        self.assertEqual(self.goal.progress, 0)
        self.assertEqual(self.goal2.progress, 100)

    def test_delete_task_recalculates_goal(self):
        self.client.post(reverse('productivity:task_delete', args=[self.task.pk]))
        self.goal.refresh_from_db()
        self.assertEqual(self.goal.progress, 0)

    def test_edit_does_not_farm_xp(self):
        task = Task.objects.create(goal=self.goal, title='Test')
        url = reverse('productivity:task_edit', args=[task.pk])
        for status in ('done', 'todo', 'done'):
            self.client.post(url, self.task_data(title='Test', status=status))
        self.assertEqual(XPEvent.objects.filter(key=f'task:{task.pk}').count(), 1)

    def test_habit_pause_keeps_history_and_delete_removes_it(self):
        habit = Habit.objects.create(user=self.user, name='Đọc sách')
        HabitLog.objects.create(habit=habit, date=timezone.now().date(), completed=True)
        self.client.post(reverse('productivity:habit_edit', args=[habit.pk]), {
            'name': 'Đọc sách 30p', 'frequency': habit.frequency, 'target_per_day': 1, 'icon': '📚', 'color': '#ffffff',
        })
        habit.refresh_from_db()
        self.assertEqual(habit.name, 'Đọc sách 30p')
        self.assertFalse(habit.is_active)
        self.assertEqual(habit.logs.count(), 1)
        self.client.post(reverse('productivity:habit_delete', args=[habit.pk]))
        self.assertFalse(HabitLog.objects.exists())

    def test_cannot_touch_other_users_items(self):
        foreign_goal = Goal.objects.create(user=self.other, title='X')
        foreign_task = Task.objects.create(goal=foreign_goal, title='X')
        foreign_habit = Habit.objects.create(user=self.other, name='X')
        for name, pk in (('goal', foreign_goal.pk), ('task', foreign_task.pk), ('habit', foreign_habit.pk)):
            self.assertEqual(self.client.get(reverse(f'productivity:{name}_edit', args=[pk])).status_code, 404)
            self.assertEqual(self.client.post(reverse(f'productivity:{name}_delete', args=[pk])).status_code, 404)

    def test_cannot_move_task_to_other_users_goal(self):
        foreign_goal = Goal.objects.create(user=self.other, title='X')
        response = self.client.post(reverse('productivity:task_edit', args=[self.task.pk]), self.task_data(goal=foreign_goal.pk))
        self.assertEqual(response.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.goal, self.goal)

    def test_delete_requires_post(self):
        self.assertEqual(self.client.get(reverse('productivity:task_delete', args=[self.task.pk])).status_code, 405)
