from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from academic.models import CodeSnippet, Course, Note, Semester, Tag
from core.templatetags.core_tags import markdownify
from productivity.models import Goal, Task

User = get_user_model()


class AcademicEditTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='student', password='password123')
        self.other = User.objects.create_user(username='other', password='password123')
        self.client.login(username='student', password='password123')
        self.sem = Semester.objects.create(user=self.user, name='HK1', year=2026, term='spring', is_current=True)
        self.course = Course.objects.create(semester=self.sem, name='Web', credits=3)

    def test_enter_grade_after_exam(self):
        self.client.post(reverse('academic:course_edit', args=[self.course.pk]), {
            'semester': self.sem.pk, 'name': 'Web', 'code': 'IT001', 'credits': 3, 'grade': '3.5', 'is_completed': 'on',
        })
        self.course.refresh_from_db()
        self.assertEqual((self.course.grade, self.course.is_completed), (3.5, True))
        self.assertEqual(self.sem.gpa, 3.5)

    def test_course_delete_keeps_linked_tasks(self):
        goal = Goal.objects.create(user=self.user, title='Học')
        task = Task.objects.create(goal=goal, title='Ôn Web', course=self.course)
        self.client.post(reverse('academic:course_delete', args=[self.course.pk]))
        task.refresh_from_db()
        self.assertIsNone(task.course)

    def test_semester_edit_current_unsets_others(self):
        sem2 = Semester.objects.create(user=self.user, name='HK2', year=2026, term='fall')
        self.client.post(reverse('academic:semester_edit', args=[sem2.pk]), {
            'name': 'HK2', 'year': 2026, 'term': 'fall', 'is_current': 'on',
        })
        self.sem.refresh_from_db()
        sem2.refresh_from_db()
        self.assertFalse(self.sem.is_current)
        self.assertTrue(sem2.is_current)

    def test_semester_edit_rejects_duplicate_term(self):
        sem2 = Semester.objects.create(user=self.user, name='HK2', year=2026, term='fall')
        response = self.client.post(reverse('academic:semester_edit', args=[sem2.pk]), {
            'name': 'HK2', 'year': 2026, 'term': 'spring',
        })
        self.assertEqual(response.status_code, 200)
        sem2.refresh_from_db()
        self.assertEqual(sem2.term, 'fall')

    def test_semester_delete_cascades(self):
        self.client.post(reverse('academic:semester_delete', args=[self.sem.pk]))
        self.assertFalse(Course.objects.exists())

    def test_note_edit_archive_and_delete(self):
        note = Note.objects.create(user=self.user, title='A', content='x')
        self.client.post(reverse('academic:note_edit', args=[note.pk]), {
            'title': 'A2', 'content': 'y', 'is_archived': 'on',
        })
        note.refresh_from_db()
        self.assertEqual((note.title, note.is_archived), ('A2', True))
        self.assertEqual(list(self.client.get(reverse('academic:note_list')).context['notes']), [])
        self.assertEqual(list(self.client.get(reverse('academic:note_list'), {'archived': '1'}).context['notes']), [note])
        self.client.post(reverse('academic:note_delete', args=[note.pk]))
        self.assertFalse(Note.objects.exists())

    def test_new_tags_created_and_reused(self):
        Tag.objects.create(user=self.user, name='Django')
        self.client.post(reverse('academic:note_list'), {
            'title': 'N', 'content': 'c', 'new_tags': 'django, Thuật toán, thuật toán, ',
        })
        note = Note.objects.get(title='N')
        self.assertEqual(sorted(t.name for t in note.tags.all()), ['Django', 'Thuật toán'])
        self.assertEqual(Tag.objects.filter(user=self.user).count(), 2)

    def test_snippet_edit_with_new_tag_and_delete(self):
        snippet = CodeSnippet.objects.create(user=self.user, title='S', code='print(1)')
        self.client.post(reverse('academic:snippet_edit', args=[snippet.pk]), {
            'title': 'S2', 'language': 'python', 'code': 'print(2)', 'new_tags': 'python',
        })
        snippet.refresh_from_db()
        self.assertEqual((snippet.title, [t.name for t in snippet.tags.all()]), ('S2', ['python']))
        self.client.post(reverse('academic:snippet_delete', args=[snippet.pk]))
        self.assertFalse(CodeSnippet.objects.exists())

    def test_cannot_touch_other_users_items(self):
        other_sem = Semester.objects.create(user=self.other, name='X', year=2026, term='spring')
        items = {
            'semester': other_sem.pk,
            'course': Course.objects.create(semester=other_sem, name='X').pk,
            'note': Note.objects.create(user=self.other, title='X', content='x').pk,
            'snippet': CodeSnippet.objects.create(user=self.other, title='X', code='x').pk,
        }
        for name, pk in items.items():
            self.assertEqual(self.client.get(reverse(f'academic:{name}_edit', args=[pk])).status_code, 404, name)
            self.assertEqual(self.client.post(reverse(f'academic:{name}_delete', args=[pk])).status_code, 404, name)


class MarkdownTest(TestCase):
    def test_renders_common_markdown(self):
        html = markdownify('# Tiêu đề\n\n**đậm** và `code`\n\n- a\n- b\n\n```python\nx = 1\n```')
        for fragment in ('<h1>Tiêu đề</h1>', '<strong>đậm</strong>', '<code>code</code>', '<li>a</li>', '<pre><code class="language-python">'):
            self.assertIn(fragment, html)

    def test_strips_dangerous_html(self):
        html = markdownify('<script>alert(1)</script><img src=x onerror="alert(1)"> [x](javascript:alert(1)) <a href="https://ok.vn" onclick="x()">ok</a>')
        self.assertNotIn('<script', html)
        self.assertNotIn('onerror', html)
        self.assertNotIn('javascript:', html)
        self.assertNotIn('onclick', html)
        self.assertIn('href="https://ok.vn"', html)

    def test_note_detail_renders_markdown(self):
        user = User.objects.create_user(username='md', password='password123')
        self.client.login(username='md', password='password123')
        note = Note.objects.create(user=user, title='T', content='## Mục 1\n\n| a | b |\n|---|---|\n| 1 | 2 |')
        response = self.client.get(reverse('academic:note_detail', args=[note.pk]))
        self.assertContains(response, '<h2>Mục 1</h2>', html=False)
        self.assertContains(response, '<table>')
