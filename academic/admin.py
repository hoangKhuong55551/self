from django.contrib import admin
from .models import Semester, Course, Tag, Note, CodeSnippet

class CourseInline(admin.TabularInline):
    model = Course
    extra = 1

@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'year', 'term', 'is_current', 'gpa')
    list_filter = ('year', 'term', 'is_current')
    search_fields = ('name', 'user__username')
    inlines = [CourseInline]

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'semester', 'credits', 'grade', 'is_completed')
    list_filter = ('is_completed', 'credits', 'grade')
    search_fields = ('name', 'code')

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'color')
    search_fields = ('name', 'user__username')

@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'is_pinned', 'is_archived', 'updated_at')
    list_filter = ('is_pinned', 'is_archived', 'updated_at')
    search_fields = ('title', 'content', 'user__username')
    filter_horizontal = ('tags',)

@admin.register(CodeSnippet)
class CodeSnippetAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'language', 'updated_at')
    list_filter = ('language', 'updated_at')
    search_fields = ('title', 'description', 'user__username')
    filter_horizontal = ('tags',)
