from django.db import models
from django.utils.text import slugify


# cases/models.py
# ─────────────────────────────────────────────────────────────
# Models (in order):
#   1.  Service              — top-level grouping (e.g. "Immigration")
#   2.  Category             — sub-categories, supports nesting
#   3.  RequirementSection   — named banks for the library (e.g. "Personal Information")
#   4.  GovernmentForm       — Phase 4: immigration form object (IMM5710, IMM5257, …)
#   5.  Requirement          — LIBRARY ITEM: reusable question, belongs to a section
#   6.  RequirementChoice    — options for 'select'-type requirements
#   7.  CategoryRequirement  — M2M bridge: Requirement ↔ Category with ordering + overrides
#   8.  FormRequirement      — Phase 4: M2M bridge: Requirement ↔ GovernmentForm
#   9.  CategoryForm         — Phase 4: M2M bridge: GovernmentForm ↔ Category
#   10. Case                 — a user's application for a category
#   11. CaseAnswer           — answers to requirements for a specific case
#   12. CaseRequirement      — per-case active/inactive tracking of requirements
#
# KEY DESIGN CHANGE (Phase 1):
#   Previously: Requirement had a direct FK to Category (one category only).
#   Now:        Requirement is a LIBRARY ITEM — it has no category FK.
#               To attach a requirement to a category, create a CategoryRequirement row.
#               One Requirement can appear in many categories (M2M via CategoryRequirement).
#
# WHY?
#   "Date of Arrival in Canada" defined once → used in 12 categories.
#   Every CaseAnswer for that question points to the same requirement_id → auto-fill works.
#   Without M2M: 12 copies of the question → 12 different requirement_ids → no auto-fill.
#
# Case ownership — three scenarios, all handled by the same Case model:
#   Personal:  user=Ali,  group=None,         managed_profile=None
#   Group:     user=Ali,  group=HassanFamily,  managed_profile=None
#   Managed:   user=Ali,  group=HassanFamily,  managed_profile=Mother
#
# 'user' is always set. 'group' and 'managed_profile' are optional context.
# ─────────────────────────────────────────────────────────────


# ── 1. SERVICE ────────────────────────────────────────────────
# Top-level grouping of categories.
# Example: Service="Immigration" → Categories=["Work Visa", "Study Permit"]
# EXPAND: add 'icon' or 'color' field for UI differentiation.

class Service(models.Model):
    name        = models.CharField(max_length=100)
    slug        = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True, null=True)
    is_active   = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        # Auto-generate slug from name on first save.
        # Appends a counter (-2, -3 …) if the slug is already taken.
        if not self.slug:
            base    = slugify(self.name)[:100]
            slug    = base
            counter = 2
            while Service.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{counter}'
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


# ── 2. CATEGORY ───────────────────────────────────────────────
# Sub-categories under a service. Supports nesting via self-referencing FK.
# Top-level categories have parent=None.
# Access children: category.subcategories.all()
# Access requirements: category.category_requirements.all()  ← via CategoryRequirement
# EXPAND: add 'order' IntegerField for custom display ordering within a service.

class Category(models.Model):
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name='categories'
    )
    parent = models.ForeignKey(
        'self',                         # self-referencing — points to same model
        on_delete=models.SET_NULL,      # parent deleted → children become top-level
        null=True, blank=True,
        related_name='subcategories'    # category.subcategories.all()
    )
    name        = models.CharField(max_length=100)
    slug        = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True, null=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    is_active   = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        # Auto-generate slug from name on first save. Duplicates get -2, -3 …
        if not self.slug:
            base    = slugify(self.name)[:100]
            slug    = base
            counter = 2
            while Category.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{counter}'
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


# ── 3. REQUIREMENT SECTION ────────────────────────────────────
# Named "shelf" in the requirement library.
# Groups related questions so admins can browse and bulk-add them to categories.
#
# Default sections (created in data migration 0006):
#   "Personal Information", "Family Information", "Travel History",
#   "Education & Career", "Documents", "Other"
#
# EXPAND: add 'icon' (emoji or CSS class) so each section has a visual marker in the builder.

class RequirementSection(models.Model):
    name        = models.CharField(max_length=100, unique=True)
    slug        = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True, null=True)
    order       = models.PositiveIntegerField(default=0)
    # 'order' drives display sorting in the builder sidebar — lower = shown first
    is_active   = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'name']    # default queryset order: by order field, then name

    def save(self, *args, **kwargs):
        # Auto-generate slug from name on first save.
        if not self.slug:
            base    = slugify(self.name)[:100]
            slug    = base
            counter = 2
            while RequirementSection.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{counter}'
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


