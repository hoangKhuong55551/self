"""View phục vụ bản chạy online: ảnh lưu trong database và đường link cho máy hẹn giờ (cron)."""
from django.conf import settings
from django.http import Http404, HttpResponse, JsonResponse
from django.utils.crypto import constant_time_compare
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from .models import StoredFile


@require_GET
def db_media(request, name):
    """Ảnh công khai (avatar, bìa sách...) khi DJANGO_FILE_STORAGE=db. Ảnh riêng tư không bao giờ trả ở đây."""
    row = StoredFile.objects.filter(name=name, is_private=False).first()
    if row is None:
        raise Http404
    response = HttpResponse(bytes(row.content), content_type=row.content_type)
    response['Cache-Control'] = 'public, max-age=86400'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@csrf_exempt
@never_cache
def cron_run(request, secret):
    """
    Máy hẹn giờ (GitHub Actions, cron-job.org...) gọi vào đây: gửi nhắc việc và trừ/cộng tiền
    khoản định kỳ đến hạn. Khoá sai hoặc chưa đặt DJANGO_CRON_SECRET thì trả 404 như không tồn tại.
    """
    expected = settings.CRON_SECRET
    if len(expected) < 20 or not constant_time_compare(secret, expected):
        raise Http404
    if request.method not in ('GET', 'POST'):
        return HttpResponse(status=405)

    from finance.models import Subscription
    from finance.services import charge_due_subscriptions

    from .push import is_configured
    from .reminders import send_due_reminders

    charged = charge_due_subscriptions(Subscription.objects.all())
    reminders = send_due_reminders() if is_configured() else 0
    return JsonResponse({'ok': True, 'charged': charged, 'reminders': reminders})
