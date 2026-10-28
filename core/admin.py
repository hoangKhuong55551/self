from django.contrib import admin
from .models import UserProfile

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'level', 'xp', 'hp', 'longest_streak', 'last_active')
    search_fields = ('user__username', 'user__email')
    list_filter = ('level',)
