def admin_context(request):
    """
    Makes admin_profile and is_super available in every admin template
    automatically — no need to pass them from each view.
    """
    if not request.user.is_authenticated:
        return {}
    return {
        'admin_profile': getattr(request.user, 'admin_profile', None),
        'is_super':      request.user.is_superuser,
    }