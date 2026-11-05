"""
Middleware: Tự động kiểm tra subscription đến hạn khi user truy cập trang
(thay thế cron cho môi trường dev hoặc server không có cron).

Khi deploy có cron, đặt DJANGO_CHARGE_SUBSCRIPTIONS_ON_REQUEST=False và chạy định kỳ:
    python manage.py process_subscriptions
"""
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone


class SubscriptionCheckMiddleware:
    """
    Xử lý subscription đến hạn tối đa 1 lần/ngày/user.
    Đánh dấu theo user (cache) chứ không theo session, nên đăng nhập trên nhiều thiết bị
    cũng không chạy lặp; kể cả khi chạy trùng, charge_due_subscriptions vẫn không trừ tiền hai lần.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.CHARGE_SUBSCRIPTIONS_ON_REQUEST and request.user.is_authenticated:
            today = timezone.localdate().isoformat()
            session_key = f'sub_checked_{today}'
            # Session: không chạy lại trong cùng phiên. Cache.add: chỉ trả True cho request đầu tiên
            # trong ngày của user này, kể cả khi đăng nhập ở thiết bị khác.
            if not request.session.get(session_key):
                request.session[session_key] = True
                if cache.add(f'sub_checked:{request.user.pk}:{today}', True, 60 * 60 * 24):
                    from finance.models import Subscription
                    from finance.services import charge_due_subscriptions

                    charge_due_subscriptions(Subscription.objects.filter(user=request.user))

        return self.get_response(request)
