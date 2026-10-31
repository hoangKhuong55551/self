from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.db.models import Sum
from decimal import Decimal


class Wallet(models.Model):
    """Ví tiền: tiền mặt, ngân hàng, ví điện tử..."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='wallets'
    )
    name = models.CharField(max_length=100)
    initial_balance = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00'),
        help_text="Số dư lúc tạo ví, gốc để tính lại số dư"
    )
    balance = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00')
    )
    currency = models.CharField(max_length=3, default='VND')
    icon = models.CharField(max_length=50, default='wallet')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'name'],
                name='unique_wallet_per_user'
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.balance:,.0f} {self.currency})"

    def save(self, *args, **kwargs):
        # Ví mới: số dư nhập vào chính là số dư ban đầu
        if self._state.adding and not self.initial_balance:
            self.initial_balance = self.balance
        super().save(*args, **kwargs)

    def compute_balance(self):
        """Số dư = ban đầu + thu - chi + tiền chuyển đến - tiền chuyển đi."""
        def total(qs):
            return qs.aggregate(total=Sum('amount'))['total'] or Decimal('0')

        return (
            self.initial_balance
            + total(self.transactions.filter(transaction_type='income'))
            - total(self.transactions.filter(transaction_type='expense'))
            + total(self.transfers_in.all())
            - total(self.transfers_out.all())
        )

    def recalculate_balance(self):
        """Tính lại số dư từ toàn bộ lịch sử (bảo toàn tính nhất quán)."""
        self.balance = self.compute_balance()
        self.save(update_fields=['balance'])


class Category(models.Model):
    """Danh mục Thu/Chi: Ăn uống, Di chuyển, Lương, Freelance..."""

    class CategoryType(models.TextChoices):
        INCOME = 'income', 'Thu nhập'
        EXPENSE = 'expense', 'Chi tiêu'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='categories'
    )
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=7, choices=CategoryType.choices)
    icon = models.CharField(max_length=50, default='tag')
    color = models.CharField(max_length=7, default='#6366f1')

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']

    def __str__(self):
        return f"{self.get_type_display()}: {self.name}"


class Transaction(models.Model):
    """Giao dịch Thu/Chi — bảng ghi trung tâm của phân hệ tài chính."""

    class TransactionType(models.TextChoices):
        INCOME = 'income', 'Thu nhập'
        EXPENSE = 'expense', 'Chi tiêu'

    class Source(models.TextChoices):
        MANUAL = 'manual', 'Nhập tay'
        SUBSCRIPTION = 'subscription', 'Gói đăng ký tự động'
        WISHLIST = 'wishlist', 'Mua từ Wishlist'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='transactions'
    )
    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name='transactions'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='transactions'
    )
    transaction_type = models.CharField(
        max_length=7,
        choices=TransactionType.choices
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    date = models.DateField(default=timezone.now)
    note = models.TextField(blank=True, default='')
    source = models.CharField(
        max_length=15,
        choices=Source.choices,
        default=Source.MANUAL
    )

    subscription = models.ForeignKey(
        'Subscription',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='generated_transactions'
    )
    wishlist_item = models.ForeignKey(
        'WishlistItem',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='generated_transactions'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['user', 'date']),
            models.Index(fields=['user', 'transaction_type']),
            models.Index(fields=['wallet', 'date']),
        ]

    def __str__(self):
        sign = '+' if self.transaction_type == 'income' else '-'
        return f"{sign}{self.amount:,.0f} | {self.note[:30]}"


class Transfer(models.Model):
    """Chuyển tiền giữa hai ví của cùng user — không tính là thu hay chi."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='transfers'
    )
    from_wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name='transfers_out'
    )
    to_wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name='transfers_in'
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    date = models.DateField(default=timezone.now)
    note = models.CharField(max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.from_wallet.name} → {self.to_wallet.name}: {self.amount:,.0f}"


