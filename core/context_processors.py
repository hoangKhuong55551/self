def user_profile_context(request):
    """Inject user profile vào mọi template để dùng {{ profile.xp }}, {{ profile.level }}..."""
    if request.user.is_authenticated:
        try:
            return {'profile': request.user.profile}
        except Exception:
            return {'profile': None}
    return {'profile': None}
