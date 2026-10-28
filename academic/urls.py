from django.urls import path
from . import views

app_name = 'academic'

urlpatterns = [
    path('', views.academic_dashboard, name='dashboard'),
    path('gpa/', views.gpa_tracker, name='gpa_tracker'),
    path('gpa/simulator/', views.gpa_simulator, name='gpa_simulator'),
    path('notes/', views.note_list, name='note_list'),
    path('notes/<int:pk>/', views.note_detail, name='note_detail'),
    path('snippets/', views.snippet_list, name='snippet_list'),
    path('snippets/<int:pk>/', views.snippet_detail, name='snippet_detail'),
]
