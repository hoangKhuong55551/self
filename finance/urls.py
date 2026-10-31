from django.urls import path
from . import views

app_name = 'finance'

urlpatterns = [
    path('', views.finance_dashboard, name='dashboard'),

    path('wallets/', views.wallet_list, name='wallet_list'),
    path('wallets/<int:pk>/edit/', views.wallet_edit, name='wallet_edit'),
    path('wallets/<int:pk>/delete/', views.wallet_delete, name='wallet_delete'),
    path('wallets/<int:pk>/recalculate/', views.wallet_recalculate, name='wallet_recalculate'),

    path('categories/', views.category_list, name='category_list'),
    path('categories/<int:pk>/edit/', views.category_edit, name='category_edit'),
    path('categories/<int:pk>/delete/', views.category_delete, name='category_delete'),

    path('transactions/', views.transaction_list, name='transaction_list'),
    path('transactions/import/', views.transaction_import, name='transaction_import'),
    path('transactions/<int:pk>/edit/', views.transaction_edit, name='transaction_edit'),
    path('transactions/<int:pk>/delete/', views.transaction_delete, name='transaction_delete'),

    path('transfers/', views.transfer_list, name='transfer_list'),
    path('transfers/<int:pk>/delete/', views.transfer_delete, name='transfer_delete'),

    path('budgets/', views.budget_list, name='budget_list'),
    path('budgets/copy-last-month/', views.budget_copy_last_month, name='budget_copy_last_month'),
    path('budgets/<int:pk>/edit/', views.budget_edit, name='budget_edit'),
    path('budgets/<int:pk>/delete/', views.budget_delete, name='budget_delete'),

    path('subscriptions/', views.subscription_list, name='subscription_list'),
    path('subscriptions/<int:pk>/edit/', views.subscription_edit, name='subscription_edit'),
    path('subscriptions/<int:pk>/toggle/', views.subscription_toggle, name='subscription_toggle'),
    path('subscriptions/<int:pk>/delete/', views.subscription_delete, name='subscription_delete'),

    path('savings/', views.saving_goal_list, name='saving_goal_list'),
    path('savings/<int:pk>/adjust/', views.saving_goal_adjust, name='saving_goal_adjust'),
    path('savings/<int:pk>/edit/', views.saving_goal_edit, name='saving_goal_edit'),
    path('savings/<int:pk>/delete/', views.saving_goal_delete, name='saving_goal_delete'),

    path('wishlist/', views.wishlist_view, name='wishlist'),
    path('wishlist/<int:pk>/edit/', views.wishlist_edit, name='wishlist_edit'),
    path('wishlist/<int:pk>/delete/', views.wishlist_delete, name='wishlist_delete'),
    path('wishlist/<int:pk>/purchase/', views.wishlist_purchase, name='wishlist_purchase'),

    path('assets/', views.asset_list, name='asset_list'),
]
