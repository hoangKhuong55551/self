from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .services import get_weekly_dashboard
from .forms import RegisterForm

@login_required
def dashboard(request):
    """View hiển thị dashboard tổng hợp tuần."""
    context = get_weekly_dashboard(request.user)
    return render(request, 'core/dashboard.html', context)

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
