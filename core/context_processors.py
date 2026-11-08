def user_profile_context(request):
    """Inject user profile vào mọi template để dùng {{ profile.xp }}, {{ profile.level }}..."""
    if request.user.is_authenticated:
        try:
            return {'profile': request.user.profile}
        except Exception:
            return {'profile': None}
    return {'profile': None}


def site_settings(request):
    from django.conf import settings
    return {'allow_registration': settings.ALLOW_REGISTRATION}


def notifications_context(request):
    """Nhắc hạn cho chuông trên topbar (xem core/notifications.py)."""
    if not request.user.is_authenticated:
        return {}

    from core.notifications import get_notifications

    from django.conf import settings

    items, total = get_notifications(request.user)
    return {'notifications': items, 'notification_count': total, 'vapid_public_key': settings.VAPID_PUBLIC_KEY}
