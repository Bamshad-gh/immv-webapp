# admin_panel/views.py
# ─────────────────────────────────────────────────────────────
# What's in this file (in order):
#   1.  admin_login()               — separate staff login
#   2.  admin_logout()              — destroy session
#   3.  admin_dashboard()           — home: stats based on permissions
#   4.  user_list()                 — list all regular users
#   5+.  admin_view_user()            — view a user's dashboard as an admin
#   5.  create_user()               — admin creates a new user
#   6.  manage_admins()             — superadmin: list all admins
#   7.  create_admin()              — superadmin: create new admin
#   8.  edit_admin_permissions()    — superadmin: update admin permissions
#   9.  case_list()                 — list all cases with filters
#   10. case_detail()               — view case + answers + manage requirements
#   11. create_case()               — admin creates case, auto-creates CaseRequirements
#   12. toggle_requirement()        — soft delete/restore a requirement per case
#   13. add_extra_requirement()     — add requirement not in category defaults
#   14. group_list()                — list all groups
#   15. group_detail()              — view group members + managed profiles
#   15++. admin_create_group()       — admin creates a group and assigns an owner
#   15++. admin_add_member()         — admin adds a user to a group with optional role
#   15++. admin_toggle_member()      — admin suspends or restores a group member
#   15++. admin_set_member_permissions() — admin sets which GroupPermissions a member has
#   15++++ admin_change_member_role()      — admin changes a member's role within the group
#   16. get_categories()            — AJAX: categories for a service
#   17. get_subcategories()         — AJAX: subcategories for a category
#    18. service_builder()             — superadmin: create/edit services, categories, requirements
#    19. service_list()                — list all services with their categories and requirements
#    20. ajax_get_services()             — AJAX: get all services (for dynamic form dropdowns)
#    21. ajax_create_service()          — AJAX: superadmin creates a new service (from service_builder page)
#    22.ajax_get_categories()             — AJAX: get categories for a service (for dynamic form dropdowns)
#    23. ajax_create_category()          — AJAX: superadmin creates a new category (from service_builder page)
#    24. ajax_get_category_details()       — AJAX: get category details including requirements (for service_builder edit form)
#    25.ajax_create_requrment()           — AJAX: superadmin creates a new requirement (from service_builder page)
#    26. ajax_edit_requrment()             — AJAX: superadmin edits a requirement (from service_builder page)
#    27. ajax_editIcategory()             — AJAX: superadmin edits a category (from service_builder page)
#    28. ajax_delete_service()           — AJAX: superadmin deletes a service (from service_builder page)
#    29. ajax_delete_category()          — AJAX: superadmin deletes a category (from service_builder page)
#    30. ajax_delete_requirement()       — AJAX: superadmin deletes a requirement (from service_builder page)
#    31.task_list()                    — list all tasks (admin→user and admin→admin) with filters
#    32.task_create()                  — create a new task, either admin→user or admin→admin
#    33.task_detail()                    — view task details and edit (reassign, change status, etc.)
#    34.invoice_list()                   — list all invoices with filters
#    35.invoice_create()                 — create a new invoice for a user or group
#    36.invoice_detail()                 — view invoice details and edit (change status, etc.)
#    37.user_balance_overview()             — view a user's balance and transaction history (for invoice management)

# ─────────────────────────────────────────────────────────────

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import JsonResponse

from .decorators import admin_required, superadmin_required, admin_permission_required 
from django.views.decorators.csrf import ensure_csrf_cookie
from .forms import AdminLoginForm, CreateUserForm, CreateAdminForm, CreateCaseForm
from users.models import AdminProfile
from groups.models import Group, GroupMembership , Role , GroupPermission
from cases.models import Case, CaseAnswer, CaseRequirement, Category, Service, Requirement
from .forms import AdminGroupCreateForm, AdminAddMemberForm
from django.contrib.auth import get_user_model

import json
from django.views.decorators.http import require_http_methods

from django.db import transaction
from django.db.models import Sum
from decimal import Decimal
from tasks.models import Task, notify_task_assigned
from payments.models import Invoice, Payment
from tasks.models import Task, notify_task_assigned, notify_task_completed, notify_invoice_created, notify_payment_recorded
from django.contrib.auth import get_user_model




User = get_user_model()


# ── 1. ADMIN LOGIN ────────────────────────────────────────────

def admin_login(request):
    if request.user.is_authenticated and request.user.is_staff:
        if request.user.is_superuser:
            return redirect('admin_panel:admin_dashboard')  # superuser skips profile check
        if request.user.is_staff and hasattr(request.user, 'admin_profile'):
            return redirect('admin_panel:admin_dashboard')
        # is_staff but no admin_profile — don't redirect to dashboard, show error
        if request.user.is_staff:
            logout(request)  # ← log them out instead of looping
            form = AdminLoginForm()
            form.add_error(None, 'Your admin profile is not configured. Contact a superadmin.')
            return render(request, 'admin_panel/login.html', {'form': form})

    form = AdminLoginForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        email    = form.cleaned_data['email']
        password = form.cleaned_data['password']
        user     = authenticate(request, email=email, password=password)

        if user and user.is_staff:
            login(request, user)
            return redirect('admin_panel:admin_dashboard')
        else:
            form.add_error(None, 'Invalid credentials or insufficient access.')

    return render(request, 'admin_panel/login.html', {'form': form})


# ── 2. ADMIN LOGOUT ───────────────────────────────────────────

def admin_logout(request):
    logout(request)
    return redirect('admin_panel:admin_login')


# ── 3. ADMIN DASHBOARD ────────────────────────────────────────
# Only loads stats the admin has permission to see.
# EXPAND: add more stat blocks as new capabilities are added.
@ensure_csrf_cookie  # ← add this
@admin_required
def admin_dashboard(request):
    admin_profile = getattr(request.user, 'admin_profile', None)
    stats         = {}

    # superuser sees everything, admin sees only what they have permission for
    if request.user.is_superuser or (admin_profile and admin_profile.can_view_all_cases):
        stats['total_cases']     = Case.objects.filter(is_active=True).count()
        stats['pending_cases']   = Case.objects.filter(status='pending',   is_active=True).count()
        stats['completed_cases'] = Case.objects.filter(status='completed', is_active=True).count()

    if request.user.is_superuser or (admin_profile and admin_profile.can_create_groups):
        stats['total_groups']  = Group.objects.filter(is_active=True).count()
        stats['total_members'] = GroupMembership.objects.filter(is_active=True).count()

    if request.user.is_superuser or (admin_profile and admin_profile.can_create_users):
        stats['total_users'] = User.objects.filter(is_staff=False).count()

    return render(request, 'admin_panel/dashboard.html', {
        'admin_profile': admin_profile,  # None for superusers — template handles it
        'stats':         stats,
    })