# ── 4. GOVERNMENT FORM ────────────────────────────────────────
# Phase 4: A government immigration form as a reusable library object.
# Example: IMM 5710 "Application to Change Conditions, Extend My Stay or Remain in Canada"
#
# Relationships:
#   form.form_requirements.all()  → requirements in this form (via FormRequirement)
#   form.category_forms.all()     → categories that require this form (via CategoryForm)
#
# Deduplication — the KEY insight:
#   "Background Check" appears in IMM5710 AND IMM5257 → one Requirement object, two FormRequirement rows.
#   The same Requirement is linked to both forms → zero duplication in the library.
#
# EXPAND: add version/date field if forms are revised over time (e.g. "IMM5710 — Jan 2025 revision").

class GovernmentForm(models.Model):
    code = models.CharField(
        max_length=20,
        unique=True,
        # Short identifier used as the form_field_id prefix: 'IMM5710', 'IMM5257'
    )
    name = models.CharField(
        max_length=200,
        # Full official name: 'Application to Change Conditions, Extend My Stay...'
    )
    description = models.TextField(blank=True, null=True)
    source_url  = models.URLField(
        blank=True, null=True,
        # Official government URL — also serves as the seed URL for the future web crawler.
        # Crawler reads this page to auto-create requirements for this form.
    )
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.code} — {self.name}'

    def req_count(self):
        # How many active requirements are linked to this form.
        # Called in the service builder to show "(4 requirements)" next to the form.
        return self.form_requirements.filter(requirement__is_active=True).count()

    def category_count(self):
        # How many categories require this form.
        return self.category_forms.count()


# ── 5. REQUIREMENT ────────────────────────────────────────────
# LIBRARY ITEM — a reusable question or field.
# No longer tied to a single category. Use CategoryRequirement to attach to categories.
#
# Phase 1 adds three new types:
#   'select'    → dropdown; options come from RequirementChoice rows
#   'boolean'   → yes / no radio buttons; stored as answer_text ('yes' or 'no')
#   'info_text' → read-only information block; no answer stored at all
#
# 'profile_mapping' (renamed from auto_field_form) is a dot-path to a profile field.
# Example: "profile.date_of_birth" → Phase 2 will read user.profile.date_of_birth
# and pre-fill the answer automatically. Leave blank if no auto-fill is needed.
#
# EXPAND: add 'is_verified_required' BooleanField if certain answers need admin approval.

