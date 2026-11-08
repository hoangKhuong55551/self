from django import forms
from django.db import models
from .models import ClassSession, Semester, Course, Tag, Note, CodeSnippet

class SemesterForm(forms.ModelForm):
    class Meta:
        model = Semester
        fields = ['name', 'year', 'term', 'is_current', 'start_date', 'end_date']
        labels = {'name': 'Tên học kỳ', 'year': 'Năm học', 'term': 'Kỳ', 'is_current': 'Đặt làm kỳ hiện tại',
                  'start_date': 'Ngày bắt đầu học (tuỳ chọn)', 'end_date': 'Ngày kết thúc (tuỳ chọn)'}
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ví dụ: Học kỳ 1 (2025 - 2026)'}),
            'year': forms.NumberInput(attrs={'class': 'form-control', 'min': 2020, 'max': 2035}),
            'term': forms.Select(attrs={'class': 'form-select'}),
            'is_current': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        # Ràng buộc unique (user, year, term) không được form tự kiểm vì 'user' không nằm trong fields
        cleaned = super().clean()
        start, end = cleaned.get('start_date'), cleaned.get('end_date')
        if start and end and end < start:
            self.add_error('end_date', 'Ngày kết thúc phải sau ngày bắt đầu.')
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
        labels = {
            'semester': 'Thuộc học kỳ', 'name': 'Tên môn học', 'code': 'Mã môn', 'credits': 'Số tín chỉ',
            'grade': 'Điểm (thang 4)', 'is_completed': 'Đã hoàn thành',
        }
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


class TaggedForm(forms.ModelForm):
    """Thêm ô 'Tag mới' (cách nhau bởi dấu phẩy): tạo tag nếu chưa có rồi gắn vào bản ghi."""
    new_tags = forms.CharField(
        required=False, label='Tag mới',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'VD: django, thuat-toan (cách nhau bởi dấu phẩy)'}),
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['tags'].queryset = Tag.objects.filter(user=self.user)
        self.fields['tags'].required = False

    def clean_new_tags(self):
        names = []
        for raw in self.cleaned_data.get('new_tags', '').split(','):
            name = raw.strip()[:50]
            if name and name.casefold() not in {n.casefold() for n in names}:
                names.append(name)
        return names

    def _save_m2m(self):
        super()._save_m2m()
        if not self.user:
            return
        existing = {t.name.casefold(): t for t in Tag.objects.filter(user=self.user)}
        for name in self.cleaned_data.get('new_tags', []):
            tag = existing.get(name.casefold()) or Tag.objects.create(user=self.user, name=name)
            self.instance.tags.add(tag)


class NoteForm(TaggedForm):
    class Meta:
        model = Note
        fields = ['title', 'content', 'tags', 'is_pinned', 'is_archived']
        labels = {
            'title': 'Tiêu đề', 'content': 'Nội dung (Markdown)', 'tags': 'Tag',
            'is_pinned': 'Ghim lên đầu', 'is_archived': 'Lưu trữ (ẩn khỏi danh sách)',
        }
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tiêu đề ghi chú...'}),
            'content': forms.Textarea(attrs={'class': 'form-control font-monospace', 'rows': 12, 'placeholder': '# Viết ghi chú bằng Markdown ở đây...'}),
            'tags': forms.SelectMultiple(attrs={'class': 'form-select', 'size': '4'}),
            'is_pinned': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_archived': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class CodeSnippetForm(TaggedForm):
    class Meta:
        model = CodeSnippet
        fields = ['title', 'language', 'code', 'description', 'tags']
        labels = {'title': 'Tên đoạn code', 'language': 'Ngôn ngữ', 'code': 'Mã nguồn', 'description': 'Mô tả', 'tags': 'Tag'}
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên đoạn code (VD: Thuật toán Dijkstra, Django Signal Handler)'}),
            'language': forms.Select(attrs={'class': 'form-select'}),
            'code': forms.Textarea(attrs={'class': 'form-control font-monospace', 'rows': 12, 'placeholder': 'Dán mã nguồn vào đây...'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Mô tả công dụng hoặc cách dùng...'}),
            'tags': forms.SelectMultiple(attrs={'class': 'form-select', 'size': '4'}),
        }


class ClassSessionForm(forms.ModelForm):
    class Meta:
        model = ClassSession
        fields = ['course', 'weekday', 'start_time', 'end_time', 'room', 'note']
        labels = {'course': 'Môn học', 'weekday': 'Thứ', 'start_time': 'Bắt đầu', 'end_time': 'Kết thúc',
                  'room': 'Phòng', 'note': 'Ghi chú'}
        widgets = {
            'course': forms.Select(attrs={'class': 'form-select'}),
            'weekday': forms.Select(attrs={'class': 'form-select'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}, format='%H:%M'),
            'end_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}, format='%H:%M'),
            'room': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'A2-301'}),
            'note': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Lý thuyết / Thực hành...'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            # Môn chưa hoàn thành, ưu tiên học kỳ hiện tại
            self.fields['course'].queryset = Course.objects.filter(semester__user=user).filter(
                models.Q(is_completed=False) | models.Q(pk=self.instance.course_id)
            ).select_related('semester').order_by('-semester__is_current', '-semester__year', 'name')

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get('start_time'), cleaned.get('end_time')
        if start and end and end <= start:
            self.add_error('end_time', 'Giờ kết thúc phải sau giờ bắt đầu.')
        return cleaned