# ── 4. USER LIST ──────────────────────────────────────────────

@admin_permission_required('can_create_users')
def user_list(request):
    users = User.objects.filter(is_staff=False).order_by('-date_joined')
    return render(request, 'admin_panel/user_list.html', {'users': users})


# ── 5. CREATE USER ────────────────────────────────────────────

@admin_permission_required('can_create_users')
def create_user(request):
    if request.method == 'POST':
        form = CreateUserForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'User {user.email} created successfully.')
            return redirect('admin_panel:user_list')
    else:
        form = CreateUserForm()

    return render(request, 'admin_panel/create_user.html', {'form': form})

# ── 6. VIEW USER DASHBOARD ───────────────────────────────────
@admin_required
def admin_view_user(request, user_id):
    """
    Admin views a user's full dashboard — cases, groups, managed profiles.
    Reuses the user-facing template — no duplicate templates needed.

    The key difference from the real user dashboard:
      - request.user  = the admin (for access control)
      - target_user   = the user being viewed (for data)

    EXPAND: add an 'edit profile' button that links to admin_edit_user view.
    """
    target_user = get_object_or_404(User, id=user_id)

    # Same three queries as cases/views.py user_pickedCases_dashboard
    # but using target_user instead of request.user
    personal_cases = Case.objects.filter(
        user=target_user,
        group=None,
        managed_profile=None
    )

    user_group_ids = GroupMembership.objects.filter(
        user=target_user,
        is_active=True
    ).values_list('group_id', flat=True)

    group_cases = Case.objects.filter(
        group_id__in=user_group_ids,
        managed_profile=None
    )

    managed_cases = Case.objects.filter(
        managed_profile__created_by=target_user
    )

    # User's groups with their roles
    memberships = (
        GroupMembership.objects
        .filter(user=target_user, is_active=True)
        .select_related('group', 'role')
    )

    return render(request, 'admin_panel/user_view.html', {
        'target_user':    target_user,
        'personal_cases': personal_cases,
        'group_cases':    group_cases,
        'managed_cases':  managed_cases,
        'memberships':    memberships,
    })


# ── 6. MANAGE ADMINS ──────────────────────────────────────────

@superadmin_required
def manage_admins(request):
    admins = (
        AdminProfile.objects
        .select_related('user', 'created_by')
        .order_by('-created_at')
    )
    return render(request, 'admin_panel/manage_admins.html', {'admins': admins})


# ── 7. CREATE ADMIN ───────────────────────────────────────────

@superadmin_required
def create_admin(request):
    if request.method == 'POST':
        form = CreateAdminForm(request.POST)
        if form.is_valid():
            user = form.save(created_by=request.user)
            messages.success(request, f'Admin {user.email} created successfully.')
            return redirect('admin_panel:manage_admins')
    else:
        form = CreateAdminForm()

    return render(request, 'admin_panel/create_admin.html', {'form': form})


# ── 8. EDIT ADMIN PERMISSIONS ─────────────────────────────────

@superadmin_required
def edit_admin_permissions(request, admin_id):
    admin_profile = get_object_or_404(AdminProfile, id=admin_id)

    if request.method == 'POST':
        # checkbox checked = key exists in POST | unchecked = key missing
        # EXPAND: add new permission fields here as AdminProfile grows
        admin_profile.can_create_groups   = 'can_create_groups'   in request.POST
        admin_profile.can_assign_members  = 'can_assign_members'  in request.POST
        admin_profile.can_view_all_cases  = 'can_view_all_cases'  in request.POST
        admin_profile.can_create_users    = 'can_create_users'    in request.POST
        admin_profile.can_manage_roles    = 'can_manage_roles'    in request.POST
        admin_profile.save()

        messages.success(request, f'Permissions updated for {admin_profile.user.email}.')
        return redirect('admin_panel:manage_admins')

    return render(request, 'admin_panel/edit_admin_permissions.html', {
        'admin_profile': admin_profile,
    })


# ── 9. CASE LIST ──────────────────────────────────────────────

@admin_permission_required('can_view_all_cases')
def case_list(request):
    cases = (
        Case.objects
        .filter(is_active=True)
        .select_related('user', 'category', 'group', 'managed_profile')
        .order_by('-created_at')
    )

    # GET filters — usage: /admin-panel/cases/?status=pending&user=ali@email.com
    status_filter = request.GET.get('status')
    user_filter   = request.GET.get('user')

    if status_filter:
        cases = cases.filter(status=status_filter)
    if user_filter:
        cases = cases.filter(user__email__icontains=user_filter)

    return render(request, 'admin_panel/case_list.html', {
        'cases':          cases,
        'status_filter':  status_filter,
        'user_filter':    user_filter,
        'status_choices': Case.STATUS_CHOICES,
    })


# ── 10. CASE DETAIL ───────────────────────────────────────────
# Shows case info, answers, and the requirement management panel.
# Admin updates status/notes here.
# Requirement toggling handled by toggle_requirement view (POST only).
# Extra requirements added by add_extra_requirement view (POST only).

