from django.urls import path
from . import views

app_name = 'productivity'

urlpatterns = [
    path('', views.productivity_dashboard, name='dashboard'),
    path('goals/', views.goal_list, name='goal_list'),
    path('kanban/', views.kanban_board, name='kanban_board'),
    path('tasks/<int:pk>/status/', views.update_task_status, name='update_task_status'),
    path('habits/', views.habit_tracker, name='habit_tracker'),
    path('habits/<int:pk>/toggle/', views.toggle_habit_today, name='toggle_habit_today'),
    path('pomodoro/', views.pomodoro_timer, name='pomodoro_timer'),
    path('pomodoro/save/', views.save_pomodoro_session, name='save_pomodoro_session'),
]
