"""
Life OS - Root URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from core import views_deploy

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('core.urls', namespace='core')),
    path('finance/', include('finance.urls', namespace='finance')),
    path('productivity/', include('productivity.urls', namespace='productivity')),
    path('academic/', include('academic.urls', namespace='academic')),
    path('library/', include('library.urls', namespace='library')),
    path('cron/<path:secret>/', views_deploy.cron_run, name='cron_run'),
]

if settings.FILE_STORAGE == 'db':
    # Ảnh lưu trong database (host không có ổ đĩa lâu dài)
    urlpatterns += [path(settings.MEDIA_URL.lstrip('/') + '<path:name>', views_deploy.db_media, name='db_media')]
elif settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = '🚀 Life OS - Admin Panel'
admin.site.site_title = 'Life OS Admin'
admin.site.index_title = 'Quản lý hệ thống Life OS'
