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
    path('cases/<int:case_id>/',         views.case_detail, name='case_detail'),
    path('cases/<int:case_id>/delete/',  views.delete_case, name='delete_case'),

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

    # ── Group case management ──────────────────────────────────
    # Create an interior person (managed profile) in a group
    path(
        'groups/<int:group_id>/add-person/',
        views.admin_create_managed_profile,
        name='admin_create_managed_profile'
    ),
    # Assign a case to a specific real member
    path(
        'groups/<int:group_id>/member/<int:membership_id>/assign-case/',
        views.admin_assign_case_to_member,
        name='admin_assign_case_to_member'
    ),
    # Managed profile detail — personal info + all their cases
    path(
        'groups/<int:group_id>/managed/<int:managed_id>/',
        views.admin_managed_profile_detail,
        name='admin_managed_profile_detail'
    ),
    # Assign a case to a managed profile
    path(
        'groups/<int:group_id>/managed/<int:managed_id>/assign-case/',
        views.admin_create_case_for_managed,
        name='admin_create_case_for_managed'
    ),
    # Link a managed profile to an existing user account
    path(
        'groups/<int:group_id>/managed/<int:managed_id>/link-user/',
        views.admin_link_managed_to_user,
        name='admin_link_managed_to_user'
    ),
    # Bulk-assign one category to ALL members + managed profiles
    path(
        'groups/<int:group_id>/assign-category/',
        views.admin_assign_category_to_group,
        name='admin_assign_category_to_group'
    ),

    # ── AJAX (called by JavaScript, not visited directly) ─────
    path('ajax/categories/',    views.get_categories,    name='get_categories'),
    path('ajax/subcategories/', views.get_subcategories, name='get_subcategories'),
    # User search autocomplete — used by CreateCaseForm + AdminAddMemberForm
    path('ajax/user-search/',   views.ajax_user_search,  name='ajax_user_search'),
    
    
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

    # Save the source_url on a category (used by the Crawler bar in the service builder)
    path('ajax/builder/category/<int:category_id>/source-url/',
         views.ajax_set_category_source_url,
         name='ajax_set_category_source_url'),

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

    # ── Phase 1: Requirement Library AJAX ─────────────────────
    # Sections (question banks)
    path('ajax/builder/sections/',
         views.ajax_get_sections,
         name='ajax_get_sections'),

    path('ajax/builder/section/create/',
         views.ajax_create_section,
         name='ajax_create_section'),

    path('ajax/builder/section/<int:section_id>/edit/',
         views.ajax_edit_section,
         name='ajax_edit_section'),

    # Library browser (all requirements, filterable by section)
    path('ajax/builder/library/',
         views.ajax_get_library,
         name='ajax_get_library'),

    # Library create (also covers old /requirement/create/ — mapped to same view)
    path('ajax/builder/library/create/',
         views.ajax_create_requirement,
         name='ajax_create_library_req'),

    # Category ↔ Requirement links (CategoryRequirement)
    path('ajax/builder/category/<int:category_id>/add-req/',
         views.ajax_add_to_category,
         name='ajax_add_to_category'),

    path('ajax/builder/category/<int:category_id>/add-section/',
         views.ajax_add_section_to_category,
         name='ajax_add_section_to_category'),

    path('ajax/builder/category/<int:category_id>/req/<int:cr_id>/remove/',
         views.ajax_remove_from_category,
         name='ajax_remove_from_category'),

    path('ajax/builder/category/<int:category_id>/reorder/',
         views.ajax_reorder_category_req,
         name='ajax_reorder_category_req'),

    # CategoryRequirement override (is_required per category)
    path('ajax/builder/category-req/<int:cr_id>/edit/',
         views.ajax_edit_category_req,
         name='ajax_edit_category_req'),

    # Choices for select-type requirements
    path('ajax/builder/requirement/<int:requirement_id>/choices/',
         views.ajax_get_choices,
         name='ajax_get_choices'),

    path('ajax/builder/requirement/<int:requirement_id>/choices/create/',
         views.ajax_create_choice,
         name='ajax_create_choice'),

    path('ajax/builder/choice/<int:choice_id>/edit/',
         views.ajax_edit_choice,
         name='ajax_edit_choice'),

    path('ajax/builder/choice/<int:choice_id>/delete/',
         views.ajax_delete_choice,
         name='ajax_delete_choice'),

    # ── Phase 4: Government Forms Library ─────────────────────────────────
    # Forms are reusable immigration form objects (IMM5710, IMM5257, etc.).
    # Requirements inside forms are shared from the library — no duplication.
    path('ajax/builder/forms/',
         views.ajax_get_forms,
         name='ajax_get_forms'),
    path('ajax/builder/form/create/',
         views.ajax_create_form,
         name='ajax_create_form'),
    path('ajax/builder/form/<int:form_id>/',
         views.ajax_get_form_detail,
         name='ajax_get_form_detail'),
    path('ajax/builder/form/<int:form_id>/edit/',
         views.ajax_edit_form,
         name='ajax_edit_form'),
    path('ajax/builder/form/<int:form_id>/delete/',
         views.ajax_delete_form,
         name='ajax_delete_form'),
    # Form ↔ Requirement linking
    path('ajax/builder/form/<int:form_id>/add-req/',
         views.ajax_add_req_to_form,
         name='ajax_add_req_to_form'),
    path('ajax/builder/form/<int:form_id>/req/<int:fr_id>/remove/',
         views.ajax_remove_req_from_form,
         name='ajax_remove_req_from_form'),
    # Category ↔ Form linking
    path('ajax/builder/category/<int:category_id>/forms/',
         views.ajax_get_forms_for_category,
         name='ajax_get_forms_for_category'),
    path('ajax/builder/category/<int:category_id>/add-form/',
         views.ajax_add_form_to_category,
         name='ajax_add_form_to_category'),
    path('ajax/builder/category/<int:category_id>/form/<int:cf_id>/remove/',
         views.ajax_remove_form_from_category,
         name='ajax_remove_form_from_category'),
    # Web crawler placeholder
    path('ajax/builder/import/',
         views.ajax_import_from_url,
         name='ajax_import_from_url'),
    # PDF upload: extract AcroForm fields from an uploaded fillable PDF
    path('ajax/builder/form/<int:form_id>/upload-pdf/',
         views.ajax_upload_form_pdf,
         name='ajax_upload_form_pdf'),
    # PDF import: create a Requirement from one extracted field and link it to the form
    path('ajax/builder/form/<int:form_id>/import-pdf-field/',
         views.ajax_import_pdf_field_to_form,
         name='ajax_import_pdf_field_to_form'),

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

    # ── Phase 5: Eligibility Scoring ──────────────────────────
    # Single category eligibility check (used by case creation + service browser)
    path('ajax/eligibility/',
         views.ajax_eligibility_check,
         name='ajax_eligibility_check'),
    # All child categories of a service with eligibility scores (service browser accordion)
    path('ajax/service-eligibility/',
         views.ajax_service_eligibility,
         name='ajax_service_eligibility'),
    # Service browser — hierarchical service/category view with eligibility % badges
    path('services/browse/',
         views.service_browser,
         name='service_browser'),
    # Eligibility quiz — admin fills in quiz answers on behalf of a user
    path('users/<int:user_id>/eligibility-quiz/',
         views.eligibility_quiz,
         name='eligibility_quiz'),

    # ── Crawler ────────────────────────────────────────────────
    # Trigger a crawl on a specific category's source_url (POST only)
    path('categories/<int:category_id>/crawl/',
         views.crawl_category_view,
         name='crawl_category'),
    # Review queue — list all pending CrawlerSuggestion rows
    path('crawler/review/',
         views.crawler_review,
         name='crawler_review'),
    # Accept a pending suggestion (POST: creates Requirement/Form in library)
    path('crawler/suggestions/<int:suggestion_id>/accept/',
         views.accept_suggestion,
         name='accept_suggestion'),
    # Reject a pending suggestion (POST: marks as rejected, kept for audit)
    path('crawler/suggestions/<int:suggestion_id>/reject/',
         views.reject_suggestion,
         name='reject_suggestion'),
]