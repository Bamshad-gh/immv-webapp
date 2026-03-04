from django import forms

# cases/forms.py
# ─────────────────────────────────────────────────────────────
# Dynamic form builder for case requirements.
#
# Phase 1 additions:
#   - 'select'    → ChoiceField dropdown; options loaded from RequirementChoice rows
#   - 'boolean'   → ChoiceField with RadioSelect (Yes / No)
#   - 'info_text' → NOT added as a form field at all (display-only in the template)
#
# How to add a new type in future (EXPAND):
#   1. Add the type to Requirement.TYPE_CHOICES in cases/models.py
#   2. Add one lambda to field_map in RequirementForm._field_for_type()
#   3. Add one entry to type_to_field in build_initial() and save_answers()
#   4. Done — nothing else changes.
# ─────────────────────────────────────────────────────────────


class RequirementForm(forms.BaseForm):
    """
    A dynamic form that builds its fields from database Requirement objects.

    USAGE:
        # 'requirements' = list of Requirement model instances to show as form fields
        form = RequirementForm(requirements, data=request.POST, files=request.FILES, initial=initial)

    KEY BEHAVIOUR:
        - 'info_text' requirements are NOT added as form fields.
          The template must handle them separately (render as a <div> info block).
        - 'select' requirements need their choices loaded at form build time
          (done inside _field_for_type via req.choices.all()).
        - Field validation (required=True/False) respects the CategoryRequirement.effective_is_required()
          value if a CategoryRequirement is passed via the 'cr_map' kwarg (see __init__).

    REUSE:
        Drop this class into any Django project with a Requirement model that has
        a 'type' field and a 'choices' reverse relation. Adjust type names in field_map.
    """

    def __init__(self, requirements, *args, cr_map=None, **kwargs):
        # cr_map: optional dict {requirement_id: CategoryRequirement}
        # If provided, use effective_is_required() per category instead of req.is_required.
        # This allows the same requirement to be optional in one category but required in another.
        # EXPAND (Phase 1 usage): pass cr_map from the view that renders the case fill form.
        self.cr_map = cr_map or {}

        # Build fields BEFORE calling super().__init__() because BaseForm reads
        # base_fields during __init__. Setting base_fields here is how Django's
        # BaseForm allows us to create fields dynamically.
        self.base_fields = self._build_fields(requirements)
        super().__init__(*args, **kwargs)

    def _build_fields(self, requirements):
        """
        Loops through requirements and creates one Django form field per requirement.
        Returns a dict: {'req_5': Field, 'req_12': Field, ...}

        'info_text' requirements are SKIPPED — they have no answer to collect.
        """
        fields = {}
        for req in requirements:
            if req.type == 'info_text':
                # info_text = display-only; no form field, no answer saved.
                # The template checks req.type and renders a styled <div> instead.
                continue

            field_name        = f'req_{req.id}'     # e.g. 'req_5' — unique per requirement
            fields[field_name] = self._field_for_type(req)
        return fields

    def _field_for_type(self, req):
        """
        Maps a Requirement's type string to a Django form field instance.

        TO ADD A NEW TYPE (EXPAND):
            Add one line to field_map:
                'your_type': lambda: forms.YourField(...)
            That's it. Nothing else changes.

        field_map uses lambdas so a fresh field instance is created for each
        requirement — fields are NOT shared between form instances.
        """

        # Determine whether this field should be required.
        # If a CategoryRequirement was passed (cr_map), use its effective_is_required()
        # which respects per-category overrides. Otherwise fall back to req.is_required.
        cr = self.cr_map.get(req.id)
        is_required = cr.effective_is_required() if cr else req.is_required

        field_map = {
            # ── Existing types ────────────────────────────────────────────
            'text': lambda: forms.CharField(
                widget    = forms.Textarea(attrs={'rows': 4, 'placeholder': f'Enter {req.name}...'}),
                required  = is_required,
                label     = req.name,
                help_text = req.description or '',
            ),
            'question': lambda: forms.CharField(
                widget    = forms.Textarea(attrs={'rows': 4, 'placeholder': f'Answer {req.name}...'}),
                required  = is_required,
                label     = req.name,
                help_text = req.description or '',
            ),
            'number': lambda: forms.DecimalField(
                required  = is_required,
                label     = req.name,
                help_text = req.description or '',
                widget    = forms.NumberInput(attrs={'placeholder': '0.00'}),
            ),
            'date': lambda: forms.DateField(
                required  = is_required,
                label     = req.name,
                help_text = req.description or '',
                widget    = forms.DateInput(attrs={'type': 'date'}),
                # type='date' tells the browser to show a native date picker
            ),
            'document': lambda: forms.FileField(
                required  = is_required,
                label     = req.name,
                help_text = req.description or '',
            ),

            # ── Phase 1 new types ─────────────────────────────────────────
            'select': lambda: forms.ChoiceField(
                # Load choices from RequirementChoice rows ordered by 'order' field.
                # The empty first choice ('', '— Select …') prompts the user to pick.
                choices   = [('', f'— Select {req.name} —')] + [
                    (c.value, c.label)
                    for c in req.choices.order_by('order')
                    # c.value is stored in the DB; c.label is what the user sees.
                ],
                required  = is_required,
                label     = req.name,
                help_text = req.description or '',
            ),
            'boolean': lambda: forms.ChoiceField(
                # Two radio buttons: Yes / No
                # Stored as the string 'yes' or 'no' in CaseAnswer.answer_text.
                choices   = [('', '— Select —'), ('yes', 'Yes'), ('no', 'No')],
                widget    = forms.RadioSelect,
                required  = is_required,
                label     = req.name,
                help_text = req.description or '',
            ),
            # EXPAND: add new types here. E.g.:
            # 'url': lambda: forms.URLField(required=is_required, label=req.name),
        }

        # Get the builder for this type.
        # Fallback to CharField so unknown types still work rather than crash.
        builder = field_map.get(
            req.type,
            lambda: forms.CharField(
                required  = is_required,
                label     = req.name,
                help_text = req.description or '',
            ),
        )
        return builder()    # call lambda to create the field instance


