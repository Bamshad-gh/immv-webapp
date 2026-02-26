# admin_panel/urls.py
# ─────────────────────────────────────────────────────────────
# Wire up in config/urls.py:
#   path('admin-panel/', include('admin_panel.urls', namespace='admin_panel')),
# ─────────────────────────────────────────────────────────────

from django.urls import path
from . import views

app_name = 'admin_panel'

urlpatterns = [

    # ── Auth ──────────────────────────────────────────────────
    path('login/', views.admin_login, name='admin_login'),
    path('logout/', views.admin_logout, name='admin_logout'),

    # ── Dashboard ─────────────────────────────────────────────
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),

    # ── Users ─────────────────────────────────────────────────
    path('users/',        views.user_list,   name='user_list'),
    path('users/create/', views.create_user, name='create_user'),
    #   User proxy view
    path('users/<int:user_id>/view/', views.admin_view_user, name='admin_view_user'),

    # ── Admins (superadmin only) ───────────────────────────────
    path('admins/',                               views.manage_admins,          name='manage_admins'),
    path('admins/create/',                        views.create_admin,           name='create_admin'),
    path('admins/<int:admin_id>/permissions/',    views.edit_admin_permissions, name='edit_admin_permissions'),

    # ── Cases ─────────────────────────────────────────────────
    path('cases/',                views.case_list,   name='case_list'),
    path('cases/create/',         views.create_case, name='create_case'),
    path('cases/<int:case_id>/',  views.case_detail, name='case_detail'),

    # ── Case requirement management (POST only, no templates) ─
    # toggle = soft delete or restore a requirement for a specific case
    path(
        'cases/<int:case_id>/requirements/<int:case_requirement_id>/toggle/',
        views.toggle_requirement,
        name='toggle_requirement'
    ),
    # add_extra = add a requirement not in the category defaults
    path(
        'cases/<int:case_id>/requirements/add/',
        views.add_extra_requirement,
        name='add_extra_requirement'
    ),

    # ── Groups ────────────────────────────────────────────────
    path('groups/',                views.group_list,   name='group_list'),
    path('groups/<int:group_id>/', views.group_detail, name='group_detail'),
    path('groups/create/',                   views.admin_create_group,           name='admin_create_group'),
    path('groups/<int:group_id>/add-member/',views.admin_add_member,             name='admin_add_member'),
    path('groups/<int:group_id>/members/<int:membership_id>/toggle/',
                                             views.admin_toggle_member,          name='admin_toggle_member'),
    path('groups/<int:group_id>/members/<int:membership_id>/permissions/',
                                             views.admin_set_member_permissions, name='admin_set_member_permissions'),
    # Inline role change
    path(
        'groups/<int:group_id>/members/<int:membership_id>/role/',
        views.admin_change_member_role,
        name='admin_change_member_role'
    ),

    # ── AJAX (called by JavaScript, not visited directly) ─────
    path('ajax/categories/',    views.get_categories,    name='get_categories'),
    path('ajax/subcategories/', views.get_subcategories, name='get_subcategories'),
    
    

    

]