# groups/urls.py
# ─────────────────────────────────────────────────────────────
# app_name = 'groups' enables namespacing.
# Always reference these as 'groups:url_name' — never just 'url_name'.
# This prevents clashes if another app has a URL with the same name.
#
# Usage in templates:  {% url 'groups:group_dashboard' %}
# Usage in views:      redirect('groups:group_detail', group_id=group.id)
# ─────────────────────────────────────────────────────────────

from django.urls import path
from . import views

app_name = 'groups'

urlpatterns = [

    # ── Dashboard — list all groups user belongs to ───────────
    path(
        '',
        views.group_dashboard,
        name='group_dashboard'
    ),

    # ── Create a new group ────────────────────────────────────
    path(
        'create/',
        views.group_create,
        name='group_create'
    ),

    # ── Single group detail page ──────────────────────────────
    path(
        '<int:group_id>/',
        views.group_detail,
        name='group_detail'
    ),

    # ── Add an existing registered user to a group ────────────
    path(
        '<int:group_id>/add-member/',
        views.add_member,
        name='add_member'
    ),

    # ── Create a managed profile (interior person) ────────────
    path(
        '<int:group_id>/add-managed/',
        views.create_managed_profile,
        name='create_managed_profile'
    ),

    # ── Fill case requirements on behalf of a managed profile ─
    # URL carries three IDs:
    #   group_id   → which group (access check)
    #   managed_id → which managed profile (ownership check)
    #   case_id    → which case (must belong to that managed profile)
    path(
        '<int:group_id>/managed/<int:managed_id>/case/<int:case_id>/',
        views.fill_case_for_managed,
        name='fill_case_for_managed'
    ),

    # EXPAND: add new user-facing URL patterns here
    # Case assignment and managed-profile operations → admin_panel/urls.py

]