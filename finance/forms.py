from django import forms
from .models import Wallet, Transaction, Category, Budget, Subscription, WishlistItem, Transfer, SavingGoal, Asset, WorkoutLog


def date_input():
    # type=date chỉ nhận YYYY-MM-DD; thiếu format thì form sửa sẽ hiện trống với locale 'vi'
    return forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d')


def own_wallets(user, include=None):
    """Ví đang hoạt động của user, kèm ví `include` (khi sửa bản ghi thuộc ví đã khoá)."""
    qs = Wallet.objects.filter(user=user, is_active=True)
    if include:
        qs = qs | Wallet.objects.filter(pk=include)
    return qs.distinct()


class WalletForm(forms.ModelForm):
    class Meta:
        model = Wallet
        fields = ['name', 'balance', 'currency', 'icon']
        labels = {'name': 'Tên ví', 'balance': 'Số dư ban đầu', 'currency': 'Đơn vị tiền tệ', 'icon': 'Icon'}
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ví dụ: Ví Tiền Mặt, Vietcombank...'}),
            'balance': forms.NumberInput(attrs={'class': 'form-control', 'step': '1000'}),
            'currency': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'VND'}),
            'icon': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'wallet, cash, credit-card...'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_name(self):
        # Ràng buộc unique (user, name) không được form tự kiểm vì 'user' không nằm trong fields
        name = self.cleaned_data['name']
        if self.user and Wallet.objects.filter(user=self.user, name=name).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Bạn đã có ví với tên này.")
        return name


class WalletEditForm(WalletForm):
    """Sửa ví: số dư không sửa tay (được tính từ lịch sử), có thể khoá/mở ví."""
    class Meta(WalletForm.Meta):
        fields = ['name', 'currency', 'icon', 'is_active']
        labels = {**WalletForm.Meta.labels, 'is_active': 'Đang sử dụng'}
        widgets = {**WalletForm.Meta.widgets, 'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})}


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['transaction_type', 'amount', 'wallet', 'category', 'date', 'note']
        labels = {
            'wallet': 'Ví', 'category': 'Danh mục', 'transaction_type': 'Loại giao dịch',
            'amount': 'Số tiền (VND)', 'date': 'Ngày giao dịch', 'note': 'Ghi chú',
        }
        widgets = {
            'wallet': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'transaction_type': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '1000', 'placeholder': 'Số tiền'}),
            'date': date_input(),
            'note': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ghi chú giao dịch...'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['wallet'].queryset = own_wallets(user, include=self.instance.wallet_id)
            self.fields['category'].queryset = Category.objects.filter(user=user)

    def clean(self):
        cleaned = super().clean()
        category, kind = cleaned.get('category'), cleaned.get('transaction_type')
        if category and kind and category.type != kind:
            self.add_error('category', f"Danh mục '{category.name}' dành cho {category.get_type_display().lower()}.")
        return cleaned


