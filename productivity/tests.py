from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from productivity.models import Goal, Task, Habit, HabitLog, PomodoroSession
import json

User = get_user_model()

class ProductivityModuleTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='productivity_master', password='password123')
        self.client = Client()
        self.client.login(username='productivity_master', password='password123')
        self.goal = Goal.objects.create(user=self.user, title='Hoàn thành luận văn tốt nghiệp')

    def test_dashboard_view(self):
        response = self.client.get(reverse('productivity:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hoàn thành luận văn tốt nghiệp')

    def test_create_and_update_task_via_ajax(self):
        task = Task.objects.create(goal=self.goal, title='Viết chương 1', status='todo', quadrant='do')
        self.assertEqual(self.goal.progress, 0)

        # Cập nhật sang done
        response = self.client.post(
            reverse('productivity:update_task_status', args=[task.pk]),
            data=json.dumps({'status': 'done'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['goal_progress'], 100.0)

        task.refresh_from_db()
        self.assertEqual(task.status, 'done')

    def test_toggle_habit_and_streak(self):
        habit = Habit.objects.create(user=self.user, name='Đọc sách', target_per_day=1)
        response = self.client.post(reverse('productivity:toggle_habit_today', args=[habit.pk]))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['completed'])
        self.assertEqual(data['streak'], 1)

    def test_save_pomodoro_session(self):
        task = Task.objects.create(goal=self.goal, title='Đọc tài liệu tham khảo')
        initial_xp = self.user.profile.xp

        response = self.client.post(reverse('productivity:save_pomodoro_session'), {
            'task_id': task.pk,
            'duration_minutes': 25,
            'note': 'Đọc xong 2 bài báo'
        })
        self.assertEqual(response.status_code, 200)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.xp, initial_xp + 15)
        self.assertEqual(PomodoroSession.objects.count(), 1)