def _extract_answer_value(answer):
    """
    Extracts the right value from a CaseAnswer row based on its requirement type.

    Used by build_initial() and _try_cross_case_fill() to avoid repeating
    the type-switch logic in multiple places.

    Returns the Python value (str, Decimal, date, File, etc.) or None.
    """
    if answer is None:
        return None

    req_type = answer.requirement.type

    if req_type == 'select':
        # select → value string from the chosen RequirementChoice (e.g. 'male')
        return answer.answer_choice.value if answer.answer_choice else None

    elif req_type in ('text', 'question', 'boolean'):
        return answer.answer_text           # 'boolean' stored as 'yes' / 'no'

    elif req_type == 'number':
        return answer.answer_number

    elif req_type == 'date':
        return answer.answer_date

    elif req_type == 'document':
        return answer.answer_file           # FieldFile — Django handles display in template

    # info_text never has a CaseAnswer row → return None
    return None


def _try_profile_fill(req, user):
    """
    Resolves req.profile_mapping dot-path against the user object.

    Examples:
        profile_mapping = 'profile.date_of_birth'  → user.profile.date_of_birth
        profile_mapping = 'email'                   → user.email
        profile_mapping = 'profile.first_name'      → user.profile.first_name

    Returns the resolved value or None if the path is blank, broken, or empty string.

    WHY dot-path?
        profile_mapping is stored as a plain string like "profile.date_of_birth".
        Splitting on '.' and calling getattr() repeatedly walks any depth of related objects.
        This avoids hard-coding which attributes to check — admin sets the mapping in the
        service builder, Phase 2 just resolves whatever path was stored.

    EXPAND (future): support 'managed_profile.first_name' for managed profile auto-fill.
    """
    if not req.profile_mapping:
        return None

    try:
        obj = user
        for part in req.profile_mapping.split('.'):
            # Walk each segment of the path. getattr with None default is safe —
            # if any segment doesn't exist, we get None and return None below.
            obj = getattr(obj, part, None)
            if obj is None:
                return None         # path broken at this segment → nothing to fill

        # Reject empty strings so we don't pre-fill a blank value as if it were data.
        return obj if obj != '' else None

    except Exception:
        # Defensive: if anything unexpected happens (e.g. model method raises),
        # silently skip rather than crashing the form.
        return None


def _try_managed_profile_fill(req, managed_profile):
    """
    Resolves req.managed_profile_mapping dot-path against the ManagedProfile object.

    Examples:
        managed_profile_mapping = 'first_name'       → managed_profile.first_name
        managed_profile_mapping = 'date_of_birth'    → managed_profile.date_of_birth
        managed_profile_mapping = 'passport_number'  → managed_profile.passport_number

    Available fields come from PersonalInfo abstract base (users/models.py):
        first_name, last_name, date_of_birth, gender,
        country_of_birth, city_of_birth, passport_number

    Returns the resolved value or None if the mapping is blank, broken, or empty.

    WHY separate from _try_profile_fill?
        Profile resolves from user.profile.* — a related object on the User model.
        ManagedProfile is resolved directly from the managed_profile object.
        The path depth is different, but the resolution logic is the same.

    EXPAND (Phase 4): add support for nested paths if ManagedProfile gets related models.
    """
    if not req.managed_profile_mapping or managed_profile is None:
        return None

    try:
        obj = managed_profile
        for part in req.managed_profile_mapping.split('.'):
            obj = getattr(obj, part, None)
            if obj is None:
                return None
        return obj if obj != '' else None
    except Exception:
        return None


