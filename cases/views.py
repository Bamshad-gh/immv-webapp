# cases/views.py
# ─────────────────────────────────────────────────────────────
# What's in this file (in order):
#   1. user_pickedCases_dashboard() — lists personal, group, managed cases
#   2. user_pickedCases_detail()    — fills requirements for a case
#
# Key change from original:
#   requirements now come from CaseRequirement (active only)
#   instead of case.category.requirements.all()
#   This respects any customization admin did per case.
# ─────────────────────────────────────────────────────────────

from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .models import Case, CaseAnswer, CaseRequirement
from .forms import RequirementForm, build_initial, save_answers
from groups.models import GroupMembership




@login_required
def user_pickedCases_dashboard(request):
    # ── Personal cases — user applied for themselves ───────────
    personal_cases = Case.objects.filter(
        user=request.user,
        group=None,
        managed_profile=None
    )

    # ── Group cases — cases under groups the user belongs to ───
    # values_list flat=True → returns [1, 3, 7] instead of [{'group_id':1}]
    user_group_ids = GroupMembership.objects.filter(
        user=request.user,
        is_active=True
    ).values_list('group_id', flat=True)

    group_cases = Case.objects.filter(
        group_id__in=user_group_ids,
        managed_profile=None
    )

    # ── Managed profile cases — cases for people this user manages
    managed_cases = Case.objects.filter(
        managed_profile__created_by=request.user
    )

    return render(request, 'cases/user_pickedCases_dashboard.html', {
        'personal_cases': personal_cases,
        'group_cases':    group_cases,
        'managed_cases':  managed_cases,
    })


@login_required
def user_pickedCases_detail(request, case_id):
    # ── GET CASE ──────────────────────────────────────────────
    case = get_object_or_404(Case, id=case_id, is_active=True)

    # ── ACCESS CHECK ──────────────────────────────────────────
    # Allow access if ANY of these are true:
    #   1. They submitted the case themselves (case.user == requester)
    #   2. They created the managed profile AND created_by is not null
    #      (Phase 3: created_by is now nullable — group-level profiles have no specific owner)
    #   3. They are an active group member with can_fill_cases permission
    #      This also covers managed profiles where created_by is null — any authorized
    #      group member can fill cases for any managed profile in their group.
    is_case_owner    = (case.user == request.user)
    is_profile_owner = (
        case.managed_profile and
        case.managed_profile.created_by is not None and
        case.managed_profile.created_by == request.user
    )
    is_group_member_with_permission = False

    # Check group membership — covers both group cases AND managed profile cases
    # (managed profile's group is used when the case has no direct group FK)
    check_group = case.group or (case.managed_profile and case.managed_profile.group)
    if check_group:
        try:
            membership = GroupMembership.objects.get(
                user=request.user,
                group=check_group,
                is_active=True
            )
            is_group_member_with_permission = membership.can_fill_cases()
        except GroupMembership.DoesNotExist:
            pass

    if not any([is_case_owner, is_profile_owner, is_group_member_with_permission]):
        messages.error(request, 'You do not have access to this case.')
        return redirect('cases:dashboard')

    # ── GET REQUIREMENTS ──────────────────────────────────────
    # Use CaseRequirement instead of case.category.requirements.all()
    # This respects any customization admin made for this specific case:
    #   - requirements admin removed → is_active=False → excluded here
    #   - requirements admin added extra → is_extra=True → included here
    requirements = CaseRequirement.objects.filter(
        case=case,
        is_active=True
    ).select_related('requirement')

    # Extract the actual Requirement objects for RequirementForm
    # RequirementForm expects Requirement objects, not CaseRequirement objects
    requirement_objects = [cr.requirement for cr in requirements]

    # Phase 2: pass case + user + requirements so build_initial() can auto-fill
    # from profile_mapping and from previous case answers.
    # select_related fetches answer_choice in the same query (avoids N+1 for select-type answers).
    existing_answers = (
        CaseAnswer.objects
        .filter(case=case)
        .select_related('requirement', 'answer_choice')
    )
    initial, auto_filled_ids = build_initial(
        existing_answers,
        case         = case,
        user         = request.user,
        requirements = requirement_objects,
    )
    # auto_filled_ids: set of requirement IDs pre-filled by the system (not the user).
    # Passed to the template to show "Auto-filled ✓" badges next to those fields.

    # ── POST — validate and save ──────────────────────────────
    if request.method == 'POST':
        form = RequirementForm(
            requirement_objects,
            data=request.POST,
            files=request.FILES,
            initial=initial
        )
        if form.is_valid():
            save_answers(form, case, requirement_objects, auto_filled_ids=auto_filled_ids)
            messages.success(request, 'Answers saved successfully!')
            return redirect('cases:case-detail', case_id=case_id)

    # ── GET — show prefilled form ─────────────────────────────
    else:
        form = RequirementForm(requirement_objects, initial=initial)

    # Convert auto_filled_ids set to a list of HTML field names for the template.
    # Field names match RequirementForm's naming pattern: 'req_<id>'.
    # The template uses this list to add auto-fill badges via JavaScript.
    auto_filled_fields = [f'req_{rid}' for rid in auto_filled_ids]

    return render(request, 'cases/user_pickedCases_detail.html', {
        'case':               case,
        'form':               form,
        'requirements':       requirement_objects,   # for info_text display
        'auto_filled_fields': auto_filled_fields,    # list of field names — for JS badge rendering
        'auto_filled_ids':    auto_filled_ids,       # original set — for save_answers on POST
    })