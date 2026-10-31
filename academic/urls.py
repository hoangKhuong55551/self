from django.urls import path
from . import views

app_name = 'academic'

urlpatterns = [
    path('', views.academic_dashboard, name='dashboard'),
    path('gpa/', views.gpa_tracker, name='gpa_tracker'),
    path('gpa/simulator/', views.gpa_simulator, name='gpa_simulator'),
    path('semesters/<int:pk>/edit/', views.semester_edit, name='semester_edit'),
    path('semesters/<int:pk>/delete/', views.semester_delete, name='semester_delete'),
    path('courses/<int:pk>/edit/', views.course_edit, name='course_edit'),
    path('courses/<int:pk>/delete/', views.course_delete, name='course_delete'),
    path('notes/', views.note_list, name='note_list'),
    path('notes/<int:pk>/', views.note_detail, name='note_detail'),
    path('notes/<int:pk>/edit/', views.note_edit, name='note_edit'),
    path('notes/<int:pk>/delete/', views.note_delete, name='note_delete'),
    path('snippets/', views.snippet_list, name='snippet_list'),
    path('snippets/<int:pk>/', views.snippet_detail, name='snippet_detail'),
    path('snippets/<int:pk>/edit/', views.snippet_edit, name='snippet_edit'),
    path('snippets/<int:pk>/delete/', views.snippet_delete, name='snippet_delete'),
]
