from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('register/', views.register_view, name='register'),
    path('search/', views.search_api, name='search'),
    path('achievements/', views.achievements_view, name='achievements'),
    path('review/', views.weekly_review, name='weekly_review'),
    path('export/', views.export_page, name='export'),
    path('sw.js', views.service_worker, name='service_worker'),
    path('offline/', views.offline_page, name='offline'),
    path('export/<str:kind>/', views.export_download, name='export_download'),
]
