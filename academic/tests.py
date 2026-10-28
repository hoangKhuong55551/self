from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from academic.models import Semester, Course, Tag, Note, CodeSnippet

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
