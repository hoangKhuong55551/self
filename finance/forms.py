from django import forms
from django.db import models
from decimal import Decimal

from core.forms import HttpsURLField
from .models import Wallet, Transaction, Category, Budget, Subscription, WishlistItem, Transfer, SavingGoal, Asset, WorkoutLog, Debt, DebtPayment


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


RECEIPT_MAX_BYTES = 8 * 1024 * 1024
RECEIPT_MAX_SIDE = 1600


def process_receipt(upload):
    """
    Ảnh hoá đơn: kiểm tra đúng là ảnh, xoay theo EXIF, thu nhỏ, lưu JPEG.
    Lưu lại ảnh mới nên mọi EXIF (vị trí GPS, máy chụp...) bị bỏ.
    """
    from io import BytesIO

    from django.core.files.base import ContentFile
    from PIL import Image, ImageOps, UnidentifiedImageError

    if upload.size > RECEIPT_MAX_BYTES:
        raise forms.ValidationError('Ảnh tối đa 8 MB.')
    try:
        image = Image.open(upload)
        image.load()
    except (UnidentifiedImageError, OSError):
        raise forms.ValidationError('File không phải ảnh hợp lệ (JPG, PNG, WebP...).')
    image = ImageOps.exif_transpose(image).convert('RGB')
    image.thumbnail((RECEIPT_MAX_SIDE, RECEIPT_MAX_SIDE))
    out = BytesIO()
    image.save(out, 'JPEG', quality=82, optimize=True)
    return ContentFile(out.getvalue(), name='receipt.jpg')


