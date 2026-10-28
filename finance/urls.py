from django.urls import path
from . import views

app_name = 'finance'

urlpatterns = [
    path('', views.finance_dashboard, name='dashboard'),
    path('wallets/', views.wallet_list, name='wallet_list'),
    path('transactions/', views.transaction_list, name='transaction_list'),
    path('budgets/', views.budget_list, name='budget_list'),
    path('subscriptions/', views.subscription_list, name='subscription_list'),
    path('wishlist/', views.wishlist_view, name='wishlist'),
    path('wishlist/<int:pk>/purchase/', views.wishlist_purchase, name='wishlist_purchase'),
    path('assets/', views.asset_list, name='asset_list'),
]
