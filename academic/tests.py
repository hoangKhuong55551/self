from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from datetime import timedelta

from django.utils import timezone

from academic.models import Semester, Course, Tag, Note, CodeSnippet
from academic.services import gpa_trend, study_time_by_course
from productivity.models import Goal, PomodoroSession, Task

User = get_user_model()

class AcademicModuleTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='academic_scholar', password='password123')
        self.client = Client()
        self.client.login(username='academic_scholar', password='password123')

        self.sem = Semester.objects.create(
            user=self.user, name='HK1 2025-2026', year=2025, term='spring', is_current=True
        )
        self.course1 = Course.objects.create(
            semester=self.sem, name='Lập trình Web với Django', credits=3, grade=4.0, is_completed=True
        )
        self.course2 = Course.objects.create(
            semester=self.sem, name='Cơ sở dữ liệu', credits=3, grade=3.0, is_completed=True
        )

    def test_gpa_calculation(self):
        # (4.0 * 3 + 3.0 * 3) / 6 = 3.5
        self.assertEqual(self.sem.gpa, 3.5)

    def test_academic_dashboard(self):
        response = self.client.get(reverse('academic:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['cgpa'], 3.5)
        self.assertContains(response, 'HK1 2025-2026')

    def test_gpa_simulator(self):
        # current = 3.5 (6 credits). Target = 3.6 với 6 credits tiếp theo => cần (3.6*12 - 21)/6 = 3.7
        response = self.client.get(reverse('academic:gpa_simulator'), {
            'target_gpa': '3.6',
            'remaining_credits': '6'
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['required_gpa'], 3.7)

    def test_create_note_and_snippet(self):
        tag = Tag.objects.create(user=self.user, name='Django')
        note = Note.objects.create(user=self.user, title='Kiến trúc Django MVT', content='# MVT Pattern')
        note.tags.add(tag)

        snippet = CodeSnippet.objects.create(
            user=self.user, title='Django Model Signal', language='python', code='@receiver(post_save)...'
        )
        snippet.tags.add(tag)

        self.assertEqual(Note.objects.count(), 1)
        self.assertEqual(CodeSnippet.objects.count(), 1)
        self.assertEqual(note.tags.first().name, 'Django')


class GPAEdgeCaseTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='student', password='password123')
        self.client.login(username='student', password='password123')
        self.sem = Semester.objects.create(user=self.user, name='HK1', year=2025, term='spring')

    def test_gpa_ignores_incomplete_and_ungraded_courses(self):
        Course.objects.create(semester=self.sem, name='A', credits=4, grade=4.0, is_completed=True)
        Course.objects.create(semester=self.sem, name='B', credits=3, grade=1.0, is_completed=False)
        Course.objects.create(semester=self.sem, name='C', credits=2, grade=None, is_completed=True)
        self.assertEqual(self.sem.gpa, 4.0)

    def test_empty_semester_gpa_is_zero(self):
        self.assertEqual(self.sem.gpa, 0.0)
        response = self.client.get(reverse('academic:dashboard'))
        self.assertEqual(response.context['cgpa'], 0.0)

    def test_cgpa_weights_credits_across_semesters(self):
        sem2 = Semester.objects.create(user=self.user, name='HK2', year=2025, term='fall')
        Course.objects.create(semester=self.sem, name='A', credits=1, grade=4.0, is_completed=True)
        Course.objects.create(semester=sem2, name='B', credits=3, grade=2.0, is_completed=True)
        response = self.client.get(reverse('academic:dashboard'))
        self.assertEqual(response.context['cgpa'], 2.5)  # (4*1 + 2*3) / 4

    def test_cgpa_excludes_other_users(self):
        other = User.objects.create_user(username='other', password='password123')
        other_sem = Semester.objects.create(user=other, name='X', year=2025, term='spring')
        Course.objects.create(semester=other_sem, name='X', credits=3, grade=0.0, is_completed=True)
        Course.objects.create(semester=self.sem, name='A', credits=3, grade=3.0, is_completed=True)
        self.assertEqual(self.client.get(reverse('academic:dashboard')).context['cgpa'], 3.0)

    def test_simulator_flags_impossible_target(self):
        Course.objects.create(semester=self.sem, name='A', credits=30, grade=2.0, is_completed=True)
        response = self.client.get(
            reverse('academic:gpa_simulator'), {'target_gpa': '3.8', 'remaining_credits': '10'}
        )
        self.assertFalse(response.context['possible'])

    def test_simulator_rejects_invalid_input(self):
        url = reverse('academic:gpa_simulator')
        for params in (
            {'target_gpa': 'abc', 'remaining_credits': '10'},
            {'target_gpa': '3.0', 'remaining_credits': '-5'},
            {'target_gpa': '5.0', 'remaining_credits': '10'},
        ):
            response = self.client.get(url, params)
            self.assertEqual(response.status_code, 200)
            self.assertIsNone(response.context['required_gpa'], params)

    def test_simulator_already_reached_target_needs_zero(self):
        Course.objects.create(semester=self.sem, name='A', credits=30, grade=4.0, is_completed=True)
        response = self.client.get(
            reverse('academic:gpa_simulator'), {'target_gpa': '2.0', 'remaining_credits': '10'}
        )
        self.assertEqual(response.context['required_gpa'], 0)
        self.assertTrue(response.context['possible'])


class GPATrackerFormTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tracker', password='password123')
        self.client.login(username='tracker', password='password123')
        self.sem = Semester.objects.create(
            user=self.user, name='HK1', year=2025, term='spring', is_current=True
        )

    def test_new_current_semester_unsets_previous(self):
        self.client.post(reverse('academic:gpa_tracker'), {
            'add_semester': '1', 'name': 'HK2', 'year': 2025, 'term': 'fall', 'is_current': 'on',
        })
        self.sem.refresh_from_db()
        self.assertFalse(self.sem.is_current)
        self.assertTrue(Semester.objects.get(name='HK2').is_current)

    def test_duplicate_semester_shows_error_instead_of_crashing(self):
        response = self.client.post(reverse('academic:gpa_tracker'), {
            'add_semester': '1', 'name': 'Trùng', 'year': 2025, 'term': 'spring',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['sem_form'].errors)
        self.assertEqual(Semester.objects.count(), 1)

    def test_cannot_add_course_to_other_users_semester(self):
        other = User.objects.create_user(username='other2', password='password123')
        other_sem = Semester.objects.create(user=other, name='X', year=2025, term='spring')
        response = self.client.post(reverse('academic:gpa_tracker'), {
            'add_course': '1', 'semester': other_sem.pk, 'name': 'Hack', 'credits': 3,
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['course_form'].errors)
        self.assertFalse(Course.objects.filter(name='Hack').exists())


class SecondBrainTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='brain', password='password123')
        self.other = User.objects.create_user(username='spy', password='password123')
        self.client.login(username='brain', password='password123')
        self.tag = Tag.objects.create(user=self.user, name='Django')
        self.note = Note.objects.create(user=self.user, title='Signals', content='post_save hook')
        self.note.tags.add(self.tag)
        Note.objects.create(user=self.user, title='CSS', content='flexbox')

    def test_search_and_tag_filter(self):
        url = reverse('academic:note_list')
        self.assertEqual(list(self.client.get(url, {'q': 'hook'}).context['notes']), [self.note])
        self.assertEqual(list(self.client.get(url, {'tag': self.tag.pk}).context['notes']), [self.note])

    def test_invalid_tag_param_does_not_crash(self):
        response = self.client.get(reverse('academic:note_list'), {'tag': 'abc'})
        self.assertEqual(response.status_code, 200)

    def test_note_content_is_escaped(self):
        note = Note.objects.create(user=self.user, title='XSS', content='<script>alert(1)</script>')
        response = self.client.get(reverse('academic:note_detail', args=[note.pk]))
        self.assertNotContains(response, '<script>alert(1)</script>')

    def test_other_users_note_and_snippet_are_404(self):
        self.client.logout()
        self.client.login(username='spy', password='password123')
        snippet = CodeSnippet.objects.create(user=self.user, title='S', code='x')
        self.assertEqual(self.client.get(reverse('academic:note_detail', args=[self.note.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('academic:snippet_detail', args=[snippet.pk])).status_code, 404)

    def test_cannot_attach_other_users_tag(self):
        foreign = Tag.objects.create(user=self.other, name='Spy')
        response = self.client.post(reverse('academic:note_list'), {
            'title': 'N', 'content': 'c', 'tags': [foreign.pk],
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Note.objects.filter(title='N').exists())

    def test_snippet_language_filter(self):
        CodeSnippet.objects.create(user=self.user, title='Py', language='python', code='print()')
        CodeSnippet.objects.create(user=self.user, title='JS', language='javascript', code='log()')
        response = self.client.get(reverse('academic:snippet_list'), {'lang': 'javascript'})
        self.assertEqual([s.title for s in response.context['snippets']], ['JS'])


class CourseStudyLinkTest(TestCase):
    """Liên kết Task ↔ Course: thời gian Pomodoro được thống kê theo môn học."""

    def setUp(self):
        self.user = User.objects.create_user(username='linker', password='password123')
        self.client.login(username='linker', password='password123')
        self.sem = Semester.objects.create(user=self.user, name='HK1', year=2026, term='spring', is_current=True)
        self.web = Course.objects.create(semester=self.sem, name='Web', credits=3)
        self.db = Course.objects.create(semester=self.sem, name='CSDL', credits=3)
        self.goal = Goal.objects.create(user=self.user, title='Học tốt')

    def _focus(self, course, minutes, completed=True, when=None):
        task = Task.objects.create(goal=self.goal, title=f'Ôn {course.name}', course=course)
        PomodoroSession.objects.create(
            task=task, start_time=when or timezone.now(), duration_minutes=minutes, completed=completed
        )

    def test_study_time_by_course_counts_only_completed(self):
        self._focus(self.web, 25)
        self._focus(self.web, 50)
        self._focus(self.db, 25)
        self._focus(self.db, 99, completed=False)
        stats = {c.name: (c.focus_minutes, c.sessions) for c in study_time_by_course(self.user)}
        self.assertEqual(stats, {'Web': (75, 2), 'CSDL': (25, 1)})

    def test_dashboard_shows_study_time_and_gpa_trend(self):
        self._focus(self.web, 125)
        response = self.client.get(reverse('academic:dashboard'))
        self.assertEqual([c.name for c in response.context['study_courses']], ['Web'])
        self.assertContains(response, '2h 05m')

    def test_task_form_only_offers_own_courses(self):
        other = User.objects.create_user(username='x', password='password123')
        other_sem = Semester.objects.create(user=other, name='X', year=2026, term='spring')
        foreign = Course.objects.create(semester=other_sem, name='Foreign', credits=3)
        response = self.client.post(reverse('productivity:kanban_board'), {
            'goal': self.goal.pk, 'title': 'Hack', 'course': foreign.pk,
            'status': 'todo', 'quadrant': 'do', 'estimated_pomodoros': 1,
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Task.objects.filter(title='Hack').exists())

    def test_gpa_trend_orders_terms_and_accumulates(self):
        Course.objects.filter(pk=self.web.pk).update(grade=4.0, is_completed=True)
        fall = Semester.objects.create(user=self.user, name='HK2', year=2026, term='fall')
        summer = Semester.objects.create(user=self.user, name='Hè', year=2026, term='summer')
        Course.objects.create(semester=fall, name='AI', credits=3, grade=2.0, is_completed=True)
        Course.objects.create(semester=summer, name='TT', credits=6, grade=3.0, is_completed=True)
        Semester.objects.create(user=self.user, name='Trống', year=2025, term='fall')
        trend = gpa_trend(self.user)
        self.assertEqual([t['label'] for t in trend], ['HK1', 'HK2', 'Hè'])
        self.assertEqual([t['gpa'] for t in trend], [4.0, 2.0, 3.0])
        self.assertEqual([t['cgpa'] for t in trend], [4.0, 3.0, 3.0])

    def test_weekly_review_includes_academic(self):
        self._focus(self.db, 30)
        self._focus(self.web, 45, when=timezone.now() - timedelta(days=30))
        Note.objects.create(user=self.user, title='N', content='c')
        response = self.client.get(reverse('core:weekly_review'))
        self.assertEqual([c.name for c in response.context['study_courses']], ['CSDL'])
        self.assertEqual(response.context['notes_written'], 1)
