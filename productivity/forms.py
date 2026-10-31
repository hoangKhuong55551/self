from django import forms
from academic.models import Course
from .models import Goal, Task, Habit


def date_input():
    # type=date chỉ nhận YYYY-MM-DD; thiếu format thì form sửa sẽ hiện trống với locale 'vi'
    return forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d')


class GoalForm(forms.ModelForm):
    class Meta:
        model = Goal
        fields = ['title', 'description', 'status', 'deadline', 'color']
        labels = {'title': 'Tên mục tiêu', 'description': 'Mô tả', 'status': 'Trạng thái', 'deadline': 'Hạn chót', 'color': 'Màu'}
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ví dụ: Đạt chứng chỉ IELTS 7.0, Hoàn thành đồ án Web...'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Mô tả chi tiết mục tiêu...'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'deadline': date_input(),
            'color': forms.TextInput(attrs={'class': 'form-control form-control-color', 'type': 'color'}),
        }


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['goal', 'title', 'description', 'course', 'status', 'quadrant', 'due_date', 'estimated_pomodoros']
        labels = {
            'goal': 'Thuộc mục tiêu', 'title': 'Tên công việc', 'description': 'Mô tả', 'course': 'Môn học liên quan',
            'status': 'Trạng thái', 'quadrant': 'Ma trận Eisenhower', 'due_date': 'Hạn hoàn thành',
            'estimated_pomodoros': 'Dự kiến Pomodoro',
        }
        widgets = {
            'goal': forms.Select(attrs={'class': 'form-select'}),
            'course': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên đầu việc cần làm...'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Ghi chú công việc...'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'quadrant': forms.Select(attrs={'class': 'form-select'}),
            'due_date': date_input(),
            'estimated_pomodoros': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 20}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['goal'].queryset = Goal.objects.filter(user=user)
            self.fields['course'].queryset = Course.objects.filter(
                semester__user=user
            ).select_related('semester').order_by('-semester__year', 'name')
        self.fields['course'].empty_label = '— Không gắn môn học —'


class HabitForm(forms.ModelForm):
    class Meta:
        model = Habit
        fields = ['name', 'description', 'frequency', 'target_per_day', 'icon', 'color']
        labels = {
            'name': 'Tên thói quen', 'description': 'Mô tả', 'frequency': 'Tần suất',
            'target_per_day': 'Mục tiêu mỗi ngày', 'icon': 'Icon', 'color': 'Màu', 'is_active': 'Đang theo dõi',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ví dụ: Đọc sách 30p, Chạy bộ 3km, Code LeetCode...'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'frequency': forms.Select(attrs={'class': 'form-select'}),
            'target_per_day': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'icon': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Emoji hoặc tên icon: 🏃, 📚, 💻'}),
            'color': forms.TextInput(attrs={'class': 'form-control form-control-color', 'type': 'color'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class HabitEditForm(HabitForm):
    """Sửa thói quen: thêm tuỳ chọn tạm ngưng theo dõi (giữ nguyên lịch sử)."""
    class Meta(HabitForm.Meta):
        fields = HabitForm.Meta.fields + ['is_active']
