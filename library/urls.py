from django.urls import path
from . import views

app_name = 'library'

urlpatterns = [
    path('', views.library_shelf, name='shelf'),
    path('lookup/', views.book_lookup, name='book_lookup'),
    path('<int:pk>/', views.item_detail, name='item_detail'),
    path('<int:pk>/quick/', views.item_quick_update, name='item_quick_update'),
    path('<int:pk>/delete/', views.item_delete, name='item_delete'),
]
