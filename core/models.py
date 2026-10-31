import math
from django.db import models
from django.conf import settings


class UserProfile(models.Model):
    """
    Mở rộng User với hệ thống Gamification (XP/HP/Level).
    Mỗi user có đúng 1 profile, tạo tự động qua signal.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)

    # --- Gamification ---
    xp = models.PositiveIntegerField(default=0, help_text="Experience Points")
    hp = models.PositiveIntegerField(default=100, help_text="Health Points (max 100)")
    level = models.PositiveIntegerField(default=1)
    longest_streak = models.PositiveIntegerField(default=0)
    last_active = models.DateField(auto_now=True)

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self):
        return f"{self.user.username} (Lv.{self.level})"

    @property
    def xp_for_next_level(self):
        """XP cần để lên level tiếp: 100 * level^1.5 (tăng dần)."""
        return int(100 * math.pow(self.level, 1.5))

    @property
    def xp_progress_percent(self):
        """Phần trăm XP tiến tới level tiếp theo."""
        needed = self.xp_for_next_level
        return min(round((self.xp / needed) * 100, 1), 100) if needed > 0 else 100

    def award_xp_once(self, key, amount, reason=''):
        """
        Cộng XP đúng một lần cho mỗi nguồn thưởng (key), ví dụ 'task:12'.
        Trả về True nếu lần này thực sự được cộng.
        """
        _, created = XPEvent.objects.get_or_create(
            user_id=self.user_id, key=key,
            defaults={'amount': amount, 'reason': reason[:200]},
        )
        if created:
            # Profile có thể đã cũ trong bộ nhớ, đọc lại trước khi cộng dồn
            self.refresh_from_db(fields=['xp', 'level', 'hp'])
            self.add_xp(amount)
        return created

    def add_xp(self, amount):
        """Cộng XP và tự động level-up nếu đủ."""
        self.xp += amount
        while self.xp >= self.xp_for_next_level:
            self.xp -= self.xp_for_next_level
            self.level += 1
            self.hp = min(self.hp + 10, 100)  # Hồi 10 HP khi lên level
        self.save(update_fields=['xp', 'level', 'hp'])

    def lose_hp(self, amount):
        """Trừ HP (minimum 0)."""
        self.hp = max(self.hp - amount, 0)
        self.save(update_fields=['hp'])


class XPEvent(models.Model):
    """
    Sổ ghi XP: mỗi nguồn thưởng (task, habit log, pomodoro, media...)
    có một key duy nhất để không thể cộng XP lặp lại.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='xp_events'
    )
    key = models.CharField(max_length=100)
    amount = models.IntegerField()
    reason = models.CharField(max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'key'], name='unique_xp_event_per_source')
        ]

    def __str__(self):
        return f"{self.user} +{self.amount} XP ({self.key})"


class UserAchievement(models.Model):
    """Huy hiệu đã mở khoá. Định nghĩa huy hiệu nằm trong core/achievements.py."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='achievements'
    )
    code = models.CharField(max_length=50)
    unlocked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-unlocked_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'code'], name='unique_user_achievement')
        ]

    def __str__(self):
        return f"{self.user} 🏅 {self.code}"


class WeeklyReflection(models.Model):
    """Suy ngẫm cuối tuần, gắn với ngày thứ Hai đầu tuần."""

    class Mood(models.IntegerChoices):
        AWFUL = 1, '😫 Tệ'
        BAD = 2, '😕 Không ổn'
        OK = 3, '😐 Bình thường'
        GOOD = 4, '🙂 Tốt'
        GREAT = 5, '🤩 Tuyệt vời'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='weekly_reflections'
    )
    week_start = models.DateField()
    mood = models.PositiveSmallIntegerField(choices=Mood.choices, null=True, blank=True)
    went_well = models.TextField(blank=True, default='')
    to_improve = models.TextField(blank=True, default='')
    next_focus = models.TextField(blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-week_start']
        constraints = [
            models.UniqueConstraint(fields=['user', 'week_start'], name='unique_weekly_reflection')
        ]

    def __str__(self):
        return f"{self.user} – tuần {self.week_start:%d/%m/%Y}"