class TransferForm(forms.ModelForm):
    class Meta:
        model = Transfer
        fields = ['from_wallet', 'to_wallet', 'amount', 'date', 'note']
        labels = {
            'from_wallet': 'Từ ví', 'to_wallet': 'Đến ví', 'amount': 'Số tiền (VND)',
            'date': 'Ngày', 'note': 'Ghi chú',
        }
        widgets = {
            'from_wallet': forms.Select(attrs={'class': 'form-select'}),
            'to_wallet': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '1000'}),
            'date': date_input(),
            'note': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'VD: Rút ATM'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['from_wallet'].queryset = own_wallets(user, include=self.instance.from_wallet_id)
            self.fields['to_wallet'].queryset = own_wallets(user, include=self.instance.to_wallet_id)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('from_wallet') and cleaned.get('from_wallet') == cleaned.get('to_wallet'):
            self.add_error('to_wallet', "Ví nhận phải khác ví chuyển.")
        return cleaned


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'type', 'icon', 'color']
        labels = {'name': 'Tên danh mục', 'type': 'Loại', 'icon': 'Icon (Bootstrap Icons)', 'color': 'Màu'}
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên danh mục'}),
            'type': forms.Select(attrs={'class': 'form-select'}),
            'icon': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'tag, cup-hot, cart...'}),
            'color': forms.TextInput(attrs={'class': 'form-control form-control-color', 'type': 'color'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        # So sánh trong Python: iexact của SQLite không phân biệt hoa/thường với chữ có dấu
        name = cleaned.get('name', '').strip().casefold()
        siblings = Category.objects.filter(user=self.user, type=cleaned.get('type')).exclude(pk=self.instance.pk)
        if self.user and any(c.name.strip().casefold() == name for c in siblings):
            self.add_error('name', "Danh mục này đã tồn tại.")
        return cleaned


class BudgetForm(forms.ModelForm):
    class Meta:
        model = Budget
        fields = ['category', 'amount', 'month', 'year']
        labels = {'category': 'Danh mục chi tiêu', 'amount': 'Hạn mức (VND)', 'month': 'Tháng', 'year': 'Năm'}
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '10000'}),
            'month': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 12}),
            'year': forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['category'].queryset = Category.objects.filter(user=self.user, type='expense')

    def clean_month(self):
        month = self.cleaned_data['month']
        if not 1 <= month <= 12:
            raise forms.ValidationError("Tháng phải từ 1 đến 12.")
        return month

    def clean(self):
        cleaned = super().clean()
        exists = self.user and Budget.objects.filter(
            user=self.user,
            category=cleaned.get('category'),
            month=cleaned.get('month'),
            year=cleaned.get('year'),
        ).exclude(pk=self.instance.pk).exists()
        if exists:
            raise forms.ValidationError("Danh mục này đã có ngân sách cho tháng đã chọn.")
        return cleaned


class SubscriptionForm(forms.ModelForm):
    class Meta:
        model = Subscription
        fields = ['name', 'amount', 'wallet', 'category', 'billing_cycle', 'start_date', 'next_billing_date', 'url', 'note']
        labels = {
            'name': 'Tên dịch vụ', 'amount': 'Chi phí (VND)', 'wallet': 'Ví thanh toán', 'category': 'Danh mục',
            'billing_cycle': 'Chu kỳ thanh toán', 'start_date': 'Ngày bắt đầu',
            'next_billing_date': 'Kỳ hạn kế tiếp', 'url': 'URL', 'note': 'Ghi chú',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Netflix, Spotify...'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '1000'}),
            'wallet': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'billing_cycle': forms.Select(attrs={'class': 'form-select'}),
            'start_date': date_input(),
            'next_billing_date': date_input(),
            'url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
            'note': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['wallet'].queryset = own_wallets(user, include=self.instance.wallet_id)
            self.fields['category'].queryset = Category.objects.filter(user=user, type='expense')


class WishlistItemForm(forms.ModelForm):
    class Meta:
        model = WishlistItem
        fields = ['name', 'price', 'priority', 'wallet', 'saving_goal', 'target_date', 'url', 'description']
        labels = {
            'name': 'Tên món đồ', 'price': 'Giá (VND)', 'priority': 'Mức ưu tiên', 'wallet': 'Ví thanh toán',
            'saving_goal': 'Quỹ tiết kiệm', 'target_date': 'Dự định mua', 'url': 'Link', 'description': 'Mô tả',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Món đồ muốn mua'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '1000'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'wallet': forms.Select(attrs={'class': 'form-select'}),
            'saving_goal': forms.Select(attrs={'class': 'form-select'}),
            'target_date': date_input(),
            'url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'Link sản phẩm'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['saving_goal'].empty_label = '— Không dùng quỹ —'
        if user:
            self.fields['wallet'].queryset = own_wallets(user, include=self.instance.wallet_id)
            self.fields['saving_goal'].queryset = SavingGoal.objects.filter(user=user)


class SavingGoalForm(forms.ModelForm):
    class Meta:
        model = SavingGoal
        fields = ['name', 'target_amount', 'deadline']
        labels = {'name': 'Tên mục tiêu', 'target_amount': 'Số tiền cần (VND)', 'deadline': 'Hạn chót'}
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'VD: Quỹ khẩn cấp, Laptop mới...'}),
            'target_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '100000'}),
            'deadline': date_input(),
        }


class SavingGoalAdjustForm(forms.Form):
    ACTIONS = [('deposit', 'Nạp vào quỹ'), ('withdraw', 'Rút khỏi quỹ')]
    action = forms.ChoiceField(choices=ACTIONS)
    amount = forms.DecimalField(min_value=1, max_digits=15, decimal_places=2)


