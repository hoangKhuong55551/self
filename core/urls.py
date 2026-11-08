from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('register/', views.register_view, name='register'),
    path('search/', views.search_api, name='search'),
    path('quick-add/', views.quick_add, name='quick_add'),
    path('achievements/', views.achievements_view, name='achievements'),
    path('review/', views.weekly_review, name='weekly_review'),
    path('calendar/', views.calendar_view, name='calendar'),
    path('calendar/feed/<str:token>.ics', views.calendar_feed, name='calendar_feed'),
    path('calendar/link/', views.calendar_token_reset, name='calendar_token_reset'),
    path('export/', views.export_page, name='export'),
    path('export/restore/', views.restore_backup, name='restore'),
    path('sw.js', views.service_worker, name='service_worker'),
    path('push/subscribe/', views.push_subscribe, name='push_subscribe'),
    path('push/unsubscribe/', views.push_unsubscribe, name='push_unsubscribe'),
    path('push/test/', views.push_test, name='push_test'),
    path('offline/', views.offline_page, name='offline'),
    path('export/<str:kind>/', views.export_download, name='export_download'),
]
