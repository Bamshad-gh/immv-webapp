# groups/views.py
# ─────────────────────────────────────────────────────────────
# What's in this file (in order):
#   1. get_group_access()       — reusable helper: returns (is_creator, membership)
#   2. group_dashboard()        — list all groups the user belongs to
#   3. group_detail()           — single group: members, roles, managed profiles, cases
#   4. group_create()           — create a new group + extra info
#   5. add_member()             — add existing user to a group
#   6. create_managed_profile() — create interior person (no account)
#   7. fill_case_for_managed()  — fill case requirements on behalf of managed profile
#
# Pattern used in every view:
#   1. Authenticate  → @login_required
#   2. Authorize     → get_group_access() + permission check
#   3. Query         → get the data needed
#   4. Handle POST   → validate form, save, redirect
#   5. Render        → pass context to template
# ─────────────────────────────────────────────────────────────

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .models import Group, GroupMembership
from .forms import GroupCreateForm, AddMemberForm, ManagedProfileForm
from users.models import ManagedProfile


# ── 1. ACCESS HELPER ─────────────────────────────────────────
# Reusable — call this at the top of any view that needs to check
# if the current user has access to a group.
#
# Returns (is_creator, membership):
#   is_creator = True if this user created the group
#   membership = GroupMembership object if they're an active member, else None

def get_group_access(request, group):
    is_creator = (group.created_by == request.user)
    try:
        membership = GroupMembership.objects.get(
            user=request.user,
            group=group,
            is_active=True
        )
    except GroupMembership.DoesNotExist:
        membership = None
    return is_creator, membership


# ── 2. GROUP DASHBOARD ────────────────────────────────────────
# Shows all groups the current user belongs to.
# select_related avoids N+1 — fetches group + role in one SQL join.
#
# EXPAND: add search/filter by group type.
# EXPAND: add pagination if user belongs to many groups.

@login_required
def group_dashboard(request):
    memberships = (
        GroupMembership.objects
        .filter(user=request.user, is_active=True)
        .select_related('group', 'role')
        .order_by('group__type', 'group__name')
    )

    return render(request, 'groups/dashboard.html', {
        'memberships': memberships,
    })


# ── 3. GROUP DETAIL ───────────────────────────────────────────
# Shows a single group: members, roles, managed profiles, and cases.
# Permission flags control what each member sees in the template.
# The template never makes access decisions — that's the view's job.

@login_required
def group_detail(request, group_id):
    group                  = get_object_or_404(Group, id=group_id, is_active=True)
    is_creator, membership = get_group_access(request, group)

    # Block access entirely if user has no connection to this group
    if not is_creator and not membership:
        messages.error(request, 'You do not have access to this group.')
        return redirect('groups:group_dashboard')

    # prefetch_related avoids N+1 on the permissions M2M
    all_memberships = (
        group.memberships
        .filter(is_active=True)
        .select_related('user', 'role')
        .prefetch_related('permissions')
    )

    managed_profiles = group.managed_profiles.select_related('created_by')

    # Group-level cases only — excludes managed profile cases
    # Managed profile cases show under each managed profile card in the template
    from cases.models import Case
    group_cases = Case.objects.filter(
        group=group,
        managed_profile=None,
        is_active=True
    ).select_related('user', 'category')

    context = {
        'group':            group,
        'membership':       membership,
        'is_creator':       is_creator,
        'all_memberships':  all_memberships,
        'managed_profiles': managed_profiles,
        'group_cases':      group_cases,

        # Permission flags — template uses these to show/hide sections
        # Creator always gets full access
        # Everyone else depends on their GroupMembership.permissions
        'can_view_members':   is_creator or (membership and membership.can_view_members()),
        'can_manage_members': is_creator or (membership and membership.can_manage_members()),
        'can_fill_cases':     is_creator or (membership and membership.can_fill_cases()),

        # EXPAND: add flags for custom permissions here
        # 'can_export_data': is_creator or (membership and membership.can_export_data()),
    }
    return render(request, 'groups/detail.html', context)


# ── 4. GROUP CREATE ───────────────────────────────────────────
# Creates a new group + type-specific extra info (FamilyInfo/BusinessInfo).
# Auto-adds the creator as a member so they appear in the members list.
#
# Why commit=False?
#   Gives us the Group object without saving to DB yet so we can
#   set created_by manually before the row hits the database.

@login_required
def group_create(request):
    if request.method == 'POST':
        form = GroupCreateForm(request.POST, user=request.user)
        if form.is_valid():
            group            = form.save(commit=False)
            group.created_by = request.user
            group.save()
            form.save()  # creates FamilyInfo or BusinessInfo

            # Auto-add creator as member so they appear in the members list
            GroupMembership.objects.create(
                user=request.user,
                group=group,
            )

            messages.success(request, f"Group '{group.name}' created successfully!")
            return redirect('groups:group_detail', group_id=group.id)
    else:
        form = GroupCreateForm(user=request.user)

    return render(request, 'groups/create.html', {'form': form})