class TransactionFilterForm(forms.Form):
    """Bộ lọc GET cho lịch sử giao dịch; mọi trường đều tuỳ chọn."""
    q = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Tìm ghi chú...'}))
    type = forms.ChoiceField(
        required=False, choices=[('', 'Mọi loại')] + list(Transaction.TransactionType.choices),
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    wallet = forms.ModelChoiceField(
        required=False, queryset=Wallet.objects.none(), empty_label='Mọi ví',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    category = forms.ModelChoiceField(
        required=False, queryset=Category.objects.none(), empty_label='Mọi danh mục',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'}, format='%Y-%m-%d'))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'}, format='%Y-%m-%d'))
    amount_min = forms.DecimalField(required=False, min_value=0, widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Từ (đ)'}))
    amount_max = forms.DecimalField(required=False, min_value=0, widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Đến (đ)'}))

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields['wallet'].queryset = Wallet.objects.filter(user=user)
            self.fields['category'].queryset = Category.objects.filter(user=user)

    def apply(self, qs):
        if not self.is_valid():
            return qs
        d = self.cleaned_data
        filters = {
            'note__icontains': d.get('q'),
            'transaction_type': d.get('type'),
            'wallet': d.get('wallet'),
            'category': d.get('category'),
            'date__gte': d.get('date_from'),
            'date__lte': d.get('date_to'),
            'amount__gte': d.get('amount_min'),
            'amount__lte': d.get('amount_max'),
        }
        return qs.filter(**{k: v for k, v in filters.items() if v not in (None, '')})


class TransactionImportForm(forms.Form):
    wallet = forms.ModelChoiceField(
        queryset=Wallet.objects.none(), label='Nhập vào ví',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    file = forms.FileField(
        label='File CSV', widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.csv,text/csv'}),
    )

    MAX_SIZE = 2 * 1024 * 1024

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields['wallet'].queryset = Wallet.objects.filter(user=user, is_active=True)

    def clean_file(self):
        f = self.cleaned_data['file']
        if f.size > self.MAX_SIZE:
            raise forms.ValidationError("File tối đa 2MB.")
        return f


class AssetForm(forms.ModelForm):
    class Meta:
        model = Asset
        fields = ['name', 'description', 'purchase_price', 'purchase_date', 'condition', 'max_lifespan_hours']
        labels = {
            'name': 'Tên tài sản', 'description': 'Mô tả', 'purchase_price': 'Giá mua (VND)',
            'purchase_date': 'Ngày mua', 'condition': 'Tình trạng', 'max_lifespan_hours': 'Tuổi thọ dự kiến (giờ)',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'VD: Giày chạy Nike, Vợt cầu lông...'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'purchase_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '1000'}),
            'purchase_date': date_input(),
            'condition': forms.Select(attrs={'class': 'form-select'}),
            'max_lifespan_hours': forms.NumberInput(attrs={'class': 'form-control', 'step': '10', 'placeholder': 'VD: giày chạy ~ 100 giờ'}),
        }


class WorkoutLogForm(forms.ModelForm):
    class Meta:
        model = WorkoutLog
        fields = ['date', 'activity_type', 'duration_minutes', 'distance_km', 'calories', 'gear_used', 'notes']
        labels = {
            'date': 'Ngày', 'activity_type': 'Hoạt động', 'duration_minutes': 'Thời gian (phút)',
            'distance_km': 'Quãng đường (km)', 'calories': 'Calo', 'gear_used': 'Dụng cụ / giày', 'notes': 'Ghi chú',
        }
        widgets = {
            'date': date_input(),
            'activity_type': forms.Select(attrs={'class': 'form-select'}),
            'duration_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'distance_km': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': 0}),
            'calories': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'gear_used': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['gear_used'].empty_label = '— Không dùng —'
        if user:
            self.fields['gear_used'].queryset = Asset.objects.filter(user=user)

    def clean_duration_minutes(self):
        minutes = self.cleaned_data['duration_minutes']
        if not minutes:
            raise forms.ValidationError("Thời gian phải lớn hơn 0.")
        return minutes