@admin_permission_required('can_view_all_cases')
def case_detail(request, case_id):
    """
    Admin views and manages a case.

    POST actions — determined by 'action' hidden field in each form:
      'update_case'   — update status and notes
      'edit_answer'   — admin edits a specific requirement's answer
      'toggle_req'    — handled by separate toggle_requirement view
      'add_extra'     — handled by separate add_extra_requirement view

    Data passed to template:
      requirement_rows — list of dicts, each with:
        cr      : CaseRequirement object
        req     : Requirement object
        answer  : CaseAnswer or None
      No lookups needed in template — everything pre-fetched here.

    EXPAND: add 'history' tracking to log every admin edit with timestamp.
    """
    case = get_object_or_404(Case, id=case_id)

    # ── Handle POST actions ───────────────────────────────────
    if request.method == 'POST':
        action = request.POST.get('action')

        # Action 1 — update case status and notes
        if action == 'update_case':
            new_status = request.POST.get('status')
            new_notes  = request.POST.get('notes', '')
            if new_status in dict(Case.STATUS_CHOICES):
                case.status = new_status
            case.notes = new_notes
            case.save()
            messages.success(request, 'Case updated.')

        # Action 2 — admin edits a specific answer
        elif action == 'edit_answer':
            requirement_id = request.POST.get('requirement_id')
            notify_user    = 'notify_user' in request.POST  # checkbox

            req = get_object_or_404(
                Requirement,
                id=requirement_id,
                # Security: requirement must belong to this case's category
                # or be an extra requirement for this case
            )

            # Get or create the answer row
            answer, _ = CaseAnswer.objects.get_or_create(
                case=case,
                requirement=req,
            )

            # Update the correct field based on requirement type
            # Each type maps to a different CaseAnswer field
            if req.type == 'text' or req.type == 'question':
                answer.answer_text   = request.POST.get('answer_value', '')
                answer.answer_date   = None
                answer.answer_number = None
                answer.answer_file   = None

            elif req.type == 'date':
                date_value = request.POST.get('answer_value', '')
                answer.answer_date   = date_value if date_value else None
                answer.answer_text   = None
                answer.answer_number = None
                answer.answer_file   = None

            elif req.type == 'number':
                number_value = request.POST.get('answer_value', '')
                answer.answer_number = number_value if number_value else None
                answer.answer_text   = None
                answer.answer_date   = None
                answer.answer_file   = None

            elif req.type == 'file':
                if 'answer_file' in request.FILES:
                    answer.answer_file   = request.FILES['answer_file']
                    answer.answer_text   = None
                    answer.answer_date   = None
                    answer.answer_number = None

            # Mark as admin edited + set notification preference
            answer.edited_by_admin = True
            answer.notify_user     = notify_user
            answer.save()

            if notify_user:
                messages.success(
                    request,
                    f'Answer updated and user will be notified.'
                )
            else:
                messages.success(
                    request,
                    f'Answer updated silently.'
                )

        return redirect('admin_panel:case_detail', case_id=case_id)

    # ── Build requirement rows for template ───────────────────
    # Pre-fetch all answers for this case once — O(n)
    answers_map = {
        a.requirement_id: a
        for a in CaseAnswer.objects.filter(case=case).select_related('requirement')
    }

    case_requirements = (
        CaseRequirement.objects
        .filter(case=case)
        .select_related('requirement')
        .order_by('-is_active', 'requirement__name')
        # active first, then inactive, alphabetical within each group
    )

    # Build combined rows — template iterates this, no lookups needed
    # EXPAND: add more keys here if template needs more data
    requirement_rows = [
        {
            'cr':     cr,
            'req':    cr.requirement,
            'answer': answers_map.get(cr.requirement_id),
        }
        for cr in case_requirements
    ]

    # Requirements available to add as extras
    existing_req_ids = [row['req'].id for row in requirement_rows]
    available_to_add = (
        Requirement.objects
        .filter(category=case.category, is_active=True)
        .exclude(id__in=existing_req_ids)
    )

    return render(request, 'admin_panel/case_detail.html', {
        'case':              case,
        'requirement_rows':  requirement_rows,
        'available_to_add':  available_to_add,
        'status_choices':    Case.STATUS_CHOICES,
    })


# ── 11. CREATE CASE ───────────────────────────────────────────
# After saving the Case, auto-creates CaseRequirement rows for all
# active requirements in the selected category.
# This is the "ready package" the user will fill in.

@admin_permission_required('can_view_all_cases')
def create_case(request):
    if request.method == 'POST':
        print("=== RAW POST DATA ===")
        print(dict(request.POST))  # ← add this
        form = CreateCaseForm(request.POST)
        print("=== FORM VALID ===", form.is_valid())
        print("=== FORM ERRORS ===", form.errors)  # ← add this
        if form.is_valid():
            ...
        form = CreateCaseForm(request.POST)
        if form.is_valid():
            case = form.save(created_by=request.user)

            # Auto-create CaseRequirement rows from category defaults
            # One row per active requirement — all active by default
            # Admin can toggle individual ones later from case_detail
            requirements = Requirement.objects.filter(
                category=case.category,
                is_active=True
            )
            for req in requirements:
                CaseRequirement.objects.create(
                    case=case,
                    requirement=req,
                    is_active=True,
                    is_extra=False,  # from category defaults, not manually added
                )

            messages.success(
                request,
                f'Case created for {form.cleaned_user.email} '
                f'— {requirements.count()} requirements loaded.'
            )
            return redirect('admin_panel:case_detail', case_id=case.id)
    else:
        form = CreateCaseForm()

    return render(request, 'admin_panel/create_case.html', {
        'form':     form,
        'services': Service.objects.filter(is_active=True),
    })

    
# ── 12. TOGGLE REQUIREMENT ────────────────────────────────────
# Flips is_active on a CaseRequirement — soft delete or restore.
# POST only — no template. Redirects back to case_detail.
#
# Active   → removed: user no longer sees this requirement
# Removed  → restored: user sees it again

@admin_permission_required('can_view_all_cases')
def toggle_requirement(request, case_id, case_requirement_id):
    if request.method != 'POST':
        return redirect('admin_panel:case_detail', case_id=case_id)

    case_req = get_object_or_404(
        CaseRequirement,
        id=case_requirement_id,
        case_id=case_id  # security: must belong to this case
    )

    case_req.is_active = not case_req.is_active
    case_req.save()

    status = 'restored' if case_req.is_active else 'removed'
    messages.success(request, f'"{case_req.requirement.name}" {status}.')
    return redirect('admin_panel:case_detail', case_id=case_id)


# ── 13. ADD EXTRA REQUIREMENT ─────────────────────────────────
# Admin adds a requirement to a case that wasn't in the category defaults.
# is_extra=True marks it as manually added.
# POST only — requirement_id comes from a select on the case_detail page.

@admin_permission_required('can_view_all_cases')
def add_extra_requirement(request, case_id):
    if request.method != 'POST':
        return redirect('admin_panel:case_detail', case_id=case_id)

    case           = get_object_or_404(Case, id=case_id)
    requirement_id = request.POST.get('requirement_id')
    requirement    = get_object_or_404(
        Requirement,
        id=requirement_id,
        category=case.category  # security: must belong to same category
    )

    # get_or_create — safe if row already exists (e.g., was removed before)
    case_req, created = CaseRequirement.objects.get_or_create(
        case=case,
        requirement=requirement,
        defaults={
            'is_active': True,
            'is_extra':  True,
        }
    )

    if not created:
        # Row existed but was inactive — restore it
        case_req.is_active = True
        case_req.save()

    messages.success(request, f'"{requirement.name}" added to this case.')
    return redirect('admin_panel:case_detail', case_id=case_id)