def _try_managed_cross_case_fill(req, managed_profile, current_case):
    """
    Looks for the most recent answer to the same requirement in any OTHER case
    belonging to this managed profile.

    WHY separate from _try_cross_case_fill?
        Regular cross-case reuse queries case__user=user.
        For managed profiles there is no login user — the case is owned by the group
        leader (case.user = leader) but associated with the managed profile via
        case.managed_profile. So we query case__managed_profile=managed_profile instead.

    Returns the extracted value or None.
    """
    from .models import CaseAnswer   # local import to avoid circular import

    if managed_profile is None or current_case is None:
        return None

    prev = (
        CaseAnswer.objects
        .filter(case__managed_profile=managed_profile, requirement=req)
        .exclude(case=current_case)
        .select_related('answer_choice', 'requirement')
        .order_by('-case__created_at')
        .first()
    )
    return _extract_answer_value(prev) if prev else None


def _try_cross_case_fill(req, user, current_case):
    """
    Looks for the most recent answer to the same requirement in any OTHER case
    belonging to this user.

    WHY cross-case reuse?
        "Date of Arrival" answered in Case A should auto-fill in Case B without
        the user re-entering it. Because we use one Requirement row for all cases,
        CaseAnswer.requirement_id is the same across cases → one query finds past answers.

    Returns the extracted value (via _extract_answer_value) or None.

    Skipped silently if current_case is None (e.g. new unsaved case).
    """
    from .models import CaseAnswer   # local import to avoid circular import at module level

    if current_case is None or user is None:
        return None

    prev = (
        CaseAnswer.objects
        .filter(case__user=user, requirement=req)   # same user, same requirement
        .exclude(case=current_case)                  # not this case
        .select_related('answer_choice', 'requirement')
        .order_by('-case__created_at')               # most recent case first
        .first()
    )
    return _extract_answer_value(prev) if prev else None


def build_initial(existing_answers, case=None, user=None, managed_profile=None, requirements=None):
    """
    Builds the 'initial' dict for pre-filling the RequirementForm.

    Phase 3 priority order (higher = wins):
        1. Existing saved answer for THIS case (user already answered it — never overwritten)
        2. Managed profile fill (req.managed_profile_mapping → managed_profile.field)
           — interior person's own data is most specific; tried first when available
        3. User profile fill (req.profile_mapping → user.profile.field)
           — tried even for managed-profile cases; filling gaps when managed_profile_mapping
           is not set but profile_mapping is (e.g. shared address, group name)
        4. Managed cross-case reuse (same req answered in this managed profile's previous case)
        5. User cross-case reuse (same req answered in this user's previous cases — last resort)

    USAGE — personal case:
        initial, auto_filled_ids = build_initial(
            existing_answers, case=case, user=request.user, requirements=reqs
        )

    USAGE — managed profile case:
        initial, auto_filled_ids = build_initial(
            existing_answers,
            case=case,
            user=request.user,          # managing user — fills gaps via profile_mapping
            managed_profile=managed,    # interior person — fills via managed_profile_mapping
            requirements=reqs,
        )

    Returns:
        initial         — dict {'req_5': value, ...} for RequirementForm
        auto_filled_ids — set of requirement IDs that were auto-filled (not user-entered)
                          used by the template to show 'Auto-filled ✓' badges and by
                          save_answers() to mark CaseAnswer.is_auto_filled = True

    BACKWARDS COMPAT:
        Callers that only pass existing_answers still work — they just get no auto-fill.
    """

    # ── Step 1: existing saved answers (existing behaviour, unchanged) ────
    # Build lookup dict: requirement_id → True (just need to know what's answered)
    already_answered = {}
    initial = {}

    for answer in existing_answers:
        field_name = f'req_{answer.requirement.id}'
        val = _extract_answer_value(answer)
        if val is not None:
            initial[field_name] = val
        already_answered[answer.requirement_id] = True
    # WHY build already_answered separately?
    # An answer row might exist but have val=None (e.g. blank file field).
    # We still want to mark it as "answered" so we don't overwrite with auto-fill.

    auto_filled_ids = set()

    # ── Steps 2-5: auto-fill — runs when requirements + at least one source is provided ──
    if requirements and (user or managed_profile):
        for req in requirements:
            # Skip: already answered by user, or display-only info_text
            if req.id in already_answered or req.type == 'info_text':
                continue

            key    = f'req_{req.id}'
            filled = None

            # Priority 2: interior person's own data — most specific source
            if managed_profile:
                filled = _try_managed_profile_fill(req, managed_profile)

            # Priority 3: managing user's profile — fills gaps (profile_mapping set, no mp_mapping)
            if filled is None and user:
                filled = _try_profile_fill(req, user)

            # Priority 4: managed profile's cross-case history
            if filled is None and managed_profile:
                filled = _try_managed_cross_case_fill(req, managed_profile, case)

            # Priority 5: managing user's cross-case history — last resort
            if filled is None and user:
                filled = _try_cross_case_fill(req, user, case)

            if filled is not None:
                initial[key] = filled
                auto_filled_ids.add(req.id)
                # auto_filled_ids → template (badge display) + save_answers() (is_auto_filled=True)

    return initial, auto_filled_ids


