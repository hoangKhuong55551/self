from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, Http404
from django.urls import reverse
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
    from academic.services_schedule import sessions_on

    context = get_weekly_dashboard(request.user)
    context['today_classes'] = sessions_on(request.user, timezone.localdate())
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
    if not settings.ALLOW_REGISTRATION:
        raise Http404('Đăng ký đã bị tắt')
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, f"Chào mừng {user.username} đến với Life OS! Hành trình của bạn bắt đầu từ hôm nay.")
            return redirect('core:dashboard')
    else:
        form = RegisterForm()

    return render(request, 'registration/register.html', {'form': form})


@login_required
def quick_add(request):
    """Thêm nhanh từ Ctrl+K. GET ?q= : xem trước (không ghi). POST q= : lưu."""
    from . import quick_add as qa

    text = (request.POST.get('q') if request.method == 'POST' else request.GET.get('q')) or ''
    parsed = qa.parse(request.user, text[:300])
    if parsed is None:
        return JsonResponse({'match': False})
    if request.method != 'POST' or not parsed['ok']:
        return JsonResponse({
            'match': True, 'ok': parsed['ok'], 'kind': parsed['kind'],
            'title': parsed.get('title') or parsed.get('error'),
            'subtitle': parsed.get('subtitle', ''),
        }, status=200 if parsed['ok'] or request.method != 'POST' else 400)
    message, url = qa.commit(request.user, parsed)
    return JsonResponse({'match': True, 'ok': True, 'message': message, 'url': url})


@login_required
def calendar_view(request):
    """Lịch tháng gom hạn task, mục tiêu, khoản định kỳ, khoản nợ, quỹ tiết kiệm."""
    from .calendar import build_month

    today = timezone.localdate()
    try:
        year, month = (int(x) for x in request.GET.get('m', '').split('-'))
        date(year, month, 1)
        if not 1900 <= year <= 2200:  # tránh tràn ngày khi tính lưới tuần / tháng trước-sau
            raise ValueError
    except (ValueError, TypeError):
        year, month = today.year, today.month
    data = build_month(request.user, year, month, today)
    first = data['first']
    prev_month = (first - timedelta(days=1)).replace(day=1)
    next_month = (data['last'] + timedelta(days=1))
    token = getattr(getattr(request.user, 'profile', None), 'calendar_token', '')
    feed_url = request.build_absolute_uri(reverse('core:calendar_feed', args=[token])) if token else ''
    return render(request, 'core/calendar.html', {
        **data, 'today': today, 'feed_url': feed_url,
        'webcal_url': feed_url.replace('https://', 'webcal://').replace('http://', 'webcal://'),
        'prev_m': f'{prev_month:%Y-%m}', 'next_m': f'{next_month:%Y-%m}', 'this_m': f'{today:%Y-%m}',
        'weekday_names': ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN'],
    })


def calendar_feed(request, token):
    """File .ics cho ứng dụng lịch (không đăng nhập được nên xác thực bằng token bí mật trong link)."""
    from .ics import build_ics
    from .models import UserProfile

    if len(token) < 20:
        raise Http404
    profile = UserProfile.objects.filter(calendar_token=token).select_related('user').first()
    if not profile or not profile.user.is_active:
        raise Http404
    body = build_ics(profile.user, request.build_absolute_uri('/').rstrip('/'))
    response = HttpResponse(body, content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = 'inline; filename="lifeos.ics"'
    response['Cache-Control'] = 'private, max-age=900'
    return response


@login_required
def calendar_token_reset(request):
    """Tạo link lịch mới (link cũ hết hiệu lực ngay), hoặc tắt hẳn."""
    from .ics import new_token
    from .models import UserProfile

    if request.method != 'POST':
        return redirect('core:calendar')
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.POST.get('action') == 'disable':
        profile.calendar_token = ''
        messages.success(request, "Đã tắt link lịch. Ứng dụng lịch đang đăng ký sẽ không cập nhật nữa.")
    else:
        had = bool(profile.calendar_token)
        profile.calendar_token = new_token()
        messages.success(request, "Đã tạo link lịch mới." + (" Link cũ không còn dùng được." if had else ""))
    profile.save(update_fields=['calendar_token'])
    return redirect('core:calendar')


@login_required
def restore_backup(request):
    """Khôi phục từ file JSON sao lưu (POST multipart: file, mode, confirm)."""
    from .restore import RestoreError, load_backup, restore

    if request.method != 'POST':
        return redirect('core:export')
    upload = request.FILES.get('file')
    mode = request.POST.get('mode', 'merge')
    if not upload:
        messages.error(request, "Chọn file sao lưu (.json) trước.")
        return redirect('core:export')
    if mode == 'replace' and request.POST.get('confirm', '').strip().upper() != 'KHOI PHUC':
        messages.error(request, 'Chế độ thay thế sẽ xoá dữ liệu hiện tại: gõ "KHOI PHUC" để xác nhận.')
        return redirect('core:export')
    try:
        counts = restore(request.user, load_backup(upload), mode)
    except RestoreError as e:
        messages.error(request, str(e))
        return redirect('core:export')
    total = sum(counts.values())
    verb = 'Đã khôi phục' if mode == 'replace' else 'Đã thêm'
    messages.success(request, f"{verb} {total} bản ghi từ bản sao lưu. Số dư các ví đã được tính lại.")
    return redirect('core:export')


# --- THÔNG BÁO ĐẨY ---
@login_required
def push_subscribe(request):
    """Lưu đăng ký Web Push của trình duyệt (POST JSON: endpoint, keys.p256dh, keys.auth)."""
    import json

    from .models import PushSubscription

    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)
    try:
        data = json.loads(request.body)
        endpoint, keys = data['endpoint'], data['keys']
        p256dh, auth = keys['p256dh'], keys['auth']
    except (ValueError, KeyError, TypeError):
        return JsonResponse({'ok': False, 'error': 'Dữ liệu đăng ký không hợp lệ'}, status=400)
    if not str(endpoint).startswith('https://') or len(endpoint) > 1000:
        return JsonResponse({'ok': False, 'error': 'Endpoint không hợp lệ'}, status=400)
    # Endpoint là duy nhất theo trình duyệt: đăng nhập tài khoản khác trên cùng máy thì chuyển chủ
    PushSubscription.objects.update_or_create(endpoint=endpoint, defaults={
        'user': request.user, 'p256dh': p256dh[:255], 'auth': auth[:255],
        'user_agent': request.META.get('HTTP_USER_AGENT', '')[:255],
    })
    return JsonResponse({'ok': True})


@login_required
def push_unsubscribe(request):
    import json

    from .models import PushSubscription

    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)
    try:
        endpoint = json.loads(request.body).get('endpoint', '')
    except ValueError:
        endpoint = ''
    PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
    return JsonResponse({'ok': True})


@login_required
def push_test(request):
    from .push import is_configured, send_push

    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)
    if not is_configured():
        return JsonResponse({'ok': False, 'error': 'Máy chủ chưa cấu hình khoá VAPID'}, status=503)
    n = send_push(request.user, '🔔 Life OS', 'Thông báo đã hoạt động trên thiết bị này!', '/', tag='test')
    return JsonResponse({'ok': n > 0, 'delivered': n})
