"""Gửi thông báo đẩy (Web Push, chuẩn VAPID) tới mọi thiết bị đã bật của một người dùng."""
import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def is_configured():
    return bool(settings.VAPID_PUBLIC_KEY and settings.VAPID_PRIVATE_KEY)


def send_push(user, title, body='', url='/', tag=''):
    """Trả về số thiết bị nhận thành công. Thiết bị đã huỷ đăng ký (404/410) bị xoá khỏi danh sách."""
    if not is_configured():
        return 0
    from pywebpush import WebPushException, webpush

    payload = json.dumps({'title': title, 'body': body, 'url': url, 'tag': tag}, ensure_ascii=False)
    delivered = 0
    for sub in user.push_subscriptions.all():
        try:
            webpush(
                subscription_info=sub.as_webpush(), data=payload, ttl=6 * 3600,
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={'sub': settings.VAPID_SUBJECT},
            )
            delivered += 1
        except WebPushException as exc:
            status = getattr(exc.response, 'status_code', None)
            if status in (404, 410):
                sub.delete()  # trình duyệt đã huỷ đăng ký / gỡ app
            else:
                logger.warning('Gửi push thất bại (%s): %s', status, exc)
        except Exception as exc:  # lỗi mạng...: một thiết bị lỗi không làm hỏng cả lượt
            logger.warning('Gửi push lỗi: %s', exc)
    return delivered
