from django import forms
from .models import MediaItem, LibraryGoal

RATING_CHOICES = [('', '— Chưa chấm —')] + [(i, '★' * i) for i in range(1, 6)]


class MediaItemForm(forms.ModelForm):
    rating = forms.TypedChoiceField(
        choices=RATING_CHOICES, coerce=int, empty_value=None, required=False,
        widget=forms.Select(attrs={'class': 'form-select'}), label='Đánh giá'
    )

    class Meta:
        model = MediaItem
        fields = [
            'media_type', 'title', 'creator', 'genre', 'status',
            'progress_current', 'progress_total', 'rating',
            'cover', 'cover_url', 'review', 'started_on', 'finished_on',
        ]
        widgets = {
            'media_type': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'VD: Nhà Giả Kim, Interstellar, Elden Ring...'}),
            'creator': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tác giả / Đạo diễn / Studio'}),
            'genre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Thể loại'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'progress_current': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'progress_total': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'cover': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'cover_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
            'review': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Cảm nhận, trích dẫn yêu thích...'}),
            'started_on': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'finished_on': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
        }

    def clean(self):
        cleaned = super().clean()
        current = cleaned.get('progress_current') or 0
        total = cleaned.get('progress_total') or 0
        if total and current > total:
            self.add_error('progress_current', 'Tiến độ hiện tại không được lớn hơn tổng.')
        return cleaned


class QuickAddForm(forms.ModelForm):
    """Form rút gọn trên trang kệ."""

    class Meta:
        model = MediaItem
        fields = ['media_type', 'title', 'creator', 'genre', 'status', 'progress_total', 'cover_url']
        widgets = {**MediaItemForm.Meta.widgets, 'genre': forms.HiddenInput()}


class LibraryGoalForm(forms.ModelForm):
    class Meta:
        model = LibraryGoal
        fields = ['media_type', 'target']
        widgets = {
            'media_type': forms.Select(attrs={'class': 'form-select'}),
            'target': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'placeholder': 'VD: 24'}),
        }