class Requirement(models.Model):
    TYPE_CHOICES = [
        # ── Data entry types ──────────────────────────────────────────
        ('text',      'Text Field'),       # free-form text (short or long)
        ('question',  'Question'),         # same as text but semantically a question
        ('number',    'Number'),           # decimal input
        ('date',      'Date'),             # date picker
        ('document',  'Document Upload'),  # file upload
        # ── Phase 1 new types ─────────────────────────────────────────
        ('select',    'Select / Dropdown'),# user picks from RequirementChoice list
        ('boolean',   'Yes / No'),         # radio: yes or no; stored in answer_text
        ('info_text', 'Information Block'),# read-only block; no answer stored
        # EXPAND: add new types here + matching entry in cases/forms.py field_map
    ]

    # Which section this requirement belongs to in the library.
    # null=True → "uncategorized" in the library browser (admin should assign a section).
    section = models.ForeignKey(
        RequirementSection,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='requirements'     # section.requirements.all()
    )

    type           = models.CharField(max_length=20, choices=TYPE_CHOICES)
    name           = models.CharField(max_length=100)
    description    = models.TextField(blank=True, null=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    is_active      = models.BooleanField(default=True)
    is_required    = models.BooleanField(default=True)
    # is_required is the LIBRARY DEFAULT. CategoryRequirement.is_required_override can change it per category.

    # Dot-path to a profile or managed_profile field for Phase 2 auto-fill.
    # Example: "profile.first_name"  or  "profile.date_of_birth"
    # Phase 2 resolves this: getattr(user.profile, 'first_name') → pre-fill answer.
    # EXPAND (Phase 2): see build_initial() in cases/forms.py for implementation.
    profile_mapping = models.CharField(max_length=100, blank=True, null=True)

    # Phase 3: dot-path into ManagedProfile for auto-fill when filling on behalf of an
    # interior person (someone without a login account).
    # Same syntax as profile_mapping — e.g. 'first_name', 'date_of_birth', 'passport_number'.
    # Available fields come from PersonalInfo abstract base in users/models.py:
    #   first_name, last_name, date_of_birth, gender,
    #   country_of_birth, city_of_birth, passport_number
    # EXPAND (Phase 3): see _try_managed_profile_fill() in cases/forms.py.
    managed_profile_mapping = models.CharField(
        max_length=100,
        blank=True, null=True,
        help_text="Dot-path into ManagedProfile for auto-fill when filling on behalf of an interior person. E.g. 'first_name', 'date_of_birth', 'passport_number'."
    )

    # Government form field identifier for the scraper auto-population engine.
    # Format: '<form_code>__<field_id>'  e.g. 'IMM5710__Section2_gender'
    # Phase 4 replaces this single-value field with the FormRequirement M2M which
    # supports one requirement appearing in multiple forms. This field is kept for
    # backwards compatibility and as a quick lookup key.
    # EXPAND: deprecate this once FormRequirement is fully adopted everywhere.
    form_field_id = models.CharField(max_length=100, blank=True, null=True)

    # ── Phase 4: Eligibility check fields ─────────────────────────
    # WHY: Some requirements are not data collection — they are ELIGIBILITY GATES.
    # Example: "Date of arrival in Canada" (date type, is_eligibility=True,
    #           operator='on_or_before_date', value='2025-02-28',
    #           fail_message='You did not arrive before the required cut-off date.')
    # When a user fills a case, eligibility requirements are evaluated first.
    # If any fail → the user sees their eligibility status and the fail message.
    # All eligibility checks must pass for the case to proceed to data collection.
    #
    # EXPAND: add 'eligibility_pass_message' if you want positive confirmation too.

    is_eligibility = models.BooleanField(
        default=False,
        help_text='Mark as eligibility gate: the user\'s answer is checked against a condition. '
                  'Fails block the application.'
    )

    ELIGIBILITY_OPERATOR_CHOICES = [
        # Date comparisons (for 'date' type requirements)
        ('on_or_before_date', 'On or before date'),
        ('before_date',       'Strictly before date'),
        ('on_or_after_date',  'On or after date'),
        ('after_date',        'Strictly after date'),
        # String / select comparisons
        ('equals',            'Equals'),
        ('not_equals',        'Does not equal'),
        ('contains',          'Contains text'),
        # Boolean comparisons (for 'boolean' type requirements)
        ('yes',               'Answer is Yes'),
        ('no',                'Answer is No'),
        # EXPAND: add 'in_list' for checking against a comma-separated list of values
    ]
    eligibility_operator = models.CharField(
        max_length=30,
        choices=ELIGIBILITY_OPERATOR_CHOICES,
        blank=True, null=True,
        # Which type of comparison to make — chosen by admin in service builder.
    )
    eligibility_value = models.CharField(
        max_length=200,
        blank=True, null=True,
        # The threshold to compare against.
        # date type:   '2025-02-28' (ISO format; parsed to date.fromisoformat())
        # text/select: 'canada'     (string comparison)
        # boolean:     'yes' / 'no' (not needed — use operator 'yes' / 'no' instead)
    )
    eligibility_fail_message = models.CharField(
        max_length=300,
        blank=True, null=True,
        # Shown to user when they fail this check.
        # Example: 'You did not arrive in Canada before the required cut-off date.'
    )

    def check_eligibility(self, answer_value):
        """
        Evaluates whether answer_value passes the eligibility condition.
        Returns True (eligible / pass) or False (ineligible / fail).

        Called by the case filling view when is_eligibility=True.
        answer_value is the raw Python value extracted from the CaseAnswer
        (a date object, string, Decimal, etc.) — NOT a string representation.

        EXPAND: add logging here when a user fails an eligibility check.
        """
        if not self.is_eligibility or not self.eligibility_operator:
            return True   # not an eligibility check — always pass

        from datetime import date as date_type
        op        = self.eligibility_operator
        threshold = (self.eligibility_value or '').strip()

        # ── Date comparisons ──────────────────────────────────────
        if 'date' in op:
            # answer_value should be a datetime.date object from CaseAnswer.answer_date
            if not isinstance(answer_value, date_type):
                return False   # can't compare — treat as fail
            try:
                from datetime import date
                cut_off = date.fromisoformat(threshold)   # '2025-02-28' → date(2025,2,28)
            except ValueError:
                return True    # misconfigured threshold — don't block user
            if op == 'on_or_before_date': return answer_value <= cut_off
            if op == 'before_date':       return answer_value <  cut_off
            if op == 'on_or_after_date':  return answer_value >= cut_off
            if op == 'after_date':        return answer_value >  cut_off

        # ── Boolean (yes/no) ──────────────────────────────────────
        # answer_value is 'yes' or 'no' string (stored in answer_text for boolean type)
        elif op == 'yes':  return str(answer_value).lower() == 'yes'
        elif op == 'no':   return str(answer_value).lower() == 'no'

        # ── String comparisons ────────────────────────────────────
        elif op == 'equals':     return str(answer_value).lower() == threshold.lower()
        elif op == 'not_equals': return str(answer_value).lower() != threshold.lower()
        elif op == 'contains':   return threshold.lower() in str(answer_value).lower()

        return True   # unknown operator — don't block

    def __str__(self):
        section_name = self.section.name if self.section else 'Uncategorized'
        return f'{self.name} [{section_name}]'


# ── 5. REQUIREMENT CHOICE ─────────────────────────────────────
# Options for 'select'-type requirements.
# Example: Requirement "Gender" → choices: Male, Female, Non-binary, Prefer not to say
#
# Why a separate model (not a JSONField)?
#   Each choice is a row → admin can add one, remove one, reorder — without
#   touching the requirement itself. A FK from CaseAnswer.answer_choice to
#   RequirementChoice means the stored answer is always a valid choice (referential integrity).
#
# EXPAND: add 'is_active' to soft-hide choices without deleting past answers that used them.

class RequirementChoice(models.Model):
    requirement = models.ForeignKey(
        Requirement,
        on_delete=models.CASCADE,
        related_name='choices'          # requirement.choices.all()
    )
    label = models.CharField(max_length=100)
    # 'label' is the human-readable text shown in the dropdown: "Yes", "Male", etc.

    value = models.CharField(max_length=100)
    # 'value' is the stored/exported string. Usually same as label but lowercase.
    # Example: label="Prefer not to say", value="prefer_not_to_say"

    order = models.PositiveIntegerField(default=0)
    # Controls display order in the dropdown — lower = shown first

    class Meta:
        ordering = ['order', 'label']   # default order: by order field, then alphabetical

    def __str__(self):
        return f'{self.requirement.name}: {self.label}'


# ── 6. CATEGORY REQUIREMENT ───────────────────────────────────
# The M2M bridge between Category and Requirement.
# One CategoryRequirement row = "this category uses this requirement".
# One Requirement can belong to many categories → many CategoryRequirement rows.
#
# This replaces the old Requirement.category FK.
#
# Fields:
#   order                — display position within this category (independent of other categories)
#   is_required_override — None = use requirement.is_required (library default)
#                          True = force required in THIS category even if library says optional
#                          False = force optional in THIS category even if library says required
#
# Usage:
#   category.category_requirements.filter(requirement__is_active=True).order_by('order')
#   requirement.category_requirements.all()  → see all categories using this requirement
#
# EXPAND: add 'added_by' ForeignKey(AdminProfile) to track who added this to the category.

class CategoryRequirement(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='category_requirements'    # category.category_requirements.all()
    )
    requirement = models.ForeignKey(
        Requirement,
        on_delete=models.CASCADE,
        related_name='category_requirements'    # requirement.category_requirements.all()
    )
    order = models.PositiveIntegerField(default=0)
    # Controls display order within this specific category.
    # Drag-and-drop in the builder AJAX calls /ajax/builder/category/<id>/reorder/ to update this.

    is_required_override = models.BooleanField(null=True, blank=True, default=None)
    # None  = inherit requirement.is_required (the library default)
    # True  = force required in this category regardless of library setting
    # False = force optional in this category regardless of library setting
    # Why nullable boolean? Avoids a separate 'use_default' BooleanField — cleaner model.

    class Meta:
        unique_together = ['category', 'requirement']
        ordering        = ['order']     # default: sorted by order field

    def effective_is_required(self):
        """
        Returns the actual 'required' status for this requirement in this category.
        Checks override first, falls back to the library default on the Requirement.
        Called in forms.py when building form field validation.
        """
        if self.is_required_override is not None:
            return self.is_required_override        # category-level override
        return self.requirement.is_required         # library default

    def __str__(self):
        return f'{self.requirement.name} → {self.category.name} (order={self.order})'


# ── 8. FORM REQUIREMENT ───────────────────────────────────────
# Phase 4: M2M bridge between GovernmentForm and Requirement.
# One row = "this form contains this requirement, at this position, in this section".
#
# WHY M2M instead of FK from Requirement to GovernmentForm?
#   A single Requirement can appear in multiple forms.
#   Example: "Background Check" (boolean) is in IMM5710 AND IMM5257 — same Requirement object,
#   two FormRequirement rows pointing to it. One library item, no duplication.
#
# form_section: the named section inside the form where this question appears.
#   Examples: "Personal Information", "Family Information", "Background"
#   Used in the service builder to group requirements by section visually.
#
# field_id: the specific field identifier in the government form.
#   Example: 'Section2_gender', 'Part3_arrivalDate'
#   The future crawler uses this to map scraped fields to library requirements.
#   Supersedes the legacy Requirement.form_field_id single-value field (which only
#   worked for requirements in ONE form — M2M handles multiple forms correctly).
#
# EXPAND: add 'is_required' BooleanField if some forms make a question optional while
#         others make it required (current assumption: required status comes from Requirement).

class FormRequirement(models.Model):
    form = models.ForeignKey(
        GovernmentForm,
        on_delete=models.CASCADE,
        related_name='form_requirements'    # form.form_requirements.all()
    )
    requirement = models.ForeignKey(
        Requirement,
        on_delete=models.CASCADE,
        related_name='form_requirements'    # requirement.form_requirements.all() → which forms use this
    )
    form_section = models.CharField(
        max_length=100,
        blank=True,
        # Section name inside this specific form.
        # Example: "Personal Information", "Family Background"
        # Leave blank for ungrouped / unspecified.
    )
    field_id = models.CharField(
        max_length=100,
        blank=True,
        # The government form's field identifier for this question.
        # Example: 'Section2_gender', 'Part3_arrivalDate'
        # Used by the crawler to map scraped page fields to library requirements.
    )
    order = models.PositiveIntegerField(default=0)
    # Display order within this form — lower = appears first.

    class Meta:
        unique_together = ['form', 'requirement']
        # One requirement can only be linked to the same form once.
        ordering        = ['order']

    def __str__(self):
        return f'{self.form.code} → {self.requirement.name} ({self.form_section or "–"})'


# ── 9. CATEGORY FORM ──────────────────────────────────────────
# Phase 4: M2M bridge between Category and GovernmentForm.
# One row = "this category requires this form to be completed".
#
# Example: Category "Open Work Permit Extension" requires both IMM5710 and IMM5257.
# Both forms can be reused for other categories → zero duplication.
#
# How it feeds into the case filling UX (future):
#   When a case is created for a category, the system knows which forms are needed.
#   The user sees "You need to complete IMM5710 and IMM5257" before they start.
#   Requirements from all linked forms are automatically added to the case (via CategoryRequirement
#   populated from FormRequirements, deduplicated).
#
# EXPAND: add 'is_optional' BooleanField if some forms are only conditionally required.

class CategoryForm(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='category_forms'   # category.category_forms.all()
    )
    form = models.ForeignKey(
        GovernmentForm,
        on_delete=models.CASCADE,
        related_name='category_forms'   # form.category_forms.all() → which categories need this form
    )
    order = models.PositiveIntegerField(default=0)
    # Display order among forms for this category.

    class Meta:
        unique_together = ['category', 'form']
        ordering        = ['order']

    def __str__(self):
        return f'{self.form.code} required by {self.category.name}'


# ── 10. CASE ──────────────────────────────────────────────────
# A user's application for a specific category.
#
# Three ownership scenarios — all use the same model:
#   Personal:  user=Ali, group=None,         managed_profile=None
#   Group:     user=Ali, group=HassanFamily,  managed_profile=None
#   Managed:   user=Ali, group=HassanFamily,  managed_profile=Mother
#
# 'user' is ALWAYS set — it's who created/submitted the case.
# 'group' and 'managed_profile' are optional — they add context on who it's for.

class Case(models.Model):
    STATUS_CHOICES = [
        ('pending',   'Pending'),
        ('active',    'Active'),
        ('completed', 'Completed'),
        ('rejected',  'Rejected'),
    ]

    # Always set — who created/owns this case
    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='cases'            # user.cases.all()
    )

    # Optional — null = personal case | filled = group case
    group = models.ForeignKey(
        'groups.Group',                 # string ref avoids circular import
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='cases'
    )

    # Optional — null = case is for the user | filled = case is for a managed person
    managed_profile = models.ForeignKey(
        'users.ManagedProfile',         # string ref avoids circular import
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='cases'
    )

    category   = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='cases'
    )
    status     = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes      = models.TextField(blank=True, null=True)   # admin notes
    created_at = models.DateTimeField(auto_now_add=True)
    is_active  = models.BooleanField(default=True)

    def __str__(self):
        if self.managed_profile:
            return f'Case #{self.id} - {self.managed_profile.full_name()} (via {self.user.email})'
        if self.group:
            return f'Case #{self.id} - {self.group.name} (by {self.user.email})'
        return f'Case #{self.id} - {self.user.email} - {self.category.name}'

    def get_owner_display(self):
        """
        Returns a human-readable string describing who this case is for.
        Used in templates: {{ case.get_owner_display }}
        """
        if self.managed_profile:
            return self.managed_profile.full_name()
        if self.group:
            return self.group.name
        return self.user.email


