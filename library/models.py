from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


class MediaItem(models.Model):
    """Một cuốn sách, bộ phim, series hoặc game trong thư viện cá nhân."""

    class MediaType(models.TextChoices):
        BOOK = 'book', '📚 Sách'
        MOVIE = 'movie', '🎬 Phim lẻ'
        SERIES = 'series', '📺 Phim bộ'
        GAME = 'game', '🎮 Game'

    class Status(models.TextChoices):
        WANT = 'want', 'Muốn thử'
        IN_PROGRESS = 'in_progress', 'Đang theo dõi'
        DONE = 'done', 'Đã xong'
        DROPPED = 'dropped', 'Bỏ dở'

    # Đơn vị tiến độ theo từng loại media
    PROGRESS_UNITS = {
        MediaType.BOOK: 'trang',
        MediaType.MOVIE: 'phút',
        MediaType.SERIES: 'tập',
        MediaType.GAME: 'giờ',
    }

    # Nhãn trạng thái "đang..." theo loại media
    IN_PROGRESS_LABELS = {
        MediaType.BOOK: 'Đang đọc',
        MediaType.MOVIE: 'Đang xem',
        MediaType.SERIES: 'Đang xem',
        MediaType.GAME: 'Đang chơi',
    }

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='media_items'
    )
    media_type = models.CharField(max_length=10, choices=MediaType.choices, default=MediaType.BOOK)
    title = models.CharField(max_length=300)
    creator = models.CharField(
        max_length=200, blank=True, default='',
        help_text="Tác giả / Đạo diễn / Studio"
    )
    genre = models.CharField(max_length=100, blank=True, default='')
    cover = models.ImageField(upload_to='library/covers/', blank=True, null=True)
    cover_url = models.URLField(blank=True, default='', help_text="Link ảnh bìa (nếu không tải ảnh lên)")
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.WANT)
    progress_current = models.PositiveIntegerField(default=0)
    progress_total = models.PositiveIntegerField(default=0, help_text="0 = không rõ")
    rating = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    review = models.TextField(blank=True, default='', help_text="Cảm nhận, trích dẫn yêu thích...")
    started_on = models.DateField(null=True, blank=True)
    finished_on = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.get_media_type_display()} {self.title}"

    @property
    def cover_src(self):
        if self.cover:
            return self.cover.url
        return self.cover_url

    @property
    def progress_unit(self):
        return self.PROGRESS_UNITS.get(self.media_type, '')

    @property
    def status_label(self):
        if self.status == self.Status.IN_PROGRESS:
            return self.IN_PROGRESS_LABELS.get(self.media_type, self.get_status_display())
        return self.get_status_display()

    @property
    def progress_percent(self):
        if self.status == self.Status.DONE:
            return 100
        if not self.progress_total:
            return 0
        return min(round(self.progress_current / self.progress_total * 100), 100)

    @property
    def type_icon(self):
        return {
            self.MediaType.BOOK: 'bi-book',
            self.MediaType.MOVIE: 'bi-film',
            self.MediaType.SERIES: 'bi-tv',
            self.MediaType.GAME: 'bi-controller',
        }.get(self.media_type, 'bi-collection')


class LibraryGoal(models.Model):
    """Mục tiêu theo năm, ví dụ: đọc 24 cuốn sách trong 2026."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='library_goals'
    )
    year = models.PositiveIntegerField()
    media_type = models.CharField(max_length=10, choices=MediaItem.MediaType.choices)
    target = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        ordering = ['media_type']
        constraints = [
            models.UniqueConstraint(fields=['user', 'year', 'media_type'], name='unique_library_goal')
        ]

    def __str__(self):
        return f"{self.year}: {self.target} {self.get_media_type_display()}"