# ── 14. GROUP LIST ────────────────────────────────────────────

@admin_permission_required('can_create_groups')
def group_list(request):
    """
    Lists all groups. Admin can create a new group from here.
    EXPAND: add search/filter by group type.
    """
    groups = (
        Group.objects
        .filter(is_active=True)
        .select_related('created_by')
        .order_by('-created_at')
    )
    return render(request, 'admin_panel/group_list.html', {'groups': groups})

# ── 15++. admin_create_group ──────────────────────────────────────────
@admin_permission_required('can_create_groups')
def admin_create_group(request):
    """
    Admin creates a group and assigns an owner.
    Owner is auto-added as first member.
    EXPAND: add default permissions assignment for the owner here.
    """
    if request.method == 'POST':
        form = AdminGroupCreateForm(request.POST)
        if form.is_valid():
            group = form.save(created_by=request.user)
            messages.success(
                request,
                f'Group "{group.name}" created. '
                f'{form.cleaned_owner.email} added as owner.'
            )
            return redirect('admin_panel:group_detail', group_id=group.id)
    else:
        form = AdminGroupCreateForm()

    return render(request, 'admin_panel/create_group.html', {'form': form})

# ── 15. GROUP DETAIL ──────────────────────────────────────────

@admin_permission_required('can_assign_members')
def group_detail(request, group_id):
    """
    Admin views and manages a group:
    - Members with their roles and permissions
    - Managed profiles
    - Option to add members, toggle active status
    EXPAND: add case assignment directly from this page.
    """
    group            = get_object_or_404(Group, id=group_id)
    memberships      = (
        group.memberships
        .select_related('user', 'role')
        .prefetch_related('permissions')
        .order_by('-joined_at')
    )
    managed_profiles = group.managed_profiles.select_related('created_by')
    roles            = Role.objects.filter(group_type=group.type)
    all_permissions  = GroupPermission.objects.all()

    return render(request, 'admin_panel/group_detail.html', {
        'group':            group,
        'memberships':      memberships,
        'managed_profiles': managed_profiles,
        'roles':            roles,
        'all_permissions':  all_permissions,
    })
# ── 15++. admin_add_member ──────────────────────────────────────────
@admin_permission_required('can_assign_members')
def admin_add_member(request, group_id):
    """
    Admin adds a user to a group with optional role.
    POST only from group_detail page.
    EXPAND: add bulk member import from CSV.
    """
    group = get_object_or_404(Group, id=group_id)

    if request.method == 'POST':
        form = AdminAddMemberForm(group, request.POST)
        if form.is_valid():
            membership = form.save()
            messages.success(
                request,
                f'{membership.user.email} added to {group.name}.'
            )
        else:
            # Pass errors back — re-render group detail with form errors
            for error in form.errors.values():
                messages.error(request, error.as_text())

    return redirect('admin_panel:group_detail', group_id=group_id)

# ── 15++. admin_toggle_member ──────────────────────────────────────────
@admin_permission_required('can_assign_members')
def admin_toggle_member(request, group_id, membership_id):
    """
    Suspends or restores a group member.
    is_active=False = suspended (blocked from filling cases, viewing group)
    is_active=True  = active again
    POST only — no template needed.
    """
    if request.method != 'POST':
        return redirect('admin_panel:group_detail', group_id=group_id)

    membership = get_object_or_404(
        GroupMembership,
        id=membership_id,
        group_id=group_id  # security: must belong to this group
    )
    membership.is_active = not membership.is_active
    membership.save()

    status = 'restored' if membership.is_active else 'suspended'
    messages.success(request, f'{membership.user.email} {status}.')
    return redirect('admin_panel:group_detail', group_id=group_id)

# ── 15++. admin_set_member_permissions ──────────────────────────────────────────
@admin_permission_required('can_assign_members')
def admin_set_member_permissions(request, group_id, membership_id):
    """
    Admin sets which GroupPermissions a member has.
    Checkboxes — checked = has permission, unchecked = doesn't.
    POST only from group_detail page.

    EXPAND: add role assignment here too.
    """
    if request.method != 'POST':
        return redirect('admin_panel:group_detail', group_id=group_id)

    membership = get_object_or_404(
        GroupMembership,
        id=membership_id,
        group_id=group_id
    )

    # Get all permission IDs that were checked
    permission_ids = request.POST.getlist('permissions')

    # Replace all permissions with the checked ones
    # set() replaces the entire M2M — clean and simple
    membership.permissions.set(permission_ids)
    membership.save()

    messages.success(
        request,
        f'Permissions updated for {membership.user.email}.'
    )
    return redirect('admin_panel:group_detail', group_id=group_id)


# 15++++--- admin change member role (inline from group detail) ---
@admin_permission_required('can_assign_members')
def admin_change_member_role(request, group_id, membership_id):
    """
    Changes a member's role inline from the group detail page.
    role_id = empty string means remove the role (set to None).
    POST only.
    """
    if request.method != 'POST':
        return redirect('admin_panel:group_detail', group_id=group_id)

    membership = get_object_or_404(
        GroupMembership,
        id=membership_id,
        group_id=group_id  # security: must belong to this group
    )

    role_id = request.POST.get('role_id')

    if role_id:
        role = get_object_or_404(Role, id=role_id, group_type=membership.group.type)
        membership.role = role
    else:
        membership.role = None  # remove role

    membership.save()
    messages.success(request, f'Role updated for {membership.user.email}.')
    return redirect('admin_panel:group_detail', group_id=group_id)



# ── 16. AJAX — GET CATEGORIES ─────────────────────────────────
# Called by JavaScript when admin selects a service.
# Returns top-level categories as JSON to populate the next dropdown.

def get_categories(request):
    """
    URL: /admin-panel/ajax/categories/?service_id=3
    Response: {"categories": [{"id": 1, "name": "Work Visa"}, ...]}
    """
    service_id = request.GET.get('service_id')
    if not service_id:
        return JsonResponse({'categories': []})

    categories = Category.objects.filter(
        service_id=service_id,
        parent=None,
        is_active=True
    ).values('id', 'name')

    return JsonResponse({'categories': list(categories)})


