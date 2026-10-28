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
