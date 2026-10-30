from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from django.db.models.functions import ExtractMonth
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import MediaItem, LibraryGoal
from .forms import MediaItemForm, QuickAddForm, LibraryGoalForm


@login_required
def library_shelf(request):
    """Kệ thư viện: lưới sách/phim/game, bộ lọc, mục tiêu năm và thống kê."""
    year = timezone.localdate().year
    items = MediaItem.objects.filter(user=request.user)

    if request.method == 'POST':
        if 'add_item' in request.POST:
            form = QuickAddForm(request.POST)
            if form.is_valid():
                item = form.save(commit=False)
                item.user = request.user
                item.save()
                messages.success(request, f"Đã thêm vào kệ: {item.title}")
                return redirect('library:shelf')
            messages.error(request, "Không thể thêm, vui lòng kiểm tra lại thông tin.")
        elif 'set_goal' in request.POST:
            goal_form = LibraryGoalForm(request.POST)
            if goal_form.is_valid():
                LibraryGoal.objects.update_or_create(
                    user=request.user, year=year,
                    media_type=goal_form.cleaned_data['media_type'],
                    defaults={'target': goal_form.cleaned_data['target']},
                )
                messages.success(request, f"Đã cập nhật mục tiêu năm {year}.")
                return redirect('library:shelf')
            messages.error(request, "Mục tiêu không hợp lệ.")

    # Bộ lọc
    media_type = request.GET.get('type', '')
    status = request.GET.get('status', '')
    query = request.GET.get('q', '').strip()

    shelf = items
    if media_type in MediaItem.MediaType.values:
        shelf = shelf.filter(media_type=media_type)
    if status in MediaItem.Status.values:
        shelf = shelf.filter(status=status)
    if query:
        shelf = shelf.filter(Q(title__icontains=query) | Q(creator__icontains=query) | Q(genre__icontains=query))

    status_counts = dict(
        items.values_list('status').annotate(n=Count('id')).values_list('status', 'n')
    )

    # Mục tiêu năm + số đã xong trong năm theo loại
    done_this_year = items.filter(status=MediaItem.Status.DONE, finished_on__year=year)
    done_by_type = dict(done_this_year.values_list('media_type').annotate(n=Count('id')).values_list('media_type', 'n'))
    goals = []
    for goal in LibraryGoal.objects.filter(user=request.user, year=year):
        done = done_by_type.get(goal.media_type, 0)
        goals.append({
            'goal': goal,
            'done': done,
            'percent': min(round(done / goal.target * 100), 100),
        })

    # Biểu đồ số mục hoàn thành theo tháng, tách theo loại
    monthly = done_this_year.annotate(m=ExtractMonth('finished_on')).values('m', 'media_type').annotate(n=Count('id'))
    chart = {t: [0] * 12 for t in MediaItem.MediaType.values}
    for row in monthly:
        chart[row['media_type']][row['m'] - 1] = row['n']

    context = {
        'shelf': shelf,
        'currently': items.filter(status=MediaItem.Status.IN_PROGRESS)[:6],
        'status_counts': status_counts,
        'total_count': sum(status_counts.values()),
        'done_year_count': sum(done_by_type.values()),
        'goals': goals,
        'chart_data': chart,
        'year': year,
        'media_types': MediaItem.MediaType.choices,
        'statuses': MediaItem.Status.choices,
        'selected_type': media_type,
        'selected_status': status,
        'query': query,
        'add_form': QuickAddForm(),
        'goal_form': LibraryGoalForm(),
    }
    return render(request, 'library/shelf.html', context)


@login_required
def item_detail(request, pk):
    item = get_object_or_404(MediaItem, pk=pk, user=request.user)

    if request.method == 'POST':
        form = MediaItemForm(request.POST, request.FILES, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, f"Đã lưu thay đổi cho: {item.title}")
            return redirect('library:item_detail', pk=item.pk)
    else:
        form = MediaItemForm(instance=item)

    return render(request, 'library/item_detail.html', {'item': item, 'form': form})


@login_required
@require_POST
def item_quick_update(request, pk):
    """Đổi trạng thái hoặc cộng tiến độ nhanh từ thẻ trên kệ."""
    item = get_object_or_404(MediaItem, pk=pk, user=request.user)
    action = request.POST.get('action')

    status_actions = {
        'start': MediaItem.Status.IN_PROGRESS,
        'done': MediaItem.Status.DONE,
        'drop': MediaItem.Status.DROPPED,
        'want': MediaItem.Status.WANT,
    }

    if action in status_actions:
        item.status = status_actions[action]
        item.save()
        if action == 'done':
            messages.success(request, f"🎉 Hoàn thành {item.title}! XP đã được cộng.")
    elif action == 'progress':
        try:
            step = int(request.POST.get('step', 1))
        except ValueError:
            step = 1
        item.progress_current = max(item.progress_current + step, 0)
        if item.progress_total:
            item.progress_current = min(item.progress_current, item.progress_total)
        if item.status == MediaItem.Status.WANT:
            item.status = MediaItem.Status.IN_PROGRESS
        if item.progress_total and item.progress_current >= item.progress_total:
            item.status = MediaItem.Status.DONE
            messages.success(request, f"🎉 Hoàn thành {item.title}! XP đã được cộng.")
        item.save()

    next_url = request.POST.get('next')
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect('library:shelf')


@login_required
@require_POST
def item_delete(request, pk):
    item = get_object_or_404(MediaItem, pk=pk, user=request.user)
    title = item.title
    item.delete()
    messages.success(request, f"Đã xoá khỏi kệ: {title}")
    return redirect('library:shelf')
