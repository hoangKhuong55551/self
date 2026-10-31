"""
Middleware: Tự động kiểm tra subscription đến hạn
mỗi khi user truy cập trang (thay thế cron cho môi trường dev).
"""
from django.utils import timezone


class SubscriptionCheckMiddleware:
    """
    Kiểm tra và xử lý subscription đến hạn khi user đăng nhập.
    Chỉ chạy 1 lần/ngày/user (dùng session để track).
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            today_str = timezone.now().date().isoformat()
            session_key = f'sub_checked_{today_str}'

            if not request.session.get(session_key, False):
                from finance.models import Subscription
                from finance.services import charge_due_subscriptions

                charge_due_subscriptions(Subscription.objects.filter(user=request.user))
                request.session[session_key] = True

        return self.get_response(request)
