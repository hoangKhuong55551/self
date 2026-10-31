from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, F, FloatField, ExpressionWrapper, Q

from .models import Semester, Course, Tag, Note, CodeSnippet
from .forms import SemesterForm, CourseForm, NoteForm, CodeSnippetForm


@login_required
def academic_dashboard(request):
    """Trang chủ phân hệ Học tập & Second Brain."""
    semesters = Semester.objects.filter(user=request.user).prefetch_related('courses')
    current_sem = semesters.filter(is_current=True).first()

    # Tính cGPA (Cumulative GPA - Điểm trung bình tích lũy toàn khóa)
    all_completed_courses = Course.objects.filter(
        semester__user=request.user,
        is_completed=True,
        grade__isnull=False
    )
    res = all_completed_courses.aggregate(
        weighted_sum=Sum(ExpressionWrapper(F('grade') * F('credits'), output_field=FloatField())),
        total_credits=Sum('credits')
    )
    weighted = res['weighted_sum'] or 0.0
    total_credits = res['total_credits'] or 0
    cgpa = round(weighted / total_credits, 2) if total_credits > 0 else 0.0

    recent_notes = Note.objects.filter(user=request.user)[:5]
    recent_snippets = CodeSnippet.objects.filter(user=request.user)[:5]

    context = {
        'semesters': semesters,
        'current_sem': current_sem,
        'cgpa': cgpa,
        'total_credits': total_credits,
        'recent_notes': recent_notes,
        'recent_snippets': recent_snippets,
    }
    return render(request, 'academic/dashboard.html', context)


# --- GPA TRACKER & SIMULATOR ---
@login_required
def gpa_tracker(request):
    semesters = Semester.objects.filter(user=request.user).prefetch_related('courses')
    sem_form = SemesterForm(user=request.user)
    course_form = CourseForm(user=request.user)

    if request.method == 'POST':
        # Form không hợp lệ được giữ lại để hiển thị lỗi
        if 'add_semester' in request.POST:
            form = sem_form = SemesterForm(request.POST, user=request.user)
            if form.is_valid():
                sem = form.save(commit=False)
                sem.user = request.user
                if sem.is_current:
                    Semester.objects.filter(user=request.user).update(is_current=False)
                sem.save()
                messages.success(request, f"Đã thêm học kỳ: {sem.name}")
                return redirect('academic:gpa_tracker')
        elif 'add_course' in request.POST:
            cform = course_form = CourseForm(request.POST, user=request.user)
            if cform.is_valid():
                course = cform.save()
                messages.success(request, f"Đã thêm môn học: {course.name}")
                return redirect('academic:gpa_tracker')
        messages.error(request, "Vui lòng kiểm tra lại thông tin đã nhập.")

    return render(request, 'academic/gpa_tracker.html', {
        'semesters': semesters,
        'sem_form': sem_form,
        'course_form': course_form,
    })


@login_required
def gpa_simulator(request):
    """Mô phỏng điểm GPA cần đạt cho các học kỳ tương lai để đạt mục tiêu."""
    all_completed = Course.objects.filter(
        semester__user=request.user, is_completed=True, grade__isnull=False
    )
    res = all_completed.aggregate(
        weighted_sum=Sum(ExpressionWrapper(F('grade') * F('credits'), output_field=FloatField())),
        total_credits=Sum('credits')
    )
    current_weighted = res['weighted_sum'] or 0.0
    current_credits = res['total_credits'] or 0
    current_cgpa = round(current_weighted / current_credits, 2) if current_credits > 0 else 0.0

    target_gpa = None
    remaining_credits = None
    required_gpa = None
    possible = True

    if request.method == 'GET' and 'target_gpa' in request.GET:
        try:
            target_gpa = float(request.GET.get('target_gpa'))
            remaining_credits = int(request.GET.get('remaining_credits'))
            total_future_credits = current_credits + remaining_credits

            # Target = (current_weighted + required_gpa * remaining_credits) / total_future_credits
            # => required_gpa = (Target * total_future_credits - current_weighted) / remaining_credits
            if remaining_credits > 0 and 0 < target_gpa <= 4.0:
                required = (target_gpa * total_future_credits - current_weighted) / remaining_credits
                # Âm nghĩa là đã chắc chắn đạt mục tiêu dù các môn còn lại điểm 0
                required_gpa = max(round(required, 2), 0)
                if required_gpa > 4.0:
                    possible = False
        except (ValueError, TypeError):
            pass

    return render(request, 'academic/gpa_simulator.html', {
        'current_cgpa': current_cgpa,
        'current_credits': current_credits,
        'target_gpa': target_gpa,
        'remaining_credits': remaining_credits,
        'required_gpa': required_gpa,
        'possible': possible,
    })


# --- SECOND BRAIN: NOTES (MARKDOWN) ---
@login_required
def note_list(request):
    query = request.GET.get('q', '')
    tag_id = request.GET.get('tag')

    notes = Note.objects.filter(user=request.user).prefetch_related('tags')
    if query:
        notes = notes.filter(Q(title__icontains=query) | Q(content__icontains=query))
    if tag_id and tag_id.isdigit():
        notes = notes.filter(tags__id=tag_id)

    tags = Tag.objects.filter(user=request.user)

    if request.method == 'POST':
        form = NoteForm(request.POST, user=request.user)
        if form.is_valid():
            note = form.save(commit=False)
            note.user = request.user
            note.save()
            form.save_m2m()
            messages.success(request, f"Đã lưu ghi chú: {note.title}")
            return redirect('academic:note_list')
    else:
        form = NoteForm(user=request.user)

    return render(request, 'academic/note_list.html', {
        'notes': notes,
        'tags': tags,
        'form': form,
        'query': query,
    })


@login_required
def note_detail(request, pk):
    note = get_object_or_404(Note, pk=pk, user=request.user)
    return render(request, 'academic/note_detail.html', {'note': note})


# --- SECOND BRAIN: CODE SNIPPETS ---
@login_required
def snippet_list(request):
    query = request.GET.get('q', '')
    lang = request.GET.get('lang', '')

    snippets = CodeSnippet.objects.filter(user=request.user).prefetch_related('tags')
    if query:
        snippets = snippets.filter(Q(title__icontains=query) | Q(code__icontains=query) | Q(description__icontains=query))
    if lang:
        snippets = snippets.filter(language=lang)

    if request.method == 'POST':
        form = CodeSnippetForm(request.POST, user=request.user)
        if form.is_valid():
            snippet = form.save(commit=False)
            snippet.user = request.user
            snippet.save()
            form.save_m2m()
            messages.success(request, f"Đã lưu đoạn code: {snippet.title}")
            return redirect('academic:snippet_list')
    else:
        form = CodeSnippetForm(user=request.user)

    return render(request, 'academic/snippet_list.html', {
        'snippets': snippets,
        'form': form,
        'query': query,
        'languages': CodeSnippet.LANGUAGE_CHOICES,
        'selected_lang': lang,
    })


@login_required
def snippet_detail(request, pk):
    snippet = get_object_or_404(CodeSnippet, pk=pk, user=request.user)
    return render(request, 'academic/snippet_detail.html', {'snippet': snippet})
