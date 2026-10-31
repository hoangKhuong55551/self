from django.urls import path
from . import views

app_name = 'productivity'

urlpatterns = [
    path('', views.productivity_dashboard, name='dashboard'),
    path('goals/', views.goal_list, name='goal_list'),
    path('goals/<int:pk>/edit/', views.goal_edit, name='goal_edit'),
    path('goals/<int:pk>/delete/', views.goal_delete, name='goal_delete'),
    path('kanban/', views.kanban_board, name='kanban_board'),
    path('tasks/<int:pk>/status/', views.update_task_status, name='update_task_status'),
    path('tasks/<int:pk>/edit/', views.task_edit, name='task_edit'),
    path('tasks/<int:pk>/delete/', views.task_delete, name='task_delete'),
    path('habits/', views.habit_tracker, name='habit_tracker'),
    path('habits/<int:pk>/toggle/', views.toggle_habit_today, name='toggle_habit'),
    path('habits/<int:pk>/edit/', views.habit_edit, name='habit_edit'),
    path('habits/<int:pk>/delete/', views.habit_delete, name='habit_delete'),
    path('pomodoro/', views.pomodoro_timer, name='pomodoro_timer'),
    path('pomodoro/save/', views.save_pomodoro_session, name='save_pomodoro_session'),
]