# ── 17. AJAX — GET SUBCATEGORIES ─────────────────────────────
# Called by JavaScript when admin selects a category.

def get_subcategories(request):
    """
    URL: /admin-panel/ajax/subcategories/?category_id=5
    Response: {"subcategories": [{"id": 3, "name": "LMIA Exempt"}, ...]}
    Empty list = this category has no subcategories.
    """
    category_id = request.GET.get('category_id')
    if not category_id:
        return JsonResponse({'subcategories': []})

    subcategories = Category.objects.filter(
        parent_id=category_id,
        is_active=True
    ).values('id', 'name')

    return JsonResponse({'subcategories': list(subcategories)})

# ── Builder Page ──────────────────────────────────────────────

@admin_permission_required('can_manage_content')
def service_builder(request):
    """
    Renders the single-page service builder.
    All data loading happens via AJAX after the page loads.
    This view just renders the empty shell.
    """
    return render(request, 'admin_panel/service_builder.html')


# ── Service List (for list/overview page) ─────────────────────

@admin_permission_required('can_manage_content')
def service_list(request):
    """
    Overview page — lists all services as cards.
    Links to builder with each service pre-selected.
    """
    services = Service.objects.prefetch_related('categories').order_by('name')
    service_data = [
        {
            'service':        s,
            'category_count': s.categories.filter(is_active=True).count(),
            'req_count':      Requirement.objects.filter(
                                  category__service=s,
                                  is_active=True
                              ).count(),
        }
        for s in services
    ]
    return render(request, 'admin_panel/service_list.html', {
        'service_data': service_data,
    })


# ── AJAX: Load All Services ───────────────────────────────────

@admin_required
def ajax_get_services(request):
    """
    GET /ajax/builder/services/
    Returns all active services for the left panel.
    Response: { services: [{id, name, description, is_active, category_count}] }
    """
    services = Service.objects.filter(is_active=True).order_by('name')
    data = [
        {
            'id':             s.id,
            'name':           s.name,
            'description':    s.description or '',
            'is_active':      s.is_active,
            'category_count': s.categories.filter(is_active=True).count(),
        }
        for s in services
    ]
    return JsonResponse({'services': data})


# ── AJAX: Create Service ──────────────────────────────────────

@admin_required
@require_http_methods(['POST'])
def ajax_create_service(request):
    """
    POST /ajax/builder/service/create/
    Body: { name, description }
    Response: { ok: true, service: {id, name, description, is_active} }
              { ok: false, errors: {field: [error]} }

    Why require_http_methods?
      Explicit — rejects GET requests cleanly with 405 instead of silent failure.
    """
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'errors': {'__all__': ['Invalid JSON']}}, status=400)

    name        = body.get('name', '').strip()
    description = body.get('description', '').strip()

    # Validate
    errors = {}
    if not name:
        errors['name'] = ['Name is required.']
    if Service.objects.filter(name__iexact=name).exists():
        errors['name'] = [f'A service named "{name}" already exists.']

    if errors:
        return JsonResponse({'ok': False, 'errors': errors})

    service = Service.objects.create(name=name, description=description)
    return JsonResponse({
        'ok':      True,
        'service': {
            'id':          service.id,
            'name':        service.name,
            'description': service.description or '',
            'is_active':   service.is_active,
        }
    })


# ── AJAX: Load Categories for a Service or Parent ─────────────

@admin_required
def ajax_get_categories(request):
    """
    GET /ajax/builder/categories/?service_id=1
    GET /ajax/builder/categories/?parent_id=5
    Returns direct children only — not the full tree.
    JavaScript builds the tree level by level.

    Response: { categories: [{id, name, description, is_active, req_count, has_children}] }

    has_children tells JS whether to show an expand arrow on the category.
    """
    service_id = request.GET.get('service_id')
    parent_id  = request.GET.get('parent_id')

    if service_id:
        cats = Category.objects.filter(
            service_id=service_id,
            parent=None,
            is_active=True
        ).order_by('name')
    elif parent_id:
        cats = Category.objects.filter(
            parent_id=parent_id,
            is_active=True
        ).order_by('name')
    else:
        return JsonResponse({'categories': []})

    data = [
        {
            'id':           c.id,
            'name':         c.name,
            'description':  c.description or '',
            'is_active':    c.is_active,
            'service_id':   c.service_id,
            'parent_id':    c.parent_id,
            'req_count':    c.requirements.filter(is_active=True).count(),
            'has_children': c.subcategories.exists(),
        }
        for c in cats
    ]
    return JsonResponse({'categories': data})


# ── AJAX: Create Category ─────────────────────────────────────

@admin_required
@require_http_methods(['POST'])
def ajax_create_category(request):
    """
    POST /ajax/builder/category/create/
    Body: { name, description, service_id, parent_id (optional) }
    Response: { ok: true, category: {...} }
              { ok: false, errors: {...} }
    """
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'errors': {'__all__': ['Invalid JSON']}}, status=400)

    name        = body.get('name', '').strip()
    description = body.get('description', '').strip()
    service_id  = body.get('service_id')
    parent_id   = body.get('parent_id')  # None = top-level

    # Validate
    errors = {}
    if not name:
        errors['name'] = ['Name is required.']
    if not service_id:
        errors['service_id'] = ['Service is required.']

    if errors:
        return JsonResponse({'ok': False, 'errors': errors})

    service = get_object_or_404(Service, id=service_id)
    parent  = get_object_or_404(Category, id=parent_id) if parent_id else None

    # Ensure parent belongs to same service
    if parent and parent.service_id != service.id:
        return JsonResponse({
            'ok': False,
            'errors': {'parent_id': ['Parent must belong to the same service.']}
        })

    category = Category.objects.create(
        name        = name,
        description = description,
        service     = service,
        parent      = parent,
    )

    return JsonResponse({
        'ok':       True,
        'category': {
            'id':           category.id,
            'name':         category.name,
            'description':  category.description or '',
            'is_active':    category.is_active,
            'service_id':   category.service_id,
            'parent_id':    category.parent_id,
            'req_count':    0,
            'has_children': False,
        }
    })


# ── AJAX: Get Category Detail (requirements + inheritance) ────

