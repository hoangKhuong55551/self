def user_profile_context(request):
    """Inject user profile vào mọi template để dùng {{ profile.xp }}, {{ profile.level }}..."""
    if request.user.is_authenticated:
        try:
            return {'profile': request.user.profile}
        except Exception:
            return {'profile': None}
    return {'profile': None}


def notifications_context(request):
    """Nhắc hạn cho chuông trên topbar (xem core/notifications.py)."""
    if not request.user.is_authenticated:
        return {}

    from core.notifications import get_notifications

    items, total = get_notifications(request.user)
    return {'notifications': items, 'notification_count': total}
