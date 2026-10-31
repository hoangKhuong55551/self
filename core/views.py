from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, Http404
from django.utils import timezone
from datetime import date, timedelta
from .services import get_weekly_dashboard, global_search, get_week_review
from .achievements import evaluate_achievements
from .exports import CSV_EXPORTS, export_csv, export_json
from .models import XPEvent, WeeklyReflection
from .forms import RegisterForm, WeeklyReflectionForm

@login_required
def dashboard(request):
    """View hiển thị dashboard tổng hợp tuần."""
    _announce_new_achievements(request)
    context = get_weekly_dashboard(request.user)
    return render(request, 'core/dashboard.html', context)


def _announce_new_achievements(request):
    _, newly_unlocked = evaluate_achievements(request.user)
    for ach in newly_unlocked:
        bonus = f" +{ach.xp} XP" if ach.xp else ""
        messages.success(request, f"🏅 Mở khoá huy hiệu: {ach.title}!{bonus}")


@login_required
def achievements_view(request):
    """Trang huy hiệu thành tích + lịch sử XP."""
    progress, newly_unlocked = evaluate_achievements(request.user)
    for ach in newly_unlocked:
        messages.success(request, f"🏅 Mở khoá huy hiệu: {ach.title}!")

    unlocked_count = sum(1 for p in progress if p['unlocked_at'])
    return render(request, 'core/achievements.html', {
        'progress': progress,
        'unlocked_count': unlocked_count,
        'total_count': len(progress),
        'xp_events': XPEvent.objects.filter(user=request.user).exclude(amount=0)[:30],
    })

@login_required
def search_api(request):
    """API JSON cho thanh tìm kiếm nhanh Ctrl+K."""
    return JsonResponse({'results': global_search(request.user, request.GET.get('q', ''))})

@login_required
def weekly_review(request):
    """Tổng kết tuần: số liệu cả hệ thống + ô suy ngẫm cuối tuần."""
    today = timezone.localdate()
    this_monday = today - timedelta(days=today.weekday())
    try:
        picked = date.fromisoformat(request.GET.get('week', ''))
        week_start = picked - timedelta(days=picked.weekday())
    except ValueError:
        week_start = this_monday
    week_start = min(week_start, this_monday)

    reflection = WeeklyReflection.objects.filter(user=request.user, week_start=week_start).first()
    if request.method == 'POST':
        form = WeeklyReflectionForm(request.POST, instance=reflection)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.user = request.user
            obj.week_start = week_start
            obj.save()
            messages.success(request, "Đã lưu suy ngẫm tuần này ✍️")
            return redirect(f"{request.path}?week={week_start.isoformat()}")
    else:
        form = WeeklyReflectionForm(instance=reflection)

    context = get_week_review(request.user, week_start)
    context.update({
        'form': form,
        'prev_week': week_start - timedelta(days=7),
        'next_week': week_start + timedelta(days=7) if week_start < this_monday else None,
        'is_current_week': week_start == this_monday,
    })
    return render(request, 'core/weekly_review.html', context)

@login_required
def export_page(request):
    """Trang sao lưu: tải JSON đầy đủ hoặc CSV từng phân hệ."""
    return render(request, 'core/export.html', {
        'csv_exports': [(key, label, icon) for key, (label, icon, _) in CSV_EXPORTS.items()],
    })


@login_required
def export_download(request, kind):
    stamp = timezone.localdate().strftime('%Y%m%d')
    if kind == 'json':
        response = HttpResponse(export_json(request.user), content_type='application/json; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="lifeos-backup-{stamp}.json"'
        return response
    if kind not in CSV_EXPORTS:
        raise Http404
    response = HttpResponse(export_csv(request.user, kind), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="lifeos-{kind}-{stamp}.csv"'
    return response


def service_worker(request):
    """Service worker phải được phục vụ ở gốc site để có scope '/'."""
    response = render(request, 'sw.js', content_type='application/javascript')
    response['Cache-Control'] = 'no-cache'
    return response


def offline_page(request):
    return render(request, 'offline.html')


def register_view(request):
    """Đăng ký tài khoản người dùng mới."""
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Chào mừng {user.username} đến với Life OS! Hành trình của bạn bắt đầu từ hôm nay.")
            return redirect('core:dashboard')
    else:
        form = RegisterForm()

    return render(request, 'registration/register.html', {'form': form})