# ── 11. CASE ANSWER ───────────────────────────────────────────
# Stores a user's answer to one requirement for one specific case.
# One row per requirement per case — at most one answer per (case, requirement) pair.
# Only one answer column is filled per row — which one depends on requirement.type.
#
# answer_choice (Phase 1 addition):
#   Set when requirement.type == 'select'. Points to the chosen RequirementChoice row.
#   The choice's 'label' is shown to the user; 'value' is used in exports/conditions.
#
# is_auto_filled (Phase 2):
#   Will be set True when the answer was pre-filled from profile_mapping or from a
#   previous case answer. User can still override it.
#
# EXPAND: add 'answered_at' DateTimeField to track when the user last updated their answer.

class CaseAnswer(models.Model):
    case        = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='answers')
    requirement = models.ForeignKey(Requirement, on_delete=models.CASCADE)

    # ── Answer columns — only one filled per row ──────────────────────
    answer_text   = models.TextField(blank=True, null=True)
    # Used by: 'text', 'question', 'boolean' (stores 'yes' or 'no')

    answer_number = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    # Used by: 'number'

    answer_date   = models.DateField(blank=True, null=True)
    # Used by: 'date'

    answer_file   = models.FileField(upload_to='case_files/', blank=True, null=True)
    # Used by: 'document'

    answer_choice = models.ForeignKey(
        RequirementChoice,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='case_answers'     # answer_choice.case_answers.all()
    )
    # Used by: 'select' — FK so the stored answer is always a valid choice.
    # SET_NULL so if a choice is deleted, the answer row survives (with null choice).
    # 'info_text' requirements never have a CaseAnswer row at all.

    # ── Metadata ──────────────────────────────────────────────────────
    is_auto_filled  = models.BooleanField(default=False)
    # True = pre-filled from profile or from a previous case (Phase 2 sets this)

    edited_by_admin = models.BooleanField(default=False)
    # True = an admin manually edited this answer in the admin panel

    notify_user     = models.BooleanField(default=False)
    # True = admin edited the answer and the user should be notified

    created_at      = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.case} - {self.requirement.name}'


