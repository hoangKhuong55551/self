from django.db import models
from django.conf import settings
from django.db.models import Sum, F, FloatField, ExpressionWrapper


class Semester(models.Model):
    """Học kỳ."""

    class Term(models.TextChoices):
        SPRING = 'spring', 'Học kỳ 1'
        SUMMER = 'summer', 'Học kỳ hè'
        FALL = 'fall', 'Học kỳ 2'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='semesters'
    )
    name = models.CharField(max_length=100, help_text="VD: HK1 2025-2026")
    year = models.PositiveIntegerField()
    term = models.CharField(max_length=10, choices=Term.choices)
    is_current = models.BooleanField(default=False)

    class Meta:
        ordering = ['-year', 'term']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'year', 'term'],
                name='unique_semester_per_user'
            )
        ]

    def __str__(self):
        return self.name

    @property
    def gpa(self):
        """GPA của học kỳ = Σ(grade × credits) / Σ(credits)."""
        courses = self.courses.filter(is_completed=True, grade__isnull=False)

        result = courses.aggregate(
            weighted_sum=Sum(
                ExpressionWrapper(
                    F('grade') * F('credits'),
                    output_field=FloatField()
                )
            ),
            total_credits=Sum('credits')
        )

        weighted = result['weighted_sum']
        total_cred = result['total_credits']

        if not total_cred or total_cred == 0:
            return 0.0

        return round(weighted / total_cred, 2)


class Course(models.Model):
    """Môn học trong một học kỳ."""

    GRADE_CHOICES = [
        (4.0, 'A (4.0)'),
        (3.7, 'A- (3.7)'),
        (3.5, 'B+ (3.5)'),
        (3.0, 'B (3.0)'),
        (2.5, 'C+ (2.5)'),
        (2.0, 'C (2.0)'),
        (1.5, 'D+ (1.5)'),
        (1.0, 'D (1.0)'),
        (0.0, 'F (0.0)'),
    ]

    semester = models.ForeignKey(
        Semester,
        on_delete=models.CASCADE,
        related_name='courses'
    )
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, blank=True, default='')
    credits = models.PositiveIntegerField(default=3)
    grade = models.FloatField(
        null=True, blank=True,
        choices=GRADE_CHOICES,
        help_text="Thang điểm 4"
    )
    is_completed = models.BooleanField(default=False)

    class Meta:
        ordering = ['name']

    def __str__(self):
        grade_str = f" - {self.grade}" if self.grade is not None else ""
        return f"{self.code} {self.name} ({self.credits} TC){grade_str}"


class Tag(models.Model):
    """Tag dùng chung cho Note và CodeSnippet (Many-to-Many)."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tags'
    )
    name = models.CharField(max_length=50)
    color = models.CharField(max_length=7, default='#6366f1')

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'name'],
                name='unique_tag_per_user'
            )
        ]
        ordering = ['name']

    def __str__(self):
        return f"🏷️ {self.name}"


class Note(models.Model):
    """Ghi chú Markdown — Bộ não thứ hai."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notes'
    )
    title = models.CharField(max_length=300)
    content = models.TextField(
        help_text="Hỗ trợ Markdown"
    )
    tags = models.ManyToManyField(
        Tag,
        blank=True,
        related_name='notes'
    )
    is_pinned = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_pinned', '-updated_at']
        indexes = [
            models.Index(fields=['user', '-updated_at']),
        ]

    def __str__(self):
        pin = "📌 " if self.is_pinned else ""
        return f"{pin}{self.title}"


class CodeSnippet(models.Model):
    """Kho đoạn code cá nhân với syntax highlighting."""

    LANGUAGE_CHOICES = [
        ('python', 'Python'),
        ('javascript', 'JavaScript'),
        ('html', 'HTML'),
        ('css', 'CSS'),
        ('sql', 'SQL'),
        ('java', 'Java'),
        ('cpp', 'C++'),
        ('csharp', 'C#'),
        ('go', 'Go'),
        ('rust', 'Rust'),
        ('bash', 'Bash/Shell'),
        ('typescript', 'TypeScript'),
        ('php', 'PHP'),
        ('ruby', 'Ruby'),
        ('markdown', 'Markdown'),
        ('json', 'JSON'),
        ('yaml', 'YAML'),
        ('other', 'Khác'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='snippets'
    )
    title = models.CharField(max_length=300)
    language = models.CharField(
        max_length=20,
        choices=LANGUAGE_CHOICES,
        default='python'
    )
    code = models.TextField()
    description = models.TextField(
        blank=True, default='',
        help_text="Giải thích đoạn code"
    )
    tags = models.ManyToManyField(
        Tag,
        blank=True,
        related_name='snippets'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"💻 [{self.language}] {self.title}"