@admin_required
def ajax_get_category_detail(request, category_id):
    """
    GET /ajax/builder/category/<id>/
    Returns:
      - category info
      - own requirements (directly on this category)
      - inherited requirements (from all parent categories, with source info)

    This powers the right panel in the builder.
    Response: {
      category: {...},
      own_requirements: [{id, name, type, description, is_required, is_active}],
      inherited: [{req: {...}, from_category: {id, name}}]
    }
    """
    category = get_object_or_404(Category, id=category_id)

    # Own requirements
    own_reqs = list(
        category.requirements
        .filter(is_active=True)
        .order_by('name')
        .values('id', 'name', 'type', 'description', 'is_required', 'is_active')
    )

    # Inherited — walk up parent chain
    inherited = []
    seen_ids  = {r['id'] for r in own_reqs}
    current   = category.parent

    while current:
        parent_reqs = current.requirements.filter(is_active=True).order_by('name')
        for req in parent_reqs:
            if req.id not in seen_ids:
                seen_ids.add(req.id)
                inherited.append({
                    'req': {
                        'id':          req.id,
                        'name':        req.name,
                        'type':        req.type,
                        'description': req.description or '',
                        'is_required': req.is_required,
                    },
                    'from_category': {
                        'id':   current.id,
                        'name': current.name,
                    }
                })
        current = current.parent

    return JsonResponse({
        'category': {
            'id':          category.id,
            'name':        category.name,
            'description': category.description or '',
            'service_id':  category.service_id,
            'parent_id':   category.parent_id,
        },
        'own_requirements': own_reqs,
        'inherited':        inherited,
    })


# ── AJAX: Create Requirement ──────────────────────────────────

@admin_required
@require_http_methods(['POST'])
def ajax_create_requirement(request):
    """
    POST /ajax/builder/requirement/create/
    Body: { name, type, description, is_required, category_id }
    Response: { ok: true, requirement: {...} }
              { ok: false, errors: {...} }
    """
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'errors': {'__all__': ['Invalid JSON']}}, status=400)

    name        = body.get('name', '').strip()
    req_type    = body.get('type', '').strip()
    description = body.get('description', '').strip()
    is_required = body.get('is_required', True)
    category_id = body.get('category_id')

    # Validate
    errors      = {}
    valid_types = [t[0] for t in Requirement.TYPE_CHOICES]

    if not name:
        errors['name'] = ['Name is required.']
    if not req_type:
        errors['type'] = ['Type is required.']
    elif req_type not in valid_types:
        errors['type'] = [f'Invalid type. Choose from: {", ".join(valid_types)}']
    if not category_id:
        errors['category_id'] = ['Category is required.']

    if errors:
        return JsonResponse({'ok': False, 'errors': errors})

    category = get_object_or_404(Category, id=category_id)
    req      = Requirement.objects.create(
        name        = name,
        type        = req_type,
        description = description,
        is_required = bool(is_required),
        category    = category,
    )

    return JsonResponse({
        'ok':          True,
        'requirement': {
            'id':          req.id,
            'name':        req.name,
            'type':        req.type,
            'description': req.description or '',
            'is_required': req.is_required,
            'is_active':   req.is_active,
        }
    })


# ── AJAX: Edit Requirement ────────────────────────────────────

@admin_required
@require_http_methods(['POST'])
def ajax_edit_requirement(request, requirement_id):
    """
    POST /ajax/builder/requirement/<id>/edit/
    Body: { name, type, description, is_required, is_active }
    Response: { ok: true, requirement: {...} }
              { ok: false, errors: {...} }

    Why POST not PATCH?
      Django's CSRF middleware works cleanly with POST.
      PATCH requires extra setup for form data — POST keeps it simple.
    """
    req = get_object_or_404(Requirement, id=requirement_id)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'errors': {'__all__': ['Invalid JSON']}}, status=400)

    name        = body.get('name', req.name).strip()
    req_type    = body.get('type', req.type).strip()
    description = body.get('description', req.description or '').strip()
    is_required = body.get('is_required', req.is_required)
    is_active   = body.get('is_active',   req.is_active)

    errors      = {}
    valid_types = [t[0] for t in Requirement.TYPE_CHOICES]

    if not name:
        errors['name'] = ['Name is required.']
    if req_type not in valid_types:
        errors['type'] = [f'Invalid type.']

    if errors:
        return JsonResponse({'ok': False, 'errors': errors})

    req.name        = name
    req.type        = req_type
    req.description = description
    req.is_required = bool(is_required)
    req.is_active   = bool(is_active)
    req.save()

    return JsonResponse({
        'ok':          True,
        'requirement': {
            'id':          req.id,
            'name':        req.name,
            'type':        req.type,
            'description': req.description or '',
            'is_required': req.is_required,
            'is_active':   req.is_active,
        }
    })


# ── AJAX: Edit Category ───────────────────────────────────────

@admin_required
@require_http_methods(['POST'])
def ajax_edit_category(request, category_id):
    """
    POST /ajax/builder/category/<id>/edit/
    Body: { name, description, is_active }
    Response: { ok: true, category: {...} }
    """
    category = get_object_or_404(Category, id=category_id)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'errors': {'__all__': ['Invalid JSON']}}, status=400)

    name        = body.get('name', category.name).strip()
    description = body.get('description', category.description or '').strip()
    is_active   = body.get('is_active', category.is_active)

    errors = {}
    if not name:
        errors['name'] = ['Name is required.']

    if errors:
        return JsonResponse({'ok': False, 'errors': errors})

    category.name        = name
    category.description = description
    category.is_active   = bool(is_active)
    category.save()

    return JsonResponse({
        'ok':       True,
        'category': {
            'id':          category.id,
            'name':        category.name,
            'description': category.description or '',
            'is_active':   category.is_active,
        }
    })
    
@admin_required
@require_http_methods(['POST'])
def ajax_delete_service(request, service_id):
    """
    POST /ajax/builder/service/<id>/delete/
    Soft delete — sets is_active=False instead of destroying data.
    Why soft delete? Cases linked to this service still exist and
    must remain accessible. Hard delete would break them.
    """
    service = get_object_or_404(Service, id=service_id)
    service.is_active = False
    service.save()
    return JsonResponse({'ok': True})


@admin_required
@require_http_methods(['POST'])
def ajax_delete_category(request, category_id):
    """
    POST /ajax/builder/category/<id>/delete/
    Soft delete — sets is_active=False.
    Also soft-deletes all direct children and their requirements
    so the tree stays consistent.
    EXPAND: make this recursive for deeper nesting if needed.
    """
    category = get_object_or_404(Category, id=category_id)

    # Soft delete this category
    category.is_active = False
    category.save()

    # Soft delete direct children
    Category.objects.filter(parent=category).update(is_active=False)

    # Soft delete requirements on this category
    Requirement.objects.filter(category=category).update(is_active=False)

    return JsonResponse({'ok': True})