# ── 12. CASE REQUIREMENT ──────────────────────────────────────
# Tracks which requirements are active for a SPECIFIC CASE.
#
# Why this model?
#   By default a case inherits all requirements from its category
#   (via CategoryRequirement). But admin can customize per case:
#   - Set is_active=False to hide a requirement from only this case
#   - Set is_extra=True for requirements added manually (not from category defaults)
#   RequirementForm in forms.py filters by active CaseRequirements.
#
# When a case is created (in _create_case() helper):
#   For each CategoryRequirement on the category:
#       CaseRequirement.objects.create(case=case, requirement=cr.requirement, is_active=True)
#
# EXPAND: add 'added_by' ForeignKey(AdminProfile) to track which admin customized it.

class CaseRequirement(models.Model):
    case = models.ForeignKey(
        Case,
        on_delete=models.CASCADE,
        related_name='case_requirements'    # case.case_requirements.all()
    )
    requirement = models.ForeignKey(
        Requirement,
        on_delete=models.CASCADE,
    )
    is_active = models.BooleanField(default=True)
    # False = admin removed this requirement from this specific case only

    is_extra  = models.BooleanField(default=False)
    # True = admin added this requirement manually (not from the category's default list)

    class Meta:
        unique_together = ['case', 'requirement']

    def __str__(self):
        status = 'active' if self.is_active else 'removed'
        return f'{self.requirement.name} → Case #{self.case.id} ({status})'
