from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import WeeklyReflection

User = get_user_model()

class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'}))
    first_name = forms.CharField(max_length=50, required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Họ và tên đệm'}))
    last_name = forms.CharField(max_length=50, required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên'}))

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên đăng nhập'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class WeeklyReflectionForm(forms.ModelForm):
    class Meta:
        model = WeeklyReflection
        fields = ['mood', 'went_well', 'to_improve', 'next_focus']
        widgets = {
            'mood': forms.RadioSelect(attrs={'class': 'mood-radio'}),
            'went_well': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Điều gì diễn ra tốt tuần này?'}),
            'to_improve': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Điều gì cần cải thiện?'}),
            'next_focus': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': '1-3 việc quan trọng nhất cho tuần sau'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Bỏ lựa chọn rỗng "---------" khỏi nhóm radio cảm xúc
        self.fields['mood'].choices = WeeklyReflection.Mood.choices
