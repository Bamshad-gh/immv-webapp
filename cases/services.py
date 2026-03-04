# cases/services.py
# ─────────────────────────────────────────────────────────────
# Business logic that belongs neither in models (too tied to views)
# nor in views (too complex to repeat). Import from here in views.
#
# What's here:
#   1. resolve_profile_value()      — maps a profile_mapping dot-path to a Python value
#   2. compute_eligibility_score()  — checks a user's eligibility for a category
#
# EXPAND: add more service functions here as complexity grows
#   e.g. case_auto_fill(), notification_batch_send(), invoice_generate()
# ─────────────────────────────────────────────────────────────


# ── 1. PROFILE VALUE RESOLVER ────────────────────────────────
def resolve_profile_value(user, mapping):
    """
    Resolves a profile_mapping dot-path string against a User object.
    Returns the raw Python value (date, string, None) or None if not resolvable.

    Supported mapping formats:
      'profile.date_of_birth'  → user.profile.date_of_birth  (explicit path)
      'date_of_birth'          → user.profile.date_of_birth  (shorthand — tries profile first)
      'email'                  → user.email                  (User-level field)
      'first_name'             → user.first_name             (User-level OR profile, tries User first)

    WHY try/except at the top level:
      Profile fields are nullable. The user may not have filled them in.
      getattr(..., None) prevents AttributeError but a chain of None.attr would still
      raise AttributeError — the outer except catches that silently.

    WHY not use eval() or importlib:
      Dot-path traversal via getattr is safe and explicit. eval() on admin-entered
      strings would be a severe security vulnerability.
    """
    if not mapping:
        return None
    try:
        parts = mapping.strip().split('.')

        # Walk the dot-path starting from the user object
        value = user
        for part in parts:
            value = getattr(value, part, None)
            if value is None:
                break

        # If we ended up back at the user object itself (mapping was a single word
        # that isn't a direct User attribute), try user.profile.<mapping> as shorthand.
        # Example: 'date_of_birth' → user doesn't have it → try user.profile.date_of_birth
        if value is user:
            profile = getattr(user, 'profile', None)
            value   = getattr(profile, mapping, None) if profile else None

        return value
    except Exception:
        # Safety net: any unexpected error (missing profile, wrong type, etc.)
        # returns None so the caller treats it as "no data" rather than crashing.
        return None


# ── 2. ELIGIBILITY SCORING ENGINE ────────────────────────────
def compute_eligibility_score(user, category):
    """
    Checks a user's eligibility for a given category by evaluating all
    eligibility-gate requirements (is_eligibility=True) linked to it.

    Returns a dict:
    {
      'score':   80,        # int 0–100 (passed / answered * 100)
      'passed':  4,         # requirements that passed
      'failed':  1,         # requirements that failed (user doesn't qualify)
      'unknown': 0,         # requirements with no data source to evaluate
      'total':   5,         # total eligibility requirements in this category
      'details': [
        {
          'id':           int,                  # Requirement.id
          'name':         str,                  # Requirement.name
          'passed':       True | False | None,  # None = unknown (no answer)
          'source':       'profile' | 'quiz' | None,
          'fail_message': str | None,           # shown to user if failed
        },
        ...
      ]
    }

    Score formula: passed / (passed + failed) * 100
    WHY exclude unknown from denominator:
      We can't penalise the user for data we don't have. If a profile field
      isn't filled in and no quiz answer exists, we mark it "unknown" and skip it.
      EXPAND: make this configurable per-category if stricter scoring is needed.

    Answer source priority:
      1. profile_mapping  →  resolve_profile_value(user, req.profile_mapping)
      2. EligibilityAnswer  →  quiz answers stored for this (user, requirement)
      3. None  →  unknown
    """
    from cases.models import CategoryRequirement
    from users.models import EligibilityAnswer

    # Fetch all active eligibility-gate requirements for this category.
    # We only look at the category's OWN requirements (not inherited) to keep
    # scores consistent with what the user sees on the category page.
    # EXPAND: include inherited requirements by walking parent chain if needed.
    elig_crs = (
        CategoryRequirement.objects
        .filter(category=category, requirement__is_eligibility=True, is_active=True)
        .select_related('requirement')
        .order_by('order', 'requirement__name')
    )

    if not elig_crs.exists():
        # No eligibility requirements → 100% eligible by definition
        return {
            'score': 100, 'passed': 0, 'failed': 0,
            'unknown': 0, 'total': 0, 'details': [],
        }

    # Pre-fetch all EligibilityAnswer rows for this user in one query.
    # WHY pre-fetch: avoids N+1 — one query instead of one per requirement.
    req_ids  = [cr.requirement_id for cr in elig_crs]
    quiz_map = {
        ea.requirement_id: ea
        for ea in EligibilityAnswer.objects.filter(user=user, requirement_id__in=req_ids)
    }

    passed  = 0
    failed  = 0
    unknown = 0
    details = []

    for cr in elig_crs:
        req    = cr.requirement
        value  = None
        source = None

        # Priority 1: auto-fill from user's Profile via profile_mapping
        if req.profile_mapping:
            value = resolve_profile_value(user, req.profile_mapping)
            if value is not None:
                source = 'profile'

        # Priority 2: manual quiz answer stored in EligibilityAnswer
        if value is None and req.id in quiz_map:
            value = quiz_map[req.id].get_value()
            if value is not None:
                source = 'quiz'

        # No data at all — cannot evaluate
        if value is None:
            unknown += 1
            details.append({
                'id':           req.id,
                'name':         req.name,
                'passed':       None,   # None signals "unknown" to the UI
                'source':       None,
                'fail_message': None,
            })
            continue

        # Evaluate the condition using the existing check_eligibility() method
        is_eligible = req.check_eligibility(value)

        if is_eligible:
            passed += 1
        else:
            failed += 1

        details.append({
            'id':           req.id,
            'name':         req.name,
            'passed':       is_eligible,
            'source':       source,
            # Only include fail_message when they actually failed — no noise otherwise
            'fail_message': req.eligibility_fail_message if not is_eligible else None,
        })

    # Score = passed / answered * 100
    # answered = passed + failed (unknown excluded from denominator)
    answered = passed + failed
    score    = round(passed / answered * 100) if answered > 0 else 100

    return {
        'score':   score,
        'passed':  passed,
        'failed':  failed,
        'unknown': unknown,
        'total':   len(req_ids),
        'details': details,
    }