# ── 5. ADD MEMBER ─────────────────────────────────────────────
# Adds an existing registered user to the group with an optional role.
# Only group creator or a member with can_manage_members can do this.
#
# form.cleaned_user is set inside AddMemberForm.clean_email()
# so we don't need to look up the user again here.

@login_required
def add_member(request, group_id):
    group                  = get_object_or_404(Group, id=group_id, is_active=True)
    is_creator, membership = get_group_access(request, group)

    if not is_creator:
        if not membership or not membership.can_manage_members():
            messages.error(request, 'You do not have permission to add members.')
            return redirect('groups:group_detail', group_id=group_id)

    if request.method == 'POST':
        form = AddMemberForm(request.POST, group=group)
        if form.is_valid():
            GroupMembership.objects.create(
                user=form.cleaned_user,
                group=group,
                role=form.cleaned_data.get('role'),
            )
            messages.success(request, f'{form.cleaned_data["email"]} added to the group.')
            return redirect('groups:group_detail', group_id=group_id)
    else:
        form = AddMemberForm(group=group)

    return render(request, 'groups/add_member.html', {
        'form':  form,
        'group': group,
    })


# ── 6. CREATE MANAGED PROFILE ─────────────────────────────────
# Creates an interior person (ManagedProfile) inside a group.
# This person has no account — the group leader manages them.
#
# request.FILES is required because ManagedProfile has ImageFields
# (passport_picture, profile_picture). Without it uploads are silently ignored.

@login_required
def create_managed_profile(request, group_id):
    group                  = get_object_or_404(Group, id=group_id, is_active=True)
    is_creator, membership = get_group_access(request, group)

    if not is_creator:
        if not membership or not membership.can_manage_members():
            messages.error(request, 'You cannot add profiles to this group.')
            return redirect('groups:group_detail', group_id=group_id)

    if request.method == 'POST':
        form = ManagedProfileForm(request.POST, request.FILES)
        if form.is_valid():
            managed            = form.save(commit=False)
            managed.created_by = request.user
            managed.group      = group
            managed.save()
            messages.success(request, f'Profile for {managed.full_name()} created.')
            return redirect('groups:group_detail', group_id=group_id)
    else:
        form = ManagedProfileForm()

    return render(request, 'groups/managed_profile_form.html', {
        'form':  form,
        'group': group,
    })


# ── 7. FILL CASE FOR MANAGED PROFILE ─────────────────────────
# Fills case requirements on behalf of a managed profile (interior person).
#
# Case lookup now uses managed_profile FK directly:
#   get_object_or_404(Case, id=case_id, managed_profile=managed)
#   This is safe — a user can't access a case that doesn't belong
#   to this managed profile even if they guess the case_id.
#
# Reuses RequirementForm from cases/forms.py — same dynamic form system,
# no need to rebuild it. Just pass the right requirements and case.
#
# EXPAND: add a separate view to CREATE a new case for a managed profile.

@login_required
def fill_case_for_managed(request, group_id, managed_id, case_id):
    group                  = get_object_or_404(Group, id=group_id, is_active=True)
    is_creator, membership = get_group_access(request, group)

    # Must have can_fill_cases permission
    if not is_creator:
        if not membership or not membership.can_fill_cases():
            messages.error(request, 'You do not have permission to fill cases.')
            return redirect('groups:group_detail', group_id=group_id)

    # Managed profile must belong to this group — prevents cross-group access
    managed = get_object_or_404(ManagedProfile, id=managed_id, group=group)

    # Case must belong to this specific managed profile
    # managed_profile=managed ensures a guessed case_id from another profile won't work
    from cases.models import Case, CaseAnswer
    from cases.forms import RequirementForm, build_initial, save_answers

    case = get_object_or_404(
        Case,
        id=case_id,
        managed_profile=managed,  # ← direct FK — clean and safe
        is_active=True
    )

    requirements     = case.category.requirements.all()
    existing_answers = CaseAnswer.objects.filter(case=case)
    initial          = build_initial(existing_answers)

    if request.method == 'POST':
        form = RequirementForm(
            requirements,
            data=request.POST,
            files=request.FILES,
            initial=initial,
        )
        if form.is_valid():
            save_answers(form, case, requirements)
            messages.success(request, f'Answers saved for {managed.full_name()}.')
            return redirect('groups:group_detail', group_id=group_id)
    else:
        form = RequirementForm(requirements, initial=initial)

    return render(request, 'groups/fill_case.html', {
        'form':    form,
        'managed': managed,
        'case':    case,
        'group':   group,
    })