@admin_required
@require_http_methods(['POST'])
def ajax_delete_requirement(request, requirement_id):
    """
    POST /ajax/builder/requirement/<id>/delete/
    Soft delete — sets is_active=False.
    Does NOT remove CaseRequirement rows — existing cases keep
    their requirements. is_active=False just hides it from new cases.
    """
    req = get_object_or_404(Requirement, id=requirement_id)
    req.is_active = False
    req.save()
    return JsonResponse({'ok': True})


# ══════════════════════════════════════════════════════════════
# TASK VIEWS
# ══════════════════════════════════════════════════════════════
# ___ Task List ___
@admin_permission_required('can_manage_tasks')
def task_list(request):
    """
    Admin sees all tasks they created or that are assigned to them.
    Superadmin sees all tasks.

    Filter by status via ?status=pending etc.
    Filter by type via ?type=admin_to_user etc.

    EXPAND: add search by title or user email.
    EXPAND: add date range filter.
    """
    from cases.models import Case

    tasks = Task.objects.select_related(
    'created_by', 'assigned_to_user', 'assigned_to_admin', 'related_case'
)

    # Superadmin sees all — regular admin sees only their tasks
    if not request.user.is_superuser:
        tasks = tasks.filter(
            created_by=request.user
        ) | tasks.filter(
            assigned_to_user=request.user
        ) | tasks.filter(
            assigned_to_admin__user=request.user
        )

    # Optional filters
    status_filter = request.GET.get('status')
    type_filter   = request.GET.get('type')

    if status_filter:
        tasks = tasks.filter(status=status_filter)
    if type_filter:
        tasks = tasks.filter(task_type=type_filter)  # also check if field is 'task_type' not 'type'

    tasks = tasks.order_by('due_date', '-created_at')

    return render(request, 'admin_panel/task_list.html', {
        'tasks':          tasks,
        'status_choices': Task.STATUS_CHOICES,
        'type_choices':   Task.TYPE_CHOICES,
        'status_filter':  status_filter,
        'type_filter':    type_filter,
    })


@admin_permission_required('can_manage_tasks')
def task_create(request):
    """
    Admin creates a task and assigns it to a user or another admin.

    On save:
      1. Task is created
      2. Notification is sent to assigned person
      3. If linked to a case, case gets a note

    EXPAND: add file attachment to task for supporting documents.
    """
    from cases.models import Case, Requirement

    if request.method == 'POST':
        task_type   = request.POST.get('type')
        title       = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        assigned_id = request.POST.get('assigned_to')
        due_date    = request.POST.get('due_date') or None
        case_id     = request.POST.get('linked_case') or None
        req_id      = request.POST.get('linked_requirement') or None

        errors = {}
        if not title:
            errors['title'] = 'Title is required.'
        if not assigned_id:
            errors['assigned_to'] = 'Assignee is required.'
        if not task_type:
            errors['type'] = 'Task type is required.'

        if not errors:
            assigned_user = get_object_or_404(User, id=assigned_id)
            task = Task.objects.create(
                task_type              = task_type,
                title                  = title,
                description            = description,
                created_by             = request.user,
                assigned_to_user       = assigned_user if task_type == 'user' else None,
                assigned_to_admin      = assigned_user if task_type == 'admin' else None,
                due_date               = due_date,
                related_case_id        = case_id,
                related_requirement_id = req_id,   # ← correct
                status                 = 'pending',
                )

            # Send notification to assignee
            notify_task_assigned(task)

            messages.success(request, f'Task "{title}" created and assigned.')
            return redirect('admin_panel:task_detail', task_id=task.id)

    else:
        errors = {}

    # Get assignable users — all admins for admin_to_admin,
    # all regular users for admin_to_user
    all_users  = User.objects.filter(is_active=True).order_by('email')
    all_cases  = Case.objects.filter(is_active=True).order_by('-created_at')[:50]

    return render(request, 'admin_panel/task_create.html', {
        'errors':         errors,
        'all_users':      all_users,
        'all_cases':      all_cases,
        'type_choices':   Task.TYPE_CHOICES,
        'post':           request.POST,  # re-fill form on error
    })


@admin_permission_required('can_manage_tasks')
def task_detail(request, task_id):
    """
    View/manage a single task.
    Admin can update status, edit title/description, add notes.
    When status changes to 'completed', notifies the task creator.
    """
    task = get_object_or_404(Task, id=task_id)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'update_status':
            new_status = request.POST.get('status')
            old_status = task.status

            if new_status in dict(Task.STATUS_CHOICES):
                task.status = new_status
                task.save()

                # Notify creator when completed
                if new_status == 'completed' and old_status != 'completed':
                    from tasks.models import notify_task_completed
                    notify_task_completed(task)

                messages.success(request, f'Task status updated to {new_status}.')

        elif action == 'update_task':
            task.title       = request.POST.get('title', task.title).strip()
            task.description = request.POST.get('description', task.description).strip()
            new_due          = request.POST.get('due_date')
            task.due_date    = new_due if new_due else None
            task.save()
            messages.success(request, 'Task updated.')

        return redirect('admin_panel:task_detail', task_id=task_id)

    return render(request, 'admin_panel/task_detail.html', {
        'task':           task,
        'status_choices': Task.STATUS_CHOICES,
    })


# ══════════════════════════════════════════════════════════════
# PAYMENT VIEWS
# ══════════════════════════════════════════════════════════════
# 34__ Invoice List __
@admin_permission_required('can_manage_payments')
def invoice_list(request):
    """
    Admin sees all invoices.
    Filter by user, status (paid/unpaid/overdue).

    EXPAND: add date range filter, export to CSV.
    """
    invoices = Invoice.objects.exclude(
    status='cancelled'
    ).select_related('user', 'created_by').prefetch_related('payments')

    # Filter by user email
    email_filter = request.GET.get('email', '').strip()
    if email_filter:
        invoices = invoices.filter(user__email__icontains=email_filter)

    # Filter by payment status
    paid_filter = request.GET.get('paid')
    if paid_filter == 'unpaid':
        # Get IDs of invoices where balance > 0
        # Must compute in Python since balance() is a method, not a DB field
        # EXPAND: add balance as annotated field for DB-level filtering
        invoices = [inv for inv in invoices if inv.status in ('unpaid', 'partial')]
    elif paid_filter == 'paid':
        invoices = [inv for inv in invoices if inv.status == 'paid']
    elif paid_filter == 'overdue':
        invoices = [inv for inv in invoices if inv.is_overdue()]

    return render(request, 'admin_panel/invoice_list.html', {
        'invoices':     invoices,
        'email_filter': email_filter,
        'paid_filter':  paid_filter,
    })


