"""
Life OS - Root URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('core.urls', namespace='core')),
    path('finance/', include('finance.urls', namespace='finance')),
    path('productivity/', include('productivity.urls', namespace='productivity')),
    path('academic/', include('academic.urls', namespace='academic')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = '🚀 Life OS - Admin Panel'
admin.site.site_title = 'Life OS Admin'
admin.site.index_title = 'Quản lý hệ thống Life OS'