def save_answers(form, case, requirements, auto_filled_ids=None):
    """
    Saves or updates CaseAnswer rows from cleaned form data.

    USAGE:
        if form.is_valid():
            save_answers(form, case, requirements, auto_filled_ids=auto_filled_ids)

    Separated from the view so it can be reused in user view, admin view,
    and fill_case_for_managed without duplicating logic.

    Phase 1: handles 'select' (saves FK to RequirementChoice) and 'boolean' (saves to answer_text).
    Phase 2: adds auto_filled_ids parameter — requirement IDs that were pre-filled by the system.
             After saving, marks those CaseAnswer rows with is_auto_filled=True.
             This lets admin reports / Phase 3 know which answers came from automation.

    'info_text' requirements are silently skipped (no CaseAnswer to create).
    """
    from .models import CaseAnswer, RequirementChoice

    # Maps requirement type to the correct CaseAnswer field.
    # 'select' handled separately below (needs a FK lookup).
    type_to_field = {
        'document': 'answer_file',
        'number':   'answer_number',
        'date':     'answer_date',
        'text':     'answer_text',
        'question': 'answer_text',
        'boolean':  'answer_text',   # stored as 'yes' or 'no' string
    }

    for requirement in requirements:
        if requirement.type == 'info_text':
            # info_text has no answer field → nothing to save
            continue

        field_name = f'req_{requirement.id}'
        answer     = form.cleaned_data.get(field_name)

        if not answer and answer != 0:
            # Skip empty answers (user left the field blank).
            # '!= 0' ensures we save numeric 0 answers (otherwise `if not 0` would skip them).
            continue

        if requirement.type == 'select':
            # 'answer' here is the 'value' string from the ChoiceField (e.g. 'male').
            # Look up the RequirementChoice row with that value to store the FK.
            try:
                choice = RequirementChoice.objects.get(
                    requirement = requirement,
                    value       = answer,
                )
            except RequirementChoice.DoesNotExist:
                # Value was submitted but no matching choice exists — skip.
                # This can happen if choices were changed after the form was rendered.
                continue

            CaseAnswer.objects.update_or_create(
                case        = case,
                requirement = requirement,
                defaults    = {
                    'answer_choice': choice,
                    'answer_text':   None,      # clear other answer fields
                    'answer_number': None,
                    'answer_date':   None,
                    'answer_file':   None,
                },
            )

        else:
            # Standard types: store the value in the correct answer_* column.
            answer_field = type_to_field.get(requirement.type, 'answer_text')

            CaseAnswer.objects.update_or_create(
                case        = case,
                requirement = requirement,
                defaults    = {answer_field: answer},
                # update_or_create:
                #   → row exists (case + requirement) → UPDATE the defaults dict
                #   → row doesn't exist              → CREATE with case + requirement + defaults
            )

    # ── Phase 2: mark auto-filled answers ─────────────────────────────────
    # If the caller passed auto_filled_ids (from build_initial()), mark those
    # CaseAnswer rows with is_auto_filled=True so admin reports and Phase 3
    # conditions can distinguish system-filled answers from user-entered ones.
    # One bulk UPDATE query — no loop needed.
    if auto_filled_ids:
        CaseAnswer.objects.filter(
            case=case,
            requirement_id__in=auto_filled_ids,
        ).update(is_auto_filled=True)