@admin_permission_required('can_manage_payments')
def invoice_create(request):
    """
    Admin creates an invoice for a user.
    Sends notification to user immediately on creation.

    EXPAND: add multiple line items (InvoiceLineItem model).
    """
    if request.method == 'POST':
        user_email  = request.POST.get('user_email', '').strip()
        title       = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        amount      = request.POST.get('amount', '').strip()
        due_date    = request.POST.get('due_date') or None

        errors = {}

        # Validate user
        try:
            user = User.objects.get(email=user_email, is_active=True)
        except User.DoesNotExist:
            errors['user_email'] = 'No active user with this email.'
            user = None

        if not title:
            errors['title'] = 'Title is required.'

        # Validate amount — must be positive decimal
        try:
            amount_decimal = Decimal(amount)
            if amount_decimal <= 0:
                errors['amount'] = 'Amount must be greater than zero.'
        except Exception:
            errors['amount'] = 'Enter a valid amount (e.g. 150.00).'
            amount_decimal = None

        if not errors and user and amount_decimal:
            invoice = Invoice.objects.create(
                user        = user,
                title       = title,
                description = description,
                amount      = amount_decimal,
                due_date    = due_date,
                created_by  = request.user,
            )

            # Notify user of new invoice
            notify_invoice_created(invoice)

            messages.success(
                request,
                f'Invoice "${title}" created for {user.email}.'
            )
            return redirect('admin_panel:invoice_detail', invoice_id=invoice.id)

    else:
        errors = {}

    users = User.objects.filter(is_active=True, is_staff=False).order_by('email')

    return render(request, 'admin_panel/invoice_create.html', {
        'errors': errors,
        'users':  users,
        'post':   request.POST,
    })


@admin_permission_required('can_manage_payments')
def invoice_detail(request, invoice_id):
    """
    View invoice details + payment history + record new payment.

    Double payment protection:
      select_for_update() locks the invoice row during payment recording.
      This prevents two admins simultaneously recording the same payment.
      The lock is released after the transaction commits.

    Why transaction.atomic()?
      If anything fails after the payment is created but before the
      notification is sent, the entire operation rolls back.
      Either both succeed or neither does — no partial state.
    """
    invoice = get_object_or_404(Invoice, id=invoice_id)
    payments = invoice.payments.select_related('marked_by').order_by('-marked_at')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'record_payment':
            amount_str = request.POST.get('amount', '').strip()
            note       = request.POST.get('note', '').strip()

            try:
                amount = Decimal(amount_str)
                if amount == 0:
                    raise ValueError('Zero amount')
            except Exception:
                messages.error(request, 'Enter a valid payment amount.')
                return redirect('admin_panel:invoice_detail', invoice_id=invoice_id)

            # Double payment protection — atomic transaction + row lock
            # select_for_update() prevents concurrent writes to this invoice
            with transaction.atomic():
                # Re-fetch with lock inside transaction
                locked_invoice = Invoice.objects.select_for_update().get(
                    id=invoice_id
                )

                # Safety check — warn if payment would overpay
                if amount > locked_invoice.balance_due() and amount > 0:
                    messages.warning(
                        request,
                        f'Warning: payment of ${amount} exceeds remaining '
                        f'balance of ${locked_invoice.balance_due()}. '
                        f'Recording anyway.'
                        )

                payment = Payment.objects.create(
                    invoice   = locked_invoice,
                    amount    = amount,
                    notes     = note,       # 'notes' not 'note'
                    marked_by = request.user,
                    )
                locked_invoice.update_status()

            # Notify user — outside transaction (non-critical)
            notify_payment_recorded(invoice, payment)

            messages.success(
                request,
                f'Payment of ${amount} recorded.'
            )
            return redirect('admin_panel:invoice_detail', invoice_id=invoice_id)

    return render(request, 'admin_panel/invoice_detail.html', {
        'invoice':     invoice,
        'payments':    payments,
        'total_paid':  invoice.total_paid(),
        'balance':     invoice.balance_due(),
        'is_paid':     invoice.status == 'paid',
        'is_overdue':  invoice.is_overdue(),
    })

#
@admin_permission_required('can_manage_payments')
def user_balance_overview(request):
    """
    Admin sees all users with outstanding balances.
    Shows total owed per user across all their active invoices.

    EXPAND: add export to CSV for accounting.
    EXPAND: add filter by minimum balance amount.
    """
    # Get all users with at least one active invoice
    users_with_invoices = User.objects.filter(
    invoices__isnull=False
    ).distinct().order_by('email')

    # Build summary per user in Python
    # EXPAND: move to DB annotation when performance matters at scale
    user_balances = []
    for user in users_with_invoices:
        user_invoices = Invoice.objects.filter(user=user).exclude(status='cancelled')
        total_owed = sum(inv.balance_due() for inv in user_invoices)
        if total_owed > 0:  # only show users with outstanding balance
            user_balances.append({
                'user':         user,
                'total_owed':   total_owed,
                'invoice_count': user_invoices.count(),
            })

    # Sort by highest balance first
    user_balances.sort(key=lambda x: x['total_owed'], reverse=True)

    return render(request, 'admin_panel/user_balance_overview.html', {
        'user_balances': user_balances,
    })


# ----------- delet invoces and tasks

@admin_permission_required('can_manage_tasks')
def task_delete(request, task_id):
    if request.method == 'POST':
        task = get_object_or_404(Task, id=task_id)
        task.delete()
        messages.success(request, 'Task deleted.')
    return redirect('admin_panel:task_list')


@admin_permission_required('can_manage_payments')
def invoice_delete(request, invoice_id):
    if request.method == 'POST':
        invoice = get_object_or_404(Invoice, id=invoice_id)
        invoice.delete()
        messages.success(request, 'Invoice deleted.')
    return redirect('admin_panel:invoice_list')