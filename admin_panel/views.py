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
    case    = get_object_or_404(Case, id=case_id)
    answers = CaseAnswer.objects.filter(case=case).select_related('requirement')

    # All requirements for this case — active AND inactive
    # Template shows active with "Remove" button, inactive with "Restore" button
    case_requirements = (
        CaseRequirement.objects
        .filter(case=case)
        .select_related('requirement')
        .order_by('is_active')  # inactive (removed) ones at the bottom
    )

    # Requirements from the category not yet added to this case
    # Admin can add any of these as extras
    existing_req_ids = case_requirements.values_list('requirement_id', flat=True)
    available_to_add = Requirement.objects.filter(
        category=case.category,
        is_active=True
    ).exclude(id__in=existing_req_ids)

    if request.method == 'POST':
        new_status = request.POST.get('status')
        new_notes  = request.POST.get('notes', '')

        if new_status in dict(Case.STATUS_CHOICES):
            case.status = new_status
        case.notes = new_notes
        case.save()

        messages.success(request, 'Case updated.')
        return redirect('admin_panel:case_detail', case_id=case_id)

    return render(request, 'admin_panel/case_detail.html', {
        'case':              case,
        'answers':           answers,
        'case_requirements': case_requirements,
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