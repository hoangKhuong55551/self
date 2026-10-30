from django.contrib import admin
from .models import MediaItem, LibraryGoal

@admin.register(MediaItem)
class MediaItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'media_type', 'status', 'rating', 'finished_on', 'updated_at')
    list_filter = ('media_type', 'status', 'rating')
    search_fields = ('title', 'creator', 'genre', 'user__username')

@admin.register(LibraryGoal)
class LibraryGoalAdmin(admin.ModelAdmin):
    list_display = ('user', 'year', 'media_type', 'target')
    list_filter = ('year', 'media_type')
