from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .services import get_weekly_dashboard

@login_required
def dashboard(request):
    """View hiển thị dashboard tổng hợp tuần."""
    context = get_weekly_dashboard(request.user)
    return render(request, 'core/dashboard.html', context)
