from django.contrib import admin
from .models import UserProfile, XPEvent, UserAchievement, WeeklyReflection

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'level', 'xp', 'hp', 'longest_streak', 'last_active')
    search_fields = ('user__username', 'user__email')
    list_filter = ('level',)


@admin.register(XPEvent)
class XPEventAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'reason', 'key', 'created_at')
    search_fields = ('user__username', 'key', 'reason')
    list_filter = ('created_at',)


@admin.register(UserAchievement)
class UserAchievementAdmin(admin.ModelAdmin):
    list_display = ('user', 'code', 'unlocked_at')
    list_filter = ('code',)


@admin.register(WeeklyReflection)
class WeeklyReflectionAdmin(admin.ModelAdmin):
    list_display = ('user', 'week_start', 'mood', 'updated_at')
    list_filter = ('mood',)
