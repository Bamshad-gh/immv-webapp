# admin_panel/decorators.py
# ─────────────────────────────────────────────────────────────
# Three decorators that cover all admin access scenarios:
#   @admin_required                    — is_staff + AdminProfile exists
#                                        superusers bypass AdminProfile check
#   @superadmin_required               — is_superuser only
#   @admin_permission_required('...')  — admin + specific permission
#                                        superusers bypass permission check
#
# Why superusers bypass AdminProfile:
#   Superusers are created via createsuperuser command — they have no
#   AdminProfile by default. Requiring one would lock them out immediately.
#   Superusers have full access by definition — no profile needed.
#
# EXPAND: add new decorators for new access tiers if needed.
# ─────────────────────────────────────────────────────────────

from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def admin_required(view_func):
    """
    Gate for any admin panel view.

    Access granted if ANY of these are true:
      1. is_superuser=True         → full access, no AdminProfile needed
      2. is_staff=True + AdminProfile exists → configured staff admin

    Blocked if:
      - not authenticated          → redirect to login
      - not is_staff               → redirect to login
      - is_staff but no AdminProfile → redirect to login with message
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('admin_panel:admin_login')

        # Superusers always get through — no AdminProfile needed
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)

        if not request.user.is_staff:
            messages.error(request, 'Staff access required.')
            return redirect('admin_panel:admin_login')

        if not hasattr(request.user, 'admin_profile'):
            messages.error(request, 'Admin profile not configured. Contact a superadmin.')
            return redirect('admin_panel:admin_login')

        return view_func(request, *args, **kwargs)
    return wrapper


def superadmin_required(view_func):
    """
    Gate for superadmin-only views (e.g., managing other admins).
    Requires: is_superuser=True.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_superuser:
            messages.error(request, 'Superadmin access required.')
            return redirect('admin_panel:admin_login')
        return view_func(request, *args, **kwargs)
    return wrapper


def admin_permission_required(permission_name):
    """
    Gate for views that require a specific AdminProfile permission.
    Superusers bypass the permission check — they have full access.

    Usage:
        @admin_permission_required('can_create_groups')
        def my_view(request): ...

    EXPAND: add new boolean to AdminProfile, then use this decorator
    on the corresponding view — no other changes needed.
    """
    def decorator(view_func):
        @wraps(view_func)
        @admin_required  # runs admin_required first
        def wrapper(request, *args, **kwargs):
            # Superusers bypass permission checks
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            has_permission = getattr(request.user.admin_profile, permission_name, False)
            if not has_permission:
                messages.error(request, 'You do not have permission to do this.')
                return redirect('admin_panel:admin_dashboard')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator