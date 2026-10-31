from django import forms
from .models import Goal, Task, Habit

class GoalForm(forms.ModelForm):
    class Meta:
        model = Goal
        fields = ['title', 'description', 'status', 'deadline', 'color']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ví dụ: Đạt chứng chỉ IELTS 7.0, Hoàn thành đồ án Web...'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Mô tả chi tiết mục tiêu...'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'deadline': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'color': forms.TextInput(attrs={'class': 'form-control form-control-color', 'type': 'color'}),
        }


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['goal', 'title', 'description', 'status', 'quadrant', 'due_date', 'estimated_pomodoros']
        widgets = {
            'goal': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên đầu việc cần làm...'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Ghi chú công việc...'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'quadrant': forms.Select(attrs={'class': 'form-select'}),
            'due_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'estimated_pomodoros': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 20}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['goal'].queryset = Goal.objects.filter(user=user)


class HabitForm(forms.ModelForm):
    class Meta:
        model = Habit
        fields = ['name', 'description', 'frequency', 'target_per_day', 'icon', 'color']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ví dụ: Đọc sách 30p, Chạy bộ 3km, Code LeetCode...'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'frequency': forms.Select(attrs={'class': 'form-select'}),
            'target_per_day': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'icon': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Emoji hoặc tên icon: 🏃, 📚, 💻'}),
            'color': forms.TextInput(attrs={'class': 'form-control form-control-color', 'type': 'color'}),
        }