class Budget(models.Model):
    """Hạn mức chi tiêu theo danh mục, theo tháng."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='budgets'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='budgets'
    )
    month = models.PositiveSmallIntegerField()  # 1-12
    year = models.PositiveIntegerField()
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'category', 'month', 'year'],
                name='unique_budget_per_category_month'
            )
        ]

    def __str__(self):
        return f"Budget: {self.category.name} - {self.month}/{self.year}"

    @property
    def spent(self):
        """Tổng chi tiêu thực tế trong tháng."""
        return Transaction.objects.filter(
            user=self.user,
            category=self.category,
            transaction_type='expense',
            date__month=self.month,
            date__year=self.year,
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

    @property
    def remaining(self):
        return self.amount - self.spent

    @property
    def percent_used(self):
        if self.amount == 0:
            return 0
        return min(round((self.spent / self.amount) * 100, 1), 999)

    @property
    def is_over_budget(self):
        return self.spent > self.amount


class Subscription(models.Model):
    """Gói dịch vụ trả phí định kỳ."""

    class BillingCycle(models.TextChoices):
        WEEKLY = 'weekly', 'Hàng tuần'
        MONTHLY = 'monthly', 'Hàng tháng'
        QUARTERLY = 'quarterly', 'Hàng quý'
        YEARLY = 'yearly', 'Hàng năm'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='subscriptions'
    )
    name = models.CharField(max_length=200)
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name='subscriptions'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='subscriptions'
    )
    billing_cycle = models.CharField(
        max_length=10,
        choices=BillingCycle.choices,
        default=BillingCycle.MONTHLY
    )
    start_date = models.DateField()
    next_billing_date = models.DateField()
    is_active = models.BooleanField(default=True)
    icon = models.CharField(max_length=50, blank=True, default='')
    url = models.URLField(blank=True, default='')
    note = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['next_billing_date']

    def __str__(self):
        return f"{self.name} ({self.amount:,.0f}/{self.get_billing_cycle_display()})"

    def advance_billing_date(self):
        """Tính ngày thanh toán tiếp theo dựa trên chu kỳ."""
        from dateutil.relativedelta import relativedelta
        cycle_map = {
            'weekly': relativedelta(weeks=1),
            'monthly': relativedelta(months=1),
            'quarterly': relativedelta(months=3),
            'yearly': relativedelta(years=1),
        }
        self.next_billing_date += cycle_map[self.billing_cycle]
        self.save(update_fields=['next_billing_date'])

    @property
    def monthly_cost(self):
        multiplier = {
            'weekly': Decimal('4.33'),
            'monthly': Decimal('1'),
            'quarterly': Decimal('1') / Decimal('3'),
            'yearly': Decimal('1') / Decimal('12'),
        }
        return round(self.amount * multiplier[self.billing_cycle], 2)


class WishlistItem(models.Model):
    """Món đồ muốn mua."""

    class Priority(models.IntegerChoices):
        LOW = 1, '⬇️ Thấp'
        MEDIUM = 2, '➡️ Trung bình'
        HIGH = 3, '⬆️ Cao'
        URGENT = 4, '🔥 Cần ngay'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='wishlist_items'
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    url = models.URLField(blank=True, default='', help_text="Link sản phẩm")
    image = models.ImageField(upload_to='wishlist/', blank=True, null=True)
    priority = models.IntegerField(
        choices=Priority.choices,
        default=Priority.MEDIUM
    )
    target_date = models.DateField(null=True, blank=True)

    is_purchased = models.BooleanField(default=False)
    purchased_date = models.DateField(null=True, blank=True)
    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='wishlist_items',
        help_text="Ví sẽ trừ tiền khi mua"
    )
    saving_goal = models.ForeignKey(
        'SavingGoal',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='wishlist_items',
        help_text="Quỹ tiết kiệm dành cho món này; khi mua sẽ rút từ quỹ"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-priority', 'created_at']

    def __str__(self):
        status = "✅" if self.is_purchased else "🛒"
        return f"{status} {self.name} ({self.price:,.0f})"

    def affordability(self):
        """% giá đã có: theo quỹ tiết kiệm gắn kèm, nếu không thì theo tổng số dư các ví."""
        if self.saving_goal_id:
            available = self.saving_goal.current_amount
        else:
            available = Wallet.objects.filter(
                user=self.user, is_active=True
            ).aggregate(total=Sum('balance'))['total'] or Decimal('0')

        if self.price == 0:
            return 100
        return max(min(round((available / self.price) * 100, 1), 100), 0)


class SavingGoal(models.Model):
    """Mục tiêu tiết kiệm dài hạn."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saving_goals'
    )
    name = models.CharField(max_length=200)
    target_amount = models.DecimalField(
        max_digits=15, decimal_places=2,
        validators=[MinValueValidator(Decimal('1'))]
    )
    current_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0')
    )
    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='saving_goals'
    )
    deadline = models.DateField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['is_completed', 'deadline', '-created_at']

    def __str__(self):
        return f"🎯 {self.name}: {self.progress_percent}%"

    def adjust(self, delta):
        """Nạp (delta > 0) hoặc rút (delta < 0) tiền khỏi quỹ, không để âm. Trả về True nếu vừa đạt mục tiêu."""
        was_completed = self.is_completed
        self.current_amount = max(self.current_amount + delta, Decimal('0'))
        self.is_completed = self.current_amount >= self.target_amount
        self.save(update_fields=['current_amount', 'is_completed'])
        return self.is_completed and not was_completed

    @property
    def monthly_needed(self):
        """Số tiền cần để dành mỗi tháng để kịp hạn (None nếu không có hạn hoặc đã đạt)."""
        if not self.deadline or self.is_completed:
            return None
        today = timezone.now().date()
        months_left = max((self.deadline.year - today.year) * 12 + self.deadline.month - today.month, 1)
        return round(self.remaining / months_left, 0)

    @property
    def progress_percent(self):
        if self.target_amount == 0:
            return 100
        return min(round((self.current_amount / self.target_amount) * 100, 1), 100)

    @property
    def remaining(self):
        return max(self.target_amount - self.current_amount, Decimal('0'))


