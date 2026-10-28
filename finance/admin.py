from django.contrib import admin
from .models import Wallet, Category, Transaction, Budget, Subscription, WishlistItem, SavingGoal, Asset, WorkoutLog

@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'balance', 'currency', 'is_active', 'created_at')
    list_filter = ('currency', 'is_active')
    search_fields = ('name', 'user__username')

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'type', 'color')
    list_filter = ('type',)
    search_fields = ('name', 'user__username')

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('date', 'user', 'wallet', 'category', 'transaction_type', 'amount', 'source')
    list_filter = ('transaction_type', 'source', 'date')
    search_fields = ('note', 'user__username')

@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ('category', 'user', 'month', 'year', 'amount')
    list_filter = ('year', 'month')

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'amount', 'billing_cycle', 'next_billing_date', 'is_active')
    list_filter = ('billing_cycle', 'is_active')
    search_fields = ('name', 'user__username')

@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'price', 'priority', 'is_purchased', 'purchased_date')
    list_filter = ('priority', 'is_purchased')
    search_fields = ('name', 'user__username')

@admin.register(SavingGoal)
class SavingGoalAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'target_amount', 'current_amount', 'deadline', 'is_completed')
    list_filter = ('is_completed',)
    search_fields = ('name', 'user__username')

@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'purchase_price', 'condition', 'usage_hours', 'max_lifespan_hours')
    list_filter = ('condition',)
    search_fields = ('name', 'user__username')

@admin.register(WorkoutLog)
class WorkoutLogAdmin(admin.ModelAdmin):
    list_display = ('date', 'user', 'activity_type', 'duration_minutes', 'gear_used')
    list_filter = ('activity_type', 'date')
    search_fields = ('notes', 'user__username')
