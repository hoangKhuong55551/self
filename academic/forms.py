from django import forms
from .models import Semester, Course, Tag, Note, CodeSnippet

class SemesterForm(forms.ModelForm):
    class Meta:
        model = Semester
        fields = ['name', 'year', 'term', 'is_current']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ví dụ: Học kỳ 1 (2025 - 2026)'}),
            'year': forms.NumberInput(attrs={'class': 'form-control', 'min': 2020, 'max': 2035}),
            'term': forms.Select(attrs={'class': 'form-select'}),
            'is_current': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        # Ràng buộc unique (user, year, term) không được form tự kiểm vì 'user' không nằm trong fields
        cleaned = super().clean()
        exists = self.user and Semester.objects.filter(
            user=self.user, year=cleaned.get('year'), term=cleaned.get('term')
        ).exclude(pk=self.instance.pk).exists()
        if exists:
            raise forms.ValidationError("Bạn đã có học kỳ này trong năm đã chọn.")
        return cleaned


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['semester', 'name', 'code', 'credits', 'grade', 'is_completed']
        widgets = {
            'semester': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên môn học...'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Mã môn (VD: IT001)'}),
            'credits': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 10}),
            'grade': forms.Select(attrs={'class': 'form-select'}),
            'is_completed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['semester'].queryset = Semester.objects.filter(user=user)


class TagForm(forms.ModelForm):
    class Meta:
        model = Tag
        fields = ['name', 'color']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên nhãn (tag)'}),
            'color': forms.TextInput(attrs={'class': 'form-control form-control-color', 'type': 'color'}),
        }


class NoteForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = ['title', 'content', 'tags', 'is_pinned']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tiêu đề ghi chú...'}),
            'content': forms.Textarea(attrs={'class': 'form-control font-monospace', 'rows': 12, 'placeholder': '# Viết ghi chú bằng Markdown ở đây...'}),
            'tags': forms.SelectMultiple(attrs={'class': 'form-select', 'size': '4'}),
            'is_pinned': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['tags'].queryset = Tag.objects.filter(user=user)


class CodeSnippetForm(forms.ModelForm):
    class Meta:
        model = CodeSnippet
        fields = ['title', 'language', 'code', 'description', 'tags']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên đoạn code (VD: Thuật toán Dijkstra, Django Signal Handler)'}),
            'language': forms.Select(attrs={'class': 'form-select'}),
            'code': forms.Textarea(attrs={'class': 'form-control font-monospace', 'rows': 12, 'placeholder': 'Dán mã nguồn vào đây...'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Mô tả công dụng hoặc cách dùng...'}),
            'tags': forms.SelectMultiple(attrs={'class': 'form-select', 'size': '4'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['tags'].queryset = Tag.objects.filter(user=user)
