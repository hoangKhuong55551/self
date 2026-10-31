from django import forms
from .models import Wallet, Transaction, Category, Budget, Subscription, WishlistItem

class WalletForm(forms.ModelForm):
    class Meta:
        model = Wallet
        fields = ['name', 'balance', 'currency', 'icon']
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


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['wallet', 'category', 'transaction_type', 'amount', 'date', 'note']
        widgets = {
            'wallet': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'transaction_type': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '1000', 'placeholder': 'Số tiền'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'note': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ghi chú giao dịch...'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['wallet'].queryset = Wallet.objects.filter(user=user, is_active=True)
            self.fields['category'].queryset = Category.objects.filter(user=user)


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'type', 'icon', 'color']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên danh mục'}),
            'type': forms.Select(attrs={'class': 'form-select'}),
            'icon': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'tag, cup, cart...'}),
            'color': forms.TextInput(attrs={'class': 'form-control form-control-color', 'type': 'color'}),
        }


class BudgetForm(forms.ModelForm):
    class Meta:
        model = Budget
        fields = ['category', 'amount', 'month', 'year']
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
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Netflix, Spotify...'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '1000'}),
            'wallet': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'billing_cycle': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'next_billing_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
            'note': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['wallet'].queryset = Wallet.objects.filter(user=user, is_active=True)
            self.fields['category'].queryset = Category.objects.filter(user=user, type='expense')


class WishlistItemForm(forms.ModelForm):
    class Meta:
        model = WishlistItem
        fields = ['name', 'price', 'priority', 'wallet', 'target_date', 'url', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Món đồ muốn mua'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '1000'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'wallet': forms.Select(attrs={'class': 'form-select'}),
            'target_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'Link sản phẩm'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['wallet'].queryset = Wallet.objects.filter(user=user, is_active=True)