class Asset(models.Model):
    """Đồ đạc/Dụng cụ đang sở hữu."""

    class Condition(models.TextChoices):
        NEW = 'new', 'Mới'
        GOOD = 'good', 'Tốt'
        WORN = 'worn', 'Hao mòn'
        REPLACE = 'replace', 'Cần thay'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='assets'
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    purchase_price = models.DecimalField(
        max_digits=15, decimal_places=2,
        default=Decimal('0')
    )
    purchase_date = models.DateField(null=True, blank=True)
    condition = models.CharField(
        max_length=10,
        choices=Condition.choices,
        default=Condition.NEW
    )
    usage_hours = models.FloatField(default=0, help_text="Tổng giờ sử dụng")
    max_lifespan_hours = models.FloatField(
        null=True, blank=True,
        help_text="Tuổi thọ dự kiến (giờ)"
    )
    image = models.ImageField(upload_to='assets/', blank=True, null=True)

    from_wishlist = models.OneToOneField(
        WishlistItem,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='asset'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.get_condition_display()})"

    @property
    def lifespan_percent(self):
        if not self.max_lifespan_hours or self.max_lifespan_hours == 0:
            return None
        return min(round((self.usage_hours / self.max_lifespan_hours) * 100, 1), 100)

    @property
    def needs_replacement(self):
        pct = self.lifespan_percent
        return pct is not None and pct >= 80


class WorkoutLog(models.Model):
    """Nhật ký vận động — liên kết với Asset (dụng cụ)."""

    ACTIVITY_CHOICES = [
        ('running', '🏃 Chạy bộ'),
        ('cycling', '🚴 Đạp xe'),
        ('gym', '🏋️ Gym'),
        ('swimming', '🏊 Bơi'),
        ('badminton', '🏸 Cầu lông'),
        ('football', '⚽ Bóng đá'),
        ('basketball', '🏀 Bóng rổ'),
        ('yoga', '🧘 Yoga'),
        ('hiking', '🥾 Leo núi'),
        ('other', '🏅 Khác'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='workout_logs'
    )
    date = models.DateField(default=timezone.now)
    activity_type = models.CharField(
        max_length=20,
        choices=ACTIVITY_CHOICES
    )
    duration_minutes = models.PositiveIntegerField(help_text="Thời gian (phút)")
    distance_km = models.FloatField(null=True, blank=True, help_text="Quãng đường (km)")
    calories = models.PositiveIntegerField(null=True, blank=True)
    gear_used = models.ForeignKey(
        Asset,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='workout_logs',
        help_text="Dụng cụ/giày sử dụng"
    )
    notes = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.get_activity_type_display()} | {self.date} | {self.duration_minutes}m"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.gear_used:
            total_minutes = WorkoutLog.objects.filter(
                gear_used=self.gear_used
            ).aggregate(
                total=Sum('duration_minutes')
            )['total'] or 0
            self.gear_used.usage_hours = total_minutes / 60.0
            if self.gear_used.lifespan_percent and self.gear_used.lifespan_percent >= 80:
                self.gear_used.condition = 'replace'
            elif self.gear_used.lifespan_percent and self.gear_used.lifespan_percent >= 50:
                self.gear_used.condition = 'worn'
            self.gear_used.save(update_fields=['usage_hours', 'condition'])