class TransactionForm(forms.ModelForm):
    receipt = forms.ImageField(
        label='Ảnh hoá đơn (tuỳ chọn)', required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
    )

    class Meta:
        model = Transaction
        fields = ['transaction_type', 'amount', 'wallet', 'category', 'date', 'note', 'receipt']
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

    def clean_receipt(self):
        receipt = self.cleaned_data.get('receipt')
        # Ảnh mới tải lên: chuẩn hoá. False = bấm "xoá ảnh"; FieldFile cũ = giữ nguyên
        if receipt and hasattr(receipt, 'content_type'):
            return process_receipt(receipt)
        return receipt

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
        field_classes = {'url': HttpsURLField}
        fields = ['transaction_type', 'name', 'amount', 'wallet', 'category', 'billing_cycle', 'start_date', 'next_billing_date',
                  'saving_goal', 'saving_percent', 'url', 'note']
        labels = {
            'saving_goal': 'Tự trích vào quỹ (khoản thu)', 'saving_percent': '% trích mỗi lần nhận',
            'transaction_type': 'Loại', 'name': 'Tên khoản', 'amount': 'Số tiền (VND)', 'wallet': 'Ví', 'category': 'Danh mục',
            'billing_cycle': 'Chu kỳ thanh toán', 'start_date': 'Ngày bắt đầu',
            'next_billing_date': 'Kỳ hạn kế tiếp', 'url': 'URL', 'note': 'Ghi chú',
        }
        widgets = {
            'transaction_type': forms.Select(attrs={'class': 'form-select'}),
            'saving_goal': forms.Select(attrs={'class': 'form-select'}),
            'saving_percent': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Netflix, tiền nhà, lương...'}),
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
            # Cả danh mục thu lẫn chi; clean() kiểm tra khớp với loại khoản
            self.fields['category'].queryset = Category.objects.filter(user=user).order_by('type', 'name')
            self.fields['saving_goal'].queryset = SavingGoal.objects.filter(user=user).filter(
                models.Q(is_completed=False) | models.Q(pk=self.instance.saving_goal_id))
        self.fields['transaction_type'].required = False  # bỏ trống = khoản chi (như trước đây)
        self.fields['saving_goal'].empty_label = '— Không trích —'
        self.fields['saving_percent'].required = False

    def clean_transaction_type(self):
        return self.cleaned_data.get('transaction_type') or Transaction.TransactionType.EXPENSE

    def clean(self):
        cleaned = super().clean()
        category, kind = cleaned.get('category'), cleaned.get('transaction_type')
        if category and kind and category.type != kind:
            self.add_error('category', 'Danh mục này thuộc loại "%s", không khớp với loại khoản.' % category.get_type_display())
        goal, percent = cleaned.get('saving_goal'), cleaned.get('saving_percent') or 0
        cleaned['saving_percent'] = percent
        if goal or percent:
            if kind != Transaction.TransactionType.INCOME:
                self.add_error('saving_goal', 'Chỉ khoản thu (lương...) mới tự trích tiết kiệm được.')
            elif not goal:
                self.add_error('saving_goal', 'Chọn quỹ nhận tiền trích.')
            elif not 1 <= percent <= 100:
                self.add_error('saving_percent', 'Nhập từ 1 đến 100%.')
        return cleaned


class WishlistItemForm(forms.ModelForm):
    class Meta:
        model = WishlistItem
        field_classes = {'url': HttpsURLField}
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
        kwargs.setdefault('auto_id', 'filter_%s')  # tránh trùng id với form thêm giao dịch cùng trang
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


class DebtForm(forms.ModelForm):
    class Meta:
        model = Debt
        fields = ['direction', 'person', 'amount', 'wallet', 'date', 'due_date', 'note']
        labels = {
            'direction': 'Loại', 'person': 'Người', 'amount': 'Số tiền (VND)', 'wallet': 'Ví (tuỳ chọn)',
            'date': 'Ngày', 'due_date': 'Hẹn trả', 'note': 'Ghi chú',
        }
        widgets = {
            'direction': forms.Select(attrs={'class': 'form-select'}),
            'person': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên người vay / cho vay'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '1000'}),
            'wallet': forms.Select(attrs={'class': 'form-select'}),
            'date': date_input(),
            'due_date': date_input(),
            'note': forms.TextInput(attrs={'class': 'form-control'}),
        }
        help_texts = {'wallet': 'Chọn ví thì số dư ví thay đổi theo (cho mượn: trừ, đi vay: cộng).'}

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['wallet'].required = False
        self.fields['wallet'].empty_label = '— Không gắn ví —'
        if user:
            self.fields['wallet'].queryset = own_wallets(user, include=self.instance.wallet_id)

    def clean(self):
        cleaned = super().clean()
        date, due = cleaned.get('date'), cleaned.get('due_date')
        if date and due and due < date:
            self.add_error('due_date', 'Ngày hẹn trả phải sau ngày mượn.')
        amount = cleaned.get('amount')
        if self.instance.pk and amount is not None and amount < self.instance.paid:
            self.add_error('amount', f'Đã trả {self.instance.paid:,.0f} đ, số tiền không thể nhỏ hơn.'.replace(',', '.'))
        return cleaned


class DebtPaymentForm(forms.ModelForm):
    class Meta:
        model = DebtPayment
        fields = ['amount', 'wallet', 'date', 'note']
        labels = {'amount': 'Số tiền', 'wallet': 'Ví', 'date': 'Ngày', 'note': 'Ghi chú'}
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '1000'}),
            'wallet': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'date': forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'}, format='%Y-%m-%d'),
            'note': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Ghi chú'}),
        }

    def __init__(self, *args, debt=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.debt = debt
        self.fields['wallet'].required = False
        self.fields['wallet'].empty_label = '— Không gắn ví —'
        if user:
            self.fields['wallet'].queryset = own_wallets(user)

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if self.debt is not None and amount > self.debt.remaining:
            raise forms.ValidationError(f'Chỉ còn {self.debt.remaining:,.0f} đ chưa trả.'.replace(',', '.'))
        return amount


class SplitBillForm(forms.Form):
    """Mình trả trước cho cả nhóm, chia đều: phần mình là chi tiêu, phần mỗi người là khoản cho mượn."""
    title = forms.CharField(label='Khoản gì', max_length=120,
                            widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ăn lẩu tối thứ 6'}))
    total = forms.DecimalField(label='Tổng tiền mình đã trả (VND)', min_value=Decimal('1'), max_digits=15, decimal_places=0,
                               widget=forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}))
    people = forms.CharField(
        label='Chia với ai', help_text='Mỗi người một dòng, hoặc cách nhau bằng dấu phẩy.',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Nam, Lan, Minh'}),
    )
    include_me = forms.BooleanField(label='Tính cả phần của mình', required=False, initial=True,
                                    widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    wallet = forms.ModelChoiceField(label='Trả bằng ví', queryset=Wallet.objects.none(),
                                    widget=forms.Select(attrs={'class': 'form-select'}))
    category = forms.ModelChoiceField(label='Danh mục phần của mình', queryset=Category.objects.none(), required=False,
                                      widget=forms.Select(attrs={'class': 'form-select'}))
    date = forms.DateField(label='Ngày', widget=date_input())
    due_date = forms.DateField(label='Hẹn trả (tuỳ chọn)', required=False, widget=date_input())

    def __init__(self, *args, user=None, **kwargs):
        kwargs.setdefault('auto_id', 'split_%s')  # cùng trang với form ghi nợ
        super().__init__(*args, **kwargs)
        if user:
            self.fields['wallet'].queryset = own_wallets(user)
            self.fields['category'].queryset = Category.objects.filter(user=user, type='expense')
        self.fields['category'].empty_label = '— Chưa phân loại —'

    def clean_people(self):
        import re
        names = [n.strip() for n in re.split(r'[,\n;]+', self.cleaned_data['people']) if n.strip()]
        if not names:
            raise forms.ValidationError('Nhập ít nhất một người.')
        if len(names) > 30:
            raise forms.ValidationError('Tối đa 30 người.')
        if any(len(n) > 120 for n in names):
            raise forms.ValidationError('Tên quá dài.')
        return names

    def clean(self):
        cleaned = super().clean()
        date, due = cleaned.get('date'), cleaned.get('due_date')
        if date and due and due < date:
            self.add_error('due_date', 'Ngày hẹn trả phải sau ngày chia.')
        people, total = cleaned.get('people'), cleaned.get('total')
        if people and total is not None and total < len(people) + (1 if cleaned.get('include_me') else 0):
            self.add_error('total', 'Tổng tiền quá nhỏ để chia.')
        return cleaned
