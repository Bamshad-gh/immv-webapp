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
    # export = download requirements + answers as Excel
    path(
        'cases/<int:case_id>/export/',
        views.export_case_requirements,
        name='export_case_requirements'
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
    
    
        # ── Service Builder ───────────────────────────────────────
    path('services/',
         views.service_list,
         name='service_list'),

    path('builder/',
         views.service_builder,
         name='service_builder'),

    # AJAX endpoints — all prefixed /ajax/builder/
    # These return JSON, not HTML
    path('ajax/builder/services/',
         views.ajax_get_services,
         name='ajax_get_services'),

    path('ajax/builder/service/create/',
         views.ajax_create_service,
         name='ajax_create_service'),

    path('ajax/builder/categories/',
         views.ajax_get_categories,
         name='ajax_get_categories'),

    path('ajax/builder/category/create/',
         views.ajax_create_category,
         name='ajax_create_category'),

    path('ajax/builder/category/<int:category_id>/',
         views.ajax_get_category_detail,
         name='ajax_get_category_detail'),

    path('ajax/builder/category/<int:category_id>/edit/',
         views.ajax_edit_category,
         name='ajax_edit_category'),

    path('ajax/builder/requirement/create/',
         views.ajax_create_requirement,
         name='ajax_create_requirement'),

    path('ajax/builder/requirement/<int:requirement_id>/edit/',
         views.ajax_edit_requirement,
         name='ajax_edit_requirement'),
    
    path('ajax/builder/service/<int:service_id>/delete/',
     views.ajax_delete_service,
     name='ajax_delete_service'),

path('ajax/builder/category/<int:category_id>/delete/',
     views.ajax_delete_category,
     name='ajax_delete_category'),

path('ajax/builder/requirement/<int:requirement_id>/delete/',
     views.ajax_delete_requirement,
     name='ajax_delete_requirement'),

    # ── Tasks ─────────────────────────────────────────────────
    path('tasks/',
         views.task_list,
         name='task_list'),

    path('tasks/create/',
         views.task_create,
         name='task_create'),

    path('tasks/<int:task_id>/',
         views.task_detail,
         name='task_detail'),

    # ── Payments ──────────────────────────────────────────────
    path('invoices/',
         views.invoice_list,
         name='invoice_list'),

    path('invoices/create/',
         views.invoice_create,
         name='invoice_create'),

    path('invoices/<int:invoice_id>/',
         views.invoice_detail,
         name='invoice_detail'),

    path('payments/overview/',
         views.user_balance_overview,
         name='user_balance_overview'),
    
    
    
    # -- Delete tasks / invoices
    path('tasks/<int:task_id>/delete/',        views.task_delete,    name='task_delete'),
    path('invoices/<int:invoice_id>/delete/',  views.invoice_delete, name='invoice_delete'),

    # -- Content management (superadmin only)
    path('content/settings/',                    views.site_settings_edit, name='site_settings_edit'),
    path('content/blog/',                        views.blog_post_list,     name='blog_post_list'),
    path('content/blog/create/',                 views.blog_post_create,   name='blog_post_create'),
    path('content/blog/<int:post_id>/edit/',     views.blog_post_edit,     name='blog_post_edit'),
    path('content/blog/<int:post_id>/delete/',   views.blog_post_delete,   name='blog_post_delete'),
    path('content/messages/',                    views.contact_messages,   name='contact_messages'),
